<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { session } from '$lib/session';
	import { getQuestionsForVetting, getVetterDashboard, type QuestionForVetting, type VetterDashboard } from '$lib/api/vetting';
	import { listSubjects, getSubject, type SubjectResponse } from '$lib/api/subjects';

	onMount(() => {
		const unsub = session.subscribe((s) => {
			if (!s) goto('/teacher/login');
		});
		loadData();
		return unsub;
	});

	let loading = $state(true);
	let error = $state('');
	let stats = $state<VetterDashboard | null>(null);
	
	// Search and filters
	let searchQuery = $state('');
	let selectedSubjectId = $state('');
	let selectedTopicId = $state('');
	let loadingMore = $state(false);
	let hasMore = $state(true);
	let currentPage = $state(1);
	let allQuestions = $state<QuestionForVetting[]>([]);
	let displayedQuestions = $state<QuestionForVetting[]>([]);
	let subjects = $state<{id: string, name: string}[]>([]);
	let topics = $state<{id: string, name: string, subject_id: string}[]>([]);
	let loadingSubjects = $state(false);
	let loadingTopics = $state(false);

	async function loadData() {
		loading = true;
		error = '';
		try {
			const [dashRes] = await Promise.all([
				getVetterDashboard(),
				loadSubjects()
			]);
			stats = dashRes;
			await loadQuestions();
		} catch (e: any) {
			error = e?.message || 'Failed to load review queue';
		} finally {
			loading = false;
		}
	}

	async function loadQuestions() {
		if (currentPage === 1) {
			loading = true;
		} else {
			loadingMore = true;
		}
		error = '';
		try {
			const res = await getQuestionsForVetting({
				status: 'pending',
				subject_id: selectedSubjectId || undefined,
				topic_id: selectedTopicId || undefined,
				limit: 20,
				page: currentPage,
			});
			if (currentPage === 1) {
				allQuestions = res.questions;
				displayedQuestions = res.questions;
			} else {
				allQuestions = [...allQuestions, ...res.questions];
				displayedQuestions = allQuestions;
			}
			hasMore = res.questions.length === 20;
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to load questions';
		} finally {
			loading = false;
			loadingMore = false;
		}
	}

	async function loadSubjects() {
		loadingSubjects = true;
		try {
			const res = await listSubjects(1, 100);
			subjects = res.subjects.map(s => ({ id: s.id, name: s.name }));
		} catch (e: unknown) {
			console.error('Failed to load subjects:', e);
		} finally {
			loadingSubjects = false;
		}
	}

	async function loadTopics(subjectId: string) {
		loadingTopics = true;
		try {
			const subject = await getSubject(subjectId);
			topics = subject.topics.map(t => ({ id: t.id, name: t.name, subject_id: subjectId }));
		} catch (e: unknown) {
			console.error('Failed to load topics:', e);
		} finally {
			loadingTopics = false;
		}
	}

	async function loadMoreQuestions() {
		if (loadingMore || !hasMore) return;
		loadingMore = true;
		currentPage++;
		await loadQuestions();
	}

	function applyFilters() {
		currentPage = 1;
		allQuestions = [];
		displayedQuestions = [];
		hasMore = true;
		loadQuestions();
	}

	function handleSubjectChange(subjectId: string) {
		selectedSubjectId = subjectId;
		selectedTopicId = '';
		topics = [];
		if (subjectId) {
			loadTopics(subjectId);
		}
		applyFilters();
	}

	function handleTopicChange(topicId: string) {
		selectedTopicId = topicId;
		applyFilters();
	}

	function handleSearch() {
		applyFilters();
	}

	function handleSearchInput(e: Event) {
		const input = e.target as HTMLInputElement;
		searchQuery = input.value;
		

		if (searchQuery.includes(' ')) {
			// Clear existing timeout
			if (searchTimeout) {
				clearTimeout(searchTimeout);
			}
			
			// Set new timeout to search after 500ms of no typing
			searchTimeout = setTimeout(() => {
				applyFilters();
			}, 500);
		}
	}

	let searchTimeout: ReturnType<typeof setTimeout> | null = null;

	function startVerifying(q: QuestionForVetting) {
		const params = q.subject_id ? `?subject=${q.subject_id}` : '';
		goto(`/teacher/train/loop${params}`);
	}

	// Use displayedQuestions as the queue
	let queue = $derived(displayedQuestions);

	function formatTime(iso: string): string {
		const diff = Date.now() - new Date(iso).getTime();
		const mins = Math.floor(diff / 60000);
		if (mins < 1) return 'just now';
		if (mins < 60) return `${mins} min ago`;
		const hrs = Math.floor(mins / 60);
		if (hrs < 24) return `${hrs}h ago`;
		return `${Math.floor(hrs / 24)}d ago`;
	}

	// Intersection Observer for lazy loading
	function intersectionObserver(node: HTMLElement, callback: () => void) {
		const observer = new IntersectionObserver(
			(entries) => {
				if (entries[0].isIntersecting) {
					callback();
				}
			},
			{ threshold: 0.1 }
		);
		
		observer.observe(node);
		
		return {
			destroy() {
				observer.disconnect();
			}
		};
	}

	function typeLabel(t: string): string {
		if (t === 'mcq') return 'MCQ';
		if (t === 'true_false') return 'True/False';
		return 'Short Answer';
	}
