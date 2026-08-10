"""Restart-safe offline normalized scoring over a saved inference ledger."""

from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from evals import gold, normalization
from evals.field_scoring import confusion_rows
from src.resume_parsing.internal.pipeline import postprocess

NORMALIZATION_VERSION = "field_comparison_v037_gold_fingerprinted"


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"Inference ledger not found: {path}")
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Corrupt ledger line {line_number}: {exc}") from exc
    return rows


def append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
    with path.open("a", encoding="utf-8") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def normalization_sha256() -> str:
    material = Path(normalization.__file__).read_bytes() + Path(__file__).read_bytes()
    return hashlib.sha256(material).hexdigest()


def effective_gold() -> tuple[dict[str, dict], str]:
    """Return current effective profiles and a deterministic cache identity."""
    profiles = {example.resume_id: example.profile for example in gold.load(None)}
    material = json.dumps(
        profiles, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return profiles, hashlib.sha256(material).hexdigest()


def select_source_successes(
    source_rows: list[dict], source_experiment_key: str | None = None
) -> tuple[str, list[dict]]:
    successes = [
        row
        for row in source_rows
        if row.get("status") == "success"
        and row.get("evaluation_type") != "offline_normalized_scoring"
    ]
    if not successes:
        raise ValueError("The inference ledger contains no successful rows.")
    key = source_experiment_key or max(successes, key=lambda row: row["timestamp_utc"])[
        "experiment_key"
    ]
    latest: dict[str, dict] = {}
    for row in sorted(successes, key=lambda item: item["timestamp_utc"]):
        if row.get("experiment_key") == key:
            latest[row["resume_id"]] = row
    if not latest:
        raise ValueError(f"No successful inference rows for experiment: {key}")
    return key, list(latest.values())


def run_normalized_scoring(
    *,
    source_ledger: Path,
    output_ledger: Path,
    source_experiment_key: str | None = None,
) -> dict[str, Any]:
    """Append one derived scoring row per unscored successful inference record.

    This function performs no network operation and imports no model provider.
    """
    source_key, source_records = select_source_successes(
        read_jsonl(source_ledger), source_experiment_key
    )
    sha = normalization_sha256()
    gold_by_id, gold_sha = effective_gold()
    evaluation_key = (
        f"{source_key}:offline_normalization={NORMALIZATION_VERSION}:"
        f"normalization_sha256={sha}:gold_sha256={gold_sha}"
    )
    existing = read_jsonl(output_ledger) if output_ledger.exists() else []
    completed = {
        row.get("source_record_id")
        for row in existing
        if row.get("status") == "success"
        and row.get("source_experiment_key") == source_key
        and row.get("normalization_version") == NORMALIZATION_VERSION
        and row.get("normalization_sha256") == sha
        and row.get("gold_sha256") == gold_sha
    }
    pending = [row for row in source_records if row.get("record_id") not in completed]
    scoring_run_id = str(uuid.uuid4())
    for index, source in enumerate(pending, 1):
        started = time.perf_counter()
        prediction = postprocess.normalise(
            source.get("production_prediction") or source.get("prediction") or {}
        )
        if source["resume_id"] not in gold_by_id:
            raise ValueError(f"No current gold record for {source['resume_id']}")
        reference = postprocess.normalise(gold_by_id[source["resume_id"]])
        field_counts = confusion_rows(prediction, reference, mode="normalized")
        append_jsonl(output_ledger, {
            "record_id": str(uuid.uuid4()),
            "scoring_run_id": scoring_run_id,
            "timestamp_utc": datetime.now(UTC).isoformat(),
            "status": "success",
            "evaluation_key": evaluation_key,
            "experiment_key": evaluation_key,
            "evaluation_type": "offline_normalized_scoring",
            "normalization_version": NORMALIZATION_VERSION,
            "normalization_sha256": sha,
            "gold_corrections_version": gold.GOLD_CORRECTIONS_VERSION,
            "gold_sha256": gold_sha,
            "source_experiment_key": source_key,
            "source_record_id": source.get("record_id"),
            "resume_id": source["resume_id"],
            "split": source.get("split"),
            "category": source.get("category"),
            "model": source.get("model"),
            "prompt_version": source.get("prompt_version"),
            "value_normalization": NORMALIZATION_VERSION,
            "inference_reused": True,
            "additional_llm_calls": 0,
            "source_resume_total_seconds": source.get("resume_total_seconds"),
            "resume_total_seconds": source.get("resume_total_seconds"),
            "model_wall_seconds": source.get("model_wall_seconds"),
            "page_count": source.get("page_count"),
            "normalization_seconds": round(time.perf_counter() - started, 6),
            "stored_location_policy": "locality_only_no_exact_address",
            "prediction": prediction,
            "production_prediction": prediction,
            "raw_prediction": prediction,
            "reference": reference,
            "raw_schema_valid": source.get("raw_schema_valid", True),
            "raw_schema_errors": source.get("raw_schema_errors", []),
            "field_counts": field_counts,
        })
        print(f"[{index}/{len(pending)}] {source['resume_id']}: normalized", flush=True)

    return {
        "source_experiment_key": source_key,
        "evaluation_key": evaluation_key,
        "gold_sha256": gold_sha,
        "source_successes": len(source_records),
        "already_scored": len(source_records) - len(pending),
        "newly_scored": len(pending),
        "output_ledger": str(output_ledger),
        "additional_llm_calls": 0,
    }
