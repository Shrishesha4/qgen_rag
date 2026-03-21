<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { session } from '$lib/session';
	import { listSubjects, type SubjectResponse } from '$lib/api/subjects';

	let loading = $state(true);
	let error = $state('');
	let subjects = $state<SubjectResponse[]>([]);
	let query = $state('');

	onMount(() => {
		const unsub = session.subscribe((s) => {
			if (!s || s.user.role !== 'teacher') {
				goto('/teacher/login');
			}
		});
		loadSubjects();
		return unsub;
	});

	async function loadSubjects() {
		loading = true;
		error = '';
		try {
			const response = await listSubjects(1, 100);
			subjects = response.subjects;
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
			return [subject.name, subject.code, subject.description ?? ''].some((value) =>
				value.toLowerCase().includes(search)
			);
		});
	});

	const totals = $derived.by(() => {
		return filteredSubjects.reduce(
			(acc, subject) => {
				acc.totalTopics += subject.total_topics;
				acc.totalQuestions += subject.total_questions;
				return acc;
			},
			{ totalTopics: 0, totalQuestions: 0 }
		);
	});

	function openSubject(subjectId: string) {
		goto(`/teacher/subjects/${subjectId}`);
	}

	function goToAddSubject() {
		goto('/teacher/train/new');
	}

	function formatDate(value: string) {
		return new Date(value).toLocaleDateString();
	}
</script>

<svelte:head>
	<title>Subjects - Teacher Console</title>
</svelte:head>

