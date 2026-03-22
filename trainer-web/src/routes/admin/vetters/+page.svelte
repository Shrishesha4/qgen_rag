<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { session } from '$lib/session';
	import { getAdminDashboard, type AdminDashboard, type UserStats, type VetterBreakdown } from '$lib/api/admin';

	let loading = $state(true);
	let error = $state('');
	let query = $state('');
	let stats = $state<AdminDashboard | null>(null);

	onMount(() => {
		const unsub = session.subscribe((s) => {
			if (!s || s.user.role !== 'admin') {
				goto('/admin/login');
			}
		});
		loadVetters();
		return unsub;
	});

	async function loadVetters() {
		loading = true;
		error = '';
		try {
			stats = await getAdminDashboard();
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to load vetter analytics';
		} finally {
			loading = false;
		}
	}

	type VetterRow = {
		vetter: VetterBreakdown;
		userRecord: UserStats | null;
		approvalRate: number;
		rejectionRate: number;
		platformShare: number;
	};

	const vetterRows = $derived.by<VetterRow[]>(() => {
		if (!stats) return [];
		const platformVetted = stats.total_vetted;
		const byUser = new Map<string, UserStats>();
		for (const user of stats.users) {
			byUser.set(user.user_id, user);
		}

		const rows = stats.vetters.map((vetter) => {
			const userRecord = byUser.get(vetter.user_id) || null;
			const approvalRate = vetter.total_vetted > 0 ? Math.round((vetter.total_approved / vetter.total_vetted) * 100) : 0;
			const rejectionRate = vetter.total_vetted > 0 ? Math.round((vetter.total_rejected / vetter.total_vetted) * 100) : 0;
			const platformShare = platformVetted > 0 ? Math.round((vetter.total_vetted / platformVetted) * 100) : 0;
			return { vetter, userRecord, approvalRate, rejectionRate, platformShare };
		});

		const needle = query.trim().toLowerCase();
		const filtered = needle
			? rows.filter((row) =>
					[row.vetter.full_name || '', row.vetter.username, row.vetter.email]
						.some((value) => value.toLowerCase().includes(needle))
				)
			: rows;

		return filtered.sort((a, b) => {
			if (b.vetter.total_vetted !== a.vetter.total_vetted) return b.vetter.total_vetted - a.vetter.total_vetted;
			return a.vetter.username.localeCompare(b.vetter.username);
		});
	});

	const totals = $derived.by(() => {
		return vetterRows.reduce(
			(acc, row) => {
				acc.vetters += 1;
				acc.totalVetted += row.vetter.total_vetted;
				acc.totalApproved += row.vetter.total_approved;
				acc.totalRejected += row.vetter.total_rejected;
				return acc;
			},
			{ vetters: 0, totalVetted: 0, totalApproved: 0, totalRejected: 0 }
		);
	});
</script>

<svelte:head>
	<title>Vetter Progress — Admin</title>
</svelte:head>

