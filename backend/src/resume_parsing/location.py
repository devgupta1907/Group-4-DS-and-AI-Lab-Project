"""Privacy-preserving handling for locations extracted from resumes.

Production profiles need a locality for matching, not a candidate's street
address.  This module deliberately performs only conservative structural
cleanup: it removes address and postal components while preserving visible
city/region/country text.  It never geocodes or invents a country.
"""

from __future__ import annotations

import re
import unicodedata

_POSTAL_CODES = (
    # US ZIP / ZIP+4.
    re.compile(r"\b\d{5}(?:-\d{4})?\b", re.IGNORECASE),
    # Canadian postal code.
    re.compile(r"\b[A-Z]\d[A-Z][ -]?\d[A-Z]\d\b", re.IGNORECASE),
    # Common UK postcode forms.
    re.compile(
        r"\b(?:GIR\s?0AA|[A-Z]{1,2}\d[A-Z\d]?\s?\d[A-Z]{2})\b",
        re.IGNORECASE,
    ),
)
_PO_BOX = re.compile(r"\bP\.?\s*O\.?\s*Box\s+\w+\b", re.IGNORECASE)
_LEADING_BUILDING = re.compile(r"^\s*\d+[A-Z]?(?:[-/]\d+)?\b", re.IGNORECASE)
_STREET_WORD = re.compile(
    r"\b(?:street|st|road|rd|avenue|ave|drive|dr|lane|ln|way|boulevard|blvd|"
    r"route|highway|hwy|court|ct|circle|cir|terrace|ter|place|pl|parkway|pkwy|"
    r"trail|trl|gardens?|village|flats?|bridge|isle|spring|via|ridge)\.?\b",
    re.IGNORECASE,
)
_UNIT = re.compile(
    r"\b(?:apt|apartment|suite|unit|floor|building|bldg)\b", re.IGNORECASE
)
_ONLY_NUMBER = re.compile(r"^\s*\d+[A-Z]?(?:[-/]\d+)?\s*$", re.IGNORECASE)


def locality_only(value: object) -> str | None:
    """Return locality-level text and discard exact-address components.

    Examples:
      ``123 Elm Street, Miami, FL 33183`` -> ``Miami, FL``
      ``P.O. Box 1673, Callahan, FL 32011`` -> ``Callahan, FL``
      ``100 Montgomery St. 10th Floor`` -> ``None``

    The function intentionally keeps region/country components when present;
    those are coarse location data and useful for job matching.
    """
    if not isinstance(value, str):
        return None
    text = " ".join(unicodedata.normalize("NFKC", value).strip().split())
    if not text:
        return None

    text = _PO_BOX.sub("", text)
    for pattern in _POSTAL_CODES:
        text = pattern.sub("", text)
    text = " ".join(text.split()).strip(" ,")
    if not text:
        return None

    parts = [part.strip(" .") for part in text.split(",") if part.strip(" .")]
    while parts and _is_address_component(parts[0]):
        remainder = _locality_after_street(parts[0])
        parts.pop(0)
        if remainder:
            parts.insert(0, remainder)

    cleaned = [part for part in parts if not _ONLY_NUMBER.fullmatch(part)]
    if not cleaned:
        return None
    result = ", ".join(cleaned)
    # A single unsplit street/unit string has no safely recoverable locality.
    if _is_address_component(result):
        return None
    return result or None


def _is_address_component(value: str) -> bool:
    return bool(
        _ONLY_NUMBER.fullmatch(value)
        or _LEADING_BUILDING.search(value)
        or _PO_BOX.search(value)
        or _STREET_WORD.search(value)
        or _UNIT.search(value)
    )


def _locality_after_street(value: str) -> str | None:
    """Recover ``Bronx`` from an unpunctuated ``... St. Bronx`` component."""
    matches = list(_STREET_WORD.finditer(value))
    if not matches:
        return None
    suffix = value[matches[-1].end() :].strip(" .,-")
    if not suffix or _UNIT.search(suffix) or any(char.isdigit() for char in suffix):
        return None
    return suffix
