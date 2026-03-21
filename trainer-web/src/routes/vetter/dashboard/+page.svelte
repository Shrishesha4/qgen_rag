<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { session, currentUser } from '$lib/session';
	import { logout } from '$lib/api/auth';
	import { getVetterDashboard, type VetterDashboard } from '$lib/api/vetting';
	import ThemeSelector from '$lib/components/ThemeSelector.svelte';

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
	<title>Vetter Dashboard — VQuest Trainer</title>
</svelte:head>

<div class="vetter-dash">
	<ThemeSelector />

	<div class="hero animate-fade-in">
		<div class="hero-icon emerald">
			<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
				<circle cx="11" cy="11" r="8"></circle>
				<path d="m21 21-4.3-4.3"></path>
			</svg>
		</div>
		<h1 class="title font-serif">Vetter Dashboard</h1>
		{#if $currentUser}
			<p class="welcome">Welcome, {$currentUser.full_name || $currentUser.username}</p>
		{/if}
	</div>

	<div class="stats-row animate-slide-up">
		<div class="stat glass-panel">
			<span class="stat-value">{loading ? '…' : (stats?.total_pending ?? 0)}</span>
			<span class="stat-label">Pending</span>
		</div>
		<div class="stat glass-panel">
			<span class="stat-value">{loading ? '…' : (stats?.total_approved ?? 0)}</span>
			<span class="stat-label">Approved</span>
		</div>
		<div class="stat glass-panel">
			<span class="stat-value">{loading ? '…' : (stats?.total_rejected ?? 0)}</span>
			<span class="stat-label">Rejected</span>
		</div>
	</div>

	<div class="actions animate-slide-up">
		<button class="action-card glass-panel" onclick={startVetting}>
			<div class="action-row">
				<div class="action-icon emerald">
					<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
						<path d="M9 11l3 3L22 4"></path>
						<path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"></path>
					</svg>
				</div>
				<div class="action-info">
					<h2 class="action-title">Start Vetting</h2>
					<p class="action-desc">Review the next batch of AI-generated questions</p>
				</div>
				<svg class="arrow" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
					<polyline points="9 18 15 12 9 6"></polyline>
				</svg>
			</div>
		</button>
	</div>

	<button class="logout-link" onclick={handleLogout}>Sign Out</button>
</div>

<style>
	.vetter-dash {
		display: flex;
		flex-direction: column;
		align-items: center;
		padding: 5rem 1.5rem 2rem;
		gap: 2rem;
		min-height: 100vh;
	}

	.hero {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.5rem;
		text-align: center;
	}

	.hero-icon {
		width: 56px;
		height: 56px;
		border-radius: 50%;
		display: flex;
		align-items: center;
		justify-content: center;
		margin-bottom: 0.25rem;
	}
	.hero-icon.emerald {
		background: rgba(16, 185, 129, 0.2);
		color: #10b981;
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

	.action-card {
		width: 100%;
		padding: 1.5rem;
		border-radius: 1rem;
		background: transparent;
		border: none;
		color: inherit;
		cursor: pointer;
		text-align: left;
		transition: transform 0.2s, box-shadow 0.2s;
		/* Enhanced blur effect - force override */
		backdrop-filter: blur(10px) saturate(150%) brightness(1.02) !important;
		-webkit-backdrop-filter: blur(10px) saturate(150%) brightness(1.02) !important;
		background: linear-gradient(
			145deg,
			rgba(255,255,255,0.03) 0%,
			rgba(255,255,255,0.02) 50%,
			rgba(255,255,255,0.025) 100%
		) !important;
		box-shadow:
			0 8px 40px rgba(0, 0, 0, 0.25),
			inset 0 1px 1px rgba(255, 255, 255, 0.25),
			inset 0 -1px 1px rgba(255, 255, 255, 0.08),
			0 0 0 1px rgba(255, 255, 255, 0.12) !important;
	}

	.action-card:hover {
		transform: translateY(-2px);
		background: linear-gradient(
			145deg,
			rgba(255,255,255,0.05) 0%,
			rgba(255,255,255,0.04) 50%,
			rgba(255,255,255,0.045) 100%
		) !important;
		box-shadow: 
			0 12px 40px rgba(0, 0, 0, 0.3),
			inset 0 1px 1px rgba(255, 255, 255, 0.3),
			inset 0 -1px 1px rgba(255, 255, 255, 0.12),
			0 0 0 1px rgba(255, 255, 255, 0.18) !important;
		/* Maintain blur on hover - force override */
		backdrop-filter: blur(10px) saturate(150%) brightness(1.02) !important;
		-webkit-backdrop-filter: blur(10px) saturate(150%) brightness(1.02) !important;
	}

	.action-row {
		display: flex;
		align-items: center;
		gap: 1rem;
		width: 100%;
	}

	.action-icon {
		width: 48px;
		height: 48px;
		border-radius: 50%;
		display: flex;
		align-items: center;
		justify-content: center;
		flex-shrink: 0;
	}
	.action-icon.emerald {
		background: rgba(16, 185, 129, 0.2);
		color: #10b981;
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

	.arrow {
		opacity: 0.4;
		flex-shrink: 0;
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

	@media (max-width: 768px) {
		.vetter-dash {
			padding: 4rem 1rem 1.5rem;
			gap: 1.5rem;
		}

		.hero-icon {
			width: 48px;
			height: 48px;
		}

		.hero-icon svg {
			width: 24px;
			height: 24px;
		}

		.title {
			font-size: 1.75rem;
		}

		.welcome {
			font-size: 0.88rem;
		}

		.stats-row {
			gap: 0.5rem;
			max-width: 100%;
		}

		.stat {
			padding: 0.85rem 0.5rem;
		}

		.stat-value {
			font-size: 1.3rem;
		}

		.stat-label {
			font-size: 0.65rem;
		}

		.actions {
			max-width: 100%;
		}

		.action-card {
			padding: 1.25rem;
		}

		.action-icon {
			width: 42px;
			height: 42px;
		}

		.action-title {
			font-size: 1rem;
		}

		.action-desc {
			font-size: 0.8rem;
		}
	}

	@media (max-width: 480px) {
		.vetter-dash {
			padding: 3.5rem 0.75rem 1.25rem;
			gap: 1.25rem;
		}

		.hero {
			gap: 0.35rem;
		}

		.hero-icon {
			width: 44px;
			height: 44px;
		}

		.hero-icon svg {
			width: 22px;
			height: 22px;
		}

		.title {
			font-size: 1.5rem;
		}

		.welcome {
			font-size: 0.82rem;
		}

		.stats-row {
			gap: 0.4rem;
		}

		.stat {
			padding: 0.75rem 0.4rem;
			border-radius: 0.75rem;
		}

		.stat-value {
			font-size: 1.15rem;
		}

		.stat-label {
			font-size: 0.6rem;
		}

		.action-card {
			padding: 1rem;
			border-radius: 0.85rem;
		}

		.action-row {
			gap: 0.75rem;
		}

		.action-icon {
			width: 38px;
			height: 38px;
		}

		.action-icon svg {
			width: 18px;
			height: 18px;
		}

		.action-title {
			font-size: 0.95rem;
		}

		.action-desc {
			font-size: 0.75rem;
			line-height: 1.35;
		}

		.logout-link {
			font-size: 0.8rem;
		}
	}
</style>
