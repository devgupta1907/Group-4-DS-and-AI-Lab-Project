"""Grounded report generation with a deterministic fail-safe."""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

from src.career_report.schemas import (
    ActionItem,
    CareerPathway,
    ProfileAssessment,
    ReportNarrative,
    RoleGuidance,
    SkillUnlock,
    WeeklyPlan,
)

PROMPT_VERSION = "v3"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _profile_assessment(profile: dict[str, Any], strongest: str) -> ProfileAssessment:
    experience = profile.get("experience") or []
    education = profile.get("education") or []
    skills = [str(skill) for skill in (profile.get("skills") or []) if skill]
    titles = [_text(item.get("job_title")) for item in experience if item.get("job_title")]
    title_text = " ".join(titles).lower()
    senior = any(marker in title_text for marker in ("senior", "sr.", "lead", "principal"))
    seniority = (
        "Established senior-level profile"
        if senior
        else (
            "Established professional profile"
            if len(experience) >= 2
            else "Developing professional profile"
        )
    )
    depth = (
        "Substantial"
        if len(experience) >= 3 and len(skills) >= 8
        else ("Moderate" if experience and len(skills) >= 4 else "Limited")
    )
    evidence = []
    if titles:
        evidence.append(f"Role progression includes {', '.join(titles[:3])}.")
    if skills:
        evidence.append(
            f"The resume repeatedly presents a technical base spanning {', '.join(skills[:6])}."
        )
    if education:
        degree = _text(education[0].get("degree"))
        field = _text(education[0].get("field"))
        if degree or field:
            evidence.append(f"Formal foundation: {' in '.join(x for x in (degree, field) if x)}.")
    differentiators = []
    if senior:
        differentiators.append(
            "Senior-title experience supports ownership beyond entry-level delivery."
        )
    if len(skills) >= 8:
        differentiators.append(
            "Breadth across the stated stack supports cross-functional software delivery."
        )
    if len(experience) >= 2:
        differentiators.append(
            "Multiple experience entries provide more than a single-project signal."
        )
    watchouts = []
    if not profile.get("projects"):
        watchouts.append(
            "No separate portfolio projects were identified, so recent work outcomes "
            "must carry the proof."
        )
    if not profile.get("certifications"):
        watchouts.append(
            "No certifications were identified; this matters only where target jobs "
            "explicitly request them."
        )
    return ProfileAssessment(
        seniority_signal=seniority,
        market_position=(
            f"Your strongest evidenced market lane is {strongest}. This is a "
            "profile-positioning signal, not a percentile ranking against other candidates."
        ),
        evidence_depth=depth,
        strongest_lane=strongest,
        differentiators=differentiators[:3],
        evidence_summary=evidence[:4],
        watchouts=watchouts,
    )


def _role_evidence(rec: dict[str, Any], profile: dict[str, Any]) -> list[str]:
    evidence = [str(item) for item in (rec.get("matched_evidence") or []) if item]
    experience = profile.get("experience") or []
    titles = [_text(item.get("job_title")) for item in experience if item.get("job_title")]
    skills = [str(skill) for skill in (profile.get("skills") or []) if skill]
    if titles:
        evidence.append(f"Role history: {', '.join(titles[:3])}")
    if skills:
        evidence.append(f"Broader demonstrated stack: {', '.join(skills[:6])}")
    return list(dict.fromkeys(evidence))[:6]


def repeated_gaps(jobs: list[dict[str, Any]]) -> list[tuple[str, int]]:
    counts = Counter(
        gap.strip()
        for job in jobs
        for gap in ((job.get("judge") or {}).get("gaps") or [])
        if gap and gap.strip()
    )
    return sorted(
        ((skill, count) for skill, count in counts.items() if count >= 2),
        key=lambda item: (-item[1], item[0].lower()),
    )


