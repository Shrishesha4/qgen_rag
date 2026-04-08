import { apiFetch } from './client';

export interface FavoriteSummary {
	entity_type: 'subject' | 'group' | string;
	entity_id: string;
	created_at: string | null;
}

export interface FavoritesResponse {
	favorites: FavoriteSummary[];
}

export interface FavoriteToggleRequest {
	entity_type: 'subject' | 'group';
	entity_id: string;
	entity_name?: string;
	source_area?: string;
}

export interface ActivityEventRequest {
	action_key: string;
	action_label: string;
	category: string;
	source_area?: string;
	entity_type?: string;
	entity_id?: string;
	entity_name?: string;
	subject_id?: string;
	subject_name?: string;
	topic_id?: string;
	topic_name?: string;
	group_id?: string;
	group_name?: string;
	details?: Record<string, unknown>;
}

export interface ActivityLogSummary {
	id: string;
	actor_user_id: string | null;
	actor_role: string | null;
	actor_name: string | null;
	actor_email: string | null;
	action_key: string;
	action_label: string;
	category: string | null;
	source_area: string | null;
	entity_type: string | null;
	entity_id: string | null;
	entity_name: string | null;
	subject_id: string | null;
	subject_name: string | null;
	topic_id: string | null;
	topic_name: string | null;
	group_id: string | null;
	group_name: string | null;
	endpoint: string | null;
	http_method: string | null;
	ip_address: string | null;
	success: boolean;
	error_message: string | null;
	details: Record<string, unknown> | null;
	created_at: string | null;
}

export interface ActivityLogListResponse {
	items: ActivityLogSummary[];
	pagination: {
		page: number;
		limit: number;
		total: number;
		total_pages: number;
	};
}

export interface ActivityFilterOption {
	key: string;
	label: string;
}

export interface ActivityLogFilterOptionsResponse {
	actions: ActivityFilterOption[];
	source_areas: string[];
	actor_roles: string[];
	entity_types: string[];
	categories: string[];
}

export async function listCurrentUserFavorites(): Promise<FavoriteSummary[]> {
	const response = await apiFetch<FavoritesResponse>('/activity/favorites');
	return response.favorites;
}

export async function addCurrentUserFavorite(payload: FavoriteToggleRequest): Promise<FavoriteSummary> {
	return apiFetch<FavoriteSummary>('/activity/favorites', {
		method: 'PUT',
		body: JSON.stringify(payload),
	});
}

export async function removeCurrentUserFavorite(payload: FavoriteToggleRequest): Promise<void> {
	await apiFetch('/activity/favorites', {
		method: 'DELETE',
		body: JSON.stringify(payload),
	});
}

export async function recordActivityEvent(payload: ActivityEventRequest): Promise<void> {
	await apiFetch('/activity/events', {
		method: 'POST',
		body: JSON.stringify(payload),
	});
}

export async function getActivityLogFilterOptions(): Promise<ActivityLogFilterOptionsResponse> {
	return apiFetch<ActivityLogFilterOptionsResponse>('/activity/logs/options');
}

export async function listActivityLogs(options: {
	page?: number;
	limit?: number;
	q?: string;
	action_key?: string;
	actor_role?: string;
	source_area?: string;
	entity_type?: string;
	category?: string;
	success?: boolean | null;
} = {}): Promise<ActivityLogListResponse> {
	const params = new URLSearchParams();
	if (options.page) params.set('page', String(options.page));
	if (options.limit) params.set('limit', String(options.limit));
	if (options.q) params.set('q', options.q);
	if (options.action_key) params.set('action_key', options.action_key);
	if (options.actor_role) params.set('actor_role', options.actor_role);
	if (options.source_area) params.set('source_area', options.source_area);
	if (options.entity_type) params.set('entity_type', options.entity_type);
	if (options.category) params.set('category', options.category);
	if (typeof options.success === 'boolean') params.set('success', String(options.success));
	const suffix = params.toString() ? `?${params.toString()}` : '';
	return apiFetch<ActivityLogListResponse>(`/activity/logs${suffix}`);
}