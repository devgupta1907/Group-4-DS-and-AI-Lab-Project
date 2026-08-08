"""Run the resume-parsing evaluation against the gold set and log to LangSmith.

    uv run python -m evals.run_eval --check                     # plumbing only, no model calls
    uv run python -m evals.run_eval --variant baseline          # one prompt, dev split
    uv run python -m evals.run_eval --all-variants              # the comparison run
    uv run python -m evals.run_eval --variant baseline --split test   # once, at the end

This deliberately bypasses the router, the database and Fernet encryption: it
calls the pipeline stages directly, so 35 resumes cost 35 model calls and zero
rows. It is a harness, not a second implementation — routing, preprocessing,
normalisation and validation are the very functions production runs.

Living outside `src/` is intentional. `.importlinter` scopes its contracts to
`root_packages = src`, so the "internals are private" rule still holds for every
shipped module while this harness reaches in.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from pathlib import Path
from threading import Lock
from time import perf_counter

from dotenv import load_dotenv
from langsmith import Client, traceable

load_dotenv()

from evals import gold, metrics  # noqa: E402
from evals.prompts import VARIANTS  # noqa: E402
from src.core.config import get_settings  # noqa: E402
from src.resume_parsing.internal.document_conversion.docling import (  # noqa: E402
    build_docling_converter,
)
from src.resume_parsing.internal.pipeline import (  # noqa: E402
    extraction,
    postprocess,
    preprocess,
    routing,
)
from src.resume_parsing.internal.providers.google_ai_studio import (  # noqa: E402
    build_provider,
)

DATASET = "resume-parsing-gold"
INPUT_STRATEGIES = ("direct_vision", "docling_text")


class MetricsRecorder:
    """Append de-identified stage timings for screenshots and local analysis."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

    def write(self, row: dict) -> None:
        with self._lock, self._path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, sort_keys=True) + "\n")


# ------------------------------------------------------------------ dataset --


def ensure_dataset(client: Client, split: str) -> str:
    """Create or top up the LangSmith dataset for one split. Idempotent."""
    name = f"{DATASET}-{split}"
    examples = gold.load(split)
    if not examples:
        raise SystemExit(f"No annotated gold records in split {split!r}.")

    if client.has_dataset(dataset_name=name):
        dataset = client.read_dataset(dataset_name=name)
    else:
        dataset = client.create_dataset(
            dataset_name=name,
            description=(
                f"Milestone-2 resume gold set, {split} split ({len(examples)} resumes, "
                "43 canonical categories). Reference outputs conform to "
                "parsed_resume_schema.json."
            ),
        )

    existing = {
        e.inputs.get("resume_id")
        for e in client.list_examples(dataset_id=dataset.id)
    }
    missing = [e for e in examples if e.resume_id not in existing]
    if missing:
        client.create_examples(
            dataset_id=dataset.id,
            examples=[
                {"inputs": e.inputs, "outputs": e.profile, "metadata": {"split": split}}
                for e in missing
            ],
        )
        print(f"  + added {len(missing)} example(s) to {name}")
    print(f"  dataset {name}: {len(examples)} example(s)")
    return name


# ------------------------------------------------------------------- target --


