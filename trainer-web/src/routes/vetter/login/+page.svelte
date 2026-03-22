<script lang="ts">
	import { goto } from '$app/navigation';
	import { login, register } from '$lib/api/auth';
	import { session } from '$lib/session';

	let mode = $state<'login' | 'register'>('login');
	let email = $state('');
	let password = $state('');
	let username = $state('');
	let fullName = $state('');
	let error = $state('');
	let loading = $state(false);

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
					role: 'vetter',
				});
			}
			session.refresh();
			goto('/vetter/dashboard');
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Unable to sign in right now';
		} finally {
			loading = false;
		}
	}
</script>

<svelte:head>
	<title>Vetter Sign In — VQuest Trainer</title>
</svelte:head>

<div class="login-page">
	<div class="login-grid">
		<!-- <section class="hero-card">
			<p class="kicker">Vetter Console</p>
			<h1 class="hero-title font-serif">Review With Confidence</h1>
			<p class="hero-copy">
				Approve strong questions quickly, reject weak ones with clear feedback, and keep the question bank clean.
			</p>
			<div class="hero-points">
				<div class="point">Live vetting queues by subject and topic</div>
				<div class="point">One-click approve, reject, or edit</div>
				<div class="point">Structured feedback for regeneration</div>
			</div>
		</section> -->

		<section class="auth-card glass-panel animate-scale-in">
			<a href="/" class="back-link">← Back to Home</a>

			<h2 class="auth-title">{mode === 'login' ? 'Sign In' : 'Create Vetter Account'}</h2>
			<p class="auth-subtitle">
				{mode === 'login' ? 'Continue your review workflow' : 'Set up your vetter access'}
			</p>

			{#if error}
				<div class="error-banner" role="alert">{error}</div>
			{/if}

			<form onsubmit={(e) => { e.preventDefault(); handleSubmit(); }}>
				{#if mode === 'register'}
					<label class="field">
						<span class="field-label">Username</span>
						<input class="field-input" type="text" bind:value={username} minlength={3} maxlength={50} required />
					</label>

					<label class="field">
						<span class="field-label">Full Name <span class="optional">(optional)</span></span>
						<input class="field-input" type="text" bind:value={fullName} maxlength={255} />
					</label>
				{/if}

				<label class="field">
					<span class="field-label">Email</span>
					<input class="field-input" type="email" bind:value={email} required autocomplete="email" />
				</label>

				<label class="field">
					<span class="field-label">Password</span>
					<input
						class="field-input"
						type="password"
						bind:value={password}
						required
						minlength={mode === 'register' ? 8 : undefined}
						autocomplete={mode === 'login' ? 'current-password' : 'new-password'}
					/>
				</label>

				<button class="submit-btn" type="submit" disabled={loading}>
					{#if loading}
						<span class="spinner"></span>
					{:else}
						{mode === 'login' ? 'Sign In' : 'Create Account'}
					{/if}
				</button>
			</form>

			<div class="switch-row">
				{#if mode === 'login'}
					<span>Need an account?</span>
					<button class="switch-btn" onclick={() => { mode = 'register'; error = ''; }}>Sign Up</button>
				{:else}
					<span>Already registered?</span>
					<button class="switch-btn" onclick={() => { mode = 'login'; error = ''; }}>Sign In</button>
				{/if}
			</div>
		</section>
	</div>
</div>

<style>
	.login-page {
		min-height: 100vh;
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 2rem 1rem;
	}

	.login-grid {
		width: min(100%, 430px);
		display: grid;
		grid-template-columns: minmax(0, 1fr);
		gap: 1rem;
		margin: 0 auto;
	}

	/* .hero-card {
		padding: 2rem;
		border-radius: 1.25rem;
		background:
			radial-gradient(120% 100% at 20% 10%, rgba(16, 185, 129, 0.18), transparent 62%),
			radial-gradient(120% 100% at 85% 90%, rgba(14, 116, 144, 0.2), transparent 64%),
			rgba(8, 15, 30, 0.82);
		border: 1px solid rgba(110, 231, 183, 0.22);
		color: #dcfce7;
		display: flex;
		flex-direction: column;
		gap: 0.9rem;
	}

	.kicker {
		margin: 0;
		font-size: 0.74rem;
		font-weight: 700;
		letter-spacing: 0.1em;
		text-transform: uppercase;
		color: #86efac;
	}

	.hero-title {
		margin: 0;
		font-size: clamp(1.8rem, 3vw, 2.35rem);
		line-height: 1.06;
	}

	.hero-copy {
		margin: 0;
		font-size: 0.95rem;
		color: rgba(220, 252, 231, 0.88);
	}

	.hero-points {
		display: flex;
		flex-direction: column;
		gap: 0.45rem;
		margin-top: 0.3rem;
	}

	.point {
		font-size: 0.84rem;
		padding: 0.55rem 0.65rem;
		border-radius: 0.7rem;
		border: 1px solid rgba(167, 243, 208, 0.3);
		background: rgba(15, 23, 42, 0.46);
	} */

	.auth-card {
		padding: 1.5rem;
		border-radius: 1.25rem;
		display: flex;
		flex-direction: column;
		gap: 0.8rem;
	}

	.back-link {
		font-size: 0.84rem;
		color: var(--theme-text-muted);
		text-decoration: none;
	}

	.auth-title {
		margin: 0;
		font-size: 1.3rem;
		color: var(--theme-text-primary);
	}

	.auth-subtitle {
		margin: 0;
		font-size: 0.9rem;
		color: var(--theme-text-muted);
	}

	.error-banner {
		background: rgba(220, 38, 38, 0.14);
		border: 1px solid rgba(220, 38, 38, 0.34);
		color: #b91c1c;
		border-radius: 0.75rem;
		padding: 0.62rem 0.8rem;
		font-size: 0.84rem;
	}

	form {
		display: flex;
		flex-direction: column;
		gap: 0.72rem;
	}

	.field {
		display: flex;
		flex-direction: column;
		gap: 0.26rem;
	}

	.field-label {
		font-size: 0.79rem;
		font-weight: 700;
		color: var(--theme-text-primary);
	}

	.optional {
		font-weight: 500;
		color: var(--theme-text-muted);
	}

	.field-input {
		padding: 0.62rem 0.78rem;
		border-radius: 0.72rem;
		border: 1px solid rgba(17, 24, 39, 0.16);
		background: rgba(255, 255, 255, 0.88);
		font: inherit;
		color: var(--theme-text-primary);
	}

	.submit-btn {
		min-height: 44px;
		border-radius: 999px;
		border: 1px solid rgba(16, 185, 129, 0.48);
		background: rgba(16, 185, 129, 0.2);
		font: inherit;
		font-weight: 800;
		color: #065f46;
		cursor: pointer;
		display: inline-flex;
		justify-content: center;
		align-items: center;
	}

	.switch-row {
		display: flex;
		justify-content: center;
		align-items: center;
		gap: 0.45rem;
		font-size: 0.83rem;
		color: var(--theme-text-muted);
	}

	.switch-btn {
		border: none;
		background: transparent;
		color: var(--theme-primary);
		font-weight: 700;
		cursor: pointer;
		font: inherit;
	}

	.spinner {
		width: 16px;
		height: 16px;
		border-radius: 50%;
		border: 2px solid rgba(6, 95, 70, 0.2);
		border-top-color: #065f46;
		animation: spin 0.7s linear infinite;
	}

	@keyframes spin {
		to { transform: rotate(360deg); }
	}

	@media (max-width: 900px) {
		.login-grid {
			grid-template-columns: 1fr;
			max-width: 430px;
		}

		/* .hero-card {
			padding: 1.45rem;
		}

		.hero-title {
			font-size: 1.75rem;
		} */
	}
</style>
