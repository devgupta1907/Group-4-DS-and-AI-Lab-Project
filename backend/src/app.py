"""FastAPI application factory.

Its only job is composition: build the app, wire CORS, mount module routers and
register module exception handlers. No business logic ever lands here.

This is now the SINGLE application. `main.py` is a thin entry point that
imports `create_app()` — previously it built a second, separate app that
mounted only Career Recommendation, so the two modules could never see
each other.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.career_recommendation.api import router as career_recommendation_router
from src.core.config import get_settings
from src.resume_parsing import register_resume_parsing


def create_app() -> FastAPI:
    settings = get_settings()

    logging.basicConfig(
        level=logging.DEBUG if settings.debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    app = FastAPI(
        title="AI-Powered Intelligent Job Search and Career System — API",
        version="1.0.0",
        debug=settings.debug,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["meta"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    register_resume_parsing(app)
    app.include_router(career_recommendation_router)

    return app
