

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.job_discovery_matching.config import JobDiscoveryModuleConfig as Cfg
from src.job_discovery_matching.internal.models import (
    JobDiscoveryJudgeResult,
    JobDiscoveryRanking,
    JobDiscoveryRun,
    JobPosting,
)


def url_hash(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


class JobDiscoveryRepository:
    """Persistence for runs, the job-posting cache, rankings and judge results."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ----------------------------------------------------------------- runs --

    async def create_run(
        self,
        *,
        profile_id: UUID,
        user_id: str,
        preferences: dict,
    ) -> UUID:
        run = JobDiscoveryRun(
            id=uuid4(),
            profile_id=profile_id,
            user_id=user_id,
            preferences=preferences,
        )
        self._session.add(run)
        await self._session.commit()
        return run.id

    async def finish_run(
        self,
        run_id: UUID,
        *,
        status: str,
        message: str,
        search_queries: list[str],
        jobs_discovered: int,
        jobs_after_filter: int,
        embedding_provider: str,
        llm_model: str,
    ) -> None:
        run = await self._session.get(JobDiscoveryRun, run_id)
        if run is None:
            return
        run.status = status
        run.message = message[:1024]
        run.search_queries = search_queries
        run.jobs_discovered = jobs_discovered
        run.jobs_after_filter = jobs_after_filter
        run.embedding_provider = embedding_provider
        run.llm_model = llm_model
        run.completed_at = datetime.now(UTC)
        await self._session.commit()

    async def set_awaiting_query_selection(self, run_id: UUID, *, generated_queries: list[str]) -> None:
        """Marks a run paused at query_selection_gate. Deliberately does NOT
        set completed_at — this run isn't done, it's waiting on the user.
        `generated_queries` is stashed in `search_queries` for now; it's
        overwritten with the queries actually used once the run resumes and
        finish_run() is called for real."""
        run = await self._session.get(JobDiscoveryRun, run_id)
        if run is None:
            return
        run.status = "awaiting_query_selection"
        run.search_queries = generated_queries
        await self._session.commit()

    async def set_awaiting_judge_confirmation(self, run_id: UUID) -> None:
        """Marks a run paused at judge_confirmation_gate. No extra payload
        to stash here (unlike set_awaiting_query_selection) — the hybrid
        rankings are already persisted by rank_persist_module.py by the
        time this is called, so the paused state is fully reconstructable
        from job_discovery_rankings alone if this row is ever re-read."""
        run = await self._session.get(JobDiscoveryRun, run_id)
        if run is None:
            return
        run.status = "awaiting_judge_confirmation"
        await self._session.commit()

    async def get_profile_id(self, run_id: UUID, user_id: str) -> UUID | None:
        stmt = select(JobDiscoveryRun.profile_id).where(
            JobDiscoveryRun.id == run_id, JobDiscoveryRun.user_id == user_id
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    # ------------------------------------------------------------- postings --

    async def get_fresh_posting(self, url: str) -> JobPosting | None:
        """A cached posting is reused only within POSTING_CACHE_TTL_HOURS —
        after that it's treated as stale and re-crawled."""
        stmt = select(JobPosting).where(JobPosting.url_hash == url_hash(url))
        posting = (await self._session.execute(stmt)).scalar_one_or_none()
        if posting is None:
            return None
        cutoff = datetime.now(UTC) - timedelta(hours=Cfg.POSTING_CACHE_TTL_HOURS)
        if posting.last_seen_at is not None and posting.last_seen_at < cutoff:
            return None
        return posting

    async def upsert_posting(
        self,
        *,
        url: str,
        job_json: dict,
        job_text: str,
        embedding: list[float] | None,
    ) -> JobPosting:
        h = url_hash(url)
        stmt = select(JobPosting).where(JobPosting.url_hash == h)
        posting = (await self._session.execute(stmt)).scalar_one_or_none()
        if posting is None:
            posting = JobPosting(
                id=uuid4(),
                url_hash=h,
                source_url=url,
                job_json=job_json,
                job_text=job_text,
                embedding=embedding,
            )
            self._session.add(posting)
        else:
            posting.job_json = job_json
            posting.job_text = job_text
            posting.embedding = embedding
            posting.last_seen_at = datetime.now(UTC)
        await self._session.commit()
        return posting

    # ------------------------------------------------------------- rankings --

    async def save_rankings(
        self,
        run_id: UUID,
        ranked_entries: list[dict],
    ) -> list[JobDiscoveryRanking]:
        """`ranked_entries` are already sorted by hybrid_score descending;
        `rank_position` is assigned from that order (1-based)."""
        rankings: list[JobDiscoveryRanking] = []
        for position, entry in enumerate(ranked_entries, start=1):
            ranking = JobDiscoveryRanking(
                id=uuid4(),
                run_id=run_id,
                posting_id=entry["posting_id"],
                bm25_score=entry["bm25_score"],
                embedding_score=entry["embedding_score"],
                hybrid_score=entry["hybrid_score"],
                rank_position=position,
            )
            self._session.add(ranking)
            rankings.append(ranking)
        await self._session.commit()
        return rankings

    # --------------------------------------------------------- judge results --

    async def save_judge_result(
        self,
        ranking_id: UUID,
        *,
        interview_probability: int,
        strengths: list[str],
        gaps: list[str],
        recommendation: str,
        one_line_reason: str,
        final_score: float,
        used_llm_judge: bool,
    ) -> None:
        self._session.add(
            JobDiscoveryJudgeResult(
                id=uuid4(),
                ranking_id=ranking_id,
                interview_probability=interview_probability,
                strengths=strengths,
                gaps=gaps,
                recommendation=recommendation,
                one_line_reason=one_line_reason,
                final_score=final_score,
                used_llm_judge=used_llm_judge,
            )
        )
        await self._session.commit()

    # ------------------------------------------------------------------ reads --

    async def get_run(self, run_id: UUID, user_id: str | None = None) -> JobDiscoveryRun | None:
        stmt = select(JobDiscoveryRun).where(JobDiscoveryRun.id == run_id)
        if user_id is not None:
            stmt = stmt.where(JobDiscoveryRun.user_id == user_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_latest_run(
        self, profile_id: UUID, user_id: str | None = None
    ) -> JobDiscoveryRun | None:
        stmt = (
            select(JobDiscoveryRun)
            .where(JobDiscoveryRun.profile_id == profile_id)
            .order_by(JobDiscoveryRun.created_at.desc())
            .limit(1)
        )
        if user_id is not None:
            stmt = stmt.where(JobDiscoveryRun.user_id == user_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_runs(
        self, profile_id: UUID, user_id: str | None = None, limit: int = 10
    ) -> list[JobDiscoveryRun]:
        stmt = (
            select(JobDiscoveryRun)
            .where(JobDiscoveryRun.profile_id == profile_id)
            .order_by(JobDiscoveryRun.created_at.desc())
            .limit(limit)
        )
        if user_id is not None:
            stmt = stmt.where(JobDiscoveryRun.user_id == user_id)
        return list((await self._session.execute(stmt)).scalars().all())

    async def get_rankings_with_judge(self, run_id: UUID) -> list[JobDiscoveryRanking]:

        stmt = (
            select(JobDiscoveryRanking)
            .where(JobDiscoveryRanking.run_id == run_id)
            .options(
                selectinload(JobDiscoveryRanking.posting),
                selectinload(JobDiscoveryRanking.judge_result),
            )
            .order_by(JobDiscoveryRanking.rank_position.asc())
        )
        return list((await self._session.execute(stmt)).scalars().all())


    async def find_recent_postings(self, limit: int = 20) -> list[JobPosting]:

        stmt = (
            select(JobPosting)
            .order_by(JobPosting.first_seen_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def find_fresh_postings(self, *, max_age_hours: int, limit: int) -> list[JobPosting]:
        """Postings confirmed (last_seen_at) within `max_age_hours`, most
        recent first. Used by `db_cache_module` to build a candidate pool
        for in-memory similarity scoring against `candidate_embedding` —
        the DB check the pipeline runs BEFORE Adzuna / SearXNG+crawl4ai.
        Unlike `get_fresh_posting`, this isn't keyed by a single URL."""
        cutoff = datetime.now(UTC) - timedelta(hours=max_age_hours)
        stmt = (
            select(JobPosting)
            .where(JobPosting.last_seen_at >= cutoff)
            .order_by(JobPosting.last_seen_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())