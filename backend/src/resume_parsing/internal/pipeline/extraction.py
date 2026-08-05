"""Stage 3 — run the extraction model over the prepared pages.

Provider-agnostic on purpose: this stage knows about pages and models, not about
Google. Swapping the provider changes nothing here.
"""

from __future__ import annotations

import asyncio
import logging
from time import perf_counter

from src.resume_parsing.internal.domain import PageArtifact
from src.resume_parsing.internal.pipeline.postprocess import normalise
from src.resume_parsing.internal.providers.base import ExtractionProvider, ProviderError

logger = logging.getLogger(__name__)

# Pages are independent, so they extract concurrently — but not unboundedly,
# to stay within provider rate limits on long resumes.
_MAX_CONCURRENT_PAGES = 3


async def extract_pages(
    provider: ExtractionProvider,
    pages: list[PageArtifact],
    *,
    model: str,
) -> list[dict]:
    """Extract every page with one model, returning normalised per-page output.

    Raises `ProviderError` only when *no* page could be extracted. A partial
    failure on a multi-page resume degrades to the pages that did work, since a
    profile from three of four pages beats no profile at all.
    """
    semaphore = asyncio.Semaphore(_MAX_CONCURRENT_PAGES)

    async def one(page: PageArtifact) -> dict | None:
        async with semaphore:
            started = perf_counter()
            try:
                result = normalise(await provider.extract(page, model=model))
                logger.info(
                    "Model extraction completed model=%s page=%d input_kind=%s "
                    "duration_seconds=%.3f",
                    model,
                    page.index,
                    "vision" if page.is_visual else "text",
                    perf_counter() - started,
                )
                return result
            except ProviderError:
                logger.warning(
                    "Page %d failed extraction on %s after %.3f seconds",
                    page.index,
                    model,
                    perf_counter() - started,
                )
                return None

    results = await asyncio.gather(*(one(page) for page in pages))
    successful = [result for result in results if result is not None]

    if not successful:
        raise ProviderError(f"No page could be extracted with {model}.")
    return successful
