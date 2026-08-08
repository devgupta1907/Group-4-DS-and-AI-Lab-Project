# AI-Powered Intelligent Job Search and Career Autopilot</h1>

## Run the complete application

Copy `backend/.env.example` to `backend/.env`, set `PROFILE_ENCRYPTION_KEY`
and `GOOGLE_API_KEY`, then start the production-like local stack:

```bash
docker compose up --build
```

Open http://localhost:8080. PostgreSQL, SearXNG, migrations, the FastAPI
backend, and the frontend are started together.

The default image uses direct vision for scanned PDFs and does not install
Docling. To build the optional experimental Docling route:

```bash
ENABLE_DOCLING=true RESUME_SCANNED_PDF_STRATEGY=docling_text docker compose up --build
```

For hot-reload development:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

The development frontend is available at http://localhost:5173 and the API at
http://localhost:8000.


## 📑 Table of Contents
- [Problem Statement](#-problem-statement)
- [Project Objectives](#-project-objectives)
- [Proposed Approach](#-proposed-approach)
- [Expected Deliverables](#-expected-deliverables)
- [Tech Stack (Proposed)](#-tech-stack-proposed)

---

## Problem Statement

The modern job search process is fragmented, time-consuming, and largely manual. Candidates often lack clarity on which roles align with their background, and invest significant effort in tailoring resumes, writing cover letters, hunting for relevant listings, and researching recruiters across multiple platforms without any intelligent system guiding or automating any part of this workflow.

## 🎯 Project Objectives

1. Extract and structure candidate profiles from uploaded resumes
2. Predict suitable career paths and job roles based on candidate background
3. Discover and rank relevant job listings matched against the candidate profile
4. Automate resume tailoring, ATS score optimization, and cover letter generation for each matched role

## 🧠 Proposed Approach

A multi-agent pipeline where each agent owns a distinct stage of the job search workflow. A resume ingestion agent parses uploaded documents and extracts structured candidate attributes. These feed into an AI-based career system to make career predictions, recommending optimal job roles and growth paths aligned with the candidate's background and skills. A job discovery agent continuously searches job posts across the web, matches them against the candidate profile, and ranks opportunities by fit score. For each matched role, dedicated agents handle resume tailoring, ATS optimization scoring, and personalized cover letter generation using a large language model.


## 📦 Expected Deliverables

- A working multi-agent job search pipeline with a web interface.
- An ATS scoring and resume tailoring module integrated into the app.
- A cover letter generation agent producing role-specific, non-generic output grounded in candidate profile data.

## 💻 Tech Stack (Proposed)

*This stack reflects a modern, scalable approach suitable for AI engineering.*

- **Backend:** Python, FastAPI/Flask
- **Package Management:** `uv`
- **AI / LLM Framework:** LangChain, Gemini API
- **Frontend:** Next.js (React)
- **Deployment & Cloud:** AWS (EC2 / S3 / Amplify)


## Team Members
- Gaurav Kumar (22f1001105)
- Dev Gupta (22f2000888)
- Abhinav Ohri (24f1002064)
- Pranav N (22f2000117)
- Praveena N (22f3001454)
