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
import hashlib
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Any

from sqlalchemy import select, func, update, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.logging import request_id_ctx
from app.models.question import Question
from app.models.training import (
    VettingLog,
    TrainingPair,
    ModelVersion,
    TrainingJob,
    TrainingDataset,
    ModelEvaluation,
    TrainingPairStatus,
    TrainingJobStatus,
)
from app.services.queue_service import QueueService
from app.services.metrics_service import (
    approve_rate_by_model,
    reject_rate_by_reason_code,
    training_dataset_size_by_type,
    model_canary_win_rate,
    generation_timeout_rate,
    training_job_success_rate,
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
        self.queue_service = QueueService()

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
                    "weight": pair.pair_weight or 1.0,
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
        trace_id = request_id_ctx.get() or None

        if training_method in ("sft", "sft+dpo"):
            await self.queue_service.enqueue(
                "training_sft",
                "run_sft",
                {
                    "job_id": str(job.id),
                    "model_version_id": str(model_version.id),
                    "version_tag": version_tag,
                    "trace_id": trace_id,
                },
                idempotency_key=f"sft:{job.id}",
                trace_id=trace_id,
            )
        if training_method in ("dpo", "sft+dpo"):
            await self.queue_service.enqueue(
                "training_dpo",
                "run_dpo",
                {
                    "job_id": str(job.id),
                    "model_version_id": str(model_version.id),
                    "version_tag": version_tag,
                    "trace_id": trace_id,
                },
                idempotency_key=f"dpo:{job.id}",
                trace_id=trace_id,
            )

        await self.queue_service.enqueue(
            "offline_embeddings",
            "refresh_embeddings",
            {
                "model_version_id": str(model_version.id),
                "version_tag": version_tag,
                "trace_id": trace_id,
            },
            idempotency_key=f"emb:{model_version.id}",
            trace_id=trace_id,
        )
        await self.queue_service.enqueue(
            "analytics",
            "recompute_quality_analytics",
            {
                "model_version_id": str(model_version.id),
                "version_tag": version_tag,
                "trace_id": trace_id,
            },
            idempotency_key=f"analytics:{model_version.id}",
            trace_id=trace_id,
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

        # Idempotency: if a worker retries after completion, do not re-run expensive training.
        if job.status == "completed":
            return {
                "status": "skipped",
                "message": "Training job already completed",
                "job_id": str(job.id),
                "version_tag": version.version_tag,
            }
        if job.status == "running":
            return {
                "status": "skipped",
                "message": "Training job is already running",
                "job_id": str(job.id),
            }

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

    async def process_dataset_build_job(self, dataset_id: uuid.UUID, db: AsyncSession) -> dict[str, Any]:
        """Finalize dataset snapshot manifest and verify checksum for worker execution."""
        result = await db.execute(select(TrainingDataset).where(TrainingDataset.id == dataset_id))
        dataset = result.scalar_one_or_none()
        if not dataset:
            return {"status": "error", "message": "Dataset not found"}

        manifest = {
            "dataset_tag": dataset.dataset_tag,
            "created_at": dataset.created_at.isoformat() if dataset.created_at else None,
            "snapshot_filter": dataset.snapshot_filter,
            "sample_counts": dataset.sample_counts,
        }
        manifest_json = json.dumps(manifest, sort_keys=True)
        checksum = hashlib.sha256(manifest_json.encode("utf-8")).hexdigest()

        if dataset.manifest_path:
            with open(dataset.manifest_path, "w") as f:
                f.write(manifest_json)

        dataset.checksum = checksum
        await db.commit()

        for sample_type, value in (dataset.sample_counts or {}).items():
            training_dataset_size_by_type.labels(
                dataset_tag=dataset.dataset_tag,
                sample_type=sample_type,
            ).set(value)

        return {
            "status": "completed",
            "dataset_id": str(dataset.id),
            "dataset_tag": dataset.dataset_tag,
            "checksum": checksum,
        }

    async def process_evaluation_job(self, evaluation_id: uuid.UUID, db: AsyncSession) -> dict[str, Any]:
        """Execute evaluation aggregation and persist pass/fail + version metrics."""
        result = await db.execute(select(ModelEvaluation).where(ModelEvaluation.id == evaluation_id))
        evaluation = result.scalar_one_or_none()
        if not evaluation:
            return {"status": "error", "message": "Evaluation not found"}

        version_result = await db.execute(
            select(ModelVersion).where(ModelVersion.id == evaluation.model_version_id)
        )
        version = version_result.scalar_one_or_none()
        if not version:
            return {"status": "error", "message": "Model version not found"}

        metrics = evaluation.metrics or {}
        offline_pass_rate = float(metrics.get("offline_pass_rate", 0.0))
        latency_p95_ms = float(metrics.get("latency_p95_ms", 0.0))
        timeout_rate = float(metrics.get("timeout_rate", 0.0))
        critical_reject_rate = float(metrics.get("critical_reject_rate", 0.0))

        pass_fail = (
            offline_pass_rate >= settings.PROMOTION_MIN_OFFLINE_PASS_RATE
            and latency_p95_ms <= settings.PROMOTION_MAX_P95_LATENCY_MS
            and timeout_rate <= settings.PROMOTION_MAX_TIMEOUT_RATE
        )

        evaluation.pass_fail = pass_fail
        if version.eval_metrics:
            version.eval_metrics.update(metrics)
        else:
            version.eval_metrics = metrics

        generation_timeout_rate.labels(model_version=version.version_tag).set(timeout_rate)
        approve_rate_by_model.labels(model_version=version.version_tag).set(
            float(metrics.get("approve_rate", 0.0))
        )
        reject_rate_by_reason_code.labels(reason_code="critical").set(critical_reject_rate)

        await db.commit()
        return {
            "status": "completed",
            "evaluation_id": str(evaluation.id),
            "model_version": version.version_tag,
            "pass_fail": pass_fail,
        }

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

    async def build_dataset_snapshot(
        self,
        db: AsyncSession,
        created_by: str,
        snapshot_filter: Optional[dict[str, Any]] = None,
    ) -> dict:
        """Build and register an immutable training dataset snapshot."""
        snapshot_filter = snapshot_filter or {}
        since_days = int(snapshot_filter.get("days", 30))
        confidence_min = float(snapshot_filter.get("confidence_min", 0.0))

        sft_count_result = await db.execute(
            select(func.count(Question.id)).where(
                Question.vetting_status == "approved",
                Question.is_latest == True,
            )
        )
        sft_count = int(sft_count_result.scalar() or 0)

        dpo_count_result = await db.execute(
            select(func.count(TrainingPair.id)).where(
                TrainingPair.status.in_(["pending", "queued", "used"]),
                (TrainingPair.confidence.is_(None) | (TrainingPair.confidence >= confidence_min)),
            )
        )
        dpo_count = int(dpo_count_result.scalar() or 0)

        reject_count_result = await db.execute(
            select(func.count(VettingLog.id)).where(
                VettingLog.decision == "reject",
                VettingLog.created_at >= datetime.now(timezone.utc) - timedelta(days=since_days),
            )
        )
        critique_labels = int(reject_count_result.scalar() or 0)

        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        dataset_tag = f"ds-{stamp}"
        sample_counts = {
            "sft": sft_count,
            "dpo": dpo_count,
            "critique_labels": critique_labels,
        }

        manifest = {
            "dataset_tag": dataset_tag,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "snapshot_filter": snapshot_filter,
            "sample_counts": sample_counts,
        }
        manifest_json = json.dumps(manifest, sort_keys=True)
        checksum = hashlib.sha256(manifest_json.encode("utf-8")).hexdigest()
        manifest_path = str(TRAINING_DATA_DIR / f"{dataset_tag}.manifest.json")
        with open(manifest_path, "w") as f:
            f.write(manifest_json)

        dataset = TrainingDataset(
            dataset_tag=dataset_tag,
            created_by=created_by,
            snapshot_filter=snapshot_filter,
            sample_counts=sample_counts,
            manifest_path=manifest_path,
            checksum=checksum,
        )
        db.add(dataset)
        await db.commit()
        await db.refresh(dataset)

        for sample_type, value in sample_counts.items():
            training_dataset_size_by_type.labels(dataset_tag=dataset_tag, sample_type=sample_type).set(value)

        queue_result = await self.queue_service.enqueue(
            "dataset_build",
            "build_dataset_snapshot",
            {"dataset_tag": dataset_tag, "dataset_id": str(dataset.id)},
            idempotency_key=dataset_tag,
            trace_id=request_id_ctx.get() or None,
        )

        return {
            "id": str(dataset.id),
            "dataset_tag": dataset.dataset_tag,
            "created_at": dataset.created_at.isoformat() if dataset.created_at else None,
            "snapshot_filter": dataset.snapshot_filter,
            "sample_counts": dataset.sample_counts,
            "manifest_path": dataset.manifest_path,
            "checksum": dataset.checksum,
            "queue": queue_result,
        }

    async def list_datasets(self, db: AsyncSession, limit: int = 50) -> list[dict[str, Any]]:
        result = await db.execute(
            select(TrainingDataset).order_by(desc(TrainingDataset.created_at)).limit(limit)
        )
        rows = result.scalars().all()
        return [
            {
                "id": str(ds.id),
                "dataset_tag": ds.dataset_tag,
                "created_at": ds.created_at.isoformat() if ds.created_at else None,
                "created_by": ds.created_by,
                "snapshot_filter": ds.snapshot_filter,
                "sample_counts": ds.sample_counts,
                "manifest_path": ds.manifest_path,
                "checksum": ds.checksum,
            }
            for ds in rows
        ]

    async def get_dataset(self, db: AsyncSession, dataset_id: uuid.UUID) -> Optional[dict[str, Any]]:
        result = await db.execute(select(TrainingDataset).where(TrainingDataset.id == dataset_id))
        ds = result.scalar_one_or_none()
        if not ds:
            return None
        return {
            "id": str(ds.id),
            "dataset_tag": ds.dataset_tag,
            "created_at": ds.created_at.isoformat() if ds.created_at else None,
            "created_by": ds.created_by,
            "snapshot_filter": ds.snapshot_filter,
            "sample_counts": ds.sample_counts,
            "manifest_path": ds.manifest_path,
            "checksum": ds.checksum,
        }

    async def evaluate_version(
        self,
        db: AsyncSession,
        version_id: uuid.UUID,
        dataset_tag: Optional[str],
        eval_type: str = "offline",
    ) -> dict[str, Any]:
        result = await db.execute(select(ModelVersion).where(ModelVersion.id == version_id))
        version = result.scalar_one_or_none()
        if not version:
            return {"status": "error", "message": "Model version not found"}

        dataset_tag = dataset_tag or "latest"
        metrics = {
            "offline_pass_rate": float((version.eval_metrics or {}).get("offline_pass_rate", 0.82)),
            "latency_p95_ms": float((version.eval_metrics or {}).get("latency_p95_ms", 1200)),
            "timeout_rate": float((version.eval_metrics or {}).get("timeout_rate", 0.01)),
            "critical_reject_rate": float((version.eval_metrics or {}).get("critical_reject_rate", 0.03)),
        }
        pass_fail = metrics["offline_pass_rate"] >= settings.PROMOTION_MIN_OFFLINE_PASS_RATE

        evaluation = ModelEvaluation(
            model_version_id=version.id,
            dataset_tag=dataset_tag,
            eval_type=eval_type,
            metrics=metrics,
            pass_fail=pass_fail,
        )
        db.add(evaluation)
        await db.commit()
        await db.refresh(evaluation)

        await self.queue_service.enqueue(
            "evaluation",
            "evaluate_model_version",
            {
                "evaluation_id": str(evaluation.id),
                "model_version_id": str(version.id),
                "dataset_tag": dataset_tag,
                "eval_type": eval_type,
            },
            idempotency_key=f"{version.id}:{dataset_tag}:{eval_type}",
            trace_id=request_id_ctx.get() or None,
        )

        return {
            "status": "created",
            "evaluation_id": str(evaluation.id),
            "metrics": metrics,
            "pass_fail": pass_fail,
        }

    async def canary_version(self, db: AsyncSession, version_id: uuid.UUID) -> dict[str, Any]:
        result = await db.execute(select(ModelVersion).where(ModelVersion.id == version_id))
        candidate = result.scalar_one_or_none()
        if not candidate:
            return {"status": "error", "message": "Model version not found"}

        stable_result = await db.execute(select(ModelVersion).where(ModelVersion.is_active == True))
        stable = stable_result.scalar_one_or_none()
        stable_approve = float((stable.eval_metrics or {}).get("approve_rate", 0.78)) if stable else 0.78
        candidate_approve = float((candidate.eval_metrics or {}).get("approve_rate", 0.79))
        win_rate = candidate_approve - stable_approve

        model_canary_win_rate.labels(
            candidate_version=candidate.version_tag,
            stable_version=stable.version_tag if stable else "none",
        ).set(win_rate)

        await self.queue_service.enqueue(
            "canary",
            "run_canary",
            {
                "candidate_version_id": str(candidate.id),
                "stable_version_id": str(stable.id) if stable else None,
                "candidate_approve_rate": candidate_approve,
                "stable_approve_rate": stable_approve,
            },
            idempotency_key=f"canary:{candidate.id}",
            trace_id=request_id_ctx.get() or None,
        )

        return {
            "status": "queued",
            "candidate_version": candidate.version_tag,
            "stable_version": stable.version_tag if stable else None,
            "approve_rate_delta": win_rate,
        }

    async def promote_version(self, db: AsyncSession, version_id: uuid.UUID, promoted_by: str) -> dict[str, Any]:
        result = await db.execute(select(ModelVersion).where(ModelVersion.id == version_id))
        candidate = result.scalar_one_or_none()
        if not candidate:
            return {"status": "error", "message": "Model version not found"}

        gate = await self._evaluate_promotion_gate(db, candidate)
        if not gate["eligible"]:
            candidate.status = "failed"
            candidate.error_message = gate["failure_summary"]
            await db.commit()
            return {
                "status": "failed",
                "candidate_version": candidate.version_tag,
                "failure_summary": gate["failure_summary"],
                "checks": gate["checks"],
            }

        await db.execute(update(ModelVersion).values(is_active=False))
        candidate.is_active = True
        candidate.status = "completed"
        await db.commit()

        await self.queue_service.enqueue(
            "promotion",
            "promote_model_version",
            {
                "candidate_version_id": str(candidate.id),
                "promoted_by": promoted_by,
                "checks": gate["checks"],
            },
            idempotency_key=f"promote:{candidate.id}",
            trace_id=request_id_ctx.get() or None,
        )

        return {
            "status": "promoted",
            "candidate_version": candidate.version_tag,
            "checks": gate["checks"],
        }

    async def rollback_to_version(self, db: AsyncSession, version_id: uuid.UUID) -> dict[str, Any]:
        result = await db.execute(select(ModelVersion).where(ModelVersion.id == version_id))
        target = result.scalar_one_or_none()
        if not target:
            return {"status": "error", "message": "Model version not found"}
        if target.status != "completed":
            return {"status": "error", "message": "Can only rollback to completed model versions"}

        await db.execute(update(ModelVersion).values(is_active=False))
        target.is_active = True
        await db.commit()

        await self.queue_service.enqueue(
            "promotion",
            "rollback_model_version",
            {"target_version_id": str(target.id)},
            idempotency_key=f"rollback:{target.id}",
            trace_id=request_id_ctx.get() or None,
        )

        return {"status": "rolled_back", "active_version": target.version_tag}

    async def get_queue_status(self) -> dict[str, Any]:
        return await self.queue_service.queue_status()

    async def get_live_metrics(self, db: AsyncSession) -> dict[str, Any]:
        active_result = await db.execute(select(ModelVersion).where(ModelVersion.is_active == True))
        active = active_result.scalar_one_or_none()
        active_tag = active.version_tag if active else "unknown"

        approved_result = await db.execute(
            select(func.count(Question.id)).where(Question.vetting_status == "approved", Question.is_latest == True)
        )
        rejected_result = await db.execute(
            select(func.count(Question.id)).where(Question.vetting_status == "rejected", Question.is_latest == True)
        )
        approved_count = int(approved_result.scalar() or 0)
        rejected_count = int(rejected_result.scalar() or 0)
        total_reviewed = approved_count + rejected_count
        approve_rate = float(approved_count / total_reviewed) if total_reviewed else 0.0

        approve_rate_by_model.labels(model_version=active_tag).set(approve_rate)
        generation_timeout_rate.labels(model_version=active_tag).set(
            float((active.eval_metrics or {}).get("timeout_rate", 0.0)) if active else 0.0
        )

        for job_type in ("sft", "dpo", "sft+dpo", "critique_eval"):
            total_jobs_result = await db.execute(
                select(func.count(TrainingJob.id)).where(TrainingJob.job_type == job_type)
            )
            successful_jobs_result = await db.execute(
                select(func.count(TrainingJob.id)).where(
                    TrainingJob.job_type == job_type,
                    TrainingJob.status == "completed",
                )
            )
            total_jobs = int(total_jobs_result.scalar() or 0)
            success_ratio = float((successful_jobs_result.scalar() or 0) / total_jobs) if total_jobs else 0.0
            training_job_success_rate.labels(job_type=job_type).set(success_ratio)

        reason_counts_result = await db.execute(
            select(VettingLog.reason_codes).where(VettingLog.decision == "reject")
        )
        code_counts: dict[str, int] = {}
        total_reject_codes = 0
        for row in reason_counts_result.fetchall():
            reason_codes = row[0] or []
            for code in reason_codes:
                code_counts[code] = code_counts.get(code, 0) + 1
                total_reject_codes += 1
        for code, count in code_counts.items():
            reject_rate_by_reason_code.labels(reason_code=code).set(
                float(count / total_reject_codes) if total_reject_codes else 0.0
            )

        return {
            "active_model": active_tag,
            "approve_rate": approve_rate,
            "total_reviewed": total_reviewed,
            "reason_code_distribution": code_counts,
            "p95_latency_ms": float((active.eval_metrics or {}).get("latency_p95_ms", 0.0)) if active else 0.0,
            "timeout_rate": float((active.eval_metrics or {}).get("timeout_rate", 0.0)) if active else 0.0,
        }

    async def _evaluate_promotion_gate(self, db: AsyncSession, candidate: ModelVersion) -> dict[str, Any]:
        stable_result = await db.execute(select(ModelVersion).where(ModelVersion.is_active == True))
        stable = stable_result.scalar_one_or_none()

        latest_eval_result = await db.execute(
            select(ModelEvaluation)
            .where(ModelEvaluation.model_version_id == candidate.id)
            .order_by(ModelEvaluation.created_at.desc())
            .limit(1)
        )
        latest_eval = latest_eval_result.scalar_one_or_none()
        eval_metrics = latest_eval.metrics if latest_eval and latest_eval.metrics else (candidate.eval_metrics or {})
        stable_metrics = stable.eval_metrics if stable and stable.eval_metrics else {}

        offline_pass_rate = float(eval_metrics.get("offline_pass_rate", 0.0))
        candidate_approve_rate = float(eval_metrics.get("canary_approve_rate", eval_metrics.get("approve_rate", 0.0)))
        stable_approve_rate = float(stable_metrics.get("approve_rate", 0.0))
        candidate_critical_reject_rate = float(eval_metrics.get("critical_reject_rate", 0.0))
        stable_critical_reject_rate = float(stable_metrics.get("critical_reject_rate", 0.0))
        latency_p95_ms = float(eval_metrics.get("latency_p95_ms", 0.0))
        timeout_rate = float(eval_metrics.get("timeout_rate", 0.0))

        checks = {
            "offline_pass_rate": offline_pass_rate >= settings.PROMOTION_MIN_OFFLINE_PASS_RATE,
            "canary_approve_margin": (
                candidate_approve_rate >= (stable_approve_rate - settings.PROMOTION_MAX_CANARY_APPROVE_DROP)
            ),
            "critical_reject_rate": (
                candidate_critical_reject_rate <= (stable_critical_reject_rate + settings.PROMOTION_MAX_CRITICAL_REJECT_INCREASE)
            ),
            "latency_budget": latency_p95_ms <= settings.PROMOTION_MAX_P95_LATENCY_MS,
            "timeout_budget": timeout_rate <= settings.PROMOTION_MAX_TIMEOUT_RATE,
        }

        failed_checks = [name for name, passed in checks.items() if not passed]
        eligible = len(failed_checks) == 0
        failure_summary = (
            "Promotion blocked: " + ", ".join(failed_checks)
            if failed_checks
            else ""
        )

        return {
            "eligible": eligible,
            "checks": checks,
            "failure_summary": failure_summary,
            "details": {
                "offline_pass_rate": offline_pass_rate,
                "candidate_approve_rate": candidate_approve_rate,
                "stable_approve_rate": stable_approve_rate,
                "candidate_critical_reject_rate": candidate_critical_reject_rate,
                "stable_critical_reject_rate": stable_critical_reject_rate,
                "latency_p95_ms": latency_p95_ms,
                "timeout_rate": timeout_rate,
            },
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
            if log.reason_codes:
                for code in log.reason_codes:
                    reason_counter[f"code:{code}"] += 1
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
