/** Vetting API — fetch questions for review, submit decisions. */
import { apiFetch } from './client';
import { session } from '../session';
import { get } from 'svelte/store';

// ── Types ──

export interface VetterDashboard {
	total_pending: number;
	total_approved: number;
	total_rejected: number;
	teachers_with_pending: number;
	subjects_with_pending: number;
	recent_submissions: number;
}

export interface SourceReference {
	document_name: string | null;
	page_number: number | null;
	page_range: number[] | null;
	position_in_page: string | null;
	position_percentage: number | null;
	section_heading: string | null;
	content_snippet: string | null;
	highlighted_phrase: string | null;
	relevance_reason: string | null;
}

export interface QuestionSourceInfo {
	sources: SourceReference[];
	generation_reasoning: string | null;
	content_coverage: string | null;
}

export interface QuestionForVetting {
	id: string;
	question_text: string;
	question_type: string;
	options: string[] | null;
	correct_answer: string | null;
	explanation: string | null;
	marks: number | null;
	difficulty_level: string | null;
	bloom_taxonomy_level: string | null;
	vetting_status: string;
	vetting_notes: string | null;
	generated_at: string;
	teacher_id: string | null;
	teacher_name: string | null;
	subject_id: string | null;
	subject_name: string | null;
	subject_code: string | null;
	topic_id: string | null;
	topic_name: string | null;
	source_info: QuestionSourceInfo | null;
	version_number: number;
}

export interface QuestionListResult {
	questions: QuestionForVetting[];
	total: number;
	page: number;
	limit: number;
	pages: number;
}

export interface VetSubmission {
	question_id: string;
	decision: 'approve' | 'reject' | 'edit';
	approved_difficulty?: 'easy' | 'medium' | 'hard';
	edited_text?: string;
	edited_options?: string[];
	edited_answer?: string;
	edited_explanation?: string;
	rejection_reasons?: string[];
	feedback?: string;
	notes?: string;
	time_spent_seconds?: number;
}

interface ReasonCodeEntry {
	id: string;
	code: string;
	label: string;
	description?: string | null;
	severity_default: string;
	is_active: boolean;
	created_at: string;
}

const TAXONOMY_CACHE_TTL_MS = 5 * 60 * 1000;
let taxonomyLoadedAt = 0;
let reasonCodeEntries: ReasonCodeEntry[] = [];
let reasonLabelToCode = new Map<string, string>();
let reasonCodeSet = new Set<string>();
let fallbackReasonCode = 'quality_issue';

export interface VetterQuestionUpdate {
	marks?: number;
	difficulty_level?: 'easy' | 'medium' | 'hard';
	bloom_taxonomy_level?: string;
	correct_answer?: string;
	options?: string[];
	question_text?: string;
	course_outcome_mapping?: Record<string, unknown>;
	learning_outcome_id?: string;
}

export interface VetterTopicSummary {
	id: string;
	name: string;
	pending_count: number;
}

export interface VetterSubjectSummary {
	id: string;
	name: string;
	code: string;
	description: string | null;
	teacher_id: string;
	teacher_name: string;
	pending_count: number;
	approved_count: number;
	rejected_count: number;
	topics: VetterTopicSummary[];
}

function normalizeReasonLabel(value: string): string {
	return value.trim().toLowerCase().replace(/\s+/g, ' ');
}

function toCandidateCode(label: string): string {
	return label
		.trim()
		.toUpperCase()
		.replace(/[^A-Z0-9]+/g, '_')
		.replace(/^_+|_+$/g, '');
}

export async function warmVettingTaxonomy(force = false): Promise<void> {
	const now = Date.now();
	if (!force && now - taxonomyLoadedAt < TAXONOMY_CACHE_TTL_MS && reasonCodeEntries.length > 0) {
		return;
	}

	// Check if user is authenticated before making API call
	const currentSession = get(session);
	
	if (!currentSession) {
		// User not authenticated, don't fetch taxonomy
		return;
	}

	try {
		const entries = await apiFetch<ReasonCodeEntry[]>('/vetter/reason-codes');
		reasonCodeEntries = entries;
		reasonLabelToCode = new Map();
		reasonCodeSet = new Set(entries.map((entry) => entry.code.toLowerCase()));

		for (const entry of entries) {
			reasonLabelToCode.set(normalizeReasonLabel(entry.label), entry.code);
			if (entry.description) {
				reasonLabelToCode.set(normalizeReasonLabel(entry.description), entry.code);
			}
		}

		fallbackReasonCode = reasonCodeSet.has('quality_issue')
			? 'quality_issue'
			: entries[0]?.code ?? 'quality_issue';
		taxonomyLoadedAt = now;
	} catch {
		if (reasonCodeEntries.length === 0) {
			fallbackReasonCode = 'quality_issue';
		}
	}
}

