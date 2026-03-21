<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { session } from '$lib/session';
	import { getAdminSubject, type AdminSubjectDetail } from '$lib/api/admin';

	let loading = $state(true);
	let error = $state('');
	let subjectId = $state('');
	let subject = $state<AdminSubjectDetail | null>(null);

	onMount(() => {
		const unsub = session.subscribe((s) => {
			if (!s || s.user.role !== 'admin') {
				goto('/admin/login');
			}
		});
		const unsubPage = page.subscribe((p) => {
			subjectId = p.params.id ?? '';
		});
		loadSubject();
		return () => {
			unsub();
			unsubPage();
		};
	});

	async function loadSubject() {
		if (!subjectId) return;
		loading = true;
		error = '';
		try {
			subject = await getAdminSubject(subjectId);
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to load subject';
		} finally {
			loading = false;
		}
	}

	function approvalRate(totalApproved: number, totalQuestions: number) {
		if (!totalQuestions) return '0%';
		return `${Math.round((totalApproved / totalQuestions) * 100)}%`;
	}
</script>

<svelte:head>
	<title>{subject?.name ?? 'Subject'} — Admin Subjects</title>
</svelte:head>

<div class="page">

	{#if loading}
		<div class="center-state glass-panel">
			<div class="spinner"></div>
			<p>Loading subject…</p>
		</div>
	{:else if error}
		<div class="error-banner" role="alert">{error}</div>
	{:else if subject}
		<div class="hero glass-panel animate-fade-in">
			<div class="hero-top">
				<div>
					<p class="eyebrow">{subject.code}</p>
					<h1 class="title font-serif">{subject.name}</h1>
				</div>
			</div>
			{#if subject.description}
				<p class="description">{subject.description}</p>
			{/if}
			<div class="owner-panel">
				<div>
					<span class="owner-label">Teacher</span>
					<strong>{subject.teacher_name || 'Unknown teacher'}</strong>
				</div>
				<div>
					<span class="owner-label">Email</span>
					<strong>{subject.teacher_email || 'No email'}</strong>
				</div>
			</div>
		</div>

		<div class="stats-grid animate-slide-up">
			<div class="stat-card glass-panel">
				<span class="stat-value amber-text">{subject.total_topics}</span>
				<span class="stat-label">Topics</span>
			</div>
			<div class="stat-card glass-panel">
				<span class="stat-value white-text">{subject.total_questions}</span>
				<span class="stat-label">Questions</span>
			</div>
			<div class="stat-card glass-panel">
				<span class="stat-value green-text">{subject.total_approved}</span>
				<span class="stat-label">Approved</span>
			</div>
			<div class="stat-card glass-panel">
				<span class="stat-value red-text">{subject.total_rejected}</span>
				<span class="stat-label">Rejected</span>
			</div>
			<div class="stat-card glass-panel">
				<span class="stat-value orange-text">{subject.total_pending}</span>
				<span class="stat-label">Pending</span>
			</div>
			<div class="stat-card glass-panel">
				<span class="stat-value blue-text">{approvalRate(subject.total_approved, subject.total_questions)}</span>
				<span class="stat-label">Approval Rate</span>
			</div>
		</div>

		<div class="topic-section glass-panel animate-fade-in">
			<div class="section-head">
				<div>
					<h2 class="section-title">Topics</h2>
					<p class="section-subtitle">Topic-by-topic generation and vetting breakdown for this subject.</p>
				</div>
				<span class="topic-count">{subject.topics.length} total</span>
			</div>

			{#if subject.topics.length === 0}
				<div class="center-state compact">
					<p>No topics available for this subject yet.</p>
				</div>
			{:else}
				<div class="topic-list">
					{#each subject.topics as topic, index}
						<div class="topic-card">
							<div class="topic-index">{index + 1}</div>
							<div class="topic-body">
								<div class="topic-header">
									<div>
										<h3 class="topic-name">{topic.name}</h3>
										{#if topic.description}
											<p class="topic-description">{topic.description}</p>
										{/if}
									</div>
									<div class="topic-tags">
										{#if topic.has_syllabus}
											<span class="tag blue">Syllabus</span>
										{/if}
										<span class="tag amber">Order {topic.order_index}</span>
									</div>
								</div>
								<div class="topic-metrics">
									<div class="metric"><span>Questions</span><strong>{topic.total_questions}</strong></div>
									<div class="metric"><span>Approved</span><strong class="green-text">{topic.total_approved}</strong></div>
									<div class="metric"><span>Rejected</span><strong class="red-text">{topic.total_rejected}</strong></div>
									<div class="metric"><span>Pending</span><strong class="orange-text">{topic.total_pending}</strong></div>
									<div class="metric"><span>Approval Rate</span><strong class="blue-text">{approvalRate(topic.total_approved, topic.total_questions)}</strong></div>
								</div>
							</div>
						</div>
					{/each}
				</div>
			{/if}
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
		gap: 1rem;
	}

	.back-btn {
		align-self: flex-start;
		padding: 0.8rem 1rem;
		border-radius: 999px;
		border: 1px solid rgba(255,255,255,0.12);
		background: transparent;
		color: var(--theme-text);
		font: inherit;
		font-weight: 700;
		cursor: pointer;
	}

	.hero,
	.topic-section,
	.center-state {
		padding: 1.25rem;
		border-radius: 1.25rem;
		backdrop-filter: blur(10px) saturate(150%) brightness(1.02) !important;
		-webkit-backdrop-filter: blur(10px) saturate(150%) brightness(1.02) !important;
		background: linear-gradient(
			145deg,
			rgba(255,255,255,0.1) 0%,
			rgba(255,255,255,0.05) 50%,
			rgba(255,255,255,0.08) 100%
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
		align-items: flex-start;
		gap: 1rem;
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

	.summary-chip {
		padding: 0.45rem 0.8rem;
		border-radius: 999px;
		background: rgba(245, 158, 11, 0.15);
		color: #fbbf24;
		font-size: 0.8rem;
		font-weight: 700;
	}

	.description {
		margin: 0.85rem 0 0;
		line-height: 1.65;
		color: var(--theme-text-muted);
	}

	.owner-panel {
		margin-top: 1rem;
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 1rem;
		padding-top: 1rem;
		border-top: 1px solid rgba(255,255,255,0.08);
	}

	.owner-label {
		display: block;
		margin-bottom: 0.2rem;
		font-size: 0.72rem;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		color: var(--theme-text-muted);
		font-weight: 700;
	}

	.stats-grid {
		display: grid;
		grid-template-columns: repeat(6, minmax(0, 1fr));
		gap: 0.75rem;
	}

	.stat-card {
		padding: 1rem;
		border-radius: 1rem;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.2rem;
		backdrop-filter: blur(10px) saturate(150%) brightness(1.02) !important;
		-webkit-backdrop-filter: blur(10px) saturate(150%) brightness(1.02) !important;
		background: linear-gradient(
			145deg,
			rgba(255,255,255,0.1) 0%,
			rgba(255,255,255,0.05) 50%,
			rgba(255,255,255,0.08) 100%
		) !important;
		box-shadow:
			0 8px 40px rgba(0, 0, 0, 0.25),
			inset 0 1px 1px rgba(255, 255, 255, 0.25),
			inset 0 -1px 1px rgba(255, 255, 255, 0.08),
			0 0 0 1px rgba(255, 255, 255, 0.12) !important;
	}

	.stat-value {
		font-size: 1.55rem;
		font-weight: 800;
	}

	.stat-label {
		font-size: 0.7rem;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: var(--theme-text-muted);
		font-weight: 700;
	}

	.section-head {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		gap: 1rem;
		margin-bottom: 1rem;
	}

	.section-title {
		margin: 0;
		font-size: 1.2rem;
		color: var(--theme-text);
	}

	.section-subtitle {
		margin: 0.35rem 0 0;
		color: var(--theme-text-muted);
	}

	.topic-count {
		padding: 0.35rem 0.7rem;
		border-radius: 999px;
		background: rgba(96, 165, 250, 0.15);
		color: #93c5fd;
		font-weight: 700;
		font-size: 0.8rem;
	}

	.topic-list {
		display: flex;
		flex-direction: column;
		gap: 0.85rem;
	}

	.topic-card {
		display: flex;
		gap: 1rem;
		padding: 1rem;
		border-radius: 1rem;
		border: 1px solid rgba(255,255,255,0.08);
		backdrop-filter: blur(10px) saturate(150%) brightness(1.02) !important;
		-webkit-backdrop-filter: blur(10px) saturate(150%) brightness(1.02) !important;
		background: linear-gradient(
			145deg,
			rgba(255,255,255,0.08) 0%,
			rgba(255,255,255,0.04) 50%,
			rgba(255,255,255,0.06) 100%
		) !important;
		box-shadow:
			0 8px 40px rgba(0, 0, 0, 0.22),
			inset 0 1px 1px rgba(255, 255, 255, 0.2),
			inset 0 -1px 1px rgba(255, 255, 255, 0.06),
			0 0 0 1px rgba(255, 255, 255, 0.1) !important;
	}

	.topic-index {
		width: 40px;
		height: 40px;
		border-radius: 50%;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		flex-shrink: 0;
		background: rgba(245, 158, 11, 0.15);
		color: #fbbf24;
		font-weight: 800;
	}

	.topic-body {
		flex: 1;
		display: flex;
		flex-direction: column;
		gap: 0.9rem;
	}

	.topic-header {
		display: flex;
		justify-content: space-between;
		gap: 1rem;
	}

	.topic-name {
		margin: 0;
		font-size: 1rem;
		color: var(--theme-text);
	}

	.topic-description {
		margin: 0.3rem 0 0;
		color: var(--theme-text-muted);
		line-height: 1.55;
	}

	.topic-tags {
		display: flex;
		gap: 0.4rem;
		flex-wrap: wrap;
		justify-content: flex-end;
	}

	.tag {
		padding: 0.25rem 0.55rem;
		border-radius: 999px;
		font-size: 0.72rem;
		font-weight: 700;
	}

	.tag.blue {
		background: rgba(96, 165, 250, 0.15);
		color: #93c5fd;
	}

	.tag.amber {
		background: rgba(245, 158, 11, 0.15);
		color: #fbbf24;
	}

	.topic-metrics {
		display: grid;
		grid-template-columns: repeat(5, minmax(0, 1fr));
		gap: 0.75rem;
	}

	.metric {
		display: flex;
		flex-direction: column;
		gap: 0.12rem;
	}

	.metric span {
		font-size: 0.72rem;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		color: var(--theme-text-muted);
		font-weight: 700;
	}

	.metric strong {
		font-size: 0.95rem;
		color: var(--theme-text);
	}

	.center-state {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.8rem;
		text-align: center;
		color: var(--theme-text-muted);
	}

	.center-state.compact {
		padding: 2rem 1rem;
	}

	.error-banner {
		padding: 0.95rem 1rem;
		border-radius: 1rem;
		background: rgba(239, 68, 68, 0.12);
		border: 1px solid rgba(239, 68, 68, 0.3);
		color: #fca5a5;
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
	.green-text { color: #34d399; }
	.red-text { color: #f87171; }
	.orange-text { color: #fb923c; }

	@keyframes spin {
		to { transform: rotate(360deg); }
	}

	@media (max-width: 960px) {
		.stats-grid {
			grid-template-columns: repeat(3, minmax(0, 1fr));
		}

		.topic-metrics {
			grid-template-columns: repeat(3, minmax(0, 1fr));
		}
	}

	@media (max-width: 640px) {
		.page {
			padding: 1.5rem 1rem 2rem;
		}

		.hero-top,
		.section-head,
		.topic-header {
			flex-direction: column;
		}

		.owner-panel {
			grid-template-columns: 1fr;
		}

		.stats-grid,
		.topic-metrics {
			grid-template-columns: repeat(2, minmax(0, 1fr));
		}

		.topic-card {
			flex-direction: column;
		}
	}
</style>
