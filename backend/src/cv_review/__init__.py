"""CV review add-on: critiques a stored parsed profile.

Public surface is the router and the CvReview schema. Nothing else in the
codebase should import from this package — it is a leaf, and deliberately so:
it reads what resume_parsing already produced and writes nothing.
"""

from fastapi import FastAPI

from src.cv_review.api import router
from src.cv_review.schemas import CvFinding, CvReview

__all__ = ["CvFinding", "CvReview", "register_cv_review"]


def register_cv_review(app: FastAPI) -> None:
    app.include_router(router)
