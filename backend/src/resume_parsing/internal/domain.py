"""Internal value objects passed between pipeline stages.

Distinct from `schemas.py`: those are the module's public wire shapes, these are
private and may change freely without breaking any consumer.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.resume_parsing.schemas import ParseRoute


@dataclass(frozen=True, slots=True)
class SourceDocument:
    """An accepted upload after format detection, before preprocessing."""

    filename: str
    media_type: str
    content: bytes
    page_count: int
    route: ParseRoute


@dataclass(frozen=True, slots=True)
class PageArtifact:
    """One unit of work for the extraction engine — a page, as text or image.

    Exactly one of `text` / `image_png` is populated, determined by the route.
    """

    index: int
    text: str | None = None
    image_png: bytes | None = None

    @property
    def is_visual(self) -> bool:
        return self.image_png is not None


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    """Raw model output for one page, before normalisation or validation."""

    page_index: int
    payload: dict
    model: str


@dataclass(slots=True)
class ValidationReport:
    """Outcome of the schema gate plus the completeness heuristic."""

    schema_errors: list[str] = field(default_factory=list)
    coverage: float = 0.0
    needs_review: list[str] = field(default_factory=list)

    @property
    def schema_ok(self) -> bool:
        return not self.schema_errors

    def is_acceptable(self, threshold: float) -> bool:
        return self.schema_ok and self.coverage >= threshold
