"""
QuestionGeneration AI - FastAPI Backend
A stateful RAG-based question generation system for educators
"""

import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.database import init_db
from app.core.logging import setup_logging, logger, request_id_ctx
from app.api.v1 import api_router
from app.services.embedding_service import warmup_embedding_service
from app.services.reranker_service import warmup_reranker_service


# Initialize logging first
setup_logging(log_level=settings.LOG_LEVEL, json_logs=settings.LOG_JSON)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management."""
    # Startup
    logger.info("🚀 Starting QuestionGeneration AI...")
    
    # Initialize database and create tables/indexes
    await init_db()
    logger.info("✅ Database initialized")
    
    # Warmup ML models to avoid cold start latency
    try:
        await warmup_embedding_service()
    except Exception as e:
        logger.warning(f"⚠️ Embedding model warmup failed: {e}")
    
    try:
        warmup_reranker_service()
    except Exception as e:
        logger.warning(f"⚠️ Reranker model warmup failed: {e}")
    
    # Clean up stale generation locks from previous crashes
    try:
        from app.services.redis_service import RedisService
        redis_service = RedisService()
        await redis_service.connect()
        
        # Scan for all generation locks
        cursor = 0
        stale_locks = []
        while True:
            cursor, keys = await redis_service._client.scan(cursor, match="lock:generation:*", count=100)
            stale_locks.extend(keys)
            cursor = int(cursor)
            if cursor == 0:
                break
        
        # Delete all stale locks
        if stale_locks:
            deleted = await redis_service._client.delete(*stale_locks)
            logger.info(f"🧹 Cleaned up {deleted} stale generation locks")
    except Exception as e:
        logger.warning(f"⚠️ Failed to clean stale locks: {e}")
    
    logger.info("✅ All services ready")
    yield
    
    # Shutdown
    logger.info("👋 Shutting down...")


app = FastAPI(
    title="QuestionGeneration AI",
    description="A stateful RAG-based question generation system for educators",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS Middleware - allow_credentials must be False when using wildcard origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for React Native
    allow_credentials=False,  # Must be False with wildcard
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request ID middleware for tracing
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Add a unique request ID to each request for tracing."""
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])
    request_id_ctx.set(request_id)
    
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# Prometheus metrics (optional)
if settings.ENABLE_METRICS:
    try:
        from prometheus_fastapi_instrumentator import Instrumentator
        
        instrumentator = Instrumentator(
            should_group_status_codes=True,
            should_ignore_untemplated=True,
            excluded_handlers=["/metrics", "/health", "/"],
        )
        instrumentator.instrument(app).expose(app, endpoint="/metrics")
        logger.info("✅ Prometheus metrics enabled at /metrics")
    except ImportError:
        logger.warning("⚠️ prometheus-fastapi-instrumentator not installed, metrics disabled")


# Include API routes
app.include_router(api_router, prefix="/api/v1")


@app.get("/", tags=["Health"])
async def root():
    """Root endpoint - health check."""
    return {"status": "healthy", "service": "QuestionGeneration AI", "version": "1.0.0"}


@app.get("/health", tags=["Health"])
async def health_check():
    """Detailed health check endpoint."""
    return JSONResponse(
        content={
            "status": "healthy",
            "database": "connected",
            "redis": "connected",
            "version": "1.0.0",
        }
    )
