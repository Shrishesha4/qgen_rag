"""Application-specific Prometheus metrics for vetting and training pipelines."""

from prometheus_client import Counter, Gauge, Histogram


approve_rate_by_model = Gauge(
    "approve_rate_by_model",
    "Approval rate segmented by model version",
    ["model_version"],
)

reject_rate_by_reason_code = Gauge(
    "reject_rate_by_reason_code",
    "Reject rate segmented by reason code",
    ["reason_code"],
)

edit_distance_mean = Gauge(
    "edit_distance_mean",
    "Mean normalized edit distance between original and edited question",
)

training_dataset_size_by_type = Gauge(
    "training_dataset_size_by_type",
    "Training dataset sample counts by sample type",
    ["dataset_tag", "sample_type"],
)

model_canary_win_rate = Gauge(
    "model_canary_win_rate",
    "Canary approve-rate delta winner ratio against stable model",
    ["candidate_version", "stable_version"],
)

generation_timeout_rate = Gauge(
    "generation_timeout_rate",
    "Rate of generation timeouts",
    ["model_version"],
)

training_job_success_rate = Gauge(
    "training_pipeline_job_success_rate",
    "Rolling success ratio of training pipeline jobs",
    ["job_type"],
)

vetting_submit_success_total = Counter(
    "vetting_submit_success_total",
    "Count of successful vetting submissions",
)

vetting_submit_failure_total = Counter(
    "vetting_submit_failure_total",
    "Count of failed vetting submissions",
)

generation_stream_start_latency_ms = Histogram(
    "generation_stream_start_latency_ms",
    "Latency to first streaming chunk for generation endpoints",
    buckets=(10, 50, 100, 250, 500, 1000, 2000, 5000),
)
