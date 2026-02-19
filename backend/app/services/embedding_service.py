"""
Embedding service for generating text embeddings.

Supports multiple embedding models including:
- all-MiniLM-L6-v2 (fast, good quality)
- all-mpnet-base-v2 (better quality)
- BAAI/bge-base-en-v1.5 (best for Q&A, requires instruction prefix)

Features:
- Two-tier caching: In-memory LRU cache + optional Redis persistence
- Instruction-based embedding support for BGE models
- Batch embedding with parallel processing
"""

import hashlib
from typing import List, Optional, Dict
from collections import OrderedDict
from sentence_transformers import SentenceTransformer
import numpy as np

import logging
from app.core.config import settings

logger = logging.getLogger(__name__)


class LRUCache:
    """Simple LRU cache for embeddings."""
    
    def __init__(self, max_size: int = 10000):
        self.max_size = max_size
        self._cache: OrderedDict[str, List[float]] = OrderedDict()
        self._hits = 0
        self._misses = 0
    
    def get(self, key: str) -> Optional[List[float]]:
        """Get value from cache, moving it to the end (most recently used)."""
        if key in self._cache:
            self._cache.move_to_end(key)
            self._hits += 1
            return self._cache[key]
        self._misses += 1
        return None
    
    def put(self, key: str, value: List[float]) -> None:
        """Put value in cache, evicting oldest if necessary."""
        if key in self._cache:
            self._cache.move_to_end(key)
        else:
            if len(self._cache) >= self.max_size:
                self._cache.popitem(last=False)  # Remove oldest
            self._cache[key] = value
    
    def clear(self) -> None:
        """Clear the cache."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0
    
    def __len__(self) -> int:
        return len(self._cache)
    
    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0


class EmbeddingService:
    """
    Service for generating text embeddings using sentence-transformers.
    
    Supports two-tier caching:
    1. In-memory LRU cache for fast access to hot embeddings
    2. Optional Redis cache for persistence across restarts
    """

    _instance: Optional["EmbeddingService"] = None
    _model: Optional[SentenceTransformer] = None
    _cache: Optional[LRUCache] = None
    _redis_service = None

    def __new__(cls):
        """Singleton pattern for model reuse."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._model is None:
            self._model = SentenceTransformer(settings.EMBEDDING_MODEL)
            self._use_instruction = settings.EMBEDDING_USE_INSTRUCTION
            self._query_instruction = settings.EMBEDDING_QUERY_INSTRUCTION
            self._doc_instruction = settings.EMBEDDING_DOCUMENT_INSTRUCTION
            self._cache = LRUCache(max_size=10000)
            self._cache_enabled = True
            self._redis_cache_enabled = getattr(settings, 'EMBEDDING_REDIS_CACHE', False)
            self._redis_cache_ttl = getattr(settings, 'EMBEDDING_CACHE_TTL', 86400 * 7)  # 7 days

    def _get_redis_service(self):
        """Lazy import of Redis service to avoid circular imports."""
        if self._redis_service is None:
            from app.services.redis_service import RedisService
            self._redis_service = RedisService()
        return self._redis_service

    def _prepare_text(self, text: str, is_query: bool = True) -> str:
        """Prepare text with instruction prefix if enabled."""
        if not self._use_instruction:
            return text
        
        instruction = self._query_instruction if is_query else self._doc_instruction
        if instruction:
            return f"{instruction} {text}"
        return text

    def _get_cache_key(self, text: str, is_query: bool) -> str:
        """Generate a cache key for the text."""
        # Include model name and query flag in key to avoid collisions
        key_str = f"{settings.EMBEDDING_MODEL}:{is_query}:{text}"
        return hashlib.md5(key_str.encode()).hexdigest()

    async def get_embedding(self, text: str, is_query: bool = True) -> List[float]:
        """
        Generate embedding for a single text with two-tier caching.
        
        Cache lookup order:
        1. In-memory LRU cache (fastest)
        2. Redis cache (if enabled)
        3. Generate new embedding
        
        Args:
            text: Text to embed
            is_query: If True, use query instruction (for search queries).
                     If False, use document instruction (for documents/chunks).
        """
        cache_key = self._get_cache_key(text, is_query)
        
        # Check in-memory cache first
        if self._cache_enabled:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached
        
        # Check Redis cache (L2 cache)
        if self._redis_cache_enabled:
            try:
                redis_service = self._get_redis_service()
                cached = await redis_service.get_cached_embedding(cache_key)
                if cached is not None:
                    # Populate L1 cache from L2
                    if self._cache_enabled:
                        self._cache.put(cache_key, cached)
                    return cached
            except Exception:
                # Redis errors shouldn't break embedding generation
                pass
        
        # Generate embedding
        prepared_text = self._prepare_text(text, is_query)
        embedding = self._model.encode(prepared_text, convert_to_numpy=True).tolist()
        
        # Cache the result in L1
        if self._cache_enabled:
            self._cache.put(cache_key, embedding)
        
        # Cache in Redis (L2) asynchronously
        if self._redis_cache_enabled:
            try:
                redis_service = self._get_redis_service()
                await redis_service.cache_embedding(
                    cache_key, 
                    embedding, 
                    ttl=self._redis_cache_ttl
                )
            except Exception:
                pass  # Non-critical, continue
        
        return embedding

    async def get_embeddings(
        self, 
        texts: List[str], 
        is_query: bool = False,
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts with partial caching.
        
        Args:
            texts: List of texts to embed
            is_query: If True, use query instruction. Usually False for batch
                     document embeddings.
        """
        if not texts:
            return []
        
        results: List[Optional[List[float]]] = [None] * len(texts)
        texts_to_encode: List[tuple[int, str]] = []  # (original_index, prepared_text)
        cache_keys: List[str] = []
        
        # Check L1 cache for each text
        for i, text in enumerate(texts):
            cache_key = self._get_cache_key(text, is_query)
            cache_keys.append(cache_key)
            
            if self._cache_enabled:
                cached = self._cache.get(cache_key)
                if cached is not None:
                    results[i] = cached
                    continue
            
            texts_to_encode.append((i, text))
        
        # If some texts not in L1, check L2 (Redis)
        if texts_to_encode and self._redis_cache_enabled:
            try:
                redis_service = self._get_redis_service()
                uncached_keys = [cache_keys[i] for i, _ in texts_to_encode]
                redis_results = await redis_service.get_cached_embeddings_batch(uncached_keys)
                
                new_texts_to_encode = []
                for (orig_idx, text), cache_key in zip(texts_to_encode, uncached_keys):
                    cached = redis_results.get(cache_key)
                    if cached is not None:
                        results[orig_idx] = cached
                        # Populate L1 from L2
                        if self._cache_enabled:
                            self._cache.put(cache_key, cached)
                    else:
                        new_texts_to_encode.append((orig_idx, text))
                
                texts_to_encode = new_texts_to_encode
            except Exception:
                pass  # Continue with current texts_to_encode
        
        # Encode remaining uncached texts in batch
        if texts_to_encode:
            indices = [i for i, _ in texts_to_encode]
            prepared_texts = [self._prepare_text(text, is_query) for _, text in texts_to_encode]
            new_embeddings = self._model.encode(
                prepared_texts, 
                convert_to_numpy=True
            ).tolist()
            
            # Fill in results and update caches
            redis_to_cache = {}
            for idx, (orig_idx, _) in enumerate(texts_to_encode):
                embedding = new_embeddings[idx]
                results[orig_idx] = embedding
                cache_key = cache_keys[orig_idx]
                
                if self._cache_enabled:
                    self._cache.put(cache_key, embedding)
                
                if self._redis_cache_enabled:
                    redis_to_cache[cache_key] = embedding
            
            # Batch update Redis cache
            if redis_to_cache:
                try:
                    redis_service = self._get_redis_service()
                    await redis_service.cache_embeddings_batch(
                        redis_to_cache, 
                        ttl=self._redis_cache_ttl
                    )
                except Exception:
                    pass
        
        return results

    async def get_document_embedding(self, text: str) -> List[float]:
        """Generate embedding for a document chunk (uses document instruction)."""
        return await self.get_embedding(text, is_query=False)

    async def get_query_embedding(self, text: str) -> List[float]:
        """Generate embedding for a search query (uses query instruction)."""
        return await self.get_embedding(text, is_query=True)

    def compute_similarity(
        self,
        embedding1: List[float],
        embedding2: List[float],
    ) -> float:
        """Compute cosine similarity between two embeddings."""
        a = np.array(embedding1)
        b = np.array(embedding2)
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

    def compute_similarity_batch(
        self,
        query_embedding: List[float],
        embeddings: List[List[float]],
    ) -> List[float]:
        """Compute cosine similarity between query and multiple embeddings."""
        if not embeddings:
            return []
            
        query = np.array(query_embedding)
        matrix = np.array(embeddings)
        
        # Normalize
        query_norm = query / np.linalg.norm(query)
        matrix_norms = matrix / np.linalg.norm(matrix, axis=1, keepdims=True)
        
        # Compute similarities
        similarities = np.dot(matrix_norms, query_norm)
        return similarities.tolist()

    def get_cache_stats(self) -> Dict[str, any]:
        """Get cache statistics for both L1 and L2 caches."""
        stats = {
            "l1_size": len(self._cache) if self._cache else 0,
            "l1_max_size": self._cache.max_size if self._cache else 0,
            "l1_hit_rate": round(self._cache.hit_rate * 100, 2) if self._cache else 0,
            "l1_enabled": self._cache_enabled,
            "l2_enabled": self._redis_cache_enabled,
            "l2_ttl_seconds": self._redis_cache_ttl,
        }
        return stats

    async def get_cache_stats_full(self) -> Dict[str, any]:
        """Get full cache statistics including Redis."""
        stats = self.get_cache_stats()
        
        if self._redis_cache_enabled:
            try:
                redis_service = self._get_redis_service()
                redis_stats = await redis_service.get_embedding_cache_stats()
                stats.update({
                    "l2_cached_embeddings": redis_stats.get("cached_embeddings", 0),
                })
            except Exception as e:
                stats["l2_error"] = str(e)
        
        return stats

    def clear_cache(self) -> None:
        """Clear the in-memory embedding cache."""
        if self._cache:
            self._cache.clear()

    async def clear_all_caches(self) -> Dict[str, int]:
        """Clear both L1 and L2 caches."""
        l1_cleared = len(self._cache) if self._cache else 0
        if self._cache:
            self._cache.clear()
        
        l2_cleared = 0
        if self._redis_cache_enabled:
            try:
                redis_service = self._get_redis_service()
                l2_cleared = await redis_service.clear_embedding_cache()
            except Exception:
                pass
        
        return {"l1_cleared": l1_cleared, "l2_cleared": l2_cleared}

    def set_cache_enabled(self, enabled: bool) -> None:
        """Enable or disable in-memory caching."""
        self._cache_enabled = enabled

    def set_redis_cache_enabled(self, enabled: bool) -> None:
        """Enable or disable Redis caching."""
        self._redis_cache_enabled = enabled

    async def warmup(self) -> None:
        """
        Warmup the model by running a dummy inference.
        
        This ensures the model is fully loaded and ready before the first
        real request, avoiding cold start latency for users.
        """
        dummy_text = "This is a warmup text for model initialization."
        _ = await self.get_embedding(dummy_text)
        logger.info(f"✅ Embedding model warmed up: {settings.EMBEDDING_MODEL}")


# Module-level function for easy import
async def warmup_embedding_service() -> None:
    """Warmup the embedding service singleton."""
    service = EmbeddingService()
    await service.warmup()