async function mapReasonLabelsToCodes(labels?: string[]): Promise<string[]> {
	await warmVettingTaxonomy(false);
	if (!labels || labels.length === 0) {
		return [fallbackReasonCode];
	}

	const mapped: string[] = [];
	for (const label of labels) {
		const normalized = normalizeReasonLabel(label);
		const exact = reasonLabelToCode.get(normalized);
		if (exact) {
			mapped.push(exact);
			continue;
		}

		const candidateCode = toCandidateCode(label).toLowerCase();
		if (reasonCodeSet.has(candidateCode)) {
			mapped.push(candidateCode);
			continue;
		}

		const fuzzy = reasonCodeEntries.find((entry) => {
			const labelText = normalizeReasonLabel(entry.label);
			const descText = normalizeReasonLabel(entry.description || '');
			return labelText.includes(normalized) || normalized.includes(labelText) || descText.includes(normalized);
		});
		mapped.push(fuzzy?.code ?? fallbackReasonCode);
	}

	const uniqueCodes = [...new Set(mapped.filter(Boolean))];
	return uniqueCodes.length > 0 ? uniqueCodes : [fallbackReasonCode];
}

function buildFieldChangeRationale(data: VetSubmission): Record<string, string> | undefined {
	if (data.decision !== 'edit') return undefined;
	const rationale: Record<string, string> = {};
	if (typeof data.edited_text !== 'undefined') {
		rationale.question_text = 'Teacher edited wording';
	}
	if (typeof data.edited_answer !== 'undefined') {
		rationale.correct_answer = 'Correct answer corrected';
	}
	if (typeof data.edited_options !== 'undefined') {
		rationale.options = 'Options adjusted';
	}
	if (typeof data.edited_explanation !== 'undefined') {
		rationale.explanation = 'Explanation clarified';
	}
	return Object.keys(rationale).length > 0 ? rationale : undefined;
}

async function adaptVettingPayload(data: VetSubmission): Promise<Record<string, unknown>> {
	const payload: Record<string, unknown> = {
		...data,
		review_version: 1,
	};

	if (data.decision === 'reject') {
		payload.reason_codes = await mapReasonLabelsToCodes(data.rejection_reasons);
	}

	if (data.decision === 'edit') {
		const rationale = buildFieldChangeRationale(data);
		if (rationale) payload.field_change_rationale = rationale;
	}

	return payload;
}

// ── API calls ──

export async function getVetterDashboard(): Promise<VetterDashboard> {
	return apiFetch<VetterDashboard>('/vetter/dashboard');
}

export async function getVetterSubjects(): Promise<VetterSubjectSummary[]> {
	return apiFetch<VetterSubjectSummary[]>('/vetter/subjects');
}

export async function getVetterSubject(id: string): Promise<VetterSubjectSummary> {
	return apiFetch<VetterSubjectSummary>(`/vetter/subjects/${id}`);
}

export async function getQuestionsForVetting(opts: {
	page?: number;
	limit?: number;
	status?: string;
	subject_id?: string;
	topic_id?: string;
	search?: string;
} = {}): Promise<QuestionListResult> {
	const normalizedLimit = Math.max(1, Math.min(100, Math.trunc(opts.limit ?? 20)));
	const params = new URLSearchParams();
	params.set('page', String(opts.page ?? 1));
	params.set('limit', String(normalizedLimit));
	if (opts.status) params.set('status', opts.status);
	if (opts.subject_id) params.set('subject_id', opts.subject_id);
	if (opts.topic_id) params.set('topic_id', opts.topic_id);
	if (opts.search) params.set('search', opts.search);
	return apiFetch<QuestionListResult>(`/vetter/questions?${params}`);
}

