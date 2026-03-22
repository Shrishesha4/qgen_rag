<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { session } from '$lib/session';
	import { getSubject, listSubjects, type SubjectResponse, type TopicResponse } from '$lib/api/subjects';
	import { getBackgroundGenerationStatuses, scheduleBackgroundGeneration } from '$lib/api/documents';
	import { getQuestionsForVetting } from '$lib/api/vetting';
	import {
		createTeacherVettingLoopUrl,
		hydrateTeacherVettingProgressStoreFromRemote,
		latestTeacherVettingProgressBySubject,
		type TeacherVettingProgressSnapshot,
	} from '$lib/vetting-progress';

	let loading = $state(true);
	let error = $state('');
	let latestProgress = $state<TeacherVettingProgressSnapshot | null>(null);
	let subjects = $state<SubjectResponse[]>([]);
	let topicsMap = $state<Record<string, TopicResponse[]>>({});
	let loadingTopics = $state('');
	let selectedSubjectId = $state('');
	let searchQuery = $state('');
	let progressBySubject = $state<Record<string, TeacherVettingProgressSnapshot>>({});
	let pendingByTopic = $state<Record<string, number>>({});
	let loadingPendingCounts = $state(false);
	type SubjectGenerationState = {
		in_progress: boolean;
		status: string;
		progress: number;
		current_question: number;
		total_questions?: number | null;
	};
	let subjectGenerationStateBySubject = $state<Record<string, SubjectGenerationState>>({});
	type TopicGenerationState = {
		subjectId: string;
		status: string;
		progress: number;
		current: number;
		total: number;
		stalePolls: number;
	};
	let topicGenerationStateByTopic = $state<Record<string, TopicGenerationState>>({});
	let generationPollTimer: ReturnType<typeof setInterval> | null = null;
	let subjectGenerationPollTimer: ReturnType<typeof setInterval> | null = null;

	function toMillis(iso: string): number {
		const ts = Date.parse(iso);
		return Number.isFinite(ts) ? ts : 0;
	}

	function formatDateTime(iso: string): string {
		const ts = Date.parse(iso);
		if (!Number.isFinite(ts)) return 'Unknown';
		return new Date(ts).toLocaleString();
	}

	function resolveLatestProgress(store: Record<string, TeacherVettingProgressSnapshot>): TeacherVettingProgressSnapshot | null {
		const snapshots = Object.values(store);
		if (!snapshots.length) return null;
		return snapshots.reduce((latest, current) =>
			toMillis(current.updatedAt) > toMillis(latest.updatedAt) ? current : latest
		);
	}

	function isProgressComplete(snapshot: TeacherVettingProgressSnapshot | null | undefined): boolean {
		if (!snapshot) return false;
		if (snapshot.batchComplete) return true;
		const total = snapshot.questions.length;
		if (total <= 0) return false;
		const reviewedCount = new Set([...snapshot.approvedQuestionIds, ...snapshot.rejectedQuestionIds]).size;
		return reviewedCount >= total;
	}

	onMount(() => {
		const unsub = session.subscribe((s) => {
			if (!s || s.user.role !== 'teacher') {
				goto('/teacher/login');
			}
		});

		void initializePage();
		return unsub;
	});

	onDestroy(() => {
		if (generationPollTimer) {
			clearInterval(generationPollTimer);
			generationPollTimer = null;
		}
		if (subjectGenerationPollTimer) {
			clearInterval(subjectGenerationPollTimer);
			subjectGenerationPollTimer = null;
		}
	});

	async function initializePage() {
		await Promise.all([loadProgress(), loadSubjects()]);
	}

	async function loadProgress() {
		error = '';
		try {
			const store = await hydrateTeacherVettingProgressStoreFromRemote();
			latestProgress = resolveLatestProgress(store);
			progressBySubject = latestTeacherVettingProgressBySubject(store);
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to load your vetting progress';
		}
	}

	async function loadSubjects() {
		loading = true;
		try {
			const res = await listSubjects(1, 100);
			subjects = res.subjects;
			await refreshSubjectGenerationStatuses(res.subjects);
			ensureSubjectGenerationPolling();
			if (!selectedSubjectId && res.subjects.length > 0) {
				selectedSubjectId = res.subjects[0].id;
				await ensureTopicsLoaded(selectedSubjectId);
			}
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to load subjects';
		} finally {
			loading = false;
		}
	}

	async function refreshSubjectGenerationStatuses(subjectList: SubjectResponse[] = subjects) {
		if (subjectList.length === 0) {
			subjectGenerationStateBySubject = {};
			return;
		}
		try {
			const statusRes = await getBackgroundGenerationStatuses(subjectList.map((subject) => subject.id));
			const nextState: Record<string, SubjectGenerationState> = {};
			for (const subject of subjectList) {
				const status = statusRes.statuses[subject.id];
				if (!status) continue;
				nextState[subject.id] = {
					in_progress: Boolean(status.in_progress),
					status: status.status || '',
					progress: Math.max(0, Math.min(100, status.progress ?? 0)),
					current_question: Math.max(0, status.current_question ?? 0),
					total_questions: status.total_questions ?? null,
				};
			}
			subjectGenerationStateBySubject = nextState;
		} catch {
			// Keep last known status on transient network errors.
		}
	}

	function ensureSubjectGenerationPolling() {
		if (subjectGenerationPollTimer) {
			clearInterval(subjectGenerationPollTimer);
			subjectGenerationPollTimer = null;
		}
		subjectGenerationPollTimer = setInterval(() => {
			void refreshSubjectGenerationStatuses();
		}, 3000);
	}

	async function ensureTopicsLoaded(subjectId: string) {
		if (!subjectId) return;
		if (topicsMap[subjectId]) {
			await loadPendingCountsForSubject(subjectId, topicsMap[subjectId]);
			return;
		}
		loadingTopics = subjectId;
		try {
			const detail = await getSubject(subjectId);
			topicsMap = { ...topicsMap, [subjectId]: detail.topics };
			await loadPendingCountsForSubject(subjectId, detail.topics);
		} catch {
			topicsMap = { ...topicsMap, [subjectId]: [] };
		} finally {
			loadingTopics = '';
		}
	}

	async function loadPendingCountsForSubject(subjectId: string, topics: TopicResponse[]) {
		loadingPendingCounts = true;
		try {
			const limit = 100;
			let pageNo = 1;
			const nextPendingByTopic: Record<string, number> = {};
			for (const topic of topics) {
				nextPendingByTopic[topic.id] = 0;
			}

			while (true) {
				const pageRes = await getQuestionsForVetting({
					subject_id: subjectId,
					status: 'pending',
					page: pageNo,
					limit,
				});
				for (const q of pageRes.questions) {
					if (!q.topic_id) continue;
					nextPendingByTopic[q.topic_id] = (nextPendingByTopic[q.topic_id] ?? 0) + 1;
				}
				if (pageNo >= pageRes.pages || pageRes.questions.length === 0) break;
				pageNo += 1;
			}

			pendingByTopic = { ...pendingByTopic, ...nextPendingByTopic };
		} catch {
			// Preserve existing counts for other subjects if this fetch fails.
		} finally {
			loadingPendingCounts = false;
		}
	}

	async function selectSubject(subjectId: string) {
		selectedSubjectId = subjectId;
		await ensureTopicsLoaded(subjectId);
	}

	function resumeLastProgress() {
		if (!latestProgress) return;
		const loopUrl = createTeacherVettingLoopUrl(latestProgress, {
			resume: true,
			resumeKey: latestProgress.key,
		});
		const params = new URLSearchParams(loopUrl.split('?')[1] ?? '');
		params.set('auto_generate', '0');
		goto(`/teacher/train/loop?${params.toString()}`);
	}

	function startSubjectVetting(subjectId: string) {
		const params = new URLSearchParams({ subject: subjectId, resume: '0', auto_generate: '0' });
		goto(`/teacher/train/loop?${params.toString()}`);
	}

	function startTopicVetting(subjectId: string, topicId: string) {
		const params = new URLSearchParams({ subject: subjectId, topic: topicId, resume: '0', auto_generate: '0' });
		goto(`/teacher/train/loop?${params.toString()}`);
	}

	async function generateTopicBatch(subjectId: string, topicId: string) {
		if (topicGenerationStateByTopic[topicId]) return;
		topicGenerationStateByTopic = {
			...topicGenerationStateByTopic,
			[topicId]: {
				subjectId,
				status: 'queued',
				progress: 0,
				current: 0,
				total: 30,
				stalePolls: 0,
			},
		};
		error = '';
		try {
			const scheduleRes = await scheduleBackgroundGeneration({
				subjectId,
				count: 30,
				types: 'mcq',
				difficulty: 'medium',
				topicId,
			});
			topicGenerationStateByTopic = {
				...topicGenerationStateByTopic,
				[topicId]: {
					...(topicGenerationStateByTopic[topicId] ?? {
						subjectId,
						status: 'queued',
						progress: 0,
						current: 0,
						total: 30,
						stalePolls: 0,
					}),
					status: scheduleRes.status || 'queued',
					total: Math.max(1, scheduleRes.count || 30),
					stalePolls: 0,
				},
			};
			await pollTopicGenerationStates();
			ensureTopicGenerationPolling();
		} catch (e: unknown) {
			const nextStates = { ...topicGenerationStateByTopic };
			delete nextStates[topicId];
			topicGenerationStateByTopic = nextStates;
			error = e instanceof Error ? e.message : 'Failed to schedule topic generation';
		}
	}

	function ensureTopicGenerationPolling() {
		if (generationPollTimer) {
			clearInterval(generationPollTimer);
			generationPollTimer = null;
		}
		if (Object.keys(topicGenerationStateByTopic).length === 0) return;
		generationPollTimer = setInterval(() => {
			void pollTopicGenerationStates();
		}, 2500);
	}

	async function pollTopicGenerationStates() {
		const activeEntries = Object.entries(topicGenerationStateByTopic);
		if (activeEntries.length === 0) return;

		const subjectIds = [...new Set(activeEntries.map(([, state]) => state.subjectId))];
		let statusesBySubject: Record<string, { in_progress: boolean; status: string; progress: number; current_question: number; total_questions?: number | null }> = {};
		try {
			const statusRes = await getBackgroundGenerationStatuses(subjectIds);
			statusesBySubject = statusRes.statuses;
		} catch {
			return;
		}

		const nextStates: Record<string, TopicGenerationState> = {};

		for (const [topicId, state] of activeEntries) {
			const subjectStatus = statusesBySubject[state.subjectId];
			if (subjectStatus?.in_progress) {
				nextStates[topicId] = {
					...state,
					status: subjectStatus.status || state.status,
					progress: Math.max(0, Math.min(100, subjectStatus.progress ?? state.progress)),
					current: Math.max(0, subjectStatus.current_question ?? state.current),
					total: Math.max(1, subjectStatus.total_questions ?? state.total),
					stalePolls: 0,
				};
				continue;
			}

			const topics = topicsMap[state.subjectId] || [];
			await loadPendingCountsForSubject(state.subjectId, topics);
			const pendingCount = pendingByTopic[topicId] ?? 0;
			const serverStatus = (subjectStatus?.status || '').toLowerCase();
			if (subjectStatus && ['failed', 'error'].includes(serverStatus)) {
				error = 'Generation failed for this topic. Please retry.';
				continue;
			}
			if (subjectStatus && ['complete', 'completed'].includes(serverStatus) && pendingCount > 0) {
				continue;
			}

			const nextStalePolls = (state.stalePolls ?? 0) + 1;
			if (!subjectStatus && pendingCount > 0 && nextStalePolls >= 4) {
				continue;
			}

			nextStates[topicId] = {
				...state,
				status: subjectStatus?.status || state.status,
				stalePolls: subjectStatus ? 0 : nextStalePolls,
			};
		}

		topicGenerationStateByTopic = nextStates;
		ensureTopicGenerationPolling();
	}

	const currentProgressLabel = $derived.by(() => {
		if (!latestProgress) return 'No active progress';
		const total = latestProgress.questions.length;
		if (total <= 0) return '0/0 reviewed';
		const current = Math.min(total, Math.max(1, latestProgress.currentIndex + 1));
		return `${current}/${total} reviewed`;
	});

	const latestProgressSubjectLabel = $derived.by(() => {
		const snapshot = latestProgress;
		if (!snapshot) return '';
		const subjectNameFromList = subjects.find((subject) => subject.id === snapshot.subjectId)?.name;
		if (subjectNameFromList) return subjectNameFromList;
		const subjectNameFromQuestion = snapshot.questions.find((q) => q.subject_name)?.subject_name;
		return subjectNameFromQuestion || snapshot.subjectId;
	});

	const latestProgressIsComplete = $derived.by(() => isProgressComplete(latestProgress));

	const filteredSubjects = $derived.by(() => {
		const q = searchQuery.trim().toLowerCase();
		if (!q) return subjects;
		return subjects.filter((subject) => {
			const subjectMatch =
				subject.name.toLowerCase().includes(q) ||
				subject.code.toLowerCase().includes(q) ||
				(subject.description || '').toLowerCase().includes(q);
			if (subjectMatch) return true;
			const topics = topicsMap[subject.id] || [];
			return topics.some((topic) => topic.name.toLowerCase().includes(q));
		});
	});

	const selectedSubject = $derived.by(() => {
		if (!selectedSubjectId) return null;
		return (
			filteredSubjects.find((subject) => subject.id === selectedSubjectId) ||
			subjects.find((subject) => subject.id === selectedSubjectId) ||
			null
		);
	});

	const selectedTopics = $derived.by(() => {
		if (!selectedSubjectId) return [] as TopicResponse[];
		return topicsMap[selectedSubjectId] || [];
	});

	function getTopicPendingCount(topicId: string): number {
		return pendingByTopic[topicId] ?? 0;
	}

	function getTopicGenerationState(topicId: string): TopicGenerationState | null {
		return topicGenerationStateByTopic[topicId] ?? null;
	}

	function getSubjectGenerationState(subjectId: string): SubjectGenerationState | null {
		return subjectGenerationStateBySubject[subjectId] ?? null;
	}

	function getTopicGenerationLabel(topicId: string): string {
		const state = topicGenerationStateByTopic[topicId];
		if (!state) return 'Generate';
		const status = (state.status || '').toLowerCase();
		if (status === 'queued') return 'Queued';
		if (status === 'waiting_for_documents') return 'Waiting...';
		if (state.total > 0 && state.current > 0) return `Gen ${Math.min(state.current, state.total)}/${state.total}`;
		if (state.progress > 0) return `Gen ${state.progress}%`;
		return 'Generating...';
	}

	function getSubjectGenerationLabel(subjectId: string): string {
		const state = subjectGenerationStateBySubject[subjectId];
		if (!state || !state.in_progress) return '';
		const status = (state.status || '').toLowerCase();
		if (status === 'queued') return 'Queued';
		if (status === 'waiting_for_documents') return 'Waiting...';
		if ((state.total_questions ?? 0) > 0 && state.current_question > 0) {
			return `Gen ${Math.min(state.current_question, state.total_questions || state.current_question)}/${state.total_questions}`;
		}
		if (state.progress > 0) return `Gen ${state.progress}%`;
		return 'Generating...';
	}
