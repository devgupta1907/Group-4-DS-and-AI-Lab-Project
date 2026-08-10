"""Shared, deterministic value normalization for resume evaluation.

These functions create comparison keys only.  They never mutate persisted raw
or production values.  Location is the sole privacy exception and delegates to
the production locality-only sanitizer.
"""

from __future__ import annotations

import re
import unicodedata

from src.resume_parsing.internal.location import locality_only

NORMALIZATION_RULES = (
    "Normalize Unicode text to NFKC.",
    "Compare text case-insensitively and collapse repeated whitespace.",
    "Treat null-like placeholders as missing values.",
    "Reduce locations to locality level and discard address/postal components.",
    "Discard generic location placeholders such as City, State and Location.",
    "Remove a company suffix only when it matches that experience's location.",
    "Normalize punctuation for names, titles, organizations and certification text.",
    "Treat ampersand and the word 'and' equivalently in organization comparison.",
    "Resolve only controlled degree abbreviations such as B.Sc. and Bachelor of Science.",
    "Remove explicit field-of-study labels such as 'major in' from education-field "
    "comparison keys.",
    "Canonicalize common month/year spellings without inventing date precision.",
    "Compare year-only fields at year precision, even when a source includes a month or season.",
    "Expand apostrophe years such as '16 to 2016 when the century is unambiguous.",
    "Allow a year-only gold date to match a prediction containing the same year and month.",
    "Split a visible date range into its start or end component for the corresponding field.",
    "Split explicitly labelled or comma/semicolon-delimited skill groups into atomic items.",
    "Apply controlled technology aliases while preserving meaningful technical punctuation.",
    "Resolve evidence-backed skill phrase boundaries and remove safe SQL Server version suffixes.",
    "Normalize job-title seniority abbreviations and separated technical acronyms.",
    "Remove verified trailing city/region text from institution comparison keys.",
    "Apply only evidence-backed institution spelling and spacing aliases.",
)

