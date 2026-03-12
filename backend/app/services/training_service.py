"""
TrainingService — SFT / DPO / LoRA fine-tuning pipeline.

Phase 4 of the Dual-Engine self-correcting loop:
  1. SFT Data Prep: Aggregate approved questions into instruction-tuning JSONL.
  2. DPO Data Prep: Build (prompt, chosen, rejected) triplets from vetting edits.
  3. Fine-Tuning Execution: LoRA-based fine-tuning of the local DeepSeek model.
  4. Model Version Management: Track adapter lineage and active deployment.

This service runs as a background pipeline, independent of the web request cycle.
"""

import json
import logging
import os
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.question import Question
from app.models.training import (
    VettingLog,
    TrainingPair,
    ModelVersion,
    TrainingJob,
    TrainingPairStatus,
    TrainingJobStatus,
)


logger = logging.getLogger(__name__)

# ── Configurable paths ──
TRAINING_DATA_DIR = Path(os.environ.get("TRAINING_DATA_DIR", "./training_data"))
LORA_ADAPTERS_DIR = Path(os.environ.get("LORA_ADAPTERS_DIR", "./lora_adapters"))
BASE_MODEL_NAME = os.environ.get(
    "TRAINING_BASE_MODEL", "deepseek-ai/DeepSeek-R1-Distill-Llama-8B"
)


