<script lang="ts">
	/**
	 * Unified auth form for both Teacher and Vetter login/register.
	 * Props:
	 *   role — 'teacher' | 'vetter'
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
	const roleIcon = $derived(role === 'teacher' ? '📝' : '🔍');
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
	<div class="auth-card">
		<a href="/" class="back-link">&larr; Back</a>

		<div class="auth-header">
			<span class="auth-icon">{roleIcon}</span>
			<h1 class="auth-title">{roleLabel} {mode === 'login' ? 'Sign In' : 'Sign Up'}</h1>
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
					placeholder="you@university.edu"
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
		background: linear-gradient(135deg, rgba(255,255,255,0.12) 0%, rgba(255,255,255,0.06) 100%);
		backdrop-filter: blur(24px) saturate(180%);
		-webkit-backdrop-filter: blur(24px) saturate(180%);
		border: 0.5px solid rgba(255,255,255,0.18);
		border-radius: 1.25rem;
		padding: 2.5rem 2rem;
		width: 100%;
		max-width: 26rem;
		box-shadow:
			inset 0 1px 0 0 rgba(255,255,255,0.1),
			0 8px 32px rgba(0, 0, 0, 0.15);
	}

	.back-link {
		display: inline-block;
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
		font-size: 2.5rem;
		display: block;
		margin-bottom: 0.5rem;
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
		border-radius: 0.5rem;
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
		padding: 0.6rem 0.8rem;
		border: 0.5px solid rgba(255,255,255,0.15);
		border-radius: 0.5rem;
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
		padding: 0.7rem;
		border: none;
		border-radius: 0.5rem;
		background: var(--theme-primary);
		color: white;
		font-size: 1rem;
		font-weight: 600;
		cursor: pointer;
		transition: background 0.2s, transform 0.1s;
		display: flex;
		align-items: center;
		justify-content: center;
		min-height: 2.75rem;
	}

	.submit-btn:hover:not(:disabled) {
		background: var(--theme-primary-hover);
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
	}

	.switch-btn:hover {
		text-decoration: underline;
	}
</style>
