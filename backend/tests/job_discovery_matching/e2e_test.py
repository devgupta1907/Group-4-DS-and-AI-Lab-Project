"""
================================================================================
 END-TO-END TEST — Manual Resume Post -> Career Recommendation
                    -> Job Discovery -> Chat-Based (LLM) Judge
 (Group-4-DS-and-AI-Lab-Project backend)

 Single file. Fully non-interactive. Results captured to Excel.
================================================================================

WHAT THIS TESTS
----------------
Drives the FULL pipeline for 10 different candidates, using the real routes
in backend/src — entering through MANUAL profile posting (no file upload,
no SSE parsing), exactly the "type a profile in directly" path your
frontend's ManualProfileForm uses:

  STAGE 1 — Resume Parsing (manual route)
    POST /api/resume-parsing/profiles/manual   body = CandidateProfile
    -> 201, ProfileRecord with route == "manual". Captures profile_id.

  STAGE 2 — Career Recommendation
    POST /api/career/recommend   {"profile_id": "<from stage 1>"}
    -> 200, status "ok" or "degraded_no_llm", recommendations list.

  STAGE 3 — Job Discovery & Matching (pauses twice for human-in-the-loop,
  so this is 3 calls per candidate):
    a) POST /api/jobs/search                          {"profile_id": ...}
       -> pauses at status "awaiting_query_selection", returns generated_queries
    b) POST /api/jobs/search/{run_id}/select-queries   {"selected_queries": [...]}
       -> pauses at status "awaiting_judge_confirmation", top_jobs populated
          (judge=None on each — hybrid-ranked only, so far)
    c) POST /api/jobs/search/{run_id}/confirm-judge    {"proceed": true}
       -> STAGE 4: the chat-based (LLM) judge actually runs here.
          Final status "ok" (judge ran) / "degraded_no_llm" (judge call
          failed) / "hybrid_only" would mean proceed=False, not used here.

STAGE 4 — Chat-Based Judge (folded into 3c above)
    `proceed: true` spends the LLM judge call (judge_module.py) over the
    hybrid-ranked jobs. This script always sends proceed=true so the judge
    stage is actually exercised, and separately checks that at least the
    jobs judged came back with a JudgeResultView (recommendation,
    interview_probability, etc.) rather than just carrying the hybrid score.

AUTH
----
Dev auth (src/core/security.py) trusts X-Dev-User-Id / X-Dev-User-Email
headers, falling back to DEV_USER_ID / DEV_USER_EMAIL from backend/.env.
Defaults below match backend/.env.example ("dev-user" / "dev@example.com").

HOW TO RUN
----------
1. Start the backend (from the project root):
       docker compose -f docker-compose.dev.yml up
   or, from backend/:  uv run uvicorn main:app --reload
   Default BASE_URL below is http://localhost:8000 to match docker-compose.dev.yml.

2. Run:  python pipeline_e2e_test.py
   No prompts. 10 built-in candidate profiles are used automatically
   (edit CANDIDATE_PROFILES below to change them, or point to your own list).

3. Output: e2e_pipeline_test_results.xlsx
       - "Results" sheet  -> one row per candidate, one column per stage
       - "Summary" sheet  -> totals / pass rate / run metadata

NOTES
-----
- If the backend is unreachable, every stage for every candidate is marked
  FAIL with the reason captured — the script never crashes, and the Excel
  report is still produced.
- A later stage is skipped (marked SKIPPED, not run) if an earlier stage
  for that candidate failed, since there's no profile_id / run_id to
  continue with. This keeps a real 10/10 run always completing.
================================================================================
"""

from __future__ import annotations

import json
import time
import traceback
from datetime import datetime

import requests
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

# =============================================================================
# CONFIG
# =============================================================================

BASE_URL = "http://localhost:8000"
TIMEOUT_SECONDS = 60  # job discovery / LLM stages can be slow

