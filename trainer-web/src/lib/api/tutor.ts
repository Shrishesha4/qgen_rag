import { apiFetch } from './client';

// ── Types ────────────────────────────────────────────────────────────────────

export interface WeakTopic {
	topic_id: string;
	topic_name: string;
	avg_score: number;
	fail_count: number;
}

export interface MasteredTopic {
	topic_id: string;
	topic_name: string;
	avg_score: number;
}

export interface LearningProfile {
	weak_topics: WeakTopic[];
	mastered_topics: MasteredTopic[];
	reasoning_gaps: string[];
	total_questions_seen: number;
	overall_level: string;
}

export interface PersonalizedItemResponse {
	id: string;
	student_id: string;
	course_id: string | null;
	topic_id: string | null;
	item_type: 'test' | 'learning_module';
	template_id: string | null;
	generated_content: Record<string, unknown> | null;
	status: string;
	created_at: string;
}

export interface GenerateTestInput {
	course_id?: string;
	topic_focus?: string[];
	question_count?: number;
	difficulty_bias?: 'auto' | 'easy' | 'hard';
}

export interface GenerateModuleInput {
	course_id?: string;
	topic_id: string;
	focus_areas?: string[];
}

// ── API Functions ────────────────────────────────────────────────────────────

export function getLearningProfile(courseId?: string): Promise<LearningProfile> {
	const params = courseId ? `?course_id=${courseId}` : '';
	return apiFetch<LearningProfile>(`/tutor/learning-profile${params}`);
}

export function generateTest(input: GenerateTestInput): Promise<PersonalizedItemResponse> {
	return apiFetch<PersonalizedItemResponse>('/tutor/generate-test', {
		method: 'POST',
		body: JSON.stringify(input),
	});
}

export function generateModule(input: GenerateModuleInput): Promise<PersonalizedItemResponse> {
	return apiFetch<PersonalizedItemResponse>('/tutor/generate-module', {
		method: 'POST',
		body: JSON.stringify(input),
	});
}

export function listPersonalizedItems(params?: {
	item_type?: string;
	course_id?: string;
	limit?: number;
}): Promise<PersonalizedItemResponse[]> {
	const search = new URLSearchParams();
	if (params?.item_type) search.set('item_type', params.item_type);
	if (params?.course_id) search.set('course_id', params.course_id);
	if (params?.limit) search.set('limit', String(params.limit));
	const qs = search.toString();
	return apiFetch<PersonalizedItemResponse[]>(`/tutor/items${qs ? `?${qs}` : ''}`);
}

export function getPersonalizedItem(itemId: string): Promise<PersonalizedItemResponse> {
	return apiFetch<PersonalizedItemResponse>(`/tutor/items/${itemId}`);
}

export function completePersonalizedItem(itemId: string): Promise<PersonalizedItemResponse> {
	return apiFetch<PersonalizedItemResponse>(`/tutor/items/${itemId}/complete`, {
		method: 'PATCH',
	});
}
