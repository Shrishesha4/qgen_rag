import { apiFetch } from './client';

export interface QuestionRecord {
	id: string;
	document_id: string | null;
	subject_id: string | null;
	topic_id: string | null;
	question_text: string;
	question_type: string | null;
	marks: number | null;
	difficulty_level: string | null;
	bloom_taxonomy_level: string | null;
	options: string[] | null;
	correct_answer: string | null;
	explanation: string | null;
	vetting_status: string;
	generated_at: string;
	is_archived: boolean;
}

export interface QuestionListResponse {
	questions: QuestionRecord[];
	pagination: {
		page: number;
		limit: number;
		total: number;
		total_pages: number;
	};
}

export interface ListQuestionsParams {
	documentId?: string;
	subjectId?: string;
	topicId?: string;
	vettingStatus?: string;
	page?: number;
	limit?: number;
	questionType?: string;
	difficulty?: string;
	showArchived?: boolean;
	includeAllVersions?: boolean;
}

export async function listQuestions(params: ListQuestionsParams = {}): Promise<QuestionListResponse> {
	const searchParams = new URLSearchParams();
	if (params.documentId) searchParams.set('document_id', params.documentId);
	if (params.subjectId) searchParams.set('subject_id', params.subjectId);
	if (params.topicId) searchParams.set('topic_id', params.topicId);
	if (params.vettingStatus) searchParams.set('vetting_status', params.vettingStatus);
	if (params.questionType) searchParams.set('question_type', params.questionType);
	if (params.difficulty) searchParams.set('difficulty', params.difficulty);
	if (params.showArchived) searchParams.set('show_archived', 'true');
	if (params.includeAllVersions) searchParams.set('include_all_versions', 'true');
	searchParams.set('page', String(params.page ?? 1));
	searchParams.set('limit', String(params.limit ?? 20));

	return apiFetch<QuestionListResponse>(`/questions?${searchParams.toString()}`);
}

export async function getQuestion(questionId: string): Promise<QuestionRecord> {
	return apiFetch<QuestionRecord>(`/questions/${questionId}`);
}