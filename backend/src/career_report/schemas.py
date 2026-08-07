"""Public wire contracts for immutable career guidance reports."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

Readiness = Literal["ready_now", "near_term_stretch", "longer_term_transition"]
Effort = Literal["low", "medium", "high"]


class GenerateReportRequest(BaseModel):
    profile_id: UUID
    target_location: str | None = None
    remote_only: bool = False
    min_salary_lpa: float | None = None


class RoleGuidance(BaseModel):
    title: str
    readiness: Readiness
    confidence: Literal["high", "medium", "low"]
    rationale: str
    evidence: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    skills_to_learn: list[str] = Field(default_factory=list)
    effort: Effort = "low"
    next_step: str = ""


class SkillUnlock(BaseModel):
    skill: str
    category: Literal["quick_win", "core_gap", "differentiator"]
    unlocks: list[str] = Field(default_factory=list)
    evidence_count: int = 0


class CareerPathway(BaseModel):
    kind: Literal["immediate", "growth", "pivot"]
    title: str
    target_roles: list[str]
    evidence: list[str]
    gaps: list[str]
    learning_priorities: list[str]
    example_job_titles: list[str]


class ActionItem(BaseModel):
    horizon: Literal["7_days", "30_days", "90_days"]
    action: str
    based_on: str


class ReportNarrative(BaseModel):
    headline: str
    executive_summary: list[str]
    strongest_direction: str
    adjacent_direction: str
    development_priority: str
    roles: list[RoleGuidance]
    pathways: list[CareerPathway]
    actions: list[ActionItem]
    limitations: list[str]


class FunnelData(BaseModel):
    discovered: int
    filtered: int
    shortlisted: int


class JobOpportunity(BaseModel):
    title: str
    company: str
    location: str
    source_url: str
    interview_probability: int
    recommendation: str
    reason: str
    strengths: list[str]
    gaps: list[str]


class CareerReportContent(BaseModel):
    candidate_name: str | None = None
    candidate_location: str | None = None
    profile_skills: list[str]
    job_titles: list[str]
    narrative: ReportNarrative
    skill_unlocks: list[SkillUnlock]
    funnel: FunnelData
    opportunities: list[JobOpportunity]
    methodology: list[str]


class CareerReport(BaseModel):
    id: UUID
    profile_id: UUID
    career_run_id: UUID
    job_run_id: UUID
    status: Literal["ok", "degraded_no_llm"]
    model_used: str
    prompt_version: str
    content: CareerReportContent
    created_at: datetime
