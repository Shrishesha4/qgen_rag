"""
TrainingService — SFT / DPO / LoRA fine-tuning pipeline.

Phase 4 of the Dual-Engine self-correcting loop:
  1. SFT Data Prep: Aggregate approved questions into instruction-tuning JSONL.
  2. DPO Data Prep: Build (prompt, chosen, rejected) triplets from vetting edits.
  3. Fine-Tuning Execution: LoRA-based fine-tuning of the local DeepSeek model.
  4. Model Version Management: Track adapter lineage and active deployment.

This service runs as a background pipeline, independent of the web request cycle.
"""

import asyncio
import json
import logging
import math
import os
import re
import time
import uuid
import hashlib
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Any, Iterable

from sqlalchemy import select, func, update, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.logging import request_id_ctx
from app.models.question import Question
from app.models.subject import Subject, Topic
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
from app.services.llm_service import LLMService, LLMError


logger = logging.getLogger(__name__)

# ── Configurable paths ──
TRAINING_DATA_DIR = Path(settings.TRAINING_DATA_DIR)
LORA_ADAPTERS_DIR = Path(settings.LORA_ADAPTERS_DIR)
BASE_MODEL_NAME = settings.TRAINING_BASE_MODEL

SYNTHETIC_DPO_MIN_CONFIDENCE = float(
    os.environ.get("SYNTHETIC_DPO_MIN_CONFIDENCE", "0.85")
)
SYNTHETIC_DPO_PAIR_WEIGHT = float(
    os.environ.get("SYNTHETIC_DPO_PAIR_WEIGHT", "0.35")
)
MIN_DPO_EXPORT_PAIRS = int(os.environ.get("MIN_DPO_EXPORT_PAIRS", "32"))
SYNTHETIC_DPO_PAIR_TYPE = "synthetic_sft"
DEFAULT_TRAINING_WINDOW_DAYS = int(
    os.environ.get("DEFAULT_TRAINING_WINDOW_DAYS", "30")
)
DEFAULT_MAX_SFT_SAMPLES = int(os.environ.get("DEFAULT_MAX_SFT_SAMPLES", "10000"))
DEFAULT_MAX_DPO_SAMPLES = int(os.environ.get("DEFAULT_MAX_DPO_SAMPLES", "5000"))
DEFAULT_SAMPLE_STRATEGY = os.environ.get("DEFAULT_SAMPLE_STRATEGY", "recent_first")
MIN_SOURCE_CONTEXT_LENGTH = int(os.environ.get("MIN_SOURCE_CONTEXT_LENGTH", "50"))
VALID_SAMPLE_STRATEGIES = {"recent_first", "stratified", "random"}
REFERENCE_DATASET_PREFIXES = {
        "training": "ds",
        "evaluation": "eval",
        "holdout": "holdout",
        "anchor": "anchor",
}
REFERENCE_DATASET_ROLES = tuple(REFERENCE_DATASET_PREFIXES.keys())

STRICT_EVAL_SYSTEM_PROMPT = """You are a strict evaluator for university exam-question generation systems.

Evaluate the candidate response against the requested specification, topic, difficulty, and source context.
Return ONLY JSON with this exact schema:
{
    "format_correctness": <float 0 to 1>,
    "difficulty_alignment": <float 0 to 1>,
    "topic_relevance": <float 0 to 1>,
    "hallucination_error_rate": <float 0 to 1>,
    "accept": <true or false>,
    "notes": ["short issue or strength notes"]
}

Acceptance rule: true only when the response is well-formed, on-topic, difficulty-aligned, and does not introduce unsupported claims.
Do not include any prose outside JSON."""

STRICT_EVAL_USER_TEMPLATE = """Requested question contract:
Type: {question_type}
Difficulty: {difficulty}
Topic: {topic}

Source context:
{source_context}

Reference accepted output:
{reference_output}

Candidate model output:
{candidate_output}
"""