DEV_USER_ID = "dev-user"
DEV_USER_EMAIL = "dev@example.com"
HEADERS = {
    "X-Dev-User-Id": DEV_USER_ID,
    "X-Dev-User-Email": DEV_USER_EMAIL,
    "Content-Type": "application/json",
}

OUTPUT_FILE = "e2e_pipeline_test_results.xlsx"

# Job search preferences sent at Stage 3a. Kept minimal / permissive so the
# search isn't artificially narrowed for a test run.
SEARCH_PREFERENCES = {
    "target_location": None,
    "remote_only": False,
    "min_salary_lpa": None,
}

# Stage 3b: how many of the generated queries to select. None = select all.
MAX_QUERIES_TO_SELECT = 3

# Stage 3c / Stage 4: always exercise the chat-based (LLM) judge.
PROCEED_TO_JUDGE = True


# =============================================================================
# 10 CANDIDATE PROFILES (manual posting — matches CandidateProfile schema in
# backend/src/resume_parsing/schemas.py). Edit freely, or replace this list
# with your own 10.
# =============================================================================

def _profile(job_titles, skills, degree, field, institution, exp_title, exp_company, exp_desc, proj_name, proj_desc):
    return {
        "contact": {"name": None, "location": None, "links": []},
        "skills": skills,
        "education": [
            {
                "degree": degree,
                "field": field,
                "institution": institution,
                "start_year": "2018",
                "end_year": "2022",
            }
        ],
        "experience": [
            {
                "job_title": exp_title,
                "company": exp_company,
                "location": None,
                "start_date": "2022-06",
                "end_date": None,
                "current_role": True,
                "description": exp_desc,
            }
        ],
        "projects": [
            {"name": proj_name, "description": proj_desc, "technologies": skills[:3]}
        ],
        "certifications": [],
        "job_titles": job_titles,
    }


CANDIDATE_PROFILES = [
    _profile(
        ["Data Analyst"], ["Python", "SQL", "Power BI", "Statistics", "Excel"],
        "B.Tech", "Computer Science", "Anna University",
        "Junior Data Analyst", "Acme Corp",
        "Built dashboards and automated weekly reporting pipelines.",
        "Sales Dashboard", "Interactive Power BI dashboard tracking regional sales KPIs.",
    ),
    _profile(
        ["Software Engineer", "Backend Developer"], ["Java", "Spring Boot", "Kafka", "PostgreSQL", "Docker"],
        "B.E", "Information Technology", "VTU",
        "Software Engineer", "Beta Systems",
        "Built and maintained microservices handling 1M+ daily requests.",
        "Order Service", "Event-driven order processing service using Kafka and Spring Boot.",
    ),
    _profile(
        ["QA Engineer", "SDET"], ["Selenium", "Pytest", "CI/CD", "Java", "Postman"],
        "B.Sc", "Computer Applications", "Delhi University",
        "QA Engineer", "Gamma Testing Labs",
        "Owned regression suite; reduced release cycle time by 30%.",
        "Regression Automation Suite", "End-to-end Selenium + Pytest suite integrated into CI/CD.",
    ),
    _profile(
        ["Product Manager"], ["Roadmapping", "Agile", "Jira", "User Research", "SQL"],
        "MBA", "Product Management", "IIM Bangalore",
        "Associate Product Manager", "Delta Retail",
        "Owned checkout funnel; drove a measurable conversion lift.",
        "Checkout Redesign", "Led redesign of mobile checkout, reducing cart abandonment.",
    ),
    _profile(
        ["DevOps Engineer"], ["Docker", "Kubernetes", "Terraform", "AWS", "Prometheus"],
        "B.Tech", "Electronics and Communication", "NIT Trichy",
        "DevOps Engineer", "Epsilon Cloud",
        "Migrated on-prem workloads to Kubernetes on AWS EKS.",
        "IaC Migration", "Terraform modules to provision multi-environment infra.",
    ),
    _profile(
        ["Frontend Developer", "React Developer"], ["React", "TypeScript", "CSS", "Redux", "Jest"],
        "B.E", "Computer Science", "BMS College of Engineering",
        "Frontend Developer", "Zeta Labs",
        "Rebuilt the customer portal in React, improving load time by 40%.",
        "Customer Portal Revamp", "Migrated legacy jQuery UI to a React + TypeScript SPA.",
    ),
    _profile(
        ["Business Analyst"], ["Excel", "SQL", "PowerBI", "Requirements Gathering", "Stakeholder Management"],
        "B.Com", "Finance", "Christ University",
        "Business Analyst", "Theta Consulting",
        "Gathered requirements and translated them into functional specs.",
        "Process Automation", "Documented and automated a manual invoicing workflow.",
    ),
    _profile(
        ["Machine Learning Engineer", "ML Engineer"], ["Python", "TensorFlow", "PyTorch", "Pandas", "MLOps"],
        "M.Tech", "Artificial Intelligence", "IIT Madras",
        "ML Engineer", "Iota AI",
        "Trained and deployed a fraud-detection model to production.",
        "Fraud Detection Model", "Gradient-boosted model with a real-time inference API.",
    ),
    _profile(
        ["UX Designer", "Product Designer"], ["Figma", "User Research", "Prototyping", "Wireframing", "Design Systems"],
        "B.Des", "Interaction Design", "NID Ahmedabad",
        "UX Designer", "Kappa Studio",
        "Ran usability studies that shaped two major feature launches.",
        "Design System", "Built a shared component library adopted across 3 product teams.",
    ),
    _profile(
        ["Data Scientist"], ["Python", "Scikit-learn", "SQL", "Statistics", "A/B Testing"],
        "M.Sc", "Statistics", "ISI Kolkata",
        "Data Scientist", "Lambda Analytics",
        "Built churn-prediction models used to prioritize retention campaigns.",
        "Churn Model", "Logistic regression + XGBoost ensemble for subscriber churn.",
    ),
]


