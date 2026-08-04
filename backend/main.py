import logging

from fastapi import FastAPI

from career_recommendation.api import router as career_recommendation_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(title="AI-Powered Intelligent Job Search and Career System — API")

app.include_router(career_recommendation_router)


@app.get("/")
def root():
    return {"status": "ok"}


# Run with: uv run uvicorn main:app --reload
