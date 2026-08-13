# Overview

**DiscoverMyRole — AI-Powered Intelligent Job Search and Career System**
IIT Madras · Data Science and AI Project · Group 4 · Milestone 6

---

## 1. Purpose

A candidate looking for their next role has to work across three disconnected surfaces: a resume they maintain by hand, career-guidance sites that describe occupations in generic terms, and job boards that match on keywords. Nothing carries context from one to the next.

DiscoverMyRole closes that gap. It converts an uploaded resume into a structured candidate profile, maps that profile onto occupational roles from a standard taxonomy, and uses that role context to discover and rank live job postings, in one pass, from one application.

The objective is a system that goes from raw resume to a ranked, explained shortlist of roles and postings without the user cross-referencing anything manually, and that shows its evidence at every step rather than returning an unexplained score.

The system is organised as inference modules connected through one shared candidate profile: **Resume Parsing**, **Career Recommendation**, and **Job Discovery and Matching**, with supporting **Career Report** and **CV Review** modules. A **Feedback** module was added in Milestone 6 as the value-added enhancement.

---

## 2. Architecture Summary

The backend exposes one router per module inside a single FastAPI application. Data flows input → model → output as follows:

```
Resume (PDF / DOCX / image)
        │
        ▼
┌─────────────────────────┐
│  RESUME PARSING         │  Gemini 3.5 Flash (vision, 150 DPI)
│  vision routing →       │  → schema validation
│  extraction → merge     │  → Gemini 2.5 Flash-Lite fallback retry
└─────────────────────────┘
        │
        ▼  Candidate Profile JSON  (encrypted at rest)
        │
┌─────────────────────────┐
│  CAREER RECOMMENDATION  │  bge-base-en-v1.5 embedding (local CPU)
│  flatten → embed →      │  → pgvector HNSW cosine, Top-K 20
│  retrieve → re-rank →   │  → deterministic re-rank (skill bonus 0.02)
│  explain                │  → Gemini 3.5 Flash-Lite, Top-N 7
└─────────────────────────┘
        │
        ▼  Ranked ESCO occupations + grounded explanations
        │
┌─────────────────────────┐
│  JOB DISCOVERY &        │  Gemini 2.5 Flash-Lite (query gen)
│  MATCHING               │  → job API / SearXNG + Crawl4AI
│  7-node LangGraph       │  → zero-LLM extraction, hard filter
│  pipeline               │  → BM25 0.5 + embedding 0.5 hybrid rank
└─────────────────────────┘  → batched judge over top 5
        │
        ▼  Ranked shortlist with match score and rationale
        │
┌─────────────────────────┐
│  CAREER REPORT          │  HTML + PDF, orchestrated sequentially
└─────────────────────────┘

        ┌──────────────────────────────────────────┐
        │  FEEDBACK  (isolated — nothing imports)  │
        │  floating control on every screen        │
        └──────────────────────────────────────────┘
```

### Module contracts

| Module | Receives | Produces |
|---|---|---|
| Resume Parsing | Uploaded resume (PDF / DOCX / image) | Validated Candidate Profile JSON |
| Career Recommendation | Candidate Profile JSON | Top-N ranked ESCO occupations with grounded explanations |
| Job Discovery and Matching | Candidate Profile JSON + recommended roles | Ranked shortlist of job postings with match score and rationale |
| Career Report | Profile + recommendations + shortlist | HTML and PDF career report |
| CV Review | Stored candidate profile | Recruiter-style critical findings (read-only) |
| Feedback | Rating, reason, optional comment, optional profile identifier | Stored feedback record; aggregate summary counts |

### Request flow

A resume is uploaded and parsed into a profile. The profile is embedded and matched against the ESCO index to produce ranked career recommendations with explanations. Those recommended roles seed job search and matching, which returns a ranked shortlist. Independently of that flow, a floating feedback control is available on every screen and writes directly to the feedback table.

The Feedback module is architecturally isolated, no other module imports it, so it can fail or be disabled without affecting the recommendation or job-search paths. This is enforced automatically by an import-linter contract.

---

## 3. Deployed Components

| Component | What it is | Where it runs |
|---|---|---|
| **Frontend** | React 19 + TypeScript + Vite, served via nginx | AWS EC2 (t3.medium), port 8080 · locally on Vite dev server, port 5173 |
| **Backend API** | Single FastAPI application exposing all module routers | AWS EC2, behind the frontend · locally on port 8000 |
| **Database + vector store** | Supabase PostgreSQL with pgvector, HNSW cosine index. Holds candidate profiles, recommendation runs, the job store, feedback, and the 3,039-occupation ESCO index | Hosted (Supabase), not run locally |
| **Embedding model** | `BAAI/bge-base-en-v1.5`, 768-dim, 110M params | Local CPU inside the backend process — no GPU anywhere |
| **Generative models** | Gemini 3.5 Flash, Gemini 3.5 Flash-Lite, Gemini 2.5 Flash-Lite | Hosted API, called per request |
| **SearXNG** | Self-hosted metasearch, Job Discovery fallback | Docker container, port 8888 |
| **Crawl4AI** | Headless-browser extraction for postings without structured metadata | In-process, self-hosted |

### Live deployment

**http://13.235.73.185:8080/** — AWS EC2, active for the duration of the viva.

If the hosted URL is unavailable, the local deployment produces identical output and should be used as the fallback. Setup instructions are in [`../README.md`](../README.md).


---

## Document map

| File | Contents |
|---|---|
| `OVERVIEW.md` | This document — purpose, architecture, deployed components |
| [`TECHNICAL_DOC.md`](TECHNICAL_DOC.md) | Environment, data pipeline, model architecture, training and evaluation summaries, inference, deployment, system design, error handling, reproducibility |
| [`LICENSES.md`](LICENSES.md) | Code license, dataset licenses, model sources and citations |
| [`FUTURE_WORK.md`](FUTURE_WORK.md) | Extensions, known limitations, how to update the system, maintainers.
