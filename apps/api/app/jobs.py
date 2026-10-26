"""In-process background jobs with bounded concurrency.

Fine for a single API instance; move to a Redis-backed queue (arq/RQ) when scaling out.
"""
import asyncio
import logging

log = logging.getLogger("saasta.jobs")
_sem = asyncio.Semaphore(8)
_tasks: set[asyncio.Task] = set()


def spawn(coro) -> None:
    async def runner():
        async with _sem:
            try:
                await coro
            except Exception:
                log.exception("background job failed")

    t = asyncio.create_task(runner())
    _tasks.add(t)
    t.add_done_callback(_tasks.discard)
