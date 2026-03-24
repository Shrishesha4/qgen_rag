<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { session } from '$lib/session';
	import { apiFetch } from '$lib/api/client';

	let loading = $state(true);
	let signupEnabled = $state(true);
	let settingsLoading = $state(false);
	let settingsError = $state('');
	let settingsSaved = $state(false);

	onMount(() => {
		const unsub = session.subscribe((s) => {
			if (!s || s.user.role !== 'admin') {
				goto('/admin/login');
			}
		});
		void loadSettings();
		return unsub;
	});

	async function loadSettings() {
		loading = true;
		settingsError = '';
		try {
			const res = await apiFetch<{ signup_enabled: boolean }>('/settings/signup');
			signupEnabled = res.signup_enabled;
		} catch (e: unknown) {
			settingsError = e instanceof Error ? e.message : 'Failed to load settings';
		} finally {
			loading = false;
		}
	}

	async function toggleSignup() {
		settingsLoading = true;
		settingsError = '';
		settingsSaved = false;
		try {
			const res = await apiFetch<{ signup_enabled: boolean }>('/settings/signup', {
				method: 'PUT',
				body: JSON.stringify({ signup_enabled: !signupEnabled })
			});
			signupEnabled = res.signup_enabled;
			settingsSaved = true;
			setTimeout(() => (settingsSaved = false), 1800);
		} catch (e: unknown) {
			settingsError = e instanceof Error ? e.message : 'Failed to update settings';
		} finally {
			settingsLoading = false;
		}
	}
</script>

<svelte:head>
	<title>Admin Settings — VQuest Trainer</title>
</svelte:head>

