import logging
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

sys.path.append(str(Path(__file__).resolve().parent / "src"))
from career_recommendation.api import router as career_recommendation_router

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)

app = FastAPI(
    title="AI-Powered Intelligent Job Search and Career System — API",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(career_recommendation_router)


@app.get("/")
def root():
    return {"status": "ok", "message": "API is running cleanly!"}



# import logging

# from fastapi import FastAPI

# from career_recommendation.api import router as career_recommendation_router

# logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

# app = FastAPI(title="AI-Powered Intelligent Job Search and Career System — API")

# app.include_router(career_recommendation_router)


# @app.get("/")
# def root():
#     return {"status": "ok"}


# # Run with: uv run uvicorn main:app --reload