export async function submitVetting(data: VetSubmission): Promise<{
	message: string;
	question_id: string;
	decision: string;
	vetting_log_id: string;
	training_pair_created: boolean;
}> {
	const adapted = await adaptVettingPayload(data);
	return apiFetch('/vetter/submit', {
		method: 'POST',
		body: JSON.stringify(adapted),
	});
}

export async function updateVettedQuestion(questionId: string, data: VetterQuestionUpdate): Promise<{
	message: string;
	question_id: string;
	question: QuestionForVetting;
}> {
	return apiFetch(`/vetter/questions/${questionId}`, {
		method: 'PUT',
		body: JSON.stringify(data),
	});
}

export async function listTeacherVettingProgressRemote(opts: {
	subject_id?: string;
	topic_id?: string;
} = {}): Promise<TeacherVettingProgressRecord[]> {
	const params = new URLSearchParams();
	if (opts.subject_id) params.set('subject_id', opts.subject_id);
	if (opts.topic_id) params.set('topic_id', opts.topic_id);
	const query = params.toString();
	return apiFetch<TeacherVettingProgressRecord[]>(
		query ? `/vetter/progress?${query}` : '/vetter/progress'
	);
}

export async function upsertTeacherVettingProgressRemote(
	payload: TeacherVettingProgressUpsertPayload
): Promise<TeacherVettingProgressRecord> {
	return apiFetch<TeacherVettingProgressRecord>('/vetter/progress', {
		method: 'POST',
		body: JSON.stringify(payload),
	});
}

export async function deleteTeacherVettingProgressRemote(key: string): Promise<void> {
	const params = new URLSearchParams();
	params.set('key', key);
	await apiFetch<void>(`/vetter/progress?${params.toString()}`, {
		method: 'DELETE',
	});
}

export async function vetQuestion(
	questionId: string,
	data: { status: 'approved' | 'rejected'; notes?: string; rejection_reasons?: string[] }
): Promise<{ message: string; question_id: string; status: string }> {
	const decision = data.status === 'approved' ? 'approve' : 'reject';
	const submission: VetSubmission = {
		question_id: questionId,
		decision,
		notes: data.notes,
		feedback: data.notes,
		rejection_reasons: data.rejection_reasons,
	};
	const result = await submitVetting(submission);
	return {
		message: result.message,
		question_id: result.question_id,
		status: data.status,
	};
}

export interface RejectWithFeedbackRequest {
	feedback: string;
	rejection_reasons?: string[];
	generate_new?: boolean;
}

export interface RejectWithFeedbackResponse {
	message: string;
	question_id: string;
	decision: string;
	improved: boolean;
	regenerated: boolean;
	new_question_id?: string;
	new_question?: QuestionForVetting;
	improved_text?: string;
	improved_options?: string[] | null;
	improved_answer?: string;
	improved_explanation?: string;
	changes?: Record<string, { old: string; new: string }>;
	error?: string;
}

export interface TeacherVettingProgressRecord {
	key: string;
	subject_id: string;
	topic_id: string | null;
	mixed_topics_mode: boolean;
	selected_mixed_topic_ids: string[];
	generation_batch_size: number;
	allow_no_pdf_generation: boolean;
	questions: QuestionForVetting[];
	current_index: number;
	approved_question_ids: string[];
	rejected_question_ids: string[];
	batch_complete: boolean;
	updated_at: string;
	created_at: string;
}

export interface TeacherVettingProgressUpsertPayload {
	key: string;
	subject_id: string;
	topic_id?: string | null;
	mixed_topics_mode: boolean;
	selected_mixed_topic_ids: string[];
	generation_batch_size: number;
	allow_no_pdf_generation: boolean;
	questions: QuestionForVetting[];
	current_index: number;
	approved_question_ids: string[];
	rejected_question_ids: string[];
	batch_complete: boolean;
	updated_at?: string;
}

export async function rejectWithFeedback(
	questionId: string,
	data: RejectWithFeedbackRequest
): Promise<RejectWithFeedbackResponse> {
	return apiFetch(`/vetter/questions/${questionId}/reject-with-feedback`, {
		method: 'POST',
		body: JSON.stringify(data),
	});
}
