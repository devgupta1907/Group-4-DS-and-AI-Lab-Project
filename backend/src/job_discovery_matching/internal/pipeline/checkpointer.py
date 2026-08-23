"""Postgres-backed checkpointer for the job-discovery LangGraph pipeline —
Windows-safe against a real conflict between two hard requirements:

  - Async psycopg (`AsyncPostgresSaver`, what LangGraph's `.ainvoke()` /
    `.astream()` need — a SYNC saver like `PostgresSaver` raises
    NotImplementedError on every async method; it's for sync `.invoke()`
    graphs only, and our nodes are all `async def`, so that's not an
    option either) only works under `asyncio.SelectorEventLoop` on
    Windows.
  - crawl4ai/Playwright (the SearXNG fallback search path) needs
    `asyncio.ProactorEventLoop` on Windows for subprocess support —
    Selector can't launch subprocesses on Windows at all. `src/app.py`
    sets `WindowsProactorEventLoopPolicy()` for exactly this reason
    (and it's also just Windows' asyncio default since Python 3.8, so
    there's no "leave it unset" escape hatch either).

One process can't run both loop policies as its main loop at once. The
fix: keep the main app loop on Proactor (crawl4ai keeps working
unmodified), and run the ENTIRE async-psycopg checkpointer on a
dedicated background thread with its own persistent `SelectorEventLoop`
— `_SelectorLoopThread` below. Every checkpoint read/write is bounced
onto that thread via `run_coroutine_threadsafe` and awaited normally
from the caller's (Proactor) loop; `WindowsSafeAsyncPostgresSaver` is
just that bridge — `AsyncPostgresSaver` itself, and all real psycopg
I/O, only ever runs inside the Selector thread.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from collections.abc import AsyncIterator, Sequence
from functools import lru_cache
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    ChannelVersions,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
)
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool

from src.core.config import get_settings

logger = logging.getLogger(__name__)


def _psycopg_url() -> str:
    url = get_settings().database_url
    # postgresql+asyncpg://... -> postgresql://... (psycopg3 default driver)
    return url.replace("postgresql+asyncpg://", "postgresql://")


class _SelectorLoopThread:
    """One persistent background thread running its own asyncio
    SelectorEventLoop, isolated from whatever the main app loop is doing.
    Coroutines are submitted here from any other thread/loop via `.run()`
    and awaited there as a normal future — the caller never needs to
    know the work actually happened on a different loop entirely."""

    def __init__(self) -> None:
        self._loop = asyncio.SelectorEventLoop()
        self._thread = threading.Thread(
            target=self._run_forever, daemon=True, name="pg-checkpointer-selector-loop"
        )
        self._thread.start()

    def _run_forever(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def run(self, coro):
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return asyncio.wrap_future(future)


@lru_cache
def _loop_thread() -> _SelectorLoopThread:
    return _SelectorLoopThread()


class WindowsSafeAsyncPostgresSaver(BaseCheckpointSaver):
    """Drop-in `BaseCheckpointSaver` that delegates every method to a real
    `AsyncPostgresSaver`, but constructs and calls that saver ONLY from
    inside `_SelectorLoopThread` — see module docstring for why. On
    non-Windows platforms this indirection is harmless (one extra thread,
    not a requirement) — kept unconditional rather than branched by
    `sys.platform`, so the code path is identical, and equally tested, on
    every OS the team develops on."""

    def __init__(self) -> None:
        super().__init__()
        self._loop_thread = _loop_thread()
        self._saver: AsyncPostgresSaver | None = None
        self._init_lock = asyncio.Lock()

    async def _ensure_saver(self) -> AsyncPostgresSaver:
        if self._saver is not None:
            return self._saver
        async with self._init_lock:
            if self._saver is None:

                async def _build() -> AsyncPostgresSaver:
                    pool = AsyncConnectionPool(
                        conninfo=_psycopg_url(),
                        max_size=5,
                        open=False,
                        # Supabase's pooler silently closes idle
                        # server-side connections well before our own pool
                        # would ever consider them stale. Without `check`,
                        # the pool hands out those dead connections as-is
                        # and the first query on them dies with "server
                        # closed the connection unexpectedly" — exactly
                        # the failure seen resuming at
                        # judge_confirmation_gate, the one step with a
                        # real human-timescale wait before the resume.
                        # This makes the pool probe (cheap SELECT 1) and
                        # transparently replace a connection on checkout
                        # instead of handing out a corpse.
                        check=AsyncConnectionPool.check_connection,
                        # Recycle idle connections proactively, well under
                        # Supabase's own idle-close window, so most never
                        # get the chance to go stale in the first place.
                        # `check` above is the real fix; this just reduces
                        # how often it has to do any work.
                        max_idle=60,
                        kwargs={
                            "autocommit": True,
                            "prepare_threshold": None,
                            # TCP keepalives: surfaces a half-dead socket
                            # (proxy dropped it without a clean FIN) as an
                            # error quickly instead of hanging silently.
                            "keepalives": 1,
                            "keepalives_idle": 30,
                            "keepalives_interval": 10,
                            "keepalives_count": 3,
                        },
                    )
                    await pool.open()
                    return AsyncPostgresSaver(pool)

                self._saver = await self._loop_thread.run(_build())
        return self._saver

    async def setup(self) -> None:
        saver = await self._ensure_saver()
        await self._loop_thread.run(saver.setup())

    async def aget_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        saver = await self._ensure_saver()
        return await self._loop_thread.run(saver.aget_tuple(config))

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        saver = await self._ensure_saver()
        return await self._loop_thread.run(saver.aput(config, checkpoint, metadata, new_versions))

    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        saver = await self._ensure_saver()
        await self._loop_thread.run(saver.aput_writes(config, writes, task_id, task_path))

    async def adelete_thread(self, thread_id: str) -> None:
        saver = await self._ensure_saver()
        await self._loop_thread.run(saver.adelete_thread(thread_id))

    async def alist(
        self,
        config: RunnableConfig | None,
        *,
        filter: dict[str, Any] | None = None,
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ) -> AsyncIterator[CheckpointTuple]:
        """Collects the full result inside the selector-loop thread first,
        then yields it here — simpler and safer than bridging an async
        generator across threads item-by-item. A single job-discovery
        run's checkpoint history is a handful of steps, so the eager
        collection costs nothing real in practice."""
        saver = await self._ensure_saver()

        async def _collect() -> list[CheckpointTuple]:
            return [item async for item in saver.alist(config, filter=filter, before=before, limit=limit)]

        items = await self._loop_thread.run(_collect())
        for item in items:
            yield item


_checkpointer: WindowsSafeAsyncPostgresSaver | None = None


async def get_checkpointer() -> WindowsSafeAsyncPostgresSaver:
    """Lazily builds and returns the shared checkpointer instance. Call
    `ensure_checkpointer_tables()` once at app startup before this is
    ever used for a real run — see `src/app.py`."""
    global _checkpointer
    if _checkpointer is None:
        _checkpointer = WindowsSafeAsyncPostgresSaver()
    return _checkpointer


async def ensure_checkpointer_tables() -> None:
    """Creates the checkpoint tables if they don't exist yet. Idempotent —
    safe to call on every app startup, not just the first ever."""
    checkpointer = await get_checkpointer()
    await checkpointer.setup()
    logger.info("LangGraph checkpoint tables ready (job_discovery_matching)")