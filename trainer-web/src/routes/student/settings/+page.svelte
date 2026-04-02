<script lang="ts">
	import { onMount } from 'svelte';
	import { getTutorPreferences, updateTutorPreferences } from '$lib/api/sessions';
	import {
		Sparkles,
		Cpu,
		Bot,
		Check,
		CheckCircle,
		Save,
		RefreshCw,
		AlertCircle,
		ArrowLeft,
	} from 'lucide-svelte';

	type ProviderInfo = { key: string; name: string; model: string };

	let providers = $state<ProviderInfo[]>([]);
	let selectedProviderId = $state<string | null>(null);
	let isLoading = $state(true);
	let isSaving = $state(false);
	let error = $state<string | null>(null);
	let successMessage = $state<string | null>(null);
	const selectedProviderName = $derived(
		providers.find((provider) => provider.key === selectedProviderId)?.name ?? 'Choose a tutor',
	);

	onMount(async () => {
		await loadSettings();
	});

	async function loadSettings() {
		isLoading = true;
		error = null;
		try {
			const prefs = await getTutorPreferences();
			providers = prefs.available_providers ?? [];
			selectedProviderId = prefs.preferred_tutor_provider ?? providers[0]?.key ?? null;
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to load tutor settings';
		} finally {
			isLoading = false;
		}
	}

	async function savePreferences() {
		if (!selectedProviderId) return;
		isSaving = true;
		error = null;
		successMessage = null;
		try {
			const response = await updateTutorPreferences(selectedProviderId);
			providers = response.available_providers ?? providers;
			selectedProviderId = response.preferred_tutor_provider ?? selectedProviderId;
			successMessage = 'Tutor preference saved!';
			setTimeout(() => { successMessage = null; }, 3000);
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to save preferences';
		} finally {
			isSaving = false;
		}
	}

	function selectProvider(key: string) {
		selectedProviderId = key;
		successMessage = null;
	}
</script>

<svelte:head>
	<title>Tutor Settings | GEL Train</title>
</svelte:head>


