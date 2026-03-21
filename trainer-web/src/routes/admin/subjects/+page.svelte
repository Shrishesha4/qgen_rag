<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { session } from '$lib/session';
	import { listAdminSubjects, type AdminSubjectSummary } from '$lib/api/admin';

	let loading = $state(true);
	let error = $state('');
	let subjects = $state<AdminSubjectSummary[]>([]);
	let query = $state('');

	onMount(() => {
		const unsub = session.subscribe((s) => {
			if (!s || s.user.role !== 'admin') {
				goto('/admin/login');
			}
		});
		loadSubjects();
		return unsub;
	});

	async function loadSubjects() {
		loading = true;
		error = '';
		try {
			subjects = await listAdminSubjects();
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to load subjects';
		} finally {
			loading = false;
		}
	}

	const filteredSubjects = $derived.by(() => {
		const search = query.trim().toLowerCase();
		if (!search) return subjects;
		return subjects.filter((subject) => {
			return [
				subject.name,
				subject.code,
				subject.teacher_name ?? '',
				subject.teacher_email ?? ''
			].some((value) => value.toLowerCase().includes(search));
		});
	});

	const totals = $derived.by(() => {
		return filteredSubjects.reduce(
			(acc, subject) => {
				acc.totalTopics += subject.total_topics;
				acc.totalQuestions += subject.total_questions;
				acc.totalPending += subject.total_pending;
				return acc;
			},
			{ totalTopics: 0, totalQuestions: 0, totalPending: 0 }
		);
	});

	function openSubject(subjectId: string) {
		goto(`/admin/subjects/${subjectId}`);
	}

	function formatDate(value: string) {
		return new Date(value).toLocaleDateString();
	}
</script>

<svelte:head>
	<title>Admin Subjects — VQuest Trainer</title>
</svelte:head>

