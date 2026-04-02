/** Admin Dashboard API calls. */
import { apiFetch } from './client';

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
	is_superuser: boolean;
	can_manage_groups: boolean;
	can_generate: boolean;
	can_vet: boolean;
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

export async function getAdminDashboard(): Promise<AdminDashboard> {
	return apiFetch<AdminDashboard>('/admin/dashboard');
}

export async function listAdminSubjects(): Promise<AdminSubjectSummary[]> {
	return apiFetch<AdminSubjectSummary[]>('/admin/subjects');
}

export async function getAdminSubject(subjectId: string): Promise<AdminSubjectDetail> {
	return apiFetch<AdminSubjectDetail>(`/admin/subjects/${subjectId}`);
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
