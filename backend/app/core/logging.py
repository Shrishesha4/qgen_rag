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
        frame, depth = sys._getframe(6), 6
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def format_record(record: Dict[str, Any]) -> str:
    """
    Custom format function for console output.
    Includes request_id if available.
    """
    request_id = request_id_ctx.get()
    request_id_str = f"[{request_id}] " if request_id else ""
    
    # Color-coded log format
    return (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        f"<cyan>{request_id_str}</cyan>"
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>\n"
        "{exception}"
    )


def json_format(record: Dict[str, Any]) -> str:
    """
    JSON format for production logging (structured logs).
    Easy to parse by log aggregation tools (ELK, Datadog, etc.)
    """
    import json
    
    request_id = request_id_ctx.get()
    
    log_record = {
        "timestamp": datetime.utcnow().isoformat(),
        "level": record["level"].name,
        "logger": record["name"],
        "message": record["message"],
        "module": record["module"],
        "function": record["function"],
        "line": record["line"],
    }
    
    if request_id:
        log_record["request_id"] = request_id
    
    # Include extra data if present
    if record.get("extra"):
        for key, value in record["extra"].items():
            if key not in ("request_id",):
                log_record[key] = value
    
    # Include exception info if present
    if record["exception"]:
        log_record["exception"] = {
            "type": record["exception"].type.__name__ if record["exception"].type else None,
            "value": str(record["exception"].value) if record["exception"].value else None,
            "traceback": record["exception"].traceback if record["exception"].traceback else None,
        }
    
    return json.dumps(log_record) + "\n"


def setup_logging(
    log_level: str = "INFO",
    json_logs: bool = False,
) -> None:
    """
    Configure application logging.
    
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
        logger.add(
            sys.stdout,
            format=json_format,
            level=level,
            colorize=False,
            serialize=False,
        )
    else:
        logger.add(
            sys.stdout,
            format=format_record,
            level=level,
            colorize=True,
        )
    
    # Intercept standard library logging
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
    
    # Set levels for noisy third-party loggers
    for logger_name in (
        "uvicorn",
        "uvicorn.error",
        "uvicorn.access",
        "sqlalchemy.engine",
        "httpx",
        "httpcore",
    ):
        logging.getLogger(logger_name).setLevel(logging.WARNING)
    
    logger.info(f"Logging configured: level={level}, json={use_json}")


def log_performance(operation_name: str):
    """
    Decorator to log performance timing for critical operations.
    
    Usage:
        @log_performance("generate_questions")
        async def generate_questions(...):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
                duration = time.perf_counter() - start_time
                logger.info(
                    f"{operation_name} completed",
                    operation=operation_name,
                    duration_ms=round(duration * 1000, 2),
                    status="success",
                )
                return result
            except Exception as e:
                duration = time.perf_counter() - start_time
                logger.error(
                    f"{operation_name} failed",
                    operation=operation_name,
                    duration_ms=round(duration * 1000, 2),
                    status="error",
                    error=str(e),
                )
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                duration = time.perf_counter() - start_time
                logger.info(
                    f"{operation_name} completed",
                    operation=operation_name,
                    duration_ms=round(duration * 1000, 2),
                    status="success",
                )
                return result
            except Exception as e:
                duration = time.perf_counter() - start_time
                logger.error(
                    f"{operation_name} failed",
                    operation=operation_name,
                    duration_ms=round(duration * 1000, 2),
                    status="error",
                    error=str(e),
                )
                raise
        
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


class LogContext:
    """
    Context manager for adding contextual information to logs.
    
    Usage:
        with LogContext(user_id="123", document_id="456"):
            logger.info("Processing document")  # Will include user_id and document_id
    """
    
    def __init__(self, **kwargs):
        self.extra = kwargs
        self.token = None
    
    def __enter__(self):
        self.token = logger.contextualize(**self.extra)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.token:
            self.token.__exit__(exc_type, exc_val, exc_tb)
        return False


# Export the configured logger for use throughout the application
__all__ = [
    "logger",
    "setup_logging",
    "log_performance",
    "LogContext",
    "request_id_ctx",
]
