"""Version prompts and record exact LLM experiment inputs and outputs.

Prompt definitions are immutable JSON files intended to be committed to git.
Run records are append-only JSONL files and may contain sensitive resume data,
so the default run directory is ignored by git.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from difflib import unified_diff
from hashlib import sha256
from pathlib import Path
from string import Formatter
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class PromptVersion:
    name: str
    version: str
    template: str
    change_summary: str
    rationale: str
    parent_version: str | None = None
    acceptance_criteria: tuple[str, ...] = ()
    created_at: str = ""
    template_sha256: str = ""


class PromptExperimentStore:
    """Filesystem-backed prompt registry and experiment logger."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.prompts_dir = self.root / "prompts"
        self.runs_dir = self.root / "runs"

    @staticmethod
    def _safe_segment(value: str, field: str) -> str:
        allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
        if not value or any(char not in allowed for char in value):
            raise ValueError(f"{field} may contain only letters, numbers, '_' and '-'")
        return value

    def _prompt_path(self, name: str, version: str) -> Path:
        return (
            self.prompts_dir
            / self._safe_segment(name, "name")
            / f"{self._safe_segment(version, 'version')}.json"
        )

    def create_version(
        self,
        *,
        name: str,
        version: str,
        template: str,
        change_summary: str,
        rationale: str,
        parent_version: str | None = None,
        acceptance_criteria: list[str] | tuple[str, ...] = (),
    ) -> PromptVersion:
        """Create an immutable prompt version and document why it changed."""
        path = self._prompt_path(name, version)
        if path.exists():
            raise FileExistsError(f"Prompt version already exists: {name}/{version}")
        if parent_version is not None:
            self.load_version(name, parent_version)

        prompt = PromptVersion(
            name=name,
            version=version,
            template=template,
            change_summary=change_summary,
            rationale=rationale,
            parent_version=parent_version,
            acceptance_criteria=tuple(acceptance_criteria),
            created_at=datetime.now(UTC).isoformat(),
            template_sha256=sha256(template.encode("utf-8")).hexdigest(),
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(prompt), indent=2, ensure_ascii=False) + "\n")
        return prompt

    def load_version(self, name: str, version: str) -> PromptVersion:
        path = self._prompt_path(name, version)
        if not path.exists():
            raise FileNotFoundError(f"Unknown prompt version: {name}/{version}")
        data = json.loads(path.read_text())
        data["acceptance_criteria"] = tuple(data.get("acceptance_criteria", ()))
        prompt = PromptVersion(**data)
        actual_hash = sha256(prompt.template.encode("utf-8")).hexdigest()
        if actual_hash != prompt.template_sha256:
            raise ValueError(f"Prompt template was modified after creation: {name}/{version}")
        return prompt

    def render(
        self,
        name: str,
        version: str,
        variables: Mapping[str, Any],
    ) -> tuple[PromptVersion, str]:
        """Render a prompt strictly so missing variables cannot go unnoticed."""
        prompt = self.load_version(name, version)
        required = {
            field_name
            for _, field_name, _, _ in Formatter().parse(prompt.template)
            if field_name
        }
        missing = required - variables.keys()
        if missing:
            raise ValueError(f"Missing prompt variables: {sorted(missing)}")
        rendered = prompt.template.format_map(dict(variables))
        return prompt, rendered

    def diff_versions(
        self,
        name: str,
        old_version: str,
        new_version: str,
    ) -> str:
        """Return a readable, exact line diff between two prompt templates."""
        old = self.load_version(name, old_version)
        new = self.load_version(name, new_version)
        return "".join(
            unified_diff(
                old.template.splitlines(keepends=True),
                new.template.splitlines(keepends=True),
                fromfile=f"{name}/{old_version}",
                tofile=f"{name}/{new_version}",
            )
        )

    def record_run(
        self,
        *,
        experiment: str,
        prompt: PromptVersion,
        rendered_prompt: str,
        model: str,
        model_parameters: Mapping[str, Any],
        output: Any = None,
        metrics: Mapping[str, Any] | None = None,
        notes: str = "",
        latency_ms: float | None = None,
        error: str | None = None,
    ) -> dict[str, Any]:
        """Append one complete, reproducible experiment record."""
        experiment = self._safe_segment(experiment, "experiment")
        record = {
            "run_id": str(uuid4()),
            "recorded_at": datetime.now(UTC).isoformat(),
            "experiment": experiment,
            "prompt_name": prompt.name,
            "prompt_version": prompt.version,
            "prompt_template_sha256": prompt.template_sha256,
            "rendered_prompt": rendered_prompt,
            "model": model,
            "model_parameters": dict(model_parameters),
            "output": output,
            "metrics": dict(metrics or {}),
            "notes": notes,
            "latency_ms": latency_ms,
            "status": "error" if error else "success",
            "error": error,
        }
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        path = self.runs_dir / f"{experiment}.jsonl"
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        return record
