"""Background worker loop for queued training and analytics jobs."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Callable, Awaitable

from app.services.redis_service import RedisService
from app.services.queue_service import QueueService


logger = logging.getLogger(__name__)


class WorkerService:
    """Simple Redis-list worker loop with per-queue handlers."""

    def __init__(self) -> None:
        self.redis = RedisService()
        self.queue = QueueService()

    async def run_queue(
        self,
        queue_name: str,
        handler: Callable[[dict], Awaitable[None]],
        poll_interval_seconds: float = 1.0,
    ) -> None:
        await self.redis.connect()
        client = self.redis._client

        logger.info("Worker started for queue=%s", queue_name)
        while True:
            job_payload = await client.lpop(f"queue:{queue_name}")
            if not job_payload:
                await asyncio.sleep(poll_interval_seconds)
                continue

            job: dict = {"raw_payload": job_payload}
            try:
                job = json.loads(job_payload)
                await handler(job)
            except Exception as exc:
                logger.exception("Queue job failed queue=%s error=%s", queue_name, exc)
                try:
                    await self.queue.mark_failed(queue_name, job, str(exc))
                except Exception:
                    logger.exception("Failed writing dead-letter for queue=%s", queue_name)