<div class="page">
	<div class="hero animate-fade-in">
		<div>
			<p class="eyebrow">Admin Console</p>
			<h1 class="title font-serif">Vetter Progress</h1>
			<p class="subtitle">See individual vetter throughput, approval behavior, and contribution share across the platform.</p>
		</div>
	</div>

	<div class="toolbar glass-panel animate-slide-up">
		<input class="search-input" bind:value={query} placeholder="Search vetter by name, username, or email" />
	</div>

	{#if error}
		<div class="error-banner" role="alert">{error}</div>
	{/if}

	<div class="stats-row animate-slide-up">
		<div class="stat-card glass-panel">
			<span class="stat-value amber-text">{loading ? '…' : totals.vetters}</span>
			<span class="stat-label">Vetters</span>
		</div>
		<div class="stat-card glass-panel">
			<span class="stat-value blue-text">{loading ? '…' : totals.totalVetted}</span>
			<span class="stat-label">Total Vetted</span>
		</div>
		<div class="stat-card glass-panel">
			<span class="stat-value green-text">{loading ? '…' : totals.totalApproved}</span>
			<span class="stat-label">Approved</span>
		</div>
		<div class="stat-card glass-panel">
			<span class="stat-value red-text">{loading ? '…' : totals.totalRejected}</span>
			<span class="stat-label">Rejected</span>
		</div>
	</div>

	{#if loading}
		<div class="center-state">
			<div class="spinner"></div>
			<p>Loading vetter analytics…</p>
		</div>
	{:else if vetterRows.length === 0}
		<div class="center-state glass-panel">
			<p>No vetters matched your search.</p>
		</div>
	{:else}
		<div class="table-wrap glass-panel animate-fade-in">
			<table class="data-table">
				<thead>
					<tr>
						<th>Vetter</th>
						<th>Total Vetted</th>
						<th>Approved</th>
						<th>Rejected</th>
						<th>Approval Rate</th>
						<th>Rejection Rate</th>
						<th>Platform Share</th>
						<th>Subjects</th>
						<th>Topics</th>
					</tr>
				</thead>
				<tbody>
					{#each vetterRows as row}
						<tr>
							<td>
								<div class="user-cell">
									<span class="user-name">{row.vetter.full_name || row.vetter.username}</span>
									<span class="user-email">{row.vetter.email}</span>
								</div>
							</td>
							<td class="num">{row.vetter.total_vetted}</td>
							<td class="num green-text">{row.vetter.total_approved}</td>
							<td class="num red-text">{row.vetter.total_rejected}</td>
							<td class="num">{row.approvalRate}%</td>
							<td class="num">{row.rejectionRate}%</td>
							<td class="num">{row.platformShare}%</td>
							<td class="num">{row.userRecord?.subjects_count ?? 0}</td>
							<td class="num">{row.userRecord?.topics_count ?? 0}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}
</div>

<style>
	.page {
		max-width: 1160px;
		margin: 0 auto;
		padding: 2rem 1.5rem 2.5rem;
		display: flex;
		flex-direction: column;
		gap: 1.25rem;
	}

	.hero {
		padding-top: 0.5rem;
	}

	.eyebrow {
		margin: 0 0 0.35rem;
		font-size: 0.78rem;
		font-weight: 700;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: #fbbf24;
	}

	.title {
		margin: 0;
		font-size: 2rem;
		font-weight: 800;
		color: var(--theme-text);
	}

	.subtitle {
		margin: 0.5rem 0 0;
		max-width: 52rem;
		color: var(--theme-text-muted);
		line-height: 1.6;
	}

	.toolbar {
		display: flex;
		gap: 0.75rem;
		padding: 1rem;
		border-radius: 1rem;
	}

	.search-input {
		width: 100%;
		padding: 0.85rem 1rem;
		border-radius: 0.85rem;
		border: 1px solid rgba(255,255,255,0.14);
		background: rgba(255,255,255,0.06);
		color: var(--theme-text);
		font: inherit;
	}

	.search-input::placeholder {
		color: var(--theme-text-muted);
	}

	.error-banner {
		padding: 0.9rem 1rem;
		border-radius: 1rem;
		background: rgba(239, 68, 68, 0.12);
		border: 1px solid rgba(239, 68, 68, 0.3);
		color: #fca5a5;
	}

	.stats-row {
		display: grid;
		grid-template-columns: repeat(4, minmax(0, 1fr));
		gap: 0.75rem;
	}

	.stat-card {
		padding: 1rem;
		border-radius: 1rem;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.2rem;
	}

	.stat-value {
		font-size: 1.65rem;
		font-weight: 800;
	}

	.stat-label {
		font-size: 0.72rem;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--theme-text-muted);
		font-weight: 700;
	}

	.table-wrap {
		overflow-x: auto;
		border-radius: 1rem;
	}

	.data-table {
		width: 100%;
		border-collapse: collapse;
		min-width: 760px;
	}

	.data-table th,
	.data-table td {
		padding: 0.8rem 0.85rem;
		border-bottom: 1px solid rgba(148, 163, 184, 0.24);
		text-align: left;
		font-size: 0.86rem;
	}

	.data-table th {
		font-size: 0.72rem;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--theme-text-muted);
		font-weight: 700;
	}

	.user-cell {
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
	}

	.user-name {
		font-weight: 700;
		color: var(--theme-text);
	}

	.user-email {
		font-size: 0.78rem;
		color: var(--theme-text-muted);
	}

	.num {
		text-align: right;
		font-variant-numeric: tabular-nums;
	}

	.center-state {
		display: grid;
		place-items: center;
		gap: 0.55rem;
		padding: 2.2rem 1rem;
		text-align: center;
		color: var(--theme-text-muted);
	}

	.spinner {
		width: 22px;
		height: 22px;
		border-radius: 50%;
		border: 2px solid rgba(255,255,255,0.24);
		border-top-color: #fbbf24;
		animation: spin 1s linear infinite;
	}

	@keyframes spin {
		to { transform: rotate(360deg); }
	}

	@media (max-width: 900px) {
		.stats-row {
			grid-template-columns: repeat(2, minmax(0, 1fr));
		}
	}

	@media (max-width: 640px) {
		.page {
			padding: 1.25rem 0.95rem 1.8rem;
		}
	}

	:global([data-theme='light']) .search-input {
		background: #ffffff;
		border-color: rgba(148, 163, 184, 0.42);
		color: #0f172a;
	}

	:global([data-theme='light']) .stat-card,
	:global([data-theme='light']) .toolbar,
	:global([data-theme='light']) .table-wrap {
		background: #ffffff;
		border: 1px solid rgba(148, 163, 184, 0.3);
		box-shadow: 0 14px 34px rgba(15, 23, 42, 0.08);
	}

	:global([data-theme='light']) .title,
	:global([data-theme='light']) .user-name,
	:global([data-theme='light']) .num {
		color: #0f172a;
	}

	:global([data-theme='light']) .subtitle,
	:global([data-theme='light']) .user-email,
	:global([data-theme='light']) .stat-label,
	:global([data-theme='light']) .data-table th {
		color: #475569;
	}

	:global([data-theme='light']) .data-table th,
	:global([data-theme='light']) .data-table td {
		border-bottom-color: rgba(148, 163, 184, 0.35);
	}
</style>
