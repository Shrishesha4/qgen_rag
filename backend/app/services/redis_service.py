"""
Redis service for caching, sessions, and rate limiting.
"""

from typing import Optional, Any, List, Set
import json
import redis.asyncio as redis
from redis.exceptions import ConnectionError, TimeoutError
from datetime import timedelta
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


class RedisService:
    """Service for Redis operations."""

    _instance: Optional["RedisService"] = None
    _client: Optional[redis.Redis] = None

    def __new__(cls):
        """Singleton pattern for Redis connection reuse."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def connect(self):
        """Connect to Redis."""
        if self._client is None:
            self._client = redis.from_url(settings.REDIS_URL, decode_responses=True)

    async def disconnect(self):
        """Disconnect from Redis."""
        if self._client:
            await self._client.close()
            self._client = None

    async def get(self, key: str) -> Optional[str]:
        """Get a value by key."""
        await self.connect()
        return await self._client.get(key)

    async def set(
        self,
        key: str,
        value: str,
        expire: Optional[int] = None,
    ) -> bool:
        """Set a value with optional expiration (seconds)."""
        await self.connect()
        return await self._client.set(key, value, ex=expire)

    async def delete(self, key: str) -> bool:
        """Delete a key."""
        await self.connect()
        return await self._client.delete(key) > 0

    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        await self.connect()
        return await self._client.exists(key) > 0

    # Token blacklist operations
    async def blacklist_token(self, jti: str, expires_in: int):
        """Add a token JTI to the blacklist."""
        key = f"token:blacklist:{jti}"
        await self.set(key, "revoked", expire=expires_in)

    async def is_token_blacklisted(self, jti: str) -> bool:
        """Check if a token JTI is blacklisted."""
        key = f"token:blacklist:{jti}"
        try:
            return await self.exists(key)
        except (ConnectionError, TimeoutError, OSError) as e:
            logger.warning(f"Redis unavailable for blacklist check: {e}. Allowing token.")
            return False

    # Rate limiting operations
    async def check_rate_limit(
        self,
        identifier: str,
        endpoint: str,
        limit: int,
        window_seconds: int,
    ) -> tuple[bool, int]:
        """
        Check rate limit for identifier + endpoint.
        Returns (is_allowed, remaining_requests).
        """
        try:
            await self.connect()
            key = f"ratelimit:{identifier}:{endpoint}"
            
            current = await self._client.get(key)
            if current is None:
                await self._client.setex(key, window_seconds, 1)
                return True, limit - 1
            
            count = int(current)
            if count >= limit:
                return False, 0
            
            await self._client.incr(key)
            return True, limit - count - 1
        except (ConnectionError, TimeoutError, OSError) as e:
            logger.warning(f"Redis unavailable for rate limiting: {e}. Allowing request.")
            return True, limit

    async def increment_rate_limit(
        self,
        identifier: str,
        endpoint: str,
        window_seconds: int,
    ) -> int:
        """Increment rate limit counter and return new count."""
        await self.connect()
        key = f"ratelimit:{identifier}:{endpoint}"
        
        pipe = self._client.pipeline()
        pipe.incr(key)
        pipe.expire(key, window_seconds)
        results = await pipe.execute()
        return results[0]

    # Failed login tracking
    async def increment_failed_login(self, email: str) -> int:
        """Increment failed login counter."""
        await self.connect()
        key = f"failed_logins:{email}"
        
        pipe = self._client.pipeline()
        pipe.incr(key)
        pipe.expire(key, 900)  # 15 minutes
        results = await pipe.execute()
        return results[0]

    async def get_failed_login_count(self, email: str) -> int:
        """Get failed login count."""
        await self.connect()
        key = f"failed_logins:{email}"
        count = await self._client.get(key)
        return int(count) if count else 0

    async def reset_failed_logins(self, email: str):
        """Reset failed login counter."""
        await self.connect()
        key = f"failed_logins:{email}"
        await self._client.delete(key)

    # Generation lock
    async def acquire_generation_lock(
        self,
        user_id: str,
        document_id: str,
        timeout: int = 300,
    ) -> bool:
        """Acquire lock for question generation."""
        await self.connect()
        key = f"lock:generation:{user_id}:{document_id}"
        # Check if lock exists (it might be stale from crashed process)
        existing = await self._client.get(key)
        if existing:
            # Lock exists, get its TTL
            ttl = await self._client.ttl(key)
            # If TTL is -1 (no expire) or very old, it's stale - clean it
            if ttl == -1:
                await self._client.delete(key)
                # Try to acquire again
                return await self._client.set(key, "locked", ex=timeout, nx=True)
            return False
        return await self._client.set(key, "locked", ex=timeout, nx=True)

    async def release_generation_lock(self, user_id: str, document_id: str):
        """Release generation lock."""
        await self.connect()
        key = f"lock:generation:{user_id}:{document_id}"
        await self._client.delete(key)

    async def is_generation_locked(self, user_id: str, document_id: str) -> bool:
        """Check if generation is currently locked for this document."""
        await self.connect()
        key = f"lock:generation:{user_id}:{document_id}"
        return await self.exists(key)

    # Recent questions cache
    async def add_recent_question(
        self,
        user_id: str,
        document_id: str,
        question_id: str,
        score: float,
    ):
        """Add question to recent questions sorted set."""
        await self.connect()
        key = f"recent_questions:{user_id}:{document_id}"
        await self._client.zadd(key, {question_id: score})
        await self._client.expire(key, 86400)  # 24 hours

    async def get_recent_questions(
        self,
        user_id: str,
        document_id: str,
        limit: int = 100,
    ) -> List[str]:
        """Get recent question IDs."""
        await self.connect()
        key = f"recent_questions:{user_id}:{document_id}"
        return await self._client.zrange(key, 0, limit - 1)

    # User preferences cache
    async def cache_user_preferences(
        self,
        user_id: str,
        preferences: dict,
        expire: int = 3600,
    ):
        """Cache user preferences."""
        await self.connect()
        key = f"user:preferences:{user_id}"
        await self._client.hset(key, mapping=preferences)
        await self._client.expire(key, expire)

    async def get_user_preferences(self, user_id: str) -> Optional[dict]:
        """Get cached user preferences."""
        await self.connect()
        key = f"user:preferences:{user_id}"
        prefs = await self._client.hgetall(key)
        return prefs if prefs else None

    # Session tracking
    async def add_user_session(self, user_id: str, session_id: str):
        """Add session to user's active sessions."""
        await self.connect()
        key = f"session:user:{user_id}"
        await self._client.sadd(key, session_id)

    async def remove_user_session(self, user_id: str, session_id: str):
        """Remove session from user's active sessions."""
        await self.connect()
        key = f"session:user:{user_id}"
        await self._client.srem(key, session_id)

    async def get_user_sessions(self, user_id: str) -> Set[str]:
        """Get all active session IDs for user."""
        await self.connect()
        key = f"session:user:{user_id}"
        return await self._client.smembers(key)

    # ========== Embedding Cache Operations ==========
    
    async def cache_embedding(
        self,
        cache_key: str,
        embedding: List[float],
        ttl: int = 86400 * 7,  # 7 days default
    ) -> bool:
        """
        Cache an embedding vector in Redis.
        
        Args:
            cache_key: Unique key for this embedding (e.g., hash of text + model)
            embedding: The embedding vector
            ttl: Time-to-live in seconds (default 7 days)
        
        Returns:
            True if cached successfully
        """
        await self.connect()
        key = f"embedding:{cache_key}"
        # Store as JSON string - compact representation
        value = json.dumps(embedding)
        return await self._client.set(key, value, ex=ttl)

    async def get_cached_embedding(self, cache_key: str) -> Optional[List[float]]:
        """
        Retrieve a cached embedding from Redis.
        
        Args:
            cache_key: The cache key used when storing
        
        Returns:
            The embedding vector or None if not found
        """
        await self.connect()
        key = f"embedding:{cache_key}"
        value = await self._client.get(key)
        if value:
            return json.loads(value)
        return None

    async def cache_embeddings_batch(
        self,
        embeddings: dict[str, List[float]],
        ttl: int = 86400 * 7,
    ) -> int:
        """
        Cache multiple embeddings in a single operation.
        
        Args:
            embeddings: Dict mapping cache_key -> embedding vector
            ttl: Time-to-live in seconds
        
        Returns:
            Number of embeddings cached
        """
        if not embeddings:
            return 0
        
        await self.connect()
        pipe = self._client.pipeline()
        
        for cache_key, embedding in embeddings.items():
            key = f"embedding:{cache_key}"
            value = json.dumps(embedding)
            pipe.set(key, value, ex=ttl)
        
        results = await pipe.execute()
        return sum(1 for r in results if r)

    async def get_cached_embeddings_batch(
        self,
        cache_keys: List[str],
    ) -> dict[str, Optional[List[float]]]:
        """
        Retrieve multiple cached embeddings in a single operation.
        
        Args:
            cache_keys: List of cache keys to retrieve
        
        Returns:
            Dict mapping cache_key -> embedding (or None if not found)
        """
        if not cache_keys:
            return {}
        
        await self.connect()
        pipe = self._client.pipeline()
        
        for cache_key in cache_keys:
            key = f"embedding:{cache_key}"
            pipe.get(key)
        
        results = await pipe.execute()
        
        return {
            cache_key: json.loads(value) if value else None
            for cache_key, value in zip(cache_keys, results)
        }

    async def get_embedding_cache_stats(self) -> dict:
        """Get statistics about the embedding cache."""
        await self.connect()
        
        # Count embedding keys
        cursor = 0
        count = 0
        total_size = 0
        
        while True:
            cursor, keys = await self._client.scan(cursor, match="embedding:*", count=1000)
            count += len(keys)
            cursor = int(cursor)
            if cursor == 0:
                break
        
        return {
            "cached_embeddings": count,
            "cache_type": "redis",
        }

    async def clear_embedding_cache(self) -> int:
        """
        Clear all cached embeddings from Redis.
        
        Returns:
            Number of embeddings cleared
        """
        await self.connect()
        
        cursor = 0
        deleted = 0
        
        while True:
            cursor, keys = await self._client.scan(cursor, match="embedding:*", count=1000)
            if keys:
                deleted += await self._client.delete(*keys)
            cursor = int(cursor)
            if cursor == 0:
                break
        
        return deleted
