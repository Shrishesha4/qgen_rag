/** Auth API calls — matches backend UserCreate / UserLogin schemas. */
import {
	apiFetch,
	storeSession,
	clearSession,
	apiUrl,
	getStoredSession,
	type StoredSession
} from './client';

export interface LoginRequest {
	email: string;
	password: string;
}

export type PasswordResetMethod = 'smtp' | 'security_question';
export const DEFAULT_SECURITY_QUESTION = 'What is your security reset word?';

export interface RegisterRequest {
	email: string;
	username: string;
	full_name?: string;
	password: string;
	security_question: string;
	security_answer: string;
	role: 'teacher' | 'vetter' | 'admin';
}

export interface AuthenticatedUser {
	id: string;
	email: string;
	username: string;
	full_name: string | null;
	security_question: string | null;
	role: string;
	avatar_url: string | null;
	can_manage_groups: boolean;
	can_generate: boolean;
	can_vet: boolean;
	is_active: boolean;
	is_approved: boolean;
	approved_at: string | null;
	created_at: string;
	last_login_at: string | null;
}

export interface TokenResponse {
	access_token: string;
	refresh_token: string;
	token_type: string;
	expires_in: number;
	user: AuthenticatedUser;
}

export interface UpdateProfileRequest {
	username?: string;
	full_name?: string;
	security_question?: string;
	security_answer?: string;
}

export interface ChangePasswordRequest {
	current_password: string;
	new_password: string;
}

export interface ForgotPasswordRequest {
	email: string;
}

export interface ResetPasswordRequest {
	token: string;
	new_password: string;
}

export interface PasswordResetMethodResponse {
	method: PasswordResetMethod;
	self_service_enabled: boolean;
}

export interface SecurityQuestionLookupRequest {
	email: string;
}

export interface SecurityQuestionResponse {
	security_question: string;
}

export interface SecurityQuestionPasswordResetRequest {
	email: string;
	security_answer: string;
	new_password: string;
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
			security_question: data.user.security_question,
			role: data.user.role,
			avatar_url: data.user.avatar_url,
			can_manage_groups: data.user.can_manage_groups,
			can_generate: data.user.can_generate,
			can_vet: data.user.can_vet
		}
	});
	return data;
}

export async function register(data: RegisterRequest): Promise<{ message: string }> {
	const res = await fetch(apiUrl('/auth/register'), {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(data)
	});
	if (!res.ok) {
		const body = await res.json().catch(() => null);
		throw new Error(body?.detail || `Registration failed (${res.status})`);
	}
	return res.json();
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
	return apiFetch<AuthenticatedUser>('/auth/me');
}

export async function updateProfile(payload: UpdateProfileRequest): Promise<AuthenticatedUser> {
	const updatedUser = await apiFetch<AuthenticatedUser>('/auth/update-profile', {
		method: 'PUT',
		body: JSON.stringify(payload)
	});

	const existing = getStoredSession();
	if (existing) {
		storeSession({
			...existing,
			user: {
				...existing.user,
				email: updatedUser.email,
				username: updatedUser.username,
				full_name: updatedUser.full_name,
				security_question: updatedUser.security_question,
				role: updatedUser.role,
				avatar_url: updatedUser.avatar_url,
				can_manage_groups: updatedUser.can_manage_groups,
				can_generate: updatedUser.can_generate,
				can_vet: updatedUser.can_vet
			}
		});
	}

	return updatedUser;
}

export async function changePassword(payload: ChangePasswordRequest): Promise<{ message: string }> {
	return apiFetch<{ message: string }>('/auth/change-password', {
		method: 'POST',
		body: JSON.stringify(payload)
	});
}

export async function requestPasswordReset(payload: ForgotPasswordRequest): Promise<{ message: string }> {
	const res = await fetch(apiUrl('/auth/forgot-password'), {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(payload)
	});
	if (!res.ok) {
		const body = await res.json().catch(() => null);
		throw new Error(body?.detail || `Password reset request failed (${res.status})`);
	}
	return res.json();
}

export async function resetPassword(payload: ResetPasswordRequest): Promise<{ message: string }> {
	const res = await fetch(apiUrl('/auth/reset-password'), {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(payload)
	});
	if (!res.ok) {
		const body = await res.json().catch(() => null);
		throw new Error(body?.detail || `Password reset failed (${res.status})`);
	}
	return res.json();
}

export async function getPasswordResetMethod(): Promise<PasswordResetMethodResponse> {
	const res = await fetch(apiUrl('/settings/password-reset'));
	if (!res.ok) {
		const body = await res.json().catch(() => null);
		throw new Error(body?.detail || `Failed to load password reset method (${res.status})`);
	}
	return res.json();
}

export async function getSecurityQuestion(
	payload: SecurityQuestionLookupRequest
): Promise<SecurityQuestionResponse> {
	const res = await fetch(apiUrl('/auth/security-question'), {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(payload)
	});
	if (!res.ok) {
		const body = await res.json().catch(() => null);
		throw new Error(body?.detail || `Unable to load security question (${res.status})`);
	}
	return res.json();
}

export async function resetPasswordWithSecurityQuestion(
	payload: SecurityQuestionPasswordResetRequest
): Promise<{ message: string }> {
	const res = await fetch(apiUrl('/auth/security-question/reset-password'), {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(payload)
	});
	if (!res.ok) {
		const body = await res.json().catch(() => null);
		throw new Error(body?.detail || `Password reset failed (${res.status})`);
	}
	return res.json();
}
