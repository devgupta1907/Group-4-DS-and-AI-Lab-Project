"""Prepare a deterministic blind resume set from the original PDF corpus.

The selection is structural only: this script never reads model predictions or
resume text. Exact SHA-256 duplicates and visually near-identical first pages of
the existing gold corpus are excluded before one resume is sampled per category.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import random
import re
import shutil
from pathlib import Path

import fitz
from PIL import Image

SEED = 20260809
DEFAULT_COUNT = 30

ALIASES = {
    "datascience": "Data Science", "pythondeveloper": "Python Developer",
    "javadeveloper": "Java Developer", "dotnetdeveloper": "DotNet Developer",
    "dot": "DotNet Developer", "dotdeveloper": "DotNet Developer",
    "reactdeveloper": "React Developer", "react": "React Developer",
    "sqldeveloper": "SQL Developer", "sql": "SQL Developer",
    "sapdeveloper": "SAP Developer", "etldeveloper": "ETL Developer",
    "etl": "ETL Developer", "devopsengineer": "DevOps Engineer",
    "mechanicalengineer": "Mechanical Engineer",
    "electricalengineer": "Electrical Engineer",
    "electricalengineering": "Electrical Engineer",
    "civilengineer": "Civil Engineer", "businessanalyst": "Business Analyst",
    "networksecurityengineer": "Network Security Engineer",
    "healthfitness": "Health & Fitness", "foodbeverages": "Food & Beverages",
    "food": "Food & Beverages", "buildingconstruction": "Building & Construction",
    "webdesigning": "Web Designing", "designing": "Web Designing",
    "design": "Designer", "designer": "Designer", "digitalmedia": "Digital Media",
    "digital": "Digital Media", "humanresources": "Human Resources",
    "hr": "Human Resources", "informationtechnology": "Information Technology",
    "it": "Information Technology", "publicrelations": "Public Relations",
    "public": "Public Relations", "operationmanager": "Operations Manager",
    "operationsmanager": "Operations Manager", "managment": "Management",
    "management": "Management", "consult": "Consultant", "consultant": "Consultant",
    "architects": "Architect", "architect": "Architect",
    "agriculture": "Agricultural", "agricultural": "Agricultural",
    "sales": "Sales", "finance": "Finance", "banking": "Banking",
    "accountant": "Accountant", "advocate": "Advocate", "arts": "Arts",
    "aviation": "Aviation", "automobile": "Automobile", "apparel": "Apparel",
    "testing": "Testing", "database": "Database", "education": "Education",
    "blockchain": "Blockchain", "bpo": "BPO", "pmo": "PMO", "pbo": "PMO",
    "nse": "Network Security Engineer",
}


def canonical_category(folder: str) -> str:
    key = re.sub(r"[^a-z]", "", folder.lower().replace("resumes", ""))
    return ALIASES.get(key, folder.strip())


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def first_page_hash(path: Path, size: int = 16) -> int:
    document = fitz.open(path)
    try:
        if not document.page_count:
            raise ValueError("PDF has no pages")
        png = document[0].get_pixmap(dpi=55, alpha=False).tobytes("png")
    finally:
        document.close()
    image = Image.open(io.BytesIO(png)).convert("L").resize((size, size))
    pixels = list(image.get_flattened_data())
    average = sum(pixels) / len(pixels)
    result = 0
    for pixel in pixels:
        result = (result << 1) | int(pixel >= average)
    return result


def hamming(left: int, right: int) -> int:
    return (left ^ right).bit_count()


def empty_profile() -> dict:
    return {
        "contact": {"name": None, "location": None, "links": []},
        "skills": [], "education": [], "experience": [], "projects": [],
        "certifications": [], "job_titles": [],
    }


def prepare(source: Path, gold_dir: Path, output: Path, count: int) -> None:
    if (output / "manifest.jsonl").exists():
        raise FileExistsError(
            f"Blind manifest already exists at {output}; refusing to resample it."
        )
    gold_pdfs = sorted((gold_dir / "gold").rglob("*.pdf"))
    if not gold_pdfs:
        raise FileNotFoundError(f"No existing gold PDFs found below {gold_dir / 'gold'}")
    gold_sha = {sha256(path) for path in gold_pdfs}
    gold_visual = [first_page_hash(path) for path in gold_pdfs]

    by_category: dict[str, list[Path]] = {}
    for path in sorted(source.rglob("*.pdf")):
        by_category.setdefault(canonical_category(path.parent.name), []).append(path)
    if count > len(by_category):
        raise ValueError(f"Requested {count} categories, only {len(by_category)} exist")

    rng = random.Random(SEED)
    categories = sorted(by_category)
    rng.shuffle(categories)
    selected: list[tuple[str, Path, str, int, int]] = []
    selected_visual: list[int] = []
    for category in categories:
        candidates = list(by_category[category])
        rng.shuffle(candidates)
        for path in candidates:
            digest = sha256(path)
            if digest in gold_sha:
                continue
            try:
                visual = first_page_hash(path)
                document = fitz.open(path)
                pages = document.page_count
                document.close()
            except Exception:
                continue
            # A 256-bit average hash is deliberately conservative here: only
            # extremely similar first pages are excluded.
            if any(hamming(visual, other) <= 12 for other in gold_visual):
                continue
            if any(hamming(visual, other) <= 12 for other in selected_visual):
                continue
            selected.append((category, path, digest, visual, pages))
            selected_visual.append(visual)
            break
        if len(selected) == count:
            break
    if len(selected) != count:
        raise RuntimeError(f"Could select only {len(selected)} of {count} blind resumes")

    pdf_dir = output / "pdfs"
    pdf_dir.mkdir(parents=True, exist_ok=False)
    manifest_rows = []
    gold_rows = []
    for category, source_path, digest, _, pages in selected:
        resume_id = f"blind_{slug(category)}__{digest[:16]}"
        relative_pdf = Path("pdfs") / f"{resume_id}.pdf"
        shutil.copy2(source_path, output / relative_pdf)
        manifest_rows.append({
            "id": resume_id, "category": category, "pdf": relative_pdf.as_posix(),
            "sha256": digest, "pages": pages, "selection_seed": SEED,
            "source_corpus": "Milestone_2 original PDF corpus",
            "excluded_against_gold_count": len(gold_pdfs),
        })
        gold_rows.append({
            "id": resume_id, "category": category, "eval_split": "blind_test",
            "pdf": relative_pdf.as_posix(), "_annotated": False,
            **empty_profile(),
        })
    for name, rows in (("manifest.jsonl", manifest_rows), ("gold.jsonl", gold_rows)):
        with (output / name).open("x", encoding="utf-8") as stream:
            for row in rows:
                stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    (output / "README.md").write_text(
        "# Blind resume test set\n\n"
        "This set was selected structurally with seed 20260809. Exact SHA-256 "
        "duplicates and visually near-identical first pages of the existing 86 "
        "gold resumes were excluded. One resume was selected per category.\n\n"
        "Annotate `gold.jsonl` against the PDFs before opening model "
        "predictions. Change `_annotated` to `true` only after completing and "
        "reviewing each record. Do not tune prompts or normalization on these "
        "documents before recording the frozen-pipeline result.\n\n"
        "## Skill annotation contract\n\n"
        "Record explicit, atomic competencies rather than proficiency sentences or "
        "bundled lists. For example, `Proficient in bookkeeping with Tally` becomes "
        "`Bookkeeping` and `Tally`. Split tools named inside suites or parentheses, "
        "exclude duties and inferred skills, and preserve the specific technology "
        "named by the source. Canonical vendor/product expansion is allowed only "
        "when unambiguous (for example MS Excel, Photoshop or G Suite). Do not "
        "expand ambiguous generic names without vendor context.\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--gold-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--count", type=int, default=DEFAULT_COUNT)
    args = parser.parse_args()
    prepare(args.source, args.gold_dir, args.output, args.count)


if __name__ == "__main__":
    main()
