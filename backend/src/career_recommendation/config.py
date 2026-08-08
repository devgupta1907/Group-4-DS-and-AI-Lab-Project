from src.core.config import GlobalConfig


class CareerRecommendationModuleConfig:
    """Constants specific to the Career Recommendation module."""

    # Cleaned ESCO dataset — one row per occupation (3,039 rows)
    ESCO_DATA_PATH = str(GlobalConfig.DATA_DIR / "Career_Recommendation_Cleaned_Dataset.csv")

    #----- RAG Parameters------

    # Number of occupations to pull from vector store for re-ranking (Step 1)
    RETRIEVAL_TOP_K = 20

    # Number of occupations sent to LLM for explanation and display to user (Step 2)
    FINAL_TOP_K = 5

    # Weights for skill type
    ESSENTIAL_SKILL_WEIGHT = 1.0
    OPTIONAL_SKILL_WEIGHT = 0.5
    SKILL_BONUS_WEIGHT = 0.02


    # We gave essential skills full weight, 50% to Optional skills.
    # We chose that ratio because ESCO itself distinguishes essential skills as required for the role versus optional ones as merely related, so an essential match is stronger evidence of fit.