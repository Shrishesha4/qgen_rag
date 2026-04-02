import { apiFetch } from './client';

// ── Types ────────────────────────────────────────────────────────────────────

export interface CourseModuleResponse {
	id: string;
	course_id: string;
	title: string;
	description: string | null;
	order_index: number;
	module_type: 'content' | 'quiz' | 'assignment';
	content_data: Record<string, unknown> | null;
	duration_minutes: number | null;
	is_preview: boolean;
	created_at: string;
}

export interface CourseResponse {
	id: string;
	teacher_id: string;
	subject_id: string | null;
	title: string;
	slug: string;
	description: string | null;
	cover_image_url: string | null;
	preview_video_url: string | null;
	price_cents: number;
	currency: string;
	status: 'draft' | 'published' | 'archived';
	is_featured: boolean;
	learning_outcomes: Record<string, unknown> | null;
	created_at: string;
	updated_at: string;
	modules: CourseModuleResponse[];
}

export interface CourseSummary {
	id: string;
	teacher_id: string;
	teacher_name: string | null;
	title: string;
	slug: string;
	description: string | null;
	cover_image_url: string | null;
	price_cents: number;
	currency: string;
	status: string;
	is_featured: boolean;
	module_count: number;
	enrolled_count: number;
	created_at: string;
}

export interface CourseListResponse {
	items: CourseSummary[];
	total: number;
	page: number;
	page_size: number;
}

export interface CourseCreateInput {
	title: string;
	description?: string;
	subject_id?: string | null;
	price_cents?: number;
	currency?: string;
	cover_image_url?: string;
	preview_video_url?: string;
	learning_outcomes?: Record<string, unknown>;
}

export interface CourseUpdateInput {
	title?: string;
	description?: string;
	subject_id?: string | null;
	price_cents?: number;
	currency?: string;
	cover_image_url?: string;
	preview_video_url?: string;
	learning_outcomes?: Record<string, unknown>;
	is_featured?: boolean;
}

export interface ModuleCreateInput {
	title: string;
	description?: string;
	module_type?: 'content' | 'quiz' | 'assignment';
	content_data?: Record<string, unknown>;
	duration_minutes?: number;
	is_preview?: boolean;
}

export interface ModuleUpdateInput {
	title?: string;
	description?: string;
	module_type?: string;
	content_data?: Record<string, unknown>;
	duration_minutes?: number;
	is_preview?: boolean;
}

export interface ModuleContentGenerateInput {
	topic_id?: string;
	focus?: string;
}

export interface ModuleQuestionResponse {
	id: string;
	module_id: string;
	question_id: string;
	sequence: number;
	weight: number;
}

// ── Course API ───────────────────────────────────────────────────────────────

export interface CourseListParams {
	subject_id?: string;
	search?: string;
	price_max?: number;
	featured?: boolean;
	teacher_id?: string;
	page?: number;
	page_size?: number;
}

export async function listCourses(params: CourseListParams = {}): Promise<CourseListResponse> {
	const qs = new URLSearchParams();
	if (params.subject_id) qs.set('subject_id', params.subject_id);
	if (params.search) qs.set('search', params.search);
	if (params.price_max !== undefined) qs.set('price_max', String(params.price_max));
	if (params.featured !== undefined) qs.set('featured', String(params.featured));
	if (params.teacher_id) qs.set('teacher_id', params.teacher_id);
	qs.set('page', String(params.page ?? 1));
	qs.set('page_size', String(params.page_size ?? 20));
	return apiFetch<CourseListResponse>(`/courses?${qs}`);
}

export async function listMyCourses(
	status?: string,
	page = 1,
	page_size = 20
): Promise<CourseListResponse> {
	const qs = new URLSearchParams();
	if (status) qs.set('status', status);
	qs.set('page', String(page));
	qs.set('page_size', String(page_size));
	return apiFetch<CourseListResponse>(`/courses/my?${qs}`);
}

