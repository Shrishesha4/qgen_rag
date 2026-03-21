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

export interface EvaluationResponse {
	id: string;
	model_version_id: string;
	eval_type: string;
	eval_status: string;
	dataset_tag: string | null;
	metrics: Record<string, unknown> | null;
	gate_checks: Record<string, unknown> | null;
	spot_check_status: string | null;
	spot_check_samples: Array<Record<string, unknown>> | null;
	spot_check_reviewed_by: string | null;
	spot_check_reviewed_at: string | null;
	spot_check_notes: string | null;
	evaluated_by: string | null;
	error_message: string | null;
	created_at: string | null;
	completed_at: string | null;
}

export interface TrainingPairResponse {
	id: string;
	prompt: string;
	chosen_response: string;
	rejected_response: string;
	pair_type: string;
	status: string;
	confidence: number | null;
	created_at: string | null;
}

export interface TrainingPairsListResponse {
	pairs: TrainingPairResponse[];
	total: number;
	page: number;
	limit: number;
}

export interface TrainingDataSummary {
	total_questions: number;
	approved_questions: number;
	pending_questions: number;
	dpo_pairs: number;
	subjects: number;
	bloom_distribution: Record<string, number>;
	difficulty_distribution: Record<string, number>;
	answer_distribution: Record<string, number>;
	sft_ready: boolean;
	dpo_ready: boolean;
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

export async function listEvaluations(versionId?: string, limit = 50): Promise<EvaluationResponse[]> {
	const params = new URLSearchParams();
	if (versionId) params.set('version_id', versionId);
	params.set('limit', String(limit));
	return apiFetch<EvaluationResponse[]>(`/training/evaluations?${params.toString()}`);
}

export async function getEvaluation(id: string): Promise<EvaluationResponse> {
	return apiFetch<EvaluationResponse>(`/training/evaluations/${id}`);
}

export async function completeSpotCheck(
	evaluationId: string,
	decision: 'approved' | 'rejected',
	notes?: string,
): Promise<Record<string, unknown>> {
	return apiFetch(`/training/evaluations/${evaluationId}/spot-check`, {
		method: 'POST',
		body: JSON.stringify({ decision, notes }),
	});
}

export async function listTrainingPairs(opts: {
	page?: number;
	limit?: number;
	pair_type?: string;
	pair_status?: string;
} = {}): Promise<TrainingPairsListResponse> {
	const params = new URLSearchParams();
	if (opts.page) params.set('page', String(opts.page));
	if (opts.limit) params.set('limit', String(opts.limit));
	if (opts.pair_type) params.set('pair_type', opts.pair_type);
	if (opts.pair_status) params.set('pair_status', opts.pair_status);
	return apiFetch<TrainingPairsListResponse>(`/training/pairs?${params.toString()}`);
}

export async function getTrainingDataSummary(): Promise<TrainingDataSummary> {
	return apiFetch<TrainingDataSummary>('/training/export/stats');
}
