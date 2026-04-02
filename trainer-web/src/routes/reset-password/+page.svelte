<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { resetPassword } from '$lib/api/auth';

	let token = $state('');
	let password = $state('');
	let confirmPassword = $state('');
	let error = $state('');
	let message = $state('');
	let loading = $state(false);

	onMount(() => {
		if (typeof window !== 'undefined') {
			token = new URL(window.location.href).searchParams.get('token') ?? '';
		}
	});

	async function handleSubmit() {
		error = '';
		message = '';

		if (!token) {
			error = 'This password reset link is missing its token.';
			return;
		}
		if (password.length < 8) {
			error = 'Password must be at least 8 characters.';
			return;
		}
		if (password !== confirmPassword) {
			error = 'Passwords do not match.';
			return;
		}

		loading = true;
		try {
			const response = await resetPassword({ token, new_password: password });
			message = response.message;
			password = '';
			confirmPassword = '';
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Unable to reset password';
		} finally {
			loading = false;
		}
	}
</script>

<svelte:head>
	<title>Choose New Password — VQuest</title>
</svelte:head>

<div class="auth-page">
	<div class="auth-card glass-panel animate-scale-in">
		<a href="/" class="back-link">Back to Sign In</a>

		<div class="auth-header">
			<div class="auth-icon">
				<img src="/logo.png" alt="VQuest" class="auth-logo" />
			</div>
			<h1 class="auth-title font-serif">Choose a New Password</h1>
			<p class="auth-subtitle">Set a new password for your VQuest account.</p>
		</div>

		{#if error}
			<div class="error-banner" role="alert">{error}</div>
		{/if}

		{#if message}
			<div class="success-banner" role="status">{message}</div>
		{/if}

		<form onsubmit={(e) => { e.preventDefault(); handleSubmit(); }}>
			<label class="field">
				<span class="field-label">New Password</span>
				<input
					type="password"
					bind:value={password}
					placeholder="Minimum 8 characters"
					required
					minlength={8}
					autocomplete="new-password"
					class="field-input"
				/>
			</label>

			<label class="field">
				<span class="field-label">Confirm Password</span>
				<input
					type="password"
					bind:value={confirmPassword}
					placeholder="Re-enter your password"
					required
					autocomplete="new-password"
					class="field-input"
				/>
			</label>

			<button type="submit" class="submit-btn" disabled={loading || !token}>
				{#if loading}
					<span class="spinner"></span>
				{:else}
					Reset Password
				{/if}
			</button>
		</form>

		<div class="mode-switch">
			<button class="switch-btn" onclick={() => goto('/')}>Return to Sign In</button>
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
		max-width: 28rem;
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
	}

	.back-link:hover,
	.switch-btn:hover {
		text-decoration: underline;
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

	.error-banner,
	.success-banner {
		border-radius: 0.75rem;
		padding: 0.7rem 0.85rem;
		font-size: 0.85rem;
		margin-bottom: 1rem;
	}

	.error-banner {
		background: rgba(220, 38, 38, 0.15);
		border: 0.5px solid rgba(220, 38, 38, 0.3);
		color: #f87171;
	}

	.success-banner {
		background: rgba(15, 118, 110, 0.16);
		border: 0.5px solid rgba(15, 118, 110, 0.35);
		color: #99f6e4;
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

	.field-input {
		padding: 0.65rem 0.85rem;
		border: 1px solid rgba(255,255,255,0.15);
		border-radius: 0.75rem;
		background: rgba(255,255,255,0.08);
		backdrop-filter: blur(12px);
		-webkit-backdrop-filter: blur(12px);
		color: var(--theme-text);
		font-size: 0.95rem;
		outline: none;
	}

	.field-input:focus {
		border-color: rgba(var(--theme-primary-rgb), 0.5);
		background: rgba(255,255,255,0.12);
		box-shadow: 0 0 0 3px rgba(var(--theme-primary-rgb), 0.15);
	}

	.submit-btn {
		margin-top: 0.35rem;
		padding: 0.75rem;
		border: none;
		border-radius: 0.75rem;
		background: var(--theme-primary);
		color: white;
		font-size: 1rem;
		font-weight: 600;
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		min-height: 2.75rem;
		font-family: inherit;
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

	.mode-switch {
		text-align: center;
		margin-top: 1.25rem;
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

	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}
</style>