def build_skill_unlocks(jobs: list[dict[str, Any]], roles: list[str]) -> list[SkillUnlock]:
    unlocks = []
    for index, (skill, count) in enumerate(repeated_gaps(jobs)):
        category = "quick_win" if index == 0 else "core_gap" if count >= 3 else "differentiator"
        unlocks.append(
            SkillUnlock(
                skill=skill,
                category=category,
                unlocks=roles[:3],
                evidence_count=count,
            )
        )
    return unlocks[:8]


def fallback_narrative(
    profile: dict[str, Any], recommendations: list[dict[str, Any]], jobs: list[dict[str, Any]]
) -> ReportNarrative:
    role_titles = [
        r.get("occupation_title", "") for r in recommendations if r.get("occupation_title")
    ]
    skills = profile.get("skills", [])
    gaps = [name for name, _ in repeated_gaps(jobs)]
    strongest = (
        role_titles[0] if role_titles else (profile.get("job_titles") or ["Career exploration"])[0]
    )
    adjacent = role_titles[1] if len(role_titles) > 1 else strongest
    roles = [
        RoleGuidance(
            title=title,
            readiness="ready_now" if i == 0 else "near_term_stretch",
            confidence=rec.get("confidence", "medium"),
            rationale=rec.get(
                "explanation", "This direction aligns with the available profile evidence."
            ),
            evidence=_role_evidence(rec, profile),
            missing_skills=gaps[:3],
            skills_to_learn=gaps[:3],
            effort="low" if i == 0 else "medium",
            next_step=f"Review live {title} roles and compare their recurring requirements.",
        )
        for i, (title, rec) in enumerate(
            (r.get("occupation_title", ""), r) for r in recommendations[:3]
        )
        if title
    ]
    pathways = [
        CareerPathway(
            kind=kind,
            title=label,
            target_roles=role_titles[index : index + 1] or [strongest],
            evidence=skills[:4],
            gaps=gaps[:3] if kind != "immediate" else [],
            learning_priorities=gaps[:3],
            example_job_titles=[j.get("job", {}).get("title", "") for j in jobs[index : index + 2]],
        )
        for index, (kind, label) in enumerate(
            [
                ("immediate", "Build on your current evidence"),
                ("growth", "Unlock an adjacent role"),
                ("pivot", "Explore a longer-term niche"),
            ]
        )
    ]
    priority = gaps[0] if gaps else "Make your strongest evidence more visible"
    actions = [
        ActionItem(
            horizon="7_days",
            action="Rewrite the profile summary around the strongest demonstrated role.",
            based_on=f"Strongest direction: {strongest}",
        ),
        ActionItem(
            horizon="7_days",
            action="Add two outcome-focused bullets to the most relevant recent experience.",
            based_on="Evidence in the current experience history",
        ),
        ActionItem(
            horizon="30_days",
            action=f"Create one focused proof-of-skill artifact around {priority}.",
            based_on=f"Development priority: {priority}",
        ),
        ActionItem(
            horizon="30_days",
            action=f"Build a saved search for {strongest} and {adjacent} roles.",
            based_on=f"Recommended directions: {strongest}; {adjacent}",
        ),
        ActionItem(
            horizon="90_days",
            action="Apply selectively and record recurring requirements and responses.",
            based_on=f"{len(jobs)} shortlisted opportunities in this run",
        ),
        ActionItem(
            horizon="7_days",
            action=f"Create a two-line positioning statement for {strongest} roles.",
            based_on=f"Strongest direction: {strongest}",
        ),
        ActionItem(
            horizon="30_days",
            action="Map three recent achievements to recurring target-role requirements.",
            based_on="Experience and role evidence in this report",
        ),
        ActionItem(
            horizon="30_days",
            action=f"Draft one interview story demonstrating {priority} in context.",
            based_on=f"Development priority: {priority}",
        ),
        ActionItem(
            horizon="30_days",
            action="Compare ten saved roles and record requirements appearing at least twice.",
            based_on="Repeated-gap rule used by this report",
        ),
        ActionItem(
            horizon="30_days",
            action=f"Tailor one resume version for {strongest} and one for {adjacent}.",
            based_on=f"Recommended directions: {strongest}; {adjacent}",
        ),
        ActionItem(
            horizon="90_days",
            action="Submit a small, targeted application batch and track response quality.",
            based_on="Live opportunities and current-fit directions",
        ),
        ActionItem(
            horizon="90_days",
            action="Review response data and revise positioning, evidence, or target roles.",
            based_on="Measured application-cycle findings",
        ),
    ]
    return ReportNarrative(
        headline=f"Your strongest current direction is {strongest}",
        executive_summary=[
            f"Your profile shows evidence across {len(skills)} listed skills.",
            f"{len(jobs)} live opportunities were shortlisted for closer review.",
            f"Focus next on {priority}.",
        ],
        strongest_direction=strongest,
        adjacent_direction=adjacent,
        development_priority=priority,
        profile_assessment=_profile_assessment(profile, strongest),
        roles=roles,
        pathways=pathways,
        actions=actions,
        weekly_plan=[
            WeeklyPlan(
                week=1,
                theme="Clarify your positioning",
                outcome=f"A resume clearly positioned for {strongest}",
                tasks=actions[:2] + actions[5:6],
            ),
            WeeklyPlan(
                week=2,
                theme="Build market evidence",
                outcome=f"One visible artifact demonstrating {priority}",
                tasks=actions[2:3] + actions[6:8],
            ),
            WeeklyPlan(
                week=3,
                theme="Create a focused opportunity list",
                outcome="A shortlist built around current-fit and adjacent roles",
                tasks=actions[3:4] + actions[8:10],
            ),
            WeeklyPlan(
                week=4,
                theme="Run a measured application cycle",
                outcome="Applications tracked with evidence about what the market rewards",
                tasks=actions[4:5] + actions[10:12],
            ),
        ],
        limitations=[
            "Recommendations reflect the supplied resume and the jobs available during this run.",
            "Interview probability is a guidance signal, not an employment guarantee.",
        ],
    )


