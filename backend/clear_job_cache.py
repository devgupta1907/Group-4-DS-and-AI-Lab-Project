"""One-off: clear job_discovery_postings so the DB cache repopulates
clean, instead of serving pre-fix postings (crawled before the location
bug fix / is_real_vacancy check existed) forever within the 1h TTL.

Reuses the app's own DB config (src.core.db) — no separate credentials,
same DATABASE_URL your server already connects with.

Run from the `backend` folder:
    uv run python clear_job_cache.py

Safe to run any time: nothing outside job_discovery_matching reads this
table, and the pipeline repopulates it automatically on the next search
that finds anything (Adzuna, SearXNG, or a direct crawl).
"""

import asyncio

from sqlalchemy import text

from src.core.db import get_session_factory


async def main() -> None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        counts_before = {}
        for table in ("job_discovery_postings", "job_discovery_rankings", "job_discovery_judge_results"):
            result = await session.execute(text(f"SELECT COUNT(*) FROM {table}"))
            counts_before[table] = result.scalar_one()

        # CASCADE here is TRUNCATE's own cascade (Postgres requires it
        # explicitly for TRUNCATE, separate from the FK's own
        # ondelete="CASCADE") — it also clears job_discovery_rankings and
        # job_discovery_judge_results, since both point at postings by ID
        # and would otherwise be orphaned once the postings are gone.
        # job_discovery_runs itself is untouched — it references
        # resume_candidate_profiles, not postings.
        await session.execute(text("TRUNCATE TABLE job_discovery_postings CASCADE"))
        await session.commit()

        for table, before in counts_before.items():
            print(f"Cleared {table} — removed {before} rows.")
        print("Next search will repopulate from scratch (slower run), "
              "then serve fast from cache for 1h after that.")


if __name__ == "__main__":
    asyncio.run(main())
