"""Worker pool runner for asynchronous pipeline jobs.

Run separate worker processes per queue for isolation, e.g.:
- CPU/API-adjacent: dataset_build, evaluation, analytics
- GPU-bound: training_sft, training_dpo
"""

from __future__ import annotations

import asyncio
import logging
import uuid

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
    elif queue_name in {"training_sft", "training_dpo"}:
        handler = _gpu_training_handler
    else:
        handler = _default_handler
    await worker_service.run_queue(queue_name=queue_name, handler=handler)


async def main() -> None:
    # Launch isolated worker loops. Deploy each loop in a separate process in production.
    await asyncio.gather(
        run_worker_pool("dataset_build"),
        run_worker_pool("training_sft"),
        run_worker_pool("training_dpo"),
        run_worker_pool("evaluation"),
        run_worker_pool("offline_embeddings"),
        run_worker_pool("analytics"),
        run_worker_pool("canary"),
        run_worker_pool("promotion"),
    )


if __name__ == "__main__":
    asyncio.run(main())
