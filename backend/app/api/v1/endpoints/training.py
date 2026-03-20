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
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.v1.deps import (
    get_current_user,
    get_current_superuser,
    get_current_teacher_or_admin,
)
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
    parent_adapter_path: Optional[str] = Field(
        None,
        description="Optional filesystem path to a LoRA adapter checkpoint to warm-start from",
    )
    idempotency_key: Optional[str] = Field(
        None,
        description="Optional client-supplied idempotency key to deduplicate training job creation",
    )
    max_samples: Optional[int] = Field(
        None, ge=1,
        description="Cap on training samples per data type (SFT/DPO). Prevents OOM on large datasets.",
    )
    sample_strategy: Optional[str] = Field(
        None, pattern="^(recent_first|stratified|random)$",
        description="Sampling strategy: recent_first (default), stratified (balanced by difficulty), random.",
    )


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
    model_config = ConfigDict(protected_namespaces=())

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
    idempotency_key: Optional[str]
    replayed_from_job_id: Optional[str]


class ReplayTrainingJobRequest(BaseModel):
    idempotency_key: Optional[str] = None


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
    current_user: User = Depends(get_current_teacher_or_admin),
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
        parent_adapter_path=request.parent_adapter_path,
        idempotency_key=request.idempotency_key,
        max_samples=request.max_samples,
        sample_strategy=request.sample_strategy,
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
    version_id: str,
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
            idempotency_key=j.idempotency_key,
            replayed_from_job_id=str(j.replayed_from_job_id) if j.replayed_from_job_id else None,
        )
        for j in jobs
    ]


@router.get("/jobs/{job_id}", response_model=dict)
async def get_training_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single training job by ID."""
    job = await training_service.get_training_job(db=db, job_id=job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Training job not found")
    return job


@router.post("/jobs/{job_id}/replay", response_model=dict)
async def replay_training_job(
    job_id: str,
    payload: ReplayTrainingJobRequest,
    current_user: User = Depends(get_current_teacher_or_admin),
    db: AsyncSession = Depends(get_db),
):
    """Replay a finished training job for ops/debugging purposes."""
    return await training_service.replay_training_job(
        db=db,
        job_id=job_id,
        replayed_by=current_user.id,
        idempotency_key=payload.idempotency_key,
    )


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
    current_user: User = Depends(get_current_teacher_or_admin),
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
    dataset_id: str,
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
    version_id: str,
    dataset_tag: Optional[str] = Query(None),
    eval_type: str = Query("offline"),
    current_user: User = Depends(get_current_teacher_or_admin),
    db: AsyncSession = Depends(get_db),
):
    """Register evaluation for a model version and queue evaluation work."""
    return await training_service.evaluate_version(
        db=db,
        version_id=version_id,
        dataset_tag=dataset_tag,
        eval_type=eval_type,
        evaluated_by=current_user.id,
    )


@router.get("/evaluations", response_model=list)
async def list_evaluations(
    version_id: Optional[str] = Query(None, description="Filter by model version ID"),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List model evaluations, optionally filtered by version."""
    return await training_service.list_evaluations(db=db, version_id=version_id, limit=limit)


