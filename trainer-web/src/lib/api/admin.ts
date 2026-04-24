/** Admin Dashboard API calls. */
import { apiFetch, apiUrl, getStoredSession } from './client';

export interface VetterBreakdown {
	user_id: string;
	username: string;
	full_name: string | null;
	email: string;
	total_vetted: number;
	total_approved: number;
	total_rejected: number;
}

export interface UserStats {
	user_id: string;
	username: string;
	full_name: string | null;
	email: string;
	role: string;
	total_generated: number;
	total_vetted: number;
	total_approved: number;
	total_rejected: number;
	total_pending: number;
	subjects_count: number;
	topics_count: number;
}

export interface AdminUserSummary {
	id: string;
	email: string;
	username: string;
	full_name: string | null;
	role: 'teacher' | 'vetter' | 'admin';
	is_active: boolean;
	is_approved: boolean;
	is_superuser: boolean;
	can_manage_groups: boolean;
	can_generate: boolean;
	can_vet: boolean;
	approved_at: string | null;
	created_at: string | null;
	last_login_at: string | null;
}

export interface AdminUserCreateRequest {
	email: string;
	username: string;
	password: string;
	full_name?: string;
	security_question: string;
	security_answer: string;
	role: 'teacher' | 'vetter' | 'admin';
	is_active?: boolean;
	can_manage_groups?: boolean;
	can_generate?: boolean;
	can_vet?: boolean;
}

export interface AdminUserUpdateRequest {
	full_name?: string;
	role?: 'teacher' | 'vetter' | 'admin';
	is_active?: boolean;
	can_manage_groups?: boolean;
	can_generate?: boolean;
	can_vet?: boolean;
}

export interface AdminUserPasswordResetRequest {
	new_password: string;
}

export interface AdminUserDeleteRequest {
	delete_subjects: boolean;
	delete_questions: boolean;
	delete_vetting_data: boolean;
}

export interface AdminUserDeleteResponse {
	message: string;
	deleted_subjects: number;
	deleted_questions: number;
	deleted_vetting_logs: number;
	deleted_vetting_progress: number;
}

export interface AdminBulkApproveUsersResponse {
	approved_users: AdminUserSummary[];
	approved_count: number;
}

export interface AdminNotificationSummary {
	id: string;
	notification_type: string;
	title: string;
	message: string;
	target_user_id: string | null;
	target_user_email: string | null;
	target_username: string | null;
	action_url: string | null;
	action_label: string | null;
	payload: Record<string, unknown> | null;
	is_read: boolean;
	created_at: string | null;
}

export interface AdminNotificationListResponse {
	notifications: AdminNotificationSummary[];
	unread_count: number;
}

export interface AdminDashboard {
	total_subjects: number;
	total_topics: number;
	total_questions: number;
	total_vetted: number;
	total_approved: number;
	total_rejected: number;
	total_pending: number;
	total_users: number;
	total_teachers: number;
	total_vetters: number;
	total_admins: number;
	vetters: VetterBreakdown[];
	users: UserStats[];
}

export interface AdminTopicSummary {
	id: string;
	name: string;
	description: string | null;
	order_index: number;
	has_syllabus: boolean;
	total_questions: number;
	total_approved: number;
	total_rejected: number;
	total_pending: number;
}

export interface AdminSubjectSummary {
	id: string;
	name: string;
	code: string;
	description: string | null;
	teacher_id: string;
	teacher_name: string | null;
	teacher_email: string | null;
	total_topics: number;
	total_questions: number;
	total_approved: number;
	total_rejected: number;
	total_pending: number;
	syllabus_coverage: number;
	created_at: string;
}

export interface AdminSubjectDetail extends AdminSubjectSummary {
	topics: AdminTopicSummary[];
}

export interface AdminQuestionSummary {
	id: string;
	document_id: string | null;
	session_id: string | null;
	question_text: string;
	correct_answer: string | null;
	options: string[] | null;
	question_type: string | null;
	difficulty_level: string | null;
	marks: number | null;
	bloom_taxonomy_level: string | null;
	vetting_status: 'pending' | 'approved' | 'rejected';
	vetted_by: string | null;
	vetted_at: string | null;
	generated_at: string;
	explanation: string | null;
	answerability_score: number | null;
	specificity_score: number | null;
	generation_confidence: number | null;
	novelty_score: number | null;
	max_similarity: number | null;
	similarity_source: string | null;
	generation_attempt_count: number;
	used_reference_materials: boolean;
	generation_status: string;
	discard_reason: string | null;
	replaced_by_id: string | null;
	replaces_id: string | null;
	version_number: number;
	is_latest: boolean;
	is_archived: boolean;
	subject_id: string | null;
	subject_name: string | null;
	topic_id: string | null;
	topic_name: string | null;
	learning_outcome_id: string | null;
	vetting_notes: string | null;
	provider_key: string;
}

