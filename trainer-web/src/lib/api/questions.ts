import { apiFetch } from './client';

export interface TeacherQuestionSummary {
	id: string;
	subject_id: string | null;
	subject_name: string | null;
	subject_code: string | null;
	topic_id: string | null;
	topic_name: string | null;
	question_text: string;
	question_type: string;
	correct_answer: string | null;
	explanation: string | null;
	marks: number | null;
	difficulty_level: string | null;
	bloom_taxonomy_level: string | null;
	vetting_status: string | null;
	generated_at: string;
	version_number: number;
}

export interface TeacherQuestionListResponse {
	questions: TeacherQuestionSummary[];
	total: number;
	page: number;
	limit: number;
	pages: number;
}

export interface TeacherQuestionFeedParams {
	group_id?: string;
	subject_id?: string;
	topic_id?: string;
	vetting_status?: 'pending' | 'approved' | 'rejected' | 'all';
	question_type?: 'mcq' | 'short_answer' | 'long_answer' | 'essay' | 'true_false' | 'unspecified' | 'all';
	difficulty?: 'easy' | 'medium' | 'hard' | 'unspecified' | 'all';
	search?: string;
	page?: number;
	limit?: number;
}

function buildTeacherQuestionSearchParams(params: TeacherQuestionFeedParams = {}): URLSearchParams {
	const searchParams = new URLSearchParams();
	if (params.group_id) searchParams.set('group_id', params.group_id);
	if (params.subject_id) searchParams.set('subject_id', params.subject_id);
	if (params.topic_id) searchParams.set('topic_id', params.topic_id);
	if (params.vetting_status && params.vetting_status !== 'all') searchParams.set('vetting_status', params.vetting_status);
	if (params.question_type && params.question_type !== 'all') searchParams.set('question_type', params.question_type);
	if (params.difficulty && params.difficulty !== 'all') searchParams.set('difficulty', params.difficulty);
	if (params.search) searchParams.set('search', params.search);
	if (params.page) searchParams.set('page', String(params.page));
	if (params.limit) searchParams.set('limit', String(params.limit));
	return searchParams;
}

export async function listTeacherQuestions(
	params: TeacherQuestionFeedParams = {}
): Promise<TeacherQuestionListResponse> {
	const searchParams = buildTeacherQuestionSearchParams(params);
	const suffix = searchParams.toString() ? `?${searchParams.toString()}` : '';
	return apiFetch<TeacherQuestionListResponse>(`/questions${suffix}`);
}