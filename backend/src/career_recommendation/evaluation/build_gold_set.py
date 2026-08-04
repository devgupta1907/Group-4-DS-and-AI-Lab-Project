"""
Career Recommendation — gold set builder.

Evaluation metrics need ground truth: (candidate profile -> correct ESCO
occupation) pairs. This script bootstraps a labelled set directly from
the ESCO taxonomy so evaluation can run today, while a human-labelled
set is prepared.

HOW IT WORKS
    For a sampled occupation, a synthetic candidate profile is built from
    that occupation's own data:
        job_titles  <- an ALTERNATIVE label (not the preferred label)
        skills      <- a random SUBSET of its essential skills
        experience  <- another alternative label, or the preferred label
    The correct answer is that occupation's ESCO URI.

    Holding out the preferred label and sampling only a subset of skills
    stops the task from being trivial string matching — the system has to
    generalise from partial evidence to the right occupation.

IMPORTANT LIMITATION — STATE THIS WHEN REPORTING RESULTS
    This is a SYNTHETIC, self-consistency benchmark. Profiles are derived
    from the same ESCO text that was embedded, so scores here will be
    OPTIMISTIC relative to real resumes, which use different vocabulary,
    list transferable skills, and rarely map cleanly to one occupation.
    Treat these numbers as a regression baseline (did a change help or
    hurt?), NOT as an estimate of real-world accuracy.

Run from: backend/
    uv run python src/career_recommendation/evaluation/build_gold_set.py
"""

import json
import random
from pathlib import Path

import pandas as pd

from career_recommendation.config import CareerRecommendationModuleConfig

SEED = 42
N_PROFILES = 100
MIN_ESSENTIAL_SKILLS = 4      # occupations with fewer are skipped
SKILL_SAMPLE_MIN = 3          # how many skills go into a synthetic profile
SKILL_SAMPLE_MAX = 6

OUTPUT_PATH = Path(__file__).parent / "gold_set.json"


def _split(value) -> list[str]:
    if pd.isna(value):
        return []
    return [s.strip() for s in str(value).split(";") if s.strip()]


def build_gold_set() -> list[dict]:
    random.seed(SEED)

    df = pd.read_csv(CareerRecommendationModuleConfig.ESCO_DATA_PATH)
    print(f"Loaded {len(df)} occupations.")

    # Only occupations with enough essential skills AND at least one
    # alternative label can produce a non-trivial profile.
    usable = []
    for _, row in df.iterrows():
        essential = _split(row.get("essential_skills_text"))
        alt_labels = _split(row.get("alt_occupation_title"))
        if len(essential) >= MIN_ESSENTIAL_SKILLS and alt_labels:
            usable.append((row, essential, alt_labels))

    print(f"{len(usable)} occupations usable for profile generation.")

    sample = random.sample(usable, min(N_PROFILES, len(usable)))

    gold = []
    for i, (row, essential, alt_labels) in enumerate(sample, start=1):
        k = random.randint(SKILL_SAMPLE_MIN, min(SKILL_SAMPLE_MAX, len(essential)))
        skills = random.sample(essential, k)

        title = alt_labels[0]
        past_role = alt_labels[1] if len(alt_labels) > 1 else str(row["occupation_title"])

        gold.append({
            "profile_id": f"synthetic_{i:03d}",
            "source": "synthetic_esco",
            "profile": {
                "job_titles": [title],
                "skills": skills,
                "experience": [{"title": past_role}],
                "projects": [],
            },
            # List, because a profile can legitimately map to more than
            # one acceptable occupation. Human labellers should add
            # alternatives here rather than forcing a single answer.
            "relevant_uris": [str(row["conceptUri"])],
            "relevant_titles": [str(row["occupation_title"])],
        })

    return gold


if __name__ == "__main__":
    gold = build_gold_set()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(gold, indent=2), encoding="utf-8")

    print(f"\nWrote {len(gold)} labelled profiles to {OUTPUT_PATH}")
    print("\nExample entry:")
    print(json.dumps(gold[0], indent=2)[:900])
    print(
        "\nREMINDER: this is a synthetic self-consistency benchmark. "
        "Report it as such, and replace/extend it with human-labelled "
        "profiles before quoting these numbers as real accuracy."
    )