export interface AdminQuestionFeedResponse {
	questions: AdminQuestionSummary[];
	total_count: number;
	next_cursor: string | null;
	has_more: boolean;
}

export interface AdminQuestionExportField {
	key: string;
	label: string;
	group: string;
	description: string;
	selected_by_default: boolean;
}

export interface AdminQuestionExportColumn {
	key: string;
	label: string;
}

export interface AdminQuestionExportPreviewResponse {
	available_fields: AdminQuestionExportField[];
	selected_fields: AdminQuestionExportColumn[];
	preview_count: number;
	rows: Record<string, string>[];
}

export interface AdminQuestionFeedParams {
	subject_id?: string;
	subject_scope?: 'all' | 'assigned' | 'orphaned';
	topic_id?: string;
	vetting_status?: 'pending' | 'approved' | 'rejected' | 'all';
	question_type?: 'mcq' | 'short_answer' | 'long_answer' | 'essay' | 'true_false' | 'unspecified' | 'all';
	difficulty_level?: 'easy' | 'medium' | 'hard' | 'unspecified' | 'all';
	bloom_taxonomy_level?: 'remember' | 'understand' | 'apply' | 'analyze' | 'evaluate' | 'create' | 'unspecified' | 'all';
	generation_status?: 'accepted' | 'discarded' | 'all';
	reference_mode?: 'with_reference' | 'without_reference' | 'all';
	provider_key?: string;
	version_scope?: 'latest' | 'all';
	archived_state?: 'active' | 'archived' | 'all';
	cursor?: string;
	limit?: number;
}

function buildAdminQuestionSearchParams(
	params: AdminQuestionFeedParams = {},
	fields: string[] = []
): URLSearchParams {
	const searchParams = new URLSearchParams();
	if (params.subject_id) searchParams.set('subject_id', params.subject_id);
	if (params.subject_scope) searchParams.set('subject_scope', params.subject_scope);
	if (params.topic_id) searchParams.set('topic_id', params.topic_id);
	if (params.vetting_status) searchParams.set('vetting_status', params.vetting_status);
	if (params.question_type) searchParams.set('question_type', params.question_type);
	if (params.difficulty_level) searchParams.set('difficulty_level', params.difficulty_level);
	if (params.bloom_taxonomy_level) searchParams.set('bloom_taxonomy_level', params.bloom_taxonomy_level);
	if (params.generation_status) searchParams.set('generation_status', params.generation_status);
	if (params.reference_mode) searchParams.set('reference_mode', params.reference_mode);
	if (params.provider_key) searchParams.set('provider_key', params.provider_key);
	if (params.version_scope) searchParams.set('version_scope', params.version_scope);
	if (params.archived_state) searchParams.set('archived_state', params.archived_state);
	if (params.cursor) searchParams.set('cursor', params.cursor);
	if (params.limit) searchParams.set('limit', String(params.limit));
	for (const field of fields) {
		if (field) searchParams.append('field', field);
	}
	return searchParams;
}

async function parseAdminRawError(res: Response): Promise<Error> {
	const fallback = `Request failed (${res.status})`;
	try {
		const payload = await res.json();
		if (typeof payload?.detail === 'string' && payload.detail.trim()) {
			return new Error(payload.detail);
		}
		if (typeof payload?.message === 'string' && payload.message.trim()) {
			return new Error(payload.message);
		}
		return new Error(fallback);
	} catch {
		return new Error(fallback);
	}
}

function parseDownloadFilename(contentDisposition: string | null, fallback: string): string {
	if (!contentDisposition) return fallback;
	const encoded = contentDisposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
	if (encoded) {
		try {
			return decodeURIComponent(encoded);
		} catch {
			return fallback;
		}
	}
	const plain = contentDisposition.match(/filename="?([^";]+)"?/i)?.[1];
	return plain || fallback;
}

export async function getAdminDashboard(): Promise<AdminDashboard> {
	return apiFetch<AdminDashboard>('/admin/dashboard');
}

export async function listAdminSubjects(): Promise<AdminSubjectSummary[]> {
	return apiFetch<AdminSubjectSummary[]>('/admin/subjects');
}

