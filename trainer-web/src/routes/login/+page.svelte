<script lang="ts">
	/**
	 * Unified login page - detects user role and redirects accordingly.
	 */
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import { login, register, type TokenResponse } from '$lib/api/auth';
	import { session } from '$lib/session';
	import { getStoredSession, apiUrl } from '$lib/api/client';

	let mode: 'login' | 'register' = $state('login');
	let email = $state('');
	let password = $state('');
	let username = $state('');
	let fullName = $state('');
	let selectedRole: 'teacher' | 'vetter' | 'student' = $state('teacher');
	let error = $state('');
	let loading = $state(false);
	let signupEnabled = $state(true);
	let studentSignupEnabled = $state(false);
	let checkingSignup = $state(true);
	const SIGNUP_SETTINGS_TIMEOUT_MS = 5000;

	async function fetchSignupSettings(): Promise<{ signupEnabled: boolean; studentSignupEnabled: boolean }> {
		const controller = new AbortController();
		const timeoutId = window.setTimeout(() => controller.abort(), SIGNUP_SETTINGS_TIMEOUT_MS);

		try {
			const res = await fetch(apiUrl('/settings/signup'), {
				signal: controller.signal,
				cache: 'no-store'
			});
			if (!res.ok) {
				return { signupEnabled: true, studentSignupEnabled: true };
			}
			const data = await res.json();
			return {
				signupEnabled: data.signup_enabled ?? true,
				studentSignupEnabled: data.student_signup_enabled ?? false
			};
		} catch {
			return { signupEnabled: true, studentSignupEnabled: true };
		} finally {
			window.clearTimeout(timeoutId);
		}
	}

	onMount(async () => {
		// If already logged in, redirect to appropriate dashboard
		const existingSession = getStoredSession();
		if (existingSession?.user?.role) {
			redirectByRole(existingSession.user.role);
			return;
		}

		const settings = await fetchSignupSettings();
		signupEnabled = settings.signupEnabled;
		studentSignupEnabled = settings.studentSignupEnabled;
		checkingSignup = false;
	});

	function redirectByRole(role: string) {
		switch (role) {
			case 'admin':
				goto('/admin/dashboard');
				break;
			case 'vetter':
				goto('/vetter/dashboard');
				break;
			case 'student':
				goto('/student');
				break;
			case 'teacher':
			default:
				goto('/teacher/subjects');
				break;
		}
	}

	async function handleSubmit() {
		error = '';
		loading = true;
		try {
			let response: TokenResponse;
			if (mode === 'login') {
				response = await login({ email, password });
			} else {
				if (selectedRole === 'student' && !studentSignupEnabled && !checkingSignup) {
					error = 'Student self-signup is currently disabled. Please contact your teacher.';
					loading = false;
					return;
				}
				if (selectedRole !== 'student' && !signupEnabled && !checkingSignup) {
					error = 'Signup is currently disabled. Please contact an administrator.';
					loading = false;
					return;
				}
				if (!username.trim()) {
					error = 'Username is required';
					loading = false;
					return;
				}
				if (password.length < 8) {
					error = 'Password must be at least 8 characters';
					loading = false;
					return;
				}
				response = await register({
					email,
					username: username.trim().toLowerCase(),
					full_name: fullName.trim() || undefined,
					password,
					role: selectedRole
				});
			}
			session.refresh();
			redirectByRole(response.user.role);
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Something went wrong';
		} finally {
			loading = false;
		}
	}
</script>

<svelte:head>
	<title>Sign In — VQuest</title>
</svelte:head>

