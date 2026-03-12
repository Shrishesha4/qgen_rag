<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { session } from '$lib/session';
	import ThemeSelector from '$lib/components/ThemeSelector.svelte';
	import { listSubjects, getSubject, type SubjectResponse, type TopicResponse } from '$lib/api/subjects';

	onMount(() => {
		const unsub = session.subscribe((s) => {
			if (!s) goto('/teacher/login');
		});
		loadSubjects();
		return unsub;
	});

	let subjects = $state<SubjectResponse[]>([]);
	let loading = $state(true);
	let error = $state('');

	// Expanded state: subject id -> topics
	let expandedId = $state('');
	let topicsMap = $state<Record<string, TopicResponse[]>>({});
	let loadingTopics = $state('');

	async function loadSubjects() {
		loading = true;
		error = '';
		try {
			const res = await listSubjects(1, 100);
			subjects = res.subjects;
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to load subjects';
		} finally {
			loading = false;
		}
	}

	async function toggleSubject(id: string) {
		if (expandedId === id) {
			expandedId = '';
			return;
		}
		expandedId = id;
		if (!topicsMap[id]) {
			loadingTopics = id;
			try {
				const detail = await getSubject(id);
				topicsMap = { ...topicsMap, [id]: detail.topics };
			} catch {
				topicsMap = { ...topicsMap, [id]: [] };
			} finally {
				loadingTopics = '';
			}
		}
	}

	function trainTopic(subjectId: string, topicId: string) {
		goto(`/teacher/train/loop?subject=${subjectId}&topic=${topicId}`);
	}

	function formatDate(iso: string): string {
		return new Date(iso).toLocaleDateString('en-US', {
			month: 'short',
			day: 'numeric',
			year: 'numeric',
		});
	}
</script>

<svelte:head>
	<title>Existing Topics — QGen Trainer</title>
</svelte:head>

<ThemeSelector />

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
			<p>No subjects created yet</p>
			<button class="glass-btn" onclick={() => goto('/teacher/train/new')}>
				✨ Create New Topic
			</button>
		</div>
	{:else}
		<div class="subject-list">
			{#each subjects as s}
				<div class="subject-card glass-card" class:expanded={expandedId === s.id}>
					<button class="sc-header" onclick={() => toggleSubject(s.id)}>
						<div class="sc-top">
							<span class="sc-code">{s.code}</span>
							<span class="sc-arrow">{expandedId === s.id ? '▼' : '▶'}</span>
						</div>
						<h2 class="sc-name">{s.name}</h2>
						<div class="sc-stats">
							<span class="sc-stat">📝 {s.total_questions} questions</span>
							<span class="sc-stat">📚 {s.total_topics} topics</span>
							<span class="sc-stat">📅 {formatDate(s.created_at)}</span>
						</div>
					</button>

					{#if expandedId === s.id}
						<div class="topics-panel">
							{#if loadingTopics === s.id}
								<div class="topics-loading">
									<div class="spinner-sm"></div>
									<span>Loading topics…</span>
								</div>
							{:else if topicsMap[s.id]?.length}
								{#each topicsMap[s.id] as topic}
									<button class="topic-row" onclick={() => trainTopic(s.id, topic.id)}>
										<div class="tr-left">
											<span class="tr-name">{topic.name}</span>
											{#if topic.has_syllabus}
												<span class="tr-badge">📄 Syllabus</span>
											{/if}
										</div>
										<div class="tr-right">
											<span class="tr-qs">{topic.total_questions} Qs</span>
											<span class="tr-arrow">→</span>
										</div>
									</button>
								{/each}
							{:else}
								<p class="topics-empty">No topics found for this subject</p>
							{/if}
						</div>
					{/if}
				</div>
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
	}

	.center-state {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 1rem;
		padding: 4rem 1rem;
		text-align: center;
	}

	.center-state p {
		color: var(--theme-text-muted);
		margin: 0;
	}

	.spinner {
		width: 32px;
		height: 32px;
		border: 3px solid rgba(255, 255, 255, 0.15);
		border-top-color: var(--theme-primary);
		border-radius: 50%;
		animation: spin 0.8s linear infinite;
	}

	.spinner-sm {
		width: 18px;
		height: 18px;
		border: 2px solid rgba(255, 255, 255, 0.15);
		border-top-color: var(--theme-primary);
		border-radius: 50%;
		animation: spin 0.8s linear infinite;
	}

	@keyframes spin {
		to { transform: rotate(360deg); }
	}

	.err-icon { font-size: 2rem; }
	.err-msg { color: #e94560 !important; }
	.empty-icon { font-size: 3rem; }

	.subject-list {
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}

	.subject-card {
		padding: 0;
		width: 100%;
		overflow: hidden;
		transition: all 0.2s;
	}

	.subject-card.expanded {
		border-color: rgba(var(--theme-primary-rgb), 0.3);
	}

	.sc-header {
		display: block;
		text-align: left;
		cursor: pointer;
		padding: 1.25rem 1.5rem;
		width: 100%;
		font-family: inherit;
		background: none;
		border: none;
		color: inherit;
	}

	.sc-header:hover {
		background: rgba(255, 255, 255, 0.03);
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

	.sc-arrow {
		font-size: 0.75rem;
		color: var(--theme-text-muted);
	}

	.sc-name {
		font-size: 1.1rem;
		font-weight: 700;
		margin: 0 0 0.5rem;
		color: var(--theme-text);
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

	/* Topics panel */
	.topics-panel {
		border-top: 0.5px solid rgba(255, 255, 255, 0.08);
		padding: 0.5rem 0;
	}

	.topics-loading {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 1rem 1.5rem;
		color: var(--theme-text-muted);
		font-size: 0.85rem;
	}

	.topics-empty {
		padding: 1rem 1.5rem;
		color: var(--theme-text-muted);
		font-size: 0.85rem;
		margin: 0;
	}

	.topic-row {
		display: flex;
		align-items: center;
		justify-content: space-between;
		width: 100%;
		padding: 0.75rem 1.5rem;
		background: none;
		border: none;
		border-bottom: 0.5px solid rgba(255, 255, 255, 0.04);
		color: var(--theme-text);
		cursor: pointer;
		font-family: inherit;
		font-size: 0.9rem;
		transition: background 0.15s;
	}

	.topic-row:last-child {
		border-bottom: none;
	}

	.topic-row:hover {
		background: rgba(var(--theme-primary-rgb), 0.08);
	}

	.tr-left {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	.tr-name {
		font-weight: 600;
	}

	.tr-badge {
		font-size: 0.7rem;
		padding: 0.1rem 0.4rem;
		background: rgba(var(--theme-primary-rgb), 0.12);
		border-radius: 8px;
		color: var(--theme-primary);
	}

	.tr-right {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	.tr-qs {
		font-size: 0.75rem;
		color: var(--theme-text-muted);
	}

	.tr-arrow {
		color: var(--theme-primary);
		font-weight: 700;
	}

	@media (max-width: 768px) {
		.page {
			padding-top: 1rem;
		}
	}
</style>