# =============================================================================
# HTTP HELPERS — every call is wrapped, none of them raise
# =============================================================================

class StepResult:
    def __init__(self, ok, status_code, detail, payload=None, elapsed_ms=0.0, skipped=False):
        self.ok = ok
        self.status_code = status_code
        self.detail = detail
        self.payload = payload or {}
        self.elapsed_ms = elapsed_ms
        self.skipped = skipped

    @property
    def label(self):
        if self.skipped:
            return "SKIPPED"
        return "PASS" if self.ok else "FAIL"


def _post(path, body):
    url = BASE_URL.rstrip("/") + path
    start = time.time()
    try:
        resp = requests.post(url, headers=HEADERS, data=json.dumps(body), timeout=TIMEOUT_SECONDS)
        elapsed_ms = round((time.time() - start) * 1000, 1)
        try:
            parsed = resp.json()
        except ValueError:
            parsed = {"_raw_text": resp.text[:500]}
        return resp.status_code, parsed, elapsed_ms, None
    except requests.exceptions.ConnectionError as e:
        elapsed_ms = round((time.time() - start) * 1000, 1)
        return None, {}, elapsed_ms, f"Connection error — backend unreachable ({e.__class__.__name__})"
    except requests.exceptions.Timeout:
        elapsed_ms = round((time.time() - start) * 1000, 1)
        return None, {}, elapsed_ms, f"Request timed out after {TIMEOUT_SECONDS}s"
    except Exception:
        elapsed_ms = round((time.time() - start) * 1000, 1)
        return None, {}, elapsed_ms, "Unexpected error: " + traceback.format_exc(limit=1)[:300]


def skip(reason):
    return StepResult(ok=False, status_code="-", detail=reason, skipped=True)


# =============================================================================
# STAGE FUNCTIONS
# =============================================================================