</script>

<svelte:head>
	<title>Verifier Mode — VQuest Trainer</title>
</svelte:head>

<div class="verify-page">
	<div class="header animate-fade-in">
		<h1 class="title font-serif">Verifier Mode</h1>
		<p class="subtitle">Review AI-generated questions for quality</p>
	</div>

	<div class="stats-row animate-slide-up">
		<div class="stat glass-panel">
			<span class="stat-value">{stats?.total_pending ?? '—'}</span>
			<span class="stat-label">Pending</span>
		</div>
		<div class="stat glass-panel">
			<span class="stat-value">{stats?.total_approved ?? '—'}</span>
			<span class="stat-label">Approved</span>
		</div>
		<div class="stat glass-panel">
			<span class="stat-value">{stats?.total_rejected ?? '—'}</span>
			<span class="stat-label">Rejected</span>
		</div>
	</div>

	<!-- Search and Filters -->
	<div class="filters-section glass-panel animate-fade-in">
		<div class="filters-row">
			<div class="search-field">
				<input
					type="text"
					placeholder="Search for questions..."
					bind:value={searchQuery}
					class="search-input"
					oninput={handleSearchInput}
				/>
			</div>
			
			<div class="filter-field">
				<select bind:value={selectedSubjectId} onchange={(e) => handleSubjectChange((e.target as HTMLSelectElement).value)} class="filter-select">
					<option value="">All Subjects</option>
					{#each subjects as subject}
						<option value={subject.id}>{subject.name}</option>
					{/each}
				</select>
			</div>
			
			<div class="filter-field">
				<select bind:value={selectedTopicId} onchange={(e) => handleTopicChange((e.target as HTMLSelectElement).value)} class="filter-select" disabled={!selectedSubjectId}>
					<option value="">All Topics</option>
					{#each topics as topic}
						<option value={topic.id}>{topic.name}</option>
					{/each}
				</select>
			</div>
		</div>
	</div>

	{#if loading}
		<div class="empty">
			<div class="spinner"></div>
			<p>Loading review queue…</p>
		</div>
	{:else if error}
		<div class="empty">
			<span class="empty-icon">⚠️</span>
			<p>{error}</p>
			<button class="glass-btn" onclick={loadData}>Retry</button>
		</div>
	{:else if queue.length === 0}
		<div class="empty">
			<span class="empty-icon">✅</span>
			<p>All caught up! No questions to review.</p>
		</div>
	{:else}
		<div class="queue-section animate-slide-up">
			<h2 class="section-title">Review Queue</h2>
			<div class="queue-list">
				{#each queue as item}
					<button class="queue-item glass-panel" onclick={() => startVerifying(item)}>
						<div class="qi-top">
							<span class="qi-type">{typeLabel(item.question_type)}</span>
							{#if item.topic_name}
								<span class="qi-topic">{item.topic_name}</span>
							{/if}
						</div>
						<p class="qi-text">{item.question_text}</p>
						<span class="qi-time">{formatTime(item.generated_at)}</span>
					</button>
				{/each}
			</div>
			
			<!-- Lazy Loading Trigger -->
			{#if hasMore && !loading && queue.length > 0}
				<div class="lazy-load-trigger" use:intersectionObserver={loadMoreQuestions}>
					{#if loadingMore}
						<div class="loading-more">
							<div class="spinner small"></div>
							<p>Loading more questions...</p>
						</div>
					{:else}
						<p class="load-more-hint">Scroll for more questions</p>
					{/if}
				</div>
			{/if}
		</div>
	{/if}
</div>

<style>
	.verify-page {
		max-width: 600px;
		margin: 0 auto;
		padding: 2rem 1.5rem;
		display: flex;
		flex-direction: column;
		gap: 1.5rem;
		min-height: 100vh;
	}

	.header {
		text-align: center;
	}

	.title {
		font-size: 1.75rem;
		font-weight: 800;
		margin: 0 0 0.35rem;
		color: var(--theme-text);
	}

	.subtitle {
		font-size: 0.95rem;
		color: var(--theme-text-muted);
		margin: 0;
	}

	.stats-row {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: 0.75rem;
	}

	.stat {
		display: flex;
		flex-direction: column;
		align-items: center;
		padding: 1rem;
		gap: 0.25rem;
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

	.stat-value {
		font-size: 1.5rem;
		font-weight: 800;
		color: var(--theme-text);
	}

	.stat-label {
		font-size: 0.75rem;
		font-weight: 600;
		color: var(--theme-text-muted);
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}

	.section-title {
		font-size: 1rem;
		font-weight: 700;
		color: var(--theme-text-muted);
		margin: 0;
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}

	.queue-list {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
		margin-top: 0.75rem;
	}

	.queue-item {
		text-align: left;
		cursor: pointer;
		padding: 1rem 1.25rem;
		width: 100%;
		border: 1px solid rgba(255, 255, 255, 0.1);
		border-radius: var(--glass-radius);
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

	.qi-top {
		display: flex;
		gap: 0.5rem;
		margin-bottom: 0.5rem;
	}

	.qi-type {
		font-size: 0.7rem;
		font-weight: 700;
		padding: 0.15rem 0.5rem;
		background: rgba(var(--theme-primary-rgb), 0.15);
		color: var(--theme-primary);
		border-radius: 4px;
		text-transform: uppercase;
	}

	.qi-topic {
		font-size: 0.7rem;
		font-weight: 600;
		padding: 0.15rem 0.5rem;
		background: rgba(255, 255, 255, 0.08);
		color: var(--theme-text-muted);
		border-radius: 4px;
	}

	.qi-text {
		font-size: 0.92rem;
		color: var(--theme-text);
		margin: 0;
		line-height: 1.4;
		display: -webkit-box;
		-webkit-line-clamp: 2;
		line-clamp: 2;
		-webkit-box-orient: vertical;
		overflow: hidden;
	}

	.qi-time {
		font-size: 0.75rem;
		color: var(--theme-text-muted);
		margin-top: 0.5rem;
		display: block;
	}

	.empty {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.75rem;
		padding: 3rem;
		text-align: center;
	}

	.empty-icon {
		font-size: 3rem;
	}

	.empty p {
		color: var(--theme-text-muted);
		margin: 0;
	}

	.spinner {
		width: 2rem;
		height: 2rem;
		border: 3px solid rgba(var(--theme-primary-rgb), 0.2);
		border-top-color: var(--theme-primary);
		border-radius: 50%;
		animation: spin 0.7s linear infinite;
	}

	@keyframes spin {
		to { transform: rotate(360deg); }
	}

	@media (max-width: 768px) {
		.verify-page {
			padding: 1.5rem 1rem;
			gap: 1.25rem;
		}

		.title {
			font-size: 1.5rem;
		}

		.subtitle {
			font-size: 0.9rem;
		}

		.stats-row {
			gap: 0.5rem;
		}

		.stat {
			padding: 0.85rem 0.5rem;
		}

		.stat-value {
			font-size: 1.3rem;
		}

		.stat-label {
			font-size: 0.7rem;
		}

		.section-title {
			font-size: 0.9rem;
		}

		.queue-item {
			padding: 0.9rem 1rem;
		}

		.qi-text {
			font-size: 0.88rem;
		}
	}

	@media (max-width: 480px) {
		.verify-page {
			padding: 1.25rem 0.75rem;
			gap: 1rem;
		}

		.title {
			font-size: 1.35rem;
		}

		.subtitle {
			font-size: 0.85rem;
		}

		.stats-row {
			gap: 0.4rem;
		}

		.stat {
			padding: 0.75rem 0.4rem;
			border-radius: 10px;
		}

		.stat-value {
			font-size: 1.15rem;
		}

		.stat-label {
			font-size: 0.65rem;
		}

		.section-title {
			font-size: 0.82rem;
		}

		.queue-list {
			gap: 0.6rem;
			margin-top: 0.6rem;
		}

		.queue-item {
			padding: 0.8rem 0.9rem;
			border-radius: 10px;
		}

		.qi-top {
			gap: 0.35rem;
			margin-bottom: 0.4rem;
		}

		.qi-type,
		.qi-topic {
			font-size: 0.65rem;
			padding: 0.1rem 0.4rem;
		}

		.qi-text {
			font-size: 0.82rem;
		}

		.qi-time {
			font-size: 0.7rem;
			margin-top: 0.4rem;
		}

		.empty {
			padding: 2rem 0.75rem;
		}

		.empty-icon {
			font-size: 2.5rem;
		}

		.empty p {
			font-size: 0.9rem;
		}
	}

	/* Search and Filters */
	.filters-section {
		padding: 1rem;
	}

	.filters-row {
		display: flex;
		gap: 1rem;
		align-items: center;
		flex-wrap: wrap;
	}

	.search-field {
		flex: 1;
		min-width: 200px;
	}

	.search-input {
		width: 100%;
		padding: 0.6rem 1rem;
		border: 1px solid rgba(255, 255, 255, 0.14);
		border-radius: 10px;
		background: rgba(255, 255, 255, 0.06);
		color: var(--theme-text);
		font-family: inherit;
	}

	.search-input::placeholder {
		color: rgba(255, 255, 255, 0.5);
		opacity: 1;
	}

	.search-input:focus {
		outline: none;
		border-color: var(--theme-primary);
		box-shadow: 0 0 0 2px rgba(var(--theme-primary-rgb), 0.15);
	}

	.filter-field {
		min-width: 140px;
		flex-shrink: 0;
	}

	.filter-select {
		width: 100%;
		padding: 0.6rem 1rem;
		border: 1px solid rgba(255, 255, 255, 0.14);
		border-radius: 10px;
		background: rgba(255, 255, 255, 0.06);
		color: var(--theme-text);
		font-family: inherit;
	}

	.filter-select:focus {
		outline: none;
		border-color: var(--theme-primary);
		box-shadow: 0 0 0 2px rgba(var(--theme-primary-rgb), 0.15);
	}

	.filter-select:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	/* Lazy Loading */
	.lazy-load-trigger {
		text-align: center;
		padding: 2rem 1rem;
		color: var(--theme-text-muted);
	}

	.loading-more {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 0.5rem;
	}

	.spinner.small {
		width: 20px;
		height: 20px;
		border: 2px solid rgba(255, 255, 255, 0.1);
		border-top: 2px solid var(--theme-primary);
		border-radius: 50%;
		animation: spin 1s linear infinite;
	}

	.load-more-hint {
		font-size: 0.9rem;
		opacity: 0.7;
	}

	/* Mobile optimizations */
	@media (max-width: 768px) {
		.filters-row {
			flex-direction: column;
			gap: 0.75rem;
		}

		.search-field {
			min-width: 100%;
		}

		.filter-field {
			min-width: 100%;
		}

		.search-input,
		.filter-select {
			padding: 0.8rem 1rem;
			font-size: 16px; /* Prevents zoom on iOS */
		}
	}

	@media (max-width: 480px) {
		.filters-section {
			padding: 0.75rem;
		}

		.filters-row {
			gap: 0.5rem;
		}
	}
</style>
