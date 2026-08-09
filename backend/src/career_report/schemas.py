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
    career_run_id: UUID | None = None
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


class WeeklyPlan(BaseModel):
    week: int
    theme: str
    outcome: str
    tasks: list[ActionItem] = Field(default_factory=list)


class ProfileAssessment(BaseModel):
    seniority_signal: str = "Evidence-limited profile"
    market_position: str = "The available evidence is not sufficient for a precise positioning."
    evidence_depth: str = "Limited"
    strongest_lane: str = "Career exploration"
    differentiators: list[str] = Field(default_factory=list)
    evidence_summary: list[str] = Field(default_factory=list)
    watchouts: list[str] = Field(default_factory=list)


class ReportNarrative(BaseModel):
    headline: str
    executive_summary: list[str]
    strongest_direction: str
    adjacent_direction: str
    development_priority: str
    profile_assessment: ProfileAssessment = Field(default_factory=ProfileAssessment)
    roles: list[RoleGuidance]
    pathways: list[CareerPathway]
    actions: list[ActionItem]
    weekly_plan: list[WeeklyPlan] = Field(default_factory=list)
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


class ProfileExperience(BaseModel):
    role: str
    company: str = ""
    location: str = ""
    period: str = ""
    evidence: str = ""


class ProfileEducation(BaseModel):
    qualification: str
    institution: str = ""
    period: str = ""


class ProfileProject(BaseModel):
    name: str
    description: str = ""
    technologies: list[str] = Field(default_factory=list)


class ProfileSnapshot(BaseModel):
    current_positioning: str = ""
    experience: list[ProfileExperience] = Field(default_factory=list)
    education: list[ProfileEducation] = Field(default_factory=list)
    projects: list[ProfileProject] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    demonstrated_strengths: list[str] = Field(default_factory=list)
    data_limitations: list[str] = Field(default_factory=list)


class SourceStatus(BaseModel):
    career_status: str = ""
    career_message: str = ""
    job_status: str = ""
    job_message: str = ""


class CareerReportContent(BaseModel):
    candidate_name: str | None = None
    candidate_location: str | None = None
    profile_skills: list[str]
    job_titles: list[str]
    profile_snapshot: ProfileSnapshot = Field(default_factory=ProfileSnapshot)
    source_status: SourceStatus = Field(default_factory=SourceStatus)
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
