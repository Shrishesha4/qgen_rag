<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { session } from '$lib/session';
	import { getSubjectsTree, type SubjectTreeResponse } from '$lib/api/subjects';
	import { getVetterSubjects, type VetterSubjectSummary } from '$lib/api/vetting';
	import { buildSubjectGroupMetaById, getSubjectGroupPath, matchesSubjectSearch } from '$lib/subject-group-search';

	onMount(() => {
		const unsub = session.subscribe((s) => {
			if (!s || s.user.role !== 'vetter') goto('/vetter/login');
		});
		loadSubjects();
		return unsub;
	});

	let subjects = $state<VetterSubjectSummary[]>([]);
	let subjectTree = $state<SubjectTreeResponse | null>(null);
	let loading = $state(true);
	let error = $state('');
	let searchQuery = $state('');
	let statusFilter = $state<'all' | 'pending' | 'reviewed'>('all');

	async function loadSubjects() {
		loading = true;
		error = '';
		try {
			const [subjectList, tree] = await Promise.all([getVetterSubjects(), getSubjectsTree()]);
			subjects = subjectList;
			subjectTree = tree;
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
		goto('/vetter/dashboard/loop');
	}

	const subjectGroupMetaById = $derived.by(() => buildSubjectGroupMetaById(subjectTree?.groups ?? []));

	const hasSearchQuery = $derived.by(() => searchQuery.trim().length > 0);

	const filteredSubjects = $derived.by(() => {
		const q = searchQuery.trim().toLowerCase();
		return subjects.filter((subject) => {
			const statusMatch =
				statusFilter === 'all' ||
				(statusFilter === 'pending' && subject.pending_count > 0) ||
				(statusFilter === 'reviewed' && subject.pending_count === 0);
			if (!statusMatch) return false;

			if (!q) return true;
			if (matchesSubjectSearch(subject, q, subjectGroupMetaById)) return true;
			return subject.topics.some((topic) => topic.name.toLowerCase().includes(q));
		});
	});
</script>

<svelte:head>
	<title>Select Subject — VQuest Vetter</title>
</svelte:head>

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
			<button class="glass-btn empty-back-btn" onclick={() => goto('/vetter/dashboard')}>
				Back to Subjects
			</button>
		</div>
	{:else}
		<div class="filters glass">
			<input
				class="search-input"
				type="search"
				bind:value={searchQuery}
				placeholder="Search subject, code, topic, or group"
			/>
			<!-- <div class="filter-row">
				<button class="filter-chip" class:active={statusFilter === 'all'} onclick={() => (statusFilter = 'all')}>All</button>
				<button class="filter-chip" class:active={statusFilter === 'pending'} onclick={() => (statusFilter = 'pending')}>Pending</button>
				<button class="filter-chip" class:active={statusFilter === 'reviewed'} onclick={() => (statusFilter = 'reviewed')}>Reviewed</button>
			</div> -->
		</div>

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
			{#if filteredSubjects.length === 0}
				<div class="empty-filter">No subjects match your current search/filter.</div>
			{/if}
			{#each filteredSubjects as s}
				{@const groupPath = getSubjectGroupPath(s.id, subjectGroupMetaById)}
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
					{#if hasSearchQuery && groupPath}
						<p class="sc-group">Group: {groupPath}</p>
					{/if}
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
		padding: 5rem 1.5rem 2rem;
		gap: 1.5rem;
		display: flex;
		flex-direction: column;
	}

	.center-state {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		min-height: 56vh;
		gap: 1rem;
		padding: 4rem 1rem;
		text-align: center;
	}

	.center-state p { color: var(--theme-text-muted); margin: 0; }

	.filters {
		border: 1px solid rgba(255, 255, 255, 0.12);
		border-radius: 1rem;
		padding: 0.75rem;
		display: flex;
		flex-direction: column;
		gap: 0.6rem;
	}

	.search-input {
		width: 100%;
		padding: 0.68rem 0.78rem;
		border-radius: 0.72rem;
		border: 1px solid rgba(255, 255, 255, 0.16);
		background: rgba(255, 255, 255, 0.12);
		color: var(--theme-text);
		font: inherit;
	}

	/* .filter-row {
		display: flex;
		gap: 0.45rem;
		flex-wrap: wrap;
	}

	.filter-chip {
		padding: 0.38rem 0.72rem;
		border-radius: 999px;
		border: 1px solid rgba(255, 255, 255, 0.15);
		background: rgba(255, 255, 255, 0.08);
		color: var(--theme-text-muted);
		font: inherit;
		font-size: 0.78rem;
		font-weight: 700;
		cursor: pointer;
	}

	.filter-chip.active {
		border-color: rgba(var(--theme-primary-rgb), 0.42);
		background: rgba(var(--theme-primary-rgb), 0.16);
		color: var(--theme-text);
	} */

	.empty-filter {
		padding: 1rem;
		border-radius: 0.9rem;
		border: 1px dashed rgba(255, 255, 255, 0.16);
		color: var(--theme-text-muted);
		font-size: 0.86rem;
		text-align: center;
	}

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

	.empty-back-btn {
		min-height: 44px;
		padding: 0.6rem 1.1rem;
		border-radius: 999px;
		border: 1px solid rgba(var(--theme-primary-rgb), 0.42);
		background: rgba(var(--theme-primary-rgb), 0.18);
		color: var(--theme-text);
		font: inherit;
		font-weight: 700;
		cursor: pointer;
		box-shadow: 0 8px 20px rgba(15, 23, 42, 0.16);
		transition: transform 0.15s ease, background 0.15s ease, border-color 0.15s ease;
	}

	.empty-back-btn:hover {
		transform: translateY(-1px);
		background: rgba(var(--theme-primary-rgb), 0.24);
		border-color: rgba(var(--theme-primary-rgb), 0.58);
	}

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
	.vet-all-btn:hover {
		transform: translateY(-2px);
		border-color: rgba(var(--theme-primary-rgb), 0.5);
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
		border-radius: 1rem;
		background: transparent;
		border: 1px solid rgba(255, 255, 255, 0.1);
		color: inherit;
		transition: all 0.2s;
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

	.subject-card:hover {
		transform: translateY(-2px);
		border-color: rgba(var(--theme-primary-rgb), 0.4);
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
	.sc-group {
		font-size: 0.8rem;
		color: var(--theme-text-muted);
		margin: 0 0 0.45rem;
		line-height: 1.4;
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
		.page {
			padding: 4rem 1rem 1.5rem;
			gap: 0.85rem;
		}

		.vet-all-btn {
			padding: 1rem 1.25rem;
			gap: 0.85rem;
		}

		.vet-all-icon {
			font-size: 1.35rem;
		}

		.vet-all-title {
			font-size: 0.95rem;
		}

		.vet-all-desc {
			font-size: 0.78rem;
		}

		.subject-card {
			padding: 1rem 1.25rem;
		}

		.sc-code {
			font-size: 0.65rem;
		}

		.sc-pending,
		.sc-done {
			font-size: 0.68rem;
		}

		.sc-name {
			font-size: 1rem;
		}

		.sc-desc {
			font-size: 0.82rem;
			margin-bottom: 0.6rem;
		}

		.sc-stats {
			gap: 0.75rem;
		}

		.sc-stat {
			font-size: 0.72rem;
		}
	}

	@media (max-width: 480px) {
		.page {
			padding: 3.5rem 0.75rem 1.25rem;
			gap: 0.75rem;
		}

		.center-state {
			padding: 3rem 0.75rem;
		}

		.empty-icon {
			font-size: 2.5rem;
		}

		.divider {
			padding: 0.15rem 0;
		}

		.divider-text {
			font-size: 0.68rem;
		}

		.vet-all-btn {
			padding: 0.9rem 1rem;
			gap: 0.75rem;
			border-radius: 12px;
		}

		.vet-all-icon {
			font-size: 1.2rem;
		}

		.vet-all-title {
			font-size: 0.88rem;
		}

		.vet-all-desc {
			font-size: 0.72rem;
		}

		.subject-card {
			padding: 0.9rem 1rem;
			border-radius: 12px;
		}

		.sc-top {
			margin-bottom: 0.35rem;
		}

		.sc-code {
			font-size: 0.6rem;
			padding: 0.1rem 0.4rem;
		}

		.sc-pending,
		.sc-done {
			font-size: 0.62rem;
			padding: 0.1rem 0.4rem;
		}

		.sc-name {
			font-size: 0.95rem;
			margin-bottom: 0.2rem;
		}

		.sc-desc {
			font-size: 0.78rem;
			margin-bottom: 0.5rem;
		}

		.sc-stats {
			gap: 0.6rem;
		}

		.sc-stat {
			font-size: 0.68rem;
		}
	}

	:global(:root[data-color-mode='dark']) .center-state {
		background: transparent !important;
		border: none !important;
		box-shadow: none !important;
	}
</style>
