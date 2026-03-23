<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { changePassword, logout, updateProfile } from '$lib/api/auth';
	import { currentUser, session } from '$lib/session';

	let initialized = false;
	let fullName = '';
	let username = '';
	let profileLoading = false;
	let profileMessage = '';
	let profileError = '';

	let currentPassword = '';
	let newPassword = '';
	let confirmPassword = '';
	let passwordLoading = false;
	let passwordMessage = '';
	let passwordError = '';

	onMount(() => {
		const unsub = session.subscribe((s) => {
			if (!s || s.user.role !== 'admin') {
				goto('/admin/login');
			}
		});
		return unsub;
	});

	$: if ($currentUser && !initialized) {
		fullName = $currentUser.full_name || '';
		username = $currentUser.username || '';
		initialized = true;
	}

	function getInitials(name?: string | null, usernameValue?: string | null) {
		const source = (name || usernameValue || 'Admin').trim();
		const parts = source.split(/\s+/).filter(Boolean);
		if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
		return parts
			.slice(0, 2)
			.map((part) => part[0])
			.join('')
			.toUpperCase();
	}

	async function handleLogout() {
		await logout();
		session.clear();
		goto('/');
	}

	async function handleProfileUpdate() {
		profileError = '';
		profileMessage = '';

		const normalizedUsername = username.trim();
		const normalizedFullName = fullName.trim();

		if (!normalizedUsername) {
			profileError = 'Username is required.';
			return;
		}
		if (!/^[a-zA-Z0-9_]+$/.test(normalizedUsername)) {
			profileError = 'Username can only contain letters, numbers, and underscores.';
			return;
		}
		if (normalizedUsername.length < 3) {
			profileError = 'Username must be at least 3 characters.';
			return;
		}

		profileLoading = true;
		try {
			const updated = await updateProfile({
				username: normalizedUsername,
				full_name: normalizedFullName || undefined
			});
			session.refresh();
			fullName = updated.full_name || '';
			username = updated.username || '';
			profileMessage = 'Profile updated successfully.';
		} catch (error) {
			profileError = error instanceof Error ? error.message : 'Failed to update profile.';
		} finally {
			profileLoading = false;
		}
	}

	async function handlePasswordUpdate() {
		passwordError = '';
		passwordMessage = '';

		if (!currentPassword) {
			passwordError = 'Current password is required.';
			return;
		}
		if (newPassword.length < 8) {
			passwordError = 'New password must be at least 8 characters.';
			return;
		}
		if (newPassword !== confirmPassword) {
			passwordError = 'New password and confirmation do not match.';
			return;
		}

		passwordLoading = true;
		try {
			await changePassword({
				current_password: currentPassword,
				new_password: newPassword
			});
			passwordMessage = 'Password changed successfully.';
			currentPassword = '';
			newPassword = '';
			confirmPassword = '';
		} catch (error) {
			passwordError = error instanceof Error ? error.message : 'Failed to change password.';
		} finally {
			passwordLoading = false;
		}
	}
</script>

<svelte:head>
	<title>Admin Profile - VQuest Trainer</title>
</svelte:head>