def make_target(variant: str, input_strategy: str, recorder: MetricsRecorder):
    """Build the function LangSmith calls once per dataset example."""
    settings = get_settings()
    prompt = VARIANTS[variant]
    provider = build_provider(system_prompt=prompt)
    model = settings.resume_primary_model
    converter = build_docling_converter() if input_strategy == "docling_text" else None

    @traceable(name=f"parse_resume[{variant}]", run_type="chain")
    def target(inputs: dict) -> dict:
        total_started = perf_counter()
        path = gold.GOLD_DIR / inputs["pdf"]
        content = path.read_bytes()
        document = routing.route(path.name, "application/pdf", content)
        pages = []
        preprocess_seconds = 0.0
        input_units = 0
        try:
            preprocess_started = perf_counter()
            if converter is None:
                pages = preprocess.to_pages(document)
            else:
                pages = preprocess.text_artifact(converter.convert(document))
            preprocess_seconds = perf_counter() - preprocess_started
            input_units = sum(
                len(page.text or "")
                if page.text is not None
                else len(page.image_png or b"")
                for page in pages
            )
            model_started = perf_counter()
            raw = asyncio.run(
                extraction.extract_pages(provider, pages, model=model)
            )
            model_seconds = perf_counter() - model_started
            profile = postprocess.merge(raw).model_dump(mode="json")
            report = metrics.schema_metrics(profile)
            recorder.write(
                {
                    "resume_id": inputs["resume_id"],
                    "category": inputs["category"],
                    "input_strategy": input_strategy,
                    "prompt_variant": variant,
                    "model": model,
                    "preprocess_seconds": round(preprocess_seconds, 6),
                    "model_seconds": round(model_seconds, 6),
                    "total_seconds": round(perf_counter() - total_started, 6),
                    "input_kind": "text" if converter else "vision",
                    "input_units": input_units,
                    "page_count": document.page_count,
                    "schema_valid": next(
                        item["score"] for item in report if item["key"] == "schema_valid"
                    ),
                    "coverage": next(
                        item["score"] for item in report if item["key"] == "coverage"
                    ),
                    "output_sha256": hashlib.sha256(
                        json.dumps(profile, sort_keys=True).encode()
                    ).hexdigest(),
                    "success": True,
                }
            )
            return profile
        except Exception as exc:
            recorder.write(
                {
                    "resume_id": inputs["resume_id"],
                    "category": inputs["category"],
                    "input_strategy": input_strategy,
                    "prompt_variant": variant,
                    "model": model,
                    "preprocess_seconds": round(preprocess_seconds, 6),
                    "total_seconds": round(perf_counter() - total_started, 6),
                    "input_kind": "text" if converter else "vision",
                    "input_units": input_units,
                    "page_count": document.page_count,
                    "success": False,
                    "error_type": type(exc).__name__,
                }
            )
            raise
        finally:
            pages.clear()

    return target


def make_baseline_target(mode: str):
    """Model-free predictors that validate the evaluators themselves.

    `oracle` returns the gold profile and must score 1.0 everywhere; `empty`
    returns the null profile and must score ~0.0. If either drifts, the bug is
    in `metrics.py`, not in the parser.
    """
    by_id = {e.resume_id: e.profile for e in gold.load(None)}

    @traceable(name=f"baseline[{mode}]", run_type="chain")
    def target(inputs: dict) -> dict:
        if mode == "oracle":
            return by_id[inputs["resume_id"]]
        return dict(gold.EMPTY_PROFILE)

    return target


# ---------------------------------------------------------------------- run --


def run(client: Client, dataset_name: str, target, prefix: str, meta: dict, limit):
    from langsmith import evaluate

    data = client.list_examples(dataset_name=dataset_name, limit=limit)
    result = evaluate(
        target,
        data=data,
        evaluators=metrics.EVALUATORS,
        experiment_prefix=prefix,
        metadata=meta,
        max_concurrency=2,
    )
    print(f"  -> {result.experiment_name}")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", default="dev", choices=["dev", "test"])
    parser.add_argument("--variant", action="append", choices=sorted(VARIANTS))
    parser.add_argument("--all-variants", action="store_true")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Run the oracle/empty baselines. Validates plumbing without a model.",
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--input-strategy",
        default="direct_vision",
        choices=INPUT_STRATEGIES,
        help="Send rendered pages directly, or run Docling and send its text.",
    )
    parser.add_argument(
        "--metrics-jsonl",
        type=Path,
        default=Path("experiments/results/pipeline_timings.jsonl"),
        help="Append de-identified local stage timings here.",
    )
    args = parser.parse_args()

    client = Client()
    print(f"gold dir: {gold.GOLD_DIR}")
    dataset_name = ensure_dataset(client, args.split)

    if args.check:
        for mode in ("oracle", "empty"):
            print(f"\nbaseline: {mode}")
            run(
                client,
                dataset_name,
                make_baseline_target(mode),
                f"check-{mode}",
                {"kind": "plumbing-check", "baseline": mode, "split": args.split},
                args.limit,
            )
        return 0

    variants = sorted(VARIANTS) if args.all_variants else (args.variant or ["baseline"])
    if not get_settings().google_ai_studio_api_key:
        print(
            "\nGOOGLE_AI_STUDIO_API_KEY is empty — no model call can be made.\n"
            "Set it in backend/.env, or run with --check to validate the harness.",
            file=sys.stderr,
        )
        return 1

    settings = get_settings()
    recorder = MetricsRecorder(args.metrics_jsonl)
    for variant in variants:
        print(f"\nvariant: {variant}; input strategy: {args.input_strategy}")
        run(
            client,
            dataset_name,
            make_target(variant, args.input_strategy, recorder),
            f"{settings.resume_primary_model}-{variant}-{args.input_strategy}",
            {
                "prompt_variant": variant,
                "model": settings.resume_primary_model,
                "split": args.split,
                "render_dpi": settings.resume_render_dpi,
                "input_strategy": args.input_strategy,
            },
            args.limit,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