class TrainingService:
    """
    Orchestrates the full training pipeline:
      prepare_sft_data → prepare_dpo_data → launch_training → deploy_model
    """

    def __init__(self):
        TRAINING_DATA_DIR.mkdir(parents=True, exist_ok=True)
        LORA_ADAPTERS_DIR.mkdir(parents=True, exist_ok=True)

    # ═══════════════════════════════════════════
    # Phase 1: SFT Data Preparation
    # ═══════════════════════════════════════════

    async def prepare_sft_data(
        self,
        db: AsyncSession,
        since: Optional[datetime] = None,
    ) -> tuple[str, int]:
        """
        Export approved questions as SFT instruction-tuning JSONL.

        Format per line:
        {
          "instruction": "Generate a <type> question at <difficulty> about <topic>",
          "input": "<context from source chunks if available>",
          "output": "<question_text>\nAnswer: <answer>\nExplanation: <explanation>"
        }

        Returns (file_path, sample_count).
        """
        if since is None:
            since = datetime.now(timezone.utc) - timedelta(days=7)

        query = (
            select(Question)
            .where(
                Question.vetting_status == "approved",
                Question.is_latest == True,
                Question.vetted_at >= since,
            )
            .order_by(Question.vetted_at.asc())
        )
        result = await db.execute(query)
        questions = result.scalars().all()

        if not questions:
            logger.info("No approved questions since %s — nothing to export.", since)
            return ("", 0)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        output_path = TRAINING_DATA_DIR / f"sft_{timestamp}.jsonl"

        count = 0
        with open(output_path, "w") as f:
            for q in questions:
                instruction = self._build_sft_instruction(q)
                output_text = self._build_sft_output(q)
                input_text = ""

                # Use generation metadata for context if available
                if q.generation_metadata and "context" in q.generation_metadata:
                    input_text = q.generation_metadata["context"][:2000]

                record = {
                    "instruction": instruction,
                    "input": input_text,
                    "output": output_text,
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                count += 1

        logger.info("Exported %d SFT samples to %s", count, output_path)
        return (str(output_path), count)

    # ═══════════════════════════════════════════
    # Phase 2: DPO Data Preparation
    # ═══════════════════════════════════════════

    async def prepare_dpo_data(
        self,
        db: AsyncSession,
        since: Optional[datetime] = None,
    ) -> tuple[str, int]:
        """
        Export DPO training triplets as JSONL.

        Format per line:
        {
          "prompt": "<generation prompt>",
          "chosen": "<preferred response>",
          "rejected": "<rejected response>"
        }

        Returns (file_path, sample_count).
        """
        if since is None:
            since = datetime.now(timezone.utc) - timedelta(days=30)

        query = (
            select(TrainingPair)
            .where(
                TrainingPair.status == "pending",
                TrainingPair.created_at >= since,
                TrainingPair.chosen_response != "",
            )
            .order_by(TrainingPair.created_at.asc())
        )
        result = await db.execute(query)
        pairs = result.scalars().all()

        if not pairs:
            logger.info("No pending DPO pairs since %s — nothing to export.", since)
            return ("", 0)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        output_path = TRAINING_DATA_DIR / f"dpo_{timestamp}.jsonl"

        count = 0
        pair_ids = []
        with open(output_path, "w") as f:
            for pair in pairs:
                if not pair.chosen_response or not pair.rejected_response:
                    continue
                record = {
                    "prompt": pair.prompt,
                    "chosen": pair.chosen_response,
                    "rejected": pair.rejected_response,
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                pair_ids.append(pair.id)
                count += 1

        # Mark pairs as queued
        if pair_ids:
            await db.execute(
                update(TrainingPair)
                .where(TrainingPair.id.in_(pair_ids))
                .values(status="queued")
            )
            await db.commit()

        logger.info("Exported %d DPO pairs to %s", count, output_path)
        return (str(output_path), count)

    # ═══════════════════════════════════════════
    # Phase 3: Fine-Tuning Execution
    # ═══════════════════════════════════════════

    async def trigger_training(
        self,
        db: AsyncSession,
        triggered_by: str = "system",
        base_model: Optional[str] = None,
        training_method: str = "sft",
        hyperparameters: Optional[dict] = None,
    ) -> dict:
        """
        Trigger a new fine-tuning job.

        Steps:
        1. Create a new ModelVersion record.
        2. Prepare training data (SFT and/or DPO).
        3. Create a TrainingJob record.
        4. Launch the training process.

        Returns status dict with job_id, version_id, sample counts.
        """
        base_model = base_model or BASE_MODEL_NAME
        default_hp = {
            "learning_rate": 2e-4,
            "num_epochs": 3,
            "batch_size": 4,
            "gradient_accumulation_steps": 4,
            "lora_r": 16,
            "lora_alpha": 32,
            "lora_dropout": 0.05,
            "max_seq_length": 2048,
            "warmup_ratio": 0.03,
            "weight_decay": 0.01,
        }
        if hyperparameters:
            default_hp.update(hyperparameters)

        # Find the current active version (parent)
        active_result = await db.execute(
            select(ModelVersion).where(ModelVersion.is_active == True)
        )
        active_version = active_result.scalar_one_or_none()
        parent_id = active_version.id if active_version else None

        # Determine next version tag
        count_result = await db.execute(
            select(func.count(ModelVersion.id))
        )
        version_count = count_result.scalar() or 0
        version_tag = f"v{version_count + 1}.0-{training_method}"

        # Create model version
        model_version = ModelVersion(
            version_tag=version_tag,
            base_model=base_model,
            training_method=training_method,
            hyperparameters=default_hp,
            parent_version_id=parent_id,
            status="pending",
        )
        db.add(model_version)
        await db.flush()

        # Prepare data
        sft_path, sft_count = "", 0
        dpo_path, dpo_count = "", 0

        if training_method in ("sft", "sft+dpo"):
            sft_path, sft_count = await self.prepare_sft_data(db)
        if training_method in ("dpo", "sft+dpo"):
            dpo_path, dpo_count = await self.prepare_dpo_data(db)

        total_samples = sft_count + dpo_count
        if total_samples == 0:
            model_version.status = "failed"
            model_version.error_message = "No training data available"
            await db.commit()
            return {
                "status": "no_data",
                "message": "No training data available — need more vetting activity.",
                "version_tag": version_tag,
            }

        model_version.sft_samples_count = sft_count
        model_version.training_pairs_count = dpo_count

        # Determine adapter output path
        adapter_path = str(LORA_ADAPTERS_DIR / version_tag)
        model_version.lora_adapter_path = adapter_path

        # Create training job
        data_path = sft_path or dpo_path
        job = TrainingJob(
            model_version_id=model_version.id,
            job_type=training_method,
            status="pending",
            training_data_path=data_path,
            training_samples=total_samples,
            total_epochs=default_hp["num_epochs"],
            triggered_by=triggered_by,
        )
        db.add(job)
        await db.commit()

        # Launch training asynchronously
        # In production this would dispatch to a GPU worker queue.
        # Here we record the job and it will be picked up by the training worker.
        logger.info(
            "Training job %s created: method=%s, sft=%d, dpo=%d, version=%s",
            job.id, training_method, sft_count, dpo_count, version_tag,
        )

        return {
            "status": "created",
            "job_id": str(job.id),
            "version_id": str(model_version.id),
            "version_tag": version_tag,
            "training_method": training_method,
            "sft_samples": sft_count,
            "dpo_pairs": dpo_count,
            "total_samples": total_samples,
            "hyperparameters": default_hp,
        }

    async def run_training_job(self, job_id: uuid.UUID, db: AsyncSession) -> dict:
        """
        Execute a training job (SFT or DPO with LoRA).

        This is the actual training loop. In production, this runs on a GPU node.
        Uses HuggingFace transformers + peft + trl for LoRA fine-tuning.
        """
        # Load job and version
        job_result = await db.execute(
            select(TrainingJob).where(TrainingJob.id == job_id)
        )
        job = job_result.scalar_one_or_none()
        if not job:
            return {"status": "error", "message": "Job not found"}

        version_result = await db.execute(
            select(ModelVersion).where(ModelVersion.id == job.model_version_id)
        )
        version = version_result.scalar_one_or_none()
        if not version:
            return {"status": "error", "message": "Model version not found"}

        # Update status
        job.status = "preparing"
        job.started_at = datetime.now(timezone.utc)
        version.status = "training"
        version.training_started_at = datetime.now(timezone.utc)
        await db.commit()

        try:
            if job.job_type in ("sft", "sft+dpo"):
                await self._run_sft(job, version, db)
            if job.job_type in ("dpo", "sft+dpo"):
                await self._run_dpo(job, version, db)

            # Mark complete
            job.status = "completed"
            job.completed_at = datetime.now(timezone.utc)
            version.status = "completed"
            version.training_completed_at = datetime.now(timezone.utc)
            await db.commit()

            # Mark consumed training pairs as "used"
            await db.execute(
                update(TrainingPair)
                .where(TrainingPair.status == "queued")
                .values(status="used", used_in_version=version.version_tag)
            )
            await db.commit()

            return {
                "status": "completed",
                "job_id": str(job.id),
                "version_tag": version.version_tag,
                "adapter_path": version.lora_adapter_path,
            }

        except Exception as e:
            logger.exception("Training job %s failed: %s", job_id, e)
            job.status = "failed"
            job.error_message = str(e)[:1000]
            job.completed_at = datetime.now(timezone.utc)
            version.status = "failed"
            version.error_message = str(e)[:1000]
            await db.commit()
            return {"status": "failed", "error": str(e)}

    async def _run_sft(
        self, job: TrainingJob, version: ModelVersion, db: AsyncSession
    ):
        """
        Run Supervised Fine-Tuning with LoRA on the local model.

        Uses: transformers, peft, trl (SFTTrainer).
        """
        # Delayed imports — these are heavy ML dependencies
        from transformers import (        # type: ignore
            AutoModelForCausalLM,
            AutoTokenizer,
            TrainingArguments,
        )
        from peft import LoraConfig, get_peft_model, TaskType  # type: ignore
        from trl import SFTTrainer          # type: ignore
        from datasets import load_dataset   # type: ignore

        hp = version.hyperparameters or {}
        data_path = job.training_data_path

        logger.info("Loading SFT dataset from %s", data_path)
        dataset = load_dataset("json", data_files=data_path, split="train")

        logger.info("Loading base model: %s", version.base_model)
        tokenizer = AutoTokenizer.from_pretrained(version.base_model)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        model = AutoModelForCausalLM.from_pretrained(
            version.base_model,
            torch_dtype="auto",
            device_map="auto",
        )

        # LoRA config
        lora_config = LoraConfig(
            task_type=TaskType.CAUSAL_LM,
            r=hp.get("lora_r", 16),
            lora_alpha=hp.get("lora_alpha", 32),
            lora_dropout=hp.get("lora_dropout", 0.05),
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
        )

        output_dir = version.lora_adapter_path
        training_args = TrainingArguments(
            output_dir=output_dir,
            num_train_epochs=hp.get("num_epochs", 3),
            per_device_train_batch_size=hp.get("batch_size", 4),
            gradient_accumulation_steps=hp.get("gradient_accumulation_steps", 4),
            learning_rate=hp.get("learning_rate", 2e-4),
            warmup_ratio=hp.get("warmup_ratio", 0.03),
            weight_decay=hp.get("weight_decay", 0.01),
            logging_steps=10,
            save_strategy="epoch",
            fp16=True,
            max_grad_norm=1.0,
            report_to="none",
        )

        def formatting_func(examples):
            texts = []
            for inst, inp, out in zip(
                examples["instruction"], examples["input"], examples["output"]
            ):
                if inp:
                    text = f"### Instruction:\n{inst}\n\n### Input:\n{inp}\n\n### Response:\n{out}"
                else:
                    text = f"### Instruction:\n{inst}\n\n### Response:\n{out}"
                texts.append(text)
            return texts

        trainer = SFTTrainer(
            model=model,
            tokenizer=tokenizer,
            train_dataset=dataset,
            peft_config=lora_config,
            args=training_args,
            formatting_func=formatting_func,
            max_seq_length=hp.get("max_seq_length", 2048),
        )

        logger.info("Starting SFT training...")
        train_result = trainer.train()

        # Save LoRA adapter
        trainer.save_model(output_dir)
        tokenizer.save_pretrained(output_dir)

        # Record metrics
        job.final_loss = train_result.training_loss
        job.eval_metrics = {
            "train_loss": train_result.training_loss,
            "train_runtime": train_result.metrics.get("train_runtime"),
            "train_samples_per_second": train_result.metrics.get(
                "train_samples_per_second"
            ),
        }
        version.eval_metrics = job.eval_metrics

        logger.info(
            "SFT training complete — loss=%.4f, adapter saved to %s",
            train_result.training_loss,
            output_dir,
        )

    async def _run_dpo(
        self, job: TrainingJob, version: ModelVersion, db: AsyncSession
    ):
        """
        Run Direct Preference Optimization with LoRA.

        Uses: trl (DPOTrainer).
        """
        from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments  # type: ignore
        from peft import LoraConfig, TaskType  # type: ignore
        from trl import DPOTrainer  # type: ignore
        from datasets import load_dataset  # type: ignore

        hp = version.hyperparameters or {}

        # Find DPO data file
        dpo_files = sorted(TRAINING_DATA_DIR.glob("dpo_*.jsonl"), reverse=True)
        if not dpo_files:
            logger.warning("No DPO data files found — skipping DPO phase.")
            return

        data_path = str(dpo_files[0])
        logger.info("Loading DPO dataset from %s", data_path)
        dataset = load_dataset("json", data_files=data_path, split="train")

        logger.info("Loading model for DPO: %s", version.base_model)
        tokenizer = AutoTokenizer.from_pretrained(version.base_model)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        # Load model (with SFT adapter if available)
        adapter_path = version.lora_adapter_path
        if adapter_path and os.path.exists(os.path.join(adapter_path, "adapter_config.json")):
            from peft import PeftModel  # type: ignore
            base_model = AutoModelForCausalLM.from_pretrained(
                version.base_model, torch_dtype="auto", device_map="auto"
            )
            model = PeftModel.from_pretrained(base_model, adapter_path)
            model = model.merge_and_unload()  # Merge SFT adapter before DPO
        else:
            model = AutoModelForCausalLM.from_pretrained(
                version.base_model, torch_dtype="auto", device_map="auto"
            )

        # Reference model (frozen copy for DPO)
        ref_model = AutoModelForCausalLM.from_pretrained(
            version.base_model, torch_dtype="auto", device_map="auto"
        )

        lora_config = LoraConfig(
            task_type=TaskType.CAUSAL_LM,
            r=hp.get("lora_r", 16),
            lora_alpha=hp.get("lora_alpha", 32),
            lora_dropout=hp.get("lora_dropout", 0.05),
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
        )

        dpo_output = adapter_path + "-dpo" if adapter_path else str(
            LORA_ADAPTERS_DIR / f"{version.version_tag}-dpo"
        )
        training_args = TrainingArguments(
            output_dir=dpo_output,
            num_train_epochs=hp.get("num_epochs", 1),
            per_device_train_batch_size=hp.get("batch_size", 2),
            gradient_accumulation_steps=hp.get("gradient_accumulation_steps", 4),
            learning_rate=hp.get("learning_rate", 5e-5),
            warmup_ratio=0.1,
            logging_steps=10,
            save_strategy="epoch",
            fp16=True,
            report_to="none",
            remove_unused_columns=False,
        )

        trainer = DPOTrainer(
            model=model,
            ref_model=ref_model,
            args=training_args,
            train_dataset=dataset,
            tokenizer=tokenizer,
            peft_config=lora_config,
            beta=0.1,  # DPO temperature parameter
            max_length=hp.get("max_seq_length", 2048),
            max_prompt_length=512,
        )

        logger.info("Starting DPO training...")
        train_result = trainer.train()

        trainer.save_model(dpo_output)
        tokenizer.save_pretrained(dpo_output)

        # Update adapter path to DPO output
        version.lora_adapter_path = dpo_output

        dpo_metrics = {
            "dpo_loss": train_result.training_loss,
            "dpo_runtime": train_result.metrics.get("train_runtime"),
        }
        if version.eval_metrics:
            version.eval_metrics.update(dpo_metrics)
        else:
            version.eval_metrics = dpo_metrics

        logger.info(
            "DPO training complete — loss=%.4f, adapter saved to %s",
            train_result.training_loss,
            dpo_output,
        )

    # ═══════════════════════════════════════════
    # Phase 4: Model Deployment
    # ═══════════════════════════════════════════

    async def activate_version(
        self, version_id: uuid.UUID, db: AsyncSession
    ) -> dict:
        """
        Activate a model version — deactivate all others, set this one active.
        The CritiqueService will pick up the new adapter on next call.
        """
        # Deactivate all
        await db.execute(
            update(ModelVersion).values(is_active=False)
        )

        # Activate target
        result = await db.execute(
            select(ModelVersion).where(ModelVersion.id == version_id)
        )
        version = result.scalar_one_or_none()
        if not version:
            return {"status": "error", "message": "Version not found"}

        if version.status != "completed":
            return {
                "status": "error",
                "message": f"Cannot activate version in '{version.status}' state",
            }

        version.is_active = True
        await db.commit()

        logger.info("Activated model version: %s (%s)", version.version_tag, version.id)
        return {
            "status": "activated",
            "version_tag": version.version_tag,
            "adapter_path": version.lora_adapter_path,
        }

    # ═══════════════════════════════════════════
    # Status & Stats
    # ═══════════════════════════════════════════

    async def get_training_status(self, db: AsyncSession) -> dict:
        """Get overall training pipeline status."""
        # Active model
        active_result = await db.execute(
            select(ModelVersion).where(ModelVersion.is_active == True)
        )
        active = active_result.scalar_one_or_none()

        # Pending pairs count
        pairs_result = await db.execute(
            select(func.count(TrainingPair.id)).where(
                TrainingPair.status == "pending"
            )
        )
        pending_pairs = pairs_result.scalar() or 0

        # Total pairs
        total_pairs_result = await db.execute(
            select(func.count(TrainingPair.id))
        )
        total_pairs = total_pairs_result.scalar() or 0

        # Total approved questions (SFT candidates)
        sft_result = await db.execute(
            select(func.count(Question.id)).where(
                Question.vetting_status == "approved",
                Question.is_latest == True,
            )
        )
        total_sft_candidates = sft_result.scalar() or 0

        # Latest job
        job_result = await db.execute(
            select(TrainingJob)
            .order_by(TrainingJob.created_at.desc())
            .limit(1)
        )
        latest_job = job_result.scalar_one_or_none()

        # Version count
        version_count_result = await db.execute(
            select(func.count(ModelVersion.id))
        )
        version_count = version_count_result.scalar() or 0

        return {
            "active_version": {
                "version_tag": active.version_tag,
                "base_model": active.base_model,
                "training_method": active.training_method,
                "eval_metrics": active.eval_metrics,
                "adapter_path": active.lora_adapter_path,
            } if active else None,
            "pipeline": {
                "pending_dpo_pairs": pending_pairs,
                "total_dpo_pairs": total_pairs,
                "total_sft_candidates": total_sft_candidates,
                "total_model_versions": version_count,
            },
            "latest_job": {
                "id": str(latest_job.id),
                "type": latest_job.job_type,
                "status": latest_job.status,
                "samples": latest_job.training_samples,
                "current_epoch": latest_job.current_epoch,
                "total_epochs": latest_job.total_epochs,
                "loss": latest_job.current_loss or latest_job.final_loss,
                "created_at": latest_job.created_at.isoformat() if latest_job.created_at else None,
                "error": latest_job.error_message,
            } if latest_job else None,
        }

    # ═══════════════════════════════════════════
    # Helpers
    # ═══════════════════════════════════════════

    @staticmethod
    def _build_sft_instruction(q: Question) -> str:
        """Build the instruction string for an SFT sample."""
        parts = [f"Generate a {q.question_type or 'question'}"]
        if q.difficulty_level:
            parts.append(f"at {q.difficulty_level} difficulty")
        if q.bloom_taxonomy_level:
            parts.append(f"targeting {q.bloom_taxonomy_level} level of Bloom's taxonomy")
        if q.marks:
            parts.append(f"worth {q.marks} marks")
        return " ".join(parts) + "."

    @staticmethod
    def _build_sft_output(q: Question) -> str:
        """Build the output string for an SFT sample."""
        parts = [q.question_text]
        if q.options:
            for i, opt in enumerate(q.options):
                parts.append(f"{chr(65 + i)}) {opt}")
        if q.correct_answer:
            parts.append(f"\nAnswer: {q.correct_answer}")
        if q.explanation:
            parts.append(f"\nExplanation: {q.explanation}")
        return "\n".join(parts)

    # ═══════════════════════════════════════════
    # Phase 5: Rejection Pattern Learning
    # ═══════════════════════════════════════════

    async def get_rejection_patterns(
        self,
        db: AsyncSession,
        subject_id: Optional[uuid.UUID] = None,
        topic_id: Optional[uuid.UUID] = None,
        limit: int = 50,
    ) -> dict:
        """
        Aggregate rejection patterns from vetting logs to learn what reviewers
        commonly reject and why. Returns structured data that can be injected
        into generation prompts as negative-example guidance.
        """
        from collections import Counter

        query = (
            select(VettingLog)
            .where(VettingLog.decision == "reject")
            .order_by(VettingLog.created_at.desc())
            .limit(limit)
        )

        # Filter by subject/topic via explicit join on Question
        if subject_id or topic_id:
            query = query.join(Question, VettingLog.question_id == Question.id)
            if subject_id:
                query = query.where(Question.subject_id == subject_id)
            if topic_id:
                query = query.where(Question.topic_id == topic_id)

        result = await db.execute(query)
        logs = result.scalars().all()

        if not logs:
            return {"patterns": [], "summary": "", "count": 0}

        # Aggregate rejection reasons
        reason_counter: Counter = Counter()
        feedback_samples: list[str] = []
        rejection_examples: list[dict] = []

        for log in logs:
            if log.rejection_reasons:
                for r in log.rejection_reasons:
                    reason_counter[r] += 1
            if log.feedback and len(feedback_samples) < 10:
                feedback_samples.append(log.feedback)
            if log.original_text and len(rejection_examples) < 5:
                rejection_examples.append({
                    "question": log.original_text[:200],
                    "reasons": log.rejection_reasons or [],
                    "feedback": (log.feedback or "")[:200],
                })

        # Build a natural language summary for prompt injection
        top_reasons = reason_counter.most_common(10)
        summary_parts = []
        if top_reasons:
            summary_parts.append("Common rejection reasons (avoid these patterns):")
            for reason, count in top_reasons:
                summary_parts.append(f"  - {reason} ({count} occurrences)")
        if feedback_samples:
            summary_parts.append("\nRecent reviewer feedback:")
            for fb in feedback_samples[:5]:
                summary_parts.append(f"  - \"{fb[:150]}\"")

        return {
            "patterns": [{"reason": r, "count": c} for r, c in top_reasons],
            "examples": rejection_examples,
            "summary": "\n".join(summary_parts),
            "count": len(logs),
        }

    async def build_rejection_avoidance_prompt(
        self,
        db: AsyncSession,
        subject_id: Optional[uuid.UUID] = None,
        topic_id: Optional[uuid.UUID] = None,
    ) -> str:
        """
        Build a prompt supplement that teaches the LLM to avoid previously
        rejected patterns. Inject this into question generation prompts.
        """
        patterns = await self.get_rejection_patterns(db, subject_id, topic_id)
        if not patterns["count"]:
            return ""

        prompt = "\n\n--- QUALITY GUIDELINES (learned from reviewer feedback) ---\n"
        prompt += patterns["summary"]
        if patterns["examples"]:
            prompt += "\n\nExamples of REJECTED questions (DO NOT generate similar):\n"
            for ex in patterns["examples"][:3]:
                prompt += f"  REJECTED: \"{ex['question']}\"\n"
                if ex["reasons"]:
                    prompt += f"    Reasons: {', '.join(ex['reasons'])}\n"
        prompt += "\n--- END QUALITY GUIDELINES ---\n"
        return prompt