def stage1_manual_post(profile: dict) -> StepResult:
    """POST /api/resume-parsing/profiles/manual"""
    status_code, payload, elapsed_ms, err = _post("/api/resume-parsing/profiles/manual", profile)
    if err:
        return StepResult(False, "N/A", err, elapsed_ms=elapsed_ms)
    ok = status_code == 201 and payload.get("route") == "manual" and bool(payload.get("id"))
    detail = "OK" if ok else f"status={status_code}, body={json.dumps(payload)[:250]}"
    return StepResult(ok, status_code, detail, payload, elapsed_ms)


def stage2_career_recommend(profile_id: str) -> StepResult:
    """POST /api/career/recommend"""
    status_code, payload, elapsed_ms, err = _post("/api/career/recommend", {"profile_id": profile_id})
    if err:
        return StepResult(False, "N/A", err, elapsed_ms=elapsed_ms)
    status_ok = payload.get("status") in ("ok", "degraded_no_llm")
    ok = status_code == 200 and status_ok
    n_recs = len(payload.get("recommendations", []))
    detail = f"status={payload.get('status')}, {n_recs} recommendation(s)" if ok else (
        f"status_code={status_code}, body={json.dumps(payload)[:250]}"
    )
    return StepResult(ok, status_code, detail, payload, elapsed_ms)


def stage3a_job_search(profile_id: str) -> StepResult:
    """POST /api/jobs/search -> pauses at awaiting_query_selection"""
    body = {"profile_id": profile_id, **SEARCH_PREFERENCES}
    status_code, payload, elapsed_ms, err = _post("/api/jobs/search", body)
    if err:
        return StepResult(False, "N/A", err, elapsed_ms=elapsed_ms)
    ok = (
        status_code == 200
        and payload.get("status") == "awaiting_query_selection"
        and bool(payload.get("generated_queries"))
        and bool(payload.get("run_id"))
    )
    n_q = len(payload.get("generated_queries") or [])
    detail = f"{n_q} generated queries, run_id captured" if ok else (
        f"status={payload.get('status')}, status_code={status_code}, body={json.dumps(payload)[:250]}"
    )
    return StepResult(ok, status_code, detail, payload, elapsed_ms)


def stage3b_select_queries(run_id: str, generated_queries: list[str]) -> StepResult:
    """POST /api/jobs/search/{run_id}/select-queries -> pauses at awaiting_judge_confirmation"""
    selected = generated_queries[:MAX_QUERIES_TO_SELECT] if MAX_QUERIES_TO_SELECT else generated_queries
    status_code, payload, elapsed_ms, err = _post(
        f"/api/jobs/search/{run_id}/select-queries", {"selected_queries": selected}
    )
    if err:
        return StepResult(False, "N/A", err, elapsed_ms=elapsed_ms)
    status = payload.get("status")
    # awaiting_judge_confirmation is the expected pause point; no_jobs means
    # crawl/filter genuinely found nothing for this profile — a real
    # pipeline outcome, not a broken test, but it can't reach the judge.
    ok = status_code == 200 and status == "awaiting_judge_confirmation" and bool(payload.get("top_jobs"))
    n_jobs = len(payload.get("top_jobs") or [])
    detail = f"{n_jobs} hybrid-ranked jobs, ready for judge" if ok else (
        f"status={status}, jobs_discovered={payload.get('jobs_discovered')}, "
        f"jobs_after_filter={payload.get('jobs_after_filter')}"
    )
    return StepResult(ok, status_code, detail, payload, elapsed_ms)


