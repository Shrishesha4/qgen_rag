"""
Structured logging configuration using loguru.

Features:
- JSON structured logging for production
- Colorized console output for development
- Request ID tracking for traceability
- Performance timing for critical operations
"""

import sys
import logging
from typing import Dict, Any
from contextvars import ContextVar
from datetime import datetime
from functools import wraps
import time

from fastapi import Request
from loguru import logger

from app.core.config import settings


# Context variable for request tracking
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")


class InterceptHandler(logging.Handler):
    """
    Intercept standard library logging and redirect to loguru.
    
    This ensures all logs (including from third-party libraries like SQLAlchemy)
    go through our structured logging pipeline.
    """
    
    def emit(self, record: logging.LogRecord) -> None:
        # Get corresponding Loguru level
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where the logged message originated
        # Use try-except because call stack may be shallow during shutdown
        try:
            frame, depth = sys._getframe(6), 6
            while frame and frame.f_code.co_filename == logging.__file__:
                frame = frame.f_back
                depth += 1
        except ValueError:
            # Call stack not deep enough (e.g., during shutdown)
            depth = 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def setup_logging(log_level: str = "INFO", json_logs: bool = False):
    """
    Configure loguru logging for the application.
    
    Args:
        log_level: Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_logs: If True, output JSON structured logs (for production)
    """
    # Remove default handler
    logger.remove()
    
    # Determine log level from settings or parameter
    level = getattr(settings, "LOG_LEVEL", log_level).upper()
    use_json = getattr(settings, "LOG_JSON", json_logs)
    
    # Add handler with appropriate format
    if use_json:
        # Simple JSON format with basic fields
        logger.add(
            sys.stdout,
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
            level=level,
            colorize=False,
            serialize=True,  # Let loguru handle JSON serialization
        )
    else:
        # Simple console format
        logger.add(
            sys.stdout,
            format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
            level=level,
            colorize=True,
        )
    
    # Intercept standard library logging
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
    
    # Set levels for noisy third-party loggers
    for logger_name in (
        "uvicorn",
        "uvicorn.access",
        "uvicorn.error",
        "sqlalchemy.engine",
        "sqlalchemy.pool",
        "httpx",
        "asyncpg",
    ):
        logging.getLogger(logger_name).setLevel(logging.WARNING)


def log_execution_time(func):
    """
    Decorator to log function execution time.
    
    Usage:
        @log_execution_time
        def my_function():
            pass
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            logger.info(f"⏱️ {func.__name__} completed in {execution_time:.2f}s")
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"❌ {func.__name__} failed after {execution_time:.2f}s: {e}")
            raise
    return wrapper


class LogContext:
    """
    Context manager for adding contextual information to logs.
    
    Usage:
        with LogContext(user_id="123", document_id="456"):
            logger.info("Processing document")
    """
    
    def __init__(self, **context):
        self.context = context
        self.bound_logger = None
    
    def __enter__(self):
        self.bound_logger = logger.bind(**self.context)
        return self.bound_logger
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


# Create a request ID middleware for FastAPI
def add_request_id(request: Request, call_next):
    """
    Middleware to add request ID to all logs for a request.
    """
    import uuid
    
    request_id = str(uuid.uuid4())
    request_id_ctx.set(request_id)
    
    # Add request ID to response headers
    response = call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# Export the configured logger
__all__ = [
    "logger",
    "setup_logging", 
    "log_execution_time",
    "LogContext",
    "add_request_id",
    "request_id_ctx",
]
