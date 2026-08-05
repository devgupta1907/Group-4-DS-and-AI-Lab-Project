"""Optional document-to-text adapters used before model extraction."""

from src.resume_parsing.internal.document_conversion.base import (
    DocumentTextConversionError,
    DocumentTextConverter,
)

__all__ = ["DocumentTextConverter", "DocumentTextConversionError"]
