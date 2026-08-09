# AI-Powered Intelligent Job Search and Career System

A multi-module system that converts an uploaded resume into a structured candidate profile, maps that profile onto occupations in the ESCO taxonomy, and uses the resulting role context to discover and rank live job postings. Built as a team project for the IIT Madras BS in Data Science and Applications DS and AI Lab course.


## Run the complete application

Copy `backend/.env.example` to `backend/.env`, set `PROFILE_ENCRYPTION_KEY` and `GOOGLE_API_KEY`, then start the production-like local stack:

```bash
docker compose up --build
```

Open <http://localhost:8080>. PostgreSQL, SearXNG, migrations, the FastAPI backend, and the frontend are started together.

The default image uses direct vision for scanned PDFs and does not install Docling. To build the optional experimental Docling route:

```bash
ENABLE_DOCLING=true RESUME_SCANNED_PDF_STRATEGY=docling_text docker compose up --build
```

For hot-reload development:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

The development frontend is available at <http://localhost:5173> and the API at <http://localhost:8000>.

## Table of contents

- [Problem statement](#problem-statement)
- [Project objectives](#project-objectives)
- [System architecture](#system-architecture)
- [Tech stack](#tech-stack)
- [Evaluation](#evaluation)
- [Known limitations](#known-limitations)
- [Repository structure](#repository-structure)
- [Team members](#team-members)

---

## Problem statement

The modern job search process is fragmented, time-consuming, and largely manual. Candidates often lack clarity on which roles align with their background, and invest significant effort tailoring resumes, writing cover letters, hunting for relevant listings, and researching recruiters across multiple platforms without any intelligent system guiding or automating any part of this workflow.

## Project objectives

1. Extract and structure candidate profiles from uploaded resumes
2. Predict suitable career paths and job roles based on candidate background
3. Discover and rank relevant job listings matched against the candidate profile
4. Display a summarized report of the candidate's recommended career paths, matched job listings, and next steps in one consolidated view.

## System architecture

Three modules communicate through a shared candidate profile and a shared database:

- **Resume Parsing** — routes each resume page to a vision-first parser (primary: Gemma 4 31B, multimodal; backup and repair: Gemini 2.5 Flash-Lite), validates the output against a schema, merges multi-page results, deduplicates, and encrypts sensitive fields at rest. On a schema failure it retries once against the backup model, then falls back to a partial profile with review flags rather than failing the request.

- **Career Recommendation** — flattens the candidate profile into a query, embeds it (BAAI/bge-base-en-v1.5, 768 dimensions, local CPU), retrieves the 20 nearest ESCO occupations from a Supabase pgvector index (HNSW, cosine), re-ranks to the top 5 by blending semantic similarity with exact skill overlap, and calls an LLM (Gemini 2.5 Flash-Lite) to explain each recommendation, grounded strictly in the retrieved evidence — the model may only cite occupations and skills that were actually retrieved, and every returned occupation URI is validated before the response leaves the module.

- **Job Discovery and Matching** — a seven-node LangGraph pipeline: generates search queries from the candidate profile (Gemini 2.5 Flash-Lite), searches via a self-hosted SearXNG instance, extracts postings with Crawl4AI, applies rule-based hard filters (experience, location), ranks by a hybrid of BM25 lexical score and semantic embedding similarity, and scores the shortlist with an LLM judge (Gemma 4 31B). Results are cached in Redis with a one-hour TTL. This module is evaluated independently and is not yet integrated into the shared profile flow.

![Project Architecure](./docs/architecture/architecture_diagram.png)

## Tech stack

- **Backend:** Python 3.10+, FastAPI, `uv` for package management, SQLAlchemy 2.0 (async) with Alembic migrations
- **Frontend:** React + TypeScript (Vite)
- **AI / LLM:** LangChain (Career Recommendation), LangGraph (Job Discovery, 7-node `StateGraph`), Gemini API, Gemma (open-weight, multimodal)
- **Embeddings & retrieval:** BAAI/bge-base-en-v1.5 (local, CPU), Supabase Postgres with pgvector (HNSW, cosine index)
- **Job discovery:** SearXNG (self-hosted search), Crawl4AI (extraction), BM25 (`rank_bm25`, lexical ranking), Redis (result cache)
- **Deployment:** Docker Compose

## Known limitations

Stated plainly, per the Milestone 5 report:

- **The LLM judge stage in Job Discovery does not currently pass its own acceptance criteria** — no prompt variant tested reaches a passing rate; the best achieves 0.5 on schema validity and 0.5 on calibration.
- **Crawl success caps at 50%** on the best configuration — roughly half of discovered job postings cannot currently be extracted (client-side rendering, bot blocking, or missing structured metadata).
- **Resume Parsing has no formal per-field precision/recall/F1** in this milestone — functional and integration-verified, but not yet measured at that granularity.
- The occupation taxonomy (ESCO) is European in origin, so regional and emerging job titles (e.g. "Network Security Engineer") map less reliably — a measured, not hypothetical, source of error.

## Repository structure

```
.
├── backend/            FastAPI backend
├── frontend/            React + TypeScript frontend
├── data/                 Datasets used for training/evaluation
├── docs/                 Milestone reports and project documentation
├── notebooks/            Exploratory analysis and preprocessing notebooks
└── docker-compose.yml    Production-like local stack
```

## Team members

- Gaurav Kumar (22f1001105)
- Dev Gupta (22f2000888)
- Abhinav Ohri (24f1002064)
- Pranav N (22f2000117)
- Praveena N (22f3001454)
---

*Course project for the IIT Madras BS in Data Science and Applications — DS and AI Lab.*