<div class="page-container student-shell settings-page space-y-8">
	<header class="settings-header glass-panel">
		<div class="settings-header-main">
			<a href="/student/train" class="back-chip" aria-label="Back to GEL Train">
				<ArrowLeft class="h-4 w-4" />
			</a>
			<div>
				<p class="settings-eyebrow">Student Preferences</p>
				<h1 class="settings-title">Tutor Settings</h1>
				<p class="muted">Choose which AI model powers your tutoring sessions.</p>
			</div>
		</div>

		<div class="settings-focus-card">
			<span class="focus-label">Selected Tutor</span>
			<strong>{selectedProviderName}</strong>
			<p class="focus-note">Applies to new sessions only.</p>
		</div>
	</header>

	{#if isLoading}
		<div class="glass-panel center-state large-state">
			<div class="spinner"></div>
			<p class="muted">Loading available tutors...</p>
		</div>
	{:else if error}
		<div class="glass-panel error-panel">
			<div class="flex-row">
				<AlertCircle class="h-5 w-5" />
				<span>{error}</span>
			</div>
			<button class="pill ghost" onclick={() => void loadSettings()}>Try Again</button>
		</div>
	{:else}
		<section class="glass-panel settings-panel space-y-6">
			<div class="section-head">
				<Bot class="h-5 w-5" />
				<h2 class="section-title">Choose Your AI Tutor</h2>
			</div>

			{#if providers.length === 0}
				<div class="center-state">
					<Cpu class="h-8 w-8" style="opacity:0.35" />
					<p class="empty-title">No providers available</p>
					<p class="muted">Ask an administrator to enable at least one provider.</p>
				</div>
			{:else}
				<div class="provider-grid">
					{#each providers as provider}
						<button
							class="provider-card"
							class:is-selected={selectedProviderId === provider.key}
							onclick={() => selectProvider(provider.key)}
							type="button"
						>
							{#if selectedProviderId === provider.key}
								<div class="selected-badge" aria-label="Selected">
									<Check class="h-3.5 w-3.5" />
								</div>
							{/if}
							<div class="provider-card-icon">
								<Cpu class="h-6 w-6" />
							</div>
							<div class="provider-card-body">
								<span class="provider-name">{provider.name}</span>
								<span class="provider-model">{provider.model}</span>
								<span class="status-chip">Available</span>
							</div>
						</button>
					{/each}
				</div>
			{/if}

			<!-- Context note -->
			<div class="info-banner">
				<Sparkles class="h-4 w-4" style="color: rgb(234,179,8); flex-shrink:0; margin-top:1px;" />
				<p>
					Your choice applies to <strong>new</strong> sessions only. Sessions already in progress
					will continue using the provider they started with.
				</p>
			</div>

			<!-- Save row -->
			<div class="save-row">
				{#if successMessage}
					<span class="success-msg">
						<CheckCircle class="h-4 w-4" />
						{successMessage}
					</span>
				{:else}
					<span></span>
				{/if}
				<button
					class="pill primary save-btn"
					disabled={isSaving || !selectedProviderId}
					onclick={() => void savePreferences()}
					type="button"
				>
					{#if isSaving}
						<RefreshCw class="h-4 w-4" style="animation: spin 0.8s linear infinite" />
						Saving…
					{:else}
						<Save class="h-4 w-4" />
						Save Preference
					{/if}
				</button>
			</div>
		</section>
	{/if}
</div>

<style>
	.page-container {
		max-width: 1120px;
		margin: 0 auto;
		padding: clamp(1rem, 2vw, 1.5rem) clamp(1.25rem, 3vw, 2.25rem) clamp(2rem, 3vw, 2.75rem);
	}

	.settings-page {
		color: var(--theme-text-primary);
	}

	.settings-header {
		display: flex;
		align-items: stretch;
		justify-content: space-between;
		gap: 1rem;
		padding: clamp(1rem, 2vw, 1.5rem);
	}

	.settings-header-main {
		display: flex;
		align-items: flex-start;
		gap: 1rem;
	}

	.settings-eyebrow {
		margin: 0 0 0.35rem;
		font-size: 0.75rem;
		font-weight: 700;
		letter-spacing: 0.14em;
		text-transform: uppercase;
		color: rgba(var(--theme-primary-rgb), 0.82);
	}

	.settings-title {
		font-size: 1.6rem;
		font-weight: 700;
		margin: 0 0 0.15rem;
		color: var(--theme-text-primary);
	}

	.settings-focus-card {
		min-width: 230px;
		padding: 1rem 1.1rem;
		border-radius: 16px;
		border: 1px solid rgba(var(--theme-primary-rgb), 0.16);
		background: linear-gradient(135deg, rgba(var(--theme-primary-rgb), 0.12), rgba(255, 255, 255, 0.04));
		display: flex;
		flex-direction: column;
		justify-content: center;
		gap: 0.3rem;
	}

	.focus-label {
		font-size: 0.74rem;
		font-weight: 700;
		letter-spacing: 0.12em;
		text-transform: uppercase;
		color: var(--theme-text-secondary);
	}

	.focus-note {
		margin: 0;
		font-size: 0.82rem;
		color: var(--theme-text-secondary);
	}

	.settings-panel {
		padding: clamp(1.25rem, 2vw, 1.6rem);
	}

	.section-head {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		color: var(--theme-primary);
	}

	.section-title {
		font-size: 1.05rem;
		font-weight: 600;
		margin: 0;
		color: var(--theme-text-primary);
	}

	.provider-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
		gap: 0.85rem;
	}

	.provider-card {
		position: relative;
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
		min-height: 180px;
		padding: 1.25rem;
		border-radius: 14px;
		border: 2px solid rgba(255, 255, 255, 0.07);
		background: rgba(255, 255, 255, 0.03);
		cursor: pointer;
		transition: border-color 0.15s ease, background 0.15s ease, transform 0.12s ease;
		text-align: left;
		color: var(--theme-text-primary);
	}

	.provider-card:hover {
		border-color: rgba(var(--theme-primary-rgb), 0.35);
		background: rgba(var(--theme-primary-rgb), 0.06);
		transform: translateY(-1px);
	}

	.provider-card.is-selected {
		border-color: var(--theme-primary);
		background: rgba(var(--theme-primary-rgb), 0.1);
	}

	.selected-badge {
		position: absolute;
		top: 0;
		right: 0;
		background: var(--theme-primary);
		color: #fff;
		border-radius: 0 12px 0 10px;
		padding: 4px 7px;
		display: flex;
		align-items: center;
	}

	.provider-card-icon {
		width: 40px;
		height: 40px;
		border-radius: 10px;
		background: rgba(255, 255, 255, 0.06);
		border: 1px solid rgba(255, 255, 255, 0.1);
		display: flex;
		align-items: center;
		justify-content: center;
		opacity: 0.7;
	}

	.provider-card-body {
		display: flex;
		flex-direction: column;
		gap: 0.2rem;
	}

	.provider-name {
		font-weight: 700;
		font-size: 1rem;
	}

	.provider-model {
		font-size: 0.7rem;
		font-family: monospace;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: rgba(255, 255, 255, 0.45);
	}

	.status-chip {
		display: inline-block;
		margin-top: 0.5rem;
		padding: 2px 8px;
		border-radius: 999px;
		font-size: 0.65rem;
		font-weight: 600;
		background: rgba(52, 211, 153, 0.12);
		color: rgb(110, 231, 183);
		border: 1px solid rgba(52, 211, 153, 0.25);
	}

	.info-banner {
		display: flex;
		align-items: flex-start;
		gap: 0.6rem;
		padding: 0.85rem 1rem;
		border-radius: 10px;
		background: rgba(234, 179, 8, 0.06);
		border: 1px solid rgba(234, 179, 8, 0.15);
		font-size: 0.88rem;
		color: rgba(253, 224, 71, 0.8);
		line-height: 1.5;
	}

	.save-row {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding-top: 0.5rem;
		border-top: 1px solid rgba(255, 255, 255, 0.07);
	}

	.success-msg {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		font-size: 0.9rem;
		font-weight: 500;
		color: rgb(110, 231, 183);
	}

	.save-btn:disabled {
		opacity: 0.45;
		pointer-events: none;
	}

	.error-panel {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.75rem;
	}

	.flex-row {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		color: #fca5a5;
	}

	.center-state {
		display: grid;
		place-items: center;
		gap: 0.5rem;
		padding: 2.5rem 1.5rem;
		text-align: center;
	}

	.large-state { padding: 4rem 1.5rem; }

	.empty-title {
		font-weight: 600;
		font-size: 1.05rem;
		color: var(--theme-text-primary);
		margin: 0;
	}

	.spinner {
		width: 40px;
		height: 40px;
		border-radius: 50%;
		border: 3px solid rgba(255, 255, 255, 0.15);
		border-top-color: rgba(255, 255, 255, 0.75);
		animation: spin 0.8s linear infinite;
	}

	@keyframes spin { to { transform: rotate(360deg); } }

	.back-chip {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 36px;
		height: 36px;
		border-radius: 10px;
		border: 1px solid rgba(255, 255, 255, 0.12);
		background: rgba(255, 255, 255, 0.04);
		color: var(--theme-text-primary);
		text-decoration: none;
		flex-shrink: 0;
		margin-top: 0.3rem;
		transition: background 0.15s ease, border-color 0.15s ease;
	}
	.back-chip:hover {
		background: rgba(255, 255, 255, 0.08);
		border-color: rgba(255, 255, 255, 0.2);
	}

	.muted { color: rgba(255, 255, 255, 0.5); margin: 0; }

	.pill {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		padding: 0.55rem 0.9rem;
		border-radius: 12px;
		font-weight: 600;
		cursor: pointer;
		font-size: 0.9rem;
	}

	.pill.primary {
		background: var(--theme-primary);
		color: #fff;
		border: none;
	}
	.pill.primary:hover:not(:disabled) {
		filter: brightness(1.1);
	}

	.pill.ghost {
		border: 1px solid rgba(255, 255, 255, 0.14);
		background: rgba(255, 255, 255, 0.04);
		color: var(--theme-text-primary);
	}
	.pill.ghost:hover { background: rgba(255, 255, 255, 0.08); }

	.glass-panel {
		background: color-mix(in srgb, var(--theme-nav-glass) 88%, transparent);
		border: 1px solid var(--theme-glass-border);
		border-radius: 18px;
		padding: 22px;
		box-shadow: 0 18px 48px rgba(0, 0, 0, 0.18);
		backdrop-filter: blur(18px);
		-webkit-backdrop-filter: blur(18px);
	}

	.space-y-6 > * + * { margin-top: 1.5rem; }
	.space-y-8 > * + * { margin-top: 2rem; }

	@media (max-width: 760px) {
		.settings-header,
		.save-row,
		.error-panel {
			flex-direction: column;
			align-items: stretch;
		}

		.settings-focus-card {
			min-width: 0;
			width: 100%;
		}

		.save-btn {
			justify-content: center;
		}
	}


</style>
