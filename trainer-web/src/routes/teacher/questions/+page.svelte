<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { listTeacherQuestions, type TeacherQuestionFeedParams, type TeacherQuestionSummary } from '$lib/api/questions';
	import { session } from '$lib/session';

	const PAGE_SIZE = 50;

	type StatusFilter = 'all' | 'pending' | 'approved' | 'rejected';
	type SortKey = 'generated_at' | 'question_text' | 'subject_name' | 'topic_name' | 'vetting_status' | 'question_type';
	type SortDirection = 'asc' | 'desc';

	let loading = $state(true);
	let error = $state('');
	let questions = $state<TeacherQuestionSummary[]>([]);
	let totalQuestions = $state(0);
	let totalPages = $state(0);
	let pageNumber = $state(1);
	let searchDraft = $state('');
	let selectedStatus = $state<StatusFilter>('all');
	let groupId = $state('');
	let groupName = $state('');
	let subjectId = $state('');
	let subjectName = $state('');
	let subjectCode = $state('');
	let topicId = $state('');
	let topicName = $state('');
	let searchQuery = $state('');
	let sortKey = $state<SortKey>('generated_at');
	let sortDirection = $state<SortDirection>('desc');
	let requestSequence = 0;
	let routeSignature = '';

	const sortedQuestions = $derived.by(() => {
		const nextQuestions = [...questions];
		nextQuestions.sort((left, right) => compareQuestions(left, right, sortKey, sortDirection));
		return nextQuestions;
	});

	const activeScopeLabels = $derived.by(() => {
		const labels: string[] = [];
		if (groupName) labels.push(`Group: ${groupName}`);
		if (subjectName) labels.push(subjectCode ? `Subject: ${subjectName} (${subjectCode})` : `Subject: ${subjectName}`);
		if (topicName) labels.push(`Topic: ${topicName}`);
		return labels;
	});

	onMount(() => {
		const unsubSession = session.subscribe((currentSession) => {
			if (!currentSession || currentSession.user.role !== 'teacher') {
				goto('/teacher/login');
			}
		});

		const unsubPage = page.subscribe(($page) => {
			applyRoute($page.url.searchParams);
		});

		return () => {
			unsubSession();
			unsubPage();
		};
	});

	function normalizeStatus(value: string | null): StatusFilter {
		if (value === 'pending' || value === 'approved' || value === 'rejected') {
			return value;
		}
		return 'all';
	}

	function normalizePage(value: string | null): number {
		const parsed = Number.parseInt(value || '', 10);
		return Number.isFinite(parsed) && parsed > 0 ? parsed : 1;
	}

	function applyRoute(searchParams: URLSearchParams) {
		const nextGroupId = searchParams.get('group_id') ?? '';
		const nextGroupName = searchParams.get('group_name') ?? '';
		const nextSubjectId = searchParams.get('subject_id') ?? '';
		const nextSubjectName = searchParams.get('subject_name') ?? '';
		const nextSubjectCode = searchParams.get('subject_code') ?? '';
		const nextTopicId = searchParams.get('topic_id') ?? '';
		const nextTopicName = searchParams.get('topic_name') ?? '';
		const nextSearchQuery = searchParams.get('search') ?? '';
		const nextStatus = normalizeStatus(searchParams.get('vetting_status'));
		const nextPage = normalizePage(searchParams.get('page'));

		const nextSignature = JSON.stringify({
			groupId: nextGroupId,
			groupName: nextGroupName,
			subjectId: nextSubjectId,
			subjectName: nextSubjectName,
			subjectCode: nextSubjectCode,
			topicId: nextTopicId,
			topicName: nextTopicName,
			searchQuery: nextSearchQuery,
			selectedStatus: nextStatus,
			pageNumber: nextPage,
		});

		if (nextSignature === routeSignature) {
			return;
		}

		routeSignature = nextSignature;
		groupId = nextGroupId;
		groupName = nextGroupName;
		subjectId = nextSubjectId;
		subjectName = nextSubjectName;
		subjectCode = nextSubjectCode;
		topicId = nextTopicId;
		topicName = nextTopicName;
		searchQuery = nextSearchQuery;
		searchDraft = nextSearchQuery;
		selectedStatus = nextStatus;
		pageNumber = nextPage;
		void loadQuestions();
	}

	function currentFilters(): TeacherQuestionFeedParams {
		return {
			group_id: groupId || undefined,
			subject_id: subjectId || undefined,
			topic_id: topicId || undefined,
			vetting_status: selectedStatus,
			search: searchQuery || undefined,
			page: pageNumber,
			limit: PAGE_SIZE,
		};
	}

	async function loadQuestions() {
		const requestId = ++requestSequence;
		loading = true;
		error = '';
		try {
			const response = await listTeacherQuestions(currentFilters());
			if (requestId !== requestSequence) {
				return;
			}
			questions = response.questions;
			totalQuestions = response.total;
			totalPages = response.pages;
		} catch (value: unknown) {
			if (requestId !== requestSequence) {
				return;
			}
			error = value instanceof Error ? value.message : 'Failed to load questions';
			questions = [];
			totalQuestions = 0;
			totalPages = 0;
		} finally {
			if (requestId === requestSequence) {
				loading = false;
			}
		}
	}

	function buildRoute(overrides: {
		groupId?: string;
		groupName?: string;
		subjectId?: string;
		subjectName?: string;
		subjectCode?: string;
		topicId?: string;
		topicName?: string;
		searchQuery?: string;
		status?: StatusFilter;
		page?: number;
	}) {
		const searchParams = new URLSearchParams();
		const nextGroupId = overrides.groupId ?? groupId;
		const nextGroupName = overrides.groupName ?? groupName;
		const nextSubjectId = overrides.subjectId ?? subjectId;
		const nextSubjectName = overrides.subjectName ?? subjectName;
		const nextSubjectCode = overrides.subjectCode ?? subjectCode;
		const nextTopicId = overrides.topicId ?? topicId;
		const nextTopicName = overrides.topicName ?? topicName;
		const nextSearchQuery = overrides.searchQuery ?? searchQuery;
		const nextStatus = overrides.status ?? selectedStatus;
		const nextPage = overrides.page ?? pageNumber;

		if (nextGroupId) searchParams.set('group_id', nextGroupId);
		if (nextGroupName) searchParams.set('group_name', nextGroupName);
		if (nextSubjectId) searchParams.set('subject_id', nextSubjectId);
		if (nextSubjectName) searchParams.set('subject_name', nextSubjectName);
		if (nextSubjectCode) searchParams.set('subject_code', nextSubjectCode);
		if (nextTopicId) searchParams.set('topic_id', nextTopicId);
		if (nextTopicName) searchParams.set('topic_name', nextTopicName);
		if (nextSearchQuery.trim()) searchParams.set('search', nextSearchQuery.trim());
		if (nextStatus !== 'all') searchParams.set('vetting_status', nextStatus);
		if (nextPage > 1) searchParams.set('page', String(nextPage));

		const suffix = searchParams.toString() ? `?${searchParams.toString()}` : '';
		return `/teacher/questions${suffix}`;
	}

	function navigateWithFilters(overrides: {
		groupId?: string;
		groupName?: string;
		subjectId?: string;
		subjectName?: string;
		subjectCode?: string;
		topicId?: string;
		topicName?: string;
		searchQuery?: string;
		status?: StatusFilter;
		page?: number;
	}) {
		goto(buildRoute(overrides), { replaceState: true, noScroll: true, keepFocus: true });
	}

	function submitSearch(event: SubmitEvent) {
		event.preventDefault();
		navigateWithFilters({ searchQuery: searchDraft, page: 1 });
	}

	function clearSearch() {
		searchDraft = '';
		navigateWithFilters({ searchQuery: '', page: 1 });
	}

	function setStatusFilter(status: StatusFilter) {
		navigateWithFilters({ status, page: 1 });
	}

	function clearScope() {
		navigateWithFilters({
			groupId: '',
			groupName: '',
			subjectId: '',
			subjectName: '',
			subjectCode: '',
			topicId: '',
			topicName: '',
			page: 1,
		});
	}

	function setPage(nextPage: number) {
		if (nextPage < 1) return;
		if (totalPages > 0 && nextPage > totalPages) return;
		navigateWithFilters({ page: nextPage });
	}

	function toggleSort(nextSortKey: SortKey) {
		if (sortKey === nextSortKey) {
			sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
			return;
		}
		sortKey = nextSortKey;
		sortDirection = nextSortKey === 'generated_at' ? 'desc' : 'asc';
	}

	function compareQuestions(
		left: TeacherQuestionSummary,
		right: TeacherQuestionSummary,
		activeSortKey: SortKey,
		activeSortDirection: SortDirection,
	): number {
		const direction = activeSortDirection === 'asc' ? 1 : -1;
		const leftValue = getSortValue(left, activeSortKey);
		const rightValue = getSortValue(right, activeSortKey);
		if (leftValue < rightValue) return -1 * direction;
		if (leftValue > rightValue) return 1 * direction;
		return 0;
	}

	function getSortValue(question: TeacherQuestionSummary, activeSortKey: SortKey): number | string {
		switch (activeSortKey) {
			case 'generated_at':
				return Date.parse(question.generated_at) || 0;
			case 'question_text':
				return question.question_text.toLowerCase();
			case 'subject_name':
				return `${question.subject_name ?? ''} ${question.subject_code ?? ''}`.trim().toLowerCase();
			case 'topic_name':
				return (question.topic_name ?? '').toLowerCase();
			case 'vetting_status':
				return (question.vetting_status ?? '').toLowerCase();
			case 'question_type':
				return question.question_type.toLowerCase();
		}
	}

	function sortIndicator(key: SortKey): string {
		if (sortKey !== key) return 'Sort';
		return sortDirection === 'asc' ? 'Asc' : 'Desc';
	}

	function formatTimestamp(value: string): string {
		const timestamp = Date.parse(value);
		if (!Number.isFinite(timestamp)) {
			return 'Unknown';
		}
		return new Date(timestamp).toLocaleString();
	}

	function statusLabel(status: string | null): string {
		if (!status) return 'Unknown';
		return status.charAt(0).toUpperCase() + status.slice(1);
	}
