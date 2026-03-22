<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { logout } from '$lib/api/auth';
	import { currentUser, session } from '$lib/session';

	onMount(() => {
		const unsub = session.subscribe((s) => {
			if (!s || s.user.role !== 'vetter') {
				goto('/vetter/login');
			}
		});
		return unsub;
	});

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
