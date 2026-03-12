<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { session } from '$lib/session';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import { getVetterSubject, type VetterSubjectSummary } from '$lib/api/vetting';

	let subjectId = $state('');
	let subject = $state<VetterSubjectSummary | null>(null);
	let loading = $state(true);
	let error = $state('');

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
</script>

<svelte:head>
	<title>{subject?.name ?? 'Subject'} — QGen Vetter</title>
</svelte:head>

<PageHeader title={subject?.name ?? 'Topics'} backHref="/vetter/subjects" />

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
			<div class="divider">
				<span class="divider-text">topics</span>
			</div>

			<div class="topic-list">
				{#each subject.topics as topic, i}
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

	/* Subject hero */
	.subject-hero {
		padding: 1.5rem;
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
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
	}
	.topic-card:hover {
		transform: translateY(-1px);
		border-color: rgba(var(--theme-primary-rgb), 0.3);
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
		.page { padding-top: 1rem; }
	}
</style>
