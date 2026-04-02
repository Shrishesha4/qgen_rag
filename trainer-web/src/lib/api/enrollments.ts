import { apiFetch } from './client';
import type { CourseResponse } from './courses';

// ── Types ────────────────────────────────────────────────────────────────────

export interface EnrollmentResponse {
	id: string;
	student_id: string;
	course_id: string;
	status: 'active' | 'completed' | 'refunded';
	progress_data: {
		completed_module_ids: string[];
		quiz_scores: Record<string, number>;
	} | null;
	enrolled_at: string;
	completed_at: string | null;
	course: CourseResponse | null;
}

export interface EnrollmentListResponse {
	items: EnrollmentResponse[];
	total: number;
}

export interface EnrollmentCreateInput {
	payment_provider?: 'mock' | 'razorpay';
	mock?: boolean;
}

export interface ProgressUpdateInput {
	completed_module_ids?: string[];
	quiz_scores?: Record<string, number>;
}

// ── Enrollment API ───────────────────────────────────────────────────────────

export async function enrollInCourse(
	courseId: string,
	data: EnrollmentCreateInput = { payment_provider: 'mock', mock: true }
): Promise<EnrollmentResponse> {
	return apiFetch<EnrollmentResponse>(`/enrollments/courses/${courseId}/enroll`, {
		method: 'POST',
		body: JSON.stringify(data),
	});
}

export async function listEnrollments(
	status?: string,
	page = 1,
	page_size = 20
): Promise<EnrollmentListResponse> {
	const qs = new URLSearchParams();
	if (status) qs.set('status', status);
	qs.set('page', String(page));
	qs.set('page_size', String(page_size));
	return apiFetch<EnrollmentListResponse>(`/enrollments?${qs}`);
}

export async function getEnrollment(enrollmentId: string): Promise<EnrollmentResponse> {
	return apiFetch<EnrollmentResponse>(`/enrollments/${enrollmentId}`);
}

export async function updateProgress(
	enrollmentId: string,
	data: ProgressUpdateInput
): Promise<EnrollmentResponse> {
	return apiFetch<EnrollmentResponse>(`/enrollments/${enrollmentId}/progress`, {
		method: 'PATCH',
		body: JSON.stringify(data),
	});
}
