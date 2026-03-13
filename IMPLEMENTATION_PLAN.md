# Question Generation Model Plan

## 1. End Goal

Build a continuously improving Question Generation LLM or SLM that learns from real vetting behavior and converges toward approved quality standards.

The model must learn:
- What gets approved and why.
- What gets rejected and why.
- How edits transform weak questions into approved questions.
- How quality standards vary by difficulty, Bloom level, subject, and topic.

The system must support at least 200 active users post-deployment without degradation in user experience.

## 2. Current State (Already Present)

From the current backend and web flows, these foundations already exist:
- Vetting logs with decision types (approve, reject, edit).
- Training pairs for DPO style learning.
- Model version and training job tracking.
- Training endpoints in /api/v1/training.
- Vetter submit endpoint that can create training pairs.
- Question versioning and vetting status lifecycle.

This is a strong base. The remaining work is mostly quality of labels, training orchestration, evaluation gates, and production scale hardening.

## 3. Gaps To Close

1. Labels are not standardized enough for learning quality.
2. Rejection reasoning is not normalized into a taxonomy usable for training analytics.
3. Training data curation rules are weak (noise, duplicates, low-confidence pairs).
4. No strict promotion gate from candidate model to active model.
5. No canary or shadow deployment loop for model rollout.
6. No robust queue based architecture for high concurrency and long-running jobs.
7. Missing explicit SLOs, capacity plan, and failure runbooks for 200+ users.

## 4. Target Architecture

## 4.1 Feedback And Learning Loop

1. Generate question.
2. Human vetter decides: approve, reject, or edit.
3. Persist rich feedback with structured reason taxonomy.
4. Convert events into:
- SFT samples from approved outputs.
- Preference pairs from edit and reject-to-approve transitions.
- Critique labels for a quality classifier or reward model.
5. Run scheduled training pipeline.
6. Evaluate candidate model on frozen benchmark + live shadow traffic.
7. Promote only if quality and safety gates pass.
8. Monitor drift and regressions.

## 4.2 Serving Pattern

Use dual model serving:
- Stable model: currently active production model.
- Candidate model: receives shadow or canary traffic.

Fallback policy:
- If candidate times out or quality score is below threshold, use stable model result.

## 5. Backend Changes Required

## 5.1 Data Model Changes

Apply new migrations for the following additions.

### A. Vetting quality schema

Table: vetting_logs
- Add review_version integer default 1.
- Add quality_score numeric (0 to 1).
- Add rubric_snapshot jsonb storing rubric used at decision time.
- Add reason_codes text[] where each code comes from controlled taxonomy.
- Add severity_level text for rejection severity (minor, major, critical).

Why:
- Makes labels trainable and auditable.
- Preserves historical rubric context when standards evolve.

### B. Training pair quality controls

Table: training_pairs
- Add dedupe_hash text unique for pair identity.
- Add pair_weight numeric default 1.0.
- Add language text default en.
- Add source_split text (train, val, test).
- Add rejected_reason_codes text[].

Why:
- Enables weighted training and deterministic dataset versions.

### C. Dataset registry

New table: training_datasets
- id, dataset_tag, created_at, created_by.
- snapshot_filter jsonb (time range, subjects, confidence min).
- sample_counts jsonb (sft, dpo, critique labels).
- manifest_path text.
- checksum text.

Why:
- Every model must be reproducible from a frozen dataset snapshot.

### D. Evaluation registry

New table: model_evaluations
- id, model_version_id, dataset_tag, eval_type.
- metrics jsonb.
- pass_fail boolean.
- created_at.

Why:
- Promotion should require explicit evaluated evidence.

## 5.2 API Changes

Add or update endpoints under /api/v1:

1. Vetting taxonomy endpoints
- GET /vetter/reason-codes
- POST /vetter/reason-codes (admin)

2. Improved submit endpoint contract
- Require at least one structured reason code on reject.
- Optional free text remains allowed but not sufficient alone.
- For edit, capture field-level change rationale.

