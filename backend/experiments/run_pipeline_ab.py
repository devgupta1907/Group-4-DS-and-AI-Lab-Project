"""Paired Gemma evaluation: direct page vision versus Docling-extracted text.

The same pinned resumes, prompt, model and deterministic evaluators are used in
both branches. Raw OCR/model outputs stay under git-ignored `experiments/runs`;
the result JSONL contains only de-identified metrics and hashes.

Run from backend:
    uv run python -u experiments/run_pipeline_ab.py
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
from pathlib import Path
from time import perf_counter, sleep

import psutil
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evals import gold, metrics  # noqa: E402
from evals.prompts import VARIANTS  # noqa: E402
from src.resume_parsing.internal.document_conversion.docling import (  # noqa: E402
    build_docling_converter,
)
from src.resume_parsing.internal.pipeline import (  # noqa: E402
    extraction,
    postprocess,
    preprocess,
    routing,
)
from src.resume_parsing.internal.providers.base import ProviderError  # noqa: E402
from src.resume_parsing.internal.providers.google_ai_studio import (  # noqa: E402
    build_provider,
)

BACKEND = Path(__file__).resolve().parents[1]
RAW_PATH = BACKEND / "experiments" / "runs" / "pipeline_ab_raw.jsonl"
RESULTS_PATH = BACKEND / "experiments" / "results" / "pipeline_ab.jsonl"
STRATEGIES = ("direct_vision", "docling_text")
RATE_LIMIT_DELAYS_SECONDS = (10, 30, 60)

# Reuse the earlier model-comparison cases so prompt/model/pipeline findings can
# be discussed on the same evidence. Their categories and layouts vary, and
# every one has a human-reviewed gold profile.
CASE_IDS = (
    "sap_developer__Image_100",
    "network_security_engineer__3271dd46520c65b9",
    "sql_developer__0b8431fc6fb166a7",
    "python_developer__67",
    "data_science__Image_50",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--strategies",
        nargs="+",
        choices=STRATEGIES,
        default=STRATEGIES,
    )
    parser.add_argument("--variant", choices=sorted(VARIANTS), default="baseline")
    parser.add_argument("--model", help="Defaults to RESUME_PRIMARY_MODEL")
    parser.add_argument("--limit", type=int, default=len(CASE_IDS))
    parser.add_argument("--raw-path", type=Path, default=RAW_PATH)
    parser.add_argument("--results-path", type=Path, default=RESULTS_PATH)
    parser.add_argument(
        "--skip-successful",
        action="store_true",
        help="Do not repeat resume/strategy pairs already recorded as successful.",
    )
    return parser.parse_args()


def chosen_cases(limit: int) -> list[gold.GoldExample]:
    by_id = {example.resume_id: example for example in gold.load(None)}
    missing = set(CASE_IDS) - by_id.keys()
    if missing:
        raise RuntimeError(f"Missing fixed experiment resumes: {sorted(missing)}")
    return [by_id[resume_id] for resume_id in CASE_IDS[:limit]]


def append(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row, sort_keys=True) + "\n")


def sha256_json(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def successful_pairs(path: Path) -> set[tuple[str, str]]:
    if not path.exists():
        return set()
    pairs = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("success"):
            pairs.add((row["resume_id"], row["strategy"]))
    return pairs


def score(profile: dict, reference: dict) -> dict[str, float]:
    rows = metrics.field_metrics(profile, reference) + metrics.schema_metrics(profile)
    return {row["key"]: row["score"] for row in rows}


def call_with_backoff(provider, pages, model: str) -> tuple[list[dict], int]:
    """Run one model attempt, retrying bounded transient provider failures."""
    for attempt in range(len(RATE_LIMIT_DELAYS_SECONDS) + 1):
        try:
            return asyncio.run(extraction.extract_pages(provider, pages, model=model)), attempt
        except ProviderError:
            if attempt == len(RATE_LIMIT_DELAYS_SECONDS):
                raise
            delay = RATE_LIMIT_DELAYS_SECONDS[attempt]
            print(
                f"    provider failure; retry {attempt + 1}/"
                f"{len(RATE_LIMIT_DELAYS_SECONDS)} in {delay}s",
                flush=True,
            )
            sleep(delay)
    raise AssertionError("unreachable")


def main() -> int:
    args = parse_args()
    load_dotenv(BACKEND / ".env")
    model = args.model or os.getenv("RESUME_PRIMARY_MODEL")
    if not os.getenv("GOOGLE_AI_STUDIO_API_KEY") or not model:
        raise SystemExit("GOOGLE_AI_STUDIO_API_KEY and RESUME_PRIMARY_MODEL are required")

    cases = chosen_cases(args.limit)
    provider = build_provider(system_prompt=VARIANTS[args.variant])
    converter = build_docling_converter() if "docling_text" in args.strategies else None
    process = psutil.Process()
    completed_pairs = successful_pairs(args.results_path) if args.skip_successful else set()
    scheduled = [
        (strategy, index, example)
        for strategy in args.strategies
        for index, example in enumerate(cases, start=1)
        if (example.resume_id, strategy) not in completed_pairs
    ]
    total = len(scheduled)
    completed = 0
    print(
        f"Starting pipeline experiment: {total} pending model call(s); "
        f"{len(completed_pairs)} successful pair(s) already recorded",
        flush=True,
    )

    for strategy, case_index, example in scheduled:
        completed += 1
        print(
            f"[{completed}/{total}] {strategy}, resume "
            f"{case_index}/{len(cases)} ({example.resume_id})",
            flush=True,
        )
        started = perf_counter()
        preprocess_seconds = 0.0
        model_seconds = 0.0
        pages = []
        extracted_text = None
        rss_before = process.memory_info().rss / (1024 * 1024)
        try:
            content = example.pdf_path.read_bytes()
            document = routing.route(example.pdf_path.name, "application/pdf", content)
            preprocess_started = perf_counter()
            if strategy == "docling_text":
                if converter is None:
                    raise RuntimeError("Docling converter was not initialized")
                extracted_text = converter.convert(document)
                pages = preprocess.text_artifact(extracted_text)
            else:
                pages = preprocess.to_pages(document)
            preprocess_seconds = perf_counter() - preprocess_started

            print(
                f"    preprocessing done in {preprocess_seconds:.3f}s; calling {model}...",
                flush=True,
            )
            model_started = perf_counter()
            raw_pages, retries = call_with_backoff(provider, pages, model)
            model_seconds = perf_counter() - model_started
            profile = postprocess.merge(raw_pages).model_dump(mode="json")
            result_metrics = score(profile, example.profile)
            rss_after = process.memory_info().rss / (1024 * 1024)

            raw_row = {
                "resume_id": example.resume_id,
                "category": example.category,
                "strategy": strategy,
                "prompt_variant": args.variant,
                "model": model,
                "profile": profile,
                "reference": example.profile,
                "docling_markdown": extracted_text,
            }
            append(args.raw_path, raw_row)

            result_row = {
                "resume_id": example.resume_id,
                "resume_sha256": hashlib.sha256(content).hexdigest(),
                "category": example.category,
                "strategy": strategy,
                "prompt_variant": args.variant,
                "prompt_sha256": hashlib.sha256(VARIANTS[args.variant].encode()).hexdigest(),
                "model": model,
                "temperature": 0,
                "preprocess_seconds": round(preprocess_seconds, 6),
                "model_seconds": round(model_seconds, 6),
                "total_seconds": round(perf_counter() - started, 6),
                "page_count": document.page_count,
                "input_kind": "text" if strategy == "docling_text" else "vision",
                "input_units": sum(
                    len(page.text or "") if page.text is not None else len(page.image_png or b"")
                    for page in pages
                ),
                "rss_before_mb": round(rss_before, 3),
                "rss_after_mb": round(rss_after, 3),
                "provider_retries": retries,
                "success": True,
                "output_sha256": sha256_json(profile),
                **result_metrics,
            }
            append(args.results_path, result_row)
            print(
                f"    done: model={model_seconds:.3f}s, "
                f"total={result_row['total_seconds']:.3f}s, "
                f"macro_F1={result_metrics['profile_f1_macro']:.3f}",
                flush=True,
            )
        except Exception as exc:
            append(
                args.results_path,
                {
                    "resume_id": example.resume_id,
                    "category": example.category,
                    "strategy": strategy,
                    "prompt_variant": args.variant,
                    "model": model,
                    "preprocess_seconds": round(preprocess_seconds, 6),
                    "model_seconds": round(model_seconds, 6),
                    "total_seconds": round(perf_counter() - started, 6),
                    "success": False,
                    "error_type": type(exc).__name__,
                },
            )
            print(f"    failed: {type(exc).__name__}", flush=True)
        finally:
            pages.clear()

    print(f"Finished. Metrics: {args.results_path}", flush=True)
    print(f"Raw evidence: {args.raw_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
