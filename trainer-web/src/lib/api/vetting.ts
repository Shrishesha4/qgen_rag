/** Vetting API — fetch questions for review, submit decisions. */
import { apiFetch } from './client';

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
	edited_text?: string;
	edited_options?: string[];
	edited_answer?: string;
	edited_explanation?: string;
	rejection_reasons?: string[];
	feedback?: string;
	notes?: string;
	time_spent_seconds?: number;
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
} = {}): Promise<QuestionListResult> {
	const params = new URLSearchParams();
	params.set('page', String(opts.page ?? 1));
	params.set('limit', String(opts.limit ?? 20));
	if (opts.status) params.set('status', opts.status);
	if (opts.subject_id) params.set('subject_id', opts.subject_id);
	if (opts.topic_id) params.set('topic_id', opts.topic_id);
	return apiFetch<QuestionListResult>(`/vetter/questions?${params}`);
}

export async function submitVetting(data: VetSubmission): Promise<{
	message: string;
	question_id: string;
	decision: string;
	vetting_log_id: string;
	training_pair_created: boolean;
}> {
	return apiFetch('/vetter/submit', {
		method: 'POST',
		body: JSON.stringify(data),
	});
}

export async function vetQuestion(
	questionId: string,
	data: { status: 'approved' | 'rejected'; notes?: string }
): Promise<{ message: string; question_id: string; status: string }> {
	return apiFetch(`/vetter/questions/${questionId}/vet`, {
		method: 'POST',
		body: JSON.stringify(data),
	});
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
	improved_text?: string;
	improved_options?: string[] | null;
	improved_answer?: string;
	improved_explanation?: string;
	changes?: Record<string, { old: string; new: string }>;
	error?: string;
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
