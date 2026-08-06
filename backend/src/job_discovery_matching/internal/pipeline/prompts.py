"""LLM prompt templates.

Only two prompts exist in this file — those are the only two LLM calls
made anywhere in the pipeline, each called exactly once per run:

  1. QUERY_GENERATOR — candidate_json -> N search queries
  2. JUDGE_BATCH     — candidate_json + top-N job texts -> scores, ONE call

Ported near-verbatim from career-agent's app/pipeline/prompts.py.
"""

QUERY_GENERATOR_SYSTEM = (
    "You are a job search expert who understands that good jobs "
    "are often listed under different titles than what candidates expect."
)

QUERY_GENERATOR_USER = """\
Given this candidate profile, generate exactly {num_queries} diverse search queries
to find relevant jobs across LinkedIn, Naukri, Wellfound, and company career pages.
Include:
- Role title variants (e.g. 'Data Analyst', 'Business Analyst', 'Analytics Engineer')
- Skill-based queries (e.g. 'SQL Python jobs')
- Domain-specific queries, if a domain is present
- Seniority variants for the candidate's level
Return ONLY a JSON array of {num_queries} strings. No markdown. No explanation.
Candidate profile:
{candidate_json}
"""

JUDGE_BATCH_SYSTEM = (
    "You are a senior recruiter with 15 years of experience. You are given a "
    "candidate profile and several raw job description excerpts (already "
    "crawled from job board pages, unstructured). For EACH job, extract a "
    "clean summary and score candidate fit."
)

JUDGE_BATCH_USER = """\
Candidate profile:
{candidate_json}

Below are {num_jobs} job postings, each as raw text crawled from a job board page
(may include some site navigation noise — ignore that and focus on the job content).

{jobs_block}

For EACH job in order (JOB 0, JOB 1, ... JOB {last_index}), evaluate candidate fit using
this rubric (100 points total):
  Skills match:        40 points  (required skills candidate has vs total required)
  Experience fit:      20 points  (years and level match, not just years)
  Domain relevance:    20 points  (industry/domain overlap)
  Seniority alignment: 10 points  (overqualified and underqualified both lose points)
  Location/remote fit: 10 points  (exact match=10, remote=8, mismatch=0)

Return ONLY a valid JSON array of exactly {num_jobs} objects, one per job, in the
same order as the jobs were given, with this schema — no markdown, no explanation:
[
  {{
    "title": "<cleaned job title>",
    "company": "<company name, or empty string if not found>",
    "location": "<city/region, or empty string>",
    "is_remote": <true|false>,
    "required_skills": [<up to 8 short strings>],
    "interview_probability": <integer 0-100>,
    "strengths": [<max 4 short strings, each under 30 chars>],
    "gaps": [<max 3 short strings, each under 30 chars>],
    "recommendation": <"Apply Immediately" | "Apply" | "Skip">,
    "one_line_reason": "<one sentence, max 120 chars>"
  }},
  ...
]
"""
