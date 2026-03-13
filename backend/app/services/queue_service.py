"""Redis-backed queue service with idempotency, retries, and dead-letter support."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from app.core.config import settings
from app.services.redis_service import RedisService


@dataclass
class QueueJob:
    id: str
    queue: str
    job_type: str
    payload: dict[str, Any]
    trace_id: Optional[str] = None
    idempotency_key: Optional[str] = None
    retries: int = 0
    max_retries: int = settings.QUEUE_MAX_RETRIES
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "queue": self.queue,
            "job_type": self.job_type,
            "payload": self.payload,
            "trace_id": self.trace_id,
            "idempotency_key": self.idempotency_key,
            "retries": self.retries,
            "max_retries": self.max_retries,
            "created_at": self.created_at,
        }


class QueueService:
    """Queue abstraction used by API routes and workers."""

    def __init__(self) -> None:
        self.redis = RedisService()

    async def enqueue(
        self,
        queue_name: str,
        job_type: str,
        payload: dict[str, Any],
        *,
        idempotency_key: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> dict[str, Any]:
        await self.redis.connect()
        client = self.redis._client

        if idempotency_key:
            seen_key = f"queue:idempotency:{queue_name}:{idempotency_key}"
            if await client.set(seen_key, "1", ex=86400, nx=True) is not True:
                return {
                    "status": "duplicate",
                    "queue": queue_name,
                    "idempotency_key": idempotency_key,
                }

        job = QueueJob(
            id=str(uuid.uuid4()),
            queue=queue_name,
            job_type=job_type,
            payload=payload,
            trace_id=trace_id,
            idempotency_key=idempotency_key,
        )
        await client.rpush(f"queue:{queue_name}", json.dumps(job.as_dict()))
        return {"status": "queued", "queue": queue_name, "job_id": job.id}

    async def queue_status(self) -> dict[str, Any]:
        await self.redis.connect()
        client = self.redis._client
        queues = [
            "dataset_build",
            "training_sft",
            "training_dpo",
            "evaluation",
            "offline_embeddings",
            "analytics",
            "canary",
            "promotion",
        ]
        status: dict[str, Any] = {}
        for queue in queues:
            pending = await client.llen(f"queue:{queue}")
            dlq = await client.llen(f"{settings.QUEUE_DEAD_LETTER_PREFIX}:{queue}")
            status[queue] = {
                "pending": pending,
                "dead_letter": dlq,
            }
        return status

    async def mark_failed(self, queue_name: str, job: dict[str, Any], error: str) -> None:
        await self.redis.connect()
        client = self.redis._client

        retries = int(job.get("retries") or 0) + 1
        job["retries"] = retries
        job["last_error"] = error[:1000]
        job["failed_at"] = datetime.now(timezone.utc).isoformat()

        if retries > int(job.get("max_retries") or settings.QUEUE_MAX_RETRIES):
            await client.rpush(
                f"{settings.QUEUE_DEAD_LETTER_PREFIX}:{queue_name}",
                json.dumps(job),
            )
            return

        await client.rpush(f"queue:{queue_name}", json.dumps(job))
