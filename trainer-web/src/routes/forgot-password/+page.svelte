<script lang="ts">
	import { onMount } from 'svelte';
	import {
		getPasswordResetMethod,
		getSecurityQuestion,
		requestPasswordReset,
		resetPasswordWithSecurityQuestion,
		type PasswordResetMethod
	} from '$lib/api/auth';

	let resetMethod = $state<PasswordResetMethod>('smtp');
	let methodLoading = $state(true);
	let email = $state('');
	let loadedQuestionEmail = $state('');
	let securityQuestion = $state('');
	let securityAnswer = $state('');
	let newPassword = $state('');
	let confirmPassword = $state('');
	let error = $state('');
	let message = $state('');
	let loading = $state(false);

	onMount(() => {
		void loadResetMethod();
	});

	async function loadResetMethod() {
		methodLoading = true;
		error = '';
		try {
			const response = await getPasswordResetMethod();
			resetMethod = response.method;
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Unable to load password reset options';
		} finally {
			methodLoading = false;
		}
	}

	function clearSecurityStep() {
		loadedQuestionEmail = '';
		securityQuestion = '';
		securityAnswer = '';
		newPassword = '';
		confirmPassword = '';
	}

	function handleEmailInput() {
		const normalizedEmail = email.trim().toLowerCase();
		if (normalizedEmail !== loadedQuestionEmail) {
			clearSecurityStep();
		}
	}

	async function loadSecurityQuestionStep() {
		error = '';
		message = '';

		const normalizedEmail = email.trim().toLowerCase();
		if (!normalizedEmail) {
			error = 'Email is required';
			return;
		}

		loading = true;
		try {
			const response = await getSecurityQuestion({ email: normalizedEmail });
			loadedQuestionEmail = normalizedEmail;
			securityQuestion = response.security_question;
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Unable to load security question';
		} finally {
			loading = false;
		}
	}

	async function handleSubmit() {
		error = '';
		message = '';

		const normalizedEmail = email.trim().toLowerCase();
		if (!normalizedEmail) {
			error = 'Email is required';
			return;
		}

		if (resetMethod === 'smtp') {
			loading = true;
			try {
				const response = await requestPasswordReset({ email: normalizedEmail });
				message = response.message;
			} catch (e: unknown) {
				error = e instanceof Error ? e.message : 'Unable to send password reset email';
			} finally {
				loading = false;
			}
			return;
		}

		if (!securityQuestion || loadedQuestionEmail !== normalizedEmail) {
			await loadSecurityQuestionStep();
			return;
		}

		if (!securityAnswer.trim()) {
			error = 'Security answer is required';
			return;
		}
		if (newPassword.length < 8) {
			error = 'New password must be at least 8 characters';
			return;
		}
		if (newPassword !== confirmPassword) {
			error = 'New password and confirmation do not match';
			return;
		}

		loading = true;
		try {
			const response = await resetPasswordWithSecurityQuestion({
				email: normalizedEmail,
				security_answer: securityAnswer.trim(),
				new_password: newPassword
			});
			message = response.message;
			clearSecurityStep();
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Unable to reset password';
		} finally {
			loading = false;
		}
	}
</script>

<svelte:head>
	<title>Forgot Password — VQuest</title>
</svelte:head>

<div class="auth-page">
	<div class="auth-card glass-panel animate-scale-in">
		<a href="/" class="back-link">Back to Sign In</a>

		<div class="auth-header">
			<div class="auth-icon">
				<img src="/logo.png" alt="VQuest" class="auth-logo" />
			</div>
			<h1 class="auth-title font-serif">Reset Your Password</h1>
			{#if methodLoading}
				<p class="auth-subtitle">Loading reset options...</p>
			{:else if resetMethod === 'smtp'}
				<p class="auth-subtitle">Enter your email and we’ll send you a secure reset link.</p>
			{:else}
				<p class="auth-subtitle">Enter your email to load your security question, then set a new password.</p>
			{/if}
		</div>

		<!-- {#if !methodLoading}
			<div class="method-pill">Active reset method: {resetMethod === 'smtp' ? 'SMTP Email' : 'Security Question'}</div>
		{/if} -->

		{#if error}
			<div class="error-banner" role="alert">{error}</div>
		{/if}

		{#if message}
			<div class="success-banner" role="status">{message}</div>
		{/if}

		<form onsubmit={(e) => { e.preventDefault(); handleSubmit(); }}>
			<label class="field">
				<span class="field-label">Email</span>
				<input
					type="email"
					bind:value={email}
					oninput={handleEmailInput}
					placeholder="your email address"
					required
					autocomplete="email"
					class="field-input"
				/>
			</label>

			{#if !methodLoading && resetMethod === 'security_question'}
				{#if securityQuestion}
					<div class="question-card">
						<span class="question-label">Security Question</span>
						<p>{securityQuestion}</p>
					</div>

					<label class="field">
						<span class="field-label">Security Answer</span>
						<input
							type="password"
							bind:value={securityAnswer}
							placeholder="Enter your saved answer"
							required
							autocomplete="off"
							class="field-input"
						/>
					</label>

					<label class="field">
						<span class="field-label">New Password</span>
						<input
							type="password"
							bind:value={newPassword}
							placeholder="Min 8 characters"
							required
							minlength={8}
							autocomplete="new-password"
							class="field-input"
						/>
					</label>

					<label class="field">
						<span class="field-label">Confirm New Password</span>
						<input
							type="password"
							bind:value={confirmPassword}
							placeholder="Repeat the new password"
							required
							minlength={8}
							autocomplete="new-password"
							class="field-input"
						/>
					</label>
				{:else}
					<p class="helper-copy">We will show your configured question after you enter the account email.</p>
				{/if}
			{/if}

			<button type="submit" class="submit-btn" disabled={loading || methodLoading}>
				{#if loading || methodLoading}
					<span class="spinner"></span>
				{:else if resetMethod === 'smtp'}
					Send Reset Link
				{:else if securityQuestion}
					Reset Password
				{:else}
					Show Security Question
				{/if}
			</button>
		</form>

		<div class="mode-switch">
			<span>Remembered your password?</span>
			<a href="/" class="inline-link">Sign In</a>
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
		max-width: 30rem;
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
	.inline-link:hover {
		text-decoration: underline;
	}

	.auth-header {
		text-align: center;
		margin-bottom: 1.2rem;
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
		line-height: 1.45;
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

	.question-card {
		padding: 0.95rem 1rem;
		border-radius: 0.9rem;
		background: rgba(255,255,255,0.08);
		border: 1px solid rgba(255,255,255,0.12);
	}

	.question-label {
		display: block;
		font-size: 0.76rem;
		font-weight: 700;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: var(--theme-text-muted);
		margin-bottom: 0.45rem;
	}

	.question-card p,
	.helper-copy {
		margin: 0;
		font-size: 0.88rem;
		line-height: 1.5;
		color: var(--theme-text-muted);
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
		font-size: 0.85rem;
		color: var(--theme-text-muted);
		display: flex;
		gap: 0.35rem;
		justify-content: center;
		align-items: center;
	}

	.inline-link {
		color: var(--theme-primary);
		text-decoration: none;
		font-weight: 600;
	}

	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}
</style>