def generate_narrative(
    profile: dict[str, Any], recommendations: list[dict[str, Any]], jobs: list[dict[str, Any]]
) -> tuple[ReportNarrative, str]:
    fallback = fallback_narrative(profile, recommendations, jobs)
    try:
        from src.core.config import GlobalConfig
        from src.services.llm_client import llm

        if not GlobalConfig.GOOGLE_API_KEY:
            return fallback, ""
        allowed_roles = [r.get("occupation_title") for r in recommendations]
        allowed_gaps = [name for name, _ in repeated_gaps(jobs)]
        evidence = json.dumps(
            {"profile": profile, "recommendations": recommendations, "jobs": jobs}
        )
        prompt = (
            "Create detailed, candidate-facing career guidance from the JSON evidence. "
            "Use only supplied roles, skills, gaps and jobs. Never invent facts, scores, "
            "URLs or qualifications. Suggestions must cite evidence. Use categorical "
            "readiness and effort. Explore the candidate's current positioning before future "
            "options. Include a profile_assessment that interprets seniority, evidence depth, "
            "strongest market lane, differentiators and watchouts without repeating raw resume "
            "sections or inventing a percentile rank. Provide 3-5 roles and give each role a "
            "substantial rationale plus 3-6 independent evidence signals. One isolated skill is "
            "never sufficient proof of role fit. Provide three pathways and a four-week "
            "weekly_plan with at least three specific tasks per week. Every task must name "
            "its evidence in based_on. "
            f"Allowed role titles: {allowed_roles}. Allowed skills to learn: {allowed_gaps}. "
            f"Evidence: {evidence}"
        )
        result = llm.with_structured_output(ReportNarrative).invoke(prompt)
        if any(role.title not in allowed_roles for role in result.roles):
            return fallback, ""
        if any(
            skill not in allowed_gaps for role in result.roles for skill in role.skills_to_learn
        ):
            return fallback, ""
        if any(len(role.evidence) < 2 for role in result.roles):
            return fallback, ""
        if len(result.weekly_plan) != 4 or any(len(week.tasks) < 3 for week in result.weekly_plan):
            return fallback, ""
        return result, GlobalConfig.LLM_MODEL
    except Exception:
        return fallback, ""
