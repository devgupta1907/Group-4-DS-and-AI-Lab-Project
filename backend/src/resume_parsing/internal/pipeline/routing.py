"""Stage 1 — accept the upload, detect its format, choose text vs vision.

The working corpus is 100% image-only PDF, so vision is the default and text is
the exception. The probe is deliberately cheap and deterministic: a PDF whose
pages carry fewer than `resume_text_layer_min_chars` extractable characters is
treated as image-only regardless of what its metadata claims.
"""

from __future__ import annotations

import fitz  # PyMuPDF

from src.core.config import get_settings
from src.resume_parsing.errors import (
    FileTooLarge,
    TooManyPages,
    UnreadableDocument,
    UnsupportedFileType,
)
from src.resume_parsing.internal.domain import SourceDocument
from src.resume_parsing.schemas import ParseRoute

PDF_TYPES = {"application/pdf"}
DOCX_TYPES = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
IMAGE_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp"}

_EXTENSION_TYPES = {
    ".pdf": "application/pdf",
    ".docx": next(iter(DOCX_TYPES)),
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}


def resolve_media_type(filename: str, declared: str | None) -> str:
    """Trust the extension over the browser's guess, which is often wrong."""
    lowered = filename.lower()
    for suffix, media_type in _EXTENSION_TYPES.items():
        if lowered.endswith(suffix):
            return media_type
    if declared in PDF_TYPES | DOCX_TYPES | IMAGE_TYPES:
        return declared
    raise UnsupportedFileType()


def route(filename: str, declared_type: str | None, content: bytes) -> SourceDocument:
    """Validate the upload and decide which extraction path it takes."""
    settings = get_settings()

    if not content:
        raise UnreadableDocument("The uploaded file is empty.")
    if len(content) > settings.resume_max_upload_bytes:
        raise FileTooLarge()

    media_type = resolve_media_type(filename, declared_type)

    if media_type in IMAGE_TYPES:
        return SourceDocument(filename, media_type, content, 1, ParseRoute.VISION)

    if media_type in DOCX_TYPES:
        return SourceDocument(filename, media_type, content, 1, ParseRoute.TEXT)

    return _route_pdf(filename, media_type, content, settings.resume_max_pages,
                      settings.resume_text_layer_min_chars)


def _route_pdf(
    filename: str,
    media_type: str,
    content: bytes,
    max_pages: int,
    min_chars: int,
) -> SourceDocument:
    try:
        document = fitz.open(stream=content, filetype="pdf")
    except Exception as exc:
        raise UnreadableDocument() from exc

    try:
        if document.needs_pass:
            raise UnreadableDocument("That PDF is password-protected.")
        page_count = document.page_count
        if page_count == 0:
            raise UnreadableDocument("That PDF has no pages.")
        if page_count > max_pages:
            raise TooManyPages(
                f"That resume has {page_count} pages; the limit is {max_pages}."
            )
        has_text_layer = all(
            len(document[i].get_text("text").strip()) >= min_chars
            for i in range(page_count)
        )
    finally:
        document.close()

    chosen = ParseRoute.TEXT if has_text_layer else ParseRoute.VISION
    return SourceDocument(filename, media_type, content, page_count, chosen)
