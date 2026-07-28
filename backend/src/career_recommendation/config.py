from core.config import GlobalConfig

class CareerRecommendationModuleConfig:
    """Constants specific to the Career Recommendation module."""
    
    # Paths specific to this module
    ESCO_DATA_PATH = str(GlobalConfig.DATA_DIR / "occupation_skill_relations_clean.csv") 
    
    # RAG Parameters
    RETRIEVAL_TOP_K = 20    
    FINAL_TOP_K = 5