"""Port for converting an accepted document into layout-aware text."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.resume_parsing.internal.domain import SourceDocument


class DocumentTextConversionError(RuntimeError):
    """A document-to-text adapter could not produce usable text."""


@runtime_checkable
class DocumentTextConverter(Protocol):
    @property
    def name(self) -> str:
        """Stable converter name used in metrics and logs."""
        ...

    def convert(self, document: SourceDocument) -> str:
        """Return layout-aware text without writing the upload to disk."""
        ...
