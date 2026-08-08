"""Public registration surface for the Career Guidance Report module."""

from fastapi import FastAPI


def register_career_report(app: FastAPI) -> None:
    from src.career_report.router import router

    app.include_router(router)


__all__ = ["register_career_report"]
