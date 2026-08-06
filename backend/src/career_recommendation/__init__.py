from src.core.config import GlobalConfig


class CareerRecommendationModuleConfig:
    """Constants specific to the Career Recommendation module."""

    # Cleaned ESCO dataset — one row per occupation (3,039 rows), with
    # essential/optional skills already separated by the preprocessing
    # stage. Note: this is NOT the old long-format
    # occupation_skill_relations_clean.csv (one row per occupation-skill
    # pair) that the previous ingestion expected.
    ESCO_DATA_PATH = str(GlobalConfig.DATA_DIR / "Career_Recommendation_Cleaned_Dataset.csv")

    # RAG Parameters
    RETRIEVAL_TOP_K = 20
    FINAL_TOP_K = 5

    # Re-ranking weights. An essential-skill match is stronger evidence
    # of fit than an optional one, so it counts for more. These are
    # manually set, not yet tuned against a labelled validation set.
    ESSENTIAL_SKILL_WEIGHT = 1.0
    OPTIONAL_SKILL_WEIGHT = 0.4