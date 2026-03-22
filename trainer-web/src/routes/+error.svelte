<script lang="ts">
	import { goto } from '$app/navigation';

	let { status = 500, error } = $props<{ status?: number; error?: unknown }>();

	const isNotFound = $derived(status === 404);
	const heading = $derived(isNotFound ? 'Page Not Found' : 'Something Went Wrong');
	const message = $derived(
		isNotFound
			? 'The page you are looking for does not exist or has been moved.'
			: 'An unexpected error occurred while loading this page.'
	);
	const code = $derived(String(status || 500));

	function goHome() {
		goto('/');
	}

	function goBack() {
		if (typeof window !== 'undefined' && window.history.length > 1) {
			window.history.back();
			return;
		}
		goto('/');
	}
</script>

<svelte:head>
	<title>{isNotFound ? '404 Not Found' : `${code} Error`} — VQuest Trainer</title>
</svelte:head>

<div class="error-page">
	<div class="error-card glass-panel animate-scale-in" role="alert" aria-live="polite">
		<p class="error-code">{code}</p>
		<h1 class="error-title font-serif">{heading}</h1>
		<p class="error-message">{message}</p>
		<div class="error-actions">
			<button class="error-btn secondary" onclick={goBack}>Go Back</button>
			<button class="error-btn primary" onclick={goHome}>Go Home</button>
		</div>
	</div>
</div>

<style>
	.error-page {
		min-height: 100vh;
		display: grid;
		place-items: center;
		padding: 1.5rem;
	}

	.error-card {
		width: min(560px, 100%);
		padding: 2rem 1.5rem;
		border-radius: 1.25rem;
		display: flex;
		flex-direction: column;
		align-items: center;
		text-align: center;
		gap: 0.7rem;
	}

	.error-code {
		margin: 0;
		font-size: clamp(2.4rem, 8vw, 4.5rem);
		font-weight: 900;
		line-height: 1;
		letter-spacing: 0.02em;
		color: rgba(var(--theme-primary-rgb), 0.95);
	}

	.error-title {
		margin: 0;
		font-size: clamp(1.35rem, 4.6vw, 2rem);
		font-weight: 800;
		color: var(--theme-text-primary);
	}

	.error-message {
		margin: 0;
		max-width: 42ch;
		line-height: 1.6;
		color: var(--theme-text-muted);
	}

	.error-actions {
		display: flex;
		gap: 0.75rem;
		margin-top: 0.4rem;
		width: 100%;
		justify-content: center;
		flex-wrap: wrap;
	}

	.error-btn {
		min-width: 132px;
		height: 44px;
		padding: 0 1rem;
		border-radius: 999px;
		font: inherit;
		font-size: 0.88rem;
		font-weight: 800;
		border: 1px solid transparent;
		cursor: pointer;
		transition: transform 0.15s ease, border-color 0.15s ease, background-color 0.15s ease;
	}

	.error-btn:hover {
		transform: translateY(-1px);
	}

	.error-btn.primary {
		color: var(--theme-text-primary);
		background: rgba(var(--theme-primary-rgb), 0.22);
		border-color: rgba(var(--theme-primary-rgb), 0.5);
	}

	.error-btn.secondary {
		color: var(--theme-primary);
		background: rgba(var(--theme-primary-rgb), 0.12);
		border-color: rgba(var(--theme-primary-rgb), 0.38);
	}

	:global([data-theme='light']) .error-card {
		background: #ffffff;
		border: 1px solid rgba(148, 163, 184, 0.32);
		box-shadow: 0 16px 34px rgba(15, 23, 42, 0.1);
	}

	:global([data-theme='light']) .error-title,
	:global([data-theme='light']) .error-code {
		color: #0f172a;
	}

	:global([data-theme='light']) .error-message {
		color: #475569;
	}
</style>