3. Training dataset control
- POST /training/datasets/build
- GET /training/datasets
- GET /training/datasets/{id}

4. Evaluation and promotion flow
- POST /training/evaluate/{version_id}
- POST /training/versions/{id}/canary
- POST /training/versions/{id}/promote
- POST /training/versions/{id}/rollback

5. Operational endpoints
- GET /training/queue/status
- GET /models/live-metrics

## 5.3 Pipeline and Worker Changes

Create asynchronous workers and queues for:
- Dataset building.
- SFT and DPO training jobs.
- Evaluation jobs.
- Offline embedding and analytics jobs.

Recommended queue stack:
- Redis Streams or Celery with Redis broker.

Worker design:
- Separate worker pools per job type.
- GPU-bound jobs isolated from API workers.
- Strict job idempotency and retry policy with dead-letter queue.

## 5.4 Quality Gate Logic

Implement model promotion gate in backend service layer:

A candidate can be promoted only if all are true:
- Offline benchmark pass rate >= configured threshold.
- Live canary approve-rate is not worse than stable model by margin.
- Rejection critical-reason rate does not increase.
- Latency and timeout budget stay within SLO.

If any check fails:
- Keep stable model active.
- Mark candidate failed for promotion.
- Auto-generate failure summary for admin.

## 5.5 Prompt and Generation Controls

Backend generation service should use:
- Strict output schema validation.
- Difficulty specific prompt templates.
- Rejection-aware negative instructions based on top historical reason codes.
- Optional two-pass generation: generate then self-critique then repair.

## 5.6 Observability and Reliability

Add metrics:
- approve_rate_by_model
- reject_rate_by_reason_code
- edit_distance_mean
- training_dataset_size_by_type
- model_canary_win_rate
- generation_timeout_rate

Add traces with request and model version IDs end to end.

Define SLOs:
- API p95 latency for generation stream start.
- Vetting submit success rate.
- Training pipeline job success rate.

## 6. Frontend Changes Required (Mobile + Trainer Web)

## 6.1 Vetting UX Improvements

In trainer-web and mobile vetting screens:
- Replace free-form reject reasons with selectable taxonomy chips.
- Keep optional free text feedback.
- Force minimum feedback quality for reject and edit decisions.
- Collect quick rubric scores per question:
  - correctness
  - clarity
  - cognitive level match
  - syllabus alignment

Why:
- Better labels produce better models.

## 6.2 Confidence and Explainability UI

Show to vetters:
- Model version tag used for generation.
- Source references and rationale.
- Historical similar rejections for awareness.

Why:
- Faster and more consistent vetting decisions.

## 6.3 Training Ops Dashboard

In trainer-web admin section add:
- Dataset builder controls.
- Training run monitor (queued, running, failed).
- Evaluation scoreboard comparing stable vs candidate.
- Canary rollout slider (1 percent, 5 percent, 10 percent, 25 percent, 50 percent).
- One-click rollback.

## 7. Scale Plan For 200+ Users

## 7.1 Expected load assumptions

Assume 200 active users with mixed actions:
- 120 browsing and vetting.
- 50 generating questions.
- 30 doing uploads and admin operations.

Design for 2x burst headroom.

## 7.2 Runtime topology

Use separate services:
- api-service: stateless FastAPI replicas behind load balancer.
- worker-service: async CPU workers.
- gpu-trainer-service: isolated training and heavy inference.
- postgres primary with backups.
- redis for cache, queue, and session blacklist.
- object storage for datasets, adapters, exports.

## 7.3 Capacity targets

Starting point for 200 users:
- API replicas: 3 to 4 instances, 2 to 4 workers each.
- Worker replicas: 2 to 3 CPU workers.
- GPU nodes: 1 for training plus 1 optional standby.
- Postgres: tuned connection pool and indexes for vetting and question queries.

## 7.4 Performance and data strategies

