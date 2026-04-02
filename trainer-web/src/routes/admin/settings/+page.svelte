<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { session } from '$lib/session';
	import { apiFetch } from '$lib/api/client';

	type SettingsTab = 'general' | 'ai';
	type AITab = 'connectors' | 'statistics';
	type StatisticsTab = 'gel' | 'vquest';

	interface ProviderConfig {
		key: string;
		name: string;
		base_url: string;
		enabled: boolean;
		questions_per_batch: number;
		model: string;
		api_key: string;
	}

	interface PasswordResetSettingsResponse {
		method: PasswordResetMethod;
		self_service_enabled: boolean;
		smtp: SMTPSettingsPayload;
		smtp_password_set: boolean;
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
	let activeStatisticsTab = $state<StatisticsTab>('vquest');
	let metricsWindowDays = $state(30);
	let signupEnabled = $state(true);
	let studentSignupEnabled = $state(false);

	let passwordResetMethod = $state<PasswordResetMethod>('security_question');
	let passwordResetSelfServiceEnabled = $state(true);
	let smtpSettings = $state<SMTPSettingsPayload>({ ...DEFAULT_SMTP_SETTINGS });
	let smtpPasswordSet = $state(false);
	let passwordResetLoading = $state(false);
	let passwordResetError = $state('');
	let passwordResetMessage = $state('');
	let passwordResetSaved = $state(false);
	let testEmail = $state('');
	let testEmailLoading = $state(false);

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
				apiFetch<{ signup_enabled: boolean; student_signup_enabled?: boolean }>('/settings/signup'),
				apiFetch<ProviderSettingsResponse>('/settings/providers-generation')
			]);
			signupEnabled = signup.signup_enabled;
			studentSignupEnabled = signup.student_signup_enabled ?? false;
			providers = (providerSettings.providers || []).map((p) => normalizeProvider(p));
			await loadMetrics();
		} catch (e: unknown) {
			pageError = e instanceof Error ? e.message : 'Failed to load admin settings';
		} finally {
			loading = false;
		}
	}

	function applyPasswordResetSettings(value: PasswordResetSettingsResponse) {
		passwordResetMethod = value.method;
		passwordResetSelfServiceEnabled = value.self_service_enabled;
		smtpSettings = {
			...DEFAULT_SMTP_SETTINGS,
			...value.smtp,
			password: ''
		};
		smtpPasswordSet = value.smtp_password_set;
	}

	function pulseSignupSaved() {
		signupSaved = true;
		setTimeout(() => {
			signupSaved = false;
		}, 1800);
	}

	function pulsePasswordResetSaved() {
		passwordResetSaved = true;
		setTimeout(() => {
			passwordResetSaved = false;
		}, 1800);
	}

	async function toggleSignup() {
		signupLoading = true;
		signupError = '';
		signupSaved = false;
		try {
			const usageType = activeStatisticsTab === 'gel' ? 'gel' : 'vquest';
			providerMetrics = await apiFetch<ProviderMetricsResponse>(`/admin/provider-metrics?days=${metricsWindowDays}&usage_type=${usageType}`);
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
				method: passwordResetMethod,
				self_service_enabled: passwordResetSelfServiceEnabled,
				smtp: {
					...smtpSettings,
					host: smtpSettings.host.trim(),
					port: Number(smtpSettings.port) || 587,
					username: smtpSettings.username.trim(),
					password: smtpSettings.password,
					from_email: smtpSettings.from_email.trim(),
					from_name: smtpSettings.from_name.trim() || 'VQuest',
					timeout_seconds: Number(smtpSettings.timeout_seconds) || 20,
					password_reset_url_template: smtpSettings.password_reset_url_template.trim()
				}
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

	async function toggleSignup(type: 'general' | 'student') {
		settingsLoading = true;
		pageError = '';
		settingsSaved = false;
		try {
			const payload =
				type === 'general'
					? { signup_enabled: !signupEnabled }
					: { student_signup_enabled: !studentSignupEnabled };

			const res = await apiFetch<{ signup_enabled: boolean; student_signup_enabled?: boolean }>('/settings/signup', {
				method: 'PUT',
				body: JSON.stringify(payload)
			});
			signupEnabled = res.signup_enabled;
			studentSignupEnabled = res.student_signup_enabled ?? studentSignupEnabled;
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
	{:else}
		<div class="section glass-panel">
			<h2 class="section-title">Access Control</h2>
			{#if signupError}
				<div class="settings-error" role="alert">{signupError}</div>
			{/if}
			<div class="settings-list">
				<div class="setting-item">
					<div class="setting-info">
						<span class="setting-label">User Registration</span>
						<span class="setting-desc">Allow public teacher signup. Vetter signup remains available even when this is off, and vetter accounts are approved automatically.</span>
					</div>
					<div class="setting-control">
						<button
							class="toggle-btn"
							class:enabled={signupEnabled}
							onclick={toggleSignup}
							disabled={signupLoading}
						>
							{#if signupLoading}
								<span class="toggle-spinner"></span>
							{:else}
								<span class="toggle-track">
									<span class="toggle-thumb"></span>
								</span>
								<span class="toggle-label">{signupEnabled ? 'Enabled' : 'Disabled'}</span>
							{/if}
						</button>
						{#if signupSaved}
							<span class="saved-indicator">Saved</span>
						{/if}
					</div>
				</div>
			</div>
		</div>

		<div class="section glass-panel">
			<div class="section-heading">
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
					<h3>Teacher/Vetter Signup</h3>
					<p>Allow teachers and vetters to create their own accounts.</p>
				</div>
				<button class="status-pill" class:active={signupEnabled} onclick={() => toggleSignup('general')} disabled={settingsLoading}>
					{signupEnabled ? 'Enabled' : 'Disabled'}
				</button>
			</div>

			<div class="setting-item">
				<div>
					<h3>Student Self-Signup</h3>
					<p>Allow students to create accounts directly (skips teacher invitation).</p>
				</div>
				<button
					class="status-pill"
					class:active={studentSignupEnabled}
					onclick={() => toggleSignup('student')}
					disabled={settingsLoading}
				>
					{studentSignupEnabled ? 'Enabled' : 'Disabled'}
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
				</div>
			</div>

			{#if passwordResetError}
				<div class="settings-error" role="alert">{passwordResetError}</div>
			{/if}
			{#if passwordResetMessage}
				<div class="settings-success" role="status">{passwordResetMessage}</div>
			{/if}

			<div class="policy-block">
				<div class="method-tabs" role="tablist" aria-label="Password reset access mode">
					<button
						type="button"
						class="method-tab"
						class:selected={passwordResetSelfServiceEnabled}
						role="tab"
						aria-selected={passwordResetSelfServiceEnabled}
						onclick={() => {
							passwordResetSelfServiceEnabled = true;
						}}
					>
						<span class="method-tab-label">Self-Service</span>
						<span class="method-tab-copy">Users finish the reset flow themselves using the method below.</span>
					</button>
					<button
						type="button"
						class="method-tab"
						class:selected={!passwordResetSelfServiceEnabled}
						role="tab"
						aria-selected={!passwordResetSelfServiceEnabled}
						onclick={() => {
							passwordResetSelfServiceEnabled = false;
						}}
					>
						<span class="method-tab-label">Admin Approval</span>
						<span class="method-tab-copy">Users only send a reset alert. Admins set the new password.</span>
					</button>
				</div>
			</div>

			{#if !passwordResetSelfServiceEnabled}
				<div class="settings-note" role="status">
					Public forgot-password requests will only create admin notifications. Users will not receive reset links or security-question access.
				</div>
			{/if}

			{#if passwordResetSelfServiceEnabled}

			<div class="method-tabs" role="tablist" aria-label="Password reset method">
				<button
					type="button"
					id="password-reset-security-tab"
					class="method-tab"
					class:selected={passwordResetMethod === 'security_question'}
					role="tab"
					aria-selected={passwordResetMethod === 'security_question'}
					aria-controls="password-reset-security-panel"
					onclick={() => {
						passwordResetMethod = 'security_question';
					}}
				>
					<span class="method-tab-label">Security Question</span>
					<span class="method-tab-copy">Profile-based recovery</span>
				</button>
				<button
					type="button"
					id="password-reset-smtp-tab"
					class="method-tab"
					class:selected={passwordResetMethod === 'smtp'}
					role="tab"
					aria-selected={passwordResetMethod === 'smtp'}
					aria-controls="password-reset-smtp-panel"
					onclick={() => {
						passwordResetMethod = 'smtp';
					}}
				>
					<span class="method-tab-label">SMTP Email</span>
					<span class="method-tab-copy">Signed email reset links</span>
				</button>
			</div>
			{/if}

			{#if passwordResetMethod === 'security_question'}
				<div>

				</div>
			{:else}
				<div class="method-panel" id="password-reset-smtp-panel" role="tabpanel" aria-labelledby="password-reset-smtp-tab">
					<div class="method-summary">
						<div>
							<span class="method-summary-label">SMTP Email</span>
							<h3>Email-based password recovery</h3>
							<p>
								{passwordResetSelfServiceEnabled
									? 'Users receive a signed reset link by email. SMTP configuration is only shown while this method is selected.'
									: 'This self-service method is configured but currently on standby because admin approval is required.'}
							</p>
						</div>
						<span class="method-badge">{passwordResetSelfServiceEnabled ? 'Active' : 'Standby'}</span>
					</div>
					<div class="metric-controls">
						<select bind:value={metricsWindowDays} class="cell-input window-select" onchange={loadMetrics}>
							<option value={7}>7 days</option>
							<option value={30}>30 days</option>
							<option value={90}>90 days</option>
						</select>
						<button class="secondary-btn" onclick={loadMetrics} disabled={metricsLoading}>
							{metricsLoading ? 'Refreshing...' : 'Refresh'}
						</button>
					</div>
				</div>

				<div class="tabs ai-tabs stats-tabs" role="tablist" aria-label="Statistics type">
					<button class="tab-btn" class:active={activeStatisticsTab === 'vquest'} onclick={() => { activeStatisticsTab = 'vquest'; void loadMetrics(); }}>VQuest</button>
					<button class="tab-btn" class:active={activeStatisticsTab === 'gel'} onclick={() => { activeStatisticsTab = 'gel'; void loadMetrics(); }}>GEL Train</button>
				</div>

				{#if !providerMetrics}
					<div class="center-state">
						<p>No statistics available yet.</p>
					</div>
				{:else}
					<div class="summary-grid">
						<div class="summary-item"><span>Total {activeStatisticsTab === 'gel' ? 'Interactions' : 'Generations'}</span><strong>{activeStatisticsTab === 'gel' ? (providerMetrics.providers.reduce((sum, p) => sum + p.api_calls, 0)) : providerMetrics.total_generated}</strong></div>
						{#if activeStatisticsTab === 'vquest'}
							<div class="summary-item"><span>Total Rejected</span><strong>{providerMetrics.total_rejected}</strong></div>
							<div class="summary-item"><span>Total Regenerated</span><strong>{providerMetrics.total_regenerated}</strong></div>
							<div class="summary-item"><span>Acceptance Rate</span><strong>{providerMetrics.total_generated > 0 ? Math.round(((providerMetrics.total_generated - providerMetrics.total_rejected) / providerMetrics.total_generated) * 100) : 0}%</strong></div>
						{:else}
							<div class="summary-item"><span>Total Sessions</span><strong>{providerMetrics.providers.reduce((sum, p) => sum + p.api_calls, 0)}</strong></div>
							<div class="summary-item"><span>Active Providers</span><strong>{providerMetrics.providers.filter(p => p.api_calls > 0).length}</strong></div>
							<div class="summary-item"><span>Avg Usage</span><strong>{providerMetrics.providers.length > 0 ? Math.round(providerMetrics.providers.reduce((sum, p) => sum + p.api_calls, 0) / providerMetrics.providers.filter(p => p.api_calls > 0).length) : 0}</strong></div>
						{/if}
					</div>

					<div class="table-wrap">
						<table>
							<thead>
								<tr>
									<th>Service</th>
									{#if activeStatisticsTab === 'vquest'}
										<th>Generations</th>
									{/if}
									<th>{activeStatisticsTab === 'gel' ? 'Sessions' : 'Calls'}</th>
									{#if activeStatisticsTab === 'vquest'}
										<th>Avg/Call</th>
										<th>Rejected</th>
										<th>Regenerated</th>
										<th>Preference</th>
									{/if}
								</tr>
							</thead>
							<tbody>
								{#each providerMetrics.providers as metric}
									<tr>
										<td>{metric.provider_key}</td>
										{#if activeStatisticsTab === 'vquest'}
											<td>{metric.total_generated}</td>
										{/if}
										<td>{metric.api_calls}</td>
										{#if activeStatisticsTab === 'vquest'}
											<td>{metric.avg_questions_per_call}</td>
											<td>{metric.total_rejected}</td>
											<td>{metric.total_regenerated}</td>
											<td><span class={`pref-pill ${preferenceClass(metric.inferred_preference)}`}>{metric.inferred_preference}</span></td>
										{/if}
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

	.policy-block {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}

	.settings-note {
		padding: 0.8rem 0.9rem;
		border-radius: 0.8rem;
		background: rgba(58, 170, 255, 0.428);
		border: 1px solid rgba(99, 79, 0, 0.28);
		color: #333333;
		font-size: 0.83rem;
		line-height: 1.45;
	}

	.save-group {
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

	.settings-success {
		background: rgba(15, 118, 110, 0.16);
		border: 0.5px solid rgba(0, 133, 33, 0.528);
		color: #006015;
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

	.stats-tabs {
		margin-bottom: 1.1rem;
		padding: 0.35rem;
		background: color-mix(in srgb, var(--theme-surface) 75%, transparent);
	}

	.stats-tabs .tab-btn {
		font-size: 0.82rem;
		padding: 0.5rem 1rem;
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
