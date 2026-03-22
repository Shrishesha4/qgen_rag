<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { session } from '$lib/session';
	import { getVetterSubject, type VetterSubjectSummary } from '$lib/api/vetting';

	let subjectId = $state('');
	let subject = $state<VetterSubjectSummary | null>(null);
	let loading = $state(true);
	let error = $state('');
	let topicQuery = $state('');
	let topicStatus = $state<'all' | 'pending' | 'reviewed'>('all');

	onMount(() => {
		const unsub = session.subscribe((s) => {
			if (!s || s.user.role !== 'vetter') goto('/vetter/login');
		});
		const unsubPage = page.subscribe((p) => {
			subjectId = p.params.id ?? '';
		});
		loadSubject();
		return () => { unsub(); unsubPage(); };
	});

	async function loadSubject() {
		if (!subjectId) return;
		loading = true;
		error = '';
		try {
			subject = await getVetterSubject(subjectId);
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to load subject';
		} finally {
			loading = false;
		}
	}

	function vetAllTopics() {
		goto(`/vetter/loop?subject=${subjectId}`);
	}

	function vetTopic(topicId: string) {
		goto(`/vetter/loop?subject=${subjectId}&topic=${topicId}`);
	}

	const filteredTopics = $derived.by(() => {
		if (!subject) return [];
		const q = topicQuery.trim().toLowerCase();
		return subject.topics.filter((topic) => {
			const statusMatch =
				topicStatus === 'all' ||
				(topicStatus === 'pending' && topic.pending_count > 0) ||
				(topicStatus === 'reviewed' && topic.pending_count === 0);
			if (!statusMatch) return false;
			if (!q) return true;
			return topic.name.toLowerCase().includes(q);
		});
	});
</script>

<svelte:head>
	<title>{subject?.name ?? 'Subject'} — VQuest Vetter</title>
</svelte:head>

