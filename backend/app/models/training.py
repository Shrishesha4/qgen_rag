"""
Training pipeline database models.

Tables for the Dual-Engine training loop:
- VettingLog: Detailed per-question vetting decisions with edit diffs
- TrainingPair: DPO (chosen/rejected) pairs for preference optimization
- ModelVersion: Tracks LoRA adapter versions and active model state
"""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    String, Integer, Float, Boolean, DateTime, Text,
    ForeignKey, func, Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from pgvector.sqlalchemy import Vector
import uuid
import enum

from app.core.database import Base
from app.core.config import settings
from app.core.types import UUIDString


class VettingDecision(str, enum.Enum):
    """Possible vetting outcomes."""
    APPROVE = "approve"
    REJECT = "reject"
    EDIT = "edit"


class TrainingPairStatus(str, enum.Enum):
    """Status of a training pair in the pipeline."""
    PENDING = "pending"
    QUEUED = "queued"
    USED = "used"
    SKIPPED = "skipped"


class TrainingJobStatus(str, enum.Enum):
    """Status of a fine-tuning job."""
    PENDING = "pending"
    PREPARING = "preparing"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ═══════════════════════════════════════════
# VettingLog — captures every vetting action
# ═══════════════════════════════════════════

class VettingLog(Base):
    """
    Granular record of each vetting action — the gold mine for training.

    When a vetter *edits* a question, the original text and edited text
    are both stored so the system can create DPO (chosen/rejected) pairs.
    """

    __tablename__ = "vetting_logs"

    id: Mapped[str] = mapped_column(
        UUIDString(), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    question_id: Mapped[str] = mapped_column(
        UUIDString(), ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    vetter_id: Mapped[str] = mapped_column(
        String(36), nullable=False, index=True,
        comment="User ID of the vetter (from auth.db)",
    )

    # Decision
    decision: Mapped[str] = mapped_column(
        String(10), nullable=False,
        comment="approve | reject | edit",
    )
    review_version: Mapped[int] = mapped_column(
        Integer,
        default=1,
        comment="Review contract version used when this decision was submitted",
    )
    quality_score: Mapped[Optional[float]] = mapped_column(
        Float,
        comment="Normalized quality score between 0 and 1",
    )
    rubric_snapshot: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        comment="Rubric snapshot used at decision time",
    )
    reason_codes: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(Text),
        comment="Controlled taxonomy reason codes linked to the decision",
    )
    severity_level: Mapped[Optional[str]] = mapped_column(
        String(20),
        comment="minor | major | critical",
    )

    # Edit data (populated when decision == 'edit')
    original_text: Mapped[Optional[str]] = mapped_column(Text)
    edited_text: Mapped[Optional[str]] = mapped_column(Text)
    edit_diff: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        comment="Structured diff: {field: {old, new}} for all changed fields",
    )

    # Rejection reasoning (populated when decision == 'reject')
    rejection_reasons: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text))
    rejection_reason_embedding = mapped_column(
        Vector(settings.EMBEDDING_DIMENSION),
        comment="Embedding of concatenated rejection reasons for RAG retrieval",
    )

    # Free-text feedback
    feedback: Mapped[Optional[str]] = mapped_column(Text)

    # Rich approval metadata
    approved_difficulty: Mapped[Optional[str]] = mapped_column(
        String(20),
        comment="easy | medium | hard when an approval is explicitly graded",
    )

    # Critique scores (from Constitutional AI auto-review, if available)
    auto_critique_score: Mapped[Optional[float]] = mapped_column(Float)
    auto_critique_reasons: Mapped[Optional[dict]] = mapped_column(JSONB)

    # Metadata
    time_spent_seconds: Mapped[Optional[int]] = mapped_column(
        Integer, comment="How long the vetter spent reviewing this question",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True,
    )

    def __repr__(self) -> str:
        return f"<VettingLog {self.id} q={self.question_id} decision={self.decision}>"


# ═══════════════════════════════════════════
# TrainingPair — DPO chosen/rejected pairs
# ═══════════════════════════════════════════

