"""
Training Pipeline API endpoints.

Endpoints for monitoring and controlling the LLM fine-tuning pipeline:
  - GET  /status  — Pipeline status, active model, pending data counts
  - POST /trigger — Manually trigger a fine-tuning run (admin only)
  - GET  /versions — List all model versions
  - POST /versions/{id}/activate — Activate a specific model version
  - GET  /jobs — List training jobs
  - GET  /pairs — List DPO training pairs with pagination
"""

import uuid
from typing import Optional, List, Any
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.v1.deps import get_current_user, get_current_superuser
from app.models.user import User
from app.models.training import ModelVersion, TrainingJob, TrainingPair, VettingLog
from app.services.training_service import TrainingService


router = APIRouter()
training_service = TrainingService()


# ══════════════════════════════════════
# Schemas
# ══════════════════════════════════════

class TriggerTrainingRequest(BaseModel):
    """Request to trigger a fine-tuning run."""
    training_method: str = Field(
        default="sft", pattern="^(sft|dpo|sft\\+dpo)$",
        description="Training method: sft, dpo, or sft+dpo",
    )
    base_model: Optional[str] = Field(None, description="Override base model name")
    hyperparameters: Optional[dict] = Field(None, description="Custom hyperparameters")


class ModelVersionResponse(BaseModel):
    """Model version summary."""
    id: str
    version_tag: str
    base_model: str
    training_method: str
    sft_samples_count: int
    training_pairs_count: int
    is_active: bool
    status: str
    eval_metrics: Optional[dict]
    lora_adapter_path: Optional[str]
    created_at: Optional[str]
    training_completed_at: Optional[str]
    error_message: Optional[str]


class TrainingJobResponse(BaseModel):
    """Training job summary."""
    id: str
    model_version_id: str
    job_type: str
    status: str
    training_samples: int
    current_epoch: int
    total_epochs: int
    current_step: int
    total_steps: int
    current_loss: Optional[float]
    final_loss: Optional[float]
    eval_metrics: Optional[dict]
    created_at: Optional[str]
    started_at: Optional[str]
    completed_at: Optional[str]
    triggered_by: Optional[str]
    error_message: Optional[str]


class TrainingPairResponse(BaseModel):
    """DPO training pair summary."""
    id: str
    prompt: str
    chosen_response: str
    rejected_response: str
    pair_type: str
    status: str
    confidence: Optional[float]
    created_at: Optional[str]


class DatasetBuildRequest(BaseModel):
    snapshot_filter: Optional[dict[str, Any]] = None


class DatasetResponse(BaseModel):
    id: str
    dataset_tag: str
    created_at: Optional[str]
    created_by: Optional[str]
    snapshot_filter: Optional[dict]
    sample_counts: Optional[dict]
    manifest_path: Optional[str]
    checksum: Optional[str]


# ══════════════════════════════════════
# Endpoints
# ══════════════════════════════════════


@router.get("/status")
async def get_training_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get training pipeline status: active model, pending data, latest job.
    Accessible to any authenticated user.
    """
    return await training_service.get_training_status(db)


@router.post("/trigger")
async def trigger_training(
    request: TriggerTrainingRequest,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """
    Manually trigger a fine-tuning run. Admin only.
    """
    result = await training_service.trigger_training(
        db=db,
        triggered_by=current_user.id,
        base_model=request.base_model,
        training_method=request.training_method,
        hyperparameters=request.hyperparameters,
    )
    return result


@router.get("/versions", response_model=List[ModelVersionResponse])
async def list_model_versions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all model versions, newest first."""
    result = await db.execute(
        select(ModelVersion).order_by(ModelVersion.created_at.desc())
    )
    versions = result.scalars().all()

    return [
        ModelVersionResponse(
            id=str(v.id),
            version_tag=v.version_tag,
            base_model=v.base_model,
            training_method=v.training_method,
            sft_samples_count=v.sft_samples_count,
            training_pairs_count=v.training_pairs_count,
            is_active=v.is_active,
            status=v.status,
            eval_metrics=v.eval_metrics,
            lora_adapter_path=v.lora_adapter_path,
            created_at=v.created_at.isoformat() if v.created_at else None,
            training_completed_at=(
                v.training_completed_at.isoformat() if v.training_completed_at else None
            ),
            error_message=v.error_message,
        )
        for v in versions
    ]


