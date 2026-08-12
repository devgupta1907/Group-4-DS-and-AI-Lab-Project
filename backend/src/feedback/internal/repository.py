"""Persistence for feedback. Private to the module."""

from __future__ import annotations

from collections import Counter
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.feedback.internal.models import Feedback


class FeedbackRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(
        self,
        *,
        user_id: str,
        rating: int,
        reasons: list[str],
        comment: str,
        profile_id: UUID | None,
    ) -> Feedback:
        row = Feedback(
            user_id=user_id,
            rating=rating,
            reasons=reasons,
            comment=comment,
            profile_id=profile_id,
        )
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return row

    async def list_for_user(self, user_id: str, limit: int = 20) -> list[Feedback]:
        stmt = (
            select(Feedback)
            .where(Feedback.user_id == user_id)
            .order_by(Feedback.created_at.desc())
            .limit(limit)
        )
        return list((await self._session.execute(stmt)).scalars())

    async def summarise(self) -> tuple[int, float, dict[int, int], dict[str, int]]:
        """
        Aggregates across all responses, for reporting.

        Counted in Python rather than in SQL: the reasons are JSONB arrays, so
        counting them in the query would need an unnest, and at the scale this
        table will reach during the project the difference is not measurable.
        Revisit if the table grows past a few thousand rows.
        """
        rows = list((await self._session.execute(select(Feedback))).scalars())
        if not rows:
            return 0, 0.0, {}, {}

        ratings = [row.rating for row in rows]
        distribution = Counter(ratings)
        reasons = Counter(reason for row in rows for reason in (row.reasons or []))

        return (
            len(rows),
            round(sum(ratings) / len(ratings), 2),
            {score: distribution.get(score, 0) for score in range(1, 11)},
            dict(reasons),
        )