class TrainingPair(Base):
    """
    Training pair for Direct Preference Optimization (DPO).

    Created from vetting logs:
    - If vetter *edits*: original → rejected, edited → chosen
    - If vetter *rejects* & another version *approved*: rejected → rejected, approved → chosen
    """

    __tablename__ = "training_pairs"

    id: Mapped[str] = mapped_column(
        UUIDString(), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # The generation prompt that produced both responses
    prompt: Mapped[str] = mapped_column(Text, nullable=False)

    # The preferred response
    chosen_response: Mapped[str] = mapped_column(Text, nullable=False)

    # The rejected response
    rejected_response: Mapped[str] = mapped_column(Text, nullable=False)

    # Provenance
    vetting_log_id: Mapped[Optional[str]] = mapped_column(
        UUIDString(), ForeignKey("vetting_logs.id", ondelete="SET NULL"),
    )
    chosen_question_id: Mapped[Optional[str]] = mapped_column(
        UUIDString(), ForeignKey("questions.id", ondelete="SET NULL"),
    )
    rejected_question_id: Mapped[Optional[str]] = mapped_column(
        UUIDString(), ForeignKey("questions.id", ondelete="SET NULL"),
    )

    # Pair type for filtering during training
    pair_type: Mapped[str] = mapped_column(
        String(20), default="edit",
        comment="edit | reject_approve | critique",
    )

    # Pipeline status
    status: Mapped[str] = mapped_column(
        String(10), default="pending",
        comment="pending | queued | used | skipped",
    )
    used_in_version: Mapped[Optional[str]] = mapped_column(
        String(50), comment="model_version id that consumed this pair",
    )

    # Quality signal
    confidence: Mapped[Optional[float]] = mapped_column(
        Float, comment="How confident we are this is a good training signal (0-1)",
    )
    dedupe_hash: Mapped[Optional[str]] = mapped_column(
        String(64),
        unique=True,
        index=True,
        comment="Deterministic identity hash for pair deduplication",
    )
    pair_weight: Mapped[float] = mapped_column(
        Float,
        default=1.0,
        comment="Training-time weight for this pair",
    )
    language: Mapped[str] = mapped_column(
        String(10),
        default="en",
    )
    source_split: Mapped[Optional[str]] = mapped_column(
        String(10),
        comment="train | val | test",
    )
    rejected_reason_codes: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(Text),
        comment="Controlled taxonomy reason codes for the rejected sample",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True,
    )

    def __repr__(self) -> str:
        return f"<TrainingPair {self.id} type={self.pair_type} status={self.status}>"


# ═══════════════════════════════════════════
# ModelVersion — LoRA adapter lineage
# ═══════════════════════════════════════════

