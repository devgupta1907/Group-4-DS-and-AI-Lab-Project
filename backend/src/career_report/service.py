"""Application service for immutable career report snapshots."""

from __future__ import annotations

import asyncio
from uuid import UUID

from src.career_recommendation import store as career_store
from src.career_recommendation.service import recommend_and_persist
from src.career_report.internal.generator import (
    PROMPT_VERSION,
    build_skill_unlocks,
    generate_narrative,
)
from src.career_report.internal.repository import CareerReportRepository
from src.career_report.schemas import (
    CareerReport,
    CareerReportContent,
    FunnelData,
    JobOpportunity,
    ProfileEducation,
    ProfileExperience,
    ProfileProject,
    ProfileSnapshot,
    SourceStatus,
)
from src.core.db import get_session_factory
from src.core.security import CurrentUser
from src.job_discovery_matching import service as jobs_service
from src.job_discovery_matching.models import JobDiscoveryResult, SearchPreferences
from src.resume_parsing.service import ResumeParsingService


class ReportSourceNotFound(Exception):
    pass


# Statuses discover_jobs_for_profile() can return mid-pipeline rather than
# terminal, each corresponding to one of the pipeline's two interrupts
# (query_selection_gate, judge_confirmation_gate).
_AWAITING_STATUSES = {"awaiting_query_selection", "awaiting_judge_confirmation"}


async def _run_job_discovery_to_completion(
    profile,
    *,
    profile_id: UUID,
    user_id: str,
    preferences: SearchPreferences,
) -> JobDiscoveryResult:
    """
    discover_jobs_for_profile() now pauses mid-pipeline at two gates —
    query_selection_gate and judge_confirmation_gate. The combined report
    flow ("Get Analysis") has no UI for either, so it auto-resumes through
    whichever gates it hits — currently WITHOUT narrowing either one:

      - query_selection_gate: passes ALL of the LLM-generated queries
        (usually 6), not a subset. Used to narrow to [:2] as a cost
        tradeoff (fewer external Adzuna/SearXNG calls) — but once
        location/salary/is_real_vacancy started genuinely filtering
        (rather than being nominally present with little actually
        rejected), 2 queries -> too few raw candidates -> real attrition
        downstream could leave nothing left standing. Measured ~10.5s
        total (SearXNG + extraction combined) for 2 queries in testing,
        so 6 should still land comfortably inside a 1-minute budget on a
        cold run — revisit if that stops being true.
      - judge_confirmation_gate: passes selected_job_urls=None, i.e. NO
        narrowing — judge_module then uses its own default (top
        TOP_N_JUDGED by hybrid score). This used to pass only the top 2
        job URLs, on the assumption that narrowing here was a similar
        cost/breadth tradeoff to the query one above. It is NOT: the judge
        call is a single batched LLM request regardless of how many jobs
        are in it, so narrowing bought no savings — it just meant
        judge_module's `state["final_jobs"]` (which becomes the entire
        report's job list) only ever contained those 2 jobs, instead of
        judging a real top-N and keeping a real list. If either of the 2
        happened to score a 0/100 fit, the frontend correctly hid it,
        leaving ONE visible job in the report. Fixed by not selecting at
        all — same one LLM call, actually judges a proper top-N.

    Bounded to a few rounds as a defensive measure; the pipeline has
    exactly two gates today.
    """
    result = await jobs_service.discover_jobs_for_profile(
        profile, profile_id=profile_id, user_id=user_id, preferences=preferences
    )

    rounds = 0
    while result.status in _AWAITING_STATUSES and result.run_id is not None and rounds < 5:
        rounds += 1
        if result.status == "awaiting_query_selection":
            # Was [:2]. With location/salary/is_real_vacancy now genuinely
            # filtering (not just nominally present), 2 queries -> too few
            # raw candidates -> real attrition (hard_filter, the judge
            # correctly zeroing listing pages) can leave nothing left, as
            # opposed to before, when a thin candidate pool didn't matter
            # much because downstream filtering barely rejected anything.
            # Not narrowing at all here, matching judge_confirmation_gate's
            # fix below — this node measured ~10.5s total for 2 queries in
            # testing (SearXNG + extraction combined), so all 6 should
            # still land comfortably inside a 1-minute budget on a cold run.
            result = await jobs_service.resume_query_selection(
                result.run_id,
                user_id=user_id,
                selected_queries=result.generated_queries or [],
            )
        else:  # awaiting_judge_confirmation
            result = await jobs_service.resume_judge_confirmation(
                result.run_id,
                user_id=user_id,
                proceed=True,
                selected_job_urls=None,
            )

    return result


def _period(start: str | None, end: str | None, current: bool = False) -> str:
    finish = "Present" if current else (end or "")
    return " – ".join(part for part in [start or "", finish] if part)


def _profile_snapshot(profile) -> ProfileSnapshot:
    experience = [
        ProfileExperience(
            role=item.job_title or "Role not specified",
            company=item.company or "",
            location=item.location or "",
            period=_period(item.start_date, item.end_date, bool(item.current_role)),
            evidence=item.description or "",
        )
        for item in profile.experience
    ]
    education = [
        ProfileEducation(
            qualification=" in ".join(part for part in [item.degree, item.field] if part),
            institution=item.institution or "",
            period=_period(item.start_year, item.end_year),
        )
        for item in profile.education
    ]
    projects = [
        ProfileProject(
            name=item.name or "Project",
            description=item.description or "",
            technologies=item.technologies,
        )
        for item in profile.projects
    ]
    limitations = []
    if not profile.projects:
        limitations.append("No projects were identified in the supplied resume.")
    if not profile.certifications:
        limitations.append("No certifications were identified in the supplied resume.")
    if not profile.experience:
        limitations.append("No employment history was identified; role guidance is less specific.")
    current = experience[0].role if experience else (profile.job_titles or ["Open profile"])[0]
    return ProfileSnapshot(
        current_positioning=current,
        experience=experience,
        education=education,
        projects=projects,
        certifications=[
            " · ".join(part for part in [item.name, item.issuer, item.year] if part)
            for item in profile.certifications
        ],
        demonstrated_strengths=profile.skills[:12],
        data_limitations=limitations,
    )


