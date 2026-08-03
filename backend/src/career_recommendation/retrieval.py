"""
Career Recommendation — Retrieval step.

Takes a validated Candidate Profile JSON (output of Resume Parsing) and
pulls the top-K nearest ESCO occupations from the persisted ChromaDB
index built by ingestion.py.

Works against the enriched v2 index, whose documents contain:
    Occupation title / Alternative titles / Description /
    Essential skills / Optional or related skills
"""

from langchain_core.documents import Document

from core.config import GlobalConfig
from db.chroma_manager import get_vector_store
from career_recommendation.config import CareerRecommendationModuleConfig

# BGE models are asymmetric: short queries must carry this instruction
# prefix so they land near long passages in the vector space. Documents
# are indexed WITHOUT a prefix — only the query side gets it.
# Gemini handles this via task_type instead (RETRIEVAL_QUERY vs
# RETRIEVAL_DOCUMENT), so no prefix is applied when using Gemini.
BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


def build_query_text(candidate_profile: dict) -> str:
    """
    Turns a Candidate Profile dict into a single text string for
    embedding + semantic search against the ESCO index.

    Mirrors the shape of the indexed documents (title-like signal first,
    then skills, then free-text context) so the query and the documents
    are comparable.
    """
    parts = []

    job_titles = candidate_profile.get("job_titles") or []
    if job_titles:
        parts.append("Occupation title: " + "; ".join(job_titles))

    experience = candidate_profile.get("experience") or []
    exp_titles = [e.get("title") for e in experience if e.get("title")]
    if exp_titles:
        parts.append("Past roles: " + "; ".join(exp_titles))

    skills = candidate_profile.get("skills") or []
    if skills:
        parts.append("Skills: " + "; ".join(skills))

    projects = candidate_profile.get("projects") or []
    project_text = [p.get("description", "") for p in projects if p.get("description")]
    if project_text:
        parts.append("Project experience: " + " ".join(project_text))

    education = candidate_profile.get("education") or []
    edu_text = [
        e.get("degree") or e.get("field") or ""
        for e in education
        if isinstance(e, dict) and (e.get("degree") or e.get("field"))
    ]
    if edu_text:
        parts.append("Education: " + "; ".join(t for t in edu_text if t))

    if not parts:
        raise ValueError(
            "Candidate profile has no usable signal (skills / job titles / "
            "experience / projects) to build a retrieval query from."
        )

    query_text = ". ".join(parts)

    if GlobalConfig.EMBEDDING_PROVIDER != "gemini":
        query_text = BGE_QUERY_PREFIX + query_text

    return query_text


def retrieve_candidate_occupations(candidate_profile: dict) -> list[tuple[Document, float]]:
    """
    Step 1 of Career Recommendation: embed the candidate profile and pull
    the top-K (RETRIEVAL_TOP_K = 20) nearest ESCO occupations from the
    persisted ChromaDB index.

    Returns a list of (Document, relevance_score) tuples ordered by
    descending relevance. Each Document carries occupation_title,
    occupation_uri, essential_skills and optional_skills in metadata.
    """
    vectorstore = get_vector_store()
    query_text = build_query_text(candidate_profile)

    return vectorstore.similarity_search_with_relevance_scores(
        query_text,
        k=CareerRecommendationModuleConfig.RETRIEVAL_TOP_K,
    )


if __name__ == "__main__":
    # Manual smoke test only — not a substitute for the formal
    # Milestone 5 Recall@K / Precision@K / MRR evaluation.
    sample_profile = {
        "job_titles": ["Data Analyst"],
        "skills": ["Python", "SQL", "data visualisation", "statistics"],
        "experience": [{"title": "Junior Data Analyst"}],
        "projects": [],
    }
    for doc, score in retrieve_candidate_occupations(sample_profile):
        md = doc.metadata
        print(
            f"{score:.4f}  {md['occupation_title']:40s} "
            f"(ess={md.get('essential_skill_count', 0)}, opt={md.get('optional_skill_count', 0)})"
        )