export async function getCourseBySlug(slug: string): Promise<CourseResponse> {
	return apiFetch<CourseResponse>(`/courses/${encodeURIComponent(slug)}`);
}

export async function getCourseById(courseId: string): Promise<CourseResponse> {
	return apiFetch<CourseResponse>(`/courses/id/${courseId}`);
}

export async function createCourse(data: CourseCreateInput): Promise<CourseResponse> {
	return apiFetch<CourseResponse>('/courses', {
		method: 'POST',
		body: JSON.stringify(data),
	});
}

export async function updateCourse(courseId: string, data: CourseUpdateInput): Promise<CourseResponse> {
	return apiFetch<CourseResponse>(`/courses/${courseId}`, {
		method: 'PATCH',
		body: JSON.stringify(data),
	});
}

export async function uploadCourseThumbnail(courseId: string, file: File): Promise<CourseResponse> {
	const form = new FormData();
	form.append('file', file);

	return apiFetch<CourseResponse>(`/courses/${courseId}/thumbnail`, {
		method: 'POST',
		body: form,
	});
}

export async function publishCourse(courseId: string): Promise<CourseResponse> {
	return apiFetch<CourseResponse>(`/courses/${courseId}/publish`, {
		method: 'POST',
	});
}

export async function archiveCourse(courseId: string): Promise<void> {
	return apiFetch<void>(`/courses/${courseId}`, {
		method: 'DELETE',
	});
}

// ── Module API ───────────────────────────────────────────────────────────────

export async function createModule(courseId: string, data: ModuleCreateInput): Promise<CourseModuleResponse> {
	return apiFetch<CourseModuleResponse>(`/courses/${courseId}/modules`, {
		method: 'POST',
		body: JSON.stringify(data),
	});
}

export async function updateModule(
	courseId: string,
	moduleId: string,
	data: ModuleUpdateInput
): Promise<CourseModuleResponse> {
	return apiFetch<CourseModuleResponse>(`/courses/${courseId}/modules/${moduleId}`, {
		method: 'PATCH',
		body: JSON.stringify(data),
	});
}

export async function generateModuleContent(
	courseId: string,
	moduleId: string,
	data: ModuleContentGenerateInput
): Promise<CourseModuleResponse> {
	return apiFetch<CourseModuleResponse>(`/courses/${courseId}/modules/${moduleId}/generate-content`, {
		method: 'POST',
		body: JSON.stringify(data),
	});
}

export async function deleteModule(courseId: string, moduleId: string): Promise<void> {
	return apiFetch<void>(`/courses/${courseId}/modules/${moduleId}`, {
		method: 'DELETE',
	});
}

export async function reorderModules(courseId: string, moduleIds: string[]): Promise<void> {
	return apiFetch<void>(`/courses/${courseId}/modules/reorder`, {
		method: 'POST',
		body: JSON.stringify({ module_ids: moduleIds }),
	});
}

// ── Module Questions API ─────────────────────────────────────────────────────

export async function addQuestionsToModule(
	courseId: string,
	moduleId: string,
	questionIds: string[]
): Promise<ModuleQuestionResponse[]> {
	return apiFetch<ModuleQuestionResponse[]>(`/courses/${courseId}/modules/${moduleId}/questions`, {
		method: 'POST',
		body: JSON.stringify({ question_ids: questionIds }),
	});
}

export async function listModuleQuestions(
	courseId: string,
	moduleId: string
): Promise<ModuleQuestionResponse[]> {
	return apiFetch<ModuleQuestionResponse[]>(`/courses/${courseId}/modules/${moduleId}/questions`);
}

export async function removeQuestionFromModule(
	courseId: string,
	moduleId: string,
	questionId: string
): Promise<void> {
	return apiFetch<void>(`/courses/${courseId}/modules/${moduleId}/questions/${questionId}`, {
		method: 'DELETE',
	});
}
