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
from src.job_discovery_matching.models import SearchPreferences
from src.resume_parsing.service import ResumeParsingService


class ReportSourceNotFound(Exception):
    pass


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
) -> CareerReport:
    """The single end-to-end entry point after a resume has been reviewed."""
    record = await resume_service.get_profile(profile_id, user)
    career_task = asyncio.to_thread(
        recommend_and_persist,
        record.profile,
        profile_id=profile_id,
        user_id=user.id,
    )
    jobs_task = jobs_service.discover_jobs_for_profile(
        record.profile,
        profile_id=profile_id,
        user_id=user.id,
        preferences=preferences,
    )
    career_result, jobs_result = await asyncio.gather(career_task, jobs_task)
    if career_result.run_id is None or jobs_result.run_id is None:
        raise ReportSourceNotFound
    return await generate_report(
        profile_id=profile_id,
        career_run_id=career_result.run_id,
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
