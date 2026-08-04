"""Parse one resume with the production pipeline and emit its profile as JSON.

Run from the backend directory:

    uv run python demo_parse_resume.py /path/to/resume.pdf
    uv run python demo_parse_resume.py /path/to/resume.pdf --output parsed.json

The configured primary model is used by default (currently Gemma). This script
does not start the API, access PostgreSQL, encrypt data, or use LangSmith.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from src.core.config import get_settings  # noqa: E402
from src.resume_parsing.internal.pipeline import (  # noqa: E402
    extraction,
    postprocess,
    preprocess,
    routing,
    validation,
)
from src.resume_parsing.internal.providers.google_ai_studio import (  # noqa: E402
    build_provider,
)
# // gemini-3.5-flash

DEFAULT_RESUME = (
    Path(__file__).resolve().parents[2]
    / "Milestone_2_Resume_Parsing"
    / "final_dataset"
    / "gold"
    / "sql_developer"
    / "sql_developer__0b8431fc6fb166a7.pdf"
)


async def parse_resume(path: Path, model: str) -> tuple[dict, object]:
    """Run the same routing, preprocessing and extraction stages as production."""
    content = path.read_bytes()
    document = routing.route(path.name, None, content)
    pages = preprocess.to_pages(document)
    try:
        provider = build_provider()
        raw_pages = await extraction.extract_pages(provider, pages, model=model)
        profile = postprocess.merge(raw_pages).model_dump(mode="json")
        return profile, validation.validate(profile)
    finally:
        pages.clear()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Parse one PDF, DOCX, PNG, JPEG or WebP resume into JSON."
    )
    parser.add_argument("resume", type=Path, help="Path to the resume file")
    parser.add_argument("-o", "--output", type=Path, help="Also save JSON to this file")
    parser.add_argument(
        "--model",
        help="Google AI Studio model ID; defaults to RESUME_PRIMARY_MODEL from .env",
    )
    args = parser.parse_args()

    if not args.resume.is_file():
        parser.error(f"resume file not found: {args.resume}")

    settings = get_settings()
    if not settings.google_ai_studio_api_key:
        parser.error("GOOGLE_AI_STUDIO_API_KEY is missing from backend/.env")

    model = args.model or settings.resume_primary_model
    print(f"Parsing {args.resume} with {model} ...", file=sys.stderr, flush=True)

    profile, report = asyncio.run(parse_resume(args.resume, model))
    rendered = json.dumps(profile, ensure_ascii=False, indent=2)
    print(rendered)

    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
        print(f"Saved JSON to {args.output}", file=sys.stderr)

    print(
        f"schema_valid={report.schema_ok} coverage={report.coverage:.2f} "
        f"needs_review={report.needs_review}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
