"""Worker pool runner for asynchronous pipeline jobs.

Run separate worker processes per queue for isolation, e.g.:
- CPU/API-adjacent: dataset_build, evaluation, analytics
- GPU-bound: training_sft, training_dpo
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime

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
    """Poll adaptive training policy and trigger jobs only when justified."""
    from sqlalchemy import select, func
    from app.models.training import TrainingJob

    logger.info(
        "✅ Auto-training scheduler enabled: poll=%d min min_interval=%d h",
        settings.AUTO_TRAINING_POLL_MINUTES,
        settings.AUTO_TRAINING_MIN_INTERVAL_HOURS,
    )

    while True:
        try:
            async with AsyncSessionLocal() as db:
                running_jobs = await db.execute(
                    select(func.count(TrainingJob.id)).where(
                        TrainingJob.status.in_(["pending", "preparing", "running"]),
                    )
                )
                pending_count = running_jobs.scalar() or 0
                if pending_count > 0:
                    logger.info(
                        "⏭️ Skip auto-training: %d job(s) already pending or running",
                        pending_count,
                    )
                else:
                    decision = await training_service.evaluate_auto_training_policy(
                        db,
                        created_by="system:auto-scheduler",
                    )
                    if not decision.get("should_train"):
                        logger.info(
                            "⏭️ Skip auto-training: %s",
                            decision.get("reason", "policy conditions not met"),
                        )
                    else:
                        time_bucket = datetime.utcnow().strftime("%Y%m%d%H")
                        idempotency_key = f"auto-policy:{decision['training_method']}:{time_bucket}"
                        logger.info(
                            "🚀 Triggering policy-based auto-training method=%s idempotency_key=%s",
                            decision["training_method"],
                            idempotency_key,
                        )
                        result = await training_service.trigger_training(
                            db=db,
                            triggered_by="system:auto-scheduler",
                            training_method=decision["training_method"],
                            idempotency_key=idempotency_key,
                            policy_snapshot=decision,
                        )
                        logger.info("✅ Auto-training triggered result=%s", result)
        except Exception as exc:
            logger.exception("❌ Auto-training trigger failed error=%s", exc)
        await asyncio.sleep(max(300, int(settings.AUTO_TRAINING_POLL_MINUTES) * 60))


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