<div class="page">
	<!-- <div class="header glass-panel">
		<div>
			<p class="eyebrow">Admin Console</p>
			<h1 class="title">Settings</h1>
			<p class="subtitle">Manage platform-wide controls for account access and onboarding.</p>
		</div>
	</div> -->

	{#if settingsError}
		<div class="settings-error" role="alert">{settingsError}</div>
	{/if}

	{#if loading}
		<div class="center-state glass-panel">
			<div class="spinner"></div>
			<p>Loading settings...</p>
		</div>
	{:else}
		<div class="section glass-panel">
			<h2 class="section-title">System Settings</h2>
			<div class="settings-list">
				<div class="setting-item">
					<div class="setting-info">
						<span class="setting-label">User Registration</span>
						<span class="setting-desc">Allow new users to create accounts. When disabled, only existing users can log in.</span>
					</div>
					<div class="setting-control">
						<button
							class="toggle-btn"
							class:enabled={signupEnabled}
							onclick={toggleSignup}
							disabled={settingsLoading}
						>
							{#if settingsLoading}
								<span class="toggle-spinner"></span>
							{:else}
								<span class="toggle-track">
									<span class="toggle-thumb"></span>
								</span>
								<span class="toggle-label">{signupEnabled ? 'Enabled' : 'Disabled'}</span>
							{/if}
						</button>
						{#if settingsSaved}
							<span class="saved-indicator">Saved</span>
						{/if}
					</div>
				</div>
			</div>
		</div>
	{/if}
</div>

<style>
	.page {
		max-width: 980px;
		margin: 0 auto;
		padding: 2rem 1.25rem 2.4rem;
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}

	/* .header {
		padding: 1rem;
		border-radius: 1rem;
	}

	.eyebrow {
		margin: 0;
		font-size: 0.78rem;
		font-weight: 700;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: #fbbf24;
	}

	.title {
		margin: 0.35rem 0 0;
		font-size: 1.9rem;
		font-weight: 800;
		color: var(--theme-text);
	}

	.subtitle {
		margin: 0.45rem 0 0;
		color: var(--theme-text-muted);
		line-height: 1.55;
	} */

	.section {
		padding: 1.2rem;
		border-radius: 1rem;
	}

	.section-title {
		margin: 0 0 1rem;
		font-size: 1.08rem;
		font-weight: 700;
		color: var(--theme-text);
	}

	.settings-error {
		background: rgba(220, 38, 38, 0.15);
		border: 0.5px solid rgba(220, 38, 38, 0.3);
		color: #f87171;
		border-radius: 0.75rem;
		padding: 0.65rem 0.85rem;
		font-size: 0.85rem;
	}

	.settings-list {
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}

	.setting-item {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 1.5rem;
		padding: 1rem;
		border-radius: 0.85rem;
		background: color-mix(in srgb, var(--theme-surface) 88%, transparent);
		border: 1px solid var(--theme-glass-border);
	}

	.setting-info {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		flex: 1;
	}

	.setting-label {
		font-size: 0.95rem;
		font-weight: 600;
		color: var(--theme-text);
	}

	.setting-desc {
		font-size: 0.82rem;
		color: var(--theme-text-muted);
		line-height: 1.45;
	}

	.setting-control {
		display: flex;
		align-items: center;
		gap: 0.75rem;
	}

	.toggle-btn {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		padding: 0.5rem 0.85rem;
		border: 1px solid var(--theme-glass-border);
		border-radius: 999px;
		background: var(--theme-input-bg);
		color: var(--theme-text-muted);
		font-size: 0.82rem;
		font-weight: 600;
		cursor: pointer;
		transition: all 0.2s;
		font-family: inherit;
		min-width: 120px;
		justify-content: center;
	}

	.toggle-btn:hover:not(:disabled) {
		filter: brightness(1.06);
	}

	.toggle-btn:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}

	.toggle-btn.enabled {
		background: color-mix(in srgb, #10b981 18%, var(--theme-input-bg));
		border-color: color-mix(in srgb, #10b981 55%, var(--theme-glass-border));
		color: color-mix(in srgb, #10b981 74%, var(--theme-text));
	}

	.toggle-track {
		width: 32px;
		height: 18px;
		border-radius: 999px;
		background: color-mix(in srgb, var(--theme-text-muted) 28%, transparent);
		position: relative;
		transition: background 0.2s;
	}

	.toggle-btn.enabled .toggle-track {
		background: #10b981;
	}

	.toggle-thumb {
		position: absolute;
		top: 2px;
		left: 2px;
		width: 14px;
		height: 14px;
		border-radius: 50%;
		background: white;
		transition: transform 0.2s;
	}

	.toggle-btn.enabled .toggle-thumb {
		transform: translateX(14px);
	}

	.toggle-label {
		min-width: 55px;
	}

	.toggle-spinner {
		width: 1rem;
		height: 1rem;
		border: 2px solid rgba(255, 255, 255, 0.2);
		border-top-color: var(--theme-primary);
		border-radius: 50%;
		animation: spin 0.6s linear infinite;
	}

	.saved-indicator {
		font-size: 0.78rem;
		font-weight: 700;
		color: #10b981;
	}

	.center-state {
		padding: 1.6rem;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.7rem;
		border-radius: 1rem;
		color: var(--theme-text-muted);
	}

	.spinner {
		width: 1.6rem;
		height: 1.6rem;
		border-radius: 999px;
		border: 2px solid rgba(255, 255, 255, 0.2);
		border-top-color: var(--theme-primary);
		animation: spin 1s linear infinite;
	}

	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}

	@media (max-width: 640px) {
		.page {
			padding: 1.3rem 0.95rem 1.9rem;
		}

		.setting-item {
			flex-direction: column;
			align-items: flex-start;
			gap: 0.85rem;
		}

		.setting-control {
			width: 100%;
			justify-content: flex-start;
		}
	}

	:global([data-color-mode='light']) .section,
	:global([data-color-mode='light']) .setting-item,
	:global([data-color-mode='light']) .center-state {
		background: #ffffff;
		border-color: rgba(148, 163, 184, 0.32);
		box-shadow: 0 12px 32px rgba(15, 23, 42, 0.08);
	}

	/* :global([data-color-mode='light']) .header,
	:global([data-color-mode='light']) .section,
	:global([data-color-mode='light']) .setting-item,
	:global([data-color-mode='light']) .center-state {
		background: #ffffff;
		border-color: rgba(148, 163, 184, 0.32);
		box-shadow: 0 12px 32px rgba(15, 23, 42, 0.08);
	} */

	:global([data-color-mode='light']) .toggle-btn {
		background: #f8fafc;
		border-color: rgba(148, 163, 184, 0.36);
		color: #334155;
	}
</style>