@router.get("/evaluations/{evaluation_id}", response_model=dict)
async def get_evaluation(
    evaluation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single model evaluation by ID, including spot-check details."""
    result = await training_service.get_evaluation(db=db, evaluation_id=evaluation_id)
    if not result:
        raise HTTPException(status_code=404, detail="Evaluation not found")
    return result


class SpotCheckRequest(BaseModel):
    decision: str = Field(..., pattern="^(approved|rejected)$", description="Spot-check decision")
    notes: Optional[str] = Field(None, description="Reviewer notes on spot-check quality")


@router.post("/evaluations/{evaluation_id}/spot-check", response_model=dict)
async def complete_spot_check(
    evaluation_id: str,
    payload: SpotCheckRequest,
    current_user: User = Depends(get_current_teacher_or_admin),
    db: AsyncSession = Depends(get_db),
):
    """Complete a human-in-the-loop spot check for a model evaluation."""
    return await training_service.complete_spot_check(
        db=db,
        evaluation_id=evaluation_id,
        decision=payload.decision,
        reviewed_by=current_user.id,
        notes=payload.notes,
    )


@router.post("/versions/{version_id}/canary", response_model=dict)
async def canary_model_version(
    version_id: str,
    current_user: User = Depends(get_current_teacher_or_admin),
    db: AsyncSession = Depends(get_db),
):
    """Queue canary analysis for a model version against stable model."""
    return await training_service.canary_version(db=db, version_id=version_id)


@router.post("/versions/{version_id}/promote", response_model=dict)
async def promote_model_version(
    version_id: str,
    current_user: User = Depends(get_current_teacher_or_admin),
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
    version_id: str,
    current_user: User = Depends(get_current_teacher_or_admin),
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


# ══════════════════════════════════════
# Training Data Export
# ══════════════════════════════════════

@router.get("/export/sft")
async def export_sft_jsonl(
    subject_id: Optional[str] = Query(None, description="Filter by subject ID"),
    status_filter: str = Query("all", description="all | approved | pending"),
    include_context: bool = Query(True, description="Include source chunk text in input field"),
    limit: int = Query(10000, ge=1, le=50000),
    current_user: User = Depends(get_current_teacher_or_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Export questions as JSONL for Supervised Fine-Tuning (SFT).

    Each line is a JSON object with:
    - instruction: system + metadata prompt
    - input: source context (optional)
    - output: full MCQ JSON (question_text, options, correct_answer, correct_answer_text, explanation)

    Compatible with axolotl, unsloth, and LLaMA-Factory training pipelines.
    """
    import json as json_mod
    import re
    from fastapi.responses import StreamingResponse
    from sqlalchemy.orm import selectinload
    from app.models.document import DocumentChunk

    # Build query
    q = (
        select(Question)
        .options(selectinload(Question.subject), selectinload(Question.topic))
        .where(Question.is_archived == False, Question.is_latest == True)
    )

    if subject_id:
        q = q.where(Question.subject_id == str(subject_id))
    if status_filter == "approved":
        q = q.where(Question.vetting_status == "approved")
    elif status_filter == "pending":
        q = q.where(Question.vetting_status == "pending")

    q = q.order_by(Question.generated_at.desc()).limit(limit)
    result = await db.execute(q)
    questions = result.scalars().all()

    # Pre-fetch source chunks if include_context
    chunk_cache: dict = {}
    if include_context:
        all_chunk_ids = set()
        for question in questions:
            if question.source_chunk_ids:
                all_chunk_ids.update(question.source_chunk_ids)
        if all_chunk_ids:
            chunk_result = await db.execute(
                select(DocumentChunk).where(DocumentChunk.id.in_(list(all_chunk_ids)[:500]))
            )
            for chunk in chunk_result.scalars().all():
                chunk_cache[chunk.id] = chunk.chunk_text

    def _extract_option_text(opt: str) -> str:
        m = re.match(r'^[A-F]\)\s*', opt)
        return opt[m.end():] if m else opt

    def generate_lines():
        for question in questions:
            # Build instruction
            instruction_parts = [
                "You are an expert MCQ generator for university examinations.",
                "Generate a high-quality multiple choice question from the given context.",
                "",
            ]

            subject_name = question.subject.name if question.subject else "Unknown"
            subject_code = question.subject.code if question.subject else ""
            topic_name = question.topic.name if question.topic else (question.topic_tags[0] if question.topic_tags else "General")

            instruction_parts.append(f"Subject: {subject_name} ({subject_code})")
            instruction_parts.append(f"Topic: {topic_name}")
            instruction_parts.append(f"Difficulty: {question.difficulty_level or 'medium'}")
            instruction_parts.append(f"Bloom Level: {question.bloom_taxonomy_level or 'apply'}")
            if question.marks:
                instruction_parts.append(f"Marks: {question.marks}")
            instruction_parts.append("")
            instruction_parts.append("Generate an MCQ with 4 options (A-D), the correct answer letter, and a detailed explanation. Output valid JSON only.")

            instruction = "\n".join(instruction_parts)

            # Build input (source context)
            input_text = ""
            if include_context and question.source_chunk_ids:
                chunks_text = []
                for cid in question.source_chunk_ids[:3]:
                    if cid in chunk_cache:
                        chunks_text.append(chunk_cache[cid])
                if chunks_text:
                    input_text = "\n\n---\n\n".join(chunks_text)

            # Build output — full MCQ JSON
            options = question.options or []
            correct_letter = question.correct_answer or "A"
            correct_text = ""
            labels = ['A', 'B', 'C', 'D', 'E', 'F']
            for i, label in enumerate(labels[:len(options)]):
                if label == correct_letter.strip().upper():
                    correct_text = _extract_option_text(options[i])
                    break

            output = {
                "question_text": question.question_text,
                "options": options,
                "correct_answer": correct_letter,
                "correct_answer_text": correct_text,
                "explanation": question.explanation or "",
            }

            record = {
                "instruction": instruction,
                "input": input_text,
                "output": json_mod.dumps(output, ensure_ascii=False),
            }

            yield json_mod.dumps(record, ensure_ascii=False) + "\n"

    return StreamingResponse(
        generate_lines(),
        media_type="application/x-ndjson",
        headers={
            "Content-Disposition": f"attachment; filename=sft_mcq_export_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.jsonl",
        },
    )


@router.get("/export/dpo")
async def export_dpo_jsonl(
    limit: int = Query(10000, ge=1, le=50000),
    current_user: User = Depends(get_current_teacher_or_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Export DPO training pairs as JSONL.

    Each line is a JSON object with:
    - prompt: enriched generation prompt
    - chosen: preferred response
    - rejected: rejected response

    Compatible with TRL DPOTrainer and axolotl DPO pipelines.
    """
    import json as json_mod
    from fastapi.responses import StreamingResponse

    result = await db.execute(
        select(TrainingPair)
        .where(TrainingPair.status.in_(["pending", "queued", "used"]))
        .order_by(TrainingPair.created_at.desc())
        .limit(limit)
    )
    pairs = result.scalars().all()

    synthetic_records = []
    if len(pairs) < limit:
        excluded_question_ids = {
            pair.chosen_question_id
            for pair in pairs
            if pair.chosen_question_id is not None
        }
        synthetic_records = await training_service._generate_synthetic_dpo_records(
            db=db,
            since=training_service._resolve_training_since(),
            limit=limit - len(pairs),
            exclude_question_ids=excluded_question_ids,
        )

    def generate_lines():
        for pair in pairs:
            record = {
                "prompt": training_service._normalize_dpo_prompt(pair.prompt),
                "chosen": training_service._normalize_dpo_completion(pair.chosen_response),
                "rejected": training_service._normalize_dpo_completion(pair.rejected_response),
                "weight": pair.pair_weight or 1.0,
                "metadata": {
                    "pair_type": pair.pair_type,
                    "confidence": pair.confidence,
                    "language": pair.language,
                    "rejected_reason_codes": pair.rejected_reason_codes,
                },
            }
            yield json_mod.dumps(record, ensure_ascii=False) + "\n"

        for record in synthetic_records:
            yield json_mod.dumps(record, ensure_ascii=False) + "\n"

    return StreamingResponse(
        generate_lines(),
        media_type="application/x-ndjson",
        headers={
            "Content-Disposition": f"attachment; filename=dpo_pairs_export_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.jsonl",
        },
    )


@router.get("/export/stats")
async def export_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get training data statistics — overview of available data for fine-tuning."""
    from app.models.question import Question
    from app.models.subject import Subject

    total_q = await db.execute(select(func.count(Question.id)).where(Question.is_archived == False))
    approved_q = await db.execute(select(func.count(Question.id)).where(Question.is_archived == False, Question.vetting_status == "approved"))
    pending_q = await db.execute(select(func.count(Question.id)).where(Question.is_archived == False, Question.vetting_status == "pending"))
    total_pairs = await db.execute(select(func.count(TrainingPair.id)))
    total_subjects = await db.execute(select(func.count(Subject.id)))

    # Bloom distribution
    bloom_result = await db.execute(
        select(Question.bloom_taxonomy_level, func.count(Question.id))
        .where(Question.is_archived == False)
        .group_by(Question.bloom_taxonomy_level)
    )
    bloom_dist = {row[0]: row[1] for row in bloom_result.all()}

    # Difficulty distribution
    diff_result = await db.execute(
        select(Question.difficulty_level, func.count(Question.id))
        .where(Question.is_archived == False)
        .group_by(Question.difficulty_level)
    )
    diff_dist = {row[0]: row[1] for row in diff_result.all()}

    # Answer distribution
    ans_result = await db.execute(
        select(Question.correct_answer, func.count(Question.id))
        .where(Question.is_archived == False)
        .group_by(Question.correct_answer)
    )
    ans_dist = {row[0]: row[1] for row in ans_result.all()}

    return {
        "total_questions": total_q.scalar(),
        "approved_questions": approved_q.scalar(),
        "pending_questions": pending_q.scalar(),
        "dpo_pairs": total_pairs.scalar(),
        "subjects": total_subjects.scalar(),
        "bloom_distribution": bloom_dist,
        "difficulty_distribution": diff_dist,
        "answer_distribution": ans_dist,
        "sft_ready": total_q.scalar() > 0,
        "dpo_ready": total_pairs.scalar() >= 10,
    }
