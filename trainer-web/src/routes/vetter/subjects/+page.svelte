<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { session } from '$lib/session';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import { getVetterSubjects, type VetterSubjectSummary } from '$lib/api/vetting';

	onMount(() => {
		const unsub = session.subscribe((s) => {
			if (!s || s.user.role !== 'vetter') goto('/vetter/login');
		});
		loadSubjects();
		return unsub;
	});

	let subjects = $state<VetterSubjectSummary[]>([]);
	let loading = $state(true);
	let error = $state('');

	async function loadSubjects() {
		loading = true;
		error = '';
		try {
			subjects = await getVetterSubjects();
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to load subjects';
		} finally {
			loading = false;
		}
	}

	function openSubject(id: string) {
		goto(`/vetter/subjects/${id}`);
	}

	function startAllVetting() {
		goto('/vetter/loop');
	}
</script>

<svelte:head>
	<title>Select Subject — QGen Vetter</title>
</svelte:head>

<PageHeader title="Select Subject" backHref="/vetter/dashboard" />

<div class="page">
	{#if loading}
		<div class="center-state">
			<div class="spinner"></div>
			<p>Loading subjects…</p>
		</div>
	{:else if error}
		<div class="center-state">
			<span class="err-icon">⚠️</span>
			<p class="err-msg">{error}</p>
			<button class="glass-btn" onclick={loadSubjects}>Retry</button>
		</div>
	{:else if subjects.length === 0}
		<div class="center-state">
			<span class="empty-icon">📭</span>
			<p>No subjects available for vetting</p>
			<button class="glass-btn" onclick={() => goto('/vetter/dashboard')}>
				Back to Dashboard
			</button>
		</div>
	{:else}
		<!-- Vet all pending button -->
		<button class="vet-all-btn glass" onclick={startAllVetting}>
			<span class="vet-all-icon">📋</span>
			<div class="vet-all-info">
				<span class="vet-all-title">Vet All Pending</span>
				<span class="vet-all-desc">Review questions across all subjects</span>
			</div>
			<span class="vet-all-arrow">→</span>
		</button>

		<div class="divider">
			<span class="divider-text">or choose a subject</span>
		</div>

		<div class="subject-list">
			{#each subjects as s}
				<button class="subject-card glass" onclick={() => openSubject(s.id)}>
					<div class="sc-top">
						<span class="sc-code">{s.code}</span>
						{#if s.pending_count > 0}
							<span class="sc-pending">{s.pending_count} pending</span>
						{:else}
							<span class="sc-done">✓ All reviewed</span>
						{/if}
					</div>
					<h2 class="sc-name">{s.name}</h2>
					{#if s.description}
						<p class="sc-desc">{s.description}</p>
					{/if}
					<div class="sc-stats">
						<span class="sc-stat">📝 {s.pending_count + s.approved_count + s.rejected_count} questions</span>
						<span class="sc-stat">📚 {s.topics.length} topics</span>
					</div>
				</button>
			{/each}
		</div>
	{/if}
</div>

<style>
	.page {
		max-width: 600px;
		margin: 0 auto;
		padding: 2rem 1.5rem;
		min-height: 100vh;
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}

	.center-state {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 1rem;
		padding: 4rem 1rem;
		text-align: center;
	}

	.center-state p { color: var(--theme-text-muted); margin: 0; }

	.spinner {
		width: 32px; height: 32px;
		border: 3px solid rgba(255, 255, 255, 0.15);
		border-top-color: var(--theme-primary);
		border-radius: 50%;
		animation: spin 0.8s linear infinite;
	}
	@keyframes spin { to { transform: rotate(360deg); } }

	.err-icon { font-size: 2rem; }
	.err-msg { color: #e94560 !important; }
	.empty-icon { font-size: 3rem; }

	/* Vet all button */
	.vet-all-btn {
		display: flex;
		align-items: center;
		gap: 1rem;
		padding: 1.25rem 1.5rem;
		width: 100%;
		border: 1px solid rgba(var(--theme-primary-rgb), 0.3);
		background: rgba(var(--theme-primary-rgb), 0.08);
		cursor: pointer;
		font-family: inherit;
		color: inherit;
		text-align: left;
		transition: all 0.2s;
	}
	.vet-all-btn:hover {
		transform: translateY(-2px);
		border-color: rgba(var(--theme-primary-rgb), 0.5);
		background: rgba(var(--theme-primary-rgb), 0.12);
	}
	.vet-all-icon { font-size: 1.5rem; }
	.vet-all-info { flex: 1; display: flex; flex-direction: column; gap: 0.15rem; }
	.vet-all-title { font-size: 1rem; font-weight: 700; color: var(--theme-text); }
	.vet-all-desc { font-size: 0.82rem; color: var(--theme-text-muted); }
	.vet-all-arrow { font-size: 1.2rem; color: var(--theme-primary); font-weight: 700; }

	/* Divider */
	.divider {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		padding: 0.25rem 0;
	}
	.divider::before, .divider::after {
		content: '';
		flex: 1;
		height: 1px;
		background: rgba(255, 255, 255, 0.08);
	}
	.divider-text {
		font-size: 0.75rem;
		color: var(--theme-text-muted);
		text-transform: uppercase;
		letter-spacing: 0.05em;
		font-weight: 600;
	}

	/* Subject cards */
	.subject-list {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}

	.subject-card {
		text-align: left;
		cursor: pointer;
		padding: 1.25rem 1.5rem;
		width: 100%;
		font-family: inherit;
		color: inherit;
		transition: all 0.2s;
	}
	.subject-card:hover {
		transform: translateY(-2px);
		border-color: rgba(var(--theme-primary-rgb), 0.4);
	}

	.sc-top {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 0.5rem;
	}
	.sc-code {
		font-size: 0.7rem;
		font-weight: 700;
		padding: 0.15rem 0.5rem;
		background: rgba(var(--theme-primary-rgb), 0.15);
		color: var(--theme-primary);
		border-radius: 4px;
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}
	.sc-pending {
		font-size: 0.72rem;
		font-weight: 600;
		padding: 0.15rem 0.5rem;
		background: rgba(240, 180, 40, 0.15);
		color: #f0c060;
		border-radius: 4px;
	}
	.sc-done {
		font-size: 0.72rem;
		font-weight: 600;
		padding: 0.15rem 0.5rem;
		background: rgba(72, 192, 80, 0.15);
		color: #6ee87a;
		border-radius: 4px;
	}
	.sc-name {
		font-size: 1.1rem;
		font-weight: 700;
		margin: 0 0 0.3rem;
		color: var(--theme-text);
	}
	.sc-desc {
		font-size: 0.85rem;
		color: var(--theme-text-muted);
		margin: 0 0 0.75rem;
		line-height: 1.4;
		display: -webkit-box;
		-webkit-line-clamp: 2;
		line-clamp: 2;
		-webkit-box-orient: vertical;
		overflow: hidden;
	}
	.sc-stats {
		display: flex;
		gap: 1rem;
		flex-wrap: wrap;
	}
	.sc-stat {
		font-size: 0.75rem;
		color: var(--theme-text-muted);
	}

	@media (max-width: 768px) {
		.page { padding-top: 1rem; }
	}
</style>
