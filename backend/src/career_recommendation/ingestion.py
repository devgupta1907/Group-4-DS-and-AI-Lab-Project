import time

import pandas as pd
from tqdm import tqdm
from langchain_core.documents import Document
from langchain_chroma import Chroma

from core.config import GlobalConfig
from services.llm_client import document_embeddings
from career_recommendation.config import CareerRecommendationModuleConfig

EMBED_BATCH_SIZE = 100
MAX_RETRIES = 3


def _clean(value) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def _split_skills(value) -> list[str]:
    text = _clean(value)
    if not text:
        return []
    return [s.strip() for s in text.split(";") if s.strip()]


def prepare_documents(csv_path: str) -> list[Document]:
    print(f"Reading data from {csv_path}...")
    df = pd.read_csv(csv_path)
    print(f"  {len(df)} rows, {df['occupation_title'].nunique()} unique occupations")

    docs = []
    for _, row in df.iterrows():
        title = _clean(row["occupation_title"])
        uri = _clean(row["conceptUri"])
        alt_labels = _clean(row.get("alt_occupation_title"))
        description = _clean(row.get("occ_description"))
        essential = _split_skills(row.get("essential_skills_text"))
        optional = _split_skills(row.get("optional_skills_text"))

        text_payload = _clean(row.get("career_role_context"))
        if not text_payload:
            parts = [f"Occupation title: {title}."]
            if alt_labels:
                parts.append(f"Alternative titles: {alt_labels}.")
            if description:
                parts.append(f"Description: {description}.")
            if essential:
                parts.append(f"Essential skills: {'; '.join(essential)}.")
            if optional:
                parts.append(f"Optional or related skills: {'; '.join(optional)}.")
            text_payload = " ".join(parts)

        metadata = {
            "occupation_title": title,
            "occupation_uri": uri,
            "alt_occupation_title": alt_labels,
            "occ_description": description,
            "essential_skills": "; ".join(essential),
            "optional_skills": "; ".join(optional),
            "essential_skill_count": len(essential),
            "optional_skill_count": len(optional),
            "isco_group": _clean(row.get("isco_group")),
            "occupation_code": _clean(row.get("occupation_code")),
        }
        docs.append(Document(page_content=text_payload, metadata=metadata))

    return docs


# def build_vector_store():
#     """
#     Vectorizes the documents using the centralized Gemini embeddings 
#     and stores them in ChromaDB.
#     """
#     # 2. Use the CareerRecommendationModuleConfig for the specific dataset path
#     docs = prepare_documents(CareerRecommendationModuleConfig.ESCO_DATA_PATH)
#     print(f"Prepared {len(docs)} unique atomic occupation chunks.")
    
#     print("Initializing ChromaDB and embedding documents (This may take a few minutes)...")
    
#     # 3. Use the centralized embeddings instance and GlobalConfig database path
#     vectorstore = Chroma.from_documents(
#         documents=docs,
#         embedding=embeddings,
#         persist_directory=GlobalConfig.CHROMA_DB_DIR
#     )
    
#     print(f"Success! Vector Store built and persisted at: {GlobalConfig.CHROMA_DB_DIR}")

from tqdm import tqdm # Add this to the very top of your imports

def build_vector_store():
    docs = prepare_documents(CareerRecommendationModuleConfig.ESCO_DATA_PATH)
    print(f"\nPrepared {len(docs)} occupation documents.")

    model_name = (
        GlobalConfig.GEMINI_EMBEDDING_MODEL
        if GlobalConfig.EMBEDDING_PROVIDER == "gemini"
        else GlobalConfig.HF_EMBEDDING_MODEL
    )
    print(f"Provider: {GlobalConfig.EMBEDDING_PROVIDER} | Model: {model_name} | Dims: {GlobalConfig.EMBEDDING_DIM}")
    print(f"Target: {GlobalConfig.CHROMA_DB_DIR} | Collection: {GlobalConfig.CHROMA_COLLECTION}\n")

    vectorstore = Chroma(
        collection_name=GlobalConfig.CHROMA_COLLECTION,
        embedding_function=document_embeddings,
        persist_directory=GlobalConfig.CHROMA_DB_DIR,
        collection_metadata={"hnsw:space": "cosine"},
    )

    # --- Resume support: skip anything already embedded ---
    existing = set()
    try:
        got = vectorstore._collection.get(include=["metadatas"])
        existing = {m.get("occupation_uri") for m in got["metadatas"]}
    except Exception:
        pass
    if existing:
        print(f"Resuming: {len(existing)} already embedded, skipping those.\n")
        docs = [d for d in docs if d.metadata["occupation_uri"] not in existing]
        print(f"Remaining: {len(docs)}\n")

    if not docs:
        print("Nothing to do — index already complete.")
        return

    # Free tier allows 100 embed requests/minute. Stay under it.
    is_local = GlobalConfig.EMBEDDING_PROVIDER != "gemini"
    BATCH = 200 if is_local else 90
    PAUSE = 0 if is_local else 62

    total = len(docs)
    for start in range(0, total, BATCH):
        batch = docs[start:start + BATCH]

        for attempt in range(1, 6):
            try:
                vectorstore.add_documents(batch)
                break
            except Exception as exc:
                if attempt == 5:
                    print(f"\nFAILED on batch {start}: {exc}")
                    raise
                if "RESOURCE_EXHAUSTED" in str(exc) or "429" in str(exc):
                    wait = 65
                    print(f"  rate limited; waiting {wait}s...")
                else:
                    wait = 5 * attempt
                    print(f"  batch {start} attempt {attempt} failed; retrying in {wait}s...")
                time.sleep(wait)

        done = min(start + BATCH, total)
        print(f"  embedded {done}/{total}")

        if PAUSE and done < total:
            time.sleep(PAUSE)

    print(f"\nSuccess! {vectorstore._collection.count()} vectors at {GlobalConfig.CHROMA_DB_DIR}")


if __name__ == "__main__":
    build_vector_store()