<div class="profile-page">
	<div class="profile-card glass-panel animate-scale-in">
		<div class="avatar-ring">
			<div class="avatar-core">{getInitials($currentUser?.full_name, $currentUser?.username)}</div>
		</div>

		<div class="profile-copy">
			<p class="eyebrow">Admin Profile</p>
			<h1 class="profile-name font-serif">{$currentUser?.full_name || $currentUser?.username || 'Admin'}</h1>
			<p class="profile-email">{$currentUser?.email || 'No email available'}</p>
		</div>

		<div class="detail-grid">
			<div class="detail-item">
				<span class="detail-label">Username</span>
				<span class="detail-value">{$currentUser?.username || 'Not set'}</span>
			</div>
			<div class="detail-item">
				<span class="detail-label">Role</span>
				<span class="detail-value">{$currentUser?.role || 'No role available'}</span>
			</div>
		</div>

		<div class="profile-actions">
			<button class="secondary-action glass-panel" onclick={() => goto('/admin/dashboard')}>Back to Dashboard</button>
			<button class="primary-action" onclick={handleLogout}>Sign Out</button>
		</div>
	</div>

	<div class="settings-stack animate-fade-in">
		<form
			class="settings-form glass-panel"
			onsubmit={(event) => {
				event.preventDefault();
				handleProfileUpdate();
			}}
		>
			<p class="section-title">Profile Settings</p>
			<label class="field">
				<span>Full name</span>
				<input bind:value={fullName} type="text" maxlength="255" placeholder="Enter your full name" />
			</label>
			<label class="field">
				<span>Username</span>
				<input bind:value={username} type="text" minlength="3" maxlength="50" placeholder="Enter username" />
			</label>
			{#if profileError}
				<p class="feedback error">{profileError}</p>
			{/if}
			{#if profileMessage}
				<p class="feedback success">{profileMessage}</p>
			{/if}
			<button class="save-action" type="submit" disabled={profileLoading}>
				{profileLoading ? 'Saving...' : 'Save Profile'}
			</button>
		</form>

		<form
			class="settings-form glass-panel"
			onsubmit={(event) => {
				event.preventDefault();
				handlePasswordUpdate();
			}}
		>
			<p class="section-title">Reset Password</p>
			<input
				class="username-accessibility-field"
				type="text"
				autocomplete="username"
				value={username}
				readonly
				tabindex="-1"
				aria-label="Username"
			/>
			<label class="field">
				<span>Current password</span>
				<input bind:value={currentPassword} type="password" autocomplete="current-password" required />
			</label>
			<label class="field">
				<span>New password</span>
				<input bind:value={newPassword} type="password" minlength="8" autocomplete="new-password" required />
			</label>
			<label class="field">
				<span>Confirm new password</span>
				<input bind:value={confirmPassword} type="password" minlength="8" autocomplete="new-password" required />
			</label>
			{#if passwordError}
				<p class="feedback error">{passwordError}</p>
			{/if}
			{#if passwordMessage}
				<p class="feedback success">{passwordMessage}</p>
			{/if}
			<button class="save-action" type="submit" disabled={passwordLoading}>
				{passwordLoading ? 'Updating...' : 'Update Password'}
			</button>
		</form>
	</div>
</div>

<style>
	.profile-page {
		width: min(100%, 860px);
		margin: 0 auto;
		min-height: 100%;
		max-height: 100%;
		overflow-y: auto;
		padding: 1.25rem 1.25rem max(1.5rem, env(safe-area-inset-bottom));
		display: flex;
		flex-direction: column;
		align-items: stretch;
		justify-content: flex-start;
		gap: 1.25rem;
		box-sizing: border-box;
		-webkit-overflow-scrolling: touch;
	}

	.settings-stack {
		width: 100%;
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 0.9rem;
	}

	.profile-card {
		width: 100%;
		padding: 2rem 1.5rem;
		border-radius: 1.5rem;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 1.5rem;
		text-align: center;
		backdrop-filter: blur(16px) saturate(140%);
		-webkit-backdrop-filter: blur(16px) saturate(140%);
		background: rgba(255, 255, 255, 0.82);
		border: 1px solid rgba(17, 24, 39, 0.12);
		box-shadow: 0 18px 36px rgba(15, 23, 42, 0.12), inset 0 1px 0 rgba(255, 255, 255, 0.65);
	}

	.avatar-ring {
		width: 108px;
		height: 108px;
		padding: 6px;
		border-radius: 999px;
		background: linear-gradient(135deg, rgba(var(--theme-primary-rgb), 0.65), rgba(255, 255, 255, 0.24));
		display: flex;
		align-items: center;
		justify-content: center;
		box-shadow: 0 18px 48px rgba(0, 0, 0, 0.22);
	}

	.avatar-core {
		width: 100%;
		height: 100%;
		border-radius: 999px;
		display: flex;
		align-items: center;
		justify-content: center;
		background: rgba(17, 24, 39, 0.78);
		color: #f8fafc;
		font-size: 2rem;
		font-weight: 800;
		letter-spacing: 0.08em;
	}

	.profile-copy {
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
	}

	.eyebrow {
		margin: 0;
		font-size: 0.76rem;
		font-weight: 700;
		letter-spacing: 0.14em;
		text-transform: uppercase;
		color: var(--theme-primary);
	}

	.profile-name {
		margin: 0;
		font-size: clamp(2rem, 6vw, 2.6rem);
		line-height: 1.05;
		color: var(--theme-text);
	}

	.profile-email {
		margin: 0;
		font-size: 0.98rem;
		color: var(--theme-text-muted);
	}

	.detail-grid {
		width: 100%;
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 0.85rem;
	}

	.detail-item {
		padding: 1rem;
		border-radius: 1rem;
		background: rgba(255, 255, 255, 0.74);
		border: 1px solid rgba(17, 24, 39, 0.12);
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: 0.3rem;
		text-align: left;
	}

	.detail-label {
		font-size: 0.72rem;
		font-weight: 700;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: var(--theme-text-muted);
	}

	.detail-value {
		font-size: 0.98rem;
		font-weight: 600;
		color: var(--theme-text);
	}

	.profile-actions {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 0.65rem;
		width: 100%;
	}

	.profile-actions button {
		padding: 0.72rem 0.9rem;
		border-radius: 999px;
		border: none;
		font: inherit;
		font-weight: 700;
		cursor: pointer;
	}

	.secondary-action {
		background: rgba(255, 255, 255, 0.72);
		border: 1px solid rgba(17, 24, 39, 0.14);
		color: var(--theme-text);
	}

	.primary-action {
		background: #dc2626;
		color: #fff;
		box-shadow: 0 10px 24px rgba(127, 29, 29, 0.16);
	}

	.settings-form {
		padding: 1rem;
		border-radius: 1rem;
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
		background: rgba(255, 255, 255, 0.82);
		border: 1px solid rgba(17, 24, 39, 0.12);
		box-shadow: 0 14px 26px rgba(15, 23, 42, 0.1), inset 0 1px 0 rgba(255, 255, 255, 0.65);
	}

	.section-title {
		margin: 0;
		font-size: 1rem;
		font-weight: 700;
		color: var(--theme-text);
	}

	.field {
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
	}

	.field span {
		font-size: 0.75rem;
		font-weight: 700;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--theme-text-muted);
	}

	.field input {
		padding: 0.68rem 0.75rem;
		border-radius: 0.8rem;
		border: 1px solid rgba(15, 23, 42, 0.16);
		background: rgba(255, 255, 255, 0.92);
		color: var(--theme-text);
		font: inherit;
	}

	.field input:focus {
		outline: 2px solid rgba(var(--theme-primary-rgb), 0.32);
		outline-offset: 1px;
	}

	.username-accessibility-field {
		position: absolute;
		width: 1px;
		height: 1px;
		padding: 0;
		margin: -1px;
		overflow: hidden;
		clip: rect(0, 0, 0, 0);
		white-space: nowrap;
		border: 0;
	}

	.feedback {
		margin: 0;
		padding: 0.55rem 0.68rem;
		border-radius: 0.75rem;
		font-size: 0.8rem;
		font-weight: 600;
	}

	.feedback.error {
		background: rgba(239, 68, 68, 0.13);
		color: #b91c1c;
		border: 1px solid rgba(239, 68, 68, 0.25);
	}

	.feedback.success {
		background: rgba(16, 185, 129, 0.14);
		color: #065f46;
		border: 1px solid rgba(16, 185, 129, 0.28);
	}

	.save-action {
		margin-top: 0.15rem;
		padding: 0.68rem 0.85rem;
		border-radius: 999px;
		border: none;
		font: inherit;
		font-size: 0.9rem;
		font-weight: 700;
		cursor: pointer;
		background: rgba(var(--theme-primary-rgb), 0.85);
		color: #fff;
		box-shadow: 0 10px 20px rgba(var(--theme-primary-rgb), 0.2);
	}

	.save-action:disabled {
		opacity: 0.65;
		cursor: wait;
	}

	@media (max-width: 768px) {
		.profile-page {
			width: 100%;
			padding: 1.25rem 1rem max(1.25rem, env(safe-area-inset-bottom));
			gap: 1rem;
		}

		.settings-stack {
			grid-template-columns: 1fr;
			gap: 0.75rem;
		}

		.profile-card {
			padding: 1.75rem 1.25rem;
			border-radius: 1.25rem;
			gap: 1.25rem;
		}

		.avatar-ring {
			width: 90px;
			height: 90px;
			padding: 5px;
		}

		.avatar-core {
			font-size: 1.75rem;
		}

		.eyebrow {
			font-size: 0.7rem;
		}

		.profile-name {
			font-size: clamp(1.75rem, 6vw, 2.2rem);
		}

		.profile-email {
			font-size: 0.9rem;
		}

		.detail-grid {
			gap: 0.7rem;
		}

		.detail-item {
			padding: 0.85rem;
		}

		.detail-label {
			font-size: 0.68rem;
		}

		.detail-value {
			font-size: 0.9rem;
		}

		.profile-actions button {
			min-height: 48px;
			font-size: 0.9rem;
		}
	}

	@media (max-width: 480px) {
		.profile-page {
			padding: max(1rem, env(safe-area-inset-top)) 0.75rem max(1rem, env(safe-area-inset-bottom));
			justify-content: flex-start;
			gap: 0.85rem;
		}

		.settings-stack {
			gap: 0.6rem;
		}

		.profile-card {
			padding: 1.4rem 1rem;
			border-radius: 1rem;
			gap: 1rem;
		}

		.avatar-ring {
			width: 80px;
			height: 80px;
			padding: 4px;
		}

		.avatar-core {
			font-size: 1.5rem;
		}

		.profile-copy {
			gap: 0.25rem;
		}

		.eyebrow {
			font-size: 0.65rem;
		}

		.profile-name {
			font-size: 1.5rem;
		}

		.profile-email {
			font-size: 0.85rem;
		}

		.detail-grid,
		.profile-actions {
			grid-template-columns: 1fr;
			gap: 0.6rem;
		}

		.detail-item {
			padding: 0.75rem 0.85rem;
			border-radius: 0.75rem;
		}

		.detail-label {
			font-size: 0.65rem;
		}

		.detail-value {
			font-size: 0.85rem;
		}

		.profile-actions {
			gap: 0.5rem;
		}

		.profile-actions button {
			min-height: 44px;
			font-size: 0.85rem;
		}
	}
</style>
