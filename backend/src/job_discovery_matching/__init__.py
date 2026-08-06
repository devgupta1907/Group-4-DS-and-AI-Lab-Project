"""Job Discovery & Matching — turns a Resume Parsing profile into ranked,
judged job recommendations discovered live from the web.

The only things the rest of the application may use:

    register_job_discovery(app)         mount the module
    discover_jobs_for_profile(...)      run the pipeline for one profile
    get_latest_run(profile_id)          read back the most recent run
    get_run(run_id)                     read back one run by id
    JobDiscoveryResult, RankedJob, ...  its public shapes

Everything under `internal/` is private — see `.importlinter` at the repo
root for the enforced contract (mirrors resume_parsing's module isolation).
"""

from __future__ import annotations

from fastapi import FastAPI

from src.job_discovery_matching.api import router
from src.job_discovery_matching.models import (
    JobDiscoveryResult,
    JobPostingView,
    JudgeResultView,
    RankedJob,
    SearchPreferences,
)
from src.job_discovery_matching.service import (
    discover_jobs_for_profile,
    get_latest_run,
    get_run,
    get_runs,
)


def register_job_discovery(app: FastAPI) -> None:
    """Mount this module onto an application."""
    app.include_router(router)


__all__ = [
    "JobDiscoveryResult",
    "JobPostingView",
    "JudgeResultView",
    "RankedJob",
    "SearchPreferences",
    "discover_jobs_for_profile",
    "get_latest_run",
    "get_run",
    "get_runs",
    "register_job_discovery",
]