<div class="auth-page">
	<div class="auth-card glass-panel animate-scale-in">
		<a href="/" class="back-link">
			<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
				<polyline points="15 18 9 12 15 6"></polyline>
			</svg>
			Back
		</a>

		<div class="auth-header">
			<div class="auth-icon">
				<img src="/logo.png" alt="VQuest" class="auth-logo" />
			</div>
			<h1 class="auth-title font-serif">{mode === 'login' ? 'Welcome Back' : 'Create Account'}</h1>
			<p class="auth-subtitle">
				{mode === 'login' ? 'Sign in to continue to VQuest' : 'Join VQuest to get started'}
			</p>
		</div>

		{#if error}
			<div class="error-banner" role="alert">{error}</div>
		{/if}

		<form onsubmit={(e) => { e.preventDefault(); handleSubmit(); }}>
			{#if mode === 'register'}
				<label class="field">
					<span class="field-label">Username</span>
					<input
						type="text"
						bind:value={username}
						placeholder="e.g. jane_doe"
						required
						minlength={3}
						maxlength={50}
						autocomplete="username"
						class="field-input"
					/>
				</label>

				<label class="field">
					<span class="field-label">Full Name <span class="optional">(optional)</span></span>
					<input
						type="text"
						bind:value={fullName}
						placeholder="Jane Doe"
						maxlength={255}
						autocomplete="name"
						class="field-input"
					/>
				</label>

				<div class="field">
					<span class="field-label">Role</span>
					<div class="role-selector">
						<button
							type="button"
							class="role-option"
							class:selected={selectedRole === 'teacher'}
							onclick={() => selectedRole = 'teacher'}
						>
							<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
								<path d="M12 20h9"></path>
								<path d="M16.5 3.5a 2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"></path>
							</svg>
							Teacher
						</button>
						<button
							type="button"
							class="role-option"
							class:selected={selectedRole === 'vetter'}
							onclick={() => selectedRole = 'vetter'}
						>
							<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
								<circle cx="11" cy="11" r="8"></circle>
								<path d="m21 21-4.3-4.3"></path>
							</svg>
							Vetter
						</button>
						<button
							type="button"
							class="role-option"
							class:selected={selectedRole === 'student'}
							onclick={() => selectedRole = 'student'}
							disabled={!studentSignupEnabled && !checkingSignup}
							title={!studentSignupEnabled && !checkingSignup ? 'Student signup is currently disabled' : 'Sign up as a student'}
						>
							<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
								<path d="M4 4h16v4H4z"></path>
								<path d="M4 12h16v8H4z"></path>
								<path d="M9 8v4"></path>
								<path d="M15 8v4"></path>
							</svg>
							Student
						</button>
					</div>
				</div>
			{/if}

			<label class="field">
				<span class="field-label">Email</span>
				<input
					type="email"
					bind:value={email}
					placeholder="your email address"
					required
					autocomplete="email"
					class="field-input"
				/>
			</label>

			<label class="field">
				<span class="field-label">Password</span>
				<input
					type="password"
					bind:value={password}
					placeholder={mode === 'register' ? 'Min 8 characters' : '••••••••'}
					required
					minlength={mode === 'register' ? 8 : undefined}
					autocomplete={mode === 'login' ? 'current-password' : 'new-password'}
					class="field-input"
				/>
			</label>

			<button type="submit" class="submit-btn" disabled={loading}>
				{#if loading}
					<span class="spinner"></span>
				{:else}
					{mode === 'login' ? 'Sign In' : 'Create Account'}
				{/if}
			</button>
		</form>

		<div class="mode-switch">
			{#if mode === 'login'}
				{#if signupEnabled || checkingSignup}
					<span>Don't have an account?</span>
					<button class="switch-btn" onclick={() => { mode = 'register'; error = ''; }}>
						Sign Up
					</button>
				{:else}
					<span>Signup is currently disabled.</span>
				{/if}
			{:else}
				<span>Already have an account?</span>
				<button class="switch-btn" onclick={() => { mode = 'login'; error = ''; }}>
					Sign In
				</button>
			{/if}
		</div>
	</div>
</div>

<style>
	.auth-page {
		min-height: 100vh;
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 2rem 1rem;
	}

	.auth-card {
		padding: 2.5rem 2rem;
		width: 100%;
		max-width: 26rem;
		border-radius: 1.5rem;
		backdrop-filter: blur(10px) saturate(150%) brightness(1.02);
		-webkit-backdrop-filter: blur(10px) saturate(150%) brightness(1.02);
		background: linear-gradient(
			145deg,
			rgba(255,255,255,0.1) 0%,
			rgba(255,255,255,0.05) 50%,
			rgba(255,255,255,0.08) 100%
		);
		box-shadow:
			0 8px 40px rgba(0, 0, 0, 0.25),
			inset 0 1px 1px rgba(255, 255, 255, 0.25),
			inset 0 -1px 1px rgba(255, 255, 255, 0.08),
			0 0 0 1px rgba(255, 255, 255, 0.12);
	}

	.back-link {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		font-size: 0.85rem;
		color: var(--theme-text-muted);
		text-decoration: none;
		margin-bottom: 1.25rem;
		transition: color 0.15s;
	}

	.back-link:hover {
		color: var(--theme-primary);
	}

	.auth-header {
		text-align: center;
		margin-bottom: 1.5rem;
	}

	.auth-icon {
		width: 72px;
		height: 72px;
		display: flex;
		align-items: center;
		justify-content: center;
		margin: 0 auto 0.75rem;
	}

	.auth-logo {
		width: 72px;
		height: 72px;
		object-fit: contain;
	}

	.auth-title {
		font-size: 1.5rem;
		font-weight: 700;
		margin: 0 0 0.35rem;
		color: var(--theme-text);
	}

	.auth-subtitle {
		font-size: 0.9rem;
		color: var(--theme-text-muted);
		margin: 0;
	}

	.error-banner {
		background: rgba(220, 38, 38, 0.15);
		border: 0.5px solid rgba(220, 38, 38, 0.3);
		color: #f87171;
		border-radius: 0.75rem;
		padding: 0.65rem 0.85rem;
		font-size: 0.85rem;
		margin-bottom: 1rem;
	}

	form {
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}

	.field {
		display: flex;
		flex-direction: column;
		gap: 0.3rem;
	}

	.field-label {
		font-size: 0.8rem;
		font-weight: 600;
		color: var(--theme-text);
	}

	.optional {
		font-weight: 400;
		color: var(--theme-text-muted);
	}

	.field-input {
		padding: 0.65rem 0.85rem;
		border: 1px solid rgba(255,255,255,0.15);
		border-radius: 0.75rem;
		background: rgba(255,255,255,0.08);
		backdrop-filter: blur(12px);
		-webkit-backdrop-filter: blur(12px);
		color: var(--theme-text);
		font-size: 0.95rem;
		transition: border-color 0.2s, box-shadow 0.2s, background 0.2s;
		outline: none;
	}

	.field-input:focus {
		border-color: rgba(var(--theme-primary-rgb), 0.5);
		background: rgba(255,255,255,0.12);
		box-shadow: 0 0 0 3px rgba(var(--theme-primary-rgb), 0.15);
	}

	.field-input::placeholder {
		color: var(--theme-text-muted);
		opacity: 0.7;
	}

	.role-selector {
		display: flex;
		gap: 0.5rem;
	}

	.role-option {
		flex: 1;
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 0.5rem;
		padding: 0.7rem 1rem;
		border: 1px solid rgba(255,255,255,0.15);
		border-radius: 0.75rem;
		background: rgba(255,255,255,0.05);
		color: var(--theme-text-muted);
		font-size: 0.9rem;
		font-weight: 500;
		cursor: pointer;
		transition: all 0.2s;
		font-family: inherit;
	}

	.role-option:hover {
		background: rgba(255,255,255,0.1);
		border-color: rgba(255,255,255,0.25);
	}

	.role-option.selected {
		background: rgba(var(--theme-primary-rgb), 0.15);
		border-color: rgba(var(--theme-primary-rgb), 0.4);
		color: var(--theme-primary);
	}

	.submit-btn {
		margin-top: 0.5rem;
		padding: 0.75rem;
		border: none;
		border-radius: 0.75rem;
		background: var(--theme-primary);
		color: white;
		font-size: 1rem;
		font-weight: 600;
		cursor: pointer;
		transition: all 0.2s;
		display: flex;
		align-items: center;
		justify-content: center;
		min-height: 2.75rem;
		font-family: inherit;
	}

	.submit-btn:hover:not(:disabled) {
		filter: brightness(1.1);
		transform: translateY(-1px);
	}

	.submit-btn:active:not(:disabled) {
		transform: scale(0.98);
	}

	.submit-btn:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}

	.spinner {
		width: 1.2rem;
		height: 1.2rem;
		border: 2px solid rgba(255, 255, 255, 0.3);
		border-top-color: white;
		border-radius: 50%;
		animation: spin 0.6s linear infinite;
	}

	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}

	.mode-switch {
		text-align: center;
		margin-top: 1.25rem;
		font-size: 0.85rem;
		color: var(--theme-text-muted);
		display: flex;
		gap: 0.35rem;
		justify-content: center;
		align-items: center;
		min-height: 1.5rem;
	}

	.switch-btn {
		background: none;
		border: none;
		color: var(--theme-primary);
		font-weight: 600;
		cursor: pointer;
		font-size: 0.85rem;
		padding: 0;
		font-family: inherit;
	}

	.switch-btn:hover {
		text-decoration: underline;
	}

	@media (max-width: 768px) {
		.auth-page {
			padding: 1.5rem 0.75rem;
		}

		.auth-card {
			padding: 2rem 1.5rem;
			border-radius: 1.25rem;
			backdrop-filter: blur(10px) saturate(150%) brightness(1.02);
			-webkit-backdrop-filter: blur(10px) saturate(150%) brightness(1.02);
		}

		.auth-icon {
			width: 60px;
			height: 60px;
		}

		.auth-logo {
			width: 60px;
			height: 60px;
		}

		.auth-title {
			font-size: 1.35rem;
		}

		.auth-subtitle {
			font-size: 0.85rem;
		}
	}

	@media (max-width: 480px) {
		.auth-page {
			padding: 1rem 0.5rem;
			align-items: flex-start;
			padding-top: 2rem;
		}

		.auth-card {
			padding: 1.5rem 1.25rem;
			border-radius: 1rem;
			backdrop-filter: blur(10px) saturate(150%) brightness(1.02);
			-webkit-backdrop-filter: blur(10px) saturate(150%) brightness(1.02);
		}

		.back-link {
			font-size: 0.8rem;
			margin-bottom: 1rem;
		}

		.auth-header {
			margin-bottom: 1.25rem;
		}

		.auth-icon {
			width: 52px;
			height: 52px;
			margin-bottom: 0.5rem;
		}

		.auth-logo {
			width: 52px;
			height: 52px;
		}

		.auth-title {
			font-size: 1.25rem;
		}

		.auth-subtitle {
			font-size: 0.82rem;
		}

		.error-banner {
			padding: 0.55rem 0.75rem;
			font-size: 0.8rem;
			border-radius: 0.6rem;
		}

		form {
			gap: 0.85rem;
		}

		.field-label {
			font-size: 0.75rem;
		}

		.field-input {
			padding: 0.6rem 0.75rem;
			font-size: 0.9rem;
			border-radius: 0.65rem;
		}

		.role-option {
			padding: 0.6rem 0.75rem;
			font-size: 0.82rem;
		}

		.submit-btn {
			padding: 0.65rem;
			font-size: 0.95rem;
			border-radius: 0.65rem;
			min-height: 2.5rem;
		}

		.mode-switch {
			margin-top: 1rem;
			font-size: 0.8rem;
		}

		.switch-btn {
			font-size: 0.8rem;
		}
	}
</style>
