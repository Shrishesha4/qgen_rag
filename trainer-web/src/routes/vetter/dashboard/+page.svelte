<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { session, currentUser } from '$lib/session';
	import { logout } from '$lib/api/auth';
	import { getVetterDashboard, type VetterDashboard } from '$lib/api/vetting';
	import GlassCard from '$lib/components/GlassCard.svelte';
	import IconBadge from '$lib/components/IconBadge.svelte';
	import ThemePicker from '$lib/components/ThemePicker.svelte';

	let loading = $state(true);
	let stats = $state<VetterDashboard | null>(null);

	onMount(() => {
		const unsub = session.subscribe((s) => {
			if (!s || s.user.role !== 'vetter') {
				goto('/vetter/login');
			}
		});
		loadStats();
		return unsub;
	});

	async function loadStats() {
		loading = true;
		try {
			stats = await getVetterDashboard();
		} catch {
			// silently fail — stats show '—'
		} finally {
			loading = false;
		}
	}

	async function handleLogout() {
		await logout();
		session.clear();
		goto('/');
	}

	function startVetting() {
		goto('/vetter/subjects');
	}
</script>

<svelte:head>
	<title>Vetter Dashboard — QGen Trainer</title>
</svelte:head>

<div class="vetter-dash">
	<div class="theme-corner">
		<ThemePicker />
	</div>

	<div class="hero">
		<IconBadge emoji="🔍" size="lg" />
		<h1 class="title">Vetter Dashboard</h1>
		{#if $currentUser}
			<p class="welcome">Welcome, {$currentUser.full_name || $currentUser.username}</p>
		{/if}
	</div>

	<div class="stats-row">
		<div class="stat glass">
			<span class="stat-value">{loading ? '…' : (stats?.total_pending ?? 0)}</span>
			<span class="stat-label">Pending</span>
		</div>
		<div class="stat glass">
			<span class="stat-value">{loading ? '…' : (stats?.total_approved ?? 0)}</span>
			<span class="stat-label">Approved</span>
		</div>
		<div class="stat glass">
			<span class="stat-value">{loading ? '…' : (stats?.total_rejected ?? 0)}</span>
			<span class="stat-label">Rejected</span>
		</div>
	</div>

	<div class="actions">
		<GlassCard active padding="1.75rem">
			<button class="action-row" onclick={startVetting}>
				<IconBadge emoji="📋" />
				<div class="action-info">
					<h2 class="action-title">Start Vetting</h2>
					<p class="action-desc">Review the next batch of AI-generated questions</p>
				</div>
			</button>
		</GlassCard>
	</div>

	<button class="logout-link" onclick={handleLogout}>Sign Out</button>
</div>

<style>
	.vetter-dash {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		min-height: 100vh;
		padding: 2rem 1.5rem;
		gap: 2rem;
	}

	.theme-corner {
		position: fixed;
		top: 1rem;
		right: 1rem;
		z-index: 100;
	}

	.hero {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.5rem;
		text-align: center;
	}

	.title {
		font-size: 2rem;
		font-weight: 800;
		margin: 0;
		color: var(--theme-text);
	}

	.welcome {
		font-size: 0.95rem;
		color: var(--theme-text-muted);
		margin: 0;
	}

	.stats-row {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: 0.75rem;
		width: 100%;
		max-width: 400px;
	}

	.stat {
		display: flex;
		flex-direction: column;
		align-items: center;
		padding: 1rem;
		gap: 0.25rem;
	}

	.stat-value {
		font-size: 1.5rem;
		font-weight: 800;
		color: var(--theme-text);
	}

	.stat-label {
		font-size: 0.7rem;
		font-weight: 600;
		color: var(--theme-text-muted);
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}

	.actions {
		width: 100%;
		max-width: 400px;
	}

	.action-row {
		display: flex;
		align-items: center;
		gap: 1rem;
		width: 100%;
		background: none;
		border: none;
		cursor: pointer;
		padding: 0;
		font-family: inherit;
		color: inherit;
		text-align: left;
	}

	.action-info {
		flex: 1;
	}

	.action-title {
		font-size: 1.1rem;
		font-weight: 700;
		margin: 0 0 0.2rem;
	}

	.action-desc {
		font-size: 0.85rem;
		color: var(--theme-text-muted);
		margin: 0;
	}

	.logout-link {
		background: none;
		border: none;
		color: var(--theme-text-muted);
		cursor: pointer;
		font-size: 0.85rem;
		padding: 0.5rem;
		transition: color 0.15s;
	}

	.logout-link:hover {
		color: #e94560;
	}
</style>
