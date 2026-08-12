"""Public registration surface for the user feedback module."""

from fastapi import FastAPI


def register_feedback(app: FastAPI) -> None:
    from src.feedback.api import router

    app.include_router(router)


__all__ = ["register_feedback"]