class TrainingService:
    """
    Orchestrates the full training pipeline:
      prepare_sft_data → prepare_dpo_data → launch_training → deploy_model
    """

    def __init__(self):
        self.training_data_dir = self._resolve_writable_dir(
            TRAINING_DATA_DIR,
            Path("./.data/training_data"),
            "training data",
        )
        self.lora_adapters_dir = self._resolve_writable_dir(
            LORA_ADAPTERS_DIR,
            Path("./.data/lora_adapters"),
            "lora adapters",
        )
        self.queue_service = QueueService()

    @staticmethod
    def _resolve_writable_dir(primary: Path, fallback: Path, label: str) -> Path:
        """Resolve a writable directory, falling back if the primary path is not writable."""
        try:
            primary.mkdir(parents=True, exist_ok=True)
            probe_file = primary / ".write_probe"
            with open(probe_file, "w") as f:
                f.write("ok")
            probe_file.unlink(missing_ok=True)
            return primary
        except (PermissionError, OSError):
            logger.warning("Primary %s directory not writable (%s). Using fallback: %s", label, primary, fallback)
            fallback.mkdir(parents=True, exist_ok=True)
            probe_file = fallback / ".write_probe"
            with open(probe_file, "w") as f:
                f.write("ok")
            probe_file.unlink(missing_ok=True)
            return fallback

    @staticmethod
    def _resolve_model_source(model_ref: str) -> str:
        """Resolve a model reference to a local directory when available."""
        normalized = (model_ref or "").strip()
        if not normalized:
            return model_ref

        direct_path = Path(normalized).expanduser()
        if direct_path.exists():
            return str(direct_path.resolve())

        repo_key = normalized.replace("/", "__")
        backend_root = Path(__file__).resolve().parents[2]
        candidates = [
            backend_root / "models" / repo_key,
            backend_root / "models" / normalized,
            Path.cwd() / "models" / repo_key,
            Path.cwd() / "models" / normalized,
        ]

        for candidate in candidates:
            if candidate.exists():
                return str(candidate.resolve())

        return model_ref

    @staticmethod
    def _normalize_dpo_prompt(prompt: Optional[str]) -> str:
        prompt_text = (prompt or "").replace("\r\n", "\n").strip()
        if prompt_text.endswith("### Response:"):
            return f"{prompt_text}\n"
        return f"{prompt_text}\n\n### Response:\n"

    @staticmethod
    def _normalize_dpo_completion(text: Optional[str]) -> str:
        return (text or "").replace("\r\n", "\n").strip()

    @staticmethod
    def _resolve_warmup_steps(
        hp: dict[str, Any],
        dataset_size: int,
        num_train_epochs: float,
        per_device_train_batch_size: int,
        gradient_accumulation_steps: int,
        max_steps: int,
    ) -> int:
        explicit_warmup_steps = hp.get("warmup_steps")
        if explicit_warmup_steps is not None:
            return max(0, int(explicit_warmup_steps))

        warmup_ratio = float(hp.get("warmup_ratio", 0.0) or 0.0)
        if max_steps > 0:
            total_steps = max_steps
        else:
            effective_batch_size = max(
                1,
                int(per_device_train_batch_size) * int(gradient_accumulation_steps),
            )
            steps_per_epoch = max(1, math.ceil(dataset_size / effective_batch_size))
            total_steps = max(1, math.ceil(float(num_train_epochs) * steps_per_epoch))

        return max(0, int(total_steps * warmup_ratio))

    @staticmethod
    def _distribution_from_rows(rows: list[tuple[Any, Any]]) -> dict[str, int]:
        distribution = {}
        for key, value in rows:
            label = str(key).strip() if key not in (None, "") else "unknown"
            distribution[label] = int(value or 0)
        return distribution

    @staticmethod
    def _named_distribution_from_rows(
        rows: list[tuple[Any, ...]],
        label_builder,
    ) -> dict[str, int]:
        distribution: dict[str, int] = {}
        for row in rows:
            if not row:
                continue
            *parts, count = row
            label = label_builder(*parts)
            distribution[label] = int(count or 0)
        return distribution

    @staticmethod
    def _round_metric(value: Optional[float]) -> Optional[float]:
        if value is None:
            return None
        return round(float(value), 4)

    @classmethod
    def _summarize_balance(
        cls,
        distribution: dict[str, int],
        expected_labels: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        total = int(sum(distribution.values()))
        observed = {key: value for key, value in distribution.items() if value > 0}
        shares = {
            key: round(value / total, 4)
            for key, value in observed.items()
        } if total else {}
        expected = expected_labels or sorted(observed.keys())
        present_labels = [label for label in expected if distribution.get(label, 0) > 0]
        missing_labels = [label for label in expected if distribution.get(label, 0) == 0]
        return {
            "distinct_count": len(observed),
            "distribution": distribution,
            "shares": shares,
            "coverage_ratio": round(len(present_labels) / len(expected), 4) if expected else None,
            "missing": missing_labels,
        }

    @staticmethod
    def _strip_choice_prefix(text: Optional[str]) -> str:
        cleaned = (text or "").strip()
        return re.sub(r"^\(?([A-Za-z]|\d+)\)?[\).:-]\s*", "", cleaned)

    @classmethod
    def _normalize_correct_answer(cls, answer: Optional[str], options: Optional[list[Any]]) -> str:
        answer_text = (answer or "").strip()
        if not answer_text:
            return ""
        normalized_answer = cls._strip_choice_prefix(answer_text)
        for index, option in enumerate(options or []):
            cleaned_option = cls._strip_choice_prefix(str(option))
            option_letter = chr(65 + index)
            if answer_text.upper() == option_letter or normalized_answer == cleaned_option:
                return f"{option_letter}. {cleaned_option}"
        return answer_text

    @classmethod
    def _build_sft_input(cls, q: Question) -> str:
        meta = q.generation_metadata if isinstance(q.generation_metadata, dict) else {}
        raw_response = meta.get("raw_response", {}) if isinstance(meta.get("raw_response"), dict) else {}
        topic_tags = list(getattr(q, "topic_tags", None) or [])
        if not topic_tags and raw_response.get("topic_tags"):
            topic_tags = [str(tag) for tag in raw_response.get("topic_tags", []) if tag]

        spec_lines = [
            f"Question Type: {q.question_type or 'mcq'}",
            f"Difficulty: {q.difficulty_level or 'unspecified'}",
            f"Bloom Level: {q.bloom_taxonomy_level or 'unspecified'}",
            f"Marks: {q.marks or 'unspecified'}",
        ]
        if topic_tags:
            spec_lines.append(f"Topic Tags: {', '.join(topic_tags[:6])}")
        if getattr(q, "course_outcome_mapping", None):
            spec_lines.append(
                "Course Outcome Mapping: "
                + json.dumps(q.course_outcome_mapping, ensure_ascii=False, sort_keys=True)
            )

        context = ""
        if isinstance(meta.get("context"), str):
            context = meta["context"].strip()
        elif isinstance(meta.get("source_info"), dict):
            sources = meta["source_info"].get("sources") or []
            snippets = [
                str(source.get("excerpt") or source.get("content") or "").strip()
                for source in sources
                if isinstance(source, dict)
            ]
            context = "\n\n".join(snippet for snippet in snippets if snippet)

        parts = [
            "Generate one high-quality university exam question that follows the specification and uses the supplied source context.",
            "Question Specification:\n" + "\n".join(spec_lines),
        ]
        if context:
            parts.append("Source Context:\n" + context[:3000])
        parts.append(
            "Return a complete final item with question text, options, correct answer, and explanation."
        )
        return "\n\n".join(parts)

    @staticmethod
    def _average_quality_signal(*values: Optional[float]) -> float:
        defined_values = [float(value) for value in values if value is not None]
        if not defined_values:
            return 0.0
        return float(sum(defined_values) / len(defined_values))

    @classmethod
    def _estimate_synthetic_dpo_confidence(
        cls,
        q: Question,
        review_quality: Optional[float] = None,
    ) -> float:
        base_score = cls._average_quality_signal(
            review_quality,
            q.generation_confidence,
            q.answerability_score,
            q.specificity_score,
            q.novelty_score,
        )
        structural_bonus = 0.0
        if q.question_text and q.question_text.strip():
            structural_bonus += 0.05
        if q.options and len(q.options) >= 4:
            structural_bonus += 0.05
        if q.correct_answer:
            structural_bonus += 0.05
        if q.explanation and q.explanation.strip():
            structural_bonus += 0.05
        return min(1.0, base_score + structural_bonus)

    @classmethod
    def _select_synthetic_rejected_answer(cls, q: Question) -> str:
        if not q.options:
            return ""

        normalized_correct = cls._normalize_correct_answer(q.correct_answer, q.options)
        correct_letter = (q.correct_answer or "").strip().upper()
        if len(correct_letter) != 1 or not correct_letter.isalpha():
            correct_letter = ""

        for index, option in enumerate(q.options):
            option_letter = chr(65 + index)
            candidate = f"{option_letter}. {cls._strip_choice_prefix(str(option))}"
            if candidate != normalized_correct and option_letter != correct_letter:
                return candidate
        return ""

    @classmethod
    def _build_synthetic_dpo_rejected(cls, q: Question) -> str:
        wrong_answer = cls._select_synthetic_rejected_answer(q)
        if not wrong_answer or not q.question_text or not q.question_text.strip():
            return ""

        parts = ["Question:", q.question_text.strip()]
        if q.options:
            parts.append("")
            parts.append("Options:")
            for i, opt in enumerate(q.options):
                parts.append(f"{chr(65 + i)}. {cls._strip_choice_prefix(str(opt))}")
        parts.append("")
        parts.append(f"Correct Answer: {wrong_answer}")
        parts.append("")
        parts.append(
            "Explanation: This answer is plausible at a glance, but the reasoning is incomplete and not grounded in the source context."
        )
        return "\n".join(parts)

    async def _generate_synthetic_dpo_records(
        self,
        db: AsyncSession,
        since: datetime,
        limit: Optional[int] = None,
        exclude_question_ids: Optional[set[uuid.UUID]] = None,
    ) -> list[dict[str, Any]]:
        approval_quality = (
            select(
                VettingLog.question_id.label("question_id"),
                func.max(VettingLog.quality_score).label("review_quality"),
            )
            .where(VettingLog.decision == "approve")
            .group_by(VettingLog.question_id)
            .subquery()
        )

        query = (
            select(Question, approval_quality.c.review_quality)
            .outerjoin(approval_quality, approval_quality.c.question_id == Question.id)
            .where(
                Question.vetting_status == "approved",
                Question.is_latest == True,
                Question.vetted_at >= since,
            )
            .order_by(Question.vetted_at.asc())
        )
        result = await db.execute(query)

        synthetic_records: list[dict[str, Any]] = []
        excluded = exclude_question_ids or set()
        for question, review_quality in result.all():
            if question.id in excluded:
                continue

            confidence = self._estimate_synthetic_dpo_confidence(question, review_quality)
            if confidence < SYNTHETIC_DPO_MIN_CONFIDENCE:
                continue

            prompt = self._normalize_dpo_prompt(self._build_sft_input(question))
            chosen = self._normalize_dpo_completion(self._build_sft_output(question))
            rejected = self._normalize_dpo_completion(self._build_synthetic_dpo_rejected(question))
            if not prompt.strip() or not chosen or not rejected or chosen == rejected:
                continue

            synthetic_records.append(
                {
                    "prompt": prompt,
                    "chosen": chosen,
                    "rejected": rejected,
                    "weight": SYNTHETIC_DPO_PAIR_WEIGHT,
                    "metadata": {
                        "pair_type": SYNTHETIC_DPO_PAIR_TYPE,
                        "confidence": confidence,
                        "language": "en",
                        "rejected_reason_codes": ["synthetic_fallback"],
                        "question_id": str(question.id),
                    },
                }
            )
            if limit is not None and len(synthetic_records) >= limit:
                break

        return synthetic_records

    def _build_dataset_manifest(
        self,
        *,
        dataset_tag: str,
        dataset_role: str,
        created_at: datetime,
        snapshot_filter: dict[str, Any],
        sample_counts: dict[str, int],
        composition: dict[str, Any],
        sample_ids: Optional[dict[str, list[str]]] = None,
        quality_metrics: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        return {
            "schema_version": 4,
            "dataset_tag": dataset_tag,
            "dataset_role": dataset_role,
            "created_at": created_at.isoformat(),
            "snapshot_filter": snapshot_filter,
            "sample_counts": sample_counts,
            "composition": composition,
            "sample_ids": sample_ids or {},
            "quality_metrics": quality_metrics or {},
            "data_contract": {
                "sft": {
                    "fields": ["instruction", "input", "output"],
                    "input_sections": [
                        "Question Specification",
                        "Source Context",
                    ],
                    "output_sections": [
                        "Question",
                        "Options",
                        "Correct Answer",
                        "Explanation",
                    ],
                },
                "dpo": {
                    "fields": ["prompt", "chosen", "rejected", "weight"],
                    "prompt_suffix": "### Response:",
                },
            },
        }

    @staticmethod
    def _resolve_training_window_days(days: Optional[int] = None) -> int:
        if days is None:
            return DEFAULT_TRAINING_WINDOW_DAYS
        return max(1, int(days))

    @classmethod
    def _resolve_training_since(
        cls,
        since: Optional[datetime] = None,
        *,
        days: Optional[int] = None,
    ) -> datetime:
        if since is not None:
            return since
        resolved_days = cls._resolve_training_window_days(days)
        return datetime.now(timezone.utc) - timedelta(days=resolved_days)

    @classmethod
    def _resolve_snapshot_filter(
        cls,
        snapshot_filter: Optional[dict[str, Any]] = None,
    ) -> tuple[dict[str, Any], int, datetime, float]:
        raw_filter = dict(snapshot_filter or {})
        since_days = cls._resolve_training_window_days(raw_filter.get("days"))
        confidence_min = float(raw_filter.get("confidence_min", 0.0))
        since_dt = cls._resolve_training_since(days=since_days)
        resolved_filter = {
            **raw_filter,
            "days": since_days,
            "confidence_min": confidence_min,
            "since": since_dt.isoformat(),
        }
        return resolved_filter, since_days, since_dt, confidence_min

    @staticmethod
    def _normalize_adapter_path(adapter_path: Optional[str]) -> Optional[str]:
        cleaned = (adapter_path or "").strip()
        return cleaned or None

    @classmethod
    def _has_adapter_checkpoint(cls, adapter_path: Optional[str]) -> bool:
        normalized_path = cls._normalize_adapter_path(adapter_path)
        if not normalized_path:
            return False
        return os.path.exists(os.path.join(normalized_path, "adapter_config.json"))

    @staticmethod
    def _get_parent_adapter_path(version: ModelVersion) -> Optional[str]:
        hyperparameters = version.hyperparameters if isinstance(version.hyperparameters, dict) else {}
        adapter_path = hyperparameters.get("parent_adapter_path")
        if isinstance(adapter_path, str) and adapter_path.strip():
            return adapter_path.strip()
        return None

    @staticmethod
    def _default_base_model() -> str:
        return settings.TRAINING_PRIMARY_BASE_MODEL or BASE_MODEL_NAME

    @staticmethod
    def _dataset_prefix_for_role(role: Optional[str]) -> str:
        normalized = str(role or "training").strip().lower()
        return REFERENCE_DATASET_PREFIXES.get(normalized, REFERENCE_DATASET_PREFIXES["training"])

    @classmethod
    def _dataset_role_from_tag(cls, dataset_tag: Optional[str]) -> str:
        normalized = str(dataset_tag or "").strip().lower()
        if normalized in REFERENCE_DATASET_ROLES:
            return normalized
        for role, prefix in REFERENCE_DATASET_PREFIXES.items():
            if normalized.startswith(f"{prefix}-"):
                return role
        return "training"

    @staticmethod
    def _stable_rank(value: str, salt: str = "") -> int:
        payload = f"{salt}:{value}".encode("utf-8")
        return int(hashlib.sha256(payload).hexdigest(), 16)

    @staticmethod
    def _safe_mean(values: Iterable[Optional[float]]) -> float:
        cleaned = [float(value) for value in values if value is not None]
        if not cleaned:
            return 0.0
        return float(sum(cleaned) / len(cleaned))

    @staticmethod
    def _distribution_shares(distribution: dict[str, int]) -> dict[str, float]:
        total = int(sum(distribution.values()))
        if total <= 0:
            return {}
        return {
            key: float(value / total)
            for key, value in distribution.items()
            if value > 0
        }

    @classmethod
    def _total_variation_distance(
        cls,
        current_distribution: dict[str, int],
        reference_distribution: dict[str, int],
    ) -> float:
        current = cls._distribution_shares(current_distribution)
        reference = cls._distribution_shares(reference_distribution)
        labels = set(current) | set(reference)
        if not labels:
            return 0.0
        return round(
            0.5 * sum(abs(current.get(label, 0.0) - reference.get(label, 0.0)) for label in labels),
            4,
        )

    @staticmethod
    def _percentile(values: list[float], percentile: float) -> float:
        if not values:
            return 0.0
        ordered = sorted(values)
        index = max(0, min(len(ordered) - 1, int(math.ceil((percentile / 100.0) * len(ordered))) - 1))
        return float(ordered[index])

    @classmethod
    def _question_quality_score(cls, question: Question) -> float:
        return round(
            cls._average_quality_signal(
                question.answerability_score,
                question.specificity_score,
                question.generation_confidence,
                question.novelty_score,
            ),
            4,
        )

    @staticmethod
    def _load_manifest(manifest_path: Optional[str]) -> dict[str, Any]:
        resolved_path = (manifest_path or "").strip()
        if not resolved_path or not os.path.exists(resolved_path):
            return {}
        with open(resolved_path, "r") as handle:
            return json.load(handle)

    @staticmethod
    def _extract_manifest_question_ids(manifest: dict[str, Any]) -> list[str]:
        sample_ids = manifest.get("sample_ids") if isinstance(manifest, dict) else {}
        question_ids = sample_ids.get("sft_question_ids") if isinstance(sample_ids, dict) else []
        return [str(question_id) for question_id in (question_ids or []) if question_id]

    @staticmethod
    def _extract_manifest_pair_ids(manifest: dict[str, Any]) -> list[str]:
        sample_ids = manifest.get("sample_ids") if isinstance(manifest, dict) else {}
        pair_ids = sample_ids.get("dpo_pair_ids") if isinstance(sample_ids, dict) else []
        return [str(pair_id) for pair_id in (pair_ids or []) if pair_id]

    @staticmethod
    def _tokenizer_fingerprint_from_tokenizer(tokenizer: Any) -> dict[str, Any]:
        return {
            "name_or_path": getattr(tokenizer, "name_or_path", None),
            "vocab_size": int(len(tokenizer)) if hasattr(tokenizer, "__len__") else None,
            "bos_token_id": getattr(tokenizer, "bos_token_id", None),
            "eos_token_id": getattr(tokenizer, "eos_token_id", None),
            "pad_token_id": getattr(tokenizer, "pad_token_id", None),
            "unk_token_id": getattr(tokenizer, "unk_token_id", None),
        }

    @staticmethod
    def _compare_tokenizer_fingerprints(
        expected: Optional[dict[str, Any]],
        actual: dict[str, Any],
    ) -> tuple[bool, str]:
        if not expected:
            return (True, "no_expected_fingerprint")

        drift_fields = [
            field
            for field in ("vocab_size", "bos_token_id", "eos_token_id", "pad_token_id", "unk_token_id")
            if expected.get(field) != actual.get(field)
        ]
        if drift_fields:
            return (
                False,
                "tokenizer drift detected in: " + ", ".join(drift_fields),
            )
        return (True, "match")

    @classmethod
    def _build_inference_prompt(cls, question: Question) -> str:
        instruction = cls._build_sft_instruction(question)
        input_text = cls._build_sft_input(question)
        if input_text:
            return f"### Instruction:\n{instruction}\n\n### Input:\n{input_text}\n\n### Response:\n"
        return f"### Instruction:\n{instruction}\n\n### Response:\n"

    @staticmethod
    def _deterministic_format_score(response_text: str, question_type: Optional[str]) -> float:
        text = (response_text or "").strip()
        if not text:
            return 0.0

        required_sections = ["Question:", "Correct Answer:", "Explanation:"]
        score = 0.0
        for section in required_sections:
            if section.lower() in text.lower():
                score += 1.0

        normalized_type = str(question_type or "").strip().lower()
        if normalized_type in {"mcq", "multiple_choice", "multiple-choice"}:
            if "Options:" in text:
                option_lines = re.findall(r"^[A-D][\).:-]\s+.+$", text, flags=re.MULTILINE)
                if len(option_lines) >= 4:
                    score += 1.0
        else:
            score += 1.0

        return round(score / 4.0, 4)

    async def _get_dataset_by_role(
        self,
        db: AsyncSession,
        role: str,
    ) -> Optional[TrainingDataset]:
        prefix = self._dataset_prefix_for_role(role)
        result = await db.execute(
            select(TrainingDataset)
            .where(TrainingDataset.dataset_tag.like(f"{prefix}-%"))
            .order_by(desc(TrainingDataset.created_at))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _reference_dataset_bundle(
        self,
        db: AsyncSession,
        role: str,
    ) -> dict[str, Any]:
        dataset = await self._get_dataset_by_role(db, role)
        manifest = self._load_manifest(dataset.manifest_path) if dataset else {}
        question_ids = self._extract_manifest_question_ids(manifest)
        pair_ids = self._extract_manifest_pair_ids(manifest)
        sample_counts = dataset.sample_counts if dataset and isinstance(dataset.sample_counts, dict) else {}
        return {
            "role": role,
            "dataset": dataset,
            "manifest": manifest,
            "question_ids": question_ids,
            "pair_ids": pair_ids,
            "available": dataset is not None,
            "dataset_tag": dataset.dataset_tag if dataset else None,
            "created_at": dataset.created_at.isoformat() if dataset and dataset.created_at else None,
            "sample_count": len(question_ids) if question_ids else int(sample_counts.get("sft", 0)),
        }

    def _select_reference_question_ids(
        self,
        questions: list[Question],
        target_size: int,
        role: str,
    ) -> list[str]:
        if target_size <= 0 or not questions:
            return []

        def sort_key(question: Question) -> tuple[Any, ...]:
            quality = self._question_quality_score(question)
            novelty = float(question.novelty_score or 0.0)
            vetted_at = question.vetted_at or datetime.min.replace(tzinfo=timezone.utc)

            if role == "anchor":
                return (-quality, vetted_at, self._stable_rank(str(question.id), role))
            if role == "evaluation":
                return (novelty, -quality, self._stable_rank(str(question.id), role))
            return (self._stable_rank(str(question.id), role), vetted_at)

        buckets: dict[str, list[Question]] = defaultdict(list)
        for question in questions:
            difficulty = str(question.difficulty_level or "unknown").strip().lower()
            buckets[difficulty].append(question)

        labels = ["easy", "medium", "hard", "unknown"]
        for label in labels:
            buckets[label].sort(key=sort_key)

        selected_ids: list[str] = []
        seen_ids: set[str] = set()

        while len(selected_ids) < target_size:
            progressed = False
            for label in labels:
                while buckets[label]:
                    candidate = buckets[label].pop(0)
                    if candidate.id in seen_ids:
                        continue
                    seen_ids.add(candidate.id)
                    selected_ids.append(str(candidate.id))
                    progressed = True
                    break
                if len(selected_ids) >= target_size:
                    break
            if not progressed:
                break

        if len(selected_ids) < target_size:
            remaining = [question for question in questions if question.id not in seen_ids]
            remaining.sort(key=sort_key)
            for question in remaining:
                if len(selected_ids) >= target_size:
                    break
                selected_ids.append(str(question.id))

        return selected_ids[:target_size]

    async def _ensure_reference_datasets(
        self,
        db: AsyncSession,
        created_by: str = "system",
    ) -> dict[str, Any]:
        bundles = {
            role: await self._reference_dataset_bundle(db, role)
            for role in ("evaluation", "holdout", "anchor")
        }
        if all(bundle["available"] for bundle in bundles.values()):
            return bundles

        approved_result = await db.execute(
            select(Question)
            .where(
                Question.vetting_status == "approved",
                Question.is_latest == True,
            )
        )
        approved_questions = list(approved_result.scalars().all())

        reserved_ids = set()
        for bundle in bundles.values():
            reserved_ids.update(bundle["question_ids"])

        available_questions = [
            question for question in approved_questions if str(question.id) not in reserved_ids
        ]

        dataset_sizes = {
            "evaluation": settings.TRAINING_REFERENCE_EVAL_SIZE,
            "holdout": settings.TRAINING_REFERENCE_HOLDOUT_SIZE,
            "anchor": settings.TRAINING_REFERENCE_ANCHOR_SIZE,
        }

        for role in ("evaluation", "holdout", "anchor"):
            if bundles[role]["available"]:
                continue

            target_size = int(dataset_sizes[role])
            selected_ids = self._select_reference_question_ids(
                available_questions,
                target_size=target_size,
                role=role,
            )
            if not selected_ids:
                logger.warning(
                    "Unable to bootstrap %s reference dataset: no eligible approved questions.",
                    role,
                )
                continue

            snapshot_filter = {
                "dataset_role": role,
                "immutable": True,
                "question_ids": selected_ids,
            }
            await self.build_dataset_snapshot(
                db=db,
                created_by=created_by,
                snapshot_filter=snapshot_filter,
            )

            selected_set = set(selected_ids)
            available_questions = [
                question for question in available_questions if str(question.id) not in selected_set
            ]
            bundles[role] = await self._reference_dataset_bundle(db, role)

        return bundles

    async def _select_policy_training_questions(
        self,
        db: AsyncSession,
        since: datetime,
        cap: int,
        strategy: str,
    ) -> tuple[list[Question], dict[str, int]]:
        bundles = await self._ensure_reference_datasets(db, created_by="system:policy")
        excluded_ids = set(bundles["evaluation"]["question_ids"]) | set(bundles["holdout"]["question_ids"])
        anchor_ids = [
            question_id
            for question_id in bundles["anchor"]["question_ids"]
            if question_id not in excluded_ids
        ]

        recent_fraction = min(max(float(settings.TRAINING_RECENT_DATA_FRACTION), 0.6), 0.8)
        recent_cap = cap
        anchor_cap = 0
        if anchor_ids:
            recent_cap = max(1, int(round(cap * recent_fraction)))
            anchor_cap = max(0, cap - recent_cap)

        base_filters = [
            Question.vetting_status == "approved",
            Question.is_latest == True,
            Question.vetted_at >= since,
        ]
        if excluded_ids:
            base_filters.append(Question.id.notin_(list(excluded_ids)))

        if strategy == "stratified":
            recent_questions = await self._stratified_sample_sft(db, base_filters, recent_cap)
        elif strategy == "random":
            recent_query = (
                select(Question)
                .where(*base_filters)
                .order_by(func.random())
                .limit(recent_cap)
            )
            recent_questions = list((await db.execute(recent_query)).scalars().all())
        else:
            recent_query = (
                select(Question)
                .where(*base_filters)
                .order_by(Question.vetted_at.desc())
                .limit(recent_cap)
            )
            recent_questions = list((await db.execute(recent_query)).scalars().all())

        anchor_questions: list[Question] = []
        if anchor_cap > 0 and anchor_ids:
            anchor_query = select(Question).where(Question.id.in_(anchor_ids))
            anchor_questions = list((await db.execute(anchor_query)).scalars().all())
            anchor_questions.sort(
                key=lambda question: (
                    -self._question_quality_score(question),
                    question.vetted_at or datetime.min.replace(tzinfo=timezone.utc),
                )
            )
            anchor_questions = anchor_questions[:anchor_cap]

        selected_questions: list[Question] = []
        seen_ids: set[str] = set()
        for question in recent_questions + anchor_questions:
            question_id = str(question.id)
            if question_id in seen_ids:
                continue
            seen_ids.add(question_id)
            selected_questions.append(question)

        if len(selected_questions) < cap and anchor_ids:
            remaining_anchor = [
                question for question in anchor_questions if str(question.id) not in seen_ids
            ]
            for question in remaining_anchor:
                if len(selected_questions) >= cap:
                    break
                seen_ids.add(str(question.id))
                selected_questions.append(question)

        return (
            selected_questions[:cap],
            {
                "recent": sum(1 for question in selected_questions if str(question.id) not in set(anchor_ids)),
                "anchor": sum(1 for question in selected_questions if str(question.id) in set(anchor_ids)),
            },
        )

    async def _latest_completed_training_job(self, db: AsyncSession) -> Optional[TrainingJob]:
        result = await db.execute(
            select(TrainingJob)
            .where(TrainingJob.status == "completed")
            .order_by(desc(TrainingJob.completed_at), desc(TrainingJob.created_at))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _latest_completed_sft_version(self, db: AsyncSession) -> Optional[ModelVersion]:
        result = await db.execute(
            select(ModelVersion)
            .where(
                ModelVersion.status == "completed",
                ModelVersion.sft_samples_count > 0,
            )
            .order_by(desc(ModelVersion.training_completed_at), desc(ModelVersion.created_at))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _compute_pending_pair_diversity(
        self,
        db: AsyncSession,
        since: datetime,
    ) -> tuple[float, dict[str, Any]]:
        pair_result = await db.execute(
            select(TrainingPair)
            .where(
                TrainingPair.status.in_(["pending", "queued"]),
                TrainingPair.created_at >= since,
            )
        )
        pairs = list(pair_result.scalars().all())
        if not pairs:
            return (0.0, {"pair_count": 0})

        pair_type_counts = Counter(str(pair.pair_type or "unknown") for pair in pairs)
        reason_codes = {
            code
            for pair in pairs
            for code in (pair.rejected_reason_codes or [])
            if code
        }
        languages = {str(pair.language or "unknown") for pair in pairs if pair.language}

        chosen_question_ids = [pair.chosen_question_id for pair in pairs if pair.chosen_question_id]
        difficulty_counts: Counter[str] = Counter()
        if chosen_question_ids:
            question_rows = await db.execute(
                select(Question.difficulty_level)
                .where(Question.id.in_(chosen_question_ids))
            )
            difficulty_counts.update(
                str(row[0] or "unknown") for row in question_rows.all()
            )

        diversity_score = round(
            self._safe_mean(
                [
                    min(1.0, len(pair_type_counts) / 4.0),
                    min(1.0, len(reason_codes) / 5.0),
                    min(1.0, len(difficulty_counts) / 3.0),
                    min(1.0, len(languages) / 2.0),
                ]
            ),
            4,
        )
        return (
            diversity_score,
            {
                "pair_count": len(pairs),
                "pair_type_distribution": dict(pair_type_counts),
                "reason_code_count": len(reason_codes),
                "difficulty_distribution": dict(difficulty_counts),
                "language_count": len(languages),
            },
        )

    async def evaluate_auto_training_policy(
        self,
        db: AsyncSession,
        *,
        created_by: str = "system",
        bootstrap_reference_datasets: bool = True,
    ) -> dict[str, Any]:
        if bootstrap_reference_datasets:
            reference_bundles = await self._ensure_reference_datasets(db, created_by=created_by)
        else:
            reference_bundles = {
                role: await self._reference_dataset_bundle(db, role)
                for role in ("evaluation", "holdout", "anchor")
            }
        reference_ready = all(
            bundle["available"] for bundle in reference_bundles.values()
        )

        latest_job = await self._latest_completed_training_job(db)
        latest_sft_version = await self._latest_completed_sft_version(db)
        since = latest_job.completed_at if latest_job and latest_job.completed_at else self._resolve_training_since(days=DEFAULT_TRAINING_WINDOW_DAYS)
        hours_since_last_training = (
            (datetime.now(timezone.utc) - latest_job.completed_at).total_seconds() / 3600.0
            if latest_job and latest_job.completed_at
            else float("inf")
        )

        approved_result = await db.execute(
            select(Question)
            .where(
                Question.vetting_status == "approved",
                Question.is_latest == True,
                Question.vetted_at >= since,
            )
        )
        recent_questions = list(approved_result.scalars().all())

        quality_result = await db.execute(
            select(func.avg(VettingLog.quality_score)).where(
                VettingLog.decision == "approve",
                VettingLog.created_at >= since,
            )
        )
        review_quality_score = quality_result.scalar()

        recent_difficulty_counts = Counter(
            str(question.difficulty_level or "unknown") for question in recent_questions
        )
        recent_type_counts = Counter(
            str(question.question_type or "unknown") for question in recent_questions
        )
        data_quality_score = round(
            self._average_quality_signal(
                review_quality_score,
                self._safe_mean(question.answerability_score for question in recent_questions),
                self._safe_mean(question.specificity_score for question in recent_questions),
                self._safe_mean(question.generation_confidence for question in recent_questions),
            ),
            4,
        )
        novelty_score = round(
            self._safe_mean(question.novelty_score for question in recent_questions),
            4,
        )

        dynamic_threshold = settings.AUTO_TRAINING_SFT_BASE_THRESHOLD
        if data_quality_score > settings.AUTO_TRAINING_HIGH_QUALITY_THRESHOLD:
            dynamic_threshold = settings.AUTO_TRAINING_SFT_MIN_THRESHOLD
        elif data_quality_score < settings.AUTO_TRAINING_LOW_QUALITY_THRESHOLD:
            dynamic_threshold = settings.AUTO_TRAINING_SFT_MAX_THRESHOLD

        anchor_manifest = reference_bundles["anchor"].get("manifest") or {}
        anchor_composition = anchor_manifest.get("composition") if isinstance(anchor_manifest, dict) else {}
        anchor_sft = anchor_composition.get("sft") if isinstance(anchor_composition, dict) else {}
        difficulty_shift = self._total_variation_distance(
            dict(recent_difficulty_counts),
            anchor_sft.get("by_difficulty", {}) if isinstance(anchor_sft, dict) else {},
        )
        type_shift = self._total_variation_distance(
            dict(recent_type_counts),
            anchor_sft.get("by_question_type", {}) if isinstance(anchor_sft, dict) else {},
        )
        distribution_shift_score = round(self._safe_mean([difficulty_shift, type_shift]), 4)

        pair_diversity_score, pair_diversity_details = await self._compute_pending_pair_diversity(db, since)
        pending_pair_count = int(pair_diversity_details.get("pair_count", 0))
        recent_sft_checkpoint_exists = latest_sft_version is not None and bool(
            latest_sft_version.training_completed_at
            and latest_sft_version.training_completed_at >= self._resolve_training_since(days=DEFAULT_TRAINING_WINDOW_DAYS)
        )

        interval_ready = hours_since_last_training >= float(settings.AUTO_TRAINING_MIN_INTERVAL_HOURS)
        sft_ready = (
            reference_ready
            and len(recent_questions) >= int(dynamic_threshold)
            and interval_ready
            and novelty_score >= float(settings.AUTO_TRAINING_MIN_NOVELTY_SCORE)
        )
        dpo_ready = (
            pending_pair_count >= int(settings.AUTO_TRAINING_DPO_MIN_PAIRS)
            and pair_diversity_score >= float(settings.AUTO_TRAINING_DPO_MIN_DIVERSITY_SCORE)
            and recent_sft_checkpoint_exists
        )

        training_method = "skip"
        if sft_ready and dpo_ready:
            training_method = "sft+dpo"
        elif sft_ready:
            training_method = "sft"
        elif dpo_ready:
            training_method = "dpo"

        reasons: list[str] = []
        if not reference_ready and settings.TRAINING_REFERENCE_DATASETS_REQUIRED:
            reasons.append("reference datasets not ready")
        if not interval_ready:
            reasons.append("minimum interval since last training not reached")
        if len(recent_questions) < int(dynamic_threshold):
            reasons.append("insufficient newly approved SFT samples")
        if novelty_score < float(settings.AUTO_TRAINING_MIN_NOVELTY_SCORE):
            reasons.append("recent data novelty below floor")
        if pending_pair_count < int(settings.AUTO_TRAINING_DPO_MIN_PAIRS):
            reasons.append("insufficient DPO preference pairs")
        if pair_diversity_score < float(settings.AUTO_TRAINING_DPO_MIN_DIVERSITY_SCORE):
            reasons.append("DPO pair diversity below floor")
        if not recent_sft_checkpoint_exists:
            reasons.append("recent SFT checkpoint unavailable")

        return {
            "should_train": training_method != "skip",
            "training_method": training_method,
            "reason": "training triggered" if training_method != "skip" else "; ".join(dict.fromkeys(reasons)) or "no trigger conditions met",
            "reasons": list(dict.fromkeys(reasons)),
            "inputs": {
                "new_vetted_samples": len(recent_questions),
                "data_quality_score": data_quality_score,
                "data_novelty_score": novelty_score,
                "dynamic_sft_threshold": int(dynamic_threshold),
                "hours_since_last_training": round(hours_since_last_training, 2) if math.isfinite(hours_since_last_training) else None,
                "pending_preference_pairs": pending_pair_count,
                "pair_diversity_score": pair_diversity_score,
                "recent_sft_checkpoint_exists": recent_sft_checkpoint_exists,
                "distribution_shift_score": distribution_shift_score,
            },
            "distribution_shift": {
                "overall": distribution_shift_score,
                "difficulty": difficulty_shift,
                "question_type": type_shift,
            },
            "pair_diversity": pair_diversity_details,
            "reference_datasets": {
                role: {
                    "available": bundle["available"],
                    "dataset_tag": bundle["dataset_tag"],
                    "sample_count": bundle["sample_count"],
                    "created_at": bundle["created_at"],
                }
                for role, bundle in reference_bundles.items()
            },
            "benchmark_models": {
                "primary": self._default_base_model(),
                "secondary": settings.TRAINING_BENCHMARK_BASE_MODEL,
            },
        }

    # ═══════════════════════════════════════════
    # Phase 1: SFT Data Preparation
    # ═══════════════════════════════════════════

    async def prepare_sft_data(
        self,
        db: AsyncSession,
        since: Optional[datetime] = None,
        *,
        max_samples: Optional[int] = None,
        sample_strategy: Optional[str] = None,
    ) -> tuple[str, int]:
        """
        Export approved questions as SFT instruction-tuning JSONL.

        Format per line:
        {
          "instruction": "Generate a <type> question at <difficulty> about <topic>",
          "input": "<context from source chunks if available>",
          "output": "<question_text>\nAnswer: <answer>\nExplanation: <explanation>"
        }

        Args:
            max_samples: Cap on exported samples (default from DEFAULT_MAX_SFT_SAMPLES).
            sample_strategy: One of 'recent_first', 'stratified', 'random'.

        Returns (file_path, sample_count).
        """
        since = self._resolve_training_since(since)
        cap = max_samples if max_samples is not None else DEFAULT_MAX_SFT_SAMPLES
        strategy = sample_strategy or DEFAULT_SAMPLE_STRATEGY
        if strategy not in VALID_SAMPLE_STRATEGIES:
            logger.warning("Unknown sample_strategy '%s', falling back to 'recent_first'", strategy)
            strategy = "recent_first"

        mix_counts = {"recent": 0, "anchor": 0}
        questions: list[Question] = []
        if settings.TRAINING_REFERENCE_DATASETS_REQUIRED:
            questions, mix_counts = await self._select_policy_training_questions(
                db=db,
                since=since,
                cap=cap,
                strategy=strategy,
            )

        if not questions:
            base_filters = [
                Question.vetting_status == "approved",
                Question.is_latest == True,
                Question.vetted_at >= since,
            ]

            if strategy == "stratified":
                questions = await self._stratified_sample_sft(db, base_filters, cap)
            elif strategy == "random":
                query = (
                    select(Question)
                    .where(*base_filters)
                    .order_by(func.random())
                    .limit(cap)
                )
                result = await db.execute(query)
                questions = list(result.scalars().all())
            else:
                query = (
                    select(Question)
                    .where(*base_filters)
                    .order_by(Question.vetted_at.desc())
                    .limit(cap)
                )
                result = await db.execute(query)
                questions = list(result.scalars().all())
                mix_counts["recent"] = len(questions)

        if not questions:
            logger.info("No approved questions since %s — nothing to export.", since)
            return ("", 0)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        output_path = self.training_data_dir / f"sft_{timestamp}.jsonl"

        count = 0
        skipped_no_context = 0
        skipped_empty_output = 0
        with open(output_path, "w") as f:
            for q in questions:
                input_text = self._build_sft_input(q)
                output_text = self._build_sft_output(q)

                if not output_text or not output_text.strip():
                    skipped_empty_output += 1
                    continue

                has_context = self._has_usable_source_context(q, input_text)
                if not has_context:
                    skipped_no_context += 1

                instruction = self._build_sft_instruction(q)
                record = {
                    "instruction": instruction,
                    "input": input_text,
                    "output": output_text,
                    "metadata": {
                        "has_source_context": has_context,
                        "question_id": str(q.id),
                    },
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                count += 1

        if skipped_no_context:
            logger.warning(
                "SFT export: %d/%d samples lack usable source context (len < %d chars)",
                skipped_no_context, count + skipped_no_context + skipped_empty_output, MIN_SOURCE_CONTEXT_LENGTH,
            )
        if skipped_empty_output:
            logger.warning("SFT export: %d samples skipped due to empty output", skipped_empty_output)

        logger.info(
            "Exported %d SFT samples to %s (strategy=%s, cap=%d, recent=%d, anchor=%d, skipped_context=%d, skipped_empty=%d)",
            count,
            output_path,
            strategy,
            cap,
            mix_counts.get("recent", 0),
            mix_counts.get("anchor", 0),
            skipped_no_context,
            skipped_empty_output,
        )
        return (str(output_path), count)

    async def _stratified_sample_sft(
        self,
        db: AsyncSession,
        base_filters: list,
        cap: int,
    ) -> list[Question]:
        """Sample SFT data with balanced representation across difficulty levels."""
        difficulty_levels = ["easy", "medium", "hard"]
        per_bucket = max(1, cap // len(difficulty_levels))
        sampled: list[Question] = []

        for difficulty in difficulty_levels:
            query = (
                select(Question)
                .where(*base_filters, Question.difficulty_level == difficulty)
                .order_by(func.random())
                .limit(per_bucket)
            )
            result = await db.execute(query)
            sampled.extend(result.scalars().all())

        remaining = cap - len(sampled)
        if remaining > 0:
            already_ids = [q.id for q in sampled]
            backfill_query = (
                select(Question)
                .where(*base_filters)
            )
            if already_ids:
                backfill_query = backfill_query.where(Question.id.notin_(already_ids))
            backfill_query = backfill_query.order_by(func.random()).limit(remaining)
            result = await db.execute(backfill_query)
            sampled.extend(result.scalars().all())

        return sampled[:cap]

    @classmethod
    def _has_usable_source_context(cls, q: Question, input_text: str) -> bool:
        """Check whether a question has usable source context for training."""
        if input_text and len(input_text.strip()) >= MIN_SOURCE_CONTEXT_LENGTH:
            return True
        meta = q.generation_metadata if isinstance(q.generation_metadata, dict) else {}
        if isinstance(meta.get("context"), str) and len(meta["context"].strip()) >= MIN_SOURCE_CONTEXT_LENGTH:
            return True
        if isinstance(meta.get("source_info"), dict):
            sources = meta["source_info"].get("sources") or []
            total_len = sum(
                len(str(s.get("excerpt") or s.get("content") or "").strip())
                for s in sources if isinstance(s, dict)
            )
            if total_len >= MIN_SOURCE_CONTEXT_LENGTH:
                return True
        return False

    # ═══════════════════════════════════════════
    # Phase 2: DPO Data Preparation
    # ═══════════════════════════════════════════

    async def prepare_dpo_data(
        self,
        db: AsyncSession,
        since: Optional[datetime] = None,
        *,
        max_samples: Optional[int] = None,
        sample_strategy: Optional[str] = None,
    ) -> tuple[str, int]:
        """
        Export DPO training triplets as JSONL.

        Format per line:
        {
          "prompt": "<generation prompt>",
          "chosen": "<preferred response>",
          "rejected": "<rejected response>"
        }

        Args:
            max_samples: Cap on exported pairs (default from DEFAULT_MAX_DPO_SAMPLES).
            sample_strategy: One of 'recent_first', 'random'. Stratified not applicable for DPO.

        Returns (file_path, sample_count).
        """
        since = self._resolve_training_since(since)
        cap = max_samples if max_samples is not None else DEFAULT_MAX_DPO_SAMPLES
        strategy = sample_strategy or DEFAULT_SAMPLE_STRATEGY
        if strategy not in VALID_SAMPLE_STRATEGIES:
            logger.warning("Unknown sample_strategy '%s' for DPO, falling back to 'recent_first'", strategy)
            strategy = "recent_first"

        order_clause = func.random() if strategy == "random" else TrainingPair.created_at.desc()

        query = (
            select(TrainingPair)
            .where(
                TrainingPair.status == "pending",
                TrainingPair.created_at >= since,
                TrainingPair.chosen_response != "",
                (TrainingPair.source_split.is_(None) | (TrainingPair.source_split == "train")),
            )
            .order_by(order_clause)
            .limit(cap)
        )
        result = await db.execute(query)
        pairs = result.scalars().all()

        dpo_records: list[dict[str, Any]] = []
        pair_ids: list[str] = []
        excluded_question_ids: set[str] = set()
        for pair in pairs:
            prompt = self._normalize_dpo_prompt(pair.prompt)
            chosen = self._normalize_dpo_completion(pair.chosen_response)
            rejected = self._normalize_dpo_completion(pair.rejected_response)
            if not chosen or not rejected:
                continue
            dpo_records.append(
                {
                    "prompt": prompt,
                    "chosen": chosen,
                    "rejected": rejected,
                    "weight": pair.pair_weight or 1.0,
                }
            )
            if pair.chosen_question_id:
                excluded_question_ids.add(pair.chosen_question_id)
            pair_ids.append(pair.id)

        real_records_count = len(dpo_records)
        synthetic_records: list[dict[str, Any]] = []
        synthetic_budget = max(0, min(cap - real_records_count, MIN_DPO_EXPORT_PAIRS - real_records_count))
        if synthetic_budget > 0:
            synthetic_records = await self._generate_synthetic_dpo_records(
                db=db,
                since=since,
                limit=synthetic_budget,
                exclude_question_ids=excluded_question_ids,
            )
            dpo_records.extend(
                {
                    "prompt": record["prompt"],
                    "chosen": record["chosen"],
                    "rejected": record["rejected"],
                    "weight": record["weight"],
                }
                for record in synthetic_records
            )

        dpo_records = dpo_records[:cap]

        if not dpo_records:
            logger.info(
                "No pending DPO pairs since %s and no eligible synthetic DPO fallback pairs.",
                since,
            )
            return ("", 0)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        output_path = self.training_data_dir / f"dpo_{timestamp}.jsonl"

        with open(output_path, "w") as f:
            for record in dpo_records:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

        # Mark pairs as queued
        if pair_ids:
            await db.execute(
                update(TrainingPair)
                .where(TrainingPair.id.in_(pair_ids))
                .values(status="queued")
            )
            await db.commit()

        logger.info(
            "Exported %d DPO pairs to %s (%d real, %d synthetic, strategy=%s, cap=%d)",
            len(dpo_records),
            output_path,
            real_records_count,
            len(synthetic_records),
            strategy,
            cap,
        )
        return (str(output_path), len(dpo_records))

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
        parent_adapter_path: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        max_samples: Optional[int] = None,
        sample_strategy: Optional[str] = None,
        policy_snapshot: Optional[dict[str, Any]] = None,
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
        base_model = base_model or self._default_base_model()
        default_hp = {
            "learning_rate": 2e-5,
            "num_epochs": 2,
            "batch_size": 4,
            "gradient_accumulation_steps": 4,
            "lora_r": 16,
            "lora_alpha": 32,
            "lora_dropout": 0.05,
            "max_seq_length": 2048,
            "warmup_ratio": settings.TRAINING_MAX_WARMUP_RATIO,
            "weight_decay": 0.01,
            "max_grad_norm": 1.0,
            "early_stopping_patience": settings.TRAINING_EARLY_STOPPING_PATIENCE,
            "peft_method": settings.TRAINING_PREFERRED_PEFT_METHOD,
        }
        if hyperparameters:
            default_hp.update(hyperparameters)
        default_hp["learning_rate"] = min(
            max(float(default_hp.get("learning_rate", 2e-5)), settings.TRAINING_MIN_LEARNING_RATE),
            settings.TRAINING_MAX_LEARNING_RATE,
        )
        default_hp["warmup_ratio"] = min(
            max(float(default_hp.get("warmup_ratio", settings.TRAINING_MAX_WARMUP_RATIO)), 0.0),
            settings.TRAINING_MAX_WARMUP_RATIO,
        )
        default_hp.pop("warmup_steps", None)

        resolved_parent_adapter_path = self._normalize_adapter_path(
            parent_adapter_path or default_hp.get("parent_adapter_path")
        )
        if resolved_parent_adapter_path:
            if not self._has_adapter_checkpoint(resolved_parent_adapter_path):
                return {
                    "status": "error",
                    "message": "Parent adapter path is missing adapter_config.json or does not exist.",
                    "parent_adapter_path": resolved_parent_adapter_path,
                }
            default_hp["parent_adapter_path"] = resolved_parent_adapter_path
        else:
            default_hp.pop("parent_adapter_path", None)

        resolved_idempotency_key = (idempotency_key or "").strip() or None
        if resolved_idempotency_key:
            existing_job_result = await db.execute(
                select(TrainingJob)
                .where(TrainingJob.idempotency_key == resolved_idempotency_key)
                .order_by(TrainingJob.created_at.desc())
                .limit(1)
            )
            existing_job = existing_job_result.scalar_one_or_none()
            if existing_job:
                existing_version_result = await db.execute(
                    select(ModelVersion).where(ModelVersion.id == existing_job.model_version_id)
                )
                existing_version = existing_version_result.scalar_one_or_none()
                return {
                    "status": "duplicate",
                    "message": "Training job with this idempotency_key already exists.",
                    "job_id": str(existing_job.id),
                    "version_id": str(existing_job.model_version_id),
                    "version_tag": existing_version.version_tag if existing_version else None,
                    "job_status": existing_job.status,
                    "idempotency_key": resolved_idempotency_key,
                }

        # Find the current active version (parent)
        active_result = await db.execute(
            select(ModelVersion).where(ModelVersion.is_active == True)
        )
        active_version = active_result.scalar_one_or_none()
        parent_id = active_version.id if active_version and not resolved_parent_adapter_path else None
        if resolved_parent_adapter_path:
            parent_version_result = await db.execute(
                select(ModelVersion)
                .where(ModelVersion.lora_adapter_path == resolved_parent_adapter_path)
                .order_by(ModelVersion.created_at.desc())
                .limit(1)
            )
            parent_version = parent_version_result.scalar_one_or_none()
            if parent_version:
                parent_id = parent_version.id

        tokenizer_fingerprint = None
        fingerprint_source_version = parent_version if resolved_parent_adapter_path and 'parent_version' in locals() else active_version
        if settings.TRAINING_ENABLE_TOKENIZER_DRIFT_CHECK:
            from transformers import AutoTokenizer  # type: ignore

            tokenizer = AutoTokenizer.from_pretrained(self._resolve_model_source(base_model))
            if tokenizer.pad_token is None:
                tokenizer.pad_token = tokenizer.eos_token
            tokenizer_fingerprint = self._tokenizer_fingerprint_from_tokenizer(tokenizer)

            expected_fingerprint = None
            if fingerprint_source_version and isinstance(fingerprint_source_version.hyperparameters, dict):
                expected_fingerprint = fingerprint_source_version.hyperparameters.get("tokenizer_fingerprint")

            matches, fingerprint_reason = self._compare_tokenizer_fingerprints(
                expected_fingerprint,
                tokenizer_fingerprint,
            )
            if not matches:
                return {
                    "status": "error",
                    "message": fingerprint_reason,
                    "base_model": base_model,
                    "tokenizer_fingerprint": tokenizer_fingerprint,
                }
            default_hp["tokenizer_fingerprint"] = tokenizer_fingerprint

        if policy_snapshot:
            default_hp["policy_snapshot"] = policy_snapshot
        default_hp["benchmark_models"] = {
            "primary": self._default_base_model(),
            "secondary": settings.TRAINING_BENCHMARK_BASE_MODEL,
        }

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

        resolved_max_samples = max_samples or default_hp.pop("max_samples", None)
        resolved_sample_strategy = sample_strategy or default_hp.pop("sample_strategy", None)

        if training_method in ("sft", "sft+dpo"):
            sft_path, sft_count = await self.prepare_sft_data(
                db, max_samples=resolved_max_samples, sample_strategy=resolved_sample_strategy,
            )
        if training_method in ("dpo", "sft+dpo"):
            dpo_path, dpo_count = await self.prepare_dpo_data(
                db, max_samples=resolved_max_samples, sample_strategy=resolved_sample_strategy,
            )

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
            idempotency_key=resolved_idempotency_key,
        )
        db.add(job)
        await db.commit()

        # Launch training asynchronously
        # In production this would dispatch to a GPU worker queue.
        # Here we record the job and it will be picked up by the training worker.
        logger.info(
            "Training job %s created: method=%s, sft=%d, dpo=%d, version=%s, warm_start=%s",
            job.id,
            training_method,
            sft_count,
            dpo_count,
            version_tag,
            resolved_parent_adapter_path or "none",
        )
        trace_id = request_id_ctx.get() or None

        queue_result = await self.queue_service.enqueue(
            "training",
            "run_training_job",
            {
                "job_id": str(job.id),
                "model_version_id": str(model_version.id),
                "version_tag": version_tag,
                "training_method": training_method,
                "trace_id": trace_id,
            },
            idempotency_key=resolved_idempotency_key or f"train:{job.id}",
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
            "parent_adapter_path": resolved_parent_adapter_path,
            "idempotency_key": resolved_idempotency_key,
            "queue": queue_result,
            "hyperparameters": default_hp,
            "policy": policy_snapshot,
        }

    async def run_training_job(self, job_id: str, db: AsyncSession) -> dict:
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

            # Auto-queue post-training evaluation on immutable reference datasets.
            eval_results: dict[str, Any] = {}
            try:
                for dataset_role in ("evaluation", "holdout"):
                    eval_result = await self.evaluate_version(
                        db=db,
                        version_id=version.id,
                        dataset_tag=dataset_role,
                        eval_type="post_training",
                        evaluated_by="system",
                    )
                    eval_results[dataset_role] = eval_result
                    logger.info(
                        "Auto-queued %s evaluation for %s: %s",
                        dataset_role,
                        version.version_tag,
                        eval_result.get("evaluation_id"),
                    )
            except Exception as eval_err:
                logger.warning(
                    "Failed to auto-queue reference evaluations for %s: %s",
                    version.version_tag,
                    eval_err,
                )

            return {
                "status": "completed",
                "job_id": str(job.id),
                "version_tag": version.version_tag,
                "adapter_path": version.lora_adapter_path,
                "auto_evaluation": eval_results,
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

    async def process_dataset_build_job(self, dataset_id: str, db: AsyncSession) -> dict[str, Any]:
        """Finalize dataset snapshot manifest and verify checksum for worker execution."""
        result = await db.execute(select(TrainingDataset).where(TrainingDataset.id == dataset_id))
        dataset = result.scalar_one_or_none()
        if not dataset:
            return {"status": "error", "message": "Dataset not found"}

        manifest = None
        if dataset.manifest_path and os.path.exists(dataset.manifest_path):
            try:
                with open(dataset.manifest_path) as f:
                    manifest = json.load(f)
            except Exception:
                manifest = None
        if manifest is None:
            manifest = {
                "dataset_tag": dataset.dataset_tag,
                "created_at": dataset.created_at.isoformat() if dataset.created_at else None,
                "snapshot_filter": dataset.snapshot_filter,
                "sample_counts": dataset.sample_counts,
            }
        manifest_json = json.dumps(manifest, sort_keys=True)
        checksum = hashlib.sha256(manifest_json.encode("utf-8")).hexdigest()

        if dataset.manifest_path:
            try:
                with open(dataset.manifest_path, "w") as f:
                    f.write(manifest_json)
            except PermissionError:
                fallback_manifest_path = self.training_data_dir / Path(dataset.manifest_path).name
                with open(fallback_manifest_path, "w") as f:
                    f.write(manifest_json)
                dataset.manifest_path = str(fallback_manifest_path)

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

    async def process_evaluation_job(self, evaluation_id: str, db: AsyncSession) -> dict[str, Any]:
        """
        Execute evaluation: compute quality metrics from held-out approved questions,
        run quality gate checks, select spot-check samples, and persist results.
        """
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

        evaluation.eval_status = "running"
        await db.commit()

        try:
            dataset_role = self._dataset_role_from_tag(evaluation.dataset_tag)
            if dataset_role in {"evaluation", "holdout"}:
                metrics = await self._score_version_on_reference_dataset(
                    db,
                    version,
                    evaluation.dataset_tag,
                )
            else:
                metrics = await self._compute_evaluation_metrics(db, version, evaluation)
            gate_checks = self._run_quality_gates(metrics, version)
            all_gates_pass = all(gate_checks.values())

            spot_check_status = "not_required"
            spot_check_samples: Optional[dict] = None
            if all_gates_pass and evaluation.eval_type in ("offline", "post_training"):
                spot_check_samples = await self._select_spot_check_samples(
                    db,
                    version,
                    dataset_tag=evaluation.dataset_tag,
                    metrics=metrics,
                )
                if spot_check_samples and spot_check_samples.get("question_ids"):
                    spot_check_status = "pending"

            evaluation.metrics = metrics
            evaluation.gate_checks = gate_checks
            evaluation.pass_fail = all_gates_pass
            evaluation.eval_status = "completed"
            evaluation.completed_at = datetime.now(timezone.utc)
            evaluation.spot_check_status = spot_check_status
            evaluation.spot_check_samples = spot_check_samples

            auto_rollback = None
            regression_delta = metrics.get("regression_delta_vs_champion") or {}
            worst_regression = min([float(value) for value in regression_delta.values()], default=0.0)
            acceptance_delta = float(metrics.get("acceptance_delta_vs_champion", 0.0) or 0.0)
            previous_champion_id = None
            if isinstance(version.hyperparameters, dict):
                previous_champion_id = version.hyperparameters.get("previous_champion_id")
            if (
                version.is_active
                and previous_champion_id
                and (
                    acceptance_delta <= -float(settings.TRAINING_METRIC_DROP_ROLLBACK_THRESHOLD)
                    or worst_regression <= -float(settings.TRAINING_METRIC_DROP_ROLLBACK_THRESHOLD)
                )
            ):
                auto_rollback = await self.rollback_to_version(db=db, version_id=str(previous_champion_id))
                gate_checks["auto_rollback"] = auto_rollback.get("status") == "rolled_back"

            if version.eval_metrics:
                version.eval_metrics.update(metrics)
            else:
                version.eval_metrics = metrics

            generation_timeout_rate.labels(model_version=version.version_tag).set(
                float(metrics.get("timeout_rate", 0.0))
            )
            approve_rate_by_model.labels(model_version=version.version_tag).set(
                float(metrics.get("acceptance_rate", metrics.get("approve_rate", 0.0)))
            )
            reject_rate_by_reason_code.labels(reason_code="critical").set(
                float(metrics.get("critical_reject_rate", 0.0))
            )

            await db.commit()
            return {
                "status": "completed",
                "evaluation_id": str(evaluation.id),
                "model_version": version.version_tag,
                "pass_fail": all_gates_pass,
                "gate_checks": gate_checks,
                "spot_check_status": spot_check_status,
                "auto_rollback": auto_rollback,
            }

        except Exception as e:
            logger.exception("Evaluation %s failed: %s", evaluation_id, e)
            evaluation.eval_status = "failed"
            evaluation.error_message = str(e)[:1000]
            evaluation.completed_at = datetime.now(timezone.utc)
            await db.commit()
            return {"status": "failed", "error": str(e)}


    async def _load_questions_for_dataset_tag(
        self,
        db: AsyncSession,
        dataset_tag: str,
    ) -> tuple[list[Question], dict[str, Any]]:
        dataset_result = await db.execute(
            select(TrainingDataset).where(TrainingDataset.dataset_tag == dataset_tag)
        )
        dataset = dataset_result.scalar_one_or_none()
        if not dataset:
            return ([], {})

        manifest = self._load_manifest(dataset.manifest_path)
        question_ids = self._extract_manifest_question_ids(manifest)
        if not question_ids:
            return ([], {"dataset": dataset, "manifest": manifest})

        question_result = await db.execute(
            select(Question).where(Question.id.in_(question_ids))
        )
        question_map = {
            str(question.id): question
            for question in question_result.scalars().all()
        }
        ordered_questions = [
            question_map[question_id]
            for question_id in question_ids
            if question_id in question_map
        ]
        return (
            ordered_questions,
            {
                "dataset": dataset,
                "manifest": manifest,
            },
        )

    @staticmethod
    def _question_topic_label(question: Question) -> str:
        topic_tags = list(question.topic_tags or [])
        if topic_tags:
            return str(topic_tags[0])
        raw_response = {}
        if isinstance(question.generation_metadata, dict):
            raw_response = question.generation_metadata.get("raw_response") or {}
        if isinstance(raw_response, dict) and raw_response.get("topic"):
            return str(raw_response["topic"])
        if question.topic_id:
            return str(question.topic_id)
        return "general"

    @staticmethod
    def _clamp_unit_interval(value: Any, *, default: float = 0.0) -> float:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            numeric = default
        return round(min(max(numeric, 0.0), 1.0), 4)

    @staticmethod
    def _group_mean_stddev(grouped_values: dict[str, list[float]]) -> float:
        means = [sum(values) / len(values) for values in grouped_values.values() if values]
        if len(means) <= 1:
            return 0.0
        average = sum(means) / len(means)
        variance = sum((value - average) ** 2 for value in means) / len(means)
        return round(math.sqrt(variance), 4)

    async def _generate_outputs_for_version(
        self,
        version: ModelVersion,
        prompts: list[str],
    ) -> tuple[list[str], list[float]]:
        import torch  # type: ignore
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, pipeline  # type: ignore
        from peft import PeftModel  # type: ignore

        model_source = self._resolve_model_source(version.base_model)
        hp = version.hyperparameters or {}
        peft_method = str(hp.get("peft_method", settings.TRAINING_PREFERRED_PEFT_METHOD)).strip().lower()

        tokenizer = AutoTokenizer.from_pretrained(model_source)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        use_cuda = torch.cuda.is_available()
        model_kwargs: dict[str, Any]
        if use_cuda and peft_method == "qlora":
            model_kwargs = {
                "device_map": "auto",
                "torch_dtype": torch.float16,
                "quantization_config": BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_quant_type="nf4",
                    bnb_4bit_use_double_quant=True,
                    bnb_4bit_compute_dtype=torch.float16,
                ),
            }
        elif use_cuda:
            model_kwargs = {
                "device_map": "auto",
                "torch_dtype": torch.float16,
            }
        else:
            model_kwargs = {
                "low_cpu_mem_usage": True,
                "torch_dtype": torch.float32,
            }

        model = AutoModelForCausalLM.from_pretrained(model_source, **model_kwargs)
        if self._has_adapter_checkpoint(version.lora_adapter_path):
            model = PeftModel.from_pretrained(model, version.lora_adapter_path)
        model.config.use_cache = True

        generator = pipeline(
            "text-generation",
            model=model,
            tokenizer=tokenizer,
            return_full_text=False,
            do_sample=False,
            temperature=0.0,
            batch_size=1,
            pad_token_id=tokenizer.eos_token_id,
        )

        max_new_tokens = max(256, min(1024, int(hp.get("max_seq_length", 2048) // 2)))
        outputs: list[str] = []
        latencies_ms: list[float] = []
        try:
            for prompt in prompts:
                started_at = time.perf_counter()
                result = await asyncio.to_thread(
                    generator,
                    prompt,
                    max_new_tokens=max_new_tokens,
                    pad_token_id=tokenizer.eos_token_id,
                    return_full_text=False,
                )
                latencies_ms.append(round((time.perf_counter() - started_at) * 1000.0, 3))
                if isinstance(result, list) and result:
                    first = result[0]
                    if isinstance(first, dict):
                        outputs.append(str(first.get("generated_text", "")).strip())
                    else:
                        outputs.append(str(first).strip())
                else:
                    outputs.append("")
        finally:
            del generator
            del model
            del tokenizer
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

        return (outputs, latencies_ms)

    async def _judge_generated_outputs(
        self,
        questions: list[Question],
        candidate_outputs: list[str],
    ) -> list[dict[str, Any]]:
        judge = LLMService(model=settings.TRAINING_JUDGE_MODEL)
        semaphore = asyncio.Semaphore(4)

        async def judge_one(question: Question, candidate_output: str) -> dict[str, Any]:
            deterministic_format = self._deterministic_format_score(
                candidate_output,
                question.question_type,
            )
            if not candidate_output.strip():
                return {
                    "format_correctness": deterministic_format,
                    "difficulty_alignment": 0.0,
                    "topic_relevance": 0.0,
                    "hallucination_error_rate": 1.0,
                    "accept": False,
                    "notes": ["empty model output"],
                }

            prompt = STRICT_EVAL_USER_TEMPLATE.format(
                question_type=question.question_type or "unknown",
                difficulty=question.difficulty_level or "medium",
                topic=self._question_topic_label(question),
                source_context=self._build_sft_input(question)[:2500],
                reference_output=self._build_sft_output(question)[:2000],
                candidate_output=candidate_output[:2000],
            )

            async with semaphore:
                try:
                    raw_scores = await judge.generate_json(
                        prompt=prompt,
                        system_prompt=STRICT_EVAL_SYSTEM_PROMPT,
                        temperature=0.0,
                        max_tokens=400,
                    )
                except LLMError as exc:
                    raise RuntimeError(f"Judge model failed: {exc}") from exc

            format_correctness = self._clamp_unit_interval(
                raw_scores.get("format_correctness"),
                default=deterministic_format,
            )
            format_correctness = round(min(format_correctness, deterministic_format), 4)
            hallucination_error_rate = self._clamp_unit_interval(
                raw_scores.get("hallucination_error_rate"),
                default=1.0,
            )
            accept = bool(raw_scores.get("accept"))
            accept = accept and format_correctness >= 0.75 and hallucination_error_rate <= 0.2

            notes = raw_scores.get("notes") or []
            if not isinstance(notes, list):
                notes = [str(notes)]

            return {
                "format_correctness": format_correctness,
                "difficulty_alignment": self._clamp_unit_interval(raw_scores.get("difficulty_alignment"), default=0.0),
                "topic_relevance": self._clamp_unit_interval(raw_scores.get("topic_relevance"), default=0.0),
                "hallucination_error_rate": hallucination_error_rate,
                "accept": accept,
                "notes": [str(note) for note in notes if note][:3],
            }

        tasks = [
            judge_one(question, candidate_output)
            for question, candidate_output in zip(questions, candidate_outputs)
        ]
        return await asyncio.gather(*tasks)

    async def _score_version_on_reference_dataset(
        self,
        db: AsyncSession,
        version: ModelVersion,
        dataset_tag: str,
        *,
        include_champion_delta: bool = True,
    ) -> dict[str, Any]:
        questions, dataset_bundle = await self._load_questions_for_dataset_tag(db, dataset_tag)
        if not questions:
            raise RuntimeError(f"No frozen questions found for dataset {dataset_tag}")

        prompts = [self._build_inference_prompt(question) for question in questions]
        candidate_outputs, latencies_ms = await self._generate_outputs_for_version(version, prompts)
        judgments = await self._judge_generated_outputs(questions, candidate_outputs)

        difficulty_groups: dict[str, list[float]] = defaultdict(list)
        topic_groups: dict[str, list[float]] = defaultdict(list)
        sample_outputs: list[dict[str, Any]] = []
        acceptance_values: list[float] = []
        format_values: list[float] = []
        difficulty_values: list[float] = []
        topic_values: list[float] = []
        hallucination_values: list[float] = []

        for question, candidate_output, judgment in zip(questions, candidate_outputs, judgments):
            accepted = 1.0 if judgment["accept"] else 0.0
            acceptance_values.append(accepted)
            format_values.append(float(judgment["format_correctness"]))
            difficulty_values.append(float(judgment["difficulty_alignment"]))
            topic_values.append(float(judgment["topic_relevance"]))
            hallucination_values.append(float(judgment["hallucination_error_rate"]))

            difficulty_groups[str(question.difficulty_level or "unknown")].append(accepted)
            topic_groups[self._question_topic_label(question)].append(accepted)
            if len(sample_outputs) < 8:
                sample_outputs.append(
                    {
                        "question_id": str(question.id),
                        "accepted": bool(judgment["accept"]),
                        "notes": judgment["notes"],
                        "candidate_preview": candidate_output[:300],
                    }
                )

        metrics: dict[str, Any] = {
            "dataset_tag": dataset_tag,
            "dataset_role": self._dataset_role_from_tag(dataset_tag),
            "samples_evaluated": len(questions),
            "format_correctness": round(self._safe_mean(format_values), 4),
            "difficulty_alignment": round(self._safe_mean(difficulty_values), 4),
            "topic_relevance": round(self._safe_mean(topic_values), 4),
            "hallucination_rate": round(self._safe_mean(hallucination_values), 4),
            "acceptance_rate": round(self._safe_mean(acceptance_values), 4),
            "latency_p95_ms": round(self._percentile(latencies_ms, 95.0), 3),
            "timeout_rate": 0.0,
            "cost_per_request": 0.0,
            "primary_kpi": "acceptance_rate",
            "variance_by_category": {
                "difficulty_acceptance_stddev": self._group_mean_stddev(difficulty_groups),
                "topic_acceptance_stddev": self._group_mean_stddev(topic_groups),
            },
            "sample_outputs": sample_outputs,
            "dataset_manifest_checksum": dataset_bundle.get("dataset").checksum if dataset_bundle.get("dataset") else None,
        }

        if include_champion_delta:
            stable_result = await db.execute(
                select(ModelVersion).where(ModelVersion.is_active == True)
            )
            stable = stable_result.scalar_one_or_none()
            if stable and stable.id != version.id:
                latest_eval_result = await db.execute(
                    select(ModelEvaluation)
                    .where(
                        ModelEvaluation.model_version_id == stable.id,
                        ModelEvaluation.dataset_tag == dataset_tag,
                        ModelEvaluation.eval_status == "completed",
                    )
                    .order_by(desc(ModelEvaluation.created_at))
                    .limit(1)
                )
                latest_eval = latest_eval_result.scalar_one_or_none()
                stable_metrics = (
                    latest_eval.metrics
                    if latest_eval and isinstance(latest_eval.metrics, dict)
                    else await self._score_version_on_reference_dataset(
                        db,
                        stable,
                        dataset_tag,
                        include_champion_delta=False,
                    )
                )
                tracked_metrics = [
                    "format_correctness",
                    "difficulty_alignment",
                    "topic_relevance",
                    "acceptance_rate",
                ]
                regression_delta = {
                    metric_name: round(float(metrics.get(metric_name, 0.0)) - float(stable_metrics.get(metric_name, 0.0)), 4)
                    for metric_name in tracked_metrics
                }
                metrics["regression_delta_vs_champion"] = regression_delta
                metrics["acceptance_delta_vs_champion"] = regression_delta["acceptance_rate"]
                metrics["hallucination_delta_vs_champion"] = round(
                    float(metrics.get("hallucination_rate", 0.0)) - float(stable_metrics.get("hallucination_rate", 0.0)),
                    4,
                )
                metrics["champion_version"] = stable.version_tag

        return metrics

    async def _compute_evaluation_metrics(
        self,
        db: AsyncSession,
        version: ModelVersion,
        evaluation: ModelEvaluation,
    ) -> dict[str, Any]:
        """
        Compute quality metrics for a model version by analyzing held-out approved questions.

        Metrics computed:
        - offline_pass_rate: fraction of held-out questions with quality scores above threshold
        - avg_novelty_score: mean novelty across held-out set
        - avg_answerability_score: mean answerability across held-out set
        - avg_specificity_score: mean specificity across held-out set
        - avg_generation_confidence: mean confidence across held-out set
        - high_similarity_rate: fraction of questions with max_similarity >= 0.85
        - context_coverage_rate: fraction with usable source context
        - approve_rate: fraction approved among all reviewed questions in window
        - critical_reject_rate: fraction of rejections with critical reason codes
        - latency_p95_ms / timeout_rate: from version eval_metrics if available
        """
        since = self._resolve_training_since(days=DEFAULT_TRAINING_WINDOW_DAYS)

        held_out_filters = [
            Question.vetting_status == "approved",
            Question.is_latest == True,
            Question.vetted_at >= since,
        ]

        quality_result = await db.execute(
            select(
                func.count(Question.id),
                func.avg(Question.novelty_score),
                func.avg(Question.answerability_score),
                func.avg(Question.specificity_score),
                func.avg(Question.generation_confidence),
                func.avg(Question.max_similarity),
                func.count(Question.id).filter(Question.max_similarity >= 0.85),
                func.count(Question.id).filter(Question.answerability_score >= 0.7),
                func.count(Question.id).filter(Question.specificity_score >= 0.7),
            ).where(*held_out_filters)
        )
        (
            total_approved,
            avg_novelty,
            avg_answerability,
            avg_specificity,
            avg_confidence,
            avg_similarity,
            high_sim_count,
            high_answerability_count,
            high_specificity_count,
        ) = quality_result.one()

        total_approved = int(total_approved or 0)

        total_reviewed_result = await db.execute(
            select(func.count(Question.id)).where(
                Question.vetting_status.in_(["approved", "rejected"]),
                Question.is_latest == True,
                Question.vetted_at >= since,
            )
        )
        total_reviewed = int(total_reviewed_result.scalar() or 0)

        reject_result = await db.execute(
            select(func.count(VettingLog.id)).where(
                VettingLog.decision == "reject",
                VettingLog.created_at >= since,
                VettingLog.reason_codes.op("&&")(["factual_error", "harmful_content", "plagiarism"]),
            )
        )
        critical_rejects = int(reject_result.scalar() or 0)

        context_check_result = await db.execute(
            select(Question).where(*held_out_filters).limit(500)
        )
        context_questions = context_check_result.scalars().all()
        context_present_count = sum(
            1 for q in context_questions
            if self._has_usable_source_context(q, self._build_sft_input(q))
        )
        context_coverage_rate = (
            round(context_present_count / len(context_questions), 4)
            if context_questions else 0.0
        )

        approve_rate = round(total_approved / total_reviewed, 4) if total_reviewed else 0.0
        offline_pass_rate = (
            round(int(high_answerability_count or 0) / total_approved, 4)
            if total_approved else 0.0
        )
        critical_reject_rate = (
            round(critical_rejects / total_reviewed, 4)
            if total_reviewed else 0.0
        )

        existing_metrics = version.eval_metrics or {}
        return {
            "total_evaluated": total_approved,
            "total_reviewed": total_reviewed,
            "offline_pass_rate": offline_pass_rate,
            "approve_rate": approve_rate,
            "critical_reject_rate": critical_reject_rate,
            "avg_novelty_score": self._round_metric(avg_novelty),
            "avg_answerability_score": self._round_metric(avg_answerability),
            "avg_specificity_score": self._round_metric(avg_specificity),
            "avg_generation_confidence": self._round_metric(avg_confidence),
            "avg_similarity_score": self._round_metric(avg_similarity),
            "high_similarity_rate": round(int(high_sim_count or 0) / total_approved, 4) if total_approved else 0.0,
            "context_coverage_rate": context_coverage_rate,
            "latency_p95_ms": float(existing_metrics.get("latency_p95_ms", 0.0)),
            "timeout_rate": float(existing_metrics.get("timeout_rate", 0.0)),
        }

    @staticmethod
    def _run_quality_gates(metrics: dict[str, Any], version: ModelVersion) -> dict[str, bool]:
        """Run quality gate checks against computed evaluation metrics."""
        if "acceptance_rate" in metrics:
            return {
                "format_correctness": float(metrics.get("format_correctness", 0.0)) >= 0.8,
                "difficulty_alignment": float(metrics.get("difficulty_alignment", 0.0)) >= 0.75,
                "topic_relevance": float(metrics.get("topic_relevance", 0.0)) >= 0.8,
                "hallucination_budget": float(metrics.get("hallucination_rate", 1.0)) <= 0.2,
                "acceptance_rate": float(metrics.get("acceptance_rate", 0.0)) >= 0.6,
                "variance_stable": float((metrics.get("variance_by_category") or {}).get("difficulty_acceptance_stddev", 0.0)) <= 0.25,
                "min_evaluated_samples": int(metrics.get("samples_evaluated", 0)) >= 10,
            }

        offline_pass_rate = float(metrics.get("offline_pass_rate", 0.0))
        critical_reject_rate = float(metrics.get("critical_reject_rate", 0.0))
        latency_p95_ms = float(metrics.get("latency_p95_ms", 0.0))
        timeout_rate = float(metrics.get("timeout_rate", 0.0))
        context_coverage_rate = float(metrics.get("context_coverage_rate", 0.0))
        avg_novelty = float(metrics.get("avg_novelty_score") or 0.0)
        avg_answerability = float(metrics.get("avg_answerability_score") or 0.0)

        return {
            "offline_pass_rate": offline_pass_rate >= settings.PROMOTION_MIN_OFFLINE_PASS_RATE,
            "critical_reject_rate": critical_reject_rate <= (settings.PROMOTION_MAX_CRITICAL_REJECT_INCREASE + 0.02),
            "latency_budget": latency_p95_ms <= settings.PROMOTION_MAX_P95_LATENCY_MS or latency_p95_ms == 0.0,
            "timeout_budget": timeout_rate <= settings.PROMOTION_MAX_TIMEOUT_RATE or timeout_rate == 0.0,
            "context_coverage": context_coverage_rate >= 0.5,
            "novelty_floor": avg_novelty >= 0.3,
            "answerability_floor": avg_answerability >= 0.5,
            "min_evaluated_samples": int(metrics.get("total_evaluated", 0)) >= 10,
        }

    async def _select_spot_check_samples(
        self,
        db: AsyncSession,
        version: ModelVersion,
        sample_size: int = 10,
        dataset_tag: Optional[str] = None,
        metrics: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Select frozen evaluation samples for human spot-check review."""
        sample_outputs = metrics.get("sample_outputs") if isinstance(metrics, dict) else []
        question_ids = [
            str(item.get("question_id"))
            for item in (sample_outputs or [])
            if isinstance(item, dict) and item.get("question_id")
        ]
        if question_ids:
            return {
                "question_ids": question_ids[:sample_size],
                "sample_size": min(sample_size, len(question_ids)),
                "model_version": version.version_tag,
                "dataset_tag": dataset_tag,
            }

        since = self._resolve_training_since(days=DEFAULT_TRAINING_WINDOW_DAYS)
        result = await db.execute(
            select(Question.id)
            .where(
                Question.vetting_status == "approved",
                Question.is_latest == True,
                Question.vetted_at >= since,
            )
            .order_by(func.random())
            .limit(sample_size)
        )
        question_ids = [str(row[0]) for row in result.all()]
        return {
            "question_ids": question_ids,
            "sample_size": len(question_ids),
            "model_version": version.version_tag,
            "dataset_tag": dataset_tag,
        }

    async def complete_spot_check(
        self,
        db: AsyncSession,
        evaluation_id: str,
        decision: str,
        reviewed_by: str,
        notes: Optional[str] = None,
    ) -> dict[str, Any]:
        """Complete a spot-check review for a model evaluation."""
        if decision not in ("approved", "rejected"):
            return {"status": "error", "message": "Decision must be 'approved' or 'rejected'."}

        result = await db.execute(select(ModelEvaluation).where(ModelEvaluation.id == evaluation_id))
        evaluation = result.scalar_one_or_none()
        if not evaluation:
            return {"status": "error", "message": "Evaluation not found"}

        if evaluation.spot_check_status != "pending":
            return {
                "status": "error",
                "message": f"Spot check is '{evaluation.spot_check_status}', not pending.",
            }

        evaluation.spot_check_status = decision
        evaluation.spot_check_reviewed_by = reviewed_by
        evaluation.spot_check_reviewed_at = datetime.now(timezone.utc)
        evaluation.spot_check_notes = notes

        if decision == "rejected":
            evaluation.pass_fail = False

        await db.commit()

        return {
            "status": "completed",
            "evaluation_id": str(evaluation.id),
            "spot_check_status": decision,
            "pass_fail": evaluation.pass_fail,
        }

    async def get_evaluation(self, db: AsyncSession, evaluation_id: str) -> Optional[dict[str, Any]]:
        """Get a single model evaluation by ID."""
        result = await db.execute(select(ModelEvaluation).where(ModelEvaluation.id == evaluation_id))
        evaluation = result.scalar_one_or_none()
        if not evaluation:
            return None
        return {
            "id": str(evaluation.id),
            "model_version_id": str(evaluation.model_version_id),
            "dataset_tag": evaluation.dataset_tag,
            "eval_type": evaluation.eval_type,
            "eval_status": evaluation.eval_status,
            "metrics": evaluation.metrics,
            "gate_checks": evaluation.gate_checks,
            "pass_fail": evaluation.pass_fail,
            "spot_check_status": evaluation.spot_check_status,
            "spot_check_samples": evaluation.spot_check_samples,
            "spot_check_reviewed_by": evaluation.spot_check_reviewed_by,
            "spot_check_notes": evaluation.spot_check_notes,
            "evaluated_by": evaluation.evaluated_by,
            "created_at": evaluation.created_at.isoformat() if evaluation.created_at else None,
            "completed_at": evaluation.completed_at.isoformat() if evaluation.completed_at else None,
            "error_message": evaluation.error_message,
        }

    async def list_evaluations(
        self, db: AsyncSession, version_id: Optional[str] = None, limit: int = 50,
    ) -> list[dict[str, Any]]:
        """List model evaluations, optionally filtered by version."""
        query = select(ModelEvaluation).order_by(desc(ModelEvaluation.created_at)).limit(limit)
        if version_id:
            query = query.where(ModelEvaluation.model_version_id == version_id)
        result = await db.execute(query)
        evaluations = result.scalars().all()
        return [
            {
                "id": str(e.id),
                "model_version_id": str(e.model_version_id),
                "dataset_tag": e.dataset_tag,
                "eval_type": e.eval_type,
                "eval_status": e.eval_status,
                "pass_fail": e.pass_fail,
                "spot_check_status": e.spot_check_status,
                "created_at": e.created_at.isoformat() if e.created_at else None,
                "completed_at": e.completed_at.isoformat() if e.completed_at else None,
            }
            for e in evaluations
        ]

    async def _run_sft(
        self, job: TrainingJob, version: ModelVersion, db: AsyncSession
    ):
        """
        Run Supervised Fine-Tuning with LoRA on the local model.

        Uses: transformers, peft, trl (SFTTrainer).
        """
        # Delayed imports — these are heavy ML dependencies
        import torch  # type: ignore
        from transformers import (        # type: ignore
            AutoModelForCausalLM,
            AutoTokenizer,
            BitsAndBytesConfig,
            EarlyStoppingCallback,
            TrainingArguments,
        )
        from peft import LoraConfig, PeftModel, TaskType, prepare_model_for_kbit_training  # type: ignore
        from trl import SFTTrainer          # type: ignore
        from datasets import load_dataset   # type: ignore

        hp = version.hyperparameters or {}
        data_path = job.training_data_path
        model_source = self._resolve_model_source(version.base_model)

        logger.info("Loading SFT dataset from %s", data_path)
        dataset = load_dataset("json", data_files=data_path, split="train")

        logger.info("Loading base model: %s", model_source)
        tokenizer = AutoTokenizer.from_pretrained(model_source)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        expected_fingerprint = hp.get("tokenizer_fingerprint") if isinstance(hp, dict) else None
        actual_fingerprint = self._tokenizer_fingerprint_from_tokenizer(tokenizer)
        fingerprint_match, fingerprint_reason = self._compare_tokenizer_fingerprints(
            expected_fingerprint,
            actual_fingerprint,
        )
        if settings.TRAINING_ENABLE_TOKENIZER_DRIFT_CHECK and not fingerprint_match:
            raise RuntimeError(fingerprint_reason)

        use_cuda = torch.cuda.is_available()
        peft_method = str(hp.get("peft_method", settings.TRAINING_PREFERRED_PEFT_METHOD)).strip().lower()
        use_qlora = False
        if use_cuda:
            if peft_method == "qlora":
                model_load_kwargs = {
                    "device_map": "auto",
                    "quantization_config": BitsAndBytesConfig(
                        load_in_4bit=True,
                        bnb_4bit_quant_type="nf4",
                        bnb_4bit_use_double_quant=True,
                        bnb_4bit_compute_dtype=torch.float16,
                    ),
                }
                use_qlora = True
                use_fp16 = False
                use_bf16 = False
                optim_name = "paged_adamw_8bit"
            else:
                model_load_kwargs = {
                    "dtype": torch.float16,
                    "device_map": "auto",
                }
                use_fp16 = True
                use_bf16 = False
                optim_name = "adamw_torch_fused"
            dataloader_pin_memory = True
            use_cpu = False
        else:
            model_load_kwargs = {
                "dtype": torch.float32,
                "low_cpu_mem_usage": True,
            }
            use_fp16 = False
            use_bf16 = False
            dataloader_pin_memory = False
            use_cpu = True
            optim_name = "adamw_torch"

        local_smoke_test = not use_cuda
        if local_smoke_test:
            num_train_epochs = 1
            per_device_train_batch_size = 1
            gradient_accumulation_steps = 1
            max_steps = 10
            logger.info(
                "Non-CUDA environment detected; enabling local smoke-test mode "
                "(epochs=%d, batch_size=%d, grad_accum=%d, max_steps=%d)",
                num_train_epochs,
                per_device_train_batch_size,
                gradient_accumulation_steps,
                max_steps,
            )
        else:
            num_train_epochs = hp.get("num_epochs", 3)
            per_device_train_batch_size = hp.get("batch_size", 4)
            gradient_accumulation_steps = hp.get("gradient_accumulation_steps", 4)
            max_steps = hp.get("max_steps", -1)

        train_dataset = dataset
        eval_dataset = None
        if len(dataset) >= 20:
            eval_size = max(1, min(len(dataset) - 1, int(round(len(dataset) * 0.1))))
            split_dataset = dataset.train_test_split(test_size=eval_size, seed=42, shuffle=True)
            train_dataset = split_dataset["train"]
            eval_dataset = split_dataset["test"]

        # LoRA config
        lora_config = LoraConfig(
            task_type=TaskType.CAUSAL_LM,
            r=hp.get("lora_r", 16),
            lora_alpha=hp.get("lora_alpha", 32),
            lora_dropout=hp.get("lora_dropout", 0.05),
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
        )

        parent_adapter_path = self._get_parent_adapter_path(version)
        trainer_peft_config = lora_config
        if self._has_adapter_checkpoint(parent_adapter_path):
            logger.info("Warm-starting SFT from adapter %s", parent_adapter_path)
            base_model = AutoModelForCausalLM.from_pretrained(
                model_source,
                **model_load_kwargs,
            )
            if use_qlora:
                base_model = prepare_model_for_kbit_training(base_model)
            model = PeftModel.from_pretrained(
                base_model,
                parent_adapter_path,
                is_trainable=True,
            )
            trainer_peft_config = None
        else:
            model = AutoModelForCausalLM.from_pretrained(
                model_source,
                **model_load_kwargs,
            )
            if use_qlora:
                model = prepare_model_for_kbit_training(model)
        model.config.use_cache = False

        output_dir = version.lora_adapter_path
        warmup_steps = self._resolve_warmup_steps(
            hp=hp,
            dataset_size=len(train_dataset),
            num_train_epochs=num_train_epochs,
            per_device_train_batch_size=per_device_train_batch_size,
            gradient_accumulation_steps=gradient_accumulation_steps,
            max_steps=max_steps,
        )
        eval_strategy = "epoch" if eval_dataset is not None else "no"
        training_args = TrainingArguments(
            output_dir=output_dir,
            num_train_epochs=num_train_epochs,
            per_device_train_batch_size=per_device_train_batch_size,
            gradient_accumulation_steps=gradient_accumulation_steps,
            max_steps=max_steps,
            learning_rate=hp.get("learning_rate", 2e-4),
            warmup_steps=warmup_steps,
            weight_decay=hp.get("weight_decay", 0.01),
            optim=optim_name,
            logging_steps=1 if local_smoke_test else 10,
            save_strategy="epoch",
            eval_strategy=eval_strategy,
            fp16=use_fp16,
            bf16=use_bf16,
            max_grad_norm=1.0,
            use_cpu=use_cpu,
            dataloader_pin_memory=dataloader_pin_memory,
            report_to="none",
            load_best_model_at_end=eval_dataset is not None,
            metric_for_best_model="eval_loss" if eval_dataset is not None else None,
            greater_is_better=False,
            save_total_limit=2,
        )

        def formatting_func(example):
            inst = example["instruction"]
            inp = example["input"]
            out = example["output"]
            if inp:
                return f"### Instruction:\n{inst}\n\n### Input:\n{inp}\n\n### Response:\n{out}"
            return f"### Instruction:\n{inst}\n\n### Response:\n{out}"

        trainer = SFTTrainer(
            model=model,
            train_dataset=train_dataset,
            eval_dataset=eval_dataset,
            peft_config=trainer_peft_config,
            args=training_args,
            processing_class=tokenizer,
            formatting_func=formatting_func,
        )
        if eval_dataset is not None:
            trainer.add_callback(
                EarlyStoppingCallback(
                    early_stopping_patience=int(hp.get("early_stopping_patience", settings.TRAINING_EARLY_STOPPING_PATIENCE)),
                )
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
            "eval_loss": train_result.metrics.get("eval_loss"),
            "validation_samples": len(eval_dataset) if eval_dataset is not None else 0,
            "peft_method": "qlora" if use_qlora else "lora",
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
        import torch  # type: ignore
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, EarlyStoppingCallback  # type: ignore
        from peft import LoraConfig, PeftModel, TaskType, prepare_model_for_kbit_training  # type: ignore
        from trl import DPOConfig, DPOTrainer  # type: ignore
        from datasets import load_dataset  # type: ignore

        hp = version.hyperparameters or {}
        model_source = self._resolve_model_source(version.base_model)

        # Find DPO data file
        dpo_files = sorted(self.training_data_dir.glob("dpo_*.jsonl"), reverse=True)
        if not dpo_files:
            logger.warning("No DPO data files found — skipping DPO phase.")
            return

        data_path = str(dpo_files[0])
        logger.info("Loading DPO dataset from %s", data_path)
        dataset = load_dataset("json", data_files=data_path, split="train")
        dataset = dataset.map(
            lambda example: {
                "prompt": self._normalize_dpo_prompt(example.get("prompt")),
                "chosen": self._normalize_dpo_completion(example.get("chosen")),
                "rejected": self._normalize_dpo_completion(example.get("rejected")),
                "weight": example.get("weight", 1.0),
            }
        )

        logger.info("Loading model for DPO: %s", model_source)
        tokenizer = AutoTokenizer.from_pretrained(model_source)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        expected_fingerprint = hp.get("tokenizer_fingerprint") if isinstance(hp, dict) else None
        actual_fingerprint = self._tokenizer_fingerprint_from_tokenizer(tokenizer)
        fingerprint_match, fingerprint_reason = self._compare_tokenizer_fingerprints(
            expected_fingerprint,
            actual_fingerprint,
        )
        if settings.TRAINING_ENABLE_TOKENIZER_DRIFT_CHECK and not fingerprint_match:
            raise RuntimeError(fingerprint_reason)

        use_cuda = torch.cuda.is_available()
        peft_method = str(hp.get("peft_method", settings.TRAINING_PREFERRED_PEFT_METHOD)).strip().lower()
        use_qlora = False
        if use_cuda:
            if peft_method == "qlora":
                model_load_kwargs = {
                    "device_map": "auto",
                    "quantization_config": BitsAndBytesConfig(
                        load_in_4bit=True,
                        bnb_4bit_quant_type="nf4",
                        bnb_4bit_use_double_quant=True,
                        bnb_4bit_compute_dtype=torch.float16,
                    ),
                }
                use_qlora = True
                use_fp16 = False
                use_bf16 = False
                optim_name = "paged_adamw_8bit"
            else:
                model_load_kwargs = {
                    "dtype": torch.float16,
                    "device_map": "auto",
                }
                use_fp16 = True
                use_bf16 = False
                optim_name = "adamw_torch_fused"
            dataloader_pin_memory = True
            use_cpu = False
        else:
            model_load_kwargs = {
                "dtype": torch.float32,
                "low_cpu_mem_usage": True,
            }
            use_fp16 = False
            use_bf16 = False
            dataloader_pin_memory = False
            use_cpu = True
            optim_name = "adamw_torch"

        local_smoke_test = not use_cuda
        if local_smoke_test:
            num_train_epochs = 1
            per_device_train_batch_size = 1
            gradient_accumulation_steps = 1
            max_steps = 3
        else:
            num_train_epochs = hp.get("num_epochs", 1)
            per_device_train_batch_size = hp.get("batch_size", 2)
            gradient_accumulation_steps = hp.get("gradient_accumulation_steps", 4)
            max_steps = hp.get("max_steps", -1)

        train_dataset = dataset
        eval_dataset = None
        if len(dataset) >= 20:
            eval_size = max(1, min(len(dataset) - 1, int(round(len(dataset) * 0.1))))
            split_dataset = dataset.train_test_split(test_size=eval_size, seed=42, shuffle=True)
            train_dataset = split_dataset["train"]
            eval_dataset = split_dataset["test"]

        lora_config = LoraConfig(
            task_type=TaskType.CAUSAL_LM,
            r=hp.get("lora_r", 16),
            lora_alpha=hp.get("lora_alpha", 32),
            lora_dropout=hp.get("lora_dropout", 0.05),
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
        )

        adapter_path = version.lora_adapter_path
        parent_adapter_path = self._get_parent_adapter_path(version)
        warm_start_adapter_path = None
        if self._has_adapter_checkpoint(adapter_path):
            warm_start_adapter_path = adapter_path
        elif self._has_adapter_checkpoint(parent_adapter_path):
            warm_start_adapter_path = parent_adapter_path

        if warm_start_adapter_path:
            logger.info("Warm-starting DPO from adapter %s", warm_start_adapter_path)
            base_model = AutoModelForCausalLM.from_pretrained(
                model_source, **model_load_kwargs
            )
            if use_qlora:
                base_model = prepare_model_for_kbit_training(base_model)
            model = PeftModel.from_pretrained(
                base_model,
                warm_start_adapter_path,
                is_trainable=True,
            )
            trainer_peft_config = None
        else:
            model = AutoModelForCausalLM.from_pretrained(
                model_source, **model_load_kwargs
            )
            if use_qlora:
                model = prepare_model_for_kbit_training(model)
            trainer_peft_config = lora_config
        model.config.use_cache = False

        # Reference model (frozen copy for DPO)
        ref_model = AutoModelForCausalLM.from_pretrained(
            model_source, **model_load_kwargs
        )
        ref_model.config.use_cache = False

        if self._has_adapter_checkpoint(adapter_path):
            dpo_output = adapter_path + "-dpo"
        else:
            dpo_output = adapter_path or str(LORA_ADAPTERS_DIR / f"{version.version_tag}-dpo")
        warmup_steps = self._resolve_warmup_steps(
            hp=hp,
            dataset_size=len(train_dataset),
            num_train_epochs=num_train_epochs,
            per_device_train_batch_size=per_device_train_batch_size,
            gradient_accumulation_steps=gradient_accumulation_steps,
            max_steps=max_steps,
        )
        eval_strategy = "epoch" if eval_dataset is not None else "no"
        training_args = DPOConfig(
            output_dir=dpo_output,
            num_train_epochs=num_train_epochs,
            per_device_train_batch_size=per_device_train_batch_size,
            gradient_accumulation_steps=gradient_accumulation_steps,
            max_steps=max_steps,
            learning_rate=hp.get("learning_rate", 5e-5),
            warmup_steps=warmup_steps,
            logging_steps=1 if local_smoke_test else 10,
            save_strategy="epoch",
            eval_strategy=eval_strategy,
            fp16=use_fp16,
            bf16=use_bf16,
            use_cpu=use_cpu,
            dataloader_pin_memory=dataloader_pin_memory,
            optim=optim_name,
            report_to="none",
            remove_unused_columns=False,
            beta=0.1,
            max_length=hp.get("max_seq_length", 2048),
            load_best_model_at_end=eval_dataset is not None,
            metric_for_best_model="eval_loss" if eval_dataset is not None else None,
            greater_is_better=False,
            save_total_limit=2,
        )

        trainer = DPOTrainer(
            model=model,
            ref_model=ref_model,
            args=training_args,
            train_dataset=train_dataset,
            eval_dataset=eval_dataset,
            processing_class=tokenizer,
            peft_config=trainer_peft_config,
        )
        if eval_dataset is not None:
            trainer.add_callback(
                EarlyStoppingCallback(
                    early_stopping_patience=int(hp.get("early_stopping_patience", settings.TRAINING_EARLY_STOPPING_PATIENCE)),
                )
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
            "dpo_eval_loss": train_result.metrics.get("eval_loss"),
            "validation_pairs": len(eval_dataset) if eval_dataset is not None else 0,
            "peft_method": "qlora" if use_qlora else "lora",
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
        self, version_id: str, db: AsyncSession
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

        challenger_result = await db.execute(
            select(ModelVersion)
            .where(ModelVersion.is_active == False)
            .order_by(desc(ModelVersion.training_completed_at), desc(ModelVersion.created_at))
            .limit(1)
        )
        challenger = challenger_result.scalar_one_or_none()

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

        orchestration_policy = await self.evaluate_auto_training_policy(
            db,
            created_by="system:status",
            bootstrap_reference_datasets=False,
        )

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
            "orchestration": {
                "champion": {
                    "version_tag": active.version_tag,
                    "base_model": active.base_model,
                    "status": active.status,
                } if active else None,
                "challenger": {
                    "version_tag": challenger.version_tag,
                    "base_model": challenger.base_model,
                    "status": challenger.status,
                } if challenger else None,
                "policy": orchestration_policy,
            },
        }

    async def build_dataset_snapshot(
        self,
        db: AsyncSession,
        created_by: str,
        snapshot_filter: Optional[dict[str, Any]] = None,
    ) -> dict:
        """Build and register an immutable training dataset snapshot."""
        resolved_snapshot_filter, _, since_dt, confidence_min = self._resolve_snapshot_filter(
            snapshot_filter
        )
        dataset_role = self._dataset_role_from_tag(resolved_snapshot_filter.get("dataset_role"))
        explicit_question_ids = [
            str(question_id)
            for question_id in (resolved_snapshot_filter.get("question_ids") or [])
            if question_id
        ]
        explicit_pair_ids = [
            str(pair_id)
            for pair_id in (resolved_snapshot_filter.get("pair_ids") or [])
            if pair_id
        ]

        if explicit_question_ids:
            sft_filters = [Question.id.in_(explicit_question_ids)]
        else:
            sft_filters = [
                Question.vetting_status == "approved",
                Question.is_latest == True,
                Question.vetted_at >= since_dt,
            ]
        if explicit_pair_ids:
            dpo_filters = [TrainingPair.id.in_(explicit_pair_ids)]
        else:
            dpo_filters = [
                TrainingPair.status.in_(["pending", "queued", "used"]),
                (TrainingPair.confidence.is_(None) | (TrainingPair.confidence >= confidence_min)),
                TrainingPair.created_at >= since_dt,
            ]

        sft_count_result = await db.execute(
            select(func.count(Question.id)).where(*sft_filters)
        )
        sft_count = int(sft_count_result.scalar() or 0)

        dpo_count_result = await db.execute(
            select(func.count(TrainingPair.id)).where(*dpo_filters)
        )
        dpo_count = int(dpo_count_result.scalar() or 0)

        reject_count_result = await db.execute(
            select(func.count(VettingLog.id)).where(
                VettingLog.decision == "reject",
                VettingLog.created_at >= since_dt,
            )
        )
        critique_labels = int(reject_count_result.scalar() or 0)

        sft_by_type_result = await db.execute(
            select(Question.question_type, func.count(Question.id))
            .where(*sft_filters)
            .group_by(Question.question_type)
        )
        sft_by_difficulty_result = await db.execute(
            select(Question.difficulty_level, func.count(Question.id))
            .where(*sft_filters)
            .group_by(Question.difficulty_level)
        )
        sft_by_bloom_result = await db.execute(
            select(Question.bloom_taxonomy_level, func.count(Question.id))
            .where(*sft_filters)
            .group_by(Question.bloom_taxonomy_level)
        )
        sft_by_subject_result = await db.execute(
            select(Subject.code, Subject.name, func.count(Question.id))
            .select_from(Question)
            .outerjoin(Subject, Subject.id == Question.subject_id)
            .where(*sft_filters)
            .group_by(Subject.code, Subject.name)
        )
        sft_by_topic_result = await db.execute(
            select(Topic.name, func.count(Question.id))
            .select_from(Question)
            .outerjoin(Topic, Topic.id == Question.topic_id)
            .where(*sft_filters)
            .group_by(Topic.name)
        )
        dpo_by_pair_type_result = await db.execute(
            select(TrainingPair.pair_type, func.count(TrainingPair.id))
            .where(*dpo_filters)
            .group_by(TrainingPair.pair_type)
        )
        sft_quality_result = await db.execute(
            select(
                func.avg(Question.novelty_score),
                func.avg(Question.max_similarity),
                func.avg(Question.answerability_score),
                func.avg(Question.specificity_score),
                func.avg(Question.generation_confidence),
                func.count(Question.id).filter(Question.max_similarity >= 0.85),
            ).where(*sft_filters)
        )
        (
            avg_novelty_score,
            avg_similarity_score,
            avg_answerability_score,
            avg_specificity_score,
            avg_generation_confidence,
            high_similarity_count,
        ) = sft_quality_result.one()

        question_id_rows = await db.execute(
            select(Question.id).where(*sft_filters).order_by(Question.vetted_at.desc(), Question.id.asc())
        )
        question_ids = [str(row[0]) for row in question_id_rows.all()]
        pair_id_rows = await db.execute(
            select(TrainingPair.id).where(*dpo_filters).order_by(TrainingPair.created_at.desc(), TrainingPair.id.asc())
        )
        pair_ids = [str(row[0]) for row in pair_id_rows.all()]

        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        dataset_tag = f"{self._dataset_prefix_for_role(dataset_role)}-{stamp}"
        difficulty_distribution = self._distribution_from_rows(sft_by_difficulty_result.all())
        bloom_distribution = self._distribution_from_rows(sft_by_bloom_result.all())
        subject_distribution = self._named_distribution_from_rows(
            sft_by_subject_result.all(),
            lambda code, name: f"{code} - {name}" if code and name else str(name or code or "unknown").strip(),
        )
        topic_distribution = self._named_distribution_from_rows(
            sft_by_topic_result.all(),
            lambda name: str(name or "unknown").strip(),
        )
        sample_counts = {
            "sft": sft_count,
            "dpo": dpo_count,
            "critique_labels": critique_labels,
        }
        composition = {
            "sft": {
                "by_question_type": self._distribution_from_rows(sft_by_type_result.all()),
                "by_subject": subject_distribution,
                "by_topic": topic_distribution,
                "by_difficulty": difficulty_distribution,
                "by_bloom_level": bloom_distribution,
            },
            "dpo": {
                "by_pair_type": self._distribution_from_rows(dpo_by_pair_type_result.all()),
            },
        }
        quality_metrics = {
            "sft": {
                "subject_balance": self._summarize_balance(subject_distribution),
                "topic_distribution": topic_distribution,
                "topic_balance": self._summarize_balance(topic_distribution),
                "difficulty_balance": self._summarize_balance(
                    difficulty_distribution,
                    ["easy", "medium", "hard"],
                ),
                "bloom_level_coverage": self._summarize_balance(
                    bloom_distribution,
                    ["remember", "understand", "apply", "analyze", "evaluate", "create"],
                ),
                "average_novelty_score": self._round_metric(avg_novelty_score),
                "average_similarity_score": self._round_metric(avg_similarity_score),
                "average_answerability_score": self._round_metric(avg_answerability_score),
                "average_specificity_score": self._round_metric(avg_specificity_score),
                "average_generation_confidence": self._round_metric(avg_generation_confidence),
                "high_similarity_count": int(high_similarity_count or 0),
                "redundancy_rate": round(float(high_similarity_count or 0) / sft_count, 4) if sft_count else 0.0,
            }
        }
        manifest_created_at = datetime.now(timezone.utc)

        manifest = self._build_dataset_manifest(
            dataset_tag=dataset_tag,
            dataset_role=dataset_role,
            created_at=manifest_created_at,
            snapshot_filter=resolved_snapshot_filter,
            sample_counts=sample_counts,
            composition=composition,
            sample_ids={
                "sft_question_ids": question_ids,
                "dpo_pair_ids": pair_ids,
            },
            quality_metrics=quality_metrics,
        )
        manifest_json = json.dumps(manifest, sort_keys=True)
        checksum = hashlib.sha256(manifest_json.encode("utf-8")).hexdigest()
        manifest_path = str(self.training_data_dir / f"{dataset_tag}.manifest.json")
        self.training_data_dir.mkdir(parents=True, exist_ok=True)
        with open(manifest_path, "w") as f:
            f.write(manifest_json)

        dataset = TrainingDataset(
            dataset_tag=dataset_tag,
            created_by=created_by,
            snapshot_filter=resolved_snapshot_filter,
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

    async def get_training_job(self, db: AsyncSession, job_id: str) -> Optional[dict[str, Any]]:
        result = await db.execute(select(TrainingJob).where(TrainingJob.id == job_id))
        job = result.scalar_one_or_none()
        if not job:
            return None
        return {
            "id": str(job.id),
            "model_version_id": str(job.model_version_id),
            "job_type": job.job_type,
            "status": job.status,
            "training_samples": job.training_samples,
            "current_epoch": job.current_epoch,
            "total_epochs": job.total_epochs,
            "current_step": job.current_step,
            "total_steps": job.total_steps,
            "current_loss": job.current_loss,
            "final_loss": job.final_loss,
            "eval_metrics": job.eval_metrics,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "triggered_by": job.triggered_by,
            "error_message": job.error_message,
            "idempotency_key": job.idempotency_key,
            "replayed_from_job_id": str(job.replayed_from_job_id) if job.replayed_from_job_id else None,
        }

    async def replay_training_job(
        self,
        db: AsyncSession,
        job_id: str,
        replayed_by: str,
        idempotency_key: Optional[str] = None,
    ) -> dict[str, Any]:
        result = await db.execute(select(TrainingJob).where(TrainingJob.id == job_id))
        original_job = result.scalar_one_or_none()
        if not original_job:
            return {"status": "error", "message": "Training job not found"}
        if original_job.status in {"pending", "preparing", "running"}:
            return {
                "status": "error",
                "message": "Can only replay completed, failed, or cancelled jobs.",
                "job_id": str(original_job.id),
                "job_status": original_job.status,
            }

        resolved_idempotency_key = (idempotency_key or "").strip() or (
            f"replay:{original_job.id}:{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        )
        existing_job_result = await db.execute(
            select(TrainingJob)
            .where(TrainingJob.idempotency_key == resolved_idempotency_key)
            .order_by(TrainingJob.created_at.desc())
            .limit(1)
        )
        existing_job = existing_job_result.scalar_one_or_none()
        if existing_job:
            return {
                "status": "duplicate",
                "message": "Training job with this idempotency_key already exists.",
                "job_id": str(existing_job.id),
                "idempotency_key": resolved_idempotency_key,
            }

        version_result = await db.execute(
            select(ModelVersion).where(ModelVersion.id == original_job.model_version_id)
        )
        version = version_result.scalar_one_or_none()
        if not version:
            return {"status": "error", "message": "Model version not found"}

        replay_job = TrainingJob(
            model_version_id=original_job.model_version_id,
            job_type=original_job.job_type,
            status="pending",
            training_data_path=original_job.training_data_path,
            training_samples=original_job.training_samples,
            validation_samples=original_job.validation_samples,
            total_epochs=original_job.total_epochs,
            triggered_by=replayed_by,
            idempotency_key=resolved_idempotency_key,
            replayed_from_job_id=original_job.id,
        )
        db.add(replay_job)
        await db.commit()
        await db.refresh(replay_job)

        queue_result = await self.queue_service.enqueue(
            "training",
            "run_training_job",
            {
                "job_id": str(replay_job.id),
                "model_version_id": str(version.id),
                "version_tag": version.version_tag,
                "training_method": replay_job.job_type,
                "trace_id": request_id_ctx.get() or None,
            },
            idempotency_key=resolved_idempotency_key,
            trace_id=request_id_ctx.get() or None,
        )

        return {
            "status": "queued",
            "job_id": str(replay_job.id),
            "replayed_from_job_id": str(original_job.id),
            "model_version_id": str(version.id),
            "version_tag": version.version_tag,
            "idempotency_key": resolved_idempotency_key,
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

    async def get_dataset(self, db: AsyncSession, dataset_id: str) -> Optional[dict[str, Any]]:
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
        version_id: str,
        dataset_tag: Optional[str],
        eval_type: str = "offline",
        evaluated_by: Optional[str] = None,
    ) -> dict[str, Any]:
        result = await db.execute(select(ModelVersion).where(ModelVersion.id == version_id))
        version = result.scalar_one_or_none()
        if not version:
            return {"status": "error", "message": "Model version not found"}

        if version.status not in ("completed", "training"):
            return {
                "status": "error",
                "message": f"Cannot evaluate version in '{version.status}' state; must be completed first.",
            }

        requested_dataset_tag = dataset_tag or "evaluation"
        resolved_dataset_tag = requested_dataset_tag
        dataset_role = self._dataset_role_from_tag(requested_dataset_tag)
        if requested_dataset_tag in {"latest", "evaluation", "holdout"}:
            reference_bundles = await self._ensure_reference_datasets(
                db,
                created_by=evaluated_by or "system",
            )
            resolved_bundle = reference_bundles.get(dataset_role if dataset_role in {"evaluation", "holdout"} else "evaluation")
            resolved_dataset_tag = resolved_bundle.get("dataset_tag") if resolved_bundle else None
            if not resolved_dataset_tag:
                return {
                    "status": "error",
                    "message": f"Reference dataset for role '{dataset_role}' is not ready.",
                }

        evaluation = ModelEvaluation(
            model_version_id=version.id,
            dataset_tag=resolved_dataset_tag,
            eval_type=eval_type,
            eval_status="pending",
            evaluated_by=evaluated_by or "system",
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
                "dataset_tag": resolved_dataset_tag,
                "eval_type": eval_type,
            },
            idempotency_key=f"{version.id}:{resolved_dataset_tag}:{eval_type}",
            trace_id=request_id_ctx.get() or None,
        )

        return {
            "status": "created",
            "evaluation_id": str(evaluation.id),
            "eval_type": eval_type,
            "dataset_tag": resolved_dataset_tag,
            "eval_status": "pending",
        }

    async def canary_version(self, db: AsyncSession, version_id: str) -> dict[str, Any]:
        result = await db.execute(select(ModelVersion).where(ModelVersion.id == version_id))
        candidate = result.scalar_one_or_none()
        if not candidate:
            return {"status": "error", "message": "Model version not found"}

        stable_result = await db.execute(select(ModelVersion).where(ModelVersion.is_active == True))
        stable = stable_result.scalar_one_or_none()
        stable_approve = float((stable.eval_metrics or {}).get("acceptance_rate", (stable.eval_metrics or {}).get("approve_rate", 0.78))) if stable else 0.78
        candidate_approve = float((candidate.eval_metrics or {}).get("acceptance_rate", (candidate.eval_metrics or {}).get("approve_rate", 0.79)))
        win_rate = candidate_approve - stable_approve

        canary_plan = {
            "status": "planned",
            "min_days": settings.TRAINING_AB_TEST_MIN_DAYS,
            "champion_traffic_share": round(1.0 - float(settings.TRAINING_CHALLENGER_TRAFFIC_SHARE), 2),
            "challenger_traffic_share": round(float(settings.TRAINING_CHALLENGER_TRAFFIC_SHARE), 2),
            "started_at": datetime.now(timezone.utc).isoformat(),
            "candidate_version": candidate.version_tag,
            "champion_version": stable.version_tag if stable else None,
        }
        candidate.status = "canary"
        if candidate.eval_metrics:
            candidate.eval_metrics["ab_test_plan"] = canary_plan
        else:
            candidate.eval_metrics = {"ab_test_plan": canary_plan}
        await db.commit()

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
            "ab_test_plan": canary_plan,
        }

    async def promote_version(self, db: AsyncSession, version_id: str, promoted_by: str) -> dict[str, Any]:
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

        stable_result = await db.execute(select(ModelVersion).where(ModelVersion.is_active == True))
        stable = stable_result.scalar_one_or_none()
        await db.execute(update(ModelVersion).values(is_active=False))
        candidate.is_active = True
        candidate.status = "active"
        if stable and stable.id != candidate.id:
            stable.status = "archived"
            hyperparameters = candidate.hyperparameters if isinstance(candidate.hyperparameters, dict) else {}
            hyperparameters["previous_champion_id"] = stable.id
            hyperparameters["promotion_checks"] = gate["checks"]
            hyperparameters["promoted_at"] = datetime.now(timezone.utc).isoformat()
            candidate.hyperparameters = hyperparameters
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

    async def rollback_to_version(self, db: AsyncSession, version_id: str) -> dict[str, Any]:
        result = await db.execute(select(ModelVersion).where(ModelVersion.id == version_id))
        target = result.scalar_one_or_none()
        if not target:
            return {"status": "error", "message": "Model version not found"}
        if target.status != "completed":
            return {"status": "error", "message": "Can only rollback to completed model versions"}

        await db.execute(update(ModelVersion).values(is_active=False))
        target.is_active = True
        target.status = "active"
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
        role_evaluations: dict[str, Optional[ModelEvaluation]] = {}
        for role in ("evaluation", "holdout"):
            prefix = self._dataset_prefix_for_role(role)
            latest_eval_result = await db.execute(
                select(ModelEvaluation)
                .where(
                    ModelEvaluation.model_version_id == candidate.id,
                    ModelEvaluation.eval_status == "completed",
                    ModelEvaluation.dataset_tag.like(f"{prefix}-%"),
                )
                .order_by(desc(ModelEvaluation.created_at))
                .limit(1)
            )
            role_evaluations[role] = latest_eval_result.scalar_one_or_none()

        primary_eval = role_evaluations.get("evaluation")
        holdout_eval = role_evaluations.get("holdout")
        primary_metrics = primary_eval.metrics if primary_eval and isinstance(primary_eval.metrics, dict) else {}
        holdout_metrics = holdout_eval.metrics if holdout_eval and isinstance(holdout_eval.metrics, dict) else {}

        primary_regressions = primary_metrics.get("regression_delta_vs_champion") or {}
        holdout_regressions = holdout_metrics.get("regression_delta_vs_champion") or {}

        checks = {
            "evaluation_exists": primary_eval is not None and primary_eval.pass_fail is True,
            "holdout_exists": holdout_eval is not None and holdout_eval.pass_fail is True,
            "human_review_passed": all(
                evaluation is not None and evaluation.spot_check_status in ("not_required", "approved")
                for evaluation in role_evaluations.values()
            ),
            "acceptance_improvement": float(primary_metrics.get("acceptance_delta_vs_champion", -1.0)) >= float(settings.TRAINING_ACCEPTANCE_IMPROVEMENT_GATE),
            "no_eval_regression": all(
                float(delta) >= -float(settings.TRAINING_MAX_METRIC_REGRESSION)
                for delta in primary_regressions.values()
            ) if primary_regressions else False,
            "no_holdout_regression": all(
                float(delta) >= -float(settings.TRAINING_MAX_METRIC_REGRESSION)
                for delta in holdout_regressions.values()
            ) if holdout_regressions else False,
            "hallucination_non_increase": (
                float(primary_metrics.get("hallucination_delta_vs_champion", 1.0)) <= 0.0
                and float(holdout_metrics.get("hallucination_delta_vs_champion", 1.0)) <= 0.0
            ),
            "latency_budget": (
                float(primary_metrics.get("latency_p95_ms", 0.0)) <= settings.PROMOTION_MAX_P95_LATENCY_MS
                or float(primary_metrics.get("latency_p95_ms", 0.0)) == 0.0
            ),
            "timeout_budget": (
                float(primary_metrics.get("timeout_rate", 0.0)) <= settings.PROMOTION_MAX_TIMEOUT_RATE
                or float(primary_metrics.get("timeout_rate", 0.0)) == 0.0
            ),
            "canary_plan_recorded": isinstance((candidate.eval_metrics or {}).get("ab_test_plan"), dict),
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
                "primary_evaluation_id": str(primary_eval.id) if primary_eval else None,
                "holdout_evaluation_id": str(holdout_eval.id) if holdout_eval else None,
                "acceptance_delta_vs_champion": primary_metrics.get("acceptance_delta_vs_champion"),
                "primary_regressions": primary_regressions,
                "holdout_regressions": holdout_regressions,
                "primary_hallucination_delta": primary_metrics.get("hallucination_delta_vs_champion"),
                "holdout_hallucination_delta": holdout_metrics.get("hallucination_delta_vs_champion"),
                "spot_check_status": {
                    role: evaluation.spot_check_status if evaluation else None
                    for role, evaluation in role_evaluations.items()
                },
            },
        }

    # ═══════════════════════════════════════════
    # Helpers
    # ═══════════════════════════════════════════

    @staticmethod
    def _build_sft_instruction(q: Question) -> str:
        """Build the instruction string for an SFT sample."""
        parts = [f"Generate one high-quality {q.question_type or 'question'} for a university-level assessment"]
        if q.difficulty_level:
            parts.append(f"at {q.difficulty_level} difficulty")
        if q.bloom_taxonomy_level:
            parts.append(f"targeting the {q.bloom_taxonomy_level} Bloom level")
        if q.marks:
            parts.append(f"worth {q.marks} marks")
        parts.append("Use the provided source context and follow the requested format exactly")
        return " ".join(parts) + "."

    @classmethod
    def _build_sft_output(cls, q: Question) -> str:
        """Build the output string for an SFT sample."""
        parts = ["Question:", q.question_text.strip()]
        if q.options:
            parts.append("")
            parts.append("Options:")
            for i, opt in enumerate(q.options):
                parts.append(f"{chr(65 + i)}. {cls._strip_choice_prefix(str(opt))}")
        if q.correct_answer:
            parts.append("")
            parts.append(f"Correct Answer: {cls._normalize_correct_answer(q.correct_answer, q.options)}")
        if q.explanation:
            parts.append("")
            parts.append(f"Explanation: {q.explanation.strip()}")
        return "\n".join(parts)

    # ═══════════════════════════════════════════
    # Phase 5: Rejection Pattern Learning
    # ═══════════════════════════════════════════

    async def get_rejection_patterns(
        self,
        db: AsyncSession,
        subject_id: Optional[str] = None,
        topic_id: Optional[str] = None,
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
        subject_id: Optional[str] = None,
        topic_id: Optional[str] = None,
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