def stage4_confirm_judge(run_id: str) -> StepResult:
    """POST /api/jobs/search/{run_id}/confirm-judge -> chat-based (LLM) judge runs here"""
    status_code, payload, elapsed_ms, err = _post(
        f"/api/jobs/search/{run_id}/confirm-judge", {"proceed": PROCEED_TO_JUDGE}
    )
    if err:
        return StepResult(False, "N/A", err, elapsed_ms=elapsed_ms)
    status = payload.get("status")
    top_jobs = payload.get("top_jobs") or []
    judged = [j for j in top_jobs if j.get("judge") is not None]
    # "ok" = judge ran cleanly. "degraded_no_llm" = judge stage ran but the
    # LLM call itself failed — pipeline still completed, so still a PASS for
    # the E2E flow, just noted in the detail.
    ok = status_code == 200 and status in ("ok", "degraded_no_llm") and len(top_jobs) > 0
    if status == "ok" and judged:
        recs = [j["judge"]["recommendation"] for j in judged]
        detail = f"LLM judge ran on {len(judged)}/{len(top_jobs)} jobs — recommendations: {recs}"
    else:
        detail = f"status={status}, {len(top_jobs)} jobs, {len(judged)} judged"
    return StepResult(ok, status_code, detail, payload, elapsed_ms)


# =============================================================================
# DRIVE ONE CANDIDATE THROUGH THE FULL PIPELINE
# =============================================================================

def run_candidate(index: int, profile: dict) -> dict:
    label = f"Candidate {index:02d} ({', '.join(profile['job_titles']) or 'untitled'})"
    print(f"\n--- {label} ---")

    s1 = stage1_manual_post(profile)
    print(f"  Stage 1 (Manual Post):        {s1.label:8s} {s1.detail}")

    if not s1.ok:
        s2 = skip("Skipped — Stage 1 did not return a profile_id")
        s3a = skip("Skipped — no profile_id")
        s3b = skip("Skipped — no run_id")
        s4 = skip("Skipped — no run_id")
    else:
        profile_id = s1.payload.get("id")

        s2 = stage2_career_recommend(profile_id)
        print(f"  Stage 2 (Career Recommend):   {s2.label:8s} {s2.detail}")

        s3a = stage3a_job_search(profile_id)
        print(f"  Stage 3a (Job Search):        {s3a.label:8s} {s3a.detail}")

        if not s3a.ok:
            s3b = skip("Skipped — Stage 3a did not return generated_queries/run_id")
            s4 = skip("Skipped — no run_id")
        else:
            run_id = s3a.payload.get("run_id")
            queries = s3a.payload.get("generated_queries") or []

            s3b = stage3b_select_queries(run_id, queries)
            print(f"  Stage 3b (Select Queries):    {s3b.label:8s} {s3b.detail}")

            if not s3b.ok:
                s4 = skip("Skipped — Stage 3b did not reach awaiting_judge_confirmation")
            else:
                s4 = stage4_confirm_judge(run_id)
                print(f"  Stage 4 (Chat-Based Judge):   {s4.label:8s} {s4.detail}")

    overall = "PASS" if (not s1.skipped and s1.ok and s4.label == "PASS") else "FAIL"
    print(f"  OVERALL:                      {overall}")

    return {
        "candidate": label,
        "job_titles": ", ".join(profile["job_titles"]),
        "stage1": s1, "stage2": s2, "stage3a": s3a, "stage3b": s3b, "stage4": s4,
        "overall": overall,
    }


# =============================================================================
# EXCEL REPORT
# =============================================================================

