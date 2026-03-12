/** Auth API calls — matches backend UserCreate / UserLogin schemas. */
import { apiFetch, storeSession, clearSession, apiUrl, type StoredSession } from './client';

export interface LoginRequest {
	email: string;
	password: string;
}

export interface RegisterRequest {
	email: string;
	username: string;
	full_name?: string;
	password: string;
	role: 'teacher' | 'vetter';
}

export interface TokenResponse {
	access_token: string;
	refresh_token: string;
	token_type: string;
	expires_in: number;
	user: {
		id: string;
		email: string;
		username: string;
		full_name: string | null;
		role: string;
		avatar_url: string | null;
		is_active: boolean;
		created_at: string;
		last_login_at: string | null;
	};
}

export async function login(credentials: LoginRequest): Promise<TokenResponse> {
	const res = await fetch(apiUrl('/auth/login'), {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(credentials)
	});
	if (!res.ok) {
		const body = await res.json().catch(() => null);
		throw new Error(body?.detail || `Login failed (${res.status})`);
	}
	const data: TokenResponse = await res.json();
	storeSession({
		access_token: data.access_token,
		refresh_token: data.refresh_token,
		user: {
			id: data.user.id,
			email: data.user.email,
			username: data.user.username,
			full_name: data.user.full_name,
			role: data.user.role,
			avatar_url: data.user.avatar_url
		}
	});
	return data;
}

export async function register(data: RegisterRequest): Promise<TokenResponse> {
	const res = await fetch(apiUrl('/auth/register'), {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(data)
	});
	if (!res.ok) {
		const body = await res.json().catch(() => null);
		throw new Error(body?.detail || `Registration failed (${res.status})`);
	}
	const tokenRes: TokenResponse = await res.json();
	storeSession({
		access_token: tokenRes.access_token,
		refresh_token: tokenRes.refresh_token,
		user: {
			id: tokenRes.user.id,
			email: tokenRes.user.email,
			username: tokenRes.user.username,
			full_name: tokenRes.user.full_name,
			role: tokenRes.user.role,
			avatar_url: tokenRes.user.avatar_url
		}
	});
	return tokenRes;
}

export async function logout(): Promise<void> {
	const raw = localStorage.getItem('qgen-trainer-session');
	if (raw) {
		try {
			const session: StoredSession = JSON.parse(raw);
			await fetch(apiUrl('/auth/logout'), {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
					Authorization: `Bearer ${session.access_token}`
				},
				body: JSON.stringify({ refresh_token: session.refresh_token })
			}).catch(() => {});
		} catch {
			// best effort
		}
	}
	clearSession();
}

export async function getCurrentUser() {
	return apiFetch<TokenResponse['user']>('/auth/me');
}