</script>

<svelte:head>
	<title>Training - Teacher Console</title>
</svelte:head>

<div class="page">
	<div class="hero">
		<p class="kicker">Teacher Console</p>
		<h1 class="title font-serif">Training</h1>
		<p class="subtitle">Resume progress quickly, then continue with subject/topic vetting below.</p>
	</div>

	{#if loading}
		<div class="center-state glass-panel">
			<div class="spinner"></div>
			<p>Loading your vetting progress...</p>
		</div>
	{:else}
		{#if error}
			<div class="error-banner" role="alert">{error}</div>
		{/if}

		{#if !latestProgress || !latestProgressIsComplete}
			<section class="resume-strip glass-panel">
				{#if latestProgress}
					<div class="summary-grid">
						<div class="summary-item">
							<span class="summary-label">Subject</span>
							<strong>{latestProgressSubjectLabel}</strong>
						</div>
						<div class="summary-item">
							<span class="summary-label">Progress</span>
							<strong>{currentProgressLabel}</strong>
						</div>
						<div class="summary-item">
							<span class="summary-label">Last Updated</span>
							<strong>{formatDateTime(latestProgress.updatedAt)}</strong>
						</div>
					</div>
					<div class="actions-row">
						<button class="primary-btn" onclick={resumeLastProgress}>Resume Vetting</button>
					</div>
				{:else}
					<p class="muted">No saved vetting progress found yet. Start a new vetting session below.</p>
				{/if}
			</section>
		{/if}

		<section class="content-panel glass-panel">
			<h2>Start New Vetting</h2>
			<p class="muted">Pick a subject and topic below, then begin vetting immediately in this page.</p>
			<div class="inline-selector-grid">
				<div class="subjects-pane">
					<p class="pane-title">Subjects</p>
					<input class="search-input" bind:value={searchQuery} placeholder="Search subjects or topics" />
					<div class="subject-list">
						{#each filteredSubjects as subject}
							<button
								class="subject-item"
								class:active={subject.id === selectedSubjectId}
								onclick={() => selectSubject(subject.id)}
							>
								<div class="subject-item-head">
									<span class="subject-code">{subject.code}</span>
									{#if progressBySubject[subject.id] && !isProgressComplete(progressBySubject[subject.id])}
										<span class="resume-dot">Resume</span>
									{/if}
								</div>
								<strong>{subject.name}</strong>
								<span class="subject-meta">{subject.total_questions} questions • {subject.total_topics} topics</span>
							</button>
						{/each}
					</div>
				</div>

				<div class="topics-pane">
					<p class="pane-title">Topics</p>
					{#if selectedSubject}
						{@const selectedSubjectGenerationState = getSubjectGenerationState(selectedSubject.id)}
						<div class="topics-head">
							<div>
								<p class="subject-code-line">{selectedSubject.code}</p>
								<h3>{selectedSubject.name}</h3>
								{#if selectedSubjectGenerationState?.in_progress}
									<p class="subject-generating-note">Background generation in progress</p>
								{/if}
							</div>
							<button class="primary-btn" onclick={() => startSubjectVetting(selectedSubject.id)} disabled={loadingPendingCounts}>Start Subject Vetting</button>
						</div>

						{#if loadingTopics === selectedSubject.id}
							<div class="loading-inline"><div class="spinner-sm"></div><span>Loading topics...</span></div>
						{:else if selectedTopics.length}
							<div class="topic-grid">
								{#each selectedTopics as topic}
									{@const pendingCount = getTopicPendingCount(topic.id)}
									{@const generationState = getTopicGenerationState(topic.id)}
									{@const subjectGenerationState = getSubjectGenerationState(selectedSubject.id)}
									{@const canStart = pendingCount > 0}
									<div class="topic-card">
										<h4>{topic.name}</h4>
										{#if topic.syllabus_content}
											<p>{topic.syllabus_content.slice(0, 120)}{topic.syllabus_content.length > 120 ? '...' : ''}</p>
										{/if}
										<div class="topic-actions">
											<span>{pendingCount} Qs</span>
											{#if generationState}
												<button class="secondary-btn" disabled>{getTopicGenerationLabel(topic.id)}</button>
											{:else if subjectGenerationState?.in_progress && pendingCount === 0}
												<button class="secondary-btn" disabled>{getSubjectGenerationLabel(selectedSubject.id)}</button>
											{:else if canStart}
												<button class="secondary-btn" onclick={() => startTopicVetting(selectedSubject.id, topic.id)}>Start</button>
											{:else}
												<button class="secondary-btn" onclick={() => generateTopicBatch(selectedSubject.id, topic.id)}>
													Generate
												</button>
											{/if}
										</div>
									</div>
								{/each}
							</div>
						{:else}
							<p class="muted">No topics found for this subject.</p>
						{/if}
					{:else}
						<p class="muted">Select a subject to begin.</p>
					{/if}
				</div>
			</div>
		</section>
	{/if}
</div>

<style>
	.page {
		max-width: 980px;
		margin: 0 auto;
		padding: 2rem 1.25rem 2.5rem;
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}

	.hero {
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
	}

	.kicker {
		margin: 0;
		font-size: 0.78rem;
		font-weight: 700;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: var(--theme-primary);
	}

	.title {
		margin: 0;
		font-size: 2rem;
		color: var(--theme-text-primary);
	}

	.subtitle {
		margin: 0;
		color: var(--theme-text-secondary);
	}

	.center-state {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		min-height: 56vh;
		gap: 0.9rem;
		padding: 2rem;
		color: var(--theme-text-muted);
	}

	.resume-strip {
		padding: 0.95rem;
		border-radius: 1rem;
		display: flex;
		flex-direction: column;
		gap: 0.55rem;
	}

	.content-panel {
		padding: 1.2rem;
		border-radius: 1.1rem;
		display: flex;
		flex-direction: column;
		gap: 0.65rem;
		min-height: 58vh;
	}

	.content-panel h2 {
		margin: 0;
		font-size: 1.2rem;
		color: var(--theme-text-primary);
	}

	.summary-grid {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 0.65rem;
	}

	.summary-item {
		padding: 0.7rem 0.75rem;
		border-radius: 0.85rem;
		border: 1px solid var(--theme-glass-border);
		background: var(--theme-glass-bg);
		display: flex;
		flex-direction: column;
		gap: 0.2rem;
	}

	.summary-label {
		font-size: 0.7rem;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--theme-text-muted);
		font-weight: 700;
	}

	.summary-item strong {
		font-size: 0.92rem;
		color: var(--theme-text-primary);
	}

	.muted {
		margin: 0;
		color: var(--theme-text-muted);
	}

	.primary-btn,
	.secondary-btn {
		margin-top: 0;
		min-height: 44px;
		padding: 0.65rem 1rem;
		border-radius: 999px;
		border: 1px solid rgba(var(--theme-primary-rgb), 0.45);
		font: inherit;
		font-weight: 800;
		cursor: pointer;
	}

	.primary-btn {
		background: rgba(var(--theme-primary-rgb), 0.22);
		color: var(--theme-text-primary);
		white-space: nowrap;
	}

	.secondary-btn {
		background: rgba(var(--theme-primary-rgb), 0.12);
		color: var(--theme-primary);
	}

	.actions-row {
		display: flex;
		gap: 0.55rem;
		flex-wrap: wrap;
		margin-top: 0.35rem;
	}

	.inline-selector-grid {
		display: grid;
		grid-template-columns: 300px minmax(0, 1fr);
		gap: 0.75rem;
		margin-top: 0.35rem;
	}

	.subjects-pane,
	.topics-pane {
		border: 1px solid var(--theme-glass-border);
		background: var(--theme-glass-bg);
		border-radius: 0.95rem;
		padding: 0.65rem;
	}

	.pane-title {
		margin: 0 0 0.5rem;
		font-size: 0.72rem;
		font-weight: 800;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: var(--theme-text-muted);
	}

	.search-input {
		width: 100%;
		padding: 0.7rem 0.8rem;
		border-radius: 0.75rem;
		border: 1px solid var(--theme-glass-border);
		background: var(--theme-input-bg);
		color: var(--theme-text-primary);
		font: inherit;
	}

	.subject-list {
		display: flex;
		flex-direction: column;
		gap: 0.45rem;
		max-height: 44vh;
		overflow: auto;
		margin-top: 0.6rem;
		overscroll-behavior: contain;
	}

	.subject-item {
		width: 100%;
		padding: 0.62rem;
		text-align: left;
		border-radius: 0.8rem;
		border: 1px solid var(--theme-glass-border);
		background: var(--theme-nav-glass);
		cursor: pointer;
		display: flex;
		flex-direction: column;
		gap: 0.22rem;
		min-height: fit-content;
	}

	.subject-item.active {
		border-color: rgba(var(--theme-primary-rgb), 0.5);
		background: rgba(var(--theme-primary-rgb), 0.16);
	}

	.subject-item-head {
		display: flex;
		align-items: center;
		justify-content: space-between;
	}

	.subject-code,
	.subject-code-line {
		margin: 0;
		font-size: 0.72rem;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		font-weight: 700;
		color: var(--theme-primary);
	}

	.subject-meta {
		font-size: 0.74rem;
		color: var(--theme-text-muted);
		line-height: 1.25;
	}

	.resume-dot {
		font-size: 0.68rem;
		font-weight: 700;
		padding: 0.15rem 0.42rem;
		border-radius: 999px;
		background: rgba(var(--theme-primary-rgb), 0.16);
		color: var(--theme-text-primary);
	}

	.topics-head {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		gap: 0.6rem;
		margin-bottom: 0.55rem;
	}

	.topics-head h3 {
		margin: 0.18rem 0 0;
		font-size: 1.12rem;
		color: var(--theme-text-primary);
	}

	.subject-generating-note {
		margin: 0.3rem 0 0;
		font-size: 0.76rem;
		font-weight: 700;
		color: var(--theme-primary);
		letter-spacing: 0.02em;
		text-transform: uppercase;
	}

	.loading-inline {
		display: flex;
		align-items: center;
		gap: 0.55rem;
		padding: 0.7rem 0;
		color: var(--theme-text-secondary);
	}

	.spinner-sm {
		width: 18px;
		height: 18px;
		border-radius: 50%;
		border: 2px solid rgba(255, 255, 255, 0.2);
		border-top-color: var(--theme-primary);
		animation: spin 0.8s linear infinite;
	}

	.topic-grid {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 0.6rem;
	}

	.topic-card {
		border: 1px solid var(--theme-glass-border);
		background: var(--theme-nav-glass);
		border-radius: 0.85rem;
		padding: 0.62rem;
		display: flex;
		flex-direction: column;
		gap: 0.3rem;
	}

	.topic-card h4 {
		margin: 0;
		font-size: 0.95rem;
		color: var(--theme-text-primary);
	}

	.topic-card p {
		margin: 0;
		font-size: 0.8rem;
		line-height: 1.35;
		color: var(--theme-text-muted);
	}

	.topic-actions {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 0.5rem;
	}

	.topic-actions span {
		font-size: 0.74rem;
		font-weight: 700;
		color: var(--theme-primary);
	}

	.error-banner {
		padding: 0.9rem 1rem;
		border-radius: 1rem;
		background: rgba(239, 68, 68, 0.12);
		border: 1px solid rgba(239, 68, 68, 0.3);
		color: #b91c1c;
	}

	.spinner {
		width: 30px;
		height: 30px;
		border-radius: 50%;
		border: 3px solid rgba(255,255,255,0.2);
		border-top-color: var(--theme-primary);
		animation: spin 0.8s linear infinite;
	}

	@keyframes spin {
		to { transform: rotate(360deg); }
	}

	@media (max-width: 860px) {
		.page {
			padding: max(0.9rem, env(safe-area-inset-top)) 1rem max(2.75rem, env(safe-area-inset-bottom));
			gap: 0.85rem;
		}

		.kicker {
			display: none;
		}

		.title {
			font-size: 1.6rem;
		}

		.subtitle {
			font-size: 0.88rem;
		}

		.summary-grid {
			grid-template-columns: 1fr;
			gap: 0.45rem;
		}

		.resume-strip {
			padding: 0.85rem;
			border-radius: 0.9rem;
		}

		.content-panel {
			padding: 1.05rem 0.9rem;
			border-radius: 0.9rem;
			min-height: auto;
		}

		.content-panel h2 {
			font-size: 1.1rem;
		}

		.inline-selector-grid {
			grid-template-columns: 1fr;
			gap: 0.65rem;
		}

		.subjects-pane,
		.topics-pane {
			padding: 0.55rem;
			border-radius: 0.85rem;
		}

		.search-input {
			padding: 0.65rem 0.75rem;
			font-size: 0.9rem;
			border-radius: 0.7rem;
		}

		.subject-list {
			max-height: min(36vh, 320px);
			gap: 0.35rem;
			margin-top: 0.5rem;
		}

		.subject-item {
			padding: 0.6rem 0.65rem;
			border-radius: 0.7rem;
			gap: 0.18rem;
		}

		.subject-item strong {
			font-size: 0.92rem;
			line-height: 1.28;
		}

		.subject-code,
		.subject-code-line {
			font-size: 0.65rem;
			letter-spacing: 0.04em;
		}

		.subject-meta {
			font-size: 0.72rem;
			color: var(--theme-text-muted);
			line-height: 1.24;
		}

		.resume-dot {
			font-size: 0.62rem;
			padding: 0.12rem 0.35rem;
		}

		.topics-head {
			flex-direction: column;
			gap: 0.5rem;
		}

		.topics-head h3 {
			font-size: 1rem;
		}

		.primary-btn,
		.secondary-btn {
			min-height: 40px;
			padding: 0.55rem 0.85rem;
			font-size: 0.88rem;
		}

		.primary-btn {
			width: 100%;
			text-align: center;
		}

		.topic-grid {
			grid-template-columns: 1fr;
			gap: 0.45rem;
		}

		.topic-card {
			padding: 0.6rem 0.65rem;
			border-radius: 0.75rem;
		}

		.topic-card h4 {
			font-size: 0.9rem;
		}

		.topic-card p {
			font-size: 0.76rem;
		}

		.actions-row {
			margin-top: 0.2rem;
		}

		.error-banner {
			padding: 0.75rem 0.85rem;
			border-radius: 0.85rem;
			font-size: 0.88rem;
		}
	}

	@media (max-width: 640px) {
		.page {
			padding-left: 0.75rem;
			padding-right: 0.75rem;
		}

		.inline-selector-grid {
			grid-template-columns: 1fr;
			gap: 0.75rem;
		}

		.content-panel {
			padding: 0.95rem 0.75rem;
			gap: 0.7rem;
		}

		.content-panel h2 {
			font-size: 1.05rem;
			line-height: 1.25;
		}

		.muted {
			font-size: 0.92rem;
			line-height: 1.5;
		}

		.subjects-pane,
		.topics-pane {
			padding: 0.55rem;
			border-radius: 0.8rem;
			background: var(--theme-glass-bg);
		}

		.subjects-pane {
			display: flex;
			flex-direction: column;
			max-height: min(42dvh, 340px);
		}

		.topics-pane {
			min-height: min(44dvh, 360px);
		}

		.pane-title {
			margin-bottom: 0.45rem;
			font-size: 0.68rem;
		}

		.search-input {
			min-height: 46px;
			font-size: 0.95rem;
		}

		.subject-list {
			max-height: min(28dvh, 240px);
			gap: 0.42rem;
		}

		.subject-item {
			padding: 0.72rem;
			border-radius: 0.85rem;
			gap: 0.28rem;
		}

		.subject-item strong {
			font-size: 1rem;
			line-height: 1.3;
		}

		.subject-meta {
			font-size: 0.8rem;
		}

		.subject-code,
		.subject-code-line {
			font-size: 0.72rem;
		}

		.topic-card {
			padding: 0.72rem;
		}

		.topics-head {
			margin-bottom: 0.65rem;
		}

		.topics-head .primary-btn {
			width: 100%;
		}

		.topic-actions {
			align-items: center;
		}

		.topic-actions span {
			font-size: 0.8rem;
		}
	}
</style>