<div class="page">
	<div class="hero animate-fade-in">
		<div>
			<p class="eyebrow">Admin Console</p>
			<h1 class="title font-serif">Subjects</h1>
			<p class="subtitle">Browse every subject, see ownership, question inventory, and drill into topic-level vetting status.</p>
		</div>
	</div>

	<div class="toolbar glass-panel animate-slide-up">
		<input class="search-input" bind:value={query} placeholder="Search by subject, code, teacher, or email" />
		<button class="refresh-btn" onclick={loadSubjects}>Refresh</button>
	</div>

	{#if error}
		<div class="error-banner" role="alert">{error}</div>
	{/if}

	<div class="stats-row animate-slide-up">
		<div class="stat-card glass-panel">
			<span class="stat-value amber-text">{loading ? '…' : filteredSubjects.length}</span>
			<span class="stat-label">Subjects</span>
		</div>
		<div class="stat-card glass-panel">
			<span class="stat-value blue-text">{loading ? '…' : totals.totalTopics}</span>
			<span class="stat-label">Topics</span>
		</div>
		<div class="stat-card glass-panel">
			<span class="stat-value white-text">{loading ? '…' : totals.totalQuestions}</span>
			<span class="stat-label">Questions</span>
		</div>
		<div class="stat-card glass-panel">
			<span class="stat-value orange-text">{loading ? '…' : totals.totalPending}</span>
			<span class="stat-label">Pending</span>
		</div>
	</div>

	{#if loading}
		<div class="center-state">
			<div class="spinner"></div>
			<p>Loading subjects…</p>
		</div>
	{:else if filteredSubjects.length === 0}
		<div class="center-state glass-panel">
			<p>No subjects matched your search.</p>
		</div>
	{:else}
		<div class="subject-grid animate-fade-in">
			{#each filteredSubjects as subject}
				<button class="subject-card glass-panel" onclick={() => openSubject(subject.id)}>
					<div class="card-top">
						<span class="subject-code">{subject.code}</span>
						<span class="coverage-chip">{subject.syllabus_coverage}% coverage</span>
					</div>
					<h2 class="subject-name">{subject.name}</h2>
					{#if subject.description}
						<p class="subject-desc">{subject.description}</p>
					{/if}
					<div class="owner-block">
						<span class="owner-name">{subject.teacher_name || 'Unknown teacher'}</span>
						<span class="owner-email">{subject.teacher_email || 'No email'}</span>
					</div>
					<div class="metrics-grid">
						<div class="metric"><span>Topics</span><strong>{subject.total_topics}</strong></div>
						<div class="metric"><span>Questions</span><strong>{subject.total_questions}</strong></div>
						<div class="metric"><span>Approved</span><strong class="green-text">{subject.total_approved}</strong></div>
						<div class="metric"><span>Rejected</span><strong class="red-text">{subject.total_rejected}</strong></div>
						<div class="metric"><span>Pending</span><strong class="orange-text">{subject.total_pending}</strong></div>
						<div class="metric"><span>Created</span><strong>{formatDate(subject.created_at)}</strong></div>
					</div>
					<div class="card-footer">
						<span>Open subject</span>
						<span class="arrow">→</span>
					</div>
				</button>
			{/each}
		</div>
	{/if}
</div>

<style>
	.page {
		max-width: 1120px;
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
		max-width: 48rem;
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
		flex: 1;
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

	.refresh-btn {
		padding: 0.85rem 1rem;
		border-radius: 0.85rem;
		border: 1px solid rgba(245, 158, 11, 0.3);
		background: rgba(245, 158, 11, 0.15);
		color: #fbbf24;
		font: inherit;
		font-weight: 700;
		cursor: pointer;
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

	.subject-grid {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 1rem;
	}

	.subject-card {
		padding: 1.25rem;
		border-radius: 1.25rem;
		text-align: left;
		border: 1px solid rgba(255, 255, 255, 0.12);
		cursor: pointer;
		color: inherit;
		transition: transform 0.2s ease, box-shadow 0.2s ease;
	}

	.subject-card:hover {
		transform: translateY(-2px);
	}

	.card-top {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 0.75rem;
	}

	.subject-code,
	.coverage-chip {
		font-size: 0.72rem;
		font-weight: 700;
		padding: 0.28rem 0.6rem;
		border-radius: 999px;
	}

	.subject-code {
		background: rgba(96, 165, 250, 0.16);
		color: #93c5fd;
	}

	.coverage-chip {
		background: rgba(245, 158, 11, 0.16);
		color: #fbbf24;
	}

	.subject-name {
		margin: 0.9rem 0 0.35rem;
		font-size: 1.2rem;
		color: var(--theme-text);
	}

	.subject-desc {
		margin: 0;
		color: var(--theme-text-muted);
		line-height: 1.55;
	}

	.owner-block {
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
		margin-top: 1rem;
		padding-top: 0.9rem;
		border-top: 1px solid rgba(255,255,255,0.08);
	}

	.owner-name {
		font-weight: 700;
		color: var(--theme-text);
	}

	.owner-email {
		font-size: 0.8rem;
		color: var(--theme-text-muted);
	}

	.metrics-grid {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 0.75rem;
		margin-top: 1rem;
	}

	.metric {
		display: flex;
		flex-direction: column;
		gap: 0.1rem;
	}

	.metric span {
		font-size: 0.72rem;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		color: var(--theme-text-muted);
	}

	.metric strong {
		font-size: 0.96rem;
		color: var(--theme-text);
	}

	.card-footer {
		margin-top: 1rem;
		padding-top: 0.9rem;
		display: flex;
		justify-content: space-between;
		align-items: center;
		border-top: 1px solid rgba(255,255,255,0.08);
		color: #fbbf24;
		font-weight: 700;
	}

	.arrow {
		font-size: 1.15rem;
	}

	.center-state {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.8rem;
		padding: 3rem 1rem;
		text-align: center;
		color: var(--theme-text-muted);
		border-radius: 1rem;
	}

	.spinner {
		width: 30px;
		height: 30px;
		border-radius: 50%;
		border: 3px solid rgba(255,255,255,0.14);
		border-top-color: #fbbf24;
		animation: spin 0.8s linear infinite;
	}

	.amber-text { color: #f59e0b; }
	.blue-text { color: #60a5fa; }
	.white-text { color: var(--theme-text); }
	.orange-text { color: #fb923c; }
	.green-text { color: #34d399; }
	.red-text { color: #f87171; }

	@keyframes spin {
		to { transform: rotate(360deg); }
	}

	@media (max-width: 900px) {
		.subject-grid {
			grid-template-columns: 1fr;
		}
	}

	@media (max-width: 640px) {
		.page {
			padding: 1.5rem 1rem 2rem;
		}

		.toolbar {
			flex-direction: column;
		}

		.stats-row {
			grid-template-columns: repeat(2, minmax(0, 1fr));
		}

		.metrics-grid {
			grid-template-columns: repeat(2, minmax(0, 1fr));
		}
	}
</style>
