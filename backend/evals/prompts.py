"""Prompt variants under comparison.

`baseline` is the live production prompt, imported rather than copied so the
experiment always measures what actually ships. Every other entry is a candidate
edit to `internal/prompts/system.py` — the winner gets promoted by editing that
file, and the experiment is the evidence for the change.

Tune here against the 35-resume dev split only. The 52-resume test split is
touched once, on the winner (AGENTS.md, "Model contract").
"""

from __future__ import annotations

from src.resume_parsing.internal.prompts import SYSTEM_PROMPT

# Adds an explicit worked ruling on the two things the dev-set annotations show
# models most often get wrong: inventing employers for bullet lists, and
# splitting one skill line into fragments.
STRICTER_ABSTENTION = SYSTEM_PROMPT + """

8. If a section header exists but its content is unreadable, emit an empty list
   rather than guessing. An empty section is correct; an invented one is not.
9. A skill is one named technology, tool or competency. Do not split a phrase
   like "Data warehousing and modeling" into separate entries unless the resume
   itself lists them separately.
10. Only list an employer under experience if a company name is actually printed.
    A bullet describing work with no named employer has company: null."""

# Pushes job_titles to be the normalised superset of experience titles, which is
# what downstream Career Recommendation consumes.
TITLE_FOCUSED = SYSTEM_PROMPT + """

8. job_titles must contain every distinct role title appearing anywhere in the
   resume, including titles named only in a summary line, normalised to their
   common form (e.g. "Sr. SW Engr" -> "Senior Software Engineer"). Preserve the
   original spelling inside experience[].job_title."""

VARIANTS: dict[str, str] = {
    "baseline": SYSTEM_PROMPT,
    "strict-abstention": STRICTER_ABSTENTION,
    "title-focused": TITLE_FOCUSED,
}
