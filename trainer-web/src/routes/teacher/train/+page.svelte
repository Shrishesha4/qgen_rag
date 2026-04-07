<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
	import { slide } from 'svelte/transition';
	import { goto } from '$app/navigation';
	import { session } from '$lib/session';
	import {
		getSubject,
		getSubjectsTree,
		type SubjectResponse,
		type SubjectGroupTreeNode,
		type SubjectTreeResponse,
		type TopicResponse
	} from '$lib/api/subjects';
	import { getBackgroundGenerationStatuses } from '$lib/api/documents';
	import { getQuestionsForVetting } from '$lib/api/vetting';
	import { buildSubjectGroupMetaById, getSubjectGroupPath, matchesSubjectSearch } from '$lib/subject-group-search';
	import {
		createTeacherVettingLoopUrl,
		hydrateTeacherVettingProgressStoreFromRemote,
		type TeacherVettingProgressSnapshot,
	} from '$lib/vetting-progress';
	import { getGenerationWebSocketClient, type StatsData } from '$lib/api/generation-websocket';

	let loading = $state(true);
	let error = $state('');
	let latestProgress = $state<TeacherVettingProgressSnapshot | null>(null);
	let progressStore = $state<Record<string, TeacherVettingProgressSnapshot>>({});
	let treeData = $state<SubjectTreeResponse | null>(null);
	let subjects = $state<SubjectResponse[]>([]);
	let expandedGroups = $state<Set<string>>(new Set());
	let topicsMap = $state<Record<string, TopicResponse[]>>({});
	let loadingTopics = $state('');
	let expandedSubjectId = $state('');
	let searchQuery = $state('');
	type TopicCountStats = {
		generated: number;
		pending: number;
		approved: number;
		rejected: number;
	};
	let topicStatsByTopic = $state<Record<string, TopicCountStats>>({});
	let loadingPendingCounts = $state(false);
	let showGenerateFirstModal = $state(false);
	let generateFirstSubjectId = $state('');
	let generateFirstTopicId = $state('');
	let generateFirstTitle = $state('');
	let generateFirstMessage = $state('');
	type ViewTab = 'subjects' | 'groups';
	let activeViewTab = $state<ViewTab>('subjects');

	type SubjectGenerationState = {
		in_progress: boolean;
		status: string;
		progress: number;
		current_question: number;
		total_questions?: number | null;
	};

	const INITIAL_SUBJECT_PRELOAD_LIMIT = 6;
	const GROUP_SUBJECT_PRELOAD_LIMIT = 8;

	let subjectGenerationStateBySubject = $state<Record<string, SubjectGenerationState>>({});
	let subjectGenerationPollTimer: ReturnType<typeof setInterval> | null = null;
	let pendingLoadInFlightCount = 0;
	const pendingCountsLoadedForSubject = new Set<string>();
	const pendingCountsLoadingForSubject = new Set<string>();
	
	// WebSocket for live stats updates
	let wsUnsubscribers: (() => void)[] = [];

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

	function hasMeaningfulProgress(snapshot: TeacherVettingProgressSnapshot | null | undefined): boolean {
		if (!snapshot) return false;
		if (snapshot.batchComplete) return true;
		const reviewedCount = new Set([...snapshot.approvedQuestionIds, ...snapshot.rejectedQuestionIds]).size;
		return reviewedCount > 0;
	}

	onMount(() => {
		const unsub = session.subscribe((s) => {
			if (!s || s.user.role !== 'teacher') {
				goto('/teacher/login');
			}
		});

		void initializePage();
		setupWebSocket();
		return unsub;
	});

	onDestroy(() => {
		if (subjectGenerationPollTimer) {
			clearInterval(subjectGenerationPollTimer);
			subjectGenerationPollTimer = null;
		}
		// Clean up WebSocket subscriptions
		wsUnsubscribers.forEach(unsub => unsub());
		wsUnsubscribers = [];
	});
	
	function setupWebSocket() {
		const wsClient = getGenerationWebSocketClient();
		wsClient.connect();
		wsClient.subscribeGlobalStats();
		
		// Handle global stats updates - update totals in treeData
		const globalUnsub = wsClient.onGlobalStats((statsData: StatsData) => {
			if (treeData) {
				treeData = {
					...treeData,
					totals: {
						...treeData.totals,
						total_questions: statsData.total_questions ?? treeData.totals.total_questions,
						total_approved: statsData.total_approved ?? treeData.totals.total_approved,
						total_rejected: statsData.total_rejected ?? treeData.totals.total_rejected,
						total_pending: statsData.total_pending ?? treeData.totals.total_pending,
					}
				};
			}
		});
		wsUnsubscribers.push(globalUnsub);
		
		// Handle subject-specific stats updates
		const subjectUnsub = wsClient.onSubjectStats((subjectId: string, statsData: StatsData) => {
			// Update the subject in the subjects array
			subjects = subjects.map(s => {
				if (s.id === subjectId) {
					return {
						...s,
						total_questions: statsData.total_questions ?? s.total_questions,
						total_approved: statsData.total_approved ?? s.total_approved,
						total_rejected: statsData.total_rejected ?? s.total_rejected,
						total_pending: statsData.total_pending ?? s.total_pending,
					};
				}
				return s;
			});
		});
		wsUnsubscribers.push(subjectUnsub);
		
		// Handle topic-specific stats updates - update pending counts
		const topicUnsub = wsClient.onTopicStats((subjectId: string, topicId: string, statsData: StatsData) => {
			topicStatsByTopic = {
				...topicStatsByTopic,
				[topicId]: {
					generated: statsData.generated ?? topicStatsByTopic[topicId]?.generated ?? 0,
					pending: statsData.pending ?? topicStatsByTopic[topicId]?.pending ?? 0,
					approved: statsData.approved ?? topicStatsByTopic[topicId]?.approved ?? 0,
					rejected: statsData.rejected ?? topicStatsByTopic[topicId]?.rejected ?? 0,
				},
			};
		});
		wsUnsubscribers.push(topicUnsub);
	}

	async function initializePage() {
		await Promise.all([loadProgress(), loadSubjects()]);
	}

	async function loadProgress() {
		error = '';
		try {
			const store = await hydrateTeacherVettingProgressStoreFromRemote();
			progressStore = store;
			latestProgress = resolveLatestProgress(store);
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to load your vetting progress';
		}
	}

	async function loadSubjects() {
		loading = true;
		try {
			pendingCountsLoadedForSubject.clear();
			pendingCountsLoadingForSubject.clear();
			pendingLoadInFlightCount = 0;
			loadingPendingCounts = false;
			const treeRes = await getSubjectsTree();
			treeData = treeRes;
			subjects = flattenSubjects(treeRes.groups, treeRes.ungrouped_subjects);
			expandedGroups = new Set();
			void preloadInitialSubjectData(subjects);
			await refreshSubjectGenerationStatuses(subjects);
			ensureSubjectGenerationPolling();
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to load subjects';
		} finally {
			loading = false;
		}
	}

	function flattenSubjects(groups: SubjectGroupTreeNode[], ungrouped: SubjectResponse[]): SubjectResponse[] {
		const result: SubjectResponse[] = [...ungrouped];
		function traverse(group: SubjectGroupTreeNode) {
			result.push(...group.subjects);
			group.children.forEach(traverse);
		}
		groups.forEach(traverse);
		return result;
	}

	function collectSubjectIdsFromGroup(group: SubjectGroupTreeNode): string[] {
		const subjectIds = group.subjects.map((subject) => subject.id);
		for (const child of group.children) {
			subjectIds.push(...collectSubjectIdsFromGroup(child));
		}
		return subjectIds;
	}

	async function preloadInitialSubjectData(subjectList: SubjectResponse[]) {
		const subjectIds = subjectList.slice(0, INITIAL_SUBJECT_PRELOAD_LIMIT).map((subject) => subject.id);
		if (subjectIds.length === 0) return;
		await Promise.all(subjectIds.map((subjectId) =>
			ensureTopicsLoaded(subjectId, { silent: true, includePendingCounts: true })
		));
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

	async function ensureTopicsLoaded(
		subjectId: string,
		opts: { silent?: boolean; includePendingCounts?: boolean } = {}
	) {
		const silent = opts.silent ?? false;
		const includePendingCounts = opts.includePendingCounts ?? true;
		if (!subjectId) return;
		if (topicsMap[subjectId]) {
			if (includePendingCounts) {
				await ensurePendingCountsLoaded(subjectId, topicsMap[subjectId], { silent });
			}
			return;
		}
		if (!silent) {
			loadingTopics = subjectId;
		}
		try {
			const detail = await getSubject(subjectId);
			topicsMap = { ...topicsMap, [subjectId]: detail.topics };
			if (includePendingCounts) {
				await ensurePendingCountsLoaded(subjectId, detail.topics, { silent });
			}
		} catch {
			topicsMap = { ...topicsMap, [subjectId]: [] };
		} finally {
			if (!silent && loadingTopics === subjectId) {
				loadingTopics = '';
			}
		}
	}

	async function ensurePendingCountsLoaded(
		subjectId: string,
		topics: TopicResponse[],
		opts: { silent?: boolean } = {}
	) {
		if (pendingCountsLoadedForSubject.has(subjectId) || pendingCountsLoadingForSubject.has(subjectId)) {
			return;
		}
		pendingCountsLoadingForSubject.add(subjectId);
		try {
			await loadPendingCountsForSubject(subjectId, topics, opts);
			pendingCountsLoadedForSubject.add(subjectId);
		} finally {
			pendingCountsLoadingForSubject.delete(subjectId);
		}
	}

	async function loadPendingCountsForSubject(
		subjectId: string,
		topics: TopicResponse[],
		opts: { silent?: boolean } = {}
	) {
		const silent = opts.silent ?? false;
		if (!silent) {
			pendingLoadInFlightCount += 1;
			loadingPendingCounts = true;
		}
		try {
			const limit = 100;
			const countByStatus = async (status: 'pending' | 'approved' | 'rejected') => {
				let pageNo = 1;
				const byTopic: Record<string, number> = {};
				let orphan = 0;
				while (true) {
					const pageRes = await getQuestionsForVetting({
						subject_id: subjectId,
						status,
						page: pageNo,
						limit,
					});
					for (const q of pageRes.questions) {
						if (q.topic_id && topics.some((topic) => topic.id === q.topic_id)) {
							byTopic[q.topic_id] = (byTopic[q.topic_id] ?? 0) + 1;
						} else {
							orphan += 1;
						}
					}
					if (pageNo >= pageRes.pages || pageRes.questions.length === 0) break;
					pageNo += 1;
				}
				return { byTopic, orphan };
			};

			const [pendingCounts, approvedCounts, rejectedCounts] = await Promise.all([
				countByStatus('pending'),
				countByStatus('approved'),
				countByStatus('rejected'),
			]);

			const singleTopicId = topics.length === 1 ? topics[0].id : null;
			const nextTopicStatsByTopic: Record<string, TopicCountStats> = {};

			for (const topic of topics) {
				let pending = pendingCounts.byTopic[topic.id] ?? 0;
				let approved = approvedCounts.byTopic[topic.id] ?? 0;
				let rejected = rejectedCounts.byTopic[topic.id] ?? 0;

				if (singleTopicId && topic.id === singleTopicId) {
					pending += pendingCounts.orphan;
					approved += approvedCounts.orphan;
					rejected += rejectedCounts.orphan;
				}

				const generatedFromStatuses = pending + approved + rejected;
				const fallbackGenerated = topic.total_questions ?? 0;
				const generated = generatedFromStatuses > 0 ? generatedFromStatuses : fallbackGenerated;
				nextTopicStatsByTopic[topic.id] = {
					generated,
					pending: generatedFromStatuses > 0 ? pending : fallbackGenerated,
					approved,
					rejected,
				};
			}

			topicStatsByTopic = { ...topicStatsByTopic, ...nextTopicStatsByTopic };
		} catch {
			// Preserve existing counts for other subjects if this fetch fails.
		} finally {
			if (!silent) {
				pendingLoadInFlightCount = Math.max(0, pendingLoadInFlightCount - 1);
				loadingPendingCounts = pendingLoadInFlightCount > 0;
			}
		}
	}

	async function toggleSubject(subjectId: string) {
		if (expandedSubjectId === subjectId) {
			expandedSubjectId = '';
			return;
		}
		expandedSubjectId = subjectId;
		await ensureTopicsLoaded(subjectId);
	}

	function resumeLastProgress() {
		if (!latestProgress) return;
		resumeSpecificProgress(latestProgress);
	}

	function resumeSpecificProgress(snapshot: TeacherVettingProgressSnapshot) {
		const loopUrl = createTeacherVettingLoopUrl(snapshot, {
			resume: true,
			resumeKey: snapshot.key,
		});
		const params = new URLSearchParams(loopUrl.split('?')[1] ?? '');
		params.set('auto_generate', '1');
		goto(`/teacher/train/loop?${params.toString()}`);
	}

	function findLatestProgressForTopic(subjectId: string, topicId: string): TeacherVettingProgressSnapshot | null {
		let winner: TeacherVettingProgressSnapshot | null = null;
		for (const snapshot of Object.values(progressStore)) {
			if (snapshot.subjectId !== subjectId || snapshot.topicId !== topicId) continue;
			if (!winner || toMillis(snapshot.updatedAt) > toMillis(winner.updatedAt)) {
				winner = snapshot;
			}
		}
		return winner;
	}

	function topicResumeSnapshot(subjectId: string, topicId: string): TeacherVettingProgressSnapshot | null {
		const snapshot = findLatestProgressForTopic(subjectId, topicId);
		if (!snapshot) return null;
		if (!hasMeaningfulProgress(snapshot)) return null;
		return isProgressComplete(snapshot) ? null : snapshot;
	}

	function openGenerateFirstModal(subjectId: string, topicId: string | null, title: string, message: string) {
		generateFirstSubjectId = subjectId;
		generateFirstTopicId = topicId ?? '';
		generateFirstTitle = title;
		generateFirstMessage = message;
		showGenerateFirstModal = true;
	}

	function closeGenerateFirstModal() {
		showGenerateFirstModal = false;
		generateFirstSubjectId = '';
		generateFirstTopicId = '';
		generateFirstTitle = '';
		generateFirstMessage = '';
	}

	function goToGenerationPageFromModal() {
		if (!generateFirstSubjectId) {
			closeGenerateFirstModal();
			return;
		}
		const targetSubjectId = generateFirstSubjectId;
		const targetTopicId = generateFirstTopicId;
		const query = new URLSearchParams();
		if (targetTopicId) query.set('topic', targetTopicId);
		const suffix = query.toString() ? `?${query.toString()}` : '';
		closeGenerateFirstModal();
		goto(`/teacher/subjects/${targetSubjectId}${suffix}`);
	}

	function startSubjectVetting(subjectId: string, totalQuestions: number) {
		if ((totalQuestions ?? 0) <= 0) {
			openGenerateFirstModal(
				subjectId,
				null,
				'No questions available',
				'This subject has no generated questions yet. Generate first, then start vetting.'
			);
			return;
		}
		const params = new URLSearchParams({ subject: subjectId, resume: '0', auto_generate: '0' });
		goto(`/teacher/train/loop?${params.toString()}`);
	}

	function startTopicVetting(subjectId: string, topicId: string, topicName: string, totalQuestions: number) {
		if ((totalQuestions ?? 0) <= 0) {
			openGenerateFirstModal(
				subjectId,
				topicId,
				'No questions in this topic',
				`${topicName} has no generated questions yet. Generate first, then start vetting.`
			);
			return;
		}
		const params = new URLSearchParams({ subject: subjectId, topic: topicId, resume: '0', auto_generate: '0' });
		goto(`/teacher/train/loop?${params.toString()}`);
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

	// All incomplete (resumable) progress snapshots, sorted by most recent first
	const allIncompleteSnapshots = $derived.by(() => {
		return Object.values(progressStore)
			.filter(s => hasMeaningfulProgress(s) && !isProgressComplete(s))
			.sort((a, b) => toMillis(b.updatedAt) - toMillis(a.updatedAt));
	});

	function snapshotSubjectLabel(snapshot: TeacherVettingProgressSnapshot): string {
		const subjectNameFromList = subjects.find((s) => s.id === snapshot.subjectId)?.name;
		if (subjectNameFromList) return subjectNameFromList;
		const subjectNameFromQuestion = snapshot.questions.find((q) => q.subject_name)?.subject_name;
		return subjectNameFromQuestion || snapshot.subjectId;
	}

	function snapshotProgressLabel(snapshot: TeacherVettingProgressSnapshot): string {
		const total = snapshot.questions.length;
		if (total <= 0) return '0/0 reviewed';
		const current = Math.min(total, Math.max(1, snapshot.currentIndex + 1));
		return `${current}/${total} reviewed`;
	}

	const subjectGroupMetaById = $derived.by(() => buildSubjectGroupMetaById(treeData?.groups ?? []));

	function matchesTrainingSubjectSearch(subject: SubjectResponse, query: string): boolean {
		if (matchesSubjectSearch(subject, query, subjectGroupMetaById)) return true;
		const topics = topicsMap[subject.id] || [];
		return topics.some((topic) => topic.name.toLowerCase().includes(query));
	}

	const filteredSubjects = $derived.by(() => {
		const q = searchQuery.trim().toLowerCase();
		if (!q) return subjects;
		return subjects.filter((subject) => matchesTrainingSubjectSearch(subject, q));
	});

	function collectGroupedSubjectIds(groups: SubjectGroupTreeNode[]): Set<string> {
		const ids = new Set<string>();
		const walk = (group: SubjectGroupTreeNode) => {
			for (const subject of group.subjects) {
				ids.add(subject.id);
			}
			for (const child of group.children) {
				walk(child);
			}
		};
		for (const group of groups) {
			walk(group);
		}
		return ids;
	}

	const groupedSubjectIds = $derived.by(() => {
		if (!treeData) return new Set<string>();
		return collectGroupedSubjectIds(treeData.groups);
	});

	const filteredGroupedSubjects = $derived.by(() => {
		const q = searchQuery.trim().toLowerCase();
		const groupedSubjects = subjects.filter((subject) => groupedSubjectIds.has(subject.id));
		if (!q) return groupedSubjects;
		return groupedSubjects.filter((subject) => matchesTrainingSubjectSearch(subject, q));
	});

	const mobileVisibleSubjects = $derived.by(() => {
		if (activeViewTab === 'groups') {
			const hasQuery = searchQuery.trim().length > 0;
			if (hasQuery) return filteredGroupedSubjects;
			return filteredGroupedSubjects;
		}
		return filteredSubjects;
	});

	const hasSearchQuery = $derived.by(() => searchQuery.trim().length > 0);

	function isExpanded(subjectId: string): boolean {
		return expandedSubjectId === subjectId;
	}

	function toggleGroup(groupId: string) {
		const next = new Set(expandedGroups);
		const isOpening = !next.has(groupId);
		if (next.has(groupId)) {
			next.delete(groupId);
		} else {
			next.add(groupId);
		}
		expandedGroups = next;

		if (!isOpening || !treeData) return;
		const allGroupSubjectIds: string[] = [];
		const stack = [...treeData.groups];
		while (stack.length > 0) {
			const group = stack.pop();
			if (!group) continue;
			if (group.id === groupId) {
				allGroupSubjectIds.push(...collectSubjectIdsFromGroup(group));
				break;
			}
			stack.push(...group.children);
		}
		for (const subjectId of allGroupSubjectIds.slice(0, GROUP_SUBJECT_PRELOAD_LIMIT)) {
			void ensureTopicsLoaded(subjectId, { silent: true, includePendingCounts: true });
		}
	}

	function getSubjectGenerationState(subjectId: string): SubjectGenerationState | null {
		return subjectGenerationStateBySubject[subjectId] ?? null;
	}

	function getTopicPendingCount(topicId: string): number {
		return topicStatsByTopic[topicId]?.pending ?? 0;
	}

	function getTopicStats(topic: TopicResponse): TopicCountStats {
		return (
			topicStatsByTopic[topic.id] ?? {
				generated: topic.total_questions ?? 0,
				pending: topic.total_questions ?? 0,
				approved: 0,
				rejected: 0,
			}
		);
	}

	function shouldStartSubjectVetting(subject: SubjectResponse): boolean {
		const approved = subject.total_approved ?? 0;
		const rejected = subject.total_rejected ?? 0;
		return approved + rejected === 0;
	}

	async function handleSubjectPrimaryAction(subject: SubjectResponse) {
		if (shouldStartSubjectVetting(subject)) {
			startSubjectVetting(subject.id, subject.total_questions ?? 0);
			return;
		}
		await toggleSubject(subject.id);
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

	function subjectPrimaryActionLabel(subject: SubjectResponse): string {
		return shouldStartSubjectVetting(subject) ? 'Start Vetting' : 'View Topics';
	}
</script>

<svelte:head>
	<title>Vetting - Teacher Console</title>
</svelte:head>

<div class="page">
	<!-- <div class="hero">
		<p class="kicker">Teacher Console</p>
		<h1 class="title font-serif">Vetting</h1>
		<p class="subtitle">Pick a subject, expand rows, and start vetting directly from the table.</p>
	</div> -->

	{#if loading}
		<div class="center-state glass-panel">
			<div class="spinner"></div>
			<p>Loading your vetting progress...</p>
		</div>
	{:else}
		{#if error}
			<div class="error-banner" role="alert">{error}</div>
		{/if}

		{#each allIncompleteSnapshots as snapshot}
			<section class="resume-strip glass-panel">
				<div class="summary-grid">
					<div class="summary-item">
						<span class="summary-label">Subject</span>
						<strong>{snapshotSubjectLabel(snapshot)}</strong>
					</div>
					<div class="summary-item">
						<span class="summary-label">Progress</span>
						<strong>{snapshotProgressLabel(snapshot)}</strong>
					</div>
					<div class="summary-item">
						<span class="summary-label">Last Updated</span>
						<strong>{formatDateTime(snapshot.updatedAt)}</strong>
					</div>
				</div>
				<div class="actions-row">
					<button class="primary-btn" onclick={() => resumeSpecificProgress(snapshot)}>Resume Vetting</button>
				</div>
			</section>
		{/each}

		<section class="content-panel glass-panel">
			<div class="panel-head">
				<div class="panel-head-left">
					<button class="table-back-btn" onclick={() => goto('/teacher/subjects')} aria-label="Go back to subjects">
						←
					</button>
					<h2>Start New Vetting</h2>
				</div>
				<div class="panel-head-center">
					<div class="tab-bar" role="tablist" aria-label="Vetting views">
						<button
							class="tab-btn"
							class:active={activeViewTab === 'subjects'}
							role="tab"
							aria-selected={activeViewTab === 'subjects'}
							onclick={() => {
								activeViewTab = 'subjects';
								searchQuery = '';
							}}
						>
							Subjects
						</button>
						<button
							class="tab-btn"
							class:active={activeViewTab === 'groups'}
							role="tab"
							aria-selected={activeViewTab === 'groups'}
							onclick={() => {
								activeViewTab = 'groups';
								searchQuery = '';
							}}
						>
							Groups
						</button>
					</div>
				</div>
				<input class="search-input" bind:value={searchQuery} placeholder="Search subjects, topics, or groups" />
			</div>

			<div class="table-shell desktop-only">
				<table class="training-table">
					<colgroup>
						<col class="name-col" />
						<col class="num-col" />
						<col class="num-col" />
						<col class="num-col" />
						<col class="num-col" />
						<col class="action-col" />
					</colgroup>
					<thead>
						<tr>
							<th>Name</th>
							<th>Questions</th>
							<th>Pending</th>
							<th>Approved</th>
							<th>Rejected</th>
							<th>Actions</th>
						</tr>
					</thead>
					<tbody>
						{#if activeViewTab === 'subjects'}
							{#if filteredSubjects.length === 0}
								<tr>
									<td colspan="6" class="empty-cell">No matching subjects.</td>
								</tr>
							{:else}
								{#each filteredSubjects as subject}
									{@render vettingSubjectRow(subject, 0)}
								{/each}
							{/if}
						{:else}
							{#if hasSearchQuery}
								{#if filteredGroupedSubjects.length === 0}
									<tr>
										<td colspan="6" class="empty-cell">No matching grouped subjects.</td>
									</tr>
								{:else}
									{#each filteredGroupedSubjects as subject}
										{@render vettingSubjectRow(subject, 0)}
									{/each}
								{/if}
							{:else if !treeData || treeData.groups.length === 0}
								<tr>
									<td colspan="6" class="empty-cell">No subjects yet.</td>
								</tr>
							{:else}
								{#each treeData.groups as group}
									{@render vettingGroupRow(group, 0)}
								{/each}
							{/if}
						{/if}
					</tbody>
				</table>
			</div>

			<div class="training-mobile-list mobile-only">
				{#if mobileVisibleSubjects.length === 0}
					<div class="mobile-card glass-panel empty-cell">No matching subjects.</div>
				{:else}
					{#each mobileVisibleSubjects as subject}
						{@const groupPath = getSubjectGroupPath(subject.id, subjectGroupMetaById)}
						<div class="mobile-card glass-panel">
							<div class="mobile-card-head">
								<div class="name-header">
									<span class="code-chip">{subject.code}</span>
									<strong>{subject.name}</strong>
								</div>
								<button class="table-btn" onclick={() => toggleSubject(subject.id)}>
									{isExpanded(subject.id) ? 'Hide Topics' : 'Show Topics'}
								</button>
							</div>
							{#if hasSearchQuery && groupPath}
								<span class="group-context">Group: {groupPath}</span>
							{/if}
							<div class="mobile-metrics">
								<span>Questions <strong>{subject.total_questions}</strong></span>
								<span>Pending <strong>{subject.total_pending ?? 0}</strong></span>
								<span class="green-text">Approved <strong>{subject.total_approved ?? 0}</strong></span>
								<span class="red-text">Rejected <strong>{subject.total_rejected ?? 0}</strong></span>
							</div>
							<div class="inline-actions">
								<button class="table-btn primary" onclick={() => void handleSubjectPrimaryAction(subject)} disabled={loadingPendingCounts}>{subjectPrimaryActionLabel(subject)}</button>
							</div>

							{#if isExpanded(subject.id)}
								{#if loadingTopics === subject.id}
									<div class="topic-loading"><span class="spinner-sm"></span> Loading topics...</div>
								{:else if (topicsMap[subject.id] || []).length === 0}
									<div class="empty-cell">No topics found for this subject.</div>
								{:else}
									<div class="mobile-topic-list">
										{#each topicsMap[subject.id] || [] as topic}
													{@const topicStats = getTopicStats(topic)}
													{@const pendingCount = topicStats.pending}
													{@const topicProgress = topicResumeSnapshot(subject.id, topic.id)}
											{@const subjectGenerationState = getSubjectGenerationState(subject.id)}
											<div class="mobile-topic-card">
												<div class="topic-title-line">
													<span class="topic-branch">  </span>
													<strong>{topic.name}</strong>
												</div>
												<div class="mobile-metrics">
															<span>Questions <strong>{topicStats.generated}</strong></span>
													<span>Pending <strong>{pendingCount}</strong></span>
															<span class="green-text">Approved <strong>{topicStats.approved}</strong></span>
															<span class="red-text">Rejected <strong>{topicStats.rejected}</strong></span>
												</div>
												<div class="inline-actions">
													{#if subjectGenerationState?.in_progress && pendingCount === 0}
														<span class="status-text generation-status"><span class="spinner-sm"></span>{getSubjectGenerationLabel(subject.id)}</span>
															{:else if topicProgress}
																<button class="table-btn" onclick={() => resumeSpecificProgress(topicProgress)} disabled={loadingPendingCounts}>Resume</button>
													{:else}
																<button class="table-btn primary" onclick={() => startTopicVetting(subject.id, topic.id, topic.name, topicStats.generated)} disabled={loadingPendingCounts}>Start Vetting</button>
													{/if}
												</div>
											</div>
										{/each}
									</div>
								{/if}
							{/if}
						</div>
					{/each}
				{/if}
			</div>
		</section>
	{/if}
</div>

{#snippet vettingGroupRow(group: SubjectGroupTreeNode, depth: number)}
	<tr class="group-row" role="button" tabindex="0" onclick={() => toggleGroup(group.id)} onkeydown={(event) => {
		if (event.key === 'Enter' || event.key === ' ') {
			event.preventDefault();
			toggleGroup(group.id);
		}
	}}>
		<td>
			<div class="row-trigger" style="padding-left: {depth * 1.8}rem">
				<button class="expand-btn" type="button" aria-label="Toggle subgroup visibility" onclick={(event) => {
					event.stopPropagation();
					toggleGroup(group.id);
				}}>
					<span class="chevron" class:open={expandedGroups.has(group.id)}>▸</span>
				</button>
				<div class="name-stack">
					<div class="name-header">
						<strong>📁 {group.name}</strong>
						<span class="code-chip">GROUP</span>
					</div>
				</div>
			</div>
		</td>
		<td>{group.total_questions}</td>
		<td>{group.total_pending}</td>
		<td class="green-text">{group.total_approved}</td>
		<td class="red-text">{group.total_rejected}</td>
		<td class="action-cell">
			<span class="status-text">⌄</span>
		</td>
	</tr>
	{#if expandedGroups.has(group.id)}
		{#each group.children as child}
			{@render vettingGroupRow(child, depth + 1)}
		{/each}
		{#each group.subjects as subject}
			{@render vettingSubjectRow(subject, depth + 1)}
		{/each}
	{/if}
{/snippet}

{#snippet vettingSubjectRow(subject: SubjectResponse, depth: number)}
	{@const groupPath = getSubjectGroupPath(subject.id, subjectGroupMetaById)}
	<tr class="subject-row" role="button" tabindex="0" onclick={() => toggleSubject(subject.id)} onkeydown={(event) => {
		if (event.key === 'Enter' || event.key === ' ') {
			event.preventDefault();
			void toggleSubject(subject.id);
		}
	}}>
		<td>
			<div class="row-trigger" style="padding-left: {depth * 2.2}rem">
				<button class="expand-btn" type="button" aria-label="Toggle topics" onclick={(event) => {
					event.stopPropagation();
					void toggleSubject(subject.id);
				}}>
					<span class="chevron" class:open={isExpanded(subject.id)}>▸</span>
				</button>
				<div class="name-stack">
					<div class="name-header">
						<!-- {#if depth > 0}
							<span class="subject-in-group-branch" aria-hidden="true"> </span>
						{/if} -->
						<strong>{subject.name}</strong>
						<span class="code-chip">{subject.code}</span>
					</div>
					{#if hasSearchQuery && groupPath}
						<span class="group-context">Group: {groupPath}</span>
					{/if}
				</div>
			</div>
		</td>
		<td>{subject.total_questions}</td>
		<td>{subject.total_pending ?? 0}</td>
		<td class="green-text">{subject.total_approved ?? 0}</td>
		<td class="red-text">{subject.total_rejected ?? 0}</td>
		<td class="action-cell">
			<div class="inline-actions action-stack">
				<button class="table-btn primary" onclick={(event) => {
					event.stopPropagation();
					void handleSubjectPrimaryAction(subject);
				}} disabled={loadingPendingCounts}>
					{subjectPrimaryActionLabel(subject)}
				</button>
				{#if getSubjectGenerationState(subject.id)?.in_progress}
					<span class="status-text generation-status">{getSubjectGenerationLabel(subject.id)}</span>
				{/if}
			</div>
		</td>
	</tr>

	{#if isExpanded(subject.id)}
		{#if loadingTopics === subject.id}
			<tr class="topic-row" transition:slide={{ duration: 180 }}>
				<td colspan="6" class="topic-loading"><span class="spinner-sm"></span> Loading topics...</td>
			</tr>
		{:else if (topicsMap[subject.id] || []).length === 0}
			<tr class="topic-row" transition:slide={{ duration: 180 }}>
				<td colspan="6" class="empty-cell">No topics found for this subject.</td>
			</tr>
		{:else}
			{#each topicsMap[subject.id] || [] as topic}
				{@const topicStats = getTopicStats(topic)}
				{@const pendingCount = topicStats.pending}
				{@const topicProgress = topicResumeSnapshot(subject.id, topic.id)}
				{@const subjectGenerationState = getSubjectGenerationState(subject.id)}
				<tr class="topic-row" transition:slide={{ duration: 180 }}>
					<td>
						<div class="topic-name-stack" style="padding-left: {depth * 1.2 + 1.2}rem">
							<div class="topic-title-line">
							<!-- ↳ -->
								<!-- <span class="topic-branch">  </span>  -->
								<strong>{topic.name}</strong>
							</div>
						</div>
					</td>
					<td>{topicStats.generated}</td>
					<td>{pendingCount}</td>
					<td class="green-text">{topicStats.approved}</td>
					<td class="red-text">{topicStats.rejected}</td>
					<td class="action-cell">
						<div class="inline-actions action-stack">
							{#if subjectGenerationState?.in_progress && pendingCount === 0}
								<span class="status-text generation-status"><span class="spinner-sm"></span>{getSubjectGenerationLabel(subject.id)}</span>
							{:else if topicProgress}
								<button class="table-btn" onclick={(event) => {
									event.stopPropagation();
									resumeSpecificProgress(topicProgress);
								}}>Resume</button>
							{:else}
								<button class="table-btn primary" onclick={(event) => {
									event.stopPropagation();
									startTopicVetting(subject.id, topic.id, topic.name, topicStats.generated);
								}} disabled={loadingPendingCounts}>Start Vetting</button>
							{/if}
						</div>
					</td>
				</tr>
			{/each}
		{/if}
	{/if}
{/snippet}

{#if showGenerateFirstModal}
	<div class="modal-backdrop" role="presentation" onclick={(event) => {
		if (event.target === event.currentTarget) closeGenerateFirstModal();
	}}>
		<div class="generate-modal glass-panel" role="dialog" tabindex="-1" aria-modal="true" aria-labelledby="generate-first-title">
			<h3 id="generate-first-title">{generateFirstTitle}</h3>
			<p>{generateFirstMessage}</p>
			<div class="modal-actions">
				<button class="table-btn" onclick={closeGenerateFirstModal}>Cancel</button>
				<button class="table-btn primary" onclick={goToGenerationPageFromModal}>Go to Generate</button>
			</div>
		</div>
	</div>
{/if}

<style>
	.page {
		max-width: 1120px;
		margin: 0 auto;
		padding: 2rem 1.25rem 2.5rem;
		display: flex;
		flex-direction: column;
		gap: 1rem;
		height: 100%;
		min-height: 0;
		overflow: hidden;
	}

	/* .hero {
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
	} */

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
		padding: 1rem;
		border-radius: 1rem;
		display: flex;
		flex-direction: column;
		gap: 0.55rem;
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

	.actions-row {
		display: flex;
		gap: 0.55rem;
		flex-wrap: wrap;
		margin-top: 0.35rem;
	}

	.content-panel {
		padding: 1rem;
		border-radius: 1.1rem;
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
		flex: 1;
		min-height: 0;
		max-height: calc(100vh);
	}

	.tab-bar {
		display: inline-flex;
		align-items: center;
		gap: 0.25rem;
		padding: 0.25rem;
		border-radius: 0.75rem;
		background: rgba(var(--theme-primary-rgb), 0.08);
		width: fit-content;
		align-self: center;
		margin: 0 auto;
	}

	.tab-btn {
		padding: 0.56rem 1.08rem;
		border-radius: 0.55rem;
		border: none;
		background: transparent;
		color: var(--theme-text-muted);
		font: inherit;
		font-size: 0.86rem;
		font-weight: 700;
		cursor: pointer;
		transition: all 0.15s ease;
	}

	.tab-btn:hover {
		background: rgba(var(--theme-primary-rgb), 0.08);
		color: var(--theme-text-primary);
	}

	.tab-btn.active {
		background: rgba(var(--theme-primary-rgb), 0.18);
		color: var(--theme-text-primary);
	}

	.panel-head {
		display: grid;
		grid-template-columns: auto 1fr auto;
		align-items: center;
		gap: 0.8rem;
	}

	.panel-head-left {
		display: inline-flex;
		align-items: center;
		gap: 0.6rem;
		min-width: 0;
	}

	.panel-head h2 {
		margin: 0;
		font-size: 1.18rem;
		color: var(--theme-text-primary);
	}

	.panel-head-center {
		display: flex;
		justify-content: center;
		min-width: 0;
	}

	.table-back-btn {
		width: 2rem;
		height: 2rem;
		border-radius: 999px;
		border: 1px solid rgba(var(--theme-primary-rgb), 0.35);
		background: rgba(var(--theme-primary-rgb), 0.1);
		color: var(--theme-primary);
		font-size: 1rem;
		font-weight: 700;
		line-height: 1;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		cursor: pointer;
		flex-shrink: 0;
		transition: background 0.15s ease, border-color 0.15s ease, transform 0.12s ease;
	}

	.table-back-btn:hover {
		background: rgba(var(--theme-primary-rgb), 0.16);
		border-color: rgba(var(--theme-primary-rgb), 0.5);
		transform: translateY(-1px);
	}

	.table-back-btn:active {
		transform: translateY(0);
	}

	.search-input {
		width: min(360px, 100%);
		padding: 0.7rem 0.8rem;
		border-radius: 0.75rem;
		border: 1px solid var(--theme-glass-border);
		background: var(--theme-input-bg);
		color: var(--theme-text-primary);
		font: inherit;
	}

	.search-input::placeholder {
		color: color-mix(in srgb, var(--theme-text-primary) 46%, #64748b);
	}

	.table-shell {
		border: 1px solid var(--theme-glass-border);
		background: var(--theme-glass-bg);
		border-radius: 0.95rem;
		overflow: auto;
		flex: 1;
		min-height: 0;
	}

	.desktop-only {
		display: block !important;
	}

	.mobile-only {
		display: none !important;
	}

	.training-mobile-list {
		display: grid;
		gap: 0.75rem;
	}

	.mobile-card {
		border: 1px solid var(--theme-glass-border);
		border-radius: 0.95rem;
		padding: 0.8rem;
		display: flex;
		flex-direction: column;
		gap: 0.55rem;
	}

	.mobile-card-head {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 0.6rem;
	}

	.mobile-topic-list {
		display: grid;
		gap: 0.5rem;
		padding-top: 0.3rem;
	}

	.mobile-topic-card {
		border: 1px solid var(--theme-glass-border);
		border-radius: 0.75rem;
		padding: 0.62rem;
		display: flex;
		flex-direction: column;
		gap: 0.42rem;
	}

	.mobile-metrics {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 0.3rem 0.8rem;
		font-size: 0.81rem;
		color: var(--theme-text-muted);
	}

	.mobile-metrics strong {
		color: var(--theme-text-primary);
	}

	.training-table {
		width: 100%;
		table-layout: fixed;
		border-collapse: collapse;
	}

	.name-col {
		width: 40%;
	}

	.num-col {
		width: 11%;
	}

	.action-col {
		width: 19%;
	}

	.training-table th {
		padding: 0.72rem 0.62rem;
		font-size: 0.72rem;
		font-weight: 800;
		letter-spacing: 0.07em;
		text-transform: uppercase;
		color: var(--theme-text-muted);
		text-align: left;
		border-bottom: 1px solid var(--theme-glass-border);
		border-right: 1px solid color-mix(in srgb, var(--theme-glass-border) 85%, transparent);
		background: rgba(255, 255, 255, 0.38);
		position: sticky;
		top: 0;
		z-index: 2;
	}

	.training-table th:last-child {
		border-right: none;
	}

	.training-table td {
		padding: 0.68rem 0.62rem;
		border-bottom: 1px solid var(--theme-glass-border);
		border-right: 1px solid color-mix(in srgb, var(--theme-glass-border) 75%, transparent);
		color: var(--theme-text-primary);
		vertical-align: top;
		word-break: break-word;
	}

	.training-table th:nth-child(n + 2),
	.training-table td:nth-child(n + 2) {
		text-align: center;
	}

	.training-table td:last-child {
		border-right: none;
	}

	.training-table tbody tr:last-child td {
		border-bottom: 1px solid var(--theme-glass-border);
	}

	.subject-row td {
		background: rgba(255, 255, 255, 0.04);
	}

	.subject-row {
		cursor: pointer;
	}

	.row-trigger {
		display: flex;
		align-items: flex-start;
		gap: 0.55rem;
		width: 100%;
	}

	.expand-btn {
		padding: 0;
		border: none;
		background: transparent;
		cursor: inherit;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 1rem;
		height: 1.2rem;
		pointer-events: none;
	}

	.chevron {
		display: inline-flex;
		width: 1rem;
		margin-top: 0.18rem;
		color: var(--theme-text-muted);
		transition: transform 0.2s ease;
	}

	.chevron.open {
		transform: rotate(90deg);
	}

	.name-stack {
		display: flex;
		flex-direction: column;
		gap: 0.28rem;
		min-width: 0;
	}

	.name-header {
		display: flex;
		align-items: center;
		gap: 2rem;
		flex-wrap: wrap;
	}

	.name-header strong {
		font-size: 1.02rem;
		color: var(--theme-text-primary);
	}

	.group-context {
		font-size: 0.78rem;
		line-height: 1.35;
		color: var(--theme-text-muted);
	}

	.code-chip {
		display: inline-flex;
		padding: 0.2rem 0.56rem;
		border-radius: 0.48rem;
		font-size: 0.72rem;
		font-weight: 700;
		letter-spacing: 0.05em;
		text-transform: uppercase;
		background: rgba(var(--theme-primary-rgb), 0.16);
		border: 1px solid rgba(var(--theme-primary-rgb), 0.34);
		color: var(--theme-primary);
	}

	.topic-row td {
		background: rgba(255, 255, 255, 0.02);
	}

	.topic-row td:first-child {
		padding-left: 1.5rem;
	}

	.topic-name-stack {
		display: flex;
		flex-direction: column;
		gap: 0.26rem;
	}

	.topic-title-line {
		display: flex;
		align-items: center;
		gap: 0.35rem;
		min-width: 0;
	}

	.topic-branch {
		color: color-mix(in srgb, var(--theme-primary) 72%, var(--theme-text-primary));
		font-weight: 700;
	}

	.topic-title-line strong {
		font-size: 0.96rem;
		color: var(--theme-text-primary);
		font-weight: 700;
	}

	/* .subject-in-group-branch {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		font-size: 0.9rem;
		font-weight: 700;
		color: color-mix(in srgb, var(--theme-primary) 68%, var(--theme-text-muted));
		margin-right: 0.2rem;
	} */

	.inline-actions {
		display: flex;
		flex-wrap: nowrap;
		gap: 0.38rem;
		overflow-x: auto;
		padding-bottom: 0.12rem;
		justify-content: flex-end;
		align-items: center;
	}

	.action-stack {
		flex-direction: column;
		align-items: center;
		justify-content: center;
		overflow: visible;
		padding-bottom: 0;
		gap: 0.42rem;
	}

	.action-cell {
		text-align: center;
		vertical-align: middle;
	}

	.table-btn,
	.primary-btn {
		padding: 0.42rem 0.74rem;
		border-radius: 999px;
		border: 1px solid rgba(var(--theme-primary-rgb), 0.35);
		font: inherit;
		font-size: 0.78rem;
		font-weight: 700;
		cursor: pointer;
		min-width: 118px;
		text-align: center;
	}

	.primary-btn {
		background: rgba(var(--theme-primary-rgb), 0.2);
		color: var(--theme-text-primary);
	}

	.table-btn {
		background: rgba(var(--theme-primary-rgb), 0.1);
		color: var(--theme-primary);
	}

	.table-btn.primary {
		background: rgba(var(--theme-primary-rgb), 0.2);
		color: var(--theme-text-primary);
	}

	.table-btn:disabled,
	.primary-btn:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}

	.status-text {
		font-size: 0.75rem;
		font-weight: 700;
		color: var(--theme-primary);
	}

	.generation-status {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		padding: 0.2rem 0.62rem;
		border-radius: 999px;
		background: rgba(var(--theme-primary-rgb), 0.12);
		border: 1px solid rgba(var(--theme-primary-rgb), 0.28);
		min-width: 96px;
	}

	.topic-loading {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		color: var(--theme-text-secondary);
	}

	.spinner-sm {
		width: 16px;
		height: 16px;
		border-radius: 50%;
		border: 2px solid rgba(255, 255, 255, 0.2);
		border-top-color: var(--theme-primary);
		animation: spin 0.8s linear infinite;
	}

	.empty-cell {
		text-align: center;
		color: var(--theme-text-muted);
		padding: 0.95rem 0.7rem;
	}

	.error-banner {
		padding: 0.9rem 1rem;
		border-radius: 1rem;
		background: rgba(239, 68, 68, 0.12);
		border: 1px solid rgba(239, 68, 68, 0.3);
		color: #b91c1c;
	}

	.modal-backdrop {
		position: fixed;
		inset: 0;
		background: rgba(15, 23, 42, 0.52);
		display: grid;
		place-items: center;
		z-index: 120;
		padding: 1rem;
	}

	.generate-modal {
		width: min(420px, 100%);
		padding: 1rem;
		border-radius: 1rem;
		display: flex;
		flex-direction: column;
		gap: 0.8rem;
	}

	.generate-modal h3 {
		margin: 0;
		font-size: 1.1rem;
		color: var(--theme-text-primary);
	}

	.generate-modal p {
		margin: 0;
		color: var(--theme-text-secondary);
		line-height: 1.45;
	}

	.modal-actions {
		display: flex;
		justify-content: flex-end;
		gap: 0.5rem;
	}

	.green-text {
		color: #059669;
	}

	.red-text {
		color: #dc2626;
	}

	.spinner {
		width: 30px;
		height: 30px;
		border-radius: 50%;
		border: 3px solid rgba(255, 255, 255, 0.2);
		border-top-color: var(--theme-primary);
		animation: spin 0.8s linear infinite;
	}

	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}

	:global([data-color-mode='light']) .training-table th {
		border-bottom-color: rgba(148, 163, 184, 0.42);
		border-right-color: rgba(148, 163, 184, 0.42);
	}

	:global([data-color-mode='light']) .training-table td {
		border-bottom-color: rgba(148, 163, 184, 0.38);
		border-right-color: rgba(148, 163, 184, 0.38);
	}

	:global([data-color-mode='light']) .search-input {
		background: rgba(255, 255, 255, 0.96);
		border-color: rgba(100, 116, 139, 0.5);
		color: #1f2937;
		box-shadow: 0 1px 0 rgba(255, 255, 255, 0.85), 0 0 0 1px rgba(255, 255, 255, 0.35) inset;
	}

	:global([data-color-mode='light']) .search-input::placeholder {
		color: #64748b;
	}

	:global([data-color-mode='light']) .search-input:focus {
		outline: none;
		border-color: rgba(var(--theme-primary-rgb), 0.62);
		box-shadow: 0 0 0 3px rgba(var(--theme-primary-rgb), 0.18);
	}

	:global([data-color-mode='light']) .code-chip {
		background: rgba(var(--theme-primary-rgb), 0.14);
		border-color: rgba(var(--theme-primary-rgb), 0.34);
		color: color-mix(in srgb, var(--theme-primary) 84%, #111827);
	}

	:global([data-color-mode='dark']) .code-chip {
		background: rgba(var(--theme-primary-rgb), 0.26);
		border-color: rgba(var(--theme-primary-rgb), 0.5);
		color: color-mix(in srgb, var(--theme-primary) 72%, #ffffff);
	}

	@media (max-width: 960px) {
		.desktop-only {
			display: none !important;
		}

		.mobile-only {
			display: grid !important;
		}

		.page {
			height: auto;
			overflow: visible;
			padding: max(0.9rem, env(safe-area-inset-top)) 0.9rem max(2.75rem, env(safe-area-inset-bottom));
			gap: 0.85rem;
		}

		/* .kicker {
			display: none;
		}

		.title {
			font-size: 1.6rem;
		} */

		.summary-grid {
			grid-template-columns: 1fr;
			gap: 0.45rem;
		}

		.panel-head {
			flex-direction: column;
			align-items: stretch;
			display: flex;
		}

		.tab-bar {
			align-self: center;
		}

		.panel-head-left {
			width: 100%;
		}

		.search-input {
			width: 100%;
		}

		.training-table th,
		.training-table td {
			padding: 0.56rem 0.42rem;
			font-size: 0.83rem;
		}

		.name-header strong {
			font-size: 0.9rem;
		}

		.code-chip {
			font-size: 0.64rem;
		}

		.table-btn,
		.primary-btn {
			font-size: 0.72rem;
			padding: 0.36rem 0.58rem;
		}

		.table-shell {
			flex: initial;
			min-height: auto;
		}
	}

</style>