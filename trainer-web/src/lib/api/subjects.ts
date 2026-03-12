/** Subjects & Topics API — CRUD for disciplines and their chapters. */
import { apiFetch } from './client';

// ── Types ──

export interface SubjectCreate {
	name: string;
	code: string;
	description?: string;
	learning_outcomes?: { id: string; name: string; description?: string }[];
	course_outcomes?: { id: string; name: string; description?: string }[];
}

export interface TopicResponse {
	id: string;
	subject_id: string;
	name: string;
	description: string | null;
	order_index: number;
	has_syllabus: boolean;
	syllabus_content: string | null;
	learning_outcome_mappings: Record<string, unknown> | null;
	total_questions: number;
	created_at: string;
	updated_at: string;
}

export interface SubjectResponse {
	id: string;
	user_id: string;
	name: string;
	code: string;
	description: string | null;
	learning_outcomes: Record<string, unknown> | null;
	course_outcomes: Record<string, unknown> | null;
	total_questions: number;
	total_topics: number;
	syllabus_coverage: number;
	created_at: string;
	updated_at: string;
}

export interface SubjectDetailResponse extends SubjectResponse {
	topics: TopicResponse[];
}

export interface SubjectListResponse {
	subjects: SubjectResponse[];
	pagination: { page: number; limit: number; total: number; total_pages: number };
}

// ── API calls ──

export async function listSubjects(page = 1, limit = 50, search?: string): Promise<SubjectListResponse> {
	const params = new URLSearchParams({ page: String(page), limit: String(limit) });
	if (search) params.set('search', search);
	return apiFetch<SubjectListResponse>(`/subjects?${params}`);
}

export async function getSubject(id: string): Promise<SubjectDetailResponse> {
	return apiFetch<SubjectDetailResponse>(`/subjects/${id}`);
}

export async function createSubject(data: SubjectCreate): Promise<SubjectResponse> {
	return apiFetch<SubjectResponse>('/subjects', {
		method: 'POST',
		body: JSON.stringify(data),
	});
}

export async function deleteSubject(id: string): Promise<void> {
	await apiFetch(`/subjects/${id}`, { method: 'DELETE' });
}

export async function createTopic(
	subjectId: string,
	data: { name: string; description?: string; order_index?: number; subject_id: string; syllabus_content?: string }
): Promise<TopicResponse> {
	return apiFetch<TopicResponse>(`/subjects/${subjectId}/topics`, {
		method: 'POST',
		body: JSON.stringify(data),
	});
}

export async function uploadSyllabus(subjectId: string, topicId: string, file: File): Promise<TopicResponse> {
	const form = new FormData();
	form.append('file', file);
	return apiFetch<TopicResponse>(`/subjects/${subjectId}/topics/${topicId}/upload-syllabus`, {
		method: 'POST',
		body: form,
	});
}

export async function extractChapters(
	subjectId: string,
	file: File
): Promise<{ message: string; chapters_created: number; topics: TopicResponse[] }> {
	const form = new FormData();
	form.append('file', file);
	return apiFetch(`/subjects/${subjectId}/extract-chapters`, {
		method: 'POST',
		body: form,
	});
}

export async function generateLearningOutcomes(subjectId: string): Promise<SubjectResponse> {
	return apiFetch<SubjectResponse>(`/subjects/${subjectId}/generate-learning-outcomes`, {
		method: 'POST',
	});
}