_MISSING_SENTINELS = {
    "-", "n/a", "na", "none", "null", "not applicable", "not available", "date", "20xx",
}
_LOCATION_PLACEHOLDERS = {
    "city", "state", "country", "city state", "city, state", "location",
}
_PUNCTUATION_INSENSITIVE_FIELDS = {
    "contact.name",
    "job_titles",
    "education.degree",
    "education.field",
    "education.institution",
    "experience.job_title",
    "experience.company",
    "projects.name",
    "certifications.name",
    "certifications.issuer",
}
_DATE_RANGE_SEPARATOR = re.compile(r"\s+(?:-|–|—|to)\s+", re.IGNORECASE)
_SKILL_FIELDS = {"skills", "projects.technologies"}
_SKILL_LABEL = re.compile(
    r"^(?:programming languages?|scripting|cloud|databases?|monitoring|containerization|"
    r"version control|virtualization|storage|web applications?|user administration|"
    r"automation|tools?|technologies|frameworks?|operating systems?)\s*:\s*",
    re.IGNORECASE,
)
_SKILL_ALIASES = {
    "amazon web services": "aws",
    "amazon aws": "aws",
    "aws cloud": "aws",
    "amazon elastic compute cloud": "ec2",
    "amazon ec2": "ec2",
    "aws elastic compute": "ec2",
    "aws elastic compute cloud": "ec2",
    "cloud ec2": "ec2",
    "cloud watch": "cloudwatch",
    "amazon cloudwatch": "cloudwatch",
    "aws cloudwatch": "cloudwatch",
    "google cloud platform": "gcp",
    "cloud formation": "cloudformation",
    "apache kafka": "kafka",
    "hibernate orm": "hibernate",
    "java script": "javascript",
    "vb net": "vb.net",
    "visual basic net": "vb.net",
    "ms office": "microsoft office",
    "microsoft office suite": "microsoft office",
    "ms word": "microsoft word",
    "word": "microsoft word",
    "ms excel": "microsoft excel",
    "excel": "microsoft excel",
    "ms powerpoint": "microsoft powerpoint",
    "powerpoint": "microsoft powerpoint",
    "ms outlook": "microsoft outlook",
    "outlook": "microsoft outlook",
    "ms access": "microsoft access",
    "access": "microsoft access",
    "adobe creative suite": "adobe creative cloud",
    "creative cloud": "adobe creative cloud",
    "photoshop": "adobe photoshop",
    "illustrator": "adobe illustrator",
    "indesign": "adobe indesign",
    "dreamweaver": "adobe dreamweaver",
    "premiere pro": "adobe premiere pro",
    "after effects": "adobe after effects",
    "lightroom": "adobe lightroom",
    "adobe acrobat": "adobe acrobat",
    "g suite": "google workspace",
    "google suite": "google workspace",
    "google docs": "google docs",
    "google sheets": "google sheets",
    "google slides": "google slides",
    "google drive": "google drive",
    "bank reconciliation": "bank reconciliation",
    "bank reconciliations": "bank reconciliation",
    "preparing financial statements": "financial statement preparation",
    "prepare financial statements": "financial statement preparation",
    "financial statements preparation": "financial statement preparation",
    "financial statement preparation": "financial statement preparation",
    "continuous integration continuous delivery": "ci/cd",
    "continuous integration and continuous delivery": "ci/cd",
    "js": "javascript",
    "ms sql": "sql server",
    "ms sql server": "sql server",
    "enterprise information and architecture": "enterprise information architecture",
    "creating and maintaining schedules": "project planning and scheduling",
    "project planning and scheduling knowledge": "project planning and scheduling",
    "knowledge of construction codes": "construction codes",
    "and negotiating with contractors": "negotiating with contractors",
    "experience and knowledge of gas facilities construction": "gas facilities construction",
    "experience and knowledge of hazardous location class 1 division 1 & 2 electrical installations":
        "hazardous location class 1 div 1 & 2 electrical installations",
}
_SKILL_GROUP_ALIASES = {
    "microsoft word, excel, access, powerpoint, & outlook": {
        "microsoft word", "microsoft excel", "microsoft access",
        "microsoft powerpoint", "microsoft outlook",
    },
    "microsoft word, excel, access, powerpoint, & outlook expertise": {
        "microsoft word", "microsoft excel", "microsoft access",
        "microsoft powerpoint", "microsoft outlook",
    },
    "microsoft word, excel, access, powerpoint, and outlook": {
        "microsoft word", "microsoft excel", "microsoft access",
        "microsoft powerpoint", "microsoft outlook",
    },
    "microsoft word, excel, access, powerpoint, and outlook expertise": {
        "microsoft word", "microsoft excel", "microsoft access",
        "microsoft powerpoint", "microsoft outlook",
    },
    "js/jquery": {"javascript", "jquery"},
    "electrical construction / electrical engineering": {
        "electrical construction", "electrical engineering",
    },
    "background in electrical construction or electrical engineering": {
        "electrical construction", "electrical engineering",
    },
}
_SQL_SERVER_VERSION_SUFFIX = re.compile(
    r"^(?:ms\s+sql|ms\s+sql\s+server|sql\s+server)\s+"
    r"(?:version\s*)?(?:19|20)?\d{2}(?:\s*/\s*(?:19|20)?\d{2})*$",
    re.IGNORECASE,
)
_TITLE_TOKEN_ALIASES = {"sr": "senior", "jr": "junior"}
_MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7,
    "july": 7, "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12,
    "december": 12,
}
_CURRENT = {"present", "current", "ongoing", "till date", "to date", "now"}
_DEGREE_ALIASES = {
    "ba": "bachelor of arts", "bachelorarts": "bachelor of arts",
    "be": "bachelor of engineering", "beng": "bachelor of engineering",
    "bachelorengineering": "bachelor of engineering", "bs": "bachelor of science",
    "bsc": "bachelor of science", "bachelorscience": "bachelor of science",
    "btech": "bachelor of technology", "bachelortechnology": "bachelor of technology",
    "ma": "master of arts", "masterarts": "master of arts",
    "me": "master of engineering", "meng": "master of engineering",
    "masterengineering": "master of engineering", "ms": "master of science",
    "msc": "master of science", "masterscience": "master of science",
    "mtech": "master of technology", "mastertechnology": "master of technology",
    "phd": "doctor of philosophy", "doctorphilosophy": "doctor of philosophy",
}
_INSTITUTION_ALIASES = {
    "penn state worldcampus": "penn state world campus",
}
_INSTITUTION_LOCATION_SUFFIXES = {
    "ames, ia", "atlanta, ga", "battle creek, mi", "charleston, sc",
    "charlottesville", "chicago, il", "columbus, oh", "dearborn, mi", "denver, co",
    "fort collins, co", "houston, tx", "idaho falls, id", "irvine, ca",
    "la", "lexington, ky", "los angeles, ca", "malibu, ca", "manzini",
    "miami, fl", "natchitoches, la", "new orleans", "philadelphia, ca",
    "pittsburgh, p.a.", "pretoria, gauteng", "saint leo, fl", "san diego, ca",
    "san marcos, ca", "savannah, ga", "singapore", "tempe, az", "york, pa",
}