class ModelVersion(Base):
    """
    Tracks fine-tuned model versions (LoRA adapters).

    Only one version is `is_active=True` at a time — the one
    currently used by the CritiqueService for auto-review.
    """

    __tablename__ = "model_versions"

    id: Mapped[str] = mapped_column(
        UUIDString(), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    version_tag: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False,
        comment="Semantic label, e.g. v1.0, v1.1-dpo",
    )

    # Base model info
    base_model: Mapped[str] = mapped_column(
        String(100), nullable=False,
        comment="e.g. deepseek-r1-distill-llama-70b",
    )
    lora_adapter_path: Mapped[Optional[str]] = mapped_column(
        String(500),
        comment="Filesystem path to the LoRA adapter weights",
    )

    # Training metadata
    training_method: Mapped[str] = mapped_column(
        String(20), default="sft",
        comment="sft | dpo | sft+dpo",
    )
    training_pairs_count: Mapped[int] = mapped_column(Integer, default=0)
    sft_samples_count: Mapped[int] = mapped_column(Integer, default=0)

    # Hyperparameters snapshot
    hyperparameters: Mapped[Optional[dict]] = mapped_column(
        JSONB, comment="lr, epochs, lora_r, lora_alpha, etc.",
    )

    # Evaluation metrics
    eval_metrics: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        comment="loss, accuracy, vetter_agreement_rate, etc.",
    )

    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=False,
        comment="Only one version is active at a time",
    )
    status: Mapped[str] = mapped_column(
        String(20), default="pending",
        comment="pending | training | completed | failed",
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    # Parent version (for lineage tracking)
    parent_version_id: Mapped[Optional[str]] = mapped_column(
        UUIDString(), ForeignKey("model_versions.id", ondelete="SET NULL"),
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )
    training_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    training_completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        return f"<ModelVersion {self.version_tag} active={self.is_active}>"


# ═══════════════════════════════════════════
# TrainingJob — individual training runs
# ═══════════════════════════════════════════

class TrainingJob(Base):
    """
    Tracks individual fine-tuning job runs.
    """

    __tablename__ = "training_jobs"

    id: Mapped[str] = mapped_column(
        UUIDString(), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    model_version_id: Mapped[str] = mapped_column(
        UUIDString(), ForeignKey("model_versions.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Job details
    job_type: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="sft | dpo | critique_eval",
    )
    status: Mapped[str] = mapped_column(
        String(20), default="pending",
        comment="pending | preparing | running | completed | failed | cancelled",
    )

    # Data snapshot
    training_data_path: Mapped[Optional[str]] = mapped_column(String(500))
    training_samples: Mapped[int] = mapped_column(Integer, default=0)
    validation_samples: Mapped[int] = mapped_column(Integer, default=0)
    idempotency_key: Mapped[Optional[str]] = mapped_column(
        String(128), index=True,
    )
    replayed_from_job_id: Mapped[Optional[str]] = mapped_column(
        UUIDString(), ForeignKey("training_jobs.id", ondelete="SET NULL"),
    )

    # Progress
    current_epoch: Mapped[int] = mapped_column(Integer, default=0)
    total_epochs: Mapped[int] = mapped_column(Integer, default=3)
    current_step: Mapped[int] = mapped_column(Integer, default=0)
    total_steps: Mapped[int] = mapped_column(Integer, default=0)
    current_loss: Mapped[Optional[float]] = mapped_column(Float)

    # Result
    final_loss: Mapped[Optional[float]] = mapped_column(Float)
    eval_metrics: Mapped[Optional[dict]] = mapped_column(JSONB)
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Triggered by
    triggered_by: Mapped[Optional[str]] = mapped_column(
        String(36), comment="User ID or 'system' for scheduled runs",
    )

    def __repr__(self) -> str:
        return f"<TrainingJob {self.id} type={self.job_type} status={self.status}>"


class VettingReasonCode(Base):
    """Controlled taxonomy of vetting reason codes."""

    __tablename__ = "vetting_reason_codes"

    id: Mapped[str] = mapped_column(
        UUIDString(), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    code: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    severity_default: Mapped[str] = mapped_column(String(20), default="minor")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True,
    )


class TrainingDataset(Base):
    """Immutable dataset snapshot registry for reproducible training."""

    __tablename__ = "training_datasets"

    id: Mapped[str] = mapped_column(
        UUIDString(), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    dataset_tag: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )
    created_by: Mapped[Optional[str]] = mapped_column(String(36))
    snapshot_filter: Mapped[Optional[dict]] = mapped_column(JSONB)
    sample_counts: Mapped[Optional[dict]] = mapped_column(JSONB)
    manifest_path: Mapped[Optional[str]] = mapped_column(String(500))
    checksum: Mapped[Optional[str]] = mapped_column(String(128))


class ModelEvaluation(Base):
    """Evaluation registry for model versions against frozen datasets."""

    __tablename__ = "model_evaluations"

    id: Mapped[str] = mapped_column(
        UUIDString(), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    model_version_id: Mapped[str] = mapped_column(
        UUIDString(), ForeignKey("model_versions.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    dataset_tag: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    eval_type: Mapped[str] = mapped_column(String(50), nullable=False)
    metrics: Mapped[Optional[dict]] = mapped_column(JSONB)
    pass_fail: Mapped[Optional[bool]] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )

    # Evaluation lifecycle
    eval_status: Mapped[str] = mapped_column(
        String(30), default="pending",
        comment="pending | running | completed | failed",
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    # Quality gate details
    gate_checks: Mapped[Optional[dict]] = mapped_column(
        JSONB, comment="Per-gate pass/fail breakdown",
    )

    # Spot-check workflow
    spot_check_status: Mapped[Optional[str]] = mapped_column(
        String(30), default="not_required",
        comment="not_required | pending | approved | rejected",
    )
    spot_check_samples: Mapped[Optional[dict]] = mapped_column(
        JSONB, comment="Sample question IDs selected for human review",
    )
    spot_check_reviewed_by: Mapped[Optional[str]] = mapped_column(String(36))
    spot_check_reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    spot_check_notes: Mapped[Optional[str]] = mapped_column(Text)

    # Lineage
    evaluated_by: Mapped[Optional[str]] = mapped_column(
        String(36), comment="User ID or 'system' for automated evaluations",
    )