@router.post("/versions/{version_id}/activate")
async def activate_model_version(
    version_id: uuid.UUID,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Activate a specific model version. Admin only."""
    return await training_service.activate_version(version_id, db)


@router.get("/jobs", response_model=List[TrainingJobResponse])
async def list_training_jobs(
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List training jobs, newest first."""
    result = await db.execute(
        select(TrainingJob)
        .order_by(TrainingJob.created_at.desc())
        .limit(limit)
    )
    jobs = result.scalars().all()

    return [
        TrainingJobResponse(
            id=str(j.id),
            model_version_id=str(j.model_version_id),
            job_type=j.job_type,
            status=j.status,
            training_samples=j.training_samples,
            current_epoch=j.current_epoch,
            total_epochs=j.total_epochs,
            current_step=j.current_step,
            total_steps=j.total_steps,
            current_loss=j.current_loss,
            final_loss=j.final_loss,
            eval_metrics=j.eval_metrics,
            created_at=j.created_at.isoformat() if j.created_at else None,
            started_at=j.started_at.isoformat() if j.started_at else None,
            completed_at=j.completed_at.isoformat() if j.completed_at else None,
            triggered_by=j.triggered_by,
            error_message=j.error_message,
        )
        for j in jobs
    ]


@router.get("/pairs", response_model=dict)
async def list_training_pairs(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    pair_type: Optional[str] = Query(None, pattern="^(edit|reject_approve|critique)$"),
    pair_status: Optional[str] = Query(None, pattern="^(pending|queued|used|skipped)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List DPO training pairs with pagination."""
    query = select(TrainingPair)

    if pair_type:
        query = query.where(TrainingPair.pair_type == pair_type)
    if pair_status:
        query = query.where(TrainingPair.status == pair_status)

    # Count
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    # Paginate
    offset = (page - 1) * limit
    query = query.order_by(TrainingPair.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    pairs = result.scalars().all()

    return {
        "pairs": [
            TrainingPairResponse(
                id=str(p.id),
                prompt=p.prompt[:200] + "..." if len(p.prompt) > 200 else p.prompt,
                chosen_response=(
                    p.chosen_response[:200] + "..."
                    if len(p.chosen_response) > 200
                    else p.chosen_response
                ),
                rejected_response=(
                    p.rejected_response[:200] + "..."
                    if len(p.rejected_response) > 200
                    else p.rejected_response
                ),
                pair_type=p.pair_type,
                status=p.status,
                confidence=p.confidence,
                created_at=p.created_at.isoformat() if p.created_at else None,
            )
            for p in pairs
        ],
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit if total > 0 else 0,
    }


@router.post("/datasets/build", response_model=dict)
async def build_training_dataset(
    payload: DatasetBuildRequest,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Build and register a frozen training dataset snapshot."""
    return await training_service.build_dataset_snapshot(
        db=db,
        created_by=current_user.id,
        snapshot_filter=payload.snapshot_filter,
    )


@router.get("/datasets", response_model=List[DatasetResponse])
async def list_training_datasets(
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List registered training datasets."""
    return await training_service.list_datasets(db=db, limit=limit)


@router.get("/datasets/{dataset_id}", response_model=DatasetResponse)
async def get_training_dataset(
    dataset_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single training dataset snapshot by ID."""
    dataset = await training_service.get_dataset(db=db, dataset_id=dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return dataset


@router.post("/evaluate/{version_id}", response_model=dict)
async def evaluate_model_version(
    version_id: uuid.UUID,
    dataset_tag: Optional[str] = Query(None),
    eval_type: str = Query("offline"),
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Register evaluation for a model version and queue evaluation work."""
    return await training_service.evaluate_version(
        db=db,
        version_id=version_id,
        dataset_tag=dataset_tag,
        eval_type=eval_type,
    )


@router.post("/versions/{version_id}/canary", response_model=dict)
async def canary_model_version(
    version_id: uuid.UUID,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Queue canary analysis for a model version against stable model."""
    return await training_service.canary_version(db=db, version_id=version_id)


@router.post("/versions/{version_id}/promote", response_model=dict)
async def promote_model_version(
    version_id: uuid.UUID,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Promote a candidate model version if all gate checks pass."""
    return await training_service.promote_version(
        db=db,
        version_id=version_id,
        promoted_by=current_user.id,
    )


@router.post("/versions/{version_id}/rollback", response_model=dict)
async def rollback_model_version(
    version_id: uuid.UUID,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Rollback active model to a specified completed model version."""
    return await training_service.rollback_to_version(db=db, version_id=version_id)


@router.get("/queue/status", response_model=dict)
async def get_training_queue_status(
    current_user: User = Depends(get_current_user),
):
    """Get queue depth and dead-letter counts by training pipeline queue."""
    return await training_service.get_queue_status()
