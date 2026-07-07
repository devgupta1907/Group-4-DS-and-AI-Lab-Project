# Review Change Log & Team Sign-off

This document summarizes the revisions incorporated into the resubmitted **Milestone_1_Reviewed.docx** following the project review meeting.

---

## 1. Change Log

Each row records a revision discussed during the review meeting, the corresponding change made, and the section where it was incorporated.

| # | Revision discussed in review | Change made (confirmed incorporated) | Section / Page |
|---|---|---|---|
| 1 | Remove "agents" / "multi-agent" | Confirmed removed throughout the document | Whole document |
| 2 | Job discovery: API/rate-limit/legal | Added a data-sourcing strategy paragraph (dataset-first approach, no ToS-violating scraping) | Section 7 – Job Discovery |
| 3 | Define ATS score + computation | ATS module dropped from project scope; section removed entirely | Removed |
| 4 | Tailoring hallucination prevention | Added a `facts(R') ⊆ facts(P)` verification-gate paragraph with a faithfulness metric; marked as an optional/stretch goal | Section 7 – Tailoring |
| 5 | Career recommendation methodology | Specified ESCO taxonomy, embedding retrieval, and LLM-generated explanations | Section 7 – Career Recommendation |
| 6 | Job matching methodology | Specified Gemini embeddings, cosine similarity, and weighted rule-based re-ranking | Section 7 – Job Matching |
| 7 | Commit to a specific model | Selected **text-embedding-004** and **Gemini 2.5 Flash** with justification | Section 7 – Architecture |
| 8 | Computational requirements | Added compute and deployment details (cloud free tier, no GPU required) | Section 7 – Architecture |
| 9 | Datasets too generic | Added exact datasets and URLs (Candidate Job Role, CareerBuilder, ESCO) | Section 8 |
| 10 | Ground truth undefined | Defined ground truth for each module, including CareerBuilder application labels | Sections 7 & 9 |
| 11 | Metrics not mapped to implementation | Added a metric-to-ground-truth mapping table for each module | Section 9 |
| 12 | No baselines / qualitative success criteria | Added Random and Cosine Similarity baselines; defined success as outperforming these baselines | Section 7 – Evaluation |
| 13 | Human evaluation methodology undefined | Added Likert-scale rubric and inter-rater agreement protocol | Section 9 |
| 14 | No database / retrieval / vector store | Confirmed PostgreSQL with pgvector/ChromaDB integration | Section 7 |
| 15 | No security / authentication | Confirmed Google SSO and secure cookie authentication | Section 7 |
| 16 | No privacy architecture | Confirmed Presidio-based PII redaction | Section 7 |
| 17 | Prompting / caching / latency | Added a consolidated subsection covering prompting, caching, and latency optimization | Section 7 |
| 18 | Limitations (scraping/API dependency) | Added explicit limitations regarding scraping and API quota dependencies | Section 10 |
| 19 | One end-to-end example | Expanded into a complete walkthrough with concrete example outputs | Section 7 – Overview |

---

## 2. Team Sign-off

Each team member confirms that they have reviewed and approved the final submission.

| Team Member | Reviewed & Approved | Initials | Date |
|---|---|---|---|
| Gaurav Kumar | Y | GK | 2026-07-07 |
| Dev Gupta | Y | DG | 2026-07-07 |
| Pranav N | Y | PrN | 2026-07-07 |
| Praveena N | Y | PvN | 2026-07-07 |
| Abhinav Ohri | Y | AO | 2026-07-07 |
