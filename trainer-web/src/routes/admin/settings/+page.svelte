<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { session } from '$lib/session';
	import { apiFetch } from '$lib/api/client';

	type SettingsTab = 'general' | 'ai';
	type AITab = 'connectors' | 'statistics';

	interface ProviderConfig {
		key: string;
		name: string;
		base_url: string;
		enabled: boolean;
		questions_per_batch: number;
		model: string;
		api_key: string;
	}

	interface ProviderSettingsResponse {
		generation_batch_size: number;
		providers: ProviderConfig[];
	}

	interface ProviderMetric {
		provider_key: string;
		total_generated: number;
		api_calls: number;
		avg_questions_per_call: number;
		total_rejected: number;
		total_regenerated: number;
		rejection_rate: number;
		regeneration_rate: number;
		inferred_preference: string;
		top_rejection_reasons: string[];
	}

	interface ProviderMetricsResponse {
		window_days: number;
		total_generated: number;
		total_rejected: number;
		total_regenerated: number;
		providers: ProviderMetric[];
	}

	let loading = $state(true);
	let settingsLoading = $state(false);
	let metricsLoading = $state(false);
	let pageError = $state('');
	let settingsSaved = $state(false);
	let activeSettingsTab = $state<SettingsTab>('general');
	let activeAITab = $state<AITab>('connectors');
	let metricsWindowDays = $state(30);
	let signupEnabled = $state(true);

	let providers = $state<ProviderConfig[]>([]);
	let providerMetrics = $state<ProviderMetricsResponse | null>(null);
	let visibleKeys = $state<Record<string, boolean>>({});

	function normalizeProvider(provider: Partial<ProviderConfig> | null | undefined): ProviderConfig {
		return {
			key: String(provider?.key ?? ''),
			name: String(provider?.name ?? provider?.key ?? 'Provider'),
			base_url: String(provider?.base_url ?? ''),
			enabled: provider?.enabled !== false,
			questions_per_batch: Number(provider?.questions_per_batch ?? 10),
			model: String(provider?.model ?? ''),
			api_key: String(provider?.api_key ?? '')
		};
	}

	onMount(() => {
		const unsub = session.subscribe((s) => {
			if (!s || s.user.role !== 'admin') {
				goto('/admin/login');
			}
		});
		void loadInitialData();
		return unsub;
	});

	async function loadInitialData() {
		loading = true;
		pageError = '';
		try {
			const [signup, providerSettings] = await Promise.all([
				apiFetch<{ signup_enabled: boolean }>('/settings/signup'),
				apiFetch<ProviderSettingsResponse>('/settings/providers-generation')
			]);
			signupEnabled = signup.signup_enabled;
			providers = (providerSettings.providers || []).map((p) => normalizeProvider(p));
			await loadMetrics();
		} catch (e: unknown) {
			pageError = e instanceof Error ? e.message : 'Failed to load admin settings';
		} finally {
			loading = false;
		}
	}

	async function loadMetrics() {
		metricsLoading = true;
		try {
			providerMetrics = await apiFetch<ProviderMetricsResponse>(`/admin/provider-metrics?days=${metricsWindowDays}`);
		} catch (e: unknown) {
			pageError = e instanceof Error ? e.message : 'Failed to load provider metrics';
		} finally {
			metricsLoading = false;
		}
	}

	function addProvider() {
		providers = [
			...providers,
			{
				key: `provider_${providers.length + 1}`,
				name: 'New Service',
				base_url: 'https://api.example.com/v1',
				enabled: true,
				questions_per_batch: 10,
				model: '',
				api_key: ''
			}
		];
	}

	function removeProvider(index: number) {
		if (providers.length <= 1) {
			pageError = 'At least one provider must be configured.';
			return;
		}
		providers = providers.filter((_, i) => i !== index);
	}

	function updateProviderField(index: number, field: keyof ProviderConfig, value: string | number | boolean) {
		providers = providers.map((provider, i) => (i === index ? { ...provider, [field]: value } : provider));
	}

	function totalQuestionsPerBatch(): number {
		return providers.filter((p) => p.enabled).reduce((sum, p) => sum + p.questions_per_batch, 0);
	}

	function hasEnabledProvider(): boolean {
		return providers.some((p) => p.enabled);
	}

	function toggleApiKeyVisibility(key: string) {
		visibleKeys = { ...visibleKeys, [key]: !visibleKeys[key] };
	}

	async function saveProviderSettings() {
		settingsLoading = true;
		pageError = '';
		settingsSaved = false;

		if (!hasEnabledProvider()) {
			pageError = 'At least one provider must be enabled.';
			settingsLoading = false;
			return;
		}

		try {
			const payload = {
				providers: providers.map((provider) => ({
					...provider,
					key: String(provider.key ?? '').trim().toLowerCase(),
					name: String(provider.name ?? '').trim(),
					base_url: String(provider.base_url ?? '').trim(),
					model: String(provider.model ?? '').trim(),
					api_key: String(provider.api_key ?? '').trim(),
					questions_per_batch: Number(provider.questions_per_batch || 1)
				}))
			};

			const res = await apiFetch<ProviderSettingsResponse>('/settings/providers-generation', {
				method: 'PUT',
				body: JSON.stringify(payload)
			});
			providers = (res.providers || []).map((p) => normalizeProvider(p));
			settingsSaved = true;
			setTimeout(() => (settingsSaved = false), 1800);
		} catch (e: unknown) {
			pageError = e instanceof Error ? e.message : 'Failed to save provider settings';
		} finally {
			settingsLoading = false;
		}
	}

	async function toggleSignup() {
		settingsLoading = true;
		pageError = '';
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
			pageError = e instanceof Error ? e.message : 'Failed to update signup settings';
		} finally {
			settingsLoading = false;
		}
	}

	function preferenceClass(preference: string): string {
		const value = preference.toLowerCase();
		if (value === 'preferred') return 'pill-preferred';
		if (value === 'avoid') return 'pill-avoid';
		return 'pill-neutral';
	}
