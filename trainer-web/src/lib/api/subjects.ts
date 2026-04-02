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

export interface SubjectUpdate {
	name?: string;
	code?: string;
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
	user_id: string | null;
	creator_username: string | null;
	name: string;
	code: string;
	description: string | null;
	learning_outcomes: Record<string, unknown> | null;
	course_outcomes: Record<string, unknown> | null;
	total_questions: number;
	total_topics: number;
	total_pending?: number;
	total_approved?: number;
	total_rejected?: number;
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

export async function updateSubject(id: string, data: SubjectUpdate): Promise<SubjectResponse> {
	return apiFetch<SubjectResponse>(`/subjects/${id}`, {
		method: 'PUT',
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

export async function updateTopic(
	subjectId: string,
	topicId: string,
	data: { name?: string; description?: string; syllabus_content?: string; has_syllabus?: boolean }
): Promise<TopicResponse> {
	return apiFetch<TopicResponse>(`/subjects/${subjectId}/topics/${topicId}`, {
		method: 'PUT',
		body: JSON.stringify(data),
	});
}

export async function deleteTopic(subjectId: string, topicId: string): Promise<void> {
	await apiFetch(`/subjects/${subjectId}/topics/${topicId}`, { method: 'DELETE' });
}

export async function generateLearningOutcomes(subjectId: string): Promise<SubjectResponse> {
	return apiFetch<SubjectResponse>(`/subjects/${subjectId}/generate-learning-outcomes`, {
		method: 'POST',
	});
}

// ── Subject Groups ──

export interface SubjectGroupCreate {
	name: string;
	parent_id?: string | null;
}

export interface SubjectGroupUpdate {
	name?: string;
	parent_id?: string | null;
	order_index?: number;
}

export interface SubjectGroupResponse {
	id: string;
	name: string;
	parent_id: string | null;
	order_index: number;
	created_at: string;
	updated_at: string;
	total_subjects: number;
	total_questions: number;
	total_pending: number;
	total_approved: number;
	total_rejected: number;
}

export interface SubjectGroupTreeNode extends SubjectGroupResponse {
	children: SubjectGroupTreeNode[];
	subjects: SubjectResponse[];
}

export interface SubjectTreeResponse {
	groups: SubjectGroupTreeNode[];
	ungrouped_subjects: SubjectResponse[];
	totals: {
		total_groups: number;
		total_subjects: number;
		total_questions: number;
		total_pending: number;
		total_approved: number;
		total_rejected: number;
	};
}

export async function listGroups(): Promise<SubjectGroupResponse[]> {
	return apiFetch<SubjectGroupResponse[]>('/subjects/groups');
}

export async function getGroup(id: string): Promise<SubjectGroupResponse> {
	return apiFetch<SubjectGroupResponse>(`/subjects/groups/${id}`);
}

export async function createGroup(data: SubjectGroupCreate): Promise<SubjectGroupResponse> {
	return apiFetch<SubjectGroupResponse>('/subjects/groups', {
		method: 'POST',
		body: JSON.stringify(data),
	});
}

export async function updateGroup(id: string, data: SubjectGroupUpdate): Promise<SubjectGroupResponse> {
	return apiFetch<SubjectGroupResponse>(`/subjects/groups/${id}`, {
		method: 'PUT',
		body: JSON.stringify(data),
	});
}

export async function deleteGroup(id: string, moveSubjectsToRoot = true): Promise<void> {
	const params = new URLSearchParams({ move_subjects_to_root: String(moveSubjectsToRoot) });
	await apiFetch(`/subjects/groups/${id}?${params}`, { method: 'DELETE' });
}

export async function moveGroup(groupId: string, newParentId: string | null): Promise<SubjectGroupResponse> {
	const params = new URLSearchParams();
	if (newParentId) params.set('new_parent_id', newParentId);
	return apiFetch<SubjectGroupResponse>(`/subjects/groups/${groupId}/move?${params}`, {
		method: 'POST',
	});
}

export async function moveSubject(subjectId: string, groupId: string | null): Promise<SubjectResponse> {
	const params = new URLSearchParams();
	if (groupId) params.set('group_id', groupId);
	return apiFetch<SubjectResponse>(`/subjects/${subjectId}/move?${params}`, {
		method: 'PUT',
	});
}

export async function getSubjectsTree(): Promise<SubjectTreeResponse> {
	return apiFetch<SubjectTreeResponse>('/subjects/tree');
}