async def run_guidance_pipeline(
    *,
    profile_id: UUID,
    preferences: SearchPreferences,
    user: CurrentUser,
    resume_service: ResumeParsingService,
    career_run_id: UUID | None = None,
) -> CareerReport:
    record = await resume_service.get_profile(profile_id, user)

    if career_run_id is None:
        career_result = await asyncio.to_thread(
            recommend_and_persist,
            record.profile,
            profile_id=profile_id,
            user_id=user.id,
        )
        career_run_id = career_result.run_id

    if career_run_id is None:
        raise ReportSourceNotFound

    # Resolve the location fallback ONCE, here, rather than in every node
    # that reads preferences.target_locations downstream (query-generation
    # prompt, Adzuna's own query param, hard_filter's location match) —
    # by the time the pipeline runs, "no locations given" and "candidate
    # has no resume location either" are the only ways target_locations
    # stays empty; everything past this point can just read the list.
    if not preferences.target_locations and record.profile.contact.location:
        preferences = preferences.model_copy(
            update={"target_locations": [record.profile.contact.location]}
        )

    jobs_result = await _run_job_discovery_to_completion(
        record.profile,
        profile_id=profile_id,
        user_id=user.id,
        preferences=preferences,
    )
    if jobs_result.run_id is None:
        raise ReportSourceNotFound

    return await generate_report(
        profile_id=profile_id,
        career_run_id=career_run_id,
        job_run_id=jobs_result.run_id,
        user=user,
        resume_service=resume_service,
    )


def _to_report(row) -> CareerReport:
    return CareerReport(
        id=row.id,
        profile_id=row.profile_id,
        career_run_id=row.career_run_id,
        job_run_id=row.job_run_id,
        status=row.status,
        model_used=row.model_used,
        prompt_version=row.prompt_version,
        content=row.content,
        created_at=row.created_at,
    )


async def generate_report(
    *,
    profile_id: UUID,
    career_run_id: UUID,
    job_run_id: UUID,
    user: CurrentUser,
    resume_service: ResumeParsingService,
) -> CareerReport:
    record = await resume_service.get_profile(profile_id, user)
    career_run = career_store.get_run(career_run_id, user_id=user.id)
    job_profile_id = await jobs_service.get_run_profile_id(job_run_id, user.id)
    job_result = await jobs_service.get_run(job_run_id, user_id=user.id)
    if (
        career_run is None
        or career_run["profile_id"] != str(profile_id)
        or job_result is None
        or job_profile_id != profile_id
    ):
        raise ReportSourceNotFound

    recommendations = career_run["result"].get("recommendations", [])
    jobs = [item.model_dump(mode="json") for item in job_result.top_jobs[:5]]
    profile = record.profile.model_dump(mode="json")
    narrative, model = generate_narrative(profile, recommendations, jobs)
    opportunities = [
        JobOpportunity(
            title=item["job"]["title"],
            company=item["job"]["company"],
            location=item["job"]["location"],
            source_url=item["job"]["source_url"],
            interview_probability=(item.get("judge") or {}).get("interview_probability", 0),
            recommendation=(item.get("judge") or {}).get("recommendation", "Skip"),
            reason=(item.get("judge") or {}).get("one_line_reason", ""),
            strengths=(item.get("judge") or {}).get("strengths", []),
            gaps=(item.get("judge") or {}).get("gaps", []),
        )
        for item in jobs
    ]
    content = CareerReportContent(
        candidate_name=record.profile.contact.name,
        candidate_location=record.profile.contact.location,
        profile_skills=record.profile.skills,
        job_titles=record.profile.job_titles,
        profile_snapshot=_profile_snapshot(record.profile),
        source_status=SourceStatus(
            career_status=career_run["status"],
            career_message=career_run["message"],
            job_status=job_result.status,
            job_message=job_result.message,
        ),
        narrative=narrative,
        skill_unlocks=build_skill_unlocks(
            jobs, [r.get("occupation_title", "") for r in recommendations]
        ),
        funnel=FunnelData(
            discovered=job_result.jobs_discovered,
            filtered=job_result.jobs_after_filter,
            shortlisted=len(jobs),
        ),
        opportunities=opportunities,
        methodology=[
            "Career directions come from the stored Career Recommendation run.",
            "Job metrics and links come directly from the stored Job Discovery run.",
            "Narrative guidance is constrained to supplied evidence; a deterministic "
            "fallback is used if the model is unavailable.",
        ],
    )
    async with get_session_factory()() as session:
        row = await CareerReportRepository(session).save(
            profile_id=profile_id,
            career_run_id=career_run_id,
            job_run_id=job_run_id,
            user_id=user.id,
            status="ok" if model else "degraded_no_llm",
            model_used=model,
            prompt_version=PROMPT_VERSION,
            content=content.model_dump(mode="json"),
        )
    return _to_report(row)


async def get_report(report_id: UUID, user_id: str) -> CareerReport | None:
    async with get_session_factory()() as session:
        row = await CareerReportRepository(session).get(report_id, user_id)
        return _to_report(row) if row else None


async def get_history(profile_id: UUID, user_id: str) -> list[CareerReport]:
    async with get_session_factory()() as session:
        rows = await CareerReportRepository(session).history(profile_id, user_id)
        return [_to_report(row) for row in rows]
