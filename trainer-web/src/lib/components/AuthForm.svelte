<script lang="ts">
	/**
	 * Unified auth form for both Teacher and Vetter login/register.
	 */
	import { goto } from '$app/navigation';
	import { login, register } from '$lib/api/auth';
	import { session } from '$lib/session';

	interface Props {
		role: 'teacher' | 'vetter';
	}

	let { role }: Props = $props();

	let mode: 'login' | 'register' = $state('login');
	let email = $state('');
	let password = $state('');
	let username = $state('');
	let fullName = $state('');
	let error = $state('');
	let loading = $state(false);

	const roleLabel = $derived(role === 'teacher' ? 'Teacher' : 'Vetter');
	const dashboardPath = $derived(role === 'teacher' ? '/teacher/dashboard' : '/vetter/dashboard');

	async function handleSubmit() {
		error = '';
		loading = true;
		try {
			if (mode === 'login') {
				await login({ email, password });
			} else {
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
				await register({
					email,
					username: username.trim().toLowerCase(),
					full_name: fullName.trim() || undefined,
					password,
					role
				});
			}
			session.refresh();
			goto(dashboardPath);
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Something went wrong';
		} finally {
			loading = false;
		}
	}
</script>

<div class="auth-page">
	<div class="auth-card glass-panel animate-scale-in">
		<a href="/" class="back-link">
			<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
				<polyline points="15 18 9 12 15 6"></polyline>
			</svg>
			Back
		</a>

		<div class="auth-header">
			<div class="auth-icon" class:teacher={role === 'teacher'} class:vetter={role === 'vetter'}>
				{#if role === 'teacher'}
					<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
						<path d="M12 20h9"></path>
						<path d="M16.5 3.5a 2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"></path>
					</svg>
				{:else}
					<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
						<circle cx="11" cy="11" r="8"></circle>
						<path d="m21 21-4.3-4.3"></path>
					</svg>
				{/if}
			</div>
			<h1 class="auth-title font-serif">{roleLabel} {mode === 'login' ? 'Sign In' : 'Sign Up'}</h1>
			<p class="auth-subtitle">
				{#if role === 'teacher'}
					Generate AI-powered assessments from your materials.
				{:else}
					Review and improve AI-generated questions.
				{/if}
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
				<span>Don't have an account?</span>
				<button class="switch-btn" onclick={() => { mode = 'register'; error = ''; }}>
					Sign Up
				</button>
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
		width: 64px;
		height: 64px;
		border-radius: 50%;
		display: flex;
		align-items: center;
		justify-content: center;
		margin: 0 auto 0.75rem;
	}

	.auth-icon.teacher {
		background: rgba(59, 130, 246, 0.2);
		color: #93c5fd;
		border: 1px solid rgba(59, 130, 246, 0.3);
	}

	.auth-icon.vetter {
		background: rgba(16, 185, 129, 0.2);
		color: #6ee7b7;
		border: 1px solid rgba(16, 185, 129, 0.3);
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
		}

		.auth-icon {
			width: 56px;
			height: 56px;
		}

		.auth-icon svg {
			width: 24px;
			height: 24px;
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
		}

		.back-link {
			font-size: 0.8rem;
			margin-bottom: 1rem;
		}

		.auth-header {
			margin-bottom: 1.25rem;
		}

		.auth-icon {
			width: 48px;
			height: 48px;
			margin-bottom: 0.5rem;
		}

		.auth-icon svg {
			width: 20px;
			height: 20px;
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
