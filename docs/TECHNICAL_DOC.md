# Technical Documentation

**DiscoverMyRole — AI-Powered Intelligent Job Search and Career System**
IIT Madras · Data Science and AI Lab Project · Group 4 · Milestone 6

> This document is the comprehensive technical reference: how the system works, what is inside it, and how to reproduce it. For step-by-step setup instructions, see the [README](../README.md).

---

## Table of Contents

**A. Overview**
- [A.1 Purpose](#a1-purpose)
- [A.2 Architecture Summary](#a2-architecture-summary)
- [A.3 Deployed Components](#a3-deployed-components)

**B. Technical Documentation**
1. [Environment Setup](#1-environment-setup)
2. [Data Pipeline](#2-data-pipeline)
3. [Model Architecture](#3-model-architecture)
4. [Training Summary](#4-training-summary)
5. [Evaluation Summary](#5-evaluation-summary)
6. [Inference Pipeline](#6-inference-pipeline)
7. [Deployment Details](#7-deployment-details)
8. [System Design Considerations](#8-system-design-considerations)
9. [Error Handling & Monitoring](#9-error-handling--monitoring)
10. [Reproducibility Checklist](#10-reproducibility-checklist)

---

# A. Overview

## A.1 Purpose

**Problem.** A candidate looking for work has to do three separate things badly: interpret their own resume into a structured summary of what they actually offer, work out which occupational roles that background maps onto, and then search job boards for postings matching those roles. These are normally done across disconnected tools — resume builders, career-guidance sites, and job boards — with the candidate acting as the integration layer between them.

**Objective.** Build one end-to-end application that converts an uploaded resume into a structured candidate profile, maps that profile onto occupational roles from a standard taxonomy, and uses that role context to discover and rank live job postings — producing a ranked, explained shortlist of both roles and postings from a single upload.

**Scope constraint that shaped the whole system.** The project has no labelled training data of the kind these tasks would require: no (resume → correct occupation) pairs, no hiring-outcome labels. Every design decision follows from that. The system performs **no gradient-based training anywhere**. Every model is pretrained and used either zero-shot through a schema-constrained prompt, or as a frozen encoder producing embeddings. The configurable surface is prompts, output schemas, retrieval parameters, and scoring weights — nothing else.

## A.2 Architecture Summary

The backend exposes one router per module inside a single FastAPI application. Data flows input → model → output as follows:

```
Resume file (PDF / DOCX / image)
        │
        ▼
┌──────────────────────┐
│  RESUME PARSING      │  vision-first routing → Gemini 3.5 Flash (150 DPI)
│                      │  → schema validation → fallback retry → merge
└──────────┬───────────┘
           │  Candidate Profile JSON  (contact, skills, education,
           │                           experience, projects,
           │                           certifications, job_titles)
           ▼
┌──────────────────────┐
│ CAREER               │  flatten → BGE embed → pgvector top-20
│ RECOMMENDATION       │  → deterministic re-rank → top-7
│                      │  → Gemini explanation → URI validation
└──────────┬───────────┘
           │  Top-7 ESCO occupations + explanations + skill gaps
           ▼
┌──────────────────────┐
│ JOB DISCOVERY &      │  query gen → search → zero-LLM extraction
│ MATCHING             │  → hard filter → BM25+embedding hybrid rank
│  (7-node LangGraph)  │  → batched judge
└──────────┬───────────┘
           │  Ranked shortlist of 5 postings + match scores + rationale
           ▼
┌──────────────────────┐
│  CAREER REPORT       │  orchestrates the three above sequentially
└──────────┬───────────┘
           ▼
     HTML + PDF report

   ┌────────────────────────────────────────────┐
   │  FEEDBACK  (isolated — nothing imports it) │
   │  floating control on every screen          │
   └────────────────────────────────────────────┘
```

### Module interfaces

| Module | Receives | Produces |
|---|---|---|
| Resume Parsing | Uploaded resume (PDF / DOCX / image) | Validated Candidate Profile JSON |
| Career Recommendation | Candidate Profile JSON | Top-N ranked ESCO occupations with grounded explanations |
| Job Discovery and Matching | Candidate Profile JSON + recommended roles | Ranked shortlist of job postings with match score and rationale |
| Career Report | Profile + recommendations + shortlist | HTML and PDF career report |
| CV Review | Stored candidate profile | Recruiter-style critical findings (read-only) |
| Feedback | Rating, reason, optional comment, optional profile identifier | Stored feedback record; aggregate summary counts |

### Component and technology map

| Module | Component | Technology |
|---|---|---|
| Resume Parsing | Primary parser | Gemini 3.5 Flash, vision-only, 150 DPI |
| Resume Parsing | Backup and repair | Gemini 2.5 Flash-Lite |
| Career Recommendation | Embedding model | BAAI/bge-base-en-v1.5, 768 dim, local CPU |
| Career Recommendation | Vector store | Supabase PostgreSQL, pgvector, HNSW cosine index |
| Career Recommendation | Explanation model | Gemini 3.5 Flash-Lite |
| Job Discovery and Matching | Query generation | Gemini 3.5 Flash-Lite |
| Job Discovery and Matching | Judge | Batched judge call over the top 5 |
| Job Discovery and Matching | Search and crawl | Azudhan job API (primary); SearXNG + Crawl4AI (fallback) |
| Job Discovery and Matching | Ranking | BM25 (rank_bm25) + bge-base-en-v1.5 cosine similarity |
| Feedback | Storage | Supabase PostgreSQL via FeedbackRepository |
| Frontend | Application | React 19, TypeScript, Vite, served via nginx |

**Request flow.** A resume is uploaded and parsed into a profile. The profile is embedded and matched against the occupation index to produce ranked career recommendations with explanations. Those recommended roles seed job search and matching, which returns a ranked shortlist. Independently of that flow, a floating feedback control is available on every screen and writes directly to the feedback table. The Feedback module is architecturally isolated — no other module imports it — so it can fail or be disabled without affecting the recommendation or job-search paths.

## A.3 Deployed Components

| Component | What it is | Where it lives |
|---|---|---|
| Frontend | React 19 + TypeScript SPA, built with Vite, served by nginx | AWS EC2 (t3.medium), port 8080 |
| Backend API | Single FastAPI application exposing all six module routers | Same EC2 instance, port 8000 (proxied) |
| Database + vector store | Supabase PostgreSQL with the pgvector extension, HNSW cosine index over 3,039 ESCO occupation vectors | Supabase managed hosting, `ap-northeast-2` |
| Embedding model | `BAAI/bge-base-en-v1.5` (110M params, ~450 MB) | Runs **locally on CPU** inside the backend process; cached from Hugging Face on first start |
| Generative models | Gemini 3.5 Flash, Gemini 3.5 Flash-Lite, Gemini 2.5 Flash-Lite | Hosted Google API — nothing is self-hosted |
| Search | SearXNG metasearch | Self-hosted Docker container, port 8888 |
| Crawler | Crawl4AI (headless Chromium) | In-process, invoked by the Job Discovery fallback path |

**Live URL:** http://13.235.73.185:8080/ — active for the viva window.

 If the hosted URL is unavailable, the local deployment produces identical output and is the intended fallback.

---

# B. Technical Documentation

## 1. Environment Setup

### 1.1 Requirements

| Requirement | Version / detail |
|---|---|
| Python | **3.12+**, managed with `uv` (`pip install uv`) |
| Node.js | **LTS** version (not Current) — for the Vite/React frontend |
| Docker Desktop | Required for SearXNG; must be running before setup |
| Git | Optional — only if cloning rather than downloading |
| Operating system | Developed and run on Windows via PowerShell. No OS-specific native dependency outside Crawl4AI's browser automation, which needs a Proactor event loop on Windows (see §9) |
| GPU | **None required anywhere.** All large models are called over hosted APIs; the only local model is the 110M-parameter bge-base-en-v1.5 encoder, which runs on CPU |
| Memory | ~600 MB to 1 GB for the application stack, plus 100–200 MB per concurrent headless browser context used by the crawler |
| Disk | ~450 MB for the cached BGE model |

### 1.2 Dependency management

Backend dependencies are declared in `backend/pyproject.toml` with a committed `backend/uv.lock`. There is no loose `requirements.txt` — **`uv sync` is the single source of truth** for a reproducible install, because the lockfile pins exact resolved versions where a `requirements.txt` would not.

```bash
cd backend
uv sync                 # creates the venv and installs pinned dependencies
uv run <command>        # runs inside that venv, no activate step
```

Frontend dependencies are declared in `frontend/package.json`:

```bash
cd frontend
npm install
```

### 1.3 Key libraries

| Layer | Library |
|---|---|
| Web framework | FastAPI, uvicorn |
| ORM / migrations | SQLAlchemy 2.0 (async), Alembic, asyncpg, psycopg2 (ingestion writes only) |
| Config | pydantic-settings |
| Orchestration | LangChain (Career Recommendation), LangGraph StateGraph (Job Discovery) |
| Embedding | sentence-transformers |
| Lexical ranking | rank_bm25 |
| Document processing | PyMuPDF, python-docx, Pillow / OpenCV |
| Crawling / search | Crawl4AI, SearXNG (external container) |
| Encryption | cryptography (Fernet) |
| Testing / quality | pytest, import-linter, ESLint |
| Frontend | React 19, TypeScript, Vite |

### 1.4 External services

| Service | Purpose | How it is started |
|---|---|---|
| SearXNG | Self-hosted metasearch used as the Job Discovery fallback path | `docker start searxng-v1` — served on port **8888** |
| Supabase PostgreSQL | Single centralised database with the pgvector extension for all modules | Hosted; reached via the configured connection string, not run locally |

> Port 8888 is intentional. Port 8080 falls inside a Windows excluded port range on some machines.

### 1.5 Configuration and secrets

All model identifiers, API keys, and connection strings are held in environment configuration rather than in source code, so a retired or rate-limited provider can be swapped without a code change. A committed `.env.example` lists every key the application reads, with placeholder values. **No real secret is committed to the repository.**

| Variable | Purpose |
|---|---|
| `GOOGLE_API_KEY` | Gemini API key — Resume Parsing, Career Recommendation explanations, Job Discovery query generation. From https://aistudio.google.com/apikey |
| `SUPABASE_URL` | Supabase project URL (Settings → API) |
| `SUPABASE_SERVICE_KEY` | Service-role key (Settings → API) |
| `SUPABASE_DB_URL` | `postgresql://postgres.<ref>:<password>@...pooler.supabase.com:6543/postgres` |
| `DATABASE_URL` | Same host, prefixed `postgresql+asyncpg://` |
| `PROFILE_ENCRYPTION_KEY` | Field-level encryption of retained sensitive profile fields |
| `SEARXNG_URL` | `http://localhost:8888` |

Generate the encryption key once:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

> **`SUPABASE_DB_URL` must use port 6543** (the transaction pooler), to stay within the pooled-connection limit.
>
> **`DATABASE_URL` must start with `postgresql+asyncpg://`**, not `postgresql://`. The `+asyncpg` driver is required by SQLAlchemy async and the application will fail at startup without it.

Full step-by-step setup: [README.md](../README.md).

---

## 2. Data Pipeline

### 2.1 Dataset sources

| Dataset | Source | Role |
|---|---|---|
| Resume corpus | Kaggle `hadikp/resume-data-pdf` — 8,905 single-page, image-only resume PDFs, with an 86-record hand-annotated gold subset | Development and evaluation of the Resume Parsing module |
| Occupation taxonomy | ESCO v1.2.1 English classification — 3,039 occupations, 13,939 skills, 126,051 occupation-skill relations | Retrieval knowledge base for Career Recommendation, indexed in full |
| Career Recommendation ground truth | 134 category-to-occupation mappings, generated by keyword matching against ESCO titles and reviewed by hand | Ground truth for retrieval and ranking metrics; **a proxy, not direct occupation labels** |
| Job Matching golden set | 86 candidates paired with a 10-job pool each, drawn from the Candidate Job Role Dataset and the LinkedIn Job Postings Dataset (both Kaggle) | Offline ranking evaluation with real BM25 and embedding scores |
| Live discovery store | Populated at runtime from the job API / SearXNG search results and Crawl4AI extraction, deduplicated by a hash of the normalised posting URL | Runtime job postings; not used for offline experiments |

### 2.2 Access and download

- The resume corpus and job-posting datasets are downloaded from their respective Kaggle listings and are **not redistributed inside the repository**. The `data/` directory documents the expected file layout.
- ESCO v1.2.1 English is downloaded from the official ESCO portal as three CSV files: occupations, skills, and occupation-skill relations.
- No credential is required to download ESCO. A Kaggle account and API token are required for the Kaggle-hosted datasets.

### 2.3 Licensing

| Asset | License / terms | Note |
|---|---|---|
| ESCO v1.2.1 | European Union open data — free reuse permitted with attribution to the European Commission | Attribution: © European Union, 2024. ESCO classification. |
| Kaggle datasets (resume corpus, Candidate Job Role, LinkedIn Job Postings) | Per each dataset's own Kaggle license page | **Not redistributed** — evaluators download them under their own Kaggle account, which keeps the project clear of any redistribution term |
| `BAAI/bge-base-en-v1.5` | MIT (model weights, via Hugging Face) | Pulled at runtime, not vendored |
| Gemini models | Google API Terms of Service | Accessed over hosted API; no weights held |
| Crawled job postings | Third-party site content | Retained only as extracted structured fields and embeddings for matching, deduplicated by URL hash; not republished |
| Project source code | See `LICENSE` at repository root | — |

### 2.4 Where data lives

| Data | Location |
|---|---|
| Raw datasets | `data/` — `Career_Recommendation_Cleaned_Dataset.csv`, `Job_Matching_Eval_dataset.xlsx`, `resume_dataset.zip`, `Job_Ranking_Preprocessed.zip`. **Gitignored.** |
| Sample / mock data | `data/sample_data/` — a few sample resumes and an ESCO subset for smoke-testing without the full corpus |
| Gold evaluation set | `backend/src/career_recommendation/evaluation/gold.jsonl` (86 records) + `category_to_esco.json` (134 mappings) |
| Built ESCO vector index | **Supabase PostgreSQL** (pgvector) — pre-populated; not rebuilt during normal setup |
| Runtime job store | Supabase PostgreSQL — `jobs` and `job_chunks` tables |
| Parsed candidate profiles | Supabase PostgreSQL, sensitive fields encrypted at rest |

> The 3,039 occupation vectors are **already built and stored** in the shared Supabase project. Rebuilding takes roughly an hour on CPU and is unnecessary to run or evaluate the system. It is only needed when pointing the application at a fresh, empty database.

### 2.5 Preprocessing

| Dataset | Format | Preprocessing |
|---|---|---|
| Resume corpus | Single-page image-only PDF per resume; no extractable text layer | PyMuPDF renders each page to an image; a 100-character-per-page text-layer probe selects the text path only when one exists. Image files and rendered pages are sent one page at a time |
| ESCO taxonomy | Three relational CSVs | One text document per occupation, concatenating preferred label, alternative labels, description, and essential and optional skills; embedded once and written to the pgvector index |
| Job postings | Structured CSV plus live HTML postings | Structured fields read from schema.org `JobPosting` JSON-LD or page metadata where available (**zero LLM calls**); postings split into RAG chunks by section header and embedded |

**Chunking strategy — Career Recommendation.** Because ESCO is a structured, atomic occupational classification rather than free-form text, sliding-window chunking is inappropriate. The module uses **semantic atomic chunking**: one chunk equals one complete occupation profile. This keeps the embedding vector for each occupation a holistic representation of the role rather than fragmenting skill information across entries.

**Chunking strategy — Job Discovery.** Each crawled job description is split by a zero-LLM heuristic splitter that looks for common section headers ("Requirements", "Responsibilities", "About the role"). Postings without recognisable headers fall back to a single chunk. Each chunk is embedded independently.

**Post-processing — Resume Parsing.** Parse and repair the JSON envelope; normalise whitespace and empty values; deduplicate skills case-insensitively; merge per-page outputs; validate against the schema; run a completeness check. **Absent sections are a valid state** — missing scalars become `null`, missing lists become `[]`, never filled by inference.

### 2.6 Feature extraction

There is no hand-engineered feature vector anywhere. Representation learning is entirely internal to the pretrained models:

- **Resume Parsing** — the model encodes the page image internally; no separate encoder is built. The only engineering is prompt construction and schema binding.
- **Career Recommendation** — candidate profiles and occupation documents are embedded into the same 768-dimensional space by the same frozen encoder. Using the same model configuration for both offline indexing and online queries is a hard requirement for comparability.
- **Job Matching** — each job is represented both as structured relational columns (for exact SQL filtering) and as one job-level 768-dim embedding plus multiple chunk-level embeddings for RAG retrieval.

---

## 3. Model Architecture

### 3.1 Final architecture: a three-stage RAG pipeline with deterministic re-ranking

The system is a **retrieval-augmented generation (RAG) pipeline**, not a trained classifier. The core architectural decision — retrieval over classification — was taken for four reasons:

1. **Data requirements.** A 3,039-class supervised classifier would need thousands of labelled candidate profiles distributed across every occupation to avoid class imbalance. That data does not exist and cannot be ethically fabricated. RAG needs only the taxonomy itself.
2. **Knowledge updates.** ESCO is versioned and updated periodically. A fine-tuned model would need retraining on every taxonomy change; under RAG an update is a re-embed and index swap, with zero change to model weights.
3. **Explainability.** A fine-tuned model's prediction is an opaque function of its weights. RAG keeps every recommendation traceable to specific retrieved records — the exact occupation URI, its essential skills, and the deterministic re-ranking logic are all inspectable and shown to the user as evidence.
4. **Maintenance.** The "training" surface reduces to re-ranking rules and prompt design — plain Python and text artifacts that can be edited, tested, and deployed without a training run.

### 3.2 Per-module architecture

**Resume Parsing — decoder-only vision-language model.**
The task has two hard requirements: the page must be read as an image (the source PDFs have no text layer), and the output is a nested JSON object whose size varies with content. Encoder-only models (LayoutLM, BERT-NER over OCR) label input tokens rather than generate new ones, so they cannot produce a variable-length nested document. A decoder-only vision-language model matches both requirements: a vision encoder attends across the page's visual patches so layout and spatial structure are preserved, while the causal decoder writes the output JSON token by token — which is what allows the output to be constrained to a schema.

**Career Recommendation — dense retrieval + deterministic re-rank + grounded generation.**

```
profile → flatten to semantic query → BGE encode (768-d)
        → pgvector HNSW cosine search, Top-K = 20
        → deterministic Python re-rank:
              1. hard-requirement exclusion
              2. blended score = cosine + (skill_bonus_weight × normalised skill overlap)
        → Top-N = 7
        → Gemini 3.5 Flash-Lite grounded explanation
        → URI validation against the retrieved set (hard gate)
```

The re-ranking step is intentionally rule-based rather than a second neural pass, so occupation order is reproducible, inspectable, and requires no additional model call.

**Job Discovery and Matching — seven-node LangGraph StateGraph.**

```
profile_ingest → query_generator → search → extraction
              → hard_filter → matching → judge
```

All nodes share one `PipelineState` object. A failed node sets an error field that downstream nodes check before executing, so a failure short-circuits the run rather than raising.

### 3.3 Chosen configuration parameters

There are no hyperparameters in the training sense. The tunable surface is prompt text, output schemas, retrieval parameters, and scoring weights. Each value below is labelled **empirical** (selected by a measured sweep) or **heuristic** (set by reasoning, not yet varied and measured).

| Module | Parameter | Value | Basis |
|---|---|---|---|
| All | Temperature | 0 | By design — reproducibility required; sampling variety has no value in any task here |
| All | Embedding dimensions | 768 | Fixed by the encoder |
| All | Random seed | 42 | Fixed across split assignment and sampling |
| Resume Parsing | Provider and route | Gemini 3.5 Flash, vision-only, 150 DPI | **Empirical** — beat the Gemma 4 baseline on every section F1 |
| Resume Parsing | Skill boundary rule | Preserve competency phrases; split explicit enumerations | **Empirical** — six prompt experiments, Skills F1 0.2268 → 0.8198 |
| Resume Parsing | Description rule | Copy visible text without summarising | **Empirical** — exact copy rate and description similarity measured |
| Resume Parsing | Text-layer probe | 100 characters per page | Heuristic — the working corpus has no extractable text layer, so untested on this data |
| Resume Parsing | Fallback retries | 1 | Heuristic — cost and latency reasoning |
| Resume Parsing | Pages per call | 1 | Heuristic — prompt size and per-page validation |
| Career Rec. | Chunk contents | Preferred/alt labels, description, essential + optional skills | **Empirical in part** — optional skills present for 2,857 of 3,039 occupations |
| Career Rec. | Vector distance | Cosine, explicit HNSW operator class | **Empirical** — measured against the default-distance index |
| Career Rec. | Skill-bonus weight | **0.02** | **Empirical** — eight values swept against MRR and Hit Rate |
| Career Rec. | Retrieval Top-K | **20** | **Empirical in part** — Hit@20 of 0.9186 confirms the window is wide enough |
| Career Rec. | Final Top-N | **7** | **Empirical** — compared at 5 and 7; Hit@7 0.8488 against Hit@5 0.8372 |
| Career Rec. | Essential/optional skill weights | 1.0 and 0.5 | Heuristic — ratio not swept |
| Job Matching | BM25 / embedding weights | **0.5 / 0.5** | **Empirical** — six configurations compared |
| Job Matching | Shortlist after hybrid ranking | 15 | Heuristic — not varied in the sweep |
| Job Matching | Hybrid / judge weights | 0.8 / 0.2 | Heuristic — not varied in the sweep |
| Job Matching | RAG chunks per job at judge time | 2 | Heuristic — judge prompt size |
| Job Discovery | Source routing | Azudhan API primary; SearXNG + Crawl4AI fallback | **Empirical** — API path validated across domains and locations |
| Job Discovery | Search and crawl parameters | max_results 5, crawl limit 3, concurrency 3, timeout 8,000 ms | **Empirical** — five parameter sets compared |

**Scoring formulas.**

```
hybrid_score = (0.5 × BM25 + 0.5 × embedding_cosine)     # top 15 kept
final_score  = 0.8 × hybrid_score + 0.2 × judge_probability
```

---

## 4. Training Summary

**There is no training.** This is the defining architectural property of the system, established at Milestone 4 and unchanged since. No weights are initialised, updated, or saved anywhere in the pipeline, because the project has no labelled training data of the kind these tasks would require.

The conventional Milestone 4 headings therefore map to configuration-tuning equivalents rather than being skipped:

| Conventional activity | Equivalent in this system |
|---|---|
| Trainable weights, optimiser, learning rate | None. Configurable prompts, schemas, retrieval parameters, and scoring weights, chosen by exhaustive sweeps over small discrete grids |
| Batch size | A cost measure only — the judge scores five shortlisted jobs per call; the parser sends one page image per call |
| Number of epochs | No repeated passes over data. The occupation index is built in a **single pass** |
| Loss function | Deterministic rule-based validators combined into a weighted composite score, maximised by each sweep |
| Early stopping | A three-condition stopping criterion for prompt refinement; a fixed exhaustive grid for parameters |
| Checkpoint selection | Configuration-bundle selection — the winning bundle is the artefact the system runs on |
| Regularisation | Schema constraints, evidence grounding, URI validation, permissive filtering |
| Training duration, loss curves | Index build time and evaluation runtime; the **sweep response curve** is the equivalent diagnostic |
| Gradient clipping, LR schedules | Not applicable — no gradients are computed |

**What was optimised instead: cost and latency.**

- Exactly **two model calls per Job Discovery run** regardless of how many jobs are discovered. A naive per-item design would issue one extraction call per discovered job and one judge call per shortlisted job — an estimated 45+ calls. Making extraction deterministic and batching the judge reduces this to two.
- **Zero-LLM extraction** — structured fields read from JSON-LD or page metadata rather than a model call. Faster, more reliable, free per job.
- **Persistent occupation index** — embeddings generated once offline, so no taxonomy embedding call is made at request time regardless of index size.
- **Global deduplicated job store** — a posting is crawled, parsed, and embedded once, then reused by every subsequent search from any candidate.
- **Local embedding model** — BGE runs on CPU, so embeddings cost nothing per call and are unaffected by API rate limits.

**Prompt-refinement stopping criterion** (the early-stopping analogue). Refinement stops when all three hold: field extraction is stable across repeated runs on the development split; no schema violations occur across that split; and no new error classes are introduced relative to the previous prompt version.

**The binding constraint was never money — it was free-tier quota.** That is what forced the local encoder, the offline index build, the batched judge, and the deterministic extraction stage.

---

## 5. Evaluation Summary

Full evaluation was carried out at Milestone 5 against the corrected 86-resume gold set, the ESCO taxonomy, and a Job Matching golden set of 86 candidates with a 10-job pool each. No scoring surface changed in Milestone 6, so those figures stand.

### 5.1 Headline results

| Component | Result | Status |
|---|---|---|
| Resume Parsing | All six sections ≥ 0.75 F1 — Contact 0.98, Experience 0.98, Education 0.92, Projects 0.88, Skills 0.82, Certifications 0.75 | **Passing** |
| Career Recommendation | MRR 0.6121, Hit@1 0.4884, Hit@5 0.8372, Hit@7 0.8488, Hit@20 0.9186, 0 failures in 86 | **Passing** |
| Career Recommendation (held-out) | MRR 0.6359, Hit@5 0.8269 on 52 unseen resumes | **Generalises** |
| Job Matching ranking | Precision@5 0.8486, NDCG@10 0.9795, Spearman 0.8767 at 226 ms | **Passing** — efficiency result |
| Job Discovery | Coverage 1.0 in every configuration; crawl success 0.50 | Coverage passing |
| Query generation prompt | Schema 1.0000, diversity 0.8010, 100% pass rate | **Passing** |
| Integration | All modules over one application and one database | **Complete** |

### 5.2 Key insights

**The re-ranker's headline gain is not real.** The Hit@5 improvement from 0.8256 to 0.8372 is **one profile** — 71 against 72 of 86. A paired exact test over the discordant pairs gives **p = 1.00**. The re-ranking step is therefore *not shown to improve* Hit@5. What the evidence supports is the weaker claim that it does not degrade the ordering — which the rule it replaced did. The earlier claim of a lift was withdrawn.

**This caveat governs every comparison in the project.** At n = 86 the 95% Wilson interval on a rate near 0.83 is roughly ±0.08, so differences below about 0.08 are not separable. Sweeps are therefore read **for the shape of their response curve**, not for the winning value. Single-run differences smaller than the interval width are described as not separable rather than as improvements.

**Exact skill matching is a tiebreaker, not a ranking signal.** The skill-bonus sweep's substantive finding is the shape of the curve: weight 0.02 improves on the pass-through floor on all three measures, but above 0.05 every measure declines monotonically, with MRR falling 0.5965 → 0.4843 across the range. The reason is measurable — resume skill text and taxonomy labels draw on different vocabularies, so exact string overlap fires rarely and often on a generic term. A skill-dominant setting lets one incidental match outrank an occupation with strong semantic similarity.

**The parser change was the largest measured effect anywhere in the system**, separable in every section, with the biggest gains in the three weakest baseline sections: Projects +0.43, Skills +0.29, Certifications +0.24.

**The judge failure is structural, not a prompt problem.** Six instruction styles at a 0% pass rate is consistent with a token-budget limit, not prompt quality — which is why further rewording was abandoned. The combined payload (full resume text + full job description + instructions + any few-shot context) exceeds the usable context budget.

**Job Matching ranking quality is flat.** Quality metrics vary by at most 0.017 across the whole weight space while latency varies eighteen-fold. The selection is decided entirely by latency — 226 ms against more than 4,000 ms for every alternative. Neither the lexical nor the semantic signal can be shown necessary on this pool; the hybrid is retained on reasoning grounds, and a ten-job pool is very likely too small to test it.

### 5.3 Failure decomposition (Career Recommendation)

Because Hit@20 is measured on the same profiles as Hit@7, the 13 misses decompose exactly rather than by estimate:

| Cause | Count | Share |
|---|---|---|
| Truncation: present in top 20, lost at top 7 | 6 | 46% |
| Never retrieved: absent from top 20 | 7 | 54% |
| — of which taxonomy coverage gap (Arts, Management, Network Security Engineer) | ≈6 | 46% |
| — of which other retrieval failure | ≈1 | 8% |

Moving the final list from five to seven recovered **one profile for two extra slots**, not seven — the truncation remedy is worth far less than the decomposition alone suggested.

### 5.4 Acknowledged limitations

- 28 of 86 gold records retain AI-drafted rather than source-verified annotations, capping accuracy on every full-set metric.
- The Career Recommendation ground truth is a keyword-generated, hand-reviewed **proxy**, not direct occupation labels.
- **No human evaluation** of recommendation usefulness, explanation quality, or job-match relevance was conducted. This is the largest remaining methodological gap for a system whose output is advisory.
- Gender bias is **unmeasured** — names reach the embedding stage, so a bias channel exists and is untested.
- The local encoder truncates at 512 tokens against occupation documents reaching ~1,300, so the tails of the longest documents are never embedded.
- The evaluation corpus is entirely single-page, English, and image-only. Claims about readiness are restricted to that envelope.

---

## 6. Inference Pipeline

### 6.1 Data flow: input → model → output

**Stage 1 — Resume Parsing**

```
Upload (PDF/DOCX/image)
  → format detection
  → text-layer probe (≥100 chars/page?) → text path : vision path
  → render page to image (150 DPI)
  → Gemini 3.5 Flash, one page per call, schema-constrained prompt
  → JSON schema validation  ── fail ──→ Gemini 2.5 Flash-Lite retry (once)
                                          ── fail ──→ partial profile + review flags
  → multi-page merge, normalisation, case-insensitive skill dedup
  → field-level encryption of sensitive fields
  → persist → Candidate Profile JSON
```

**Stage 2 — Career Recommendation**

```
Candidate Profile
  → flatten relevant fields into one semantic query string
  → BGE encode → 768-d vector
  → pgvector HNSW cosine search → Top-K 20 occupations
  → deterministic re-rank (hard exclusion, then blended cosine + 0.02 × skill overlap)
  → Top-N 7
  → Gemini 3.5 Flash-Lite: grounded explanation + skill gaps, Pydantic-bound output
  → URI validation against the retrieved set (non-matching entries dropped)
  → persist run record with provenance → ranked recommendations
```

**Stage 3 — Job Discovery and Matching**

```
Profile + recommended roles
  → profile_ingest    : embed candidate locally (no LLM call)
  → query_generator   : Gemini 2.5 Flash-Lite → 5–6 diverse queries
  → search            : Azudhan API primary; SearXNG fallback
  → extraction        : job-store hit? skip crawl : Crawl4AI + JSON-LD parse (zero LLM)
  → hard_filter       : permissive regex on experience / location
  → matching          : 0.5×BM25 + 0.5×embedding → top 15
  → judge             : batched call over top 5, top-2 RAG chunks per job
  → final_score = 0.8 × hybrid + 0.2 × judge_probability
  → ranked shortlist of 5
```

### 6.2 API call examples

**Resume upload**

```bash
curl -X POST http://localhost:8000/api/resume-parsing/resumes \
  -F "file=@data/sample_data/sample_resume.pdf"
```

Streams parsing progress over server-sent events and returns a profile identifier once parsing completes.

```json
{
  "profile_id": "8f3c1a92-...",
  "status": "complete",
  "profile": {
    "contact":        { "name": "...", "location": "..." },
    "skills":         ["Python", "SQL", "..."],
    "education":      [{ "degree": "...", "field": "...", "institution": "..." }],
    "experience":     [{ "job_title": "...", "company": "...", "description": "..." }],
    "projects":       [],
    "certifications": [{ "name": "...", "issuer": "...", "year": null }],
    "job_titles":     ["..."]
  }
}
```

Note the two reliability behaviours visible here: `projects` is empty rather than populated by inference, and the certification `year` is `null` rather than guessed. No email or telephone number appears — those are never extracted.

**Career recommendation**

```bash
curl -X POST http://localhost:8000/api/career/recommend \
  -H "Content-Type: application/json" \
  -d '{"profile_id": "8f3c1a92-..."}'
```

```json
[
  {
    "esco_uri":   "http://data.europa.eu/esco/occupation/...",
    "title":      "data analyst",
    "rank":       1,
    "match_score": 87,
    "confidence": "high",
    "explanation": "Direct match: the candidate currently works as a Junior Data Analyst and holds core technical skills in Python, SQL, and data visualisation.",
    "matched_evidence": ["Python", "SQL", "data visualisation", "statistics"],
    "skill_gaps": ["data mining"]
  }
]
```

Confidence bands track the deterministic evidence rather than being asserted by the model — five matched skills yield high, one matched skill yields low.

**Job search**

```bash
curl -X POST http://localhost:8000/api/jobs/search \
  -H "Content-Type: application/json" \
  -d '{"profile_id": "8f3c1a92-..."}'
```

Returns a ranked shortlist of five jobs, each with `final_score`, `hybrid_score`, matched and missing criteria, and a rationale. On a niche domain where neither the primary API nor the SearXNG fallback returns results, the endpoint returns an **empty shortlist with a no-matches status**, not an error.

**Feedback**

```bash
curl -X POST http://localhost:8000/api/feedback \
  -H "Content-Type: application/json" \
  -d '{"rating": 8, "reasons": ["accurate_recommendations"], "comment": "Useful shortlist."}'
```

**Health check**

```bash
curl http://localhost:8000/health          # → {"status":"ok"}
```

### 6.3 Inference invariants

- **Temperature 0 on every generative call.** Run-to-run variance is nil by construction; the deterministic stages are exactly reproducible.
- **Schema-constrained output on every generative call**, validated before downstream use.
- **The explanation model cannot introduce occupations outside the retrieved set** — every output URI is validated and non-matching entries are dropped before the response is returned.
- **Career Recommendation and Job Discovery run sequentially, not concurrently.** They were originally run under `asyncio.gather`, which caused Job Discovery to read a stale or missing recommendation. Do not re-parallelise without an explicit dependency barrier.

---

## 7. Deployment Details

### 7.1 Platform

**AWS EC2, m7i-flex.large (free-tier eligible).** Live at **http://13.235.73.185:8080/** for the duration of the viva.

 The instance runs the stack via Docker Compose.

### 7.2 How the models are hosted

| Model | Hosting |
|---|---|
| Gemini 3.5 Flash / 3.5 Flash-Lite / 2.5 Flash-Lite | **Not hosted by us** — called over Google's hosted API with `GOOGLE_API_KEY` |
| `BAAI/bge-base-en-v1.5` | **Runs in-process on CPU** inside the backend container. Pulled from Hugging Face on first start, cached in `./huggingface_models/` on the host |
| Occupation vectors | Stored in Supabase PostgreSQL (pgvector, HNSW cosine index) — pre-built, not rebuilt at deploy time |

No model checkpoints are downloaded, versioned, or served by this project. There is nothing to restore from.

### 7.3 Containerisation

The repository ships a Dockerfile for the FastAPI backend, a Dockerfile for the React frontend, and a `docker-compose.yml` that starts the full stack — PostgreSQL, SearXNG, Alembic migrations, backend, and frontend — together.

```bash
docker compose up --build      # → http://localhost:8080
```

Migrations run automatically inside the backend container on every start. SearXNG runs inside the compose network on container port 8080 and is not exposed on the host, so it does not clash with the frontend.

> The first build downloads Python and Node base images and installs every dependency from scratch — it is slow. The `uv` path in [RUNNING.md](../RUNNING.md) is substantially faster for local work and is the recommended route for evaluation.

### 7.4 How to interact with it

**Via the UI:** open the deployed URL (or `http://localhost:5173` for the dev server / `:8080` for the Docker stack) and upload a resume. The interface walks through parsing → recommendations → job shortlist → report.

**Via the API:** interactive documentation at `/docs` (FastAPI Swagger UI).

| Endpoint | Method | Purpose |
|---|---|---|
| `/health` | GET | Liveness check — returns `{"status":"ok"}` |
| `/docs` | GET | Swagger UI |
| `/api/resume-parsing/resumes` | POST | Upload and parse a resume (SSE progress) |
| `/api/career/recommend` | POST | Ranked ESCO recommendations with explanations |
| `/api/jobs/search` | POST | Seven-stage job discovery and matching |
| `/api/feedback` | POST | Submit rating, reasons, optional comment |
| `/api/feedback/mine` | GET | Current user's past submissions |
| `/api/feedback/summary` | GET | Aggregate counts only (unauthenticated) |
| `/api/feedback/reasons` | GET | The twelve-value reason enum, served from the backend so the UI cannot drift out of sync |

### 7.5 Ports

| Service | Port |
|---|---|
| Frontend (Docker / EC2) | 8080 |
| Frontend (Vite dev server) | 5173 |
| FastAPI backend | 8000 |
| SearXNG | 8888 (host) / 8080 (container-internal) |
| Supabase PostgreSQL | 6543 (transaction pooler) |

### 7.6 Hosting constraints

- **Free-tier Supabase storage is ~0.3–0.5 GB.** The job store deduplicates by hash of the normalised posting URL, so storage grows with distinct postings rather than with searches — a mitigation, not a resolved constraint.
- **Free-tier model rate limits** (~1,500 requests/day, 15/minute) suit demonstration, not production. The architecture minimises call volume specifically because of this.
- **No multi-user load testing has been performed.** Only single- and double-user latency has been measured.
- **`/api/feedback/summary` is unauthenticated.** Counts only, no comments or identifiers — but it needs an admin check before production.
- The central configuration module still carries some **retired model identifiers as default values**, so a deployment without environment overrides would start against models that no longer exist.

---

## 8. System Design Considerations

### 8.1 Modularity and the enforced architectural boundary

The system is divided into six independent module packages under `backend/src/`, each following the same `api.py` / `service.py` / `schemas.py` / `internal/` pattern. Modules communicate through **versioned JSON objects** and the shared database, never by reaching into each other's internals.

This is not a convention — it is **mechanically enforced**. An `import-linter` contract set is checked by `uv run lint-imports`, currently reporting **11 contracts kept, 0 broken**. The contract added for the Feedback module in Milestone 6 states that *nothing may import from it*, which is what makes the "feedback can fail without affecting recommendations" claim structural rather than aspirational.

| Interface | Producer | Consumer | Key fields |
|---|---|---|---|
| Candidate Profile | Resume Parsing | Career Recommendation, Job Discovery | `candidate_id`, skills, education, experience, projects, certifications, job_titles |
| Career Recommendation output | Career Recommendation | Job Discovery, Career Report | ESCO URI, title, rank, scores, confidence, explanation, matched evidence |
| Job Matching request | Resume Parsing + Career Recommendation | Job Discovery | Candidate Profile JSON + recommended occupation |
| Persistence | All modules | PostgreSQL | Profile version, model version, timestamps, status, outputs |

### 8.2 How the database and retriever interact (RAG specifics)

This is the part most specific to a RAG system, and the part where the most consequential defect of the project appeared.

**Storage layout.** The vector store *is* the application database — Supabase PostgreSQL with the pgvector extension, rather than a separate vector service. This was a deliberate migration from an earlier local ChromaDB design, and it removes the class of bug where relational state and vector state disagree.

- **Occupation index:** 3,039 rows, one per ESCO occupation, each with a `vector(768)` column, indexed with **HNSW using the explicit cosine operator class**. Specifying the operator class explicitly is not cosmetic — measured against the default-distance index it moved retrieval Hit@5 from 0.7791 to 0.8256.
- **Job store:** structured columns for fields needing exact SQL filtering (`job_key`, `source_url`, `title`, `company`, `location`, `employment_type`, `is_remote`, `skills_required`, `posted_date`, `expiry_date`) plus one job-level `vector(768)`.
- **Job chunks:** a separate `job_chunks` table holding multiple per-job chunk embeddings for RAG retrieval at judge time.

**Retrieval path.** The retriever issues a single cosine similarity search per profile, returning Top-K 20. Deterministic re-ranking then happens **in Python, not in SQL** — so ranking logic is testable and inspectable without a database round trip. At judge time, a ranked window function over `job_chunks` retrieves only the top-2 chunks per shortlisted job by cosine similarity to the candidate's own embedding, keeping the judge prompt small and focused rather than sending whole postings.

**Retrieval is queried once per profile regardless of index size**, so index growth is not a scaling problem for the retriever — but it is a latency problem for the round trip (see §8.4).

**The verification requirement.** During the migration, the vector-store client's insertion helper wrote malformed embeddings. Content, metadata, and row counts were all correct, so it passed every surface check — the only symptom was retrieval nonsense. It was detectable *only by measuring the vectors themselves*: a stored vector had an L2 norm of 0.5951 where this encoder always produces ~1.0, and comparing a stored vector against a fresh embedding of its own document text gave a cosine similarity of −0.0072, meaning a document was orthogonal to itself.

The architectural lesson is now built into the ingestion path: **a rebuilt index is checked for vector norm and self-similarity rather than trusted because the insert succeeded.** `ingestion.py --verify` performs that check. Any future re-index must run it.

### 8.3 Scalability

**What scales well.**

- The parsing pipeline is **stateless per request** — one call per page, so it scales horizontally.
- The **global deduplicated job store** means crawling and embedding cost is paid once per posting and reused by every subsequent search from any candidate. The system gets cheaper and faster the more it is used.
- **Exactly two model calls per Job Discovery run** regardless of job count, so cost does not grow with result-set size.
- The occupation index is queried once per profile regardless of its size, so taxonomy growth does not degrade throughput.

**What binds first, in order.**

1. **Hosted-provider rate limits** — all model calls are synchronous per-request dependencies, so a burst of concurrent users hits the per-minute limit well before the daily one. This is the concrete reason caching, retry-queuing, and concurrent-call limits exist, not general performance tuning.
2. **Crawler memory** — 100–200 MB per concurrent headless browser context.
3. **CPU** — last. The single-user latency figures should not be read as throughput estimates.

**Untested.** No load or concurrency measurement was performed. Only single- and double-user latency has been measured, so scalability claims above are design reasoning, not measured behaviour.

### 8.4 Notable design trade-offs

| Decision | Benefit | Trade-off |
|---|---|---|
| Retrieval over 3,039-class classification | Works without labelled training data; supports unseen profiles | Quality depends on embedding and taxonomy coverage |
| Centralised hosted vector store over local index | One source of truth; no relational/vector drift; multi-client | Career Recommendation evaluation time rose from 11.7 s to 132–158 s for the same 86 profiles — **network round-trip, not computation**. A per-query cost, not a scaling problem |
| Deterministic re-ranking before explanation | Reproducible, inspectable ordering; no extra model call | Rule-based rather than learned; measured gain is within noise |
| Zero-LLM extraction | 45+ calls per run reduced to 2; faster, free, more reliable | Depends on job boards providing JSON-LD; postings without it yield weaker field data |
| Batched judge across all 5 finalists | One call handles final judgment regardless of shortlist size | Cannot give each job individual attention beyond what fits one prompt — and this is exactly where the token-overflow failure originates |
| Sequential recommendation → discovery | Eliminates the stale-read data race | Forgoes the latency saving of running them concurrently |
| Feedback module fully isolated | Can fail or be disabled with zero blast radius | Cannot enrich other modules' behaviour without an explicit interface |
| Permissive hard filter | A wrongly excluded job cannot be recovered later in the pipeline | Vague postings pass through and consume ranking budget |

### 8.5 Security and privacy design

- **No personal-identifier extraction.** Email addresses and telephone numbers are never extracted or persisted — enforced at both prompt and schema level, and confirmed on the integration run. Locations retain locality only.
- **No raw file storage.** The original upload is never written to persistent storage. Rendered page images are transient and deleted immediately after extraction.
- **Field-level encryption** of retained sensitive fields (company, institution, location, links), decrypted only for the authenticated owner.
- **Role-based access control** — Candidate, Admin, and Service roles, with ownership checked at the application layer on every query and endpoint.
- **Audit logging** — every profile access is written to a separate audit log, stored apart from profile data so a compromise of one does not expose the other.
- **Prompt-injection handling** — resume text and job descriptions are treated as untrusted *data*, clearly delimited, and cannot alter the system instruction. Schema validation is a hard gate.
- **API keys** are scoped per environment and never logged or included in error responses.

---

## 9. Error Handling & Monitoring

### 9.1 Design principle: fail soft, never fabricate

The system's error philosophy is that a degraded, honestly-labelled answer beats both a crash and a confident fabrication. Across the annotated evaluation this produced **86 of 86 profiles returning a ranked list, with zero unrecoverable failures**.

| Condition | Behaviour |
|---|---|
| Parser output fails schema validation or completeness check | One fallback retry against a second model, then a **partial profile with review flags** rather than nothing |
| Corrupt / unreadable file | Rejected with a user-facing message; **no model call made** |
| Image-only PDF misrouted as text | Automatic re-route to the vision path when fewer than 100 extractable characters per page are detected |
| Candidate skills produce no overlap with any retrieved occupation | Similarity-only ranking, confidence reported **low**, with an explicit message stating why |
| Explanation model unavailable, or no candidates survive retrieval | Explicit degraded or no-candidates status, with the deterministic ranking intact |
| Explanation model names an occupation outside the retrieved set | Entry **dropped by URI validation** before the response is returned |
| Invalid or non-schema LLM output | Structured-output validation and one repair attempt; otherwise retrieval-only results |
| Embedding API timeout | Retry with bounded exponential backoff; **no partial recommendation created** |
| Vector store unavailable | Service-unavailable status; the request is preserved for later retry |
| Primary job API returns nothing or fails | Falls back to the SearXNG and crawl chain; an empty shortlist carries a **no-matches status** rather than raising |
| Crawl4AI fails to render a posting | That URL is skipped; the run continues. One bad page does not fail the whole run |
| Model API rate limit or quota exceeded | HTTP 503 returned; **no silent retry loop** |
| Database write fails | Error logged, ranked shortlist still returned — a write failure must not block the response |
| Any LangGraph node fails | Sets an error field that downstream nodes check before executing, so the failure short-circuits the run instead of raising |

### 9.2 Latency handling

- A **hard latency ceiling** is applied as a pass/fail condition in the evaluation harness, not just as a weighted term. This is how the judge stage was correctly classified as failing rather than merely slow.
- Redis-backed caching of search results (one-hour TTL) prevents repeated queries from re-issuing searches during development.
- The global job store means a cache/DB hit skips search and crawling entirely.

### 9.3 What is monitored

- **Append-only JSONL evidence ledger** recording outputs, schema evidence, errors, latency, and per-call token counts for every parser run. A monetary cost figure is derivable from this against published rates.
- **Run records with provenance** persisted per recommendation — including complete model and prompt fingerprints, so any past result can be traced to the exact configuration that produced it.
- **Health endpoint** at `/health`.
- **Audit log** of every profile access, separate from profile data.

### 9.4 Known monitoring gaps

Stated rather than glossed:

- **No production monitoring or alerting stack.** No metrics export, no dashboard, no alerting on error rate or latency regression. Failures are visible in logs and in the evidence ledger, not in a monitor.
- **No throughput, concurrency, or cost instrumentation.** Tokens are recorded per call, but no cost-per-resume, throughput, or concurrent-load figure exists. The call-budget design describes intent, not observed behaviour under load.
- **The batched judge stage is a known open defect**, exceeding its own 20-second ceiling at the median with one case reaching 178,664 ms. It is reported as failing, with a diagnosed but unbuilt fix.

---

## 10. Reproducibility Checklist

### 10.1 Determinism controls

| Control | Value |
|---|---|
| Random seed | **42**, fixed across split assignment and sampling |
| Temperature | **0** on every generative call, every module |
| Output format | Schema-constrained JSON on every generative call, validated before downstream use |
| Model identifiers | Held in environment configuration, so a retired model is swapped without a code change |
| Fingerprinting | Complete model and prompt fingerprints recorded per run |
| Database schema | Built from versioned Alembic revisions `0001` → `0005` plus a checked-in setup script |
| Gold corrections | Stored as **versioned overlays** that preserve the original annotations, so corrections remain auditable |
| Grading | Deterministic and rule-based, never model-graded, so the evaluation itself stays reproducible |
| Score reuse guard | Gold and normalisation hashes prevent stale scores being reused |

> Run-to-run variance is **nil by construction**. The uncertainty that matters is sampling uncertainty over the 86 records, which is what the Wilson intervals quantify — not repeated-trial variance.

### 10.2 Key paths

| Item | Path |
|---|---|
| Application entrypoint | `backend/main.py` |
| FastAPI factory, CORS, router registration | `backend/src/app.py` |
| All environment variables and derived settings | `backend/src/core/config.py` |
| Async engine, session factory, asyncpg args | `backend/src/core/db.py` |
| Gold evaluation set (86 records) | `backend/src/career_recommendation/evaluation/gold.jsonl` |
| Category → ESCO mappings (134) | `backend/src/career_recommendation/evaluation/category_to_esco.json` |
| Evaluation harness | `backend/src/career_recommendation/evaluation/evaluate_gold.py` |
| Recorded results | `backend/src/career_recommendation/evaluation/evaluation_results_gold.json` |
| Index ingestion + verification | `backend/src/career_recommendation/ingestion.py` |
| Feedback repository (all writes) | `backend/src/feedback/internal/repository.py` |
| Feedback migration | `backend/alembic/versions/0005_feedback.py` |
| Prompt sweeps, per-resume CSVs, charts | `backend/experiments/` |
| Test suite | `backend/tests/` |
| Sample data | `data/sample_data/` |
| Config template | `.env.example` |
| Setup guide | `README.md` |

### 10.3 Checkpoints

**There are no checkpoints.** No model weights are saved, versioned, or restored anywhere. The reproducible artefact is the **configuration bundle** — model identifiers, prompts and schemas, retrieval parameters, and scoring weights — recorded in §3.3 of this document and held in environment configuration plus source.

The one piece of persistent derived state is the **ESCO vector index** in Supabase. It is pre-built and shared, so evaluators do not rebuild it: a full rebuild takes roughly an hour on CPU and is unnecessary to run or evaluate the system. A rebuild is required only when pointing the application at a fresh, empty database — and must be followed by `ingestion.py --verify`.

### 10.4 Reproduction workflow

| Stage | Action |
|---|---|
| **Clone** | `git clone https://github.com/devgupta1907/Group-4-DS-and-AI-Lab-Project.git` |
| **Configure** | `cp .env.example .env` in `backend/`, fill in per §1.5 |
| **Dependencies** | `uv sync` in `backend/`; `npm install` in `frontend/` |
| **Services** | `docker start searxng-v1` |
| **Migrate** | `uv run alembic upgrade head` |
| **Run** | `uv run uvicorn main:app --reload` + `npm run dev` |
| **Verify** | `uv run pytest` · `uv run lint-imports` · `npx eslint .` |

Full detail in [README.md](../README.md).

### 10.5 Expected verification output

| Check | Command | Expected |
|---|---|---|
| Backend test suite | `uv run pytest` | **74 passed** |
| Architecture contracts | `uv run lint-imports` | **11 kept, 0 broken** |
| Frontend lint | `npx eslint .` | **exit 0**, no errors |
| Backend liveness | `curl localhost:8000/health` | `{"status":"ok"}` |
| SearXNG | open `localhost:8888` | SearXNG search page |

### 10.6 Reproducing the evaluation figures

- **Resume Parsing and Career Recommendation** — run the harness against the corrected 86-record gold set. It **reuses saved predictions and recomputes scores** rather than re-calling the model, so a re-run is deterministic given the same predictions file, and never incurs API cost.
- **Job Matching** — run against the 86-candidate × 10-job golden set with real BM25 and embedding scoring at temperature 0. Exactly reproducible.
- **Job Discovery** — requires live network access to the job API, SearXNG, and Crawl4AI, so figures **will vary run to run with the live web**. The reported numbers are point estimates from the recorded evaluation run, not a guarantee for any future run. This is an inherent property of measuring live search reliability, not a defect in the harness.

### 10.7 Expected runtime

| Stage | Measured |
|---|---|
| Resume parsing, per resume | 19.03 s median, 21.79 s mean, 80.26 s max |
| Career Recommendation, per profile | 1.5–1.8 s (132–158 s across all 86 profiles) |
| Job Matching ranking | 226 ms |
| Job Discovery, API path | Within 2 minutes for successful queries |
| Job Discovery, fallback crawl | ~2,703 ms |
| Batched judge | 21,572 ms median — **exceeds its own ceiling; open defect** |
| ESCO index build (fresh DB only) | Minutes to ~1 hour on CPU, single pass |

### 10.8 Reproducibility caveats

- **A clean-machine rebuild beyond the documented steps was not performed.** The three verification checks and the manual end-to-end record are the evidence; that is stated rather than implied to be more.
- The skill-bonus weight sweep was run over all 86 records including the 52 held out, so for that one parameter selection and confirmation are not strictly separated. The held-out comparison for the selected value was run separately and is clean.
- Live-search figures are point estimates on shallow per-domain samples.

---

## Document map

| Document | Audience | Contents |
|---|---|---|
| [README.md](../README.md) | Anyone arriving at the repository | Project summary, quick start, deployment links 
| **technical_doc.md** (this file) | Developers and evaluators | How it works, what's inside, how to reproduce |
| `docs/milestones_<<number>>/` | Course evaluators | Milestone reports 1–6 and review reports |
