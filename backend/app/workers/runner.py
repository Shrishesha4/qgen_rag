"""Worker pool runner for asynchronous pipeline jobs.

Run separate worker processes per queue for isolation, e.g.:
- CPU/API-adjacent: dataset_build, evaluation, analytics
- GPU-bound: training_sft, training_dpo
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.logging import request_id_ctx
from app.services.training_service import TrainingService
from app.services.worker_service import WorkerService


logger = logging.getLogger(__name__)
worker_service = WorkerService()
training_service = TrainingService()


async def _default_handler(job: dict) -> None:
    """Fallback handler for queues not yet mapped to concrete execution."""
    logger.info(
        "Worker consumed job queue=%s type=%s trace_id=%s payload_keys=%s",
        job.get("queue"),
        job.get("job_type"),
        job.get("trace_id"),
        sorted((job.get("payload") or {}).keys()),
    )


async def _dataset_build_handler(job: dict) -> None:
    payload = job.get("payload") or {}
    dataset_id = payload.get("dataset_id")
    if not dataset_id:
        raise ValueError("dataset_id missing for dataset build job")

    if job.get("trace_id"):
        request_id_ctx.set(job["trace_id"])

    async with AsyncSessionLocal() as db:
        result = await training_service.process_dataset_build_job(
            dataset_id=uuid.UUID(str(dataset_id)),
            db=db,
        )
        logger.info("Dataset build worker result=%s", result)


async def _evaluation_handler(job: dict) -> None:
    payload = job.get("payload") or {}
    evaluation_id = payload.get("evaluation_id")
    if not evaluation_id:
        raise ValueError("evaluation_id missing for evaluation job")

    if job.get("trace_id"):
        request_id_ctx.set(job["trace_id"])

    async with AsyncSessionLocal() as db:
        result = await training_service.process_evaluation_job(
            evaluation_id=uuid.UUID(str(evaluation_id)),
            db=db,
        )
        logger.info("Evaluation worker result=%s", result)


async def _gpu_training_handler(job: dict) -> None:
    payload = job.get("payload") or {}
    job_id = payload.get("job_id")
    if not job_id:
        raise ValueError("job_id missing for GPU training job")

    if job.get("trace_id"):
        request_id_ctx.set(job["trace_id"])

    async with AsyncSessionLocal() as db:
        result = await training_service.run_training_job(
            job_id=uuid.UUID(str(job_id)),
            db=db,
        )
        logger.info("GPU training worker result=%s", result)


async def run_worker_pool(queue_name: str) -> None:
    if queue_name == "dataset_build":
        handler = _dataset_build_handler
    elif queue_name == "evaluation":
        handler = _evaluation_handler
    elif queue_name == "training":
        handler = _gpu_training_handler
    else:
        handler = _default_handler
    await worker_service.run_queue(queue_name=queue_name, handler=handler)


async def _auto_training_scheduler() -> None:
    """Trigger one fine-tuning job daily at configured local time."""
    from sqlalchemy import select, func
    from app.models.training import TrainingJob, VettingLog, TrainingPair

    timezone = ZoneInfo(settings.AUTO_TRAINING_TIMEZONE)
    logger.info(
        "✅ Auto-training scheduler enabled: %02d:%02d %s method=%s",
        settings.AUTO_TRAINING_HOUR,
        settings.AUTO_TRAINING_MINUTE,
        settings.AUTO_TRAINING_TIMEZONE,
        settings.AUTO_TRAINING_METHOD,
    )

    while True:
        now_local = datetime.now(timezone)
        next_run = now_local.replace(
            hour=settings.AUTO_TRAINING_HOUR,
            minute=settings.AUTO_TRAINING_MINUTE,
            second=0,
            microsecond=0,
        )
        if now_local >= next_run:
            next_run = next_run + timedelta(days=1)

        sleep_seconds = max(1.0, (next_run - now_local).total_seconds())
        logger.debug(
            "Auto-training scheduler sleeping for %.0f seconds, next run at %s",
            sleep_seconds,
            next_run.strftime("%Y-%m-%d %H:%M:%S %Z"),
        )
        await asyncio.sleep(sleep_seconds)

        run_date = datetime.now(timezone).strftime("%Y-%m-%d")
        idempotency_key = f"auto-training:{run_date}:{settings.AUTO_TRAINING_METHOD}"
        run_time = datetime.now(timezone).strftime("%H:%M:%S %Z")

        try:
            async with AsyncSessionLocal() as db:
                logger.info("⏱️ Auto-training trigger starting at %s", run_time)

                # Check if training job already running today (avoid conflicts)
                running_today = await db.execute(
                    select(func.count(TrainingJob.id)).where(
                        TrainingJob.triggered_by == "system:auto-scheduler",
                        TrainingJob.status.in_(["pending", "running"]),
                        TrainingJob.created_at >= datetime.now(timezone).replace(
                            hour=0, minute=0, second=0, microsecond=0
                        ),
                    )
                )
                pending_count = running_today.scalar() or 0
                if pending_count > 0:
                    logger.info(
                        "⏭️ Skip auto-training: %d job(s) already pending/running today",
                        pending_count,
                    )
                    continue

                # Check data availability
                vetting_count = await db.execute(
                    select(func.count(VettingLog.id)).where(
                        VettingLog.action == "approve"
                    )
                )
                approved_q = vetting_count.scalar() or 0

                dpo_count = await db.execute(
                    select(func.count(TrainingPair.id)).where(
                        TrainingPair.status.in_(["pending", "queued"])
                    )
                )
                pending_pairs = dpo_count.scalar() or 0

                logger.info(
                    "📊 Data check: %d approved questions, %d pending DPO pairs",
                    approved_q,
                    pending_pairs,
                )

                if approved_q == 0 and pending_pairs == 0:
                    logger.info(
                        "⚠️ Skip auto-training: no approved questions or DPO pairs (need vetting activity)"
                    )
                    continue

                logger.info(
                    "🚀 Triggering auto-training with idempotency_key=%s method=%s",
                    idempotency_key,
                    settings.AUTO_TRAINING_METHOD,
                )
                result = await training_service.trigger_training(
                    db=db,
                    triggered_by="system:auto-scheduler",
                    training_method=settings.AUTO_TRAINING_METHOD,
                    idempotency_key=idempotency_key,
                )
                logger.info("✅ Auto-training triggered result=%s", result)
        except Exception as exc:
            logger.exception("❌ Auto-training trigger failed error=%s", exc)
            await asyncio.sleep(60)


async def main() -> None:
    # Launch isolated worker loops. Deploy each loop in a separate process in production.
    tasks = [
        run_worker_pool("dataset_build"),
        run_worker_pool("training"),
        run_worker_pool("evaluation"),
        run_worker_pool("offline_embeddings"),
        run_worker_pool("analytics"),
        run_worker_pool("canary"),
        run_worker_pool("promotion"),
    ]
    if settings.AUTO_TRAINING_ENABLED:
        tasks.append(_auto_training_scheduler())

    await asyncio.gather(*tasks)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Worker interrupted, shutting down gracefully")
