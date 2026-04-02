import { apiUrl, apiFetch, getStoredSession } from './client';

// ── Types ────────────────────────────────────────────────────────────────────

export interface InquirySessionState {
	id: string;
	user_id: string;
	subject_id: string;
	topic_id: string | null;
	current_level: 'beginner' | 'advanced' | 'pro';
	completed_turns_by_level: Record<string, number>;
	messages: Array<{ role: 'user' | 'assistant'; content: string }>;
	current_phase: 'awaiting-answer' | 'awaiting-reasoning';
	current_question_attempt: number;
	is_active: boolean;
	is_complete: boolean;
	created_at: string;
	updated_at: string;
}

export interface TutorPreferences {
	preferred_tutor_provider: string | null;
	available_providers: Array<{ key: string; name: string; model: string }>;
}

export interface InquirySessionUpdate {
	current_level?: string;
	completed_turns_by_level?: Record<string, number>;
	messages?: Array<{ role: string; content: string }>;
	current_phase?: string;
	current_question_attempt?: number;
	is_complete?: boolean;
}

// ── Session API ───────────────────────────────────────────────────────────────

export async function createInquirySession(
	subjectId: string,
	topicId: string | null
): Promise<InquirySessionState> {
	return apiFetch<InquirySessionState>('/gel/inquiry-sessions', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ subject_id: subjectId, topic_id: topicId }),
	});
}

export async function getActiveInquirySession(
	subjectId: string,
	topicId: string | null
): Promise<InquirySessionState | null> {
	const params = new URLSearchParams({ subject_id: subjectId });
	if (topicId) params.set('topic_id', topicId);
	try {
		return await apiFetch<InquirySessionState>(`/gel/inquiry-sessions/active?${params}`);
	} catch {
		return null;
	}
}

export async function updateInquirySession(
	sessionId: string,
	update: InquirySessionUpdate
): Promise<InquirySessionState> {
	return apiFetch<InquirySessionState>(`/gel/inquiry-sessions/${sessionId}`, {
		method: 'PATCH',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(update),
	});
}

// ── Preferences API ───────────────────────────────────────────────────────────

export async function getTutorPreferences(): Promise<TutorPreferences> {
	return apiFetch<TutorPreferences>('/gel/student/preferences');
}

export async function updateTutorPreferences(
	preferredProvider: string | null
): Promise<TutorPreferences> {
	return apiFetch<TutorPreferences>('/gel/student/preferences', {
		method: 'PATCH',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ preferred_tutor_provider: preferredProvider }),
	});
}