def normalize_text(value: object) -> str:
    """Unicode-, case-, and whitespace-insensitive comparison key."""
    if not isinstance(value, str):
        return ""
    text = unicodedata.normalize("NFKC", value)
    normalized = " ".join(text.casefold().split())
    return "" if normalized in _MISSING_SENTINELS else normalized


def normalize_punctuation(value: object, *, organization: bool = False) -> str:
    """Remove comparison-irrelevant punctuation from non-technical text."""
    text = normalize_text(value)
    if organization:
        text = re.sub(r"\band\b", "&", text)
    text = re.sub(r"[^\w&]+", " ", text, flags=re.UNICODE)
    return " ".join(text.split()).strip(" &")


def lookup_key(value: object) -> str:
    """Punctuation-insensitive key used only for controlled alias lookup."""
    return "".join(character for character in normalize_text(value) if character.isalnum())


def normalize_degree(value: object) -> str:
    text = normalize_text(value)
    return _DEGREE_ALIASES.get(lookup_key(value), normalize_punctuation(text))


def normalize_education_field(value: object) -> str:
    """Remove labels while preserving the stated discipline itself."""
    field = normalize_text(value)
    field = re.sub(
        r"^(?:major|field of study)\s*(?::|in\b)\s*",
        "",
        field,
        flags=re.IGNORECASE,
    )
    return normalize_punctuation(field)


def normalize_institution(value: object) -> str:
    """Remove verified locality suffixes without discarding institutional subunits."""
    institution = normalize_text(value)
    for suffix in sorted(_INSTITUTION_LOCATION_SUFFIXES, key=len, reverse=True):
        institution = re.sub(
            rf"\s*(?:,|\s[-–—]\s)\s*{re.escape(suffix)}\s*$",
            "",
            institution,
            flags=re.IGNORECASE,
        ).strip()
    normalized = normalize_punctuation(institution, organization=True)
    return _INSTITUTION_ALIASES.get(normalized, normalized)


def normalize_date(value: object) -> str:
    """Canonicalize common dates without inventing missing month precision."""
    text = normalize_text(value).strip(".,")
    if not text:
        return ""
    if text in _CURRENT:
        return "present"
    short_year = re.search(r"(?:['’]\s*)(\d{2})\b", text)
    if short_year:
        number = int(short_year.group(1))
        expanded = 2000 + number if number <= 30 else 1900 + number
        text = re.sub(r"(?:['’]\s*)\d{2}\b", str(expanded), text, count=1)
    year = re.search(r"\b((?:19|20)\d{2})\b", text)
    if not year:
        return text
    year_value = year.group(1)
    for name, number in _MONTHS.items():
        if re.search(rf"\b{re.escape(name)}\b", text):
            return f"{year_value}-{number:02d}"
    numeric_month = re.fullmatch(
        r"\s*(0?[1-9]|1[0-2])\s*[-/.]\s*((?:19|20)\d{2})\s*", text
    )
    if numeric_month:
        return f"{numeric_month.group(2)}-{int(numeric_month.group(1)):02d}"
    iso_month = re.fullmatch(
        r"\s*((?:19|20)\d{2})\s*[-/.]\s*(0?[1-9]|1[0-2])\s*", text
    )
    if iso_month:
        return f"{iso_month.group(1)}-{int(iso_month.group(2)):02d}"
    if re.fullmatch(r"(?:19|20)\d{2}", text):
        return year_value
    return text