<div class="page">
	{#if loading}
		<div class="center-state">
			<div class="spinner"></div>
			<p>Loading topics…</p>
		</div>
	{:else if error}
		<div class="center-state">
			<span class="err-icon">⚠️</span>
			<p class="err-msg">{error}</p>
			<button class="glass-btn" onclick={loadSubject}>Retry</button>
		</div>
	{:else if subject}
		<!-- Subject header -->
		<div class="subject-hero glass">
			<div class="hero-top">
				<span class="hero-code">{subject.code}</span>
				{#if subject.pending_count > 0}
					<span class="hero-pending">{subject.pending_count} pending</span>
				{:else}
					<span class="hero-done">✓ All reviewed</span>
				{/if}
			</div>
			<h1 class="hero-name">{subject.name}</h1>
			{#if subject.description}
				<p class="hero-desc">{subject.description}</p>
			{/if}
			<div class="hero-stats">
				<span class="hero-stat">📝 {subject.pending_count + subject.approved_count + subject.rejected_count} questions</span>
				<span class="hero-stat">📚 {subject.topics.length} topics</span>
			</div>
		</div>

		<!-- Vet all button -->
		{#if subject.pending_count > 0}
			<button class="vet-all-btn glass" onclick={vetAllTopics}>
				<span class="vet-all-icon">🔍</span>
				<div class="vet-all-info">
					<span class="vet-all-title">Vet All Topics</span>
					<span class="vet-all-desc">Review all {subject.pending_count} pending questions in this subject</span>
				</div>
				<span class="vet-all-arrow">→</span>
			</button>
		{/if}

		{#if subject.topics.length > 0}
			<div class="filters glass">
				<input
					class="search-input"
					type="search"
					bind:value={topicQuery}
					placeholder="Search topic"
				/>
				<div class="filter-row">
					<button class="filter-chip" class:active={topicStatus === 'all'} onclick={() => (topicStatus = 'all')}>All</button>
					<button class="filter-chip" class:active={topicStatus === 'pending'} onclick={() => (topicStatus = 'pending')}>Pending</button>
					<button class="filter-chip" class:active={topicStatus === 'reviewed'} onclick={() => (topicStatus = 'reviewed')}>Reviewed</button>
				</div>
			</div>

			<div class="divider">
				<span class="divider-text">topics</span>
			</div>

			<div class="topic-list">
				{#if filteredTopics.length === 0}
					<div class="empty-filter">No topics match your current search/filter.</div>
				{/if}
				{#each filteredTopics as topic, i}
					<button class="topic-card glass" onclick={() => vetTopic(topic.id)}>
						<div class="tc-left">
							<span class="tc-number">{i + 1}</span>
						</div>
						<div class="tc-body">
							<div class="tc-header">
								<h3 class="tc-name">{topic.name}</h3>
								{#if topic.pending_count > 0}
									<span class="tc-pending">{topic.pending_count}</span>
								{:else}
									<span class="tc-done">✓</span>
								{/if}
							</div>
						</div>
					</button>
				{/each}
			</div>
		{:else}
			<div class="center-state">
				<span class="empty-icon">📭</span>
				<p>No topics in this subject yet</p>
			</div>
		{/if}
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

	.filter-row {
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
	}

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

	/* Subject hero */
	.subject-hero {
		padding: 1.5rem;
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
		border-radius: 1rem;
		border: 1px solid rgba(255, 255, 255, 0.1);
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
	.hero-top {
		display: flex;
		justify-content: space-between;
		align-items: center;
	}
	.hero-code {
		font-size: 0.72rem;
		font-weight: 700;
		padding: 0.2rem 0.6rem;
		background: rgba(var(--theme-primary-rgb), 0.15);
		color: var(--theme-primary);
		border-radius: 4px;
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}
	.hero-pending {
		font-size: 0.72rem;
		font-weight: 600;
		padding: 0.2rem 0.6rem;
		background: rgba(240, 180, 40, 0.15);
		color: #f0c060;
		border-radius: 4px;
	}
	.hero-done {
		font-size: 0.72rem;
		font-weight: 600;
		padding: 0.2rem 0.6rem;
		background: rgba(72, 192, 80, 0.15);
		color: #6ee87a;
		border-radius: 4px;
	}
	.hero-name {
		font-size: 1.4rem;
		font-weight: 800;
		margin: 0;
		color: var(--theme-text);
	}
	.hero-desc {
		font-size: 0.88rem;
		color: var(--theme-text-muted);
		margin: 0;
		line-height: 1.5;
	}
	.hero-stats {
		display: flex;
		gap: 1rem;
		margin-top: 0.25rem;
	}
	.hero-stat {
		font-size: 0.78rem;
		color: var(--theme-text-muted);
	}

	/* Vet all */
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

	/* Topic list */
	.topic-list {
		display: flex;
		flex-direction: column;
		gap: 0.6rem;
	}

	.topic-card {
		display: flex;
		align-items: flex-start;
		gap: 1rem;
		padding: 1rem 1.25rem;
		width: 100%;
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
	.topic-card:hover {
		transform: translateY(-1px);
		border-color: rgba(var(--theme-primary-rgb), 0.3);
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

	.tc-left {
		flex-shrink: 0;
	}
	.tc-number {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 28px;
		height: 28px;
		border-radius: 8px;
		background: rgba(var(--theme-primary-rgb), 0.12);
		color: var(--theme-primary);
		font-size: 0.78rem;
		font-weight: 700;
	}

	.tc-body { flex: 1; min-width: 0; }
	.tc-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 0.5rem;
		margin-bottom: 0.25rem;
	}
	.tc-name {
		font-size: 0.95rem;
		font-weight: 700;
		margin: 0;
		color: var(--theme-text);
		flex: 1;
		min-width: 0;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.tc-pending {
		flex-shrink: 0;
		font-size: 0.7rem;
		font-weight: 700;
		min-width: 20px;
		height: 20px;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: 10px;
		background: rgba(240, 180, 40, 0.2);
		color: #f0c060;
		padding: 0 0.4rem;
	}
	.tc-done {
		flex-shrink: 0;
		font-size: 0.7rem;
		font-weight: 700;
		width: 20px;
		height: 20px;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: 10px;
		background: rgba(72, 192, 80, 0.15);
		color: #6ee87a;
	}

	@media (max-width: 768px) {
		.page {
			padding: 4rem 1rem 1.5rem;
			gap: 0.85rem;
		}

		.subject-hero {
			padding: 1.25rem;
		}

		.hero-code,
		.hero-pending,
		.hero-done {
			font-size: 0.68rem;
		}

		.hero-name {
			font-size: 1.25rem;
		}

		.hero-desc {
			font-size: 0.85rem;
		}

		.hero-stats {
			gap: 0.75rem;
		}

		.hero-stat {
			font-size: 0.75rem;
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

		.topic-card {
			padding: 0.9rem 1.1rem;
			gap: 0.85rem;
		}

		.tc-number {
			width: 26px;
			height: 26px;
			font-size: 0.75rem;
		}

		.tc-name {
			font-size: 0.9rem;
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

		.subject-hero {
			padding: 1rem;
			gap: 0.4rem;
			border-radius: 12px;
		}

		.hero-code,
		.hero-pending,
		.hero-done {
			font-size: 0.62rem;
			padding: 0.15rem 0.5rem;
		}

		.hero-name {
			font-size: 1.1rem;
		}

		.hero-desc {
			font-size: 0.8rem;
		}

		.hero-stats {
			gap: 0.6rem;
			margin-top: 0.15rem;
		}

		.hero-stat {
			font-size: 0.7rem;
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

		.divider {
			padding: 0.15rem 0;
		}

		.divider-text {
			font-size: 0.68rem;
		}

		.topic-list {
			gap: 0.5rem;
		}

		.topic-card {
			padding: 0.8rem 0.9rem;
			gap: 0.7rem;
			border-radius: 10px;
		}

		.tc-number {
			width: 24px;
			height: 24px;
			font-size: 0.7rem;
			border-radius: 6px;
		}

		.tc-name {
			font-size: 0.85rem;
		}

		.tc-pending,
		.tc-done {
			font-size: 0.65rem;
			width: 18px;
			height: 18px;
			min-width: 18px;
		}

		.tc-pending {
			padding: 0 0.35rem;
		}
	}
</style>
