"""The extraction port.

The pipeline talks to this and never to a vendor SDK, so swapping or adding a
provider is a change in `providers/` alone.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.resume_parsing.internal.domain import PageArtifact


class ProviderError(RuntimeError):
    """The provider could not produce a parseable object for this page."""


@runtime_checkable
class ExtractionProvider(Protocol):
    @property
    def primary_model(self) -> str:
        """Model id used for the first attempt."""
        ...

    @property
    def fallback_model(self) -> str:
        """Model id used for the repair attempt."""
        ...

    async def extract(self, page: PageArtifact, *, model: str) -> dict:
        """Return the raw JSON object the model produced for one page.

        Raises `ProviderError` if no JSON object could be recovered.
        """
        ...
