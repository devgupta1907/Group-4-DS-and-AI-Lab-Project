# Team Contribution Tracker — Week-wise (Milestones 1–4)

**Project:** AI-Powered Career Guidance, Resume Optimization, and Job Matching System

Each week corresponds to one milestone review cycle. Contributions are assigned by module ownership: Job Discovery & Job Matching → Pranav N, Praveena N | Resume Parsing → Abhinav Ohri | Career Recommendation → Dev Gupta, Gaurav Kumar | Cross-cutting items → All.

---

## Week 1 — Milestone 1

| Team Member | Contribution |
|---|---|
| **Pranav N / Praveena N** | 1. Designed a dataset-first data-sourcing strategy for job discovery to avoid ToS-violating scraping and API/rate-limit issues<br>2. Specified job matching methodology using Gemini embeddings and cosine similarity for candidate-job relevance<br>3. Defined weighted rule-based re-ranking on top of embedding similarity for final job ranking<br>4. Established Random and Cosine Similarity baselines as the success criteria for matching<br>5. Documented scraping/API-quota dependency as an explicit system limitation |
| **Abhinav Ohri** | 1. Removed the ATS scoring module from project scope after review feedback, dropping the section entirely<br>2. Added a facts(R') ⊆ facts(P) verification-gate paragraph to prevent hallucination during resume tailoring<br>3. Defined a faithfulness metric for tailored resume content, marked as an optional/stretch goal<br>4. Added Presidio-based PII redaction to remove privacy-sensitive fields from parsed resumes<br>5. Established privacy architecture for resume data as a core requirement |
| **Dev Gupta / Gaurav Kumar** | 1. Specified ESCO taxonomy as the foundation for career/occupation classification<br>2. Defined an embedding-based retrieval approach for matching candidate profiles to ESCO occupations<br>3. Added LLM-generated explanations to accompany each career recommendation<br>4. Incorporated exact ESCO dataset source and URL into the dataset section<br>5. Defined ground truth criteria specific to career recommendation quality |
| **All** | 1. Removed all "agents"/"multi-agent" framing throughout the document per review feedback<br>2. Selected and justified text-embedding-004 and Gemini 2.5 Flash as the core models<br>3. Added computational/deployment requirements (cloud free tier, no GPU required)<br>4. Defined a metric-to-ground-truth mapping table for each module<br>5. Confirmed PostgreSQL with pgvector/ChromaDB for retrieval and Google SSO for authentication |

---

## Week 2 — Milestone 2

| Team Member | Contribution |
|---|---|
| **Pranav N / Praveena N** | 1. Documented LinkedIn dataset's U.S.-oriented coverage and limited India representation (~0.60% of postings)<br>2. Clarified that candidate-job pair construction uses a query-document ranking structure rather than a direct join<br>3. Added RapidFuzz, rank_bm25, and BAAI/bge-base-en-v1.5 to the Job Matching preprocessing pipeline<br>4. Justified the 60/20/20 train/val/test split for Job Matching given the 200-candidate development sample<br>5. Added candidate-level splitting before candidate-job pair construction to prevent data leakage |
| **Abhinav Ohri** | 1. Connected resume dataset limitations to deployment, distinguishing evaluation data from production inputs (PDFs, DOCX, scans)<br>2. Defined the gold annotation methodology: 86 resumes (43 categories × 2), selected via duplicate isolation and fixed seed 42<br>3. Quality-checked AI-generated annotations on 15 resumes across three team members, labelling it a provisional gold set<br>4. Implemented reproducible preprocessing using PyMuPDF, MD5/pHash deduplication, and Tesseract OCR sampling<br>5. Documented preprocessing trade-offs for experience mapping, title normalization, and description truncation |
| **Dev Gupta / Gaurav Kumar** | 1. Applied lower specificity weighting to common ESCO skills and higher weighting to rare skills based on EDA findings<br>2. Documented shared-skills-across-occupations relationships identified during feature analysis<br>3. Clarified that ESCO files are integrated through occupationUri and skillUri joins<br>4. Reported ESCO data-quality metrics: 3,043 → 3,039 occupations and 13,960 → 13,939 skills after cleaning<br>5. Added ESCO role-level record examples to demonstrate dataset readiness |
| **All** | 1. Added a unified end-to-end architecture showing the full data flow from raw datasets to final recommendations<br>2. Clarified that modules integrate via shared schemas/identifiers rather than one physical dataset merge<br>3. Justified suitability and limitations for each dataset used across the project<br>4. Documented merge keys, schema mappings, and conflict-resolution rules for dataset integration<br>5. Distinguished completed vs. planned data-governance and privacy controls |

---

## Week 3 — Milestone 3

| Team Member | Contribution |
|---|---|
| **Pranav N / Praveena N** | 1. Reworked Job Matching into a pipeline: embedding → Top-K retrieval → hard filters → hybrid scoring → reranking → LLM judge<br>2. Documented heuristic rule weights (Skills 60%, Experience 25%, Location 15%) for job matching<br>3. Justified the final 60% Rule Engine / 40% LLM weighting for combining deterministic and semantic judgments<br>4. Defined Top-K stages across the matching pipeline (Top-25 pool, Top-15 hybrid ranking, Top-5 finalists, Top-2 evidence chunks)<br>5. Clarified the retrieval/evidence-augmentation role of RAG within Job Matching (vs. generative RAG in Career Recommendation) |
| **Abhinav Ohri** | 1. Contributed field-level protection requirements for sensitive resume data within the expanded security architecture<br>2. Defined temporary-image deletion and owner-only decryption controls for parsed resume artifacts<br>3. Clarified the Resume Parsing module interface: outputs a standardized Candidate Profile consumed downstream<br>4. Reviewed computational requirements (CPU/RAM/latency) relevant to parsing throughput<br>5. Supported explainability additions related to resume-derived candidate profile fields |
| **Dev Gupta / Gaurav Kumar** | 1. Justified RAG over fine-tuning for Career Recommendation: lower data needs, easier updates, no retraining on ESCO changes<br>2. Defined RAG retrieval parameters: Top-K values, chunking strategy, and metadata use<br>3. Specified reranking criteria and evidence-selection approach for career retrieval<br>4. Documented the vector-index update strategy for keeping ESCO-based retrieval current<br>5. Clarified generative RAG usage in Career Recommendation vs. evidence augmentation in Job Matching |
| **All** | 1. Separated the report into Model Architecture and System/Software Architecture views<br>2. Justified the modular pipeline against multi-agent, end-to-end neural, and fine-tuned alternatives<br>3. Standardized model naming (Gemma 4 31B, Gemini 2.5 Flash/Flash-Lite, gemini-embedding-2)<br>4. Expanded security architecture (authentication, authorization, API-key management, audit logging)<br>5. Added stateless horizontal scaling, async retries, and persistent vector-index growth planning |

---

## Week 4 — Milestone 4

| Team Member | Contribution |
|---|---|
| **Pranav N / Praveena N** | 1. Tested 7 query-generation prompt variants and 6 judge prompt variants, documenting selection criteria<br>2. Added tuning/ablation comparison tables for Job Matching, Search/Crawl, Query Generation, and Judge prompts<br>3. Reported ranking latency, discovery latency, crawl success rate, and query-generation/judge latency statistics<br>4. Added Job Matching results and discovery JSON as concrete implementation evidence<br>5. Added planned Job Discovery/Job Matching evaluation metrics to the Milestone 5 metrics table |
| **Abhinav Ohri** | 1. Replaced subjective "no visible improvement" language with a measurable stopping principle (schema stability, stable field extraction)<br>2. Reported the number of resumes processed as an implementation-maturity statistic<br>3. Added sample resume JSON output as concrete implementation evidence<br>4. Confirmed no new development-set errors emerged across resume prompt iterations<br>5. Added planned Resume Parsing evaluation metrics to the Milestone 5 metrics table |
| **Dev Gupta / Gaurav Kumar** | 1. Added ESCO retrieval/output examples as concrete implementation evidence<br>2. Reported ESCO indexing statistics as an implementation-maturity metric<br>3. Added planned Career Recommendation evaluation metrics to the Milestone 5 metrics table<br>4. Verified career recommendation outputs remained stable across configuration comparisons<br>5. Confirmed ESCO-grounded retrieval continued to function correctly in the final architecture |
| **All** | 1. Added a Traditional ML → LLM-equivalent activity mapping (training → prompt engineering, tuning → configuration optimization)<br>2. Labelled heuristic configuration parameters vs. values supported by Milestone 4 sweeps<br>3. Defined acceptance criteria for the frozen configuration: schema validity, latency, reliability, operational constraints<br>4. Replaced the Milestone 3 architecture with the final implementation architecture (Gemma 4 31B judge, PostgreSQL/pgvector)<br>5. Corrected data-flow representations across PostgreSQL, the ESCO vector store, and pgvector |

---

## Weekly Summary

| Week | Milestone | Job Discovery/Matching | Resume Parsing | Career Recommendation | Common |
|---|---|---|---|---|---|
| 1 | Milestone 1 | ✓ | ✓ | ✓ | ✓ |
| 2 | Milestone 2 | ✓ | ✓ | ✓ | ✓ |
| 3 | Milestone 3 | ✓ | ✓ | ✓ | ✓ |
| 4 | Milestone 4 | ✓ | ✓ | ✓ | ✓ |