export async function getAdminSubject(subjectId: string): Promise<AdminSubjectDetail> {
	return apiFetch<AdminSubjectDetail>(`/admin/subjects/${subjectId}`);
}

export async function listAdminQuestions(
	params: AdminQuestionFeedParams = {}
): Promise<AdminQuestionFeedResponse> {
	const searchParams = buildAdminQuestionSearchParams(params);
	const suffix = searchParams.toString() ? `?${searchParams.toString()}` : '';
	return apiFetch<AdminQuestionFeedResponse>(`/admin/questions${suffix}`);
}

export async function listAdminQuestionProviders(): Promise<string[]> {
	return apiFetch<string[]>('/admin/questions/providers');
}

export async function previewAdminQuestionExport(
	params: AdminQuestionFeedParams = {},
	fields: string[] = []
): Promise<AdminQuestionExportPreviewResponse> {
	const searchParams = buildAdminQuestionSearchParams(params, fields);
	const suffix = searchParams.toString() ? `?${searchParams.toString()}` : '';
	return apiFetch<AdminQuestionExportPreviewResponse>(`/admin/questions/export/preview${suffix}`);
}

export async function downloadAdminQuestionExport(
	params: AdminQuestionFeedParams = {},
	fields: string[] = []
): Promise<{ blob: Blob; filename: string }> {
	const searchParams = buildAdminQuestionSearchParams(params, fields);
	const suffix = searchParams.toString() ? `?${searchParams.toString()}` : '';
	const session = getStoredSession();
	const res = await fetch(apiUrl(`/admin/questions/export${suffix}`), {
		headers: session?.access_token ? { Authorization: `Bearer ${session.access_token}` } : {}
	});
	if (!res.ok) throw await parseAdminRawError(res);
	return {
		blob: await res.blob(),
		filename: parseDownloadFilename(
			res.headers.get('content-disposition'),
			'admin_questions_export.csv'
		)
	};
}

export async function listAdminUsers(): Promise<AdminUserSummary[]> {
	return apiFetch<AdminUserSummary[]>('/admin/users');
}

export async function createAdminUser(payload: AdminUserCreateRequest): Promise<AdminUserSummary> {
	return apiFetch<AdminUserSummary>('/admin/users', {
		method: 'POST',
		body: JSON.stringify(payload)
	});
}

export async function updateAdminUser(
	userId: string,
	payload: AdminUserUpdateRequest
): Promise<AdminUserSummary> {
	return apiFetch<AdminUserSummary>(`/admin/users/${userId}`, {
		method: 'PATCH',
		body: JSON.stringify(payload)
	});
}

export async function resetAdminUserPassword(
	userId: string,
	payload: AdminUserPasswordResetRequest
): Promise<{ message: string }> {
	return apiFetch<{ message: string }>(`/admin/users/${userId}/reset-password`, {
		method: 'POST',
		body: JSON.stringify(payload)
	});
}

export async function deleteAdminUser(
	userId: string,
	payload: AdminUserDeleteRequest
): Promise<AdminUserDeleteResponse> {
	return apiFetch<AdminUserDeleteResponse>(`/admin/users/${userId}`, {
		method: 'DELETE',
		body: JSON.stringify(payload)
	});
}

export async function approveAdminUser(userId: string): Promise<AdminUserSummary> {
	return apiFetch<AdminUserSummary>(`/admin/users/${userId}/approve`, {
		method: 'POST'
	});
}

export async function bulkApproveAdminUsers(userIds: string[]): Promise<AdminBulkApproveUsersResponse> {
	return apiFetch<AdminBulkApproveUsersResponse>('/admin/users/approve-bulk', {
		method: 'POST',
		body: JSON.stringify({ user_ids: userIds })
	});
}

export async function listAdminNotifications(
	options: { unreadOnly?: boolean; limit?: number } = {}
): Promise<AdminNotificationListResponse> {
	const params = new URLSearchParams();
	if (options.unreadOnly) params.set('unread_only', 'true');
	if (options.limit) params.set('limit', String(options.limit));
	const suffix = params.toString() ? `?${params.toString()}` : '';
	return apiFetch<AdminNotificationListResponse>(`/admin/notifications${suffix}`);
}

export async function markAdminNotificationRead(notificationId: string): Promise<AdminNotificationSummary> {
	return apiFetch<AdminNotificationSummary>(`/admin/notifications/${notificationId}/read`, {
		method: 'POST'
	});
}

export async function markAllAdminNotificationsRead(): Promise<{ message: string }> {
	return apiFetch<{ message: string }>('/admin/notifications/read-all', {
		method: 'POST'
	});
}