</script>

<div class="page">
	<div class="hero glass-panel">
		<div>
			<p class="eyebrow">Teacher Questions</p>
			<h1>Question drilldown</h1>
			<p class="hero-copy">Row-based question review for the current teacher scope, with sortable columns and direct filtering from dashboard count clicks.</p>
		</div>
		<div class="hero-meta">
			<span>{totalQuestions} matching questions</span>
			{#if totalPages > 1}
				<span>Page {pageNumber} of {totalPages}</span>
			{/if}
		</div>
	</div>

	<div class="toolbar glass-panel">
		<form class="search-form" onsubmit={submitSearch}>
			<input class="search-input" bind:value={searchDraft} placeholder="Search question text, answers, or explanations" />
			<button class="table-btn primary" type="submit">Search</button>
			{#if searchQuery}
				<button class="table-btn" type="button" onclick={clearSearch}>Clear</button>
			{/if}
		</form>
		<div class="status-strip" role="tablist" aria-label="Question status filters">
			{#each ['all', 'pending', 'approved', 'rejected'] as statusOption}
				<button class="status-pill" class:active={selectedStatus === statusOption} type="button" onclick={() => setStatusFilter(statusOption as StatusFilter)}>
					{statusOption === 'all' ? 'All statuses' : statusLabel(statusOption)}
				</button>
			{/each}
		</div>
		{#if activeScopeLabels.length > 0}
			<div class="scope-strip">
				{#each activeScopeLabels as label}
					<span class="scope-pill">{label}</span>
				{/each}
				<button class="scope-clear" type="button" onclick={clearScope}>Clear scope</button>
			</div>
		{/if}
	</div>

	<div class="table-shell glass-panel">
		{#if loading}
			<div class="state-message">Loading questions...</div>
		{:else if error}
			<div class="state-message error">{error}</div>
		{:else if sortedQuestions.length === 0}
			<div class="state-message">No questions matched this scope.</div>
		{:else}
			<div class="table-scroll">
				<table class="questions-table">
					<colgroup>
						<col class="question-col" />
						<col class="subject-col" />
						<col class="topic-col" />
						<col class="status-col" />
						<col class="type-col" />
						<col class="date-col" />
					</colgroup>
					<thead>
						<tr>
							<th><button class="sort-button" type="button" onclick={() => toggleSort('question_text')}>Question <span>{sortIndicator('question_text')}</span></button></th>
							<th><button class="sort-button" type="button" onclick={() => toggleSort('subject_name')}>Subject <span>{sortIndicator('subject_name')}</span></button></th>
							<th><button class="sort-button" type="button" onclick={() => toggleSort('topic_name')}>Topic <span>{sortIndicator('topic_name')}</span></button></th>
							<th><button class="sort-button" type="button" onclick={() => toggleSort('vetting_status')}>Status <span>{sortIndicator('vetting_status')}</span></button></th>
							<th><button class="sort-button" type="button" onclick={() => toggleSort('question_type')}>Type <span>{sortIndicator('question_type')}</span></button></th>
							<th><button class="sort-button" type="button" onclick={() => toggleSort('generated_at')}>Generated <span>{sortIndicator('generated_at')}</span></button></th>
						</tr>
					</thead>
					<tbody>
						{#each sortedQuestions as question}
							<tr>
								<td>
									<div class="question-cell">
										<strong>{question.question_text}</strong>
										{#if question.explanation}
											<p>{question.explanation}</p>
										{/if}
									</div>
								</td>
								<td>
									<div class="subject-cell">
										<strong>{question.subject_name ?? 'Unassigned'}</strong>
										{#if question.subject_code}
											<span>{question.subject_code}</span>
										{/if}
									</div>
								</td>
								<td>{question.topic_name ?? 'No topic'}</td>
								<td><span class={`status-badge ${question.vetting_status ?? 'unknown'}`}>{statusLabel(question.vetting_status)}</span></td>
								<td>
									<div class="type-cell">
										<span>{question.question_type}</span>
										{#if question.difficulty_level}
											<small>{question.difficulty_level}</small>
										{/if}
									</div>
								</td>
								<td>{formatTimestamp(question.generated_at)}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	</div>

	<div class="pagination-bar">
		<button class="table-btn" type="button" onclick={() => setPage(pageNumber - 1)} disabled={loading || pageNumber <= 1}>Previous</button>
		<span>Page {pageNumber}{#if totalPages > 0} of {totalPages}{/if}</span>
		<button class="table-btn" type="button" onclick={() => setPage(pageNumber + 1)} disabled={loading || (totalPages > 0 && pageNumber >= totalPages)}>Next</button>
	</div>
</div>

<style>
	.page {
		max-width: 1280px;
		margin: 0 auto;
		padding: 2rem 1.5rem 2.5rem;
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}

	.glass-panel {
		border: 1px solid var(--theme-border, rgba(148, 163, 184, 0.24));
		border-radius: 24px;
		background: linear-gradient(145deg, rgba(15, 23, 42, 0.92), rgba(30, 41, 59, 0.84));
		box-shadow: 0 24px 48px rgba(15, 23, 42, 0.22);
		backdrop-filter: blur(18px);
	}

	.hero,
	.toolbar,
	.table-shell {
		padding: 1.25rem;
	}

	.hero {
		display: flex;
		justify-content: space-between;
		gap: 1rem;
		align-items: flex-start;
	}

	.eyebrow {
		margin: 0 0 0.35rem;
		text-transform: uppercase;
		letter-spacing: 0.12em;
		font-size: 0.74rem;
		font-weight: 700;
		color: var(--theme-primary, #f59e0b);
	}

	h1 {
		margin: 0;
		font-size: clamp(1.8rem, 4vw, 2.5rem);
	}

	.hero-copy {
		margin: 0.45rem 0 0;
		max-width: 56rem;
		color: var(--theme-text-secondary, rgba(226, 232, 240, 0.76));
	}

	.hero-meta {
		display: flex;
		gap: 0.75rem;
		flex-wrap: wrap;
		justify-content: flex-end;
		color: var(--theme-text-secondary, rgba(226, 232, 240, 0.76));
	}

	.toolbar {
		display: flex;
		flex-direction: column;
		gap: 0.9rem;
	}

	.search-form {
		display: flex;
		gap: 0.75rem;
		flex-wrap: wrap;
	}

	.search-input {
		flex: 1 1 20rem;
		min-width: 16rem;
		padding: 0.82rem 0.95rem;
		border-radius: 16px;
		border: 1px solid rgba(148, 163, 184, 0.2);
		background: rgba(15, 23, 42, 0.56);
		color: inherit;
	}

	.status-strip,
	.scope-strip,
	.pagination-bar {
		display: flex;
		gap: 0.6rem;
		flex-wrap: wrap;
		align-items: center;
	}

	.status-pill,
	.scope-pill,
	.scope-clear,
	.table-btn,
	.sort-button {
		border-radius: 999px;
		border: 1px solid rgba(148, 163, 184, 0.2);
		background: rgba(15, 23, 42, 0.5);
		color: inherit;
	}

	.status-pill,
	.scope-clear,
	.table-btn {
		padding: 0.65rem 0.9rem;
		font: inherit;
		cursor: pointer;
	}

	.status-pill.active,
	.table-btn.primary {
		background: rgba(245, 158, 11, 0.2);
		border-color: rgba(245, 158, 11, 0.45);
	}

	.scope-pill {
		padding: 0.45rem 0.75rem;
		font-size: 0.92rem;
	}

	.scope-clear {
		background: transparent;
	}

	.table-shell {
		overflow: hidden;
	}

	.table-scroll {
		overflow-x: auto;
	}

	.questions-table {
		width: 100%;
		border-collapse: collapse;
		min-width: 960px;
	}

	.question-col {
		width: 36%;
	}

	.subject-col,
	.topic-col,
	.status-col,
	.type-col,
	.date-col {
		width: 12.8%;
	}

	.questions-table thead th,
	.questions-table tbody td {
		padding: 0.9rem 1rem;
		text-align: left;
		vertical-align: top;
		border-bottom: 1px solid rgba(148, 163, 184, 0.12);
	}

	.sort-button {
		padding: 0;
		width: 100%;
		display: inline-flex;
		justify-content: space-between;
		align-items: center;
		background: transparent;
		border: none;
		font: inherit;
		cursor: pointer;
	}

	.sort-button span {
		font-size: 0.72rem;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		color: rgba(226, 232, 240, 0.54);
	}

	.question-cell,
	.subject-cell,
	.type-cell {
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
	}

	.question-cell p,
	.subject-cell span,
	.type-cell small {
		margin: 0;
		color: rgba(226, 232, 240, 0.68);
	}

	.question-cell p {
		line-clamp: 2;
		display: -webkit-box;
		-webkit-line-clamp: 2;
		-webkit-box-orient: vertical;
		overflow: hidden;
	}

	.status-badge {
		display: inline-flex;
		align-items: center;
		padding: 0.38rem 0.68rem;
		border-radius: 999px;
		font-size: 0.82rem;
		font-weight: 600;
		background: rgba(148, 163, 184, 0.14);
	}

	.status-badge.pending {
		background: rgba(245, 158, 11, 0.18);
	}

	.status-badge.approved {
		background: rgba(34, 197, 94, 0.18);
	}

	.status-badge.rejected {
		background: rgba(239, 68, 68, 0.18);
	}

	.state-message {
		padding: 2rem;
		text-align: center;
		color: rgba(226, 232, 240, 0.72);
	}

	.state-message.error {
		color: #fda4af;
	}

	.pagination-bar {
		justify-content: space-between;
	}

	@media (max-width: 720px) {
		.page {
			padding-inline: 1rem;
		}

		.hero {
			flex-direction: column;
		}

		.pagination-bar {
			justify-content: flex-start;
		}
	}
</style>