"""Grounded report generation with a deterministic fail-safe."""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

from src.career_report.schemas import (
    ActionItem,
    CareerPathway,
    ReportNarrative,
    RoleGuidance,
    SkillUnlock,
)

PROMPT_VERSION = "v1"


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
            evidence=rec.get("matched_evidence", []),
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
        roles=roles,
        pathways=pathways,
        actions=[
            ActionItem(
                horizon="7_days",
                action="Tailor your resume toward the strongest recommended role.",
                based_on=f"Strongest direction: {strongest}",
            ),
            ActionItem(
                horizon="30_days",
                action=f"Build a small proof-of-skill project focused on {priority}.",
                based_on=f"Repeated gap: {priority}",
            ),
            ActionItem(
                horizon="90_days",
                action="Apply selectively and track which requirements recur across responses.",
                based_on=f"{len(jobs)} shortlisted opportunities",
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
            "Create concise candidate-facing career guidance from the JSON evidence. "
            "Use only supplied roles, skills, gaps and jobs. Never invent facts, scores, "
            "URLs or qualifications. Suggestions must cite evidence. Use categorical "
            "readiness and effort. Every action must name its evidence in based_on. "
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
        return result, GlobalConfig.LLM_MODEL
    except Exception:
        return fallback, ""