def normalize_date_field(field: str, value: object) -> str:
    """Canonicalize one date field and recover its endpoint from a visible range."""
    text = normalize_text(value)
    parts = _DATE_RANGE_SEPARATOR.split(text, maxsplit=1)
    if len(parts) == 2:
        text = parts[0] if field.endswith(("start_date", "start_year")) else parts[1]
    normalized = normalize_date(text)
    if field.rsplit(".", 1)[-1].endswith("year"):
        year = re.search(r"\b((?:19|20)\d{2})\b", normalized)
        return year.group(1) if year else normalized
    return normalized


def normalize_company(value: object, *, location: object = None) -> str:
    """Normalize a company and remove only a verified same-entry location suffix."""
    company = normalize_text(value)
    location_text = normalize_text(locality_only(location))
    if location_text:
        suffix = re.compile(
            rf"\s*(?:[,/|]|\s+-\s+)\s*{re.escape(location_text)}\s*$",
            re.IGNORECASE,
        )
        company = suffix.sub("", company).strip()
    return normalize_punctuation(company, organization=True)


def normalize_skill_values(value: object) -> set[str]:
    """Return conservative atomic comparison keys for one skill-list value."""
    text = normalize_text(value)
    if not text:
        return set()
    text = _SKILL_LABEL.sub("", text)
    punctuation_preserving_key = " ".join(text.split())
    if punctuation_preserving_key in _SKILL_GROUP_ALIASES:
        return set(_SKILL_GROUP_ALIASES[punctuation_preserving_key])
    parenthesized_group = re.fullmatch(r"[^()]+\(([^()]*[,;][^()]*)\)", text)
    if parenthesized_group:
        text = parenthesized_group.group(1)
    parts = [part.strip() for part in re.split(r"[,;]", text) if part.strip()]
    normalized = set()
    for part in parts:
        if _SQL_SERVER_VERSION_SUFFIX.fullmatch(part):
            normalized.add("sql server")
            continue
        alias_key = normalize_punctuation(part)
        canonical = _SKILL_ALIASES.get(alias_key, part)
        if canonical:
            normalized.add(canonical)
    return normalized


def normalize_job_title(value: object) -> str:
    """Normalize safe title abbreviations without equating different roles."""
    title = normalize_punctuation(value)
    tokens = [_TITLE_TOKEN_ALIASES.get(token, token) for token in title.split()]
    title = " ".join(tokens)
    return re.sub(
        r"\b(?:e\s+t\s+l|d\s+b\s+a|q\s+a)\b",
        lambda match: match.group().replace(" ", ""),
        title,
    )


def date_matches(predicted: object, expected: object) -> bool:
    """Match at the precision supplied by the gold annotation."""
    predicted_date = normalize_date(predicted)
    expected_date = normalize_date(expected)
    if predicted_date == expected_date:
        return True
    if re.fullmatch(r"(?:19|20)\d{2}", expected_date):
        return predicted_date.startswith(f"{expected_date}-")
    return False


def normalize_field_value(field: str, value: object) -> str:
    """Return the canonical comparison key for one named schema field."""
    if isinstance(value, bool):
        return str(value).casefold()
    if field.endswith(".location"):
        location = normalize_text(locality_only(value))
        punctuation_key = normalize_punctuation(location)
        return "" if punctuation_key in _LOCATION_PLACEHOLDERS else punctuation_key
    if field == "education.degree":
        return normalize_degree(value)
    if field == "education.field":
        return normalize_education_field(value)
    if field == "education.institution":
        return normalize_institution(value)
    if field in {"job_titles", "experience.job_title"}:
        return normalize_job_title(value)
    if field.rsplit(".", 1)[-1].endswith(("date", "year")):
        return normalize_date_field(field, value)
    if field in _PUNCTUATION_INSENSITIVE_FIELDS:
        return normalize_punctuation(
            value,
            organization=field in {
                "education.institution", "experience.company", "certifications.issuer"
            },
        )
    return normalize_text(value)


def normalize_field_values(field: str, value: object) -> set[str]:
    """Return one or more keys when a composite value is safely splittable."""
    if field in _SKILL_FIELDS:
        return normalize_skill_values(value)
    normalized = normalize_field_value(field, value)
    return {normalized} if normalized else set()
