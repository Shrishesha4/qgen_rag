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
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from pgvector.sqlalchemy import Vector
import uuid
import enum

from app.core.database import Base
from app.core.config import settings


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

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE"),
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

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # The generation prompt that produced both responses
    prompt: Mapped[str] = mapped_column(Text, nullable=False)

    # The preferred response
    chosen_response: Mapped[str] = mapped_column(Text, nullable=False)

    # The rejected response
    rejected_response: Mapped[str] = mapped_column(Text, nullable=False)

    # Provenance
    vetting_log_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vetting_logs.id", ondelete="SET NULL"),
    )
    chosen_question_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("questions.id", ondelete="SET NULL"),
    )
    rejected_question_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("questions.id", ondelete="SET NULL"),
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

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
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
    parent_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("model_versions.id", ondelete="SET NULL"),
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

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    model_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("model_versions.id", ondelete="CASCADE"),
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