<div class="page">
	<div class="hero animate-fade-in">
		<div>
			<p class="eyebrow">Teacher Console</p>
			<h1 class="title font-serif">Subjects</h1>
			<p class="subtitle">Browse your subjects and jump into topic-level generation or vetting.</p>
		</div>
	</div>

	<div class="toolbar animate-slide-up">
		<input class="search-input" bind:value={query} placeholder="Search by subject, code, or description" />
		<button class="add-subject-btn" onclick={goToAddSubject}>+ Add Subject</button>
		<!-- <button class="refresh-btn" onclick={loadSubjects}>Refresh</button> -->
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
	</div>

	{#if loading}
		<div class="center-state">
			<div class="spinner"></div>
			<p>Loading subjects...</p>
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
					</div>
					<h2 class="subject-name">{subject.name}</h2>
					{#if subject.description}
						<p class="subject-desc">{subject.description}</p>
					{/if}
					<div class="metrics-grid">
						<div class="metric"><span>Topics</span><strong>{subject.total_topics}</strong></div>
						<div class="metric"><span>Questions</span><strong>{subject.total_questions}</strong></div>
						<div class="metric"><span>Created</span><strong>{formatDate(subject.created_at)}</strong></div>
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

	.eyebrow {
		margin: 0 0 0.35rem;
		font-size: 0.78rem;
		font-weight: 700;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: var(--theme-primary);
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
		padding: 0;
		border-radius: 0;
	}

	.add-subject-btn {
		padding: 0.85rem 1.15rem;
		border-radius: 999px;
		border: 1px solid rgba(var(--theme-primary-rgb), 0.45);
		background: rgba(var(--theme-primary-rgb), 0.18);
		color: var(--theme-text-primary);
		font: inherit;
		font-weight: 800;
		white-space: nowrap;
		cursor: pointer;
		transition: background 0.15s ease, border-color 0.15s ease, transform 0.15s ease;
	}

	.add-subject-btn:hover {
		background: rgba(var(--theme-primary-rgb), 0.24);
		border-color: rgba(var(--theme-primary-rgb), 0.58);
		transform: translateY(-1px);
	}

	.search-input {
		flex: 1;
		padding: 0.85rem 1rem;
		border-radius: 0.85rem;
		border: 1px solid rgba(17, 24, 39, 0.14);
		background: rgba(255, 255, 255, 0.78);
		color: var(--theme-text-primary);
		font: inherit;
	}

	.search-input::placeholder {
		color: var(--theme-text-muted);
	}

	/* .refresh-btn {
		padding: 0.85rem 1rem;
		border-radius: 0.85rem;
		border: 1px solid rgba(245, 158, 11, 0.3);
		background: rgba(245, 158, 11, 0.15);
		color: #b45309;
		font: inherit;
		font-weight: 700;
		cursor: pointer;
	} */

	.error-banner {
		padding: 0.9rem 1rem;
		border-radius: 1rem;
		background: rgba(239, 68, 68, 0.12);
		border: 1px solid rgba(239, 68, 68, 0.3);
		color: #b91c1c;
	}

	.stats-row {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
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
		transition: transform 0.2s ease;
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
	/* .coverage-chip {
		font-size: 0.72rem;
		font-weight: 700;
		padding: 0.28rem 0.6rem;
		border-radius: 999px;
	} */

	.subject-code {
		background: rgba(var(--theme-primary-rgb), 0.16);
		color: var(--theme-primary);
	}

	/* .coverage-chip {
		background: rgba(245, 158, 11, 0.16);
		color: #b45309;
	} */

	.subject-name {
		margin: 0.9rem 0 0.35rem;
		font-size: 1.2rem;
		color: var(--theme-text-primary);
	}

	.subject-desc {
		margin: 0;
		color: var(--theme-text-muted);
		line-height: 1.55;
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
		color: var(--theme-text-primary);
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
		border-top-color: var(--theme-primary);
		animation: spin 0.8s linear infinite;
	}

	.amber-text { color: var(--theme-primary); }
	.blue-text { color: var(--theme-primary); }
	.white-text { color: var(--theme-text-primary); }

	@keyframes spin {
		to { transform: rotate(360deg); }
	}

	@media (max-width: 920px) {
		.page {
			gap: 0.85rem;
			padding: 1.1rem 0.9rem 1.5rem;
		}

		.toolbar {
			flex-direction: column;
		}

		.add-subject-btn {
			width: 100%;
		}

		.subject-grid {
			grid-template-columns: 1fr;
			gap: 0.75rem;
		}

		.stats-row {
			order: 2;
			grid-template-columns: repeat(3, minmax(0, 1fr));
			gap: 0.5rem;
		}

		.toolbar {
			order: 3;
			padding: 0.75rem;
			gap: 0.55rem;
		}

		.search-input {
			padding: 0.72rem 0.8rem;
			font-size: 0.9rem;
		}

		/* .refresh-btn {
			padding: 0.72rem 0.82rem;
			font-size: 0.85rem;
		} */

		.stat-card {
			padding: 0.62rem 0.4rem;
			border-radius: 0.85rem;
			gap: 0.06rem;
		}

		.stat-value {
			font-size: 1.05rem;
		}

		.stat-label {
			font-size: 0.62rem;
		}

		.subject-card {
			padding: 0.88rem;
			border-radius: 1rem;
		}

		.card-top {
			gap: 0.45rem;
		}

		.subject-name {
			margin: 0.55rem 0 0.2rem;
			font-size: 1.05rem;
		}

		.subject-desc {
			margin: 0;
			font-size: 0.82rem;
			line-height: 1.35;
			display: -webkit-box;
			line-clamp: 2;
			-webkit-line-clamp: 2;
			-webkit-box-orient: vertical;
			overflow: hidden;
		}

		.metrics-grid {
			grid-template-columns: repeat(3, minmax(0, 1fr));
			gap: 0.45rem;
			margin-top: 0.55rem;
		}

		.metric span {
			font-size: 0.6rem;
		}

		.metric strong {
			font-size: 0.82rem;
		}

		.subject-code{
			font-size: 0.64rem;
			padding: 0.22rem 0.45rem;
		}
		/* .subject-code,
		.coverage-chip {
			font-size: 0.64rem;
			padding: 0.22rem 0.45rem;
		} */
	}

	@media (max-width: 420px) {
		.title {
			font-size: 1.72rem;
		}

		.subtitle {
			font-size: 0.88rem;
			line-height: 1.45;
		}

		.search-input {
			min-width: 0;
		}

		.metrics-grid {
			gap: 0.38rem;
		}
	}
</style>
