# AI-Powered Intelligent Job Search and Career System

![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
![LangChain](https://img.shields.io/badge/langchain-1C3C3C?style=for-the-badge&logo=langchain&logoColor=white)
![Gemini](https://img.shields.io/badge/gemini-8E75B2?style=for-the-badge&logo=googlegemini&logoColor=white)
![HuggingFace](https://img.shields.io/badge/-HuggingFace-FDEE21?style=for-the-badge&logo=HuggingFace&logoColor=black)
![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)
![uv](https://img.shields.io/badge/uv-2b2b2b?style=for-the-badge&logo=python&logoColor=white)
![pgvector](https://img.shields.io/badge/pgvector-336791?style=for-the-badge&logo=postgresql&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/postgresql-%23316192.svg?style=for-the-badge&logo=postgresql&logoColor=white)
![LangGraph](https://img.shields.io/badge/langgraph-1C3C3C?style=for-the-badge&logo=langchain&logoColor=white)
![React](https://img.shields.io/badge/react-%2320232a.svg?style=for-the-badge&logo=react&logoColor=%2361DAFB)
![Redis](https://img.shields.io/badge/redis-%23DD0031.svg?style=for-the-badge&logo=redis&logoColor=white)

A multi-module system that converts an uploaded resume into a structured candidate profile, maps that profile onto occupations in the ESCO taxonomy, and uses the resulting role context to discover and rank live job postings. Built as a team project for the IIT Madras BS in Data Science and Applications DS and AI Lab course.

---

## Table of contents

- [Problem statement](#problem-statement)
- [Project objectives](#project-objectives)
- [System architecture](#system-architecture)
- [Tech stack](#tech-stack)
- [Repository structure](#repository-structure)
- [Running the project](#running-the-project)
- [Team members](#team-members)

---

## Problem statement

The modern job search process is fragmented, time-consuming, and largely manual. Candidates often lack clarity on which roles align with their background, and invest significant effort tailoring resumes, writing cover letters, hunting for relevant listings, and researching recruiters across multiple platforms without any intelligent system guiding or automating any part of this workflow.

## Project objectives

1. Extract and structure candidate profiles from uploaded resumes
2. Predict suitable career paths and job roles based on candidate background
3. Discover and rank relevant job listings matched against the candidate profile
4. Display a summarized report of the candidate's recommended career paths, matched job listings, and next steps in one consolidated view

## System architecture

Three modules communicate through a shared candidate profile and a shared database:

- **Resume Parsing** — routes each resume page to a vision-first parser (primary: Gemma 4 31B, multimodal; backup and repair: Gemini 2.5 Flash-Lite), validates the output against a schema, merges multi-page results, deduplicates, and encrypts sensitive fields at rest. On a schema failure it retries once against the backup model, then falls back to a partial profile with review flags rather than failing the request.

- **Career Recommendation** — flattens the candidate profile into a query, embeds it (BAAI/bge-base-en-v1.5, 768 dimensions, local CPU), retrieves the 20 nearest ESCO occupations from a Supabase pgvector index (HNSW, cosine), re-ranks to the top 5 by blending semantic similarity with exact skill overlap, and calls an LLM (Gemini 2.5 Flash-Lite) to explain each recommendation, grounded strictly in the retrieved evidence — the model may only cite occupations and skills that were actually retrieved, and every returned occupation URI is validated before the response leaves the module.

- **Job Discovery and Matching** — a seven-node LangGraph pipeline: generates search queries from the candidate profile (Gemini 2.5 Flash-Lite), searches via a self-hosted SearXNG instance, extracts postings with Crawl4AI, applies rule-based hard filters (experience, location), ranks by a hybrid of BM25 lexical score and semantic embedding similarity, and scores the shortlist with an LLM judge (Gemma 4 31B). Results are cached in Redis with a one-hour TTL. This module is evaluated independently and is not yet integrated into the shared profile flow.

![Project Architecture](./docs/architecture/architecture_diagram.png)

## Tech stack

| Layer | Technologies |
|---|---|
| **Backend** | Python 3.10+, FastAPI, `uv` for package management, SQLAlchemy 2.0 (async) with Alembic migrations |
| **Frontend** | React + TypeScript (Vite) |
| **AI / LLM** | LangChain (Career Recommendation), LangGraph (Job Discovery, 7-node `StateGraph`), Gemini API, Gemma (open-weight, multimodal) |
| **Embeddings & retrieval** | BAAI/bge-base-en-v1.5 (local, CPU), Supabase Postgres with pgvector (HNSW, cosine index) |
| **Job discovery** | SearXNG (self-hosted search), Crawl4AI (extraction), BM25 (`rank_bm25`, lexical ranking), Redis (result cache) |
| **Deployment** | Docker Compose |

## Repository structure

```
.
├── backend/              All core backend modules reside here
├── frontend/             React + TypeScript frontend
├── data/                 Datasets used for training/evaluation
├── docs/                 Milestone reports and project documentation
├── notebooks/            Exploratory analysis and preprocessing notebooks
└── docker-compose.yml    Production-like local stack
```

---

## Running the project

### Online deployment

The application has been deployed on AWS EC2 at **http://13.235.73.185:8080/** for the duration of the viva.

### Local deployment

This section covers first-time setup end to end, the optional Docker path, and the short command sequence for starting the system on subsequent days.

#### Prerequisites

Install these before starting. Each is required.

| Requirement | Notes |
|---|---|
| **Python 3.12+** | https://python.org — tick "Add to PATH" on Windows |
| **uv** | `pip install uv` (Python package manager) |
| **Node.js LTS** | https://nodejs.org — LTS version, not Current |
| **Docker Desktop** | https://docker.com/products/docker-desktop — must be running |
| **Git** | https://git-scm.com — if you want to clone from git |

> **Note:** Docker Desktop must be open and running before you start SearXNG in Step 3. On Windows, confirm it shows "Engine running" in the system tray.

#### First-time setup (uv / local)

**Step 1: Open a terminal in your desired location.**

**Step 1: Clone the repository, or download it from GitHub.**

```bash
git clone https://github.com/devgupta1907/Group-4-DS-and-AI-Lab-Project.git
```

or download directly from: https://github.com/devgupta1907/Group-4-DS-and-AI-Lab-Project

**Step 2: Go to the `Group-4-DS-and-AI-Lab-Project` folder.**

```bash
cd Group-4-DS-and-AI-Lab-Project
```

**Step 3: Create the backend environment.**

1. Go to the backend folder:

   ```bash
   cd backend

   copy .env.example .env    # Windows
   cp .env.example .env      # Mac / Linux
   ```

2. Open `backend/.env` and fill in the following values (a `.env.example` file is provided):

   | Variable | Value |
   |---|---|
   | **GOOGLE_API_KEY** | From https://aistudio.google.com/apikey |
   | **SUPABASE_URL** | Your Supabase project URL (Settings > API) |
   | **SUPABASE_SERVICE_KEY** | Service role key (Settings > API) |
   | **SUPABASE_DB_URL** | `postgresql://postgres.<ref>:<password>@...pooler.supabase.com:6543/postgres` |
   | **DATABASE_URL** | Same host as above, prefixed with `postgresql+asyncpg://` |
   | **PROFILE_ENCRYPTION_KEY** | Generate once — command below |
   | **SEARXNG_URL** | `http://localhost:8888` (set after Step 3) |

   Generate the encryption key:

   ```bash
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```

   > **Important:** `SUPABASE_DB_URL` must use port `6543`.
   >
   > **Important:** `DATABASE_URL` must start with `postgresql+asyncpg://` — not `postgresql://`. The `+asyncpg` driver is required by SQLAlchemy async.

**Step 4: Start SearXNG.**

SearXNG is the self-hosted search engine used by Job Discovery. Run it once to create the container, then start it on subsequent runs.

First time only:

```bash
docker run -d --name searxng-v1 --restart unless-stopped ^
  -p 8888:8080 ^
  -v "%CD%\searxng:/etc/searxng" ^
  searxng/searxng:latest
```

Subsequent runs:

```bash
docker start searxng-v1
```

Verify: open http://localhost:8888 in a browser — the SearXNG search page should appear.

> **Note:** Port 8888 is used intentionally. Port 8080 falls inside a Windows excluded port range on some machines.

**Step 5: Run database migrations.**

This creates all database tables.

```bash
cd backend
uv run alembic upgrade head
```

**Step 6: Start the backend.**

```bash
uv run uvicorn main:app --reload
```

Verify: open http://localhost:8000/health in a browser. It should return `{"status":"ok"}`.

> **Important:** Always run uvicorn from the `backend/` directory, not the repo root. The `data/` folder and module imports are resolved relative to `backend/`.

**Step 7: Start the frontend.**

Open a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 in a browser.

> **Note:** `npm install` is only needed the first time, or after pulling changes that update `package.json`.

**Step 8: Verify the installation.**

Run these from the `backend/` directory after the server is up:

```bash
uv run pytest          # expect: 74 passed
uv run lint-imports    # expect: 11 kept, 0 broken
```

Run this from `frontend/`:

```bash
npx eslint .            # expect: exit 0, no errors
```

#### Run using Docker: single-command start

If you want to run everything in containers without setting up Python or Node locally, Docker Compose handles the full stack — database, SearXNG, migrations, backend, and frontend.

**Setup**

1. Copy and fill the environment file as described in Step 3 above.
2. From the repo root, run:

   ```bash
   docker compose up --build
   ```

3. Open http://localhost:8080. The application is ready when all services show healthy.

**Notes**

- The first build downloads Python and Node base images and installs all dependencies. It takes several minutes; subsequent starts are fast.
- Migrations run automatically inside the backend container on every start.
- SearXNG runs inside Docker on port 8080 (internal). You do not need to start the standalone container from Step 4.

> **Important:** Do not run `docker compose up` and the local `uvicorn` server at the same time — they will conflict on port 8000.

---

### Normal startup after first-time setup

#### For uv setup

Once everything is set up, starting the system on subsequent days takes three commands in three terminals:

**Terminal 1 — SearXNG**

```bash
docker start searxng-v1
```

**Terminal 2 — Backend**

```bash
cd backend
uv run uvicorn main:app --reload
```

**Terminal 3 — Frontend**

```bash
cd frontend
npm run dev
```

Then open http://localhost:5173.

#### For Docker setup

```bash
docker compose up
```

---

## Team members

- Gaurav Kumar (22f1001105)
- Dev Gupta (22f2000888)
- Abhinav Ohri (24f1002064)
- Pranav N (22f2000117)
- Praveena N (22f3001454)

---

*Course project for the IIT Madras BS in Data Science and Applications — DS and AI Lab.*
