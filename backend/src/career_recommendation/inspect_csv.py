"""
Run this FIRST, before rebuilding embeddings.

Prints the actual columns and sample values in the ESCO CSV so we know
exactly which fields (optional skills, alt labels, descriptions) are
available to enrich the embedded text with.

Run from: backend/
    uv run python src/career_recommendation/inspect_csv.py
"""

import pandas as pd
from career_recommendation.config import CareerRecommendationModuleConfig

path = CareerRecommendationModuleConfig.ESCO_DATA_PATH
print(f"Reading: {path}\n")

df = pd.read_csv(path)

print(f"Shape: {df.shape[0]} rows x {df.shape[1]} columns\n")
print("Columns and dtypes:")
for col in df.columns:
    print(f"  - {col}  ({df[col].dtype})")

print("\nNull counts:")
print(df.isnull().sum().to_string())

print("\nUnique occupations:", df['occupation_title'].nunique() if 'occupation_title' in df.columns else "n/a")

# Show which columns look like they hold the essential/optional distinction
print("\nLow-cardinality columns (likely relation-type / category flags):")
for col in df.columns:
    n = df[col].nunique(dropna=True)
    if n <= 15:
        print(f"  - {col}: {n} unique -> {sorted(df[col].dropna().unique().tolist())[:15]}")

print("\nFirst 3 rows (transposed for readability):")
print(df.head(3).T.to_string())
