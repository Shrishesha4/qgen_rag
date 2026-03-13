/** Training Pipeline API — status, trigger, model versions. */
import { apiFetch } from './client';

// ── Types ──

export interface TrainingStatus {
	active_version: {
		version_tag: string;
		base_model: string;
		training_method: string;
		eval_metrics: Record<string, unknown> | null;
		adapter_path: string | null;
	} | null;
	pipeline: {
		pending_dpo_pairs: number;
		total_dpo_pairs: number;
		total_sft_candidates: number;
		total_model_versions: number;
	};
	latest_job: {
		id: string;
		type: string;
		status: string;
		samples: number;
		current_epoch: number;
		total_epochs: number;
		loss: number | null;
		created_at: string | null;
		error: string | null;
	} | null;
}

export interface ModelVersionResponse {
	id: string;
	version_tag: string;
	base_model: string;
	training_method: string;
	sft_samples_count: number;
	training_pairs_count: number;
	is_active: boolean;
	status: string;
	eval_metrics: Record<string, unknown> | null;
	lora_adapter_path: string | null;
	created_at: string | null;
	training_completed_at: string | null;
	error_message: string | null;
}

export interface TrainingJobResponse {
	id: string;
	model_version_id: string;
	job_type: string;
	status: string;
	training_samples: number;
	current_epoch: number;
	total_epochs: number;
	current_step: number;
	total_steps: number;
	current_loss: number | null;
	final_loss: number | null;
	eval_metrics: Record<string, unknown> | null;
	created_at: string | null;
	started_at: string | null;
	completed_at: string | null;
	triggered_by: string | null;
	error_message: string | null;
}

export interface TrainingDatasetResponse {
	id: string;
	dataset_tag: string;
	created_at: string | null;
	created_by: string | null;
	snapshot_filter: Record<string, unknown> | null;
	sample_counts: Record<string, number> | null;
	manifest_path: string | null;
	checksum: string | null;
}

// ── API calls ──

export async function getTrainingStatus(): Promise<TrainingStatus> {
	return apiFetch<TrainingStatus>('/training/status');
}

export async function triggerTraining(opts: {
	training_method?: string;
	base_model?: string;
	hyperparameters?: Record<string, unknown>;
} = {}): Promise<Record<string, unknown>> {
	return apiFetch('/training/trigger', {
		method: 'POST',
		body: JSON.stringify({
			training_method: opts.training_method ?? 'sft',
			base_model: opts.base_model,
			hyperparameters: opts.hyperparameters,
		}),
	});
}

export async function listModelVersions(): Promise<ModelVersionResponse[]> {
	return apiFetch<ModelVersionResponse[]>('/training/versions');
}

export async function activateModelVersion(id: string): Promise<Record<string, unknown>> {
	return apiFetch(`/training/versions/${id}/activate`, { method: 'POST' });
}

export async function listTrainingJobs(limit = 20): Promise<TrainingJobResponse[]> {
	return apiFetch<TrainingJobResponse[]>(`/training/jobs?limit=${limit}`);
}

export async function buildTrainingDataset(snapshot_filter?: Record<string, unknown>): Promise<Record<string, unknown>> {
	return apiFetch('/training/datasets/build', {
		method: 'POST',
		body: JSON.stringify({ snapshot_filter }),
	});
}

export async function listTrainingDatasets(limit = 50): Promise<TrainingDatasetResponse[]> {
	return apiFetch<TrainingDatasetResponse[]>(`/training/datasets?limit=${limit}`);
}

export async function getTrainingDataset(id: string): Promise<TrainingDatasetResponse> {
	return apiFetch<TrainingDatasetResponse>(`/training/datasets/${id}`);
}

export async function evaluateModelVersion(
	versionId: string,
	opts: { dataset_tag?: string; eval_type?: string } = {}
): Promise<Record<string, unknown>> {
	const params = new URLSearchParams();
	if (opts.dataset_tag) params.set('dataset_tag', opts.dataset_tag);
	if (opts.eval_type) params.set('eval_type', opts.eval_type);
	const suffix = params.toString() ? `?${params.toString()}` : '';
	return apiFetch(`/training/evaluate/${versionId}${suffix}`, { method: 'POST' });
}

export async function canaryModelVersion(versionId: string): Promise<Record<string, unknown>> {
	return apiFetch(`/training/versions/${versionId}/canary`, { method: 'POST' });
}

export async function promoteModelVersion(versionId: string): Promise<Record<string, unknown>> {
	return apiFetch(`/training/versions/${versionId}/promote`, { method: 'POST' });
}

export async function rollbackModelVersion(versionId: string): Promise<Record<string, unknown>> {
	return apiFetch(`/training/versions/${versionId}/rollback`, { method: 'POST' });
}

export async function getTrainingQueueStatus(): Promise<Record<string, unknown>> {
	return apiFetch('/training/queue/status');
}

export async function getLiveModelMetrics(): Promise<Record<string, unknown>> {
	return apiFetch('/models/live-metrics');
}
