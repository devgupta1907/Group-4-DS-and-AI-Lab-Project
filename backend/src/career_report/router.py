from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Response

from src.career_report import service
from src.career_report.internal.pdf import render_pdf
from src.career_report.schemas import CareerReport, GenerateReportRequest
from src.core.security import CurrentUserDep
from src.job_discovery_matching.models import SearchPreferences
from src.resume_parsing.dependencies import ServiceDep
from src.resume_parsing.errors import ProfileNotFound

router = APIRouter(prefix="/api/career-reports", tags=["career-reports"])


@router.post("", response_model=CareerReport, status_code=201)
async def create_report(
    request: GenerateReportRequest, user: CurrentUserDep, resume_service: ServiceDep
) -> CareerReport:
    try:
        return await service.run_guidance_pipeline(
            profile_id=request.profile_id,
            career_run_id=request.career_run_id,
            preferences=SearchPreferences(
                target_location=request.target_location,
                remote_only=request.remote_only,
                min_salary_lpa=request.min_salary_lpa,
            ),
            user=user,
            resume_service=resume_service,
        )
    except (ProfileNotFound, service.ReportSourceNotFound) as exc:
        raise HTTPException(
            status_code=404, detail="One or more report sources were not found."
        ) from exc


@router.get("/{report_id}", response_model=CareerReport)
async def read_report(report_id: UUID, user: CurrentUserDep) -> CareerReport:
    report = await service.get_report(report_id, user.id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found.")
    return report


@router.get("/{report_id}/pdf")
async def download_pdf(report_id: UUID, user: CurrentUserDep) -> Response:
    report = await service.get_report(report_id, user.id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found.")
    try:
        document = await render_pdf(report)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="PDF renderer is unavailable.") from exc
    return Response(
        document,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="career-report-{report_id}.pdf"'},
    )


@router.get("/profile/{profile_id}", response_model=list[CareerReport])
async def report_history(profile_id: UUID, user: CurrentUserDep) -> list[CareerReport]:
    return await service.get_history(profile_id, user.id)
