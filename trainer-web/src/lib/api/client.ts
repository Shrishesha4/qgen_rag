/** API base URL — must be provided via environment. */

function normalizeApiBase(url: string): string {
	return url.replace(/\/+$/, '');
}

const apiBaseFromEnv = import.meta.env.VITE_API_BASE;

if (!apiBaseFromEnv) {
	throw new Error('VITE_API_BASE is not configured. Set it in the trainer-web environment file.');
}

export const API_BASE = normalizeApiBase(apiBaseFromEnv);

/** Build a full API URL. */
export function apiUrl(path: string): string {
	return `${API_BASE}${path.startsWith('/') ? path : '/' + path}`;
}

/** Safely parse JSON, returning undefined for empty bodies (e.g. 204 No Content). */
async function safeJson<T>(res: Response): Promise<T> {
	const contentLength = res.headers.get('content-length');
	if (res.status === 204 || contentLength === '0') return undefined as unknown as T;
	const text = await res.text();
	if (!text || !text.trim()) return undefined as unknown as T;
	return JSON.parse(text) as T;
}

/** Typed fetch wrapper with auth header injection. */
export async function apiFetch<T>(
	path: string,
	options: RequestInit = {}
): Promise<T> {
	const session = getStoredSession();
	const headers = new Headers(options.headers);

	if (options.body != null && !headers.has('Content-Type') && !(options.body instanceof FormData)) {
		headers.set('Content-Type', 'application/json');
	}
	if (session?.access_token) {
		headers.set('Authorization', `Bearer ${session.access_token}`);
	}

	const res = await fetch(apiUrl(path), { ...options, headers });

	if (res.status === 401 && session?.refresh_token) {
		const refreshed = await refreshTokenWithDelay(session.refresh_token, 2000);
		if (refreshed) {
			headers.set('Authorization', `Bearer ${refreshed.access_token}`);
			const retry = await fetch(apiUrl(path), { ...options, headers });
			if (!retry.ok) throw await parseError(retry);
			return safeJson<T>(retry);
		}
	}

	if (!res.ok) throw await parseError(res);
	return safeJson<T>(res);
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
		security_question?: string | null;
		role: string;
		avatar_url: string | null;
		can_manage_groups?: boolean;
		can_generate?: boolean;
		can_vet?: boolean;
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

let activeRefreshPromise: Promise<{ access_token: string; refresh_token: string } | null> | null = null;

function sleep(ms: number): Promise<void> {
	return new Promise((resolve) => setTimeout(resolve, ms));
}

async function refreshTokenWithDelay(
	token: string,
	delayMs: number
): Promise<{ access_token: string; refresh_token: string } | null> {
	if (!activeRefreshPromise) {
		activeRefreshPromise = (async () => {
			if (delayMs > 0) {
				await sleep(delayMs);
			}
			return refreshToken(token);
		})();
	}

	try {
		return await activeRefreshPromise;
	} finally {
		activeRefreshPromise = null;
	}
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
