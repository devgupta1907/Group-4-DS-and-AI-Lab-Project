import sqlite3, struct, json, math
from sentence_transformers import SentenceTransformer
from core.config import GlobalConfig

import os

DB_PATH = os.path.join(GlobalConfig.CHROMA_DB_DIR, "chroma.sqlite3")


from db.chroma_manager import get_vector_store


vectorstore = get_vector_store()

collection = vectorstore._collection
print(f"Collection: {collection.name}")
print(f"Total embedded occupations: {collection.count()}")


query = "powerbi"
print(f"\nQuery: \"{query}\"\n")

results = vectorstore.similarity_search_with_relevance_scores(query, k=20)

print("Top 20 matches:")
for doc, score in results:
    title = doc.metadata.get("occupation_title")
    uri = doc.metadata.get("occupation_uri")
    print(f"  {score:.4f}  {title}   ({uri})")

# --- 4. Validation checks on the results (data integrity, not just similarity) ---
print("\n--- Validation checks on returned results ---")
checks = []

checks.append(("All 20 results returned", len(results) == 20))
checks.append(("All results have a non-empty occupation_title",
                all(doc.metadata.get("occupation_title") for doc, _ in results)))
checks.append(("All results have a valid ESCO URI",
                all(doc.metadata.get("occupation_uri", "").startswith(
                    "http://data.europa.eu/esco/occupation/") for doc, _ in results)))
checks.append(("Results are sorted by descending relevance score",
                all(results[i][1] >= results[i + 1][1] for i in range(len(results) - 1))))
checks.append(("No duplicate occupations in top-20",
                len({doc.metadata.get("occupation_title") for doc, _ in results}) == len(results)))

for desc, passed in checks:
    print(f"[{'PASS' if passed else 'FAIL'}] {desc}")

print(f"\n{sum(p for _, p in checks)}/{len(checks)} checks passed.")