</script>

<svelte:head>
	<title>Admin Settings - VQuest Trainer</title>
</svelte:head>

<div class="page">
	<!-- <header class="header">
		<h1>Admin Settings</h1>
		<p>Configure platform access and AI generation connectors.</p>
	</header> -->

	<div class="tabs" role="tablist" aria-label="Settings tabs">
		<button class="tab-btn" class:active={activeSettingsTab === 'general'} onclick={() => (activeSettingsTab = 'general')}>General</button>
		<button class="tab-btn" class:active={activeSettingsTab === 'ai'} onclick={() => (activeSettingsTab = 'ai')}>AI</button>
	</div>

	{#if pageError}
		<div class="settings-error" role="alert">{pageError}</div>
	{/if}

	{#if loading}
		<div class="center-state glass-panel">
			<div class="spinner"></div>
			<p>Loading settings...</p>
		</div>
	{:else if activeSettingsTab === 'general'}
		<section class="glass-panel section access-section">
			<!-- <div class="section-head">
				<div>
					<h2>General</h2>
					<p>Platform-level access controls.</p>
				</div>
				{#if settingsSaved}
					<span class="saved-indicator">Saved</span>
				{/if}
			</div> -->

			<div class="setting-item">
				<div>
					<h3>Signup Access</h3>
					<p>Allow or restrict self-signup for new users.</p>
				</div>
				<button class="status-pill" class:active={signupEnabled} onclick={toggleSignup} disabled={settingsLoading}>
					{signupEnabled ? 'Enabled' : 'Disabled'}
				</button>
			</div>
		</section>
	{:else}
		<section class="glass-panel section">
			<!-- <div class="section-head">
				<div>
					<h2>AI</h2>
					<p>Manage AI connectors and generation statistics.</p>
				</div>
			</div> -->

			<div class="tabs ai-tabs" role="tablist" aria-label="AI tabs">
				<button class="tab-btn" class:active={activeAITab === 'connectors'} onclick={() => (activeAITab = 'connectors')}>Connectors</button>
				<button class="tab-btn" class:active={activeAITab === 'statistics'} onclick={() => (activeAITab = 'statistics')}>Statistics</button>
			</div>

			{#if activeAITab === 'connectors'}
				<div class="section-head ai-subhead">
					<div>
						<h3>AI Service Connectors</h3>
						<p>Manage your AI service integrations and API keys</p>
					</div>
					<button class="primary-btn" onclick={addProvider}>Add Service</button>
				</div>

				<div class="batch-summary">
					<span>Total questions per batch (computed):</span>
					<strong>{totalQuestionsPerBatch()}</strong>
				</div>

				<div class="table-wrap">
					<table>
						<thead>
							<tr>
								<th>Service</th>
								<th>Base URL</th>
								<th>Model</th>
								<th>API Key</th>
								<th>Batch</th>
								<th>Status</th>
								<th>Actions</th>
							</tr>
						</thead>
						<tbody>
							{#each providers as provider, index}
								<tr>
									<td>
										<input
											class="cell-input service-input"
											value={provider.name}
											oninput={(event) => updateProviderField(index, 'name', (event.currentTarget as HTMLInputElement).value)}
										/>
										<input
											class="cell-input key-input"
											value={provider.key}
											placeholder="provider_key"
											oninput={(event) => updateProviderField(index, 'key', (event.currentTarget as HTMLInputElement).value)}
										/>
									</td>
									<td>
										<input
											class="cell-input"
											value={provider.base_url}
											placeholder="https://api.example.com/v1"
											oninput={(event) => updateProviderField(index, 'base_url', (event.currentTarget as HTMLInputElement).value)}
										/>
									</td>
									<td>
										<input
											class="cell-input"
											value={provider.model}
											placeholder="Model name"
											oninput={(event) => updateProviderField(index, 'model', (event.currentTarget as HTMLInputElement).value)}
										/>
									</td>
									<td>
										<div class="key-cell">
											<input
												class="cell-input"
												type={visibleKeys[provider.key] ? 'text' : 'password'}
												value={provider.api_key}
												placeholder="Enter API key"
												oninput={(event) => updateProviderField(index, 'api_key', (event.currentTarget as HTMLInputElement).value)}
											/>
											<button class="tiny-btn" onclick={() => toggleApiKeyVisibility(provider.key)}>
												{visibleKeys[provider.key] ? 'Hide' : 'Show'}
											</button>
										</div>
									</td>
									<td>
										<input
											type="number"
											min="1"
											max="1000"
											class="cell-input"
											value={provider.questions_per_batch}
											oninput={(event) => updateProviderField(index, 'questions_per_batch', Number((event.currentTarget as HTMLInputElement).value || '1'))}
										/>
									</td>
									<td>
										<button class="status-pill" class:active={provider.enabled} onclick={() => updateProviderField(index, 'enabled', !provider.enabled)}>
											{provider.enabled ? 'Active' : 'Inactive'}
										</button>
									</td>
									<td>
										<button class="remove-btn" onclick={() => removeProvider(index)} disabled={providers.length <= 1}>Delete</button>
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>

				<div class="actions-row">
					{#if settingsSaved}
						<span class="saved-indicator">Saved</span>
					{/if}
					<button class="primary-btn" onclick={saveProviderSettings} disabled={settingsLoading}>
						{settingsLoading ? 'Saving...' : 'Save Connectors'}
					</button>
				</div>
			{:else}
				<div class="section-head ai-subhead">
					<div>
						<h3>Usage Statistics</h3>
						<p>Overview of AI generation performance and vetting outcomes</p>
					</div>
					<div class="metric-controls">
						<select bind:value={metricsWindowDays} class="cell-input window-select">
							<option value={7}>7 days</option>
							<option value={30}>30 days</option>
							<option value={90}>90 days</option>
						</select>
						<button class="secondary-btn" onclick={loadMetrics} disabled={metricsLoading}>
							{metricsLoading ? 'Refreshing...' : 'Refresh'}
						</button>
					</div>
				</div>

				{#if !providerMetrics}
					<div class="center-state">
						<p>No statistics available yet.</p>
					</div>
				{:else}
					<div class="summary-grid">
						<div class="summary-item"><span>Total Generations</span><strong>{providerMetrics.total_generated}</strong></div>
						<div class="summary-item"><span>Total Rejected</span><strong>{providerMetrics.total_rejected}</strong></div>
						<div class="summary-item"><span>Total Regenerated</span><strong>{providerMetrics.total_regenerated}</strong></div>
						<div class="summary-item"><span>Acceptance Rate</span><strong>{providerMetrics.total_generated > 0 ? Math.round(((providerMetrics.total_generated - providerMetrics.total_rejected) / providerMetrics.total_generated) * 100) : 0}%</strong></div>
					</div>

					<div class="table-wrap">
						<table>
							<thead>
								<tr>
									<th>Service</th>
									<th>Generations</th>
									<th>Calls</th>
									<th>Avg/Call</th>
									<th>Rejected</th>
									<th>Regenerated</th>
									<th>Preference</th>
								</tr>
							</thead>
							<tbody>
								{#each providerMetrics.providers as metric}
									<tr>
										<td>{metric.provider_key}</td>
										<td>{metric.total_generated}</td>
										<td>{metric.api_calls}</td>
										<td>{metric.avg_questions_per_call}</td>
										<td>{metric.total_rejected}</td>
										<td>{metric.total_regenerated}</td>
										<td><span class={`pref-pill ${preferenceClass(metric.inferred_preference)}`}>{metric.inferred_preference}</span></td>
									</tr>
								{/each}
							</tbody>
						</table>
					</div>
				{/if}
			{/if}
		</section>
	{/if}
</div>

<style>
	.page {
		max-width: 1220px;
		margin: 0 auto;
		padding: 1.4rem 1.1rem 2.4rem;
		display: grid;
		gap: 1rem;
	}

	/* .header h1 {
		margin: 0;
		font-size: 2rem;
		font-weight: 800;
		color: var(--theme-text);
	}

	.header p {
		margin: 0.3rem 0 0;
		color: var(--theme-text-muted);
	} */

	.tabs {
		display: inline-flex;
		gap: 0.35rem;
		padding: 0.35rem;
		border: 1px solid var(--theme-glass-border);
		border-radius: 0.75rem;
		background: color-mix(in srgb, var(--theme-surface) 86%, transparent);
		width: fit-content;
	}

	.ai-tabs {
		margin-bottom: 0.9rem;
	}

	.tab-btn {
		border: 1px solid transparent;
		border-radius: 0.55rem;
		padding: 0.5rem 0.9rem;
		background: transparent;
		font-weight: 700;
		color: var(--theme-text-muted);
		cursor: pointer;
	}

	.tab-btn.active {
		background: color-mix(in srgb, var(--theme-primary) 18%, transparent);
		border-color: color-mix(in srgb, var(--theme-primary) 35%, var(--theme-glass-border));
		color: var(--theme-text);
	}

	.section {
		padding: 1rem;
		border-radius: 0.95rem;
	}

	.section-head {
		display: flex;
		justify-content: space-between;
		gap: 1rem;
		align-items: center;
		margin-bottom: 0.8rem;
	}

	.ai-subhead {
		margin-bottom: 0.6rem;
	}

	/* .section-head h2 {
		margin: 0;
		font-size: 1.5rem;
	} */

	.section-head p {
		margin: 0.15rem 0 0;
		color: var(--theme-text-muted);
	}

	.batch-summary {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.55rem 0.7rem;
		border-radius: 0.65rem;
		margin-bottom: 0.75rem;
		background: color-mix(in srgb, var(--theme-primary) 10%, transparent);
		border: 1px solid color-mix(in srgb, var(--theme-primary) 28%, var(--theme-glass-border));
	}

	.batch-summary span {
		color: var(--theme-text-muted);
		font-size: 0.84rem;
	}

	.batch-summary strong {
		color: var(--theme-primary);
	}

	.table-wrap {
		overflow-x: auto;
		border: 1px solid var(--theme-glass-border);
		border-radius: 0.75rem;
	}

	table {
		width: 100%;
		border-collapse: collapse;
		min-width: 980px;
	}

	th,
	td {
		text-align: left;
		padding: 0.65rem;
		border-bottom: 1px solid var(--theme-glass-border);
		vertical-align: middle;
		color: var(--theme-text);
	}

	th {
		font-size: 0.78rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.02em;
		color: var(--theme-text-muted);
	}

	tr:last-child td {
		border-bottom: none;
	}

	.cell-input {
		width: 100%;
		padding: 0.45rem 0.55rem;
		border-radius: 0.55rem;
		border: 1px solid var(--theme-glass-border);
		background: var(--theme-input-bg);
		color: var(--theme-text);
		outline: none;
	}

	.service-input {
		margin-bottom: 0.35rem;
	}

	.key-input {
		font-size: 0.78rem;
	}

	.key-cell {
		display: flex;
		gap: 0.35rem;
	}

	.tiny-btn,
	.remove-btn,
	.secondary-btn,
	.primary-btn {
		border-radius: 0.55rem;
		padding: 0.45rem 0.68rem;
		font-size: 0.76rem;
		font-weight: 700;
		border: 1px solid var(--theme-glass-border);
		cursor: pointer;
	}

	.tiny-btn,
	.remove-btn,
	.secondary-btn {
		background: var(--theme-input-bg);
		color: var(--theme-text-muted);
	}

	.primary-btn {
		background: color-mix(in srgb, var(--theme-primary) 22%, transparent);
		color: var(--theme-text);
	}

	.status-pill {
		border: 1px solid var(--theme-glass-border);
		border-radius: 999px;
		padding: 0.3rem 0.62rem;
		font-size: 0.74rem;
		font-weight: 700;
		background: var(--theme-input-bg);
		color: var(--theme-text-muted);
		cursor: pointer;
	}

	.status-pill.active {
		background: rgba(16, 185, 129, 0.18);
		border-color: rgba(16, 185, 129, 0.4);
		color: #34d399;
	}

	.actions-row {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-top: 0.8rem;
	}

	.saved-indicator {
		color: #10b981;
		font-weight: 700;
		font-size: 0.8rem;
	}

	.setting-item {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 1rem;
	}

	.setting-item h3 {
		margin: 0 0 0.2rem;
	}

	.setting-item p {
		margin: 0;
		color: var(--theme-text-muted);
	}

	.metric-controls {
		display: flex;
		align-items: center;
		gap: 0.4rem;
	}

	.window-select {
		max-width: 100px;
	}

	.summary-grid {
		display: grid;
		grid-template-columns: repeat(4, minmax(0, 1fr));
		gap: 0.65rem;
		margin-bottom: 0.8rem;
	}

	.summary-item {
		border: 1px solid var(--theme-glass-border);
		border-radius: 0.7rem;
		padding: 0.65rem;
		display: flex;
		flex-direction: column;
		gap: 0.24rem;
		background: color-mix(in srgb, var(--theme-surface) 90%, transparent);
	}

	.summary-item span {
		font-size: 0.78rem;
		color: var(--theme-text-muted);
	}

	.summary-item strong {
		font-size: 1.15rem;
	}

	.pref-pill {
		display: inline-flex;
		align-items: center;
		padding: 0.2rem 0.45rem;
		border-radius: 999px;
		font-size: 0.68rem;
		font-weight: 700;
		text-transform: uppercase;
	}

	.pill-preferred {
		background: rgba(16, 185, 129, 0.18);
		color: #34d399;
	}

	.pill-neutral {
		background: rgba(245, 158, 11, 0.16);
		color: #f59e0b;
	}

	.pill-avoid {
		background: rgba(239, 68, 68, 0.16);
		color: #f87171;
	}

	.settings-error {
		background: rgba(220, 38, 38, 0.14);
		border: 1px solid rgba(220, 38, 38, 0.28);
		color: #f87171;
		border-radius: 0.7rem;
		padding: 0.62rem 0.78rem;
	}

	.center-state {
		padding: 1.5rem;
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 0.6rem;
		border-radius: 0.9rem;
		color: var(--theme-text-muted);
	}

	.spinner {
		width: 1.35rem;
		height: 1.35rem;
		border: 2px solid rgba(255, 255, 255, 0.2);
		border-top-color: var(--theme-primary);
		border-radius: 999px;
		animation: spin 1s linear infinite;
	}

	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}

	@media (max-width: 900px) {
		.summary-grid {
			grid-template-columns: repeat(2, minmax(0, 1fr));
		}

		.section-head,
		.setting-item {
			flex-direction: column;
			align-items: flex-start;
		}
	}

	@media (max-width: 640px) {
		.page {
			padding: 1.1rem 0.85rem 1.8rem;
		}

		.summary-grid {
			grid-template-columns: 1fr;
		}

		.tabs {
			display: flex;
			width: 100%;
		}
	}

	:global([data-color-mode='light']) .tabs,
	:global([data-color-mode='light']) .glass-panel,
	:global([data-color-mode='light']) .summary-item,
	:global([data-color-mode='light']) .table-wrap {
		background: #ffffff;
		border-color: rgba(148, 163, 184, 0.32);
		box-shadow: 0 10px 26px rgba(15, 23, 42, 0.08);
	}
</style>