- Add pagination and indexed filters for all listing endpoints.
- Cache hot dashboard aggregates in Redis with short TTL.
- Use read replicas if analytics query pressure increases.
- Move long aggregation to background jobs.
- Use SSE carefully with heartbeat and timeout handling.

## 7.5 High availability and disaster recovery

- Daily backups for Postgres and model artifact registry.
- Versioned object storage for adapters and datasets.
- Recovery drill every 2 weeks.
- Rollback plan tested before each model promotion.

## 8. Security and Compliance

- Role based access with strict admin actions for training and promotion.
- Audit logs for all model and dataset operations.
- PII minimization in feedback logs.
- Secrets in secret manager, not env files in production.
- Rate limiting and abuse detection on generation endpoints.

## 9. MLOps Standards

## 9.1 Dataset versioning

Every training run must store:
- dataset tag
- filtering policy
- sampling strategy
- checksum

## 9.2 Experiment tracking

Track for each run:
- hyperparameters
- commit hash
- dataset tag
- evaluation metrics
- artifact paths

## 9.3 Model card per version

Generate a model card containing:
- intended use
- known failure modes
- benchmark and canary results
- approval date and approver

## 10. Rollout Roadmap

## Phase 1: Label quality foundation (1 to 2 weeks)
- Add reason taxonomy and mandatory structured reject reasons.
- Add rubric score capture in vetting UI.
- Add new schema fields and migrations.

## Phase 2: Data curation and registry (1 to 2 weeks)
- Implement dataset snapshot builder.
- Add dedupe and weighting logic.
- Build admin dataset pages.

## Phase 3: Training and eval hardening (2 to 3 weeks)
- Queue based training workers.
- Offline benchmark suite and evaluation endpoints.
- Promotion gate enforcement.

## Phase 4: Canary and scale readiness (2 weeks)
- Candidate shadow and canary traffic.
- Rollback workflows.
- Load testing and SLO verification for 200+ users.

## Phase 5: Continuous optimization (ongoing)
- Drift detection and weekly retraining cadence.
- Prompt and rubric updates.
- Cost and latency optimization.

## 11. Concrete File Level Change Guide

Backend likely touched files:
- backend/app/models/training.py
- backend/app/models/question.py
- backend/app/api/v1/endpoints/vetter.py
- backend/app/api/v1/endpoints/training.py
- backend/app/services/training_service.py
- backend/app/services/question_service.py
- backend/app/services/llm_service.py
- backend/alembic/versions/new_migration_files.py

Frontend likely touched files:
- trainer-web/src/lib/api/vetting.ts
- trainer-web/src/routes/vetter/loop/+page.svelte
- trainer-web/src/routes/vetter/subjects/[id]/+page.svelte
- trainer-web/src/routes/teacher/verify/+page.svelte
- client/components/swipe-vetting.tsx
- client/services/vetting.ts
- client/services/questions.ts

Ops and deployment files:
- docker-compose.yml
- docker-compose.prod.yml
- backend/Dockerfile
- monitoring dashboards and alert configs

## 12. Definition Of Done

A release is complete only if:
1. At least one full retraining cycle runs from real vetting data to promoted model.
2. Candidate model outperforms stable model on agreed quality metrics.
3. Canary rollout and rollback both tested in production-like environment.
4. Load test confirms stable behavior at 200 concurrent users with SLO compliance.
5. Dashboards show quality, latency, and failure metrics by model version.
6. Runbooks exist for incident response, rollback, and data recovery.

## 13. Immediate Next Actions

1. Finalize rejection reason taxonomy and rubric definitions with academic stakeholders.
2. Implement migration set for data model additions.
3. Enforce structured feedback in vetter submit API and UI.
4. Build dataset snapshot registry and evaluation endpoint.
5. Add canary promotion gate before any automatic activation.

---

Owner recommendation:
- Product and pedagogy owner for quality rubric.
- ML owner for training and evaluation policy.
- Backend owner for pipeline and API reliability.
- Frontend owner for vetting UX standardization.
- DevOps owner for scaling, observability, and incident readiness.
