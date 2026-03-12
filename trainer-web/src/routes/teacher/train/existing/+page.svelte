<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { session } from '$lib/session';
	import GlassCard from '$lib/components/GlassCard.svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import { listSubjects, type SubjectResponse } from '$lib/api/subjects';

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

	function openSubject(id: string) {
		goto(`/teacher/train/loop?subject=${id}`);
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

<PageHeader title="Existing Topics" backHref="/teacher/train" />

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
				<button class="subject-card glass-card" onclick={() => openSubject(s.id)}>
					<div class="sc-top">
						<span class="sc-code">{s.code}</span>

					</div>
					<h2 class="sc-name">{s.name}</h2>
					{#if s.description}
						<p class="sc-desc">{s.description}</p>
					{/if}
					<div class="sc-stats">
						<span class="sc-stat">📝 {s.total_questions} questions</span>
						<span class="sc-stat">📚 {s.total_topics} topics</span>
						<span class="sc-stat">📅 {formatDate(s.created_at)}</span>
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

	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}

	.err-icon {
		font-size: 2rem;
	}

	.err-msg {
		color: #e94560 !important;
	}

	.empty-icon {
		font-size: 3rem;
	}

	.subject-list {
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}

	.subject-card {
		text-align: left;
		cursor: pointer;
		padding: 1.25rem 1.5rem;
		width: 100%;
		font-family: inherit;
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
		.page {
			padding-top: 1rem;
		}
	}
</style>
