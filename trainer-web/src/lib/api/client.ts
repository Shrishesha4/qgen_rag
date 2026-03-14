/** API base URL — configured for local dev, override via env. */
const API_BASE_FALLBACK = 'http://localhost:8000/api/v1';

function normalizeApiBase(url: string): string {
	return url.replace(/\/+$/, '');
}

export const API_BASE = normalizeApiBase(import.meta.env.VITE_API_BASE || API_BASE_FALLBACK);

/** Build a full API URL. */
export function apiUrl(path: string): string {
	return `${API_BASE}${path.startsWith('/') ? path : '/' + path}`;
}

/** Typed fetch wrapper with auth header injection. */
export async function apiFetch<T>(
	path: string,
	options: RequestInit = {}
): Promise<T> {
	const session = getStoredSession();
	const headers = new Headers(options.headers);

	if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
		headers.set('Content-Type', 'application/json');
	}
	if (session?.access_token) {
		headers.set('Authorization', `Bearer ${session.access_token}`);
	}

	const res = await fetch(apiUrl(path), { ...options, headers });

	if (res.status === 401 && session?.refresh_token) {
		const refreshed = await refreshToken(session.refresh_token);
		if (refreshed) {
			headers.set('Authorization', `Bearer ${refreshed.access_token}`);
			const retry = await fetch(apiUrl(path), { ...options, headers });
			if (!retry.ok) throw await parseError(retry);
			return retry.json() as Promise<T>;
		}
	}

	if (!res.ok) throw await parseError(res);
	return res.json() as Promise<T>;
}

// ── Auth helpers ──

export interface StoredSession {
	access_token: string;
	refresh_token: string;
	user: {
		id: string;
		email: string;
		username: string;
		full_name: string | null;
		role: string;
		avatar_url: string | null;
	};
}

const SESSION_KEY = 'qgen-trainer-session';

export function getStoredSession(): StoredSession | null {
	if (typeof window === 'undefined') return null;
	const raw = localStorage.getItem(SESSION_KEY);
	if (!raw) return null;
	try {
		return JSON.parse(raw);
	} catch {
		return null;
	}
}

export function storeSession(session: StoredSession) {
	localStorage.setItem(SESSION_KEY, JSON.stringify(session));
}

export function clearSession() {
	localStorage.removeItem(SESSION_KEY);
}

async function refreshToken(
	token: string
): Promise<{ access_token: string; refresh_token: string } | null> {
	try {
		const res = await fetch(apiUrl('/auth/refresh'), {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ refresh_token: token })
		});
		if (!res.ok) return null;
		const data = await res.json();
		// update stored session with new tokens
		const session = getStoredSession();
		if (session) {
			session.access_token = data.access_token;
			session.refresh_token = data.refresh_token;
			storeSession(session);
		}
		return data;
	} catch {
		return null;
	}
}

async function parseError(res: Response): Promise<Error> {
	try {
		const body = await res.json();
		const message = extractApiErrorMessage(body);
		return new Error(message || `Request failed (${res.status})`);
	} catch {
		return new Error(`Request failed (${res.status})`);
	}
}

function extractApiErrorMessage(payload: unknown): string {
	if (typeof payload === 'string') return payload;
	if (payload && typeof payload === 'object') {
		const record = payload as Record<string, unknown>;
		const detail = record.detail;
		const message = record.message;

		if (typeof detail === 'string' && detail.trim()) return detail;
		if (typeof message === 'string' && message.trim()) return message;

		if (Array.isArray(detail)) {
			const msgs = detail
				.map((item) => {
					if (typeof item === 'string') return item;
					if (item && typeof item === 'object') {
						const err = item as Record<string, unknown>;
						const loc = Array.isArray(err.loc) ? err.loc.join('.') : '';
						const msg = typeof err.msg === 'string' ? err.msg : '';
						if (loc && msg) return `${loc}: ${msg}`;
						if (msg) return msg;
					}
					return '';
				})
				.filter((v) => v.length > 0);
			if (msgs.length > 0) return msgs.join('; ');
		}

		if (detail && typeof detail === 'object') {
			try {
				return JSON.stringify(detail);
			} catch {
				return String(detail);
			}
		}
	}

	return '';
}
