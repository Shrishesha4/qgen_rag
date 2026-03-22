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
			if (!s || s.user.role !== 'vetter') {
				goto('/vetter/login');
			}
		});
		return unsub;
	});

	$: if ($currentUser && !initialized) {
		fullName = $currentUser.full_name || '';
		username = $currentUser.username || '';
		initialized = true;
	}

	function getInitials(name?: string | null, username?: string | null) {
		const source = (name || username || 'Vetter').trim();
		const parts = source.split(/\s+/).filter(Boolean);
		if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
		return parts.slice(0, 2).map((part) => part[0]).join('').toUpperCase();
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
	<title>Vetter Profile — VQuest Trainer</title>
</svelte:head>

<div class="profile-page">
	<div class="profile-card glass-panel animate-scale-in">
		<div class="avatar-ring">
			<div class="avatar-core">{getInitials($currentUser?.full_name, $currentUser?.username)}</div>
		</div>

		<div class="profile-copy">
			<p class="eyebrow">Vetter Profile</p>
			<h1 class="profile-name font-serif">{$currentUser?.full_name || $currentUser?.username || 'Vetter'}</h1>
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

		<form class="settings-form" onsubmit={(event) => {
			event.preventDefault();
			handleProfileUpdate();
		}}>
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

		<form class="settings-form" onsubmit={(event) => {
			event.preventDefault();
			handlePasswordUpdate();
		}}>
			<p class="section-title">Reset Password</p>
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

		<div class="profile-actions">
			<button class="secondary-action glass-panel" onclick={() => goto('/vetter/dashboard')}>Back to Dashboard</button>
			<button class="primary-action" onclick={handleLogout}>Sign Out</button>
		</div>
	</div>
</div>

<style>
	.profile-page {
		min-height: 100%;
		padding: 1.25rem;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: flex-start;
	}

	.profile-card {
		margin-top: 15%;
		width: min(100%, 760px);
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
		width: 100%;
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 0.85rem;
	}

	.settings-form {
		width: 100%;
		padding: 1rem;
		border-radius: 1rem;
		border: 1px solid rgba(17, 24, 39, 0.12);
		background: rgba(255, 255, 255, 0.72);
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}

	.section-title {
		margin: 0;
		text-align: left;
		font-size: 0.78rem;
		font-weight: 700;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: var(--theme-text-muted);
	}

	.field {
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
		text-align: left;
	}

	.field span {
		font-size: 0.78rem;
		font-weight: 600;
		color: var(--theme-text-muted);
	}

	.field input {
		width: 100%;
		min-height: 44px;
		border-radius: 0.8rem;
		border: 1px solid rgba(17, 24, 39, 0.18);
		padding: 0.6rem 0.75rem;
		font: inherit;
		color: var(--theme-text);
		background: rgba(255, 255, 255, 0.92);
	}

	.field input:focus {
		outline: none;
		border-color: rgba(var(--theme-primary-rgb), 0.65);
		box-shadow: 0 0 0 3px rgba(var(--theme-primary-rgb), 0.12);
	}

	.feedback {
		margin: 0;
		font-size: 0.84rem;
		text-align: left;
	}

	.feedback.error {
		color: #991b1b;
	}

	.feedback.success {
		color: #065f46;
	}

	.save-action {
		min-height: 46px;
		border-radius: 999px;
		border: 1px solid rgba(var(--theme-primary-rgb), 0.34);
		background: rgba(var(--theme-primary-rgb), 0.14);
		color: var(--theme-text);
		font: inherit;
		font-weight: 700;
		cursor: pointer;
	}

	.save-action:disabled {
		opacity: 0.65;
		cursor: not-allowed;
	}

	.profile-actions button {
		min-height: 52px;
		border-radius: 999px;
		font: inherit;
		font-weight: 700;
		cursor: pointer;
	}

	.secondary-action {
		border: none;
		background: rgba(255, 255, 255, 0.74);
		color: var(--theme-text-primary);
		border: 1px solid rgba(17, 24, 39, 0.14);
	}

	.primary-action {
		border: 1px solid rgba(220, 38, 38, 0.4);
		background: rgba(254, 226, 226, 0.94);
		color: #7f1d1d;
		box-shadow: 0 10px 24px rgba(127, 29, 29, 0.16);
	}

	@media (max-width: 480px) {
		.profile-page {
			padding: 1rem 0.75rem;
		}

		.profile-card {
			padding: 1.5rem 1rem;
			border-radius: 1rem;
			gap: 1rem;
		}

		.detail-grid,
		.profile-actions {
			grid-template-columns: 1fr;
			gap: 0.6rem;
		}
	}
</style>
