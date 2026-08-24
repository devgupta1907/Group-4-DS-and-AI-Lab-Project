
from fastapi import FastAPI

from src.cv_review.api import router
from src.cv_review.schemas import CvFinding, CvReview

__all__ = ["CvFinding", "CvReview", "register_cv_review"]


def register_cv_review(app: FastAPI) -> None:
    app.include_router(router)
