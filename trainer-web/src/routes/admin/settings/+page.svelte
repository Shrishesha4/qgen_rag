<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { session } from '$lib/session';
	import { apiFetch } from '$lib/api/client';
	import type { PasswordResetMethod } from '$lib/api/auth';

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
		smtp: SMTPSettingsPayload;
		smtp_password_set: boolean;
	}

	type SMTPEncryptionMode = 'tls' | 'ssl' | 'none';

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
	let signupEnabled = $state(true);
	let signupLoading = $state(false);
	let signupError = $state('');
	let signupSaved = $state(false);

	let passwordResetMethod = $state<PasswordResetMethod>('security_question');
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
				return;
			}
			if (!testEmail && s.user.email) {
				testEmail = s.user.email;
			}
		});
		void loadSettings();
		return unsub;
	});

	async function loadSettings() {
		loading = true;
		signupError = '';
		passwordResetError = '';
		passwordResetMessage = '';
		try {
			const [signupResponse, passwordResetResponse] = await Promise.all([
				apiFetch<{ signup_enabled: boolean }>('/settings/signup'),
				apiFetch<PasswordResetSettingsResponse>('/settings/password-reset/admin')
			]);
			signupEnabled = signupResponse.signup_enabled;
			applyPasswordResetSettings(passwordResetResponse);
		} catch (e: unknown) {
			const message = e instanceof Error ? e.message : 'Failed to load settings';
			signupError = message;
			passwordResetError = message;
		} finally {
			loading = false;
		}
	}

	function applyPasswordResetSettings(value: PasswordResetSettingsResponse) {
		passwordResetMethod = value.method;
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
			const res = await apiFetch<{ signup_enabled: boolean }>('/settings/signup', {
				method: 'PUT',
				body: JSON.stringify({ signup_enabled: !signupEnabled })
			});
			signupEnabled = res.signup_enabled;
			pulseSignupSaved();
		} catch (e: unknown) {
			signupError = e instanceof Error ? e.message : 'Failed to update signup setting';
		} finally {
			signupLoading = false;
		}
	}

	function getEncryptionMode(): SMTPEncryptionMode {
		if (smtpSettings.use_ssl) return 'ssl';
		if (smtpSettings.use_tls) return 'tls';
		return 'none';
	}

	function setEncryptionMode(mode: SMTPEncryptionMode) {
		smtpSettings = {
			...smtpSettings,
			use_tls: mode === 'tls',
			use_ssl: mode === 'ssl'
		};
	}

	async function savePasswordResetSettings() {
		passwordResetLoading = true;
		passwordResetError = '';
		passwordResetMessage = '';
		passwordResetSaved = false;
		try {
			const payload = {
				method: passwordResetMethod,
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

			const response = await apiFetch<PasswordResetSettingsResponse>('/settings/password-reset/admin', {
				method: 'PUT',
				body: JSON.stringify(payload)
			});
			applyPasswordResetSettings(response);
			passwordResetMessage = 'Password reset settings saved.';
			pulsePasswordResetSaved();
		} catch (e: unknown) {
			passwordResetError = e instanceof Error ? e.message : 'Failed to save password reset settings';
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
</script>

<svelte:head>
	<title>Admin Settings — VQuest Trainer</title>
</svelte:head>

<div class="page">
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
						<span class="setting-desc">Allow new users to create accounts. When disabled, only existing users can log in.</span>
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
					<h2 class="section-title">Password Reset</h2>
					<p class="section-copy">Choose the active reset flow and maintain the SMTP configuration used for email-based recovery.</p>
				</div>
				<div class="save-group">
					<button class="save-btn" type="button" onclick={savePasswordResetSettings} disabled={passwordResetLoading}>
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

			{#if passwordResetMethod === 'security_question'}
				<div class="method-panel" id="password-reset-security-panel" role="tabpanel" aria-labelledby="password-reset-security-tab">
					<div class="method-summary">
						<div>
							<span class="method-summary-label">Security Question</span>
							<h3>Profile-based password recovery</h3>
							<p>Users reset their password by answering the question saved on their profile. No SMTP fields are needed for this mode.</p>
						</div>
						<span class="method-badge">Active</span>
					</div>
				</div>
			{:else}
				<div class="method-panel" id="password-reset-smtp-panel" role="tabpanel" aria-labelledby="password-reset-smtp-tab">
					<div class="method-summary">
						<div>
							<span class="method-summary-label">SMTP Email</span>
							<h3>Email-based password recovery</h3>
							<p>Users receive a signed reset link by email. SMTP configuration is only shown while this method is selected.</p>
						</div>
						<span class="method-badge">Active</span>
					</div>

					<div class="smtp-panel">
						<div class="smtp-header">
							<div>
								<h3>SMTP Configuration</h3>
								<p>These values are saved in admin settings and are used for password reset emails and test sends.</p>
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
								<input bind:value={smtpSettings.username} type="text" placeholder="mailer@example.com" />
							</label>
							<label class="field">
								<span>SMTP password</span>
								<input bind:value={smtpSettings.password} type="password" placeholder={smtpPasswordSet ? 'Leave blank to keep the saved password' : 'Enter SMTP password'} />
							</label>
							<label class="field">
								<span>From email</span>
								<input bind:value={smtpSettings.from_email} type="email" placeholder="noreply@vquest.saveetha.com" />
							</label>
							<label class="field">
								<span>From name</span>
								<input bind:value={smtpSettings.from_name} type="text" placeholder="VQuest" />
							</label>
							<label class="field">
								<span>Connection security</span>
								<select value={getEncryptionMode()} onchange={(event) => setEncryptionMode((event.currentTarget as HTMLSelectElement).value as SMTPEncryptionMode)}>
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
								<input bind:value={smtpSettings.password_reset_url_template} type="text" placeholder="https://vquest.saveetha.com/reset-password?token=%7Btoken%7D" />
								<small>Use <code>{'{token}'}</code> where the signed password reset token should be inserted.</small>
							</label>
						</div>

						<div class="test-row">
							<label class="field field-grow">
								<span>Test email target</span>
								<input bind:value={testEmail} type="email" placeholder="admin@example.com" />
							</label>
							<button class="secondary-btn" type="button" onclick={sendTestEmail} disabled={testEmailLoading}>
								{testEmailLoading ? 'Sending...' : 'Send Test Email'}
							</button>
						</div>
					</div>
				</div>
			{/if}
		</div>
	{/if}
</div>

<style>
	.page {
		max-width: 1040px;
		margin: 0 auto;
		padding: 2rem 1.25rem 2.4rem;
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}

	.section {
		padding: 1.2rem;
		border-radius: 1rem;
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}

	.section-heading {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		gap: 1rem;
	}

	.section-title {
		margin: 0;
		font-size: 1.08rem;
		font-weight: 700;
		color: var(--theme-text);
	}

	.section-copy {
		margin: 0.4rem 0 0;
		font-size: 0.84rem;
		color: var(--theme-text-muted);
		line-height: 1.45;
	}

	.save-group {
		display: flex;
		align-items: center;
		gap: 0.75rem;
	}

	.settings-error,
	.settings-success {
		border-radius: 0.75rem;
		padding: 0.65rem 0.85rem;
		font-size: 0.85rem;
	}

	.settings-error {
		background: rgba(220, 38, 38, 0.15);
		border: 0.5px solid rgba(220, 38, 38, 0.3);
		color: #f87171;
	}

	.settings-success {
		background: rgba(15, 118, 110, 0.16);
		border: 0.5px solid rgba(15, 118, 110, 0.35);
		color: #99f6e4;
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

	.toggle-btn:hover:not(:disabled),
	.save-btn:hover:not(:disabled),
	.secondary-btn:hover:not(:disabled),
	.method-tab:hover {
		filter: brightness(1.06);
	}

	.toggle-btn:disabled,
	.save-btn:disabled,
	.secondary-btn:disabled {
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

	.toggle-spinner,
	.spinner {
		border-radius: 50%;
		border: 2px solid rgba(255, 255, 255, 0.2);
		border-top-color: var(--theme-primary);
		animation: spin 0.8s linear infinite;
	}

	.toggle-spinner {
		width: 1rem;
		height: 1rem;
	}

	.spinner {
		width: 1.6rem;
		height: 1.6rem;
	}

	.saved-indicator {
		font-size: 0.78rem;
		font-weight: 700;
		color: #10b981;
	}

	.save-btn,
	.secondary-btn {
		padding: 0.7rem 1rem;
		border-radius: 0.8rem;
		border: 1px solid var(--theme-glass-border);
		font: inherit;
		font-weight: 700;
		cursor: pointer;
	}

	.save-btn {
		background: linear-gradient(180deg, color-mix(in srgb, var(--theme-primary) 85%, #ffffff 15%) 0%, var(--theme-primary) 100%);
		color: #061219;
		border-color: color-mix(in srgb, var(--theme-primary) 45%, var(--theme-glass-border));
	}

	.secondary-btn {
		background: var(--theme-input-bg);
		color: var(--theme-text);
	}

	.method-tabs {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 0.65rem;
		padding: 0.4rem;
		border-radius: 1rem;
		border: 1px solid var(--theme-glass-border);
		background: color-mix(in srgb, var(--theme-surface) 82%, transparent);
	}

	.method-tab {
		padding: 0.9rem 1rem;
		border-radius: 0.8rem;
		border: 1px solid transparent;
		background: transparent;
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: 0.22rem;
		text-align: left;
		cursor: pointer;
		font: inherit;
		transition: background 0.2s ease, border-color 0.2s ease, transform 0.2s ease;
	}

	.method-tab.selected {
		border-color: color-mix(in srgb, var(--theme-primary) 52%, var(--theme-glass-border));
		background: color-mix(in srgb, var(--theme-primary) 12%, var(--theme-input-bg));
	}

	.method-tab-label {
		font-size: 0.95rem;
		font-weight: 700;
		color: var(--theme-text);
	}

	.method-tab-copy {
		font-size: 0.78rem;
		line-height: 1.45;
		color: var(--theme-text-muted);
	}

	.method-panel {
		padding: 1rem;
		border-radius: 1rem;
		border: 1px solid var(--theme-glass-border);
		background: color-mix(in srgb, var(--theme-surface) 88%, transparent);
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}

	.method-summary {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		gap: 1rem;
	}

	.method-summary-label {
		display: inline-block;
		font-size: 0.74rem;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		color: var(--theme-text-muted);
		margin-bottom: 0.35rem;
	}

	.method-summary h3 {
		margin: 0;
		font-size: 1rem;
		color: var(--theme-text);
	}

	.method-summary p {
		margin: 0.4rem 0 0;
		font-size: 0.84rem;
		line-height: 1.5;
		color: var(--theme-text-muted);
	}

	.method-badge {
		padding: 0.45rem 0.7rem;
		border-radius: 999px;
		background: color-mix(in srgb, var(--theme-primary) 12%, var(--theme-input-bg));
		border: 1px solid color-mix(in srgb, var(--theme-primary) 38%, var(--theme-glass-border));
		font-size: 0.78rem;
		font-weight: 700;
		color: var(--theme-text);
	}

	.smtp-panel {
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}

	.smtp-header {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		gap: 1rem;
	}

	.smtp-header h3 {
		margin: 0;
		font-size: 0.98rem;
		color: var(--theme-text);
	}

	.smtp-header p {
		margin: 0.35rem 0 0;
		font-size: 0.82rem;
		line-height: 1.45;
		color: var(--theme-text-muted);
	}

	.secret-indicator {
		padding: 0.45rem 0.7rem;
		border-radius: 999px;
		background: rgba(250, 204, 21, 0.12);
		border: 1px solid rgba(250, 204, 21, 0.28);
		color: #fcd34d;
		font-size: 0.78rem;
		font-weight: 700;
	}

	.form-grid {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 0.9rem;
	}

	.field {
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
	}

	.field span {
		font-size: 0.78rem;
		font-weight: 600;
		color: var(--theme-text-muted);
	}

	.field input,
	.field select {
		width: 100%;
		padding: 0.72rem 0.9rem;
		border-radius: 0.75rem;
		border: 1px solid var(--theme-glass-border);
		background: var(--theme-input-bg);
		color: var(--theme-text);
		font: inherit;
	}

	.field input:focus,
	.field select:focus {
		outline: none;
		border-color: rgba(var(--theme-primary-rgb), 0.5);
		box-shadow: 0 0 0 3px rgba(var(--theme-primary-rgb), 0.15);
	}

	.field small {
		font-size: 0.76rem;
		color: var(--theme-text-muted);
		line-height: 1.4;
	}

	.field-span-2 {
		grid-column: span 2;
	}

	.test-row {
		display: flex;
		align-items: flex-end;
		gap: 0.85rem;
	}

	.field-grow {
		flex: 1;
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

	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}

	@media (max-width: 780px) {
		.page {
			padding: 1.3rem 0.95rem 1.9rem;
		}

		.section-heading,
		.setting-item,
		.smtp-header,
		.test-row {
			flex-direction: column;
			align-items: flex-start;
		}

		.method-tabs,
		.form-grid {
			grid-template-columns: 1fr;
		}

		.method-summary {
			flex-direction: column;
		}

		.field-span-2 {
			grid-column: span 1;
		}

		.save-group,
		.setting-control {
			width: 100%;
			justify-content: flex-start;
		}

		.secondary-btn,
		.save-btn {
			width: 100%;
		}
	}

	:global([data-color-mode='light']) .section,
	:global([data-color-mode='light']) .setting-item,
	:global([data-color-mode='light']) .center-state,
	:global([data-color-mode='light']) .method-tabs,
	:global([data-color-mode='light']) .method-panel,
	:global([data-color-mode='light']) .smtp-panel {
		background: #ffffff;
		border-color: rgba(148, 163, 184, 0.32);
		box-shadow: 0 12px 32px rgba(15, 23, 42, 0.08);
	}

	:global([data-color-mode='light']) .field input,
	:global([data-color-mode='light']) .field select,
	:global([data-color-mode='light']) .toggle-btn,
	:global([data-color-mode='light']) .secondary-btn {
		background: #f8fafc;
		border-color: rgba(148, 163, 184, 0.36);
		color: #334155;
	}

	:global([data-color-mode='light']) .save-btn {
		color: #052232;
	}
</style>