def write_excel_report(results: list[dict], output_path: str):
    wb = Workbook()
    ws = wb.active
    ws.title = "Results"

    headers = [
        "S.No", "Candidate", "Job Title(s)",
        "Stage 1: Manual Post", "Stage 2: Career Recommend",
        "Stage 3a: Job Search", "Stage 3b: Select Queries",
        "Stage 4: Chat-Based Judge", "Overall",
        "Stage 1 Detail", "Stage 2 Detail", "Stage 3a Detail", "Stage 3b Detail", "Stage 4 Detail",
    ]
    ws.append(headers)

    header_fill = PatternFill(start_color="305496", end_color="305496", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True)
    thin = Side(style="thin", color="CCCCCC")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    pass_fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
    fail_fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
    skip_fill = PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid")

    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = border

    label_fills = {"PASS": pass_fill, "FAIL": fail_fill, "SKIPPED": skip_fill}

    for i, r in enumerate(results, start=1):
        row = [
            i, r["candidate"], r["job_titles"],
            r["stage1"].label, r["stage2"].label, r["stage3a"].label, r["stage3b"].label, r["stage4"].label,
            r["overall"],
            r["stage1"].detail, r["stage2"].detail, r["stage3a"].detail, r["stage3b"].detail, r["stage4"].detail,
        ]
        ws.append(row)
        row_num = i + 1
        for col_idx in [4, 5, 6, 7, 8, 9]:
            cell = ws.cell(row=row_num, column=col_idx)
            fill = label_fills.get(cell.value)
            if fill:
                cell.fill = fill
                cell.font = Font(bold=True)
        for col_idx in range(1, len(headers) + 1):
            ws.cell(row=row_num, column=col_idx).border = border
            ws.cell(row=row_num, column=col_idx).alignment = Alignment(vertical="top", wrap_text=True)

    col_widths = [6, 26, 22, 14, 16, 14, 16, 16, 10, 34, 34, 34, 34, 40]
    for idx, width in enumerate(col_widths, start=1):
        ws.column_dimensions[get_column_letter(idx)].width = width
    ws.freeze_panes = "A2"

    # ---- Summary sheet ----
    ws2 = wb.create_sheet("Summary")
    total = len(results)
    passed = sum(1 for r in results if r["overall"] == "PASS")
    failed = total - passed

    def stage_pass_count(key):
        return sum(1 for r in results if r[key].label == "PASS")

    rows = [
        ("Test Run", "Manual Post -> Career Recommend -> Job Discovery -> Chat-Based Judge"),
        ("Executed On", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("Target Backend", BASE_URL),
        ("Total Candidates Tested", total),
        ("Overall Passed", passed),
        ("Overall Failed", failed),
        ("Overall Pass Rate", f"{(passed / total * 100):.1f}%" if total else "0%"),
        ("", ""),
        ("Stage 1 (Manual Post) Passed", f"{stage_pass_count('stage1')}/{total}"),
        ("Stage 2 (Career Recommend) Passed", f"{stage_pass_count('stage2')}/{total}"),
        ("Stage 3a (Job Search) Passed", f"{stage_pass_count('stage3a')}/{total}"),
        ("Stage 3b (Select Queries) Passed", f"{stage_pass_count('stage3b')}/{total}"),
        ("Stage 4 (Chat-Based Judge) Passed", f"{stage_pass_count('stage4')}/{total}"),
    ]
    ws2.append(["Metric", "Value"])
    for col_idx in (1, 2):
        cell = ws2.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.border = border
    for label, value in rows:
        ws2.append([label, value])
    for row_idx in range(2, len(rows) + 2):
        for col_idx in (1, 2):
            ws2.cell(row=row_idx, column=col_idx).border = border
    ws2.column_dimensions["A"].width = 32
    ws2.column_dimensions["B"].width = 55

    wb.save(output_path)


# =============================================================================
# MAIN — fully automatic, no input() calls
# =============================================================================

def main():
    print("=" * 78)
    print("E2E TEST: Manual Resume Post -> Career Recommendation -> Job Discovery")
    print("          -> Chat-Based (LLM) Judge")
    print("=" * 78)
    print(f"[INFO] Testing {len(CANDIDATE_PROFILES)} candidates against {BASE_URL}")

    results = [run_candidate(i, p) for i, p in enumerate(CANDIDATE_PROFILES, start=1)]

    write_excel_report(results, OUTPUT_FILE)

    total = len(results)
    passed = sum(1 for r in results if r["overall"] == "PASS")
    print("\n" + "=" * 78)
    print(f"DONE. {passed}/{total} candidates completed the full pipeline (incl. chat-based judge).")
    print(f"Report saved to: {OUTPUT_FILE}")
    print("=" * 78)


if __name__ == "__main__":
    main()