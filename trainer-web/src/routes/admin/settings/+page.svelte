<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { session } from '$lib/session';
	import { apiFetch } from '$lib/api/client';
	import type { PasswordResetMethod } from '$lib/api/auth';
	import { loadCustomThemes, customThemes } from '$lib/theme';
	import { builtInThemeNames } from '$lib/theme/themes';
	import type { ThemeConfig } from '$lib/theme/themes';

	type SettingsTab = 'general' | 'ai' | 'themes';
	type AITab = 'connectors' | 'statistics';
	type SMTPEncryptionMode = 'tls' | 'ssl' | 'none';

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
		total_vetted: number;
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
		total_vetted: number;
		providers: ProviderMetric[];
	}

	interface SMTPSettingsPayload {
		host: string;
		port: number;
		username: string;
		password: string;
		from_email: string;
		from_name: string;
		use_tls: boolean;
		use_ssl: boolean;
		timeout_seconds: number;
		password_reset_url_template: string;
	}

	interface PasswordResetSettingsResponse {
		method: PasswordResetMethod;
		self_service_enabled: boolean;
		smtp: SMTPSettingsPayload;
		smtp_password_set: boolean;
	}

	const DEFAULT_SMTP_SETTINGS: SMTPSettingsPayload = {
		host: '',
		port: 587,
		username: '',
		password: '',
		from_email: '',
		from_name: 'VQuest',
		use_tls: true,
		use_ssl: false,
		timeout_seconds: 20,
		password_reset_url_template: ''
	};

	let loading = $state(true);
	// AI connectors state
	let settingsLoading = $state(false);
	let metricsLoading = $state(false);
	let pageError = $state('');
	let settingsSaved = $state(false);
	let activeSettingsTab = $state<SettingsTab>('general');
	let activeAITab = $state<AITab>('connectors');
	let metricsWindowDays = $state(30);
	// Signup state
	let signupEnabled = $state(true);
	let domainRestrictionEnabled = $state(false);
	let allowedDomains = $state<string[]>([]);
	let newDomain = $state('');
	let signupLoading = $state(false);
	let signupError = $state('');
	let signupSaved = $state(false);
	// Password reset state
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

	let providers = $state<ProviderConfig[]>([]);
	let providerMetrics = $state<ProviderMetricsResponse | null>(null);
	let visibleKeys = $state<Record<string, boolean>>({});

	// Theme customization state
	interface ThemeFormData {
		id?: string;
		name: string;
		label: string;
		icon: string;
		bgImage: string;
		wallpaperOverlay: string;
		bg: string;
		bgColor: string;
		primary: string;
		primaryHover: string;
		accentGradient: string;
		primaryRgb: string;
		text: string;
		textMuted: string;
		textPrimary: string;
		textSecondary: string;
		glassBg: string;
		glassBorder: string;
		navGlass: string;
		border: string;
		glow: string;
		isActive: boolean;
	}

	const DEFAULT_THEME_FORM: ThemeFormData = {
		name: '',
		label: '',
		icon: '🎨',
		bgImage: '',
		wallpaperOverlay:
			'linear-gradient(180deg, rgba(0,0,0,0.1) 0%, rgba(0,0,0,0.05) 50%, rgba(0,0,0,0.15) 100%)',
		bg: 'linear-gradient(175deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%)',
		bgColor: '#1a1a2e',
		primary: '#6366f1',
		primaryHover: '#818cf8',
		accentGradient: '#a855f7',
		primaryRgb: '99, 102, 241',
		text: '#f8fafc',
		textMuted: '#94a3b8',
		textPrimary: '#1e293b',
		textSecondary: 'rgba(0,0,0,0.55)',
		glassBg: 'rgba(255, 255, 255, 0.55)',
		glassBorder: 'rgba(255, 255, 255, 0.7)',
		navGlass: 'rgba(255, 255, 255, 0.5)',
		border: 'rgba(255,255,255,0.14)',
		glow: 'rgba(99,102,241,0.35)',
		isActive: true
	};

	let themes = $state<ThemeConfig[]>([]);
	let themesLoading = $state(false);
	let themesError = $state('');
	let themesSaved = $state(false);
	let editingTheme = $state<ThemeFormData | null>(null);
	let isCreatingTheme = $state(false);

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
				return;
			}
			if (!testEmail && s.user.email) {
				testEmail = s.user.email;
			}
		});
		void loadInitialData();
		return unsub;
	});

	async function loadInitialData() {
		loading = true;
		pageError = '';
		signupError = '';
		passwordResetError = '';
		passwordResetMessage = '';
		try {
			const [signup, providerSettings, passwordResetResponse] = await Promise.all([
				apiFetch<{
					signup_enabled: boolean;
					domain_restriction_enabled: boolean;
					allowed_domains: string[];
				}>('/settings/signup'),
				apiFetch<ProviderSettingsResponse>('/settings/providers-generation'),
				apiFetch<PasswordResetSettingsResponse>('/settings/password-reset/admin')
			]);
			signupEnabled = signup.signup_enabled;
			domainRestrictionEnabled = signup.domain_restriction_enabled ?? false;
			allowedDomains = signup.allowed_domains ?? [];
			providers = (providerSettings.providers || []).map((p) => normalizeProvider(p));
			applyPasswordResetSettings(passwordResetResponse);
			await Promise.all([loadMetrics(), loadThemes()]);
		} catch (e: unknown) {
			pageError = e instanceof Error ? e.message : 'Failed to load admin settings';
		} finally {
			loading = false;
		}
	}

	async function loadMetrics() {
		metricsLoading = true;
		try {
			providerMetrics = await apiFetch<ProviderMetricsResponse>(
				`/admin/provider-metrics?days=${metricsWindowDays}&usage_type=vquest`
			);
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

	function updateProviderField(
		index: number,
		field: keyof ProviderConfig,
		value: string | number | boolean
	) {
		providers = providers.map((provider, i) =>
			i === index ? { ...provider, [field]: value } : provider
		);
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
					key: String(provider.key ?? '')
						.trim()
						.toLowerCase(),
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
		signupLoading = true;
		signupError = '';
		signupSaved = false;
		try {
			const res = await apiFetch<{
				signup_enabled: boolean;
				domain_restriction_enabled: boolean;
				allowed_domains: string[];
			}>('/settings/signup', {
				method: 'PUT',
				body: JSON.stringify({ signup_enabled: !signupEnabled })
			});
			signupEnabled = res.signup_enabled;
			domainRestrictionEnabled = res.domain_restriction_enabled ?? false;
			allowedDomains = res.allowed_domains ?? [];
			signupSaved = true;
			setTimeout(() => (signupSaved = false), 1800);
		} catch (e: unknown) {
			signupError = e instanceof Error ? e.message : 'Failed to update signup settings';
		} finally {
			signupLoading = false;
		}
	}

	async function saveDomainRestriction() {
		signupLoading = true;
		signupError = '';
		signupSaved = false;
		try {
			const res = await apiFetch<{
				signup_enabled: boolean;
				domain_restriction_enabled: boolean;
				allowed_domains: string[];
			}>('/settings/signup', {
				method: 'PUT',
				body: JSON.stringify({
					domain_restriction_enabled: domainRestrictionEnabled,
					allowed_domains: allowedDomains
				})
			});
			signupEnabled = res.signup_enabled;
			domainRestrictionEnabled = res.domain_restriction_enabled ?? false;
			allowedDomains = res.allowed_domains ?? [];
			signupSaved = true;
			setTimeout(() => (signupSaved = false), 1800);
		} catch (e: unknown) {
			signupError = e instanceof Error ? e.message : 'Failed to update domain restriction settings';
		} finally {
			signupLoading = false;
		}
	}

	function addDomain() {
		const domain = newDomain.trim().toLowerCase().replace(/^@/, '');
		if (domain && !allowedDomains.includes(domain)) {
			allowedDomains = [...allowedDomains, domain];
			newDomain = '';
		}
	}

	function removeDomain(domain: string) {
		allowedDomains = allowedDomains.filter((d) => d !== domain);
	}

	// Theme management functions
	async function loadThemes() {
		themesLoading = true;
		themesError = '';
		try {
			const res = await apiFetch<{ themes: ThemeConfig[] }>('/themes/all');
			themes = res.themes || [];
		} catch (e: unknown) {
			themesError = e instanceof Error ? e.message : 'Failed to load themes';
		} finally {
			themesLoading = false;
		}
	}

	function startCreateTheme() {
		editingTheme = { ...DEFAULT_THEME_FORM };
		isCreatingTheme = true;
	}

	function startEditTheme(theme: ThemeConfig) {
		editingTheme = {
			id: (theme as unknown as { id: string }).id,
			name: theme.name,
			label: theme.label,
			icon: theme.icon,
			bgImage: theme.bgImage,
			wallpaperOverlay: theme.wallpaperOverlay,
			bg: theme.bg,
			bgColor: theme.bgColor,
			primary: theme.primary,
			primaryHover: theme.primaryHover,
			accentGradient: theme.accentGradient,
			primaryRgb: theme.primaryRgb,
			text: theme.text,
			textMuted: theme.textMuted,
			textPrimary: theme.textPrimary,
			textSecondary: theme.textSecondary,
			glassBg: theme.glassBg,
			glassBorder: theme.glassBorder,
			navGlass: theme.navGlass,
			border: theme.border,
			glow: theme.glow,
			isActive: (theme as unknown as { isActive: boolean }).isActive ?? true
		};
		isCreatingTheme = false;
	}

	function cancelEditTheme() {
		editingTheme = null;
		isCreatingTheme = false;
	}

	async function saveTheme() {
		if (!editingTheme) return;

		themesLoading = true;
		themesError = '';
		themesSaved = false;

		try {
			if (isCreatingTheme) {
				await apiFetch('/themes', {
					method: 'POST',
					body: JSON.stringify(editingTheme)
				});
			} else if (editingTheme.id) {
				await apiFetch(`/themes/${editingTheme.id}`, {
					method: 'PUT',
					body: JSON.stringify(editingTheme)
				});
			}

			await loadThemes();
			await loadCustomThemes(); // Refresh the global theme store
			editingTheme = null;
			isCreatingTheme = false;
			themesSaved = true;
			setTimeout(() => (themesSaved = false), 1800);
		} catch (e: unknown) {
			themesError = e instanceof Error ? e.message : 'Failed to save theme';
		} finally {
			themesLoading = false;
		}
	}

	async function deleteTheme(themeId: string) {
		if (!confirm('Are you sure you want to delete this theme?')) return;

		themesLoading = true;
		themesError = '';
		try {
			await apiFetch(`/themes/${themeId}`, { method: 'DELETE' });
			await loadThemes();
			await loadCustomThemes();
		} catch (e: unknown) {
			themesError = e instanceof Error ? e.message : 'Failed to delete theme';
		} finally {
			themesLoading = false;
		}
	}

	function applyPasswordResetSettings(value: PasswordResetSettingsResponse) {
		passwordResetMethod = value.method;
		passwordResetSelfServiceEnabled = value.self_service_enabled;
		smtpSettings = { ...DEFAULT_SMTP_SETTINGS, ...value.smtp, password: '' };
		smtpPasswordSet = value.smtp_password_set;
	}

	function getEncryptionMode(): SMTPEncryptionMode {
		if (smtpSettings.use_ssl) return 'ssl';
		if (smtpSettings.use_tls) return 'tls';
		return 'none';
	}

	function setEncryptionMode(mode: SMTPEncryptionMode) {
		smtpSettings = { ...smtpSettings, use_tls: mode === 'tls', use_ssl: mode === 'ssl' };
	}

	async function savePasswordResetSettings() {
		passwordResetLoading = true;
		passwordResetError = '';
		passwordResetMessage = '';
		passwordResetSaved = false;
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
			const response = await apiFetch<PasswordResetSettingsResponse>(
				'/settings/password-reset/admin',
				{
					method: 'PUT',
					body: JSON.stringify(payload)
				}
			);
			applyPasswordResetSettings(response);
			passwordResetMessage = 'Password reset settings saved.';
			passwordResetSaved = true;
			setTimeout(() => (passwordResetSaved = false), 1800);
		} catch (e: unknown) {
			passwordResetError =
				e instanceof Error ? e.message : 'Failed to save password reset settings';
		} finally {
			passwordResetLoading = false;
		}
	}

	async function sendTestEmail() {
		testEmailLoading = true;
		passwordResetError = '';
		passwordResetMessage = '';
		try {
			const response = await apiFetch<{ message: string }>('/settings/password-reset/admin/test', {
				method: 'POST',
				body: JSON.stringify({ email: testEmail.trim() || undefined })
			});
			passwordResetMessage = response.message;
		} catch (e: unknown) {
			passwordResetError = e instanceof Error ? e.message : 'Failed to send test email';
		} finally {
			testEmailLoading = false;
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
		<button
			class="tab-btn"
			class:active={activeSettingsTab === 'general'}
			onclick={() => (activeSettingsTab = 'general')}>General</button
		>
		<button
			class="tab-btn"
			class:active={activeSettingsTab === 'ai'}
			onclick={() => (activeSettingsTab = 'ai')}>AI</button
		>
		<button
			class="tab-btn"
			class:active={activeSettingsTab === 'themes'}
			onclick={() => (activeSettingsTab = 'themes')}>Themes</button
		>
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
		<section class="glass-panel section">
			<h2 class="section-title">Access Control</h2>
			{#if signupError}
				<div class="settings-error" role="alert">{signupError}</div>
			{/if}
			<div class="settings-list">
				<div class="setting-item">
					<div class="setting-info">
						<span class="setting-label">User Registration</span>
						<span class="setting-desc"
							>Allow new users to submit registrations. New accounts still require admin approval
							before the first login.</span
						>
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

				<div class="setting-item domain-restriction-item">
					<div class="setting-info">
						<span class="setting-label">Email Domain Restriction</span>
						<span class="setting-desc"
							>Only allow registrations from specific email domains. When enabled, users must
							register with an email from one of the allowed domains.</span
						>
					</div>
					<div class="setting-control">
						<button
							class="toggle-btn"
							class:enabled={domainRestrictionEnabled}
							onclick={() => {
								domainRestrictionEnabled = !domainRestrictionEnabled;
							}}
							disabled={signupLoading}
						>
							<span class="toggle-track">
								<span class="toggle-thumb"></span>
							</span>
							<span class="toggle-label">{domainRestrictionEnabled ? 'Enabled' : 'Disabled'}</span>
						</button>
					</div>
				</div>

				{#if domainRestrictionEnabled}
					<div class="domain-list-section">
						<div class="domain-input-row">
							<input
								type="text"
								class="cell-input domain-input"
								placeholder="e.g. saveetha.com"
								bind:value={newDomain}
								onkeydown={(e) => {
									if (e.key === 'Enter') {
										e.preventDefault();
										addDomain();
									}
								}}
							/>
							<button class="secondary-btn" onclick={addDomain} disabled={!newDomain.trim()}
								>Add Domain</button
							>
						</div>
						{#if allowedDomains.length > 0}
							<div class="domain-tags">
								{#each allowedDomains as domain}
									<span class="domain-tag">
										@{domain}
										<button
											class="domain-remove"
											onclick={() => removeDomain(domain)}
											title="Remove domain">×</button
										>
									</span>
								{/each}
							</div>
						{:else}
							<p class="domain-empty-msg">
								No domains configured. Add at least one domain to restrict registrations.
							</p>
						{/if}
						<div class="domain-save-row">
							<button class="primary-btn" onclick={saveDomainRestriction} disabled={signupLoading}>
								{signupLoading ? 'Saving...' : 'Save Domain Settings'}
							</button>
						</div>
					</div>
				{/if}
			</div>
		</section>

		<section class="glass-panel section">
			<div class="section-heading">
				<div>
					<h2 class="section-title">Password Reset</h2>
					<p class="section-copy">
						Choose the active reset flow and maintain the SMTP configuration used for email-based
						recovery.
					</p>
				</div>
				<div class="save-group">
					<button
						class="save-btn"
						type="button"
						onclick={savePasswordResetSettings}
						disabled={passwordResetLoading}
					>
						{passwordResetLoading ? 'Saving...' : 'Save Reset Settings'}
					</button>
					{#if passwordResetSaved}
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
						<span class="method-tab-copy"
							>Users finish the reset flow themselves using the method below.</span
						>
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
						<span class="method-tab-copy"
							>Users only send a reset alert. Admins set the new password.</span
						>
					</button>
				</div>
			</div>

			{#if !passwordResetSelfServiceEnabled}
				<div class="settings-note" role="status">
					Public forgot-password requests will only create admin notifications. Users will not
					receive reset links or security-question access.
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
				<div class="settings-note" role="status">
					Users answer their profile security question to verify identity and set a new password.
				</div>
			{:else}
				<div
					class="method-panel"
					id="password-reset-smtp-panel"
					role="tabpanel"
					aria-labelledby="password-reset-smtp-tab"
				>
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
						<span class="method-badge"
							>{passwordResetSelfServiceEnabled ? 'Active' : 'Standby'}</span
						>
					</div>

					<div class="smtp-panel">
						<div class="smtp-header">
							<div>
								<h3>SMTP Configuration</h3>
								<p>
									These values are saved in admin settings and are used for password reset emails
									and test sends.
								</p>
							</div>
							{#if smtpPasswordSet}
								<span class="secret-indicator">SMTP password is already stored</span>
							{/if}
						</div>

						<div class="form-grid">
							<label class="field">
								<span>SMTP host</span>
								<input bind:value={smtpSettings.host} type="text" placeholder="smtp.example.com" />
							</label>
							<label class="field">
								<span>SMTP port</span>
								<input bind:value={smtpSettings.port} type="number" min="1" max="65535" />
							</label>
							<label class="field">
								<span>SMTP username</span>
								<input
									bind:value={smtpSettings.username}
									type="text"
									placeholder="mailer@example.com"
								/>
							</label>
							<label class="field">
								<span>SMTP password</span>
								<input
									bind:value={smtpSettings.password}
									type="password"
									placeholder={smtpPasswordSet
										? 'Leave blank to keep the saved password'
										: 'Enter SMTP password'}
								/>
							</label>
							<label class="field">
								<span>From email</span>
								<input
									bind:value={smtpSettings.from_email}
									type="email"
									placeholder="noreply@vquest.saveetha.com"
								/>
							</label>
							<label class="field">
								<span>From name</span>
								<input bind:value={smtpSettings.from_name} type="text" placeholder="VQuest" />
							</label>
							<label class="field">
								<span>Connection security</span>
								<select
									value={getEncryptionMode()}
									onchange={(event) =>
										setEncryptionMode(
											(event.currentTarget as HTMLSelectElement).value as SMTPEncryptionMode
										)}
								>
									<option value="tls">STARTTLS</option>
									<option value="ssl">SSL/TLS</option>
									<option value="none">No encryption</option>
								</select>
							</label>
							<label class="field">
								<span>Timeout (seconds)</span>
								<input bind:value={smtpSettings.timeout_seconds} type="number" min="1" max="120" />
							</label>
							<label class="field field-span-2">
								<span>Password reset URL template</span>
								<input
									bind:value={smtpSettings.password_reset_url_template}
									type="text"
									placeholder="https://vquest.saveetha.com/reset-password?token=%7Btoken%7D"
								/>
								<small
									>Use <code>{'{token}'}</code> where the signed password reset token should be inserted.</small
								>
							</label>
						</div>

						<div class="test-row">
							<label class="field field-grow">
								<span>Test email target</span>
								<input bind:value={testEmail} type="email" placeholder="admin@example.com" />
							</label>
							<button
								class="secondary-btn"
								type="button"
								onclick={sendTestEmail}
								disabled={testEmailLoading}
							>
								{testEmailLoading ? 'Sending...' : 'Send Test Email'}
							</button>
						</div>
					</div>
				</div>
			{/if}
		</section>
	{:else if activeSettingsTab === 'ai'}
		<section class="glass-panel section">
			<!-- <div class="section-head">
				<div>
					<h2>AI</h2>
					<p>Manage AI connectors and generation statistics.</p>
				</div>
			</div> -->

			<div class="tabs ai-tabs" role="tablist" aria-label="AI tabs">
				<button
					class="tab-btn"
					class:active={activeAITab === 'connectors'}
					onclick={() => (activeAITab = 'connectors')}>Connectors</button
				>
				<button
					class="tab-btn"
					class:active={activeAITab === 'statistics'}
					onclick={() => (activeAITab = 'statistics')}>Statistics</button
				>
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
											oninput={(event) =>
												updateProviderField(
													index,
													'name',
													(event.currentTarget as HTMLInputElement).value
												)}
										/>
										<input
											class="cell-input key-input"
											value={provider.key}
											placeholder="provider_key"
											oninput={(event) =>
												updateProviderField(
													index,
													'key',
													(event.currentTarget as HTMLInputElement).value
												)}
										/>
									</td>
									<td>
										<input
											class="cell-input"
											value={provider.base_url}
											placeholder="https://api.example.com/v1"
											oninput={(event) =>
												updateProviderField(
													index,
													'base_url',
													(event.currentTarget as HTMLInputElement).value
												)}
										/>
									</td>
									<td>
										<input
											class="cell-input"
											value={provider.model}
											placeholder="Model name"
											oninput={(event) =>
												updateProviderField(
													index,
													'model',
													(event.currentTarget as HTMLInputElement).value
												)}
										/>
									</td>
									<td>
										<div class="key-cell">
											<input
												class="cell-input"
												type={visibleKeys[provider.key] ? 'text' : 'password'}
												value={provider.api_key}
												placeholder="Enter API key"
												oninput={(event) =>
													updateProviderField(
														index,
														'api_key',
														(event.currentTarget as HTMLInputElement).value
													)}
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
											oninput={(event) =>
												updateProviderField(
													index,
													'questions_per_batch',
													Number((event.currentTarget as HTMLInputElement).value || '1')
												)}
										/>
									</td>
									<td>
										<button
											class="status-pill"
											class:active={provider.enabled}
											onclick={() => updateProviderField(index, 'enabled', !provider.enabled)}
										>
											{provider.enabled ? 'Active' : 'Inactive'}
										</button>
									</td>
									<td>
										<button
											class="remove-btn"
											onclick={() => removeProvider(index)}
											disabled={providers.length <= 1}>Delete</button
										>
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
						<select
							bind:value={metricsWindowDays}
							class="cell-input window-select"
							onchange={loadMetrics}
						>
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
						<div class="summary-item">
							<span>Total Generations</span><strong>{providerMetrics.total_generated}</strong>
						</div>
						<div class="summary-item">
							<span>Total Rejected</span><strong>{providerMetrics.total_rejected}</strong>
						</div>
						<div class="summary-item">
							<span>Total Regenerated</span><strong>{providerMetrics.total_regenerated}</strong>
						</div>
						<div class="summary-item">
							<span>Acceptance Rate</span><strong
								>{providerMetrics.total_generated > 0
									? Math.round(
											((providerMetrics.total_generated - providerMetrics.total_rejected) /
												providerMetrics.total_generated) *
												100
										)
									: 0}%</strong
							>
						</div>
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
									<th>Vetted</th>
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
										<td>{metric.total_vetted}</td>
									</tr>
								{/each}
							</tbody>
						</table>
					</div>
				{/if}
			{/if}
		</section>
	{:else if activeSettingsTab === 'themes'}
		<section class="glass-panel section">
			<div class="section-heading">
				<div>
					<h2 class="section-title">Theme Customization</h2>
					<p class="section-copy">Create and manage custom themes for the application.</p>
				</div>
				<button class="primary-btn" onclick={startCreateTheme} disabled={themesLoading}>
					Create Theme
				</button>
			</div>

			{#if themesError}
				<div class="settings-error" role="alert">{themesError}</div>
			{/if}

			{#if editingTheme}
				<div class="theme-editor">
					<h3 class="editor-title">{isCreatingTheme ? 'Create New Theme' : 'Edit Theme'}</h3>

					<div class="form-grid theme-form">
						<div class="field">
							<span>Name (slug)</span>
							<input
								type="text"
								bind:value={editingTheme.name}
								placeholder="my-theme"
								disabled={!isCreatingTheme}
								pattern="^[a-z0-9_-]+$"
							/>
							<small>Lowercase, no spaces. Used internally.</small>
						</div>
						<div class="field">
							<span>Label</span>
							<input type="text" bind:value={editingTheme.label} placeholder="My Theme" />
						</div>
						<div class="field">
							<span>Icon</span>
							<input type="text" bind:value={editingTheme.icon} placeholder="🎨" maxlength="10" />
						</div>
						<div class="field">
							<span>Background Image URL</span>
							<input
								type="text"
								bind:value={editingTheme.bgImage}
								placeholder="/theme-pictures/custom.webp"
							/>
						</div>
						<div class="field field-span-2">
							<span>Background Gradient</span>
							<input type="text" bind:value={editingTheme.bg} placeholder="linear-gradient(...)" />
						</div>
						<div class="field">
							<span>Background Color</span>
							<div class="color-input-row">
								<input type="color" bind:value={editingTheme.bgColor} />
								<input type="text" bind:value={editingTheme.bgColor} placeholder="#1a1a2e" />
							</div>
						</div>
						<div class="field">
							<span>Primary Color</span>
							<div class="color-input-row">
								<input type="color" bind:value={editingTheme.primary} />
								<input type="text" bind:value={editingTheme.primary} placeholder="#6366f1" />
							</div>
						</div>
						<div class="field">
							<span>Primary Hover</span>
							<div class="color-input-row">
								<input type="color" bind:value={editingTheme.primaryHover} />
								<input type="text" bind:value={editingTheme.primaryHover} placeholder="#818cf8" />
							</div>
						</div>
						<div class="field">
							<span>Accent Gradient</span>
							<div class="color-input-row">
								<input type="color" bind:value={editingTheme.accentGradient} />
								<input type="text" bind:value={editingTheme.accentGradient} placeholder="#a855f7" />
							</div>
						</div>
						<div class="field">
							<span>Primary RGB</span>
							<input type="text" bind:value={editingTheme.primaryRgb} placeholder="99, 102, 241" />
						</div>
						<div class="field">
							<span>Text Color</span>
							<div class="color-input-row">
								<input type="color" bind:value={editingTheme.text} />
								<input type="text" bind:value={editingTheme.text} placeholder="#f8fafc" />
							</div>
						</div>
						<div class="field">
							<span>Text Muted</span>
							<input type="text" bind:value={editingTheme.textMuted} placeholder="#94a3b8" />
						</div>
						<div class="field">
							<span>Text Primary</span>
							<input type="text" bind:value={editingTheme.textPrimary} placeholder="#1e293b" />
						</div>
						<div class="field">
							<span>Glass Background</span>
							<input
								type="text"
								bind:value={editingTheme.glassBg}
								placeholder="rgba(255, 255, 255, 0.55)"
							/>
						</div>
						<div class="field">
							<span>Glass Border</span>
							<input
								type="text"
								bind:value={editingTheme.glassBorder}
								placeholder="rgba(255, 255, 255, 0.7)"
							/>
						</div>
						<div class="field">
							<span>Glow Color</span>
							<input
								type="text"
								bind:value={editingTheme.glow}
								placeholder="rgba(99,102,241,0.35)"
							/>
						</div>
					</div>

					<div class="editor-actions">
						<button class="secondary-btn" onclick={cancelEditTheme}>Cancel</button>
						<button
							class="primary-btn"
							onclick={saveTheme}
							disabled={themesLoading || !editingTheme.name || !editingTheme.label}
						>
							{themesLoading ? 'Saving...' : 'Save Theme'}
						</button>
						{#if themesSaved}
							<span class="saved-indicator">Saved</span>
						{/if}
					</div>
				</div>
			{:else if themes.length === 0}
				<div class="center-state">
					<p>No custom themes yet. Click "Create Theme" to add one.</p>
				</div>
			{:else}
				<div class="themes-grid">
					{#each themes as theme (theme.name)}
						<div
							class="theme-card"
							style="--card-primary: {theme.primary}; --card-bg: {theme.bgColor};"
						>
							<div class="theme-card-header">
								<span class="theme-icon">{theme.icon}</span>
								<div class="theme-meta">
									<strong>{theme.label}</strong>
									<span class="theme-name">@{theme.name}</span>
								</div>
							</div>
							<div class="theme-colors">
								<span class="color-chip" style="background: {theme.primary};" title="Primary"
								></span>
								<span
									class="color-chip"
									style="background: {theme.primaryHover};"
									title="Primary Hover"
								></span>
								<span class="color-chip" style="background: {theme.accentGradient};" title="Accent"
								></span>
								<span class="color-chip" style="background: {theme.bgColor};" title="Background"
								></span>
							</div>
							<div class="theme-card-actions">
								<button class="tiny-btn" onclick={() => startEditTheme(theme)}>Edit</button>
								<button
									class="tiny-btn danger"
									onclick={() => deleteTheme((theme as unknown as { id: string }).id)}
									>Delete</button
								>
							</div>
						</div>
					{/each}
				</div>
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

	.domain-restriction-item {
		padding-top: 0.75rem;
		border-top: 1px solid var(--theme-glass-border);
	}

	.domain-list-section {
		margin-top: 0.75rem;
		padding: 0.85rem;
		border: 1px solid var(--theme-glass-border);
		border-radius: 0.7rem;
		background: color-mix(in srgb, var(--theme-surface) 50%, transparent);
	}

	.domain-input-row {
		display: flex;
		gap: 0.5rem;
		margin-bottom: 0.75rem;
	}

	.domain-input {
		flex: 1;
		max-width: 280px;
	}

	.domain-tags {
		display: flex;
		flex-wrap: wrap;
		gap: 0.45rem;
		margin-bottom: 0.75rem;
	}

	.domain-tag {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		padding: 0.32rem 0.55rem;
		background: color-mix(in srgb, var(--theme-primary) 18%, transparent);
		border: 1px solid color-mix(in srgb, var(--theme-primary) 35%, var(--theme-glass-border));
		border-radius: 999px;
		font-size: 0.8rem;
		font-weight: 600;
		color: var(--theme-text);
	}

	.domain-remove {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 1.1rem;
		height: 1.1rem;
		border: none;
		background: transparent;
		color: var(--theme-text-muted);
		cursor: pointer;
		font-size: 1rem;
		line-height: 1;
		border-radius: 999px;
		transition:
			background 0.15s,
			color 0.15s;
	}

	.domain-remove:hover {
		background: rgba(239, 68, 68, 0.2);
		color: #f87171;
	}

	.domain-empty-msg {
		margin: 0 0 0.75rem;
		font-size: 0.82rem;
		color: var(--theme-text-muted);
	}

	.domain-save-row {
		display: flex;
		justify-content: flex-end;
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

	/* --- General tab new styles --- */

	.section-title {
		margin: 0 0 0.75rem;
		font-size: 1.1rem;
		font-weight: 700;
	}

	.settings-list {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}

	.setting-info {
		display: flex;
		flex-direction: column;
		gap: 0.18rem;
	}

	.setting-label {
		font-weight: 700;
		font-size: 0.9rem;
	}

	.setting-desc {
		font-size: 0.82rem;
		color: var(--theme-text-muted);
		max-width: 480px;
	}

	.setting-control {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		flex-shrink: 0;
	}

	.toggle-btn {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		border: 1px solid var(--theme-glass-border);
		border-radius: 999px;
		padding: 0.32rem 0.7rem 0.32rem 0.38rem;
		background: var(--theme-input-bg);
		cursor: pointer;
		font-size: 0.78rem;
		font-weight: 700;
		color: var(--theme-text-muted);
		transition:
			border-color 0.15s,
			background 0.15s;
		min-width: 4.8rem;
	}

	.toggle-btn.enabled {
		border-color: rgba(16, 185, 129, 0.4);
		background: rgba(16, 185, 129, 0.1);
		color: #34d399;
	}

	.toggle-track {
		position: relative;
		width: 1.8rem;
		height: 1rem;
		border-radius: 999px;
		background: rgba(148, 163, 184, 0.3);
		transition: background 0.15s;
		flex-shrink: 0;
	}

	.toggle-btn.enabled .toggle-track {
		background: rgba(16, 185, 129, 0.5);
	}

	.toggle-thumb {
		position: absolute;
		top: 0.12rem;
		left: 0.12rem;
		width: 0.76rem;
		height: 0.76rem;
		border-radius: 999px;
		background: #fff;
		transition: transform 0.15s;
	}

	.toggle-btn.enabled .toggle-thumb {
		transform: translateX(0.8rem);
	}

	.toggle-label {
		line-height: 1;
	}

	.toggle-spinner {
		display: inline-block;
		width: 1rem;
		height: 1rem;
		border: 2px solid rgba(255, 255, 255, 0.2);
		border-top-color: var(--theme-primary);
		border-radius: 999px;
		animation: spin 1s linear infinite;
	}

	.section-heading {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		gap: 1rem;
		margin-bottom: 1rem;
	}

	.section-copy {
		margin: 0.2rem 0 0;
		font-size: 0.83rem;
		color: var(--theme-text-muted);
	}

	.save-group {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		flex-shrink: 0;
	}

	.save-btn {
		border-radius: 0.55rem;
		padding: 0.5rem 0.9rem;
		font-size: 0.8rem;
		font-weight: 700;
		border: 1px solid var(--theme-glass-border);
		background: color-mix(in srgb, var(--theme-primary) 22%, transparent);
		color: var(--theme-text);
		cursor: pointer;
	}

	.save-btn:disabled {
		opacity: 0.6;
		cursor: default;
	}

	.settings-success {
		background: rgba(16, 185, 129, 0.12);
		border: 1px solid rgba(16, 185, 129, 0.3);
		color: #34d399;
		border-radius: 0.7rem;
		padding: 0.62rem 0.78rem;
		margin-bottom: 0.75rem;
		font-size: 0.84rem;
	}

	.settings-note {
		background: color-mix(in srgb, var(--theme-primary) 8%, transparent);
		border: 1px solid color-mix(in srgb, var(--theme-primary) 22%, var(--theme-glass-border));
		border-radius: 0.7rem;
		padding: 0.62rem 0.78rem;
		font-size: 0.83rem;
		color: var(--theme-text-muted);
		margin-top: 0.6rem;
	}

	.policy-block {
		margin-bottom: 0.75rem;
	}

	.method-tabs {
		display: flex;
		gap: 0.5rem;
		margin-bottom: 0.6rem;
		flex-wrap: wrap;
	}

	.method-tab {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: 0.18rem;
		flex: 1;
		min-width: 160px;
		padding: 0.65rem 0.85rem;
		border: 1px solid var(--theme-glass-border);
		border-radius: 0.7rem;
		background: var(--theme-input-bg);
		cursor: pointer;
		text-align: left;
		transition:
			border-color 0.15s,
			background 0.15s;
	}

	.method-tab.selected {
		border-color: color-mix(in srgb, var(--theme-primary) 50%, var(--theme-glass-border));
		background: color-mix(in srgb, var(--theme-primary) 12%, transparent);
	}

	.method-tab-label {
		font-weight: 700;
		font-size: 0.85rem;
		color: var(--theme-text);
	}

	.method-tab-copy {
		font-size: 0.75rem;
		color: var(--theme-text-muted);
	}

	.method-panel {
		margin-top: 0.5rem;
	}

	.method-summary {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		gap: 1rem;
		padding: 0.85rem;
		border: 1px solid var(--theme-glass-border);
		border-radius: 0.8rem;
		margin-bottom: 0.85rem;
		background: color-mix(in srgb, var(--theme-surface) 80%, transparent);
	}

	.method-summary h3 {
		margin: 0.18rem 0 0.3rem;
		font-size: 0.95rem;
	}

	.method-summary p {
		margin: 0;
		font-size: 0.82rem;
		color: var(--theme-text-muted);
		max-width: 520px;
	}

	.method-summary-label {
		font-size: 0.72rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		color: var(--theme-primary);
	}

	.method-badge {
		flex-shrink: 0;
		padding: 0.28rem 0.6rem;
		border-radius: 999px;
		font-size: 0.72rem;
		font-weight: 700;
		background: rgba(16, 185, 129, 0.14);
		border: 1px solid rgba(16, 185, 129, 0.32);
		color: #34d399;
	}

	.smtp-panel {
		border: 1px solid var(--theme-glass-border);
		border-radius: 0.8rem;
		padding: 1rem;
		display: flex;
		flex-direction: column;
		gap: 0.9rem;
	}

	.smtp-header {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		gap: 1rem;
	}

	.smtp-header h3 {
		margin: 0 0 0.2rem;
		font-size: 0.95rem;
	}

	.smtp-header p {
		margin: 0;
		font-size: 0.8rem;
		color: var(--theme-text-muted);
	}

	.secret-indicator {
		flex-shrink: 0;
		font-size: 0.75rem;
		color: #f59e0b;
		border: 1px solid rgba(245, 158, 11, 0.3);
		background: rgba(245, 158, 11, 0.1);
		border-radius: 0.5rem;
		padding: 0.25rem 0.55rem;
		font-weight: 600;
	}

	.form-grid {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 0.75rem;
	}

	.field {
		display: flex;
		flex-direction: column;
		gap: 0.3rem;
		font-size: 0.82rem;
	}

	.field span {
		font-weight: 600;
		color: var(--theme-text-muted);
	}

	.field input,
	.field select {
		padding: 0.45rem 0.55rem;
		border-radius: 0.55rem;
		border: 1px solid var(--theme-glass-border);
		background: var(--theme-input-bg);
		color: var(--theme-text);
		outline: none;
		font-size: 0.84rem;
		width: 100%;
		box-sizing: border-box;
	}

	.field small {
		font-size: 0.74rem;
		color: var(--theme-text-muted);
	}

	.field small code {
		background: color-mix(in srgb, var(--theme-primary) 12%, transparent);
		border-radius: 0.25rem;
		padding: 0.05rem 0.28rem;
		font-size: 0.8em;
	}

	.field-span-2 {
		grid-column: span 2;
	}

	.field-grow {
		flex: 1;
	}

	.test-row {
		display: flex;
		align-items: flex-end;
		gap: 0.6rem;
	}

	@media (max-width: 640px) {
		.form-grid {
			grid-template-columns: 1fr;
		}

		.field-span-2 {
			grid-column: span 1;
		}

		.section-heading,
		.smtp-header,
		.method-summary {
			flex-direction: column;
		}

		.test-row {
			flex-direction: column;
			align-items: stretch;
		}
	}

	/* Theme Customization Styles */
	.theme-editor {
		border: 1px solid var(--theme-glass-border);
		border-radius: 0.8rem;
		padding: 1.2rem;
		background: color-mix(in srgb, var(--theme-surface) 50%, transparent);
	}

	.editor-title {
		margin: 0 0 1rem;
		font-size: 1rem;
		font-weight: 700;
	}

	.theme-form {
		margin-bottom: 1rem;
	}

	.color-input-row {
		display: flex;
		gap: 0.5rem;
		align-items: center;
	}

	.color-input-row input[type='color'] {
		width: 2.5rem;
		height: 2.2rem;
		padding: 0.15rem;
		border: 1px solid var(--theme-glass-border);
		border-radius: 0.4rem;
		cursor: pointer;
	}

	.color-input-row input[type='text'] {
		flex: 1;
	}

	.editor-actions {
		display: flex;
		gap: 0.6rem;
		align-items: center;
		justify-content: flex-end;
	}

	.themes-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
		gap: 1rem;
	}

	.theme-card {
		border: 1px solid var(--theme-glass-border);
		border-radius: 0.8rem;
		padding: 1rem;
		background: color-mix(in srgb, var(--card-bg, var(--theme-surface)) 15%, transparent);
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}

	.theme-card-header {
		display: flex;
		align-items: center;
		gap: 0.65rem;
	}

	.theme-icon {
		font-size: 1.5rem;
		line-height: 1;
	}

	.theme-meta {
		display: flex;
		flex-direction: column;
		gap: 0.1rem;
	}

	.theme-meta strong {
		font-size: 0.95rem;
	}

	.theme-name {
		font-size: 0.75rem;
		color: var(--theme-text-muted);
		font-family: monospace;
	}

	.theme-colors {
		display: flex;
		gap: 0.35rem;
	}

	.color-chip {
		width: 1.5rem;
		height: 1.5rem;
		border-radius: 0.35rem;
		border: 1px solid rgba(255, 255, 255, 0.2);
	}

	.theme-card-actions {
		display: flex;
		gap: 0.4rem;
		margin-top: auto;
	}

	.tiny-btn.danger {
		color: #f87171;
	}

	.tiny-btn.danger:hover {
		background: rgba(239, 68, 68, 0.15);
	}
</style>
