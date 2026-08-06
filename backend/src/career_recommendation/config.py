from src.core.config import GlobalConfig


class CareerRecommendationModuleConfig:
    """Constants specific to the Career Recommendation module."""

    # Cleaned ESCO dataset — one row per occupation (3,039 rows), with
    # essential/optional skills already separated by preprocessing.
    ESCO_DATA_PATH = str(GlobalConfig.DATA_DIR / "Career_Recommendation_Cleaned_Dataset.csv")

    # RAG Parameters
    RETRIEVAL_TOP_K = 20
    FINAL_TOP_K = 5
    ESSENTIAL_SKILL_WEIGHT = 1.0
    OPTIONAL_SKILL_WEIGHT = 0.5
    SKILL_BONUS_WEIGHT = 0.02