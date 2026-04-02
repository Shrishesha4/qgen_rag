"""Redis-backed distributed queue for background generation."""

import json
import uuid
from datetime import datetime, timezone
from typing import Optional, Any

from app.core.config import settings
from app.services.redis_service import RedisService


class RedisQueueService:
    """Distributed queue for background generation using Redis Streams."""

    STREAM_KEY = "generation:queue"
    STATUS_HASH = "generation:status"
    RUNNING_HASH = "generation:running"
    CONSUMER_GROUP = "generation_workers"

    def __init__(self):
        self._client: Optional[Any] = None
        self._redis_service = RedisService()

    async def connect(self):
        if self._client is None:
            await self._redis_service.connect()
            self._client = self._redis_service._client
            await self._ensure_consumer_group()

    async def _ensure_consumer_group(self):
        try:
            await self._client.xgroup_create(
                self.STREAM_KEY,
                self.CONSUMER_GROUP,
                id="0",
                mkstream=True,
            )
        except Exception as exc:
            # Group already exists.
            if "BUSYGROUP" not in str(exc):
                raise

    def _status_ttl_key(self, task_key: str) -> str:
        return f"generation:status:ttl:{task_key}"

    def _running_ttl_key(self, task_key: str) -> str:
        return f"generation:running:ttl:{task_key}"

    async def add_to_queue(self, user_id: str, subject_id: str, request_data: dict[str, Any], count: int) -> str:
        await self.connect()
        payload = {
            "user_id": str(user_id),
            "subject_id": str(subject_id),
            "count": str(count),
            "request_data": json.dumps(request_data),
            "added_at": datetime.now(timezone.utc).isoformat(),
            "run_id": request_data.get("run_id") or str(uuid.uuid4()),
            "retry_count": str(request_data.get("retry_count", 0)),
            "task_key": request_data.get("task_key", f"{user_id}:{subject_id}"),
        }
        return await self._client.xadd(self.STREAM_KEY, payload)

    async def claim_next_item(self, consumer_id: str, block_ms: int = 5000) -> Optional[dict[str, Any]]:
        await self.connect()
        results = await self._client.xreadgroup(
            groupname=self.CONSUMER_GROUP,
            consumername=consumer_id,
            streams={self.STREAM_KEY: ">"},
            count=1,
            block=block_ms,
        )
        if not results:
            return None

        _, messages = results[0]
        if not messages:
            return None

        message_id, fields = messages[0]
        request_data_raw = fields.get("request_data", "{}")

        return {
            "message_id": message_id,
            "user_id": fields.get("user_id"),
            "subject_id": fields.get("subject_id"),
            "count": int(fields.get("count", "0")),
            "request_data": json.loads(request_data_raw),
            "added_at": fields.get("added_at"),
            "run_id": fields.get("run_id"),
            "retry_count": int(fields.get("retry_count", "0")),
            "task_key": fields.get("task_key"),
        }

    async def ack_item(self, message_id: str):
        await self.connect()
        await self._client.xack(self.STREAM_KEY, self.CONSUMER_GROUP, message_id)

    async def get_queue_position(self, user_id: str, subject_id: str) -> int:
        await self.connect()
        target_task_key = f"{user_id}:{subject_id}"
        position = 0
        cursor = "-"

        while True:
            entries = await self._client.xrange(self.STREAM_KEY, min=cursor, max="+", count=200)
            if not entries:
                return 0

            for message_id, fields in entries:
                if cursor != "-" and message_id == cursor:
                    continue
                position += 1
                if fields.get("task_key") == target_task_key:
                    return position
                cursor = message_id

            if len(entries) < 200:
                return 0

    async def update_status(self, task_key: str, status: dict[str, Any]):
        await self.connect()
        await self._client.hset(self.STATUS_HASH, task_key, json.dumps(status))
        await self._client.setex(
            self._status_ttl_key(task_key),
            settings.REDIS_QUEUE_STATUS_TTL_SECONDS,
            "1",
        )

    async def get_status(self, task_key: str) -> Optional[dict[str, Any]]:
        await self.connect()
        if not await self._client.exists(self._status_ttl_key(task_key)):
            await self._client.hdel(self.STATUS_HASH, task_key)
            return None

        raw = await self._client.hget(self.STATUS_HASH, task_key)
        if not raw:
            return None
        return json.loads(raw)

    async def delete_status(self, task_key: str):
        await self.connect()
        await self._client.hdel(self.STATUS_HASH, task_key)
        await self._client.delete(self._status_ttl_key(task_key))

    async def get_running_count(self) -> int:
        await self.connect()
        keys = await self._client.hkeys(self.RUNNING_HASH)
        if not keys:
            return 0

        active_count = 0
        for task_key in keys:
            if await self._client.exists(self._running_ttl_key(task_key)):
                active_count += 1
            else:
                await self._client.hdel(self.RUNNING_HASH, task_key)
        return active_count

    async def register_running(self, task_key: str, run_data: dict[str, Any]):
        await self.connect()
        await self._client.hset(self.RUNNING_HASH, task_key, json.dumps(run_data))
        await self._client.setex(
            self._running_ttl_key(task_key),
            settings.REDIS_QUEUE_RUNNING_TTL_SECONDS,
            "1",
        )

    async def refresh_running(self, task_key: str):
        await self.connect()
        await self._client.expire(
            self._running_ttl_key(task_key),
            settings.REDIS_QUEUE_RUNNING_TTL_SECONDS,
        )

    async def unregister_running(self, task_key: str):
        await self.connect()
        await self._client.hdel(self.RUNNING_HASH, task_key)
        await self._client.delete(self._running_ttl_key(task_key))
