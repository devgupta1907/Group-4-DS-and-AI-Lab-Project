from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.career_report.internal.models import CareerReportSnapshot


class CareerReportRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, **values: object) -> CareerReportSnapshot:
        row = CareerReportSnapshot(**values)
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return row

    async def get(self, report_id: UUID, user_id: str) -> CareerReportSnapshot | None:
        stmt = select(CareerReportSnapshot).where(
            CareerReportSnapshot.id == report_id, CareerReportSnapshot.user_id == user_id
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def history(
        self, profile_id: UUID, user_id: str, limit: int = 10
    ) -> list[CareerReportSnapshot]:
        stmt = (
            select(CareerReportSnapshot)
            .where(
                CareerReportSnapshot.profile_id == profile_id,
                CareerReportSnapshot.user_id == user_id,
            )
            .order_by(CareerReportSnapshot.created_at.desc())
            .limit(limit)
        )
        return list((await self._session.execute(stmt)).scalars())
