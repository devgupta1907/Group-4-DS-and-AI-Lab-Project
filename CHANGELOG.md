# Review Change Log & Team Sign-off

This document summarizes the key revisions incorporated into the project across all milestone reviews.

---

## Milestone 1 — Change Log

| # | Revision discussed in review | Change made | Section / Page |
|---|---|---|---|
| 1 | Remove "agents" / "multi-agent" | Confirmed removed throughout the document | Whole document |
| 2 | Job discovery: API/rate-limit/legal | Added data-sourcing strategy (dataset-first, no ToS-violating scraping) | Section 7 – Job Discovery |
| 3 | Define ATS score + computation | ATS module dropped from scope; section removed | Removed |
| 4 | Career recommendation methodology | Specified ESCO taxonomy, embedding retrieval, LLM explanations | Section 7 – Career Recommendation |
| 5 | Job matching methodology | Specified Gemini embeddings, cosine similarity, weighted re-ranking | Section 7 – Job Matching |
| 6 | Commit to a specific model | Selected text-embedding-004 and Gemini 2.5 Flash, with justification | Section 7 – Architecture |
| 7 | Datasets too generic | Added exact datasets and URLs (Candidate Job Role, CareerBuilder, ESCO) | Section 8 |
| 8 | Ground truth undefined | Defined ground truth per module, incl. CareerBuilder labels | Sections 7 & 9 |
| 9 | No baselines / success criteria | Added Random & Cosine Similarity baselines as success benchmarks | Section 7 – Evaluation |
| 10 | No security / authentication | Confirmed Google SSO and secure cookie authentication | Section 7 |

---

## Milestone 2 — Change Log

| # | Review feedback | Change made | Section / Evidence |
|---|---|---|---|
| 1 | End-to-end architecture unclear | Added unified architecture: raw data → preprocessing → profile → recommendation → matching | End-to-End System Architecture |
| 2 | Unified dataset was unclear | Clarified modules integrate via shared schemas/IDs, not one physical merge | Dataset Integration |
| 3 | Datasets described but not justified | Added suitability/limitations for Resume, ESCO, Candidate Job Role, LinkedIn | Dataset Suitability |
| 4 | LinkedIn dataset coverage unclear | Documented only ~0.60% India-related postings; U.S.-oriented, date-limited | Dataset Suitability |
| 5 | Gold annotation methodology unclear | Clarified 86-record gold set (43 categories × 2), seed 42 | Gold Annotation Methodology |
| 6 | EDA was descriptive, not decision-oriented | Linked EDA findings to concrete preprocessing/model decisions | EDA Findings and Decisions |
| 7 | Dataset integration lacked detail | Documented merge keys, schema mappings, conflict resolution | Dataset Integration |
| 8 | Preprocessing not reproducible | Added PyMuPDF, MD5/pHash dedup, OCR sampling, embedding pipeline details | Data Preprocessing |
| 9 | Train/val/test split needed justification | Clarified zero-shot split rationale and 60/20/20 for Job Matching | Dataset Splitting |
| 10 | Data governance unclear | Clarified completed vs. planned privacy/security controls | Data Governance / Privacy |

---

## Milestone 3 — Change Log

| # | Review feedback | Change incorporated | Section / Evidence |
|---|---|---|---|
| 1 | Model vs. system architecture mixed | Separated into Model Architecture and System/Software Architecture | Architecture Overview |
| 2 | Job Matching architecture needed improvement | Reworked as a clear multi-stage retrieval-to-shortlist pipeline | Job Matching Architecture |
| 3 | RAG selection needed justification | Added rationale: lower data needs, easier updates, no retraining | RAG Architecture |
| 4 | Rule weights lacked rationale | Documented heuristic weights: Skills 60%, Experience 25%, Location 15% | Rule-Based Scoring |
| 5 | Quantitative targets missing | Added module-level targets for Recall@K, Precision@K, latency | Evaluation & Design Targets |
| 6 | Model names inconsistent | Standardized naming: Gemma 4 31B, Gemini 2.5 Flash/Flash-Lite, gemini-embedding-2 | Model Architecture |
| 7 | Security architecture incomplete | Expanded to cover auth, API-key mgmt, audit logging, field-level protection | Security Architecture |
| 8 | Scalability insufficient | Added stateless scaling, async retries, caching, vector index growth plan | Scalability |
| 9 | Failure/retry behavior unclear | Added explicit LangGraph failure boundaries and retry/queue logic | Reliability Architecture |
| 10 | Production vs. offline embedding model unclear | Documented BAAI/bge-base-en-v1.5 (offline) vs. Gemini Embedding API (production) | Embedding Architecture |

---

## Milestone 4 — Change Log

| # | Reviewer observation | Revision incorporated | Section / Evidence |
|---|---|---|---|
| 1 | Traditional training activities not applicable | Added ML→LLM-equivalent activity mapping (training → prompt engineering, etc.) | Milestone 4 Activity Mapping |
| 2 | Little concrete evidence modules work | Added sample JSON, retrieval/output examples, prompt sweep results | Implementation Evidence |
| 3 | Prompt iterations not explained | Documented variant counts (7 for query gen, 6 for judge) and selection criteria | Prompt Engineering |
| 4 | Configuration values were heuristic | Labelled heuristic parameters vs. sweep-supported values | Configuration Selection |
| 5 | Little evidence of tuning/ablation | Added comparison tables for Matching, Search/Crawl, Query Gen, Judge prompts | Optimization Experiments |
| 6 | Frozen configuration not justified | Added acceptance criteria: schema validity, ranking quality, latency, reliability | Final Configuration Selection |
| 7 | Implementation maturity metrics missing | Added resumes processed, indexing stats, latency, crawl success metrics | Quantitative Implementation Statistics |
| 8 | Architecture differed from Milestone 3 | Replaced with final implementation architecture (Gemma 4 31B judge, pgvector) | Final Implementation Architecture |
| 9 | Data-flow representations incorrect | Clarified storage/paths across PostgreSQL, ESCO vector store, pgvector | Final Data Flow |
| 10 | Implementation maturity needed clearer evidence | Added measured results, distinguishing observed results from future targets | Results vs. Targets |

---

## Team Sign-off

| Team Member | Reviewed & Approved | Initials | Date |
|---|---|---|---|
| Gaurav Kumar | Y | GK | 2026-07-07 |
| Dev Gupta | Y | DG | 2026-07-07 |
| Pranav N | Y | PrN | 2026-07-07 |
| Praveena N | Y | PvN | 2026-07-07 |
| Abhinav Ohri | Y | AO | 2026-07-07 |
