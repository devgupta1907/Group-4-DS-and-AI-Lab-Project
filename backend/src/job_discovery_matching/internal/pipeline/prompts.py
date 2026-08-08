"""LLM prompt templates.

Only two prompts exist in this file — those are the only two LLM calls
made anywhere in the pipeline, each called exactly once per run:

  1. QUERY_GENERATOR — candidate_json -> N search queries
  2. JUDGE_BATCH     — candidate_json + top-N job texts -> scores, ONE call

Ported near-verbatim from career-agent's app/pipeline/prompts.py.
"""

QUERY_GENERATOR_SYSTEM = (
    "You are a job search expert who understands that good jobs "
    "are often listed under different titles than what candidates expect. "
    "You write queries that surface live vacancy listings, never "
    "career-advice or 'what is this profession' reference pages."
)

# A bare occupation title such as "agricultural engineer" returns Wikipedia,
# government occupation profiles and university course pages — none of which
# are vacancies, and all of which are then discarded downstream after being
# crawled. Requiring a hiring word in every query, and naming the boards
# explicitly, is what moves the result set from reference material to
# postings. Query generation is one LLM call per run, so this costs nothing
# extra; the saving is in crawls that no longer happen.
QUERY_GENERATOR_USER = """\
Given this candidate profile, generate exactly {num_queries} diverse search queries
to find relevant jobs across LinkedIn, Naukri, Wellfound, Indeed and company career pages.

Every query MUST target live vacancy listings, not career-information pages.
To do that, every query must contain at least one hiring word:
"jobs", "hiring", "vacancy", "careers", or "openings".

Include:
- Role title variants (e.g. 'Data Analyst jobs', 'Business Analyst hiring', 'Analytics Engineer openings')
- Skill-based queries (e.g. 'SQL Python analyst jobs')
- Domain-specific queries, if a domain is present
- Seniority variants for the candidate's level
- At least one query restricted to a job board, using a site: operator
  (e.g. 'site:linkedin.com/jobs data analyst')

Do NOT generate queries that would return definitions, salary guides, course
listings, "how to become" articles, or professional-association pages.

Return ONLY a JSON array of {num_queries} strings. No markdown. No explanation.
Candidate profile:
{candidate_json}
"""

JUDGE_BATCH_SYSTEM = (
    "You are a senior recruiter with 15 years of experience. You are given a "
    "candidate profile and several raw job description excerpts (already "
    "crawled from job board pages, unstructured). For EACH job, extract a "
    "clean summary and score candidate fit. You return raw JSON only — no "
    "prose before or after it, and no markdown fences."
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

Some crawled pages turn out not to be vacancies at all (career guides, course
pages, association homepages). If a page describes a profession rather than a
specific opening, set "recommendation" to "Skip", "interview_probability" to 0,
and say so in "one_line_reason". Do not invent a company or location for it.

Keep "recommendation" numerically consistent with "interview_probability":
  70-100 -> "Apply Immediately"
  40-69  -> "Apply"
  0-39   -> "Skip"

Return ONLY a valid JSON array of exactly {num_jobs} objects, one per job, in the
same order as the jobs were given, with this schema. Your reply must begin with
"[" and end with "]" — no markdown, no reasoning, no explanation:
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