"""Docling-backed conversion for scanned PDFs.

The upload is passed as an in-memory stream to preserve the module's transient
PII contract. The converter returns Markdown because headings and list
boundaries give the downstream LLM more structure than flattened OCR text.
"""

from __future__ import annotations

import io
from threading import Lock

from docling.datamodel.base_models import DocumentStream, InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions, RapidOcrOptions
from docling.document_converter import DocumentConverter, PdfFormatOption

from src.resume_parsing.internal.document_conversion.base import (
    DocumentTextConversionError,
)
from src.resume_parsing.internal.domain import SourceDocument


class DoclingTextConverter:
    """Convert scanned PDFs to Markdown with full-page RapidOCR."""

    name = "docling_text"

    def __init__(self) -> None:
        options = PdfPipelineOptions(
            do_ocr=True,
            do_table_structure=False,
            ocr_options=RapidOcrOptions(
                lang=["english"],
                force_full_page_ocr=True,
            ),
        )
        self._converter = DocumentConverter(
            allowed_formats=[InputFormat.PDF],
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=options),
            },
        )
        # A service instance can process concurrent requests. Guard the shared
        # Docling pipeline because its model objects are not documented as
        # thread-safe.
        self._lock = Lock()

    def convert(self, document: SourceDocument) -> str:
        if document.media_type != "application/pdf":
            raise DocumentTextConversionError(
                "Docling preprocessing currently supports PDF resumes only."
            )

        source = DocumentStream(
            name=document.filename,
            stream=io.BytesIO(document.content),
        )
        try:
            with self._lock:
                result = self._converter.convert(source)
                text = result.document.export_to_markdown().strip()
        except Exception as exc:
            raise DocumentTextConversionError(
                "Docling could not extract text from the resume."
            ) from exc

        if not text:
            raise DocumentTextConversionError("Docling returned empty text.")
        return text


def build_docling_converter() -> DoclingTextConverter:
    return DoclingTextConverter()
