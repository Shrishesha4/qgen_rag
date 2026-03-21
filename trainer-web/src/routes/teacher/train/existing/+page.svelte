<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { session } from '$lib/session';
	import {
		listSubjects,
		getSubject,
		createTopic,
		deleteSubject,
		type SubjectResponse,
		type TopicResponse,
	} from '$lib/api/subjects';
	import {
		listReferenceDocuments,
		getDocumentStatus,
		uploadDocument,
		deleteDocumentById,
		scheduleBackgroundGeneration,
		getBackgroundGenerationStatuses,
		type BackgroundGenerationStatusItem,
		type ReferenceDocumentItem,
	} from '$lib/api/documents';
	import { estimateQuestionCapacity } from '$lib/api/question-capacity';
	import {
		createTeacherVettingLoopUrl,
		findTeacherVettingProgressForSubject,
		hydrateTeacherVettingProgressStoreFromRemote,
		latestTeacherVettingProgressBySubject,
		type TeacherVettingProgressSnapshot,
		type TeacherVettingProgressStore,
	} from '$lib/vetting-progress';

	onMount(() => {
		const unsub = session.subscribe((s) => {
			if (!s) goto('/teacher/login');
		});
		loadSubjects();
		void refreshTeacherVettingProgress();

		function handleProgressRefresh() {
			void refreshTeacherVettingProgress();
		}

		window.addEventListener('focus', handleProgressRefresh);
		window.addEventListener('storage', handleProgressRefresh);

		return () => {
			unsub();
			window.removeEventListener('focus', handleProgressRefresh);
			window.removeEventListener('storage', handleProgressRefresh);
		};
	});

	let subjects = $state<SubjectResponse[]>([]);
	let loading = $state(true);
	let error = $state('');
	let searchQuery = $state('');

	let expandedId = $state('');
	let topicsMap = $state<Record<string, TopicResponse[]>>({});
	let loadingTopics = $state('');
	let addingTopicFor = $state('');
	let showAddTopicModal = $state(false);
	let addTopicSubjectId = $state('');
	let addTopicSubjectName = $state('');
	let addTopicName = $state('');
	let addTopicSyllabus = $state('');
	let deletingSubjectId = $state('');

	let showReferenceModal = $state(false);
	let referenceSubjectId = $state('');
	let referenceSubjectName = $state('');
	let referenceTab = $state<'pdfs' | 'questions'>('pdfs');
	let referenceLoading = $state(false);
	let referenceUploading = $state(false);
	let deletingRefId = $state('');
	let referenceError = $state('');
	let pdfUploadType = $state<'reference_book' | 'template_paper'>('reference_book');
	let referenceBooks = $state<ReferenceDocumentItem[]>([]);
	let templatePapers = $state<ReferenceDocumentItem[]>([]);
	let referenceQuestions = $state<ReferenceDocumentItem[]>([]);
	let referenceProgressByDoc = $state<Record<string, number>>({});
	let referenceProgressDetailByDoc = $state<Record<string, string>>({});
	let referencePollTimer: ReturnType<typeof setInterval> | null = null;
	
	// New state for per-topic PDF management
	let selectedTopicId = $state('');
	let selectedTopicName = $state('');
	let topicDocuments = $state<Record<string, ReferenceDocumentItem[]>>({});
	let loadingTopicDocuments = $state('');
	let bgStatusBySubject = $state<Record<string, BackgroundGenerationStatusItem>>({});
	let bgStatusPollTimer: ReturnType<typeof setInterval> | null = null;

	let showGenerateModeModal = $state(false);
	let generateModalStep = $state<'choice' | 'config'>('choice');
	let generateTargetSubject = $state<SubjectResponse | null>(null);
	let generateTargetTopicId = $state<string | null>(null);
	let generateTargetMode = $state<'mixed' | 'topic'>('mixed');
	let generateQuestionCount = $state(10);
	let generateTopicScope = $state<'all' | 'selected'>('all');
	let generateSelectedTopicIds = $state<string[]>([]);
	let generateModalTopics = $state<TopicResponse[]>([]);
	let loadingGenerateTopics = $state(false);
	let schedulingBulk = $state(false);
	let generateModeError = $state('');
	let generateModeSuccess = $state('');
	let capacityEstimate = $state<{
	subject_id: string;
	primary_documents: number;
	completed_documents: number;
	reference_documents: number;
	template_documents: number;
	total_chunks: number;
	discovery_strategy: string;
} | null>(null);
	let loadingCapacity = $state(false);
	let teacherVettingProgressStore = $state<TeacherVettingProgressStore>({});
	let latestVettingProgressBySubject = $state<Record<string, TeacherVettingProgressSnapshot>>({});

	const BG_STATUS_CACHE_KEY = 'trainer.bgGenerationStatusCache.v1';
	const BG_STATUS_CACHE_TTL_MS = 2 * 60 * 60 * 1000;
	const BG_STATUS_MAX_MISSES = 10;

	const PROCESSING_DOC_STATUSES = new Set(['pending', 'processing']);

	function clearReferencePolling() {
		if (referencePollTimer) {
			clearInterval(referencePollTimer);
			referencePollTimer = null;
		}
	}

	function clearBackgroundStatusPolling() {
		if (bgStatusPollTimer) {
			clearInterval(bgStatusPollTimer);
			bgStatusPollTimer = null;
		}
	}

	async function openGenerateModeModal(subject: SubjectResponse, mode: 'mixed' | 'topic', topicId: string | null = null) {
		generateTargetSubject = subject;
		generateTargetMode = mode;
		generateQuestionCount = 10;
		generateTopicScope = mode === 'topic' ? 'selected' : 'all';
		generateTargetTopicId = topicId;
		generateModalTopics = topicsMap[subject.id] || [];
		capacityEstimate = null;
		
		// Load capacity estimation for better default
		loadingCapacity = true;
		try {
			const capacity = await estimateQuestionCapacity(subject.id);
			capacityEstimate = capacity;
		} catch (e) {
			console.error('Failed to load capacity estimate:', e);
		} finally {
			loadingCapacity = false;
		}
		
		generateModalStep = 'choice';
		generateSelectedTopicIds = topicId ? [topicId] : [];
		showGenerateModeModal = true;

		if (generateModalTopics.length === 0) {
			loadingGenerateTopics = true;
			try {
				const detail = await getSubject(subject.id);
				topicsMap = { ...topicsMap, [subject.id]: detail.topics };
				generateModalTopics = detail.topics;
				if (mode === 'mixed' && !topicId) {
					generateSelectedTopicIds = detail.topics.map((topic) => topic.id);
				}
				if (!generateTargetTopicId && detail.topics.length > 0) {
					generateTargetTopicId = detail.topics[0].id;
				}
			} catch {
				generateModeError = 'Unable to load topics for selection';
			} finally {
				loadingGenerateTopics = false;
			}
		} else if (!generateTargetTopicId && generateModalTopics.length > 0) {
			if (mode === 'mixed' && !topicId) {
				generateSelectedTopicIds = generateModalTopics.map((topic) => topic.id);
			}
			generateTargetTopicId = generateModalTopics[0].id;
		}
	}

	function closeGenerateModeModal(force = false) {
		if (schedulingBulk && !force) return;
		showGenerateModeModal = false;
		generateTargetSubject = null;
		generateTargetTopicId = null;
		generateTargetMode = 'mixed';
		generateModalStep = 'choice';
		generateTopicScope = 'all';
		generateSelectedTopicIds = [];
		generateQuestionCount = 10;
		generateModalTopics = [];
		generateModeError = '';
	}

	function toggleGenerateTopicSelection(topicId: string) {
		if (generateSelectedTopicIds.includes(topicId)) {
			generateSelectedTopicIds = generateSelectedTopicIds.filter((id) => id !== topicId);
			return;
		}
		generateSelectedTopicIds = [...generateSelectedTopicIds, topicId];
	}

	function selectAllGenerateTopics() {
		generateSelectedTopicIds = generateModalTopics.map((topic) => topic.id);
	}

	function clearGenerateTopics() {
		generateSelectedTopicIds = [];
	}

	async function refreshTeacherVettingProgress() {
		const store = await hydrateTeacherVettingProgressStoreFromRemote();
		teacherVettingProgressStore = store;
		latestVettingProgressBySubject = latestTeacherVettingProgressBySubject(store);
	}

	function getSavedProgressForSubject(subjectId: string): TeacherVettingProgressSnapshot | null {
		return latestVettingProgressBySubject[subjectId] ?? null;
	}

	function formatSavedProgressCounter(snapshot: TeacherVettingProgressSnapshot): string {
		const total = snapshot.questions.length;
		if (total <= 0) return '0/0';
		const current = Math.min(total, Math.max(1, snapshot.currentIndex + 1));
		return `${current}/${total}`;
	}

	function continueSavedProgress(snapshot: TeacherVettingProgressSnapshot) {
		goto(createTeacherVettingLoopUrl(snapshot, { resume: true, resumeKey: snapshot.key }));
	}

	function buildVetNowUrl(subjectId: string, topicId: string | null, resume: boolean): string {
		const params = new URLSearchParams();
		params.set('subject', subjectId);
		if (topicId) params.set('topic', topicId);
		params.set('resume', resume ? '1' : '0');
		return `/teacher/train/loop?${params.toString()}`;
	}

	onDestroy(() => {
		clearReferencePolling();
		clearBackgroundStatusPolling();
		if (bgSubjectRefreshTimer) { clearInterval(bgSubjectRefreshTimer); bgSubjectRefreshTimer = null; }
		if (searchDebounceTimer) { clearTimeout(searchDebounceTimer); searchDebounceTimer = null; }
	});

	const optimisticUpdates = $state<Record<string, boolean>>({});

	function getSubjectBgStatus(subjectId: string): BackgroundGenerationStatusItem | null {
		return bgStatusBySubject[subjectId] ?? null;
	}

	function readCachedBgStatuses(): Record<string, BackgroundGenerationStatusItem> {
		if (typeof window === 'undefined') return {};
		try {
			const raw = window.localStorage.getItem(BG_STATUS_CACHE_KEY);
			if (!raw) return {};
			const parsed = JSON.parse(raw) as Record<string, BackgroundGenerationStatusItem>;
			const now = Date.now();
			const next: Record<string, BackgroundGenerationStatusItem> = {};
			for (const [subjectId, status] of Object.entries(parsed)) {
				const ts = status.updated_at ? Date.parse(status.updated_at) : 0;
				// Keep in-progress statuses regardless of age (they'll be validated by server)
				// Also keep completed statuses that were recently completed (within last 5 minutes)
				const isCompleted = !status.in_progress && status._completedAt;
				const isRecentCompleted = isCompleted && (now - (status._completedAt || 0)) < 300000; // 5 minutes
				if (status.in_progress || isRecentCompleted) {
					if (Number.isFinite(ts)) {
						next[subjectId] = status;
					}
				}
			}
			console.log('[bg-gen] Loaded cached statuses', {
				totalCached: Object.keys(parsed).length,
				keptInProgress: Object.keys(next).filter(id => next[id].in_progress).length,
				keptRecentCompleted: Object.keys(next).filter(id => !next[id].in_progress).length,
			});
			return next;
		} catch (error) {
			console.warn('[bg-gen] Failed to load cached statuses', error);
			return {};
		}
	}

	function writeCachedBgStatuses(statuses: Record<string, BackgroundGenerationStatusItem>) {
		if (typeof window === 'undefined') return;
		try {
			window.localStorage.setItem(BG_STATUS_CACHE_KEY, JSON.stringify(statuses));
		} catch {
			// ignore storage failures
		}
	}

	function getBgCounter(subjectId: string): string {
		const status = getSubjectBgStatus(subjectId);
		if (!status || !status.in_progress) return '';

		const startedTotal = status.started_total_questions ?? null;
		const targetTotal = status.target_total_questions ?? null;
		
		// For active generation, show task progress (current/total_for_this_task) rather than absolute totals
		// This is more intuitive when user requests X questions - they want to see X/X, not (existing+X)/(existing+X)
		const total = status.total_questions ?? null;
		if (total !== null && total > 0) {
			const current = Math.max(0, status.current_question || 0);
			return `${current}/${total}`;
		}
		
		// Fallback: use absolute counting when we have target/started totals but no task total
		if (startedTotal !== null && targetTotal !== null && targetTotal > startedTotal) {
			const taskTotal = targetTotal - startedTotal;
			const generatedCurrent = Math.max(0, status.current_question || 0);
			const taskCurrent = Math.min(taskTotal, generatedCurrent);
			return `${taskCurrent}/${taskTotal}`;
		}
		
		// Edge case: no total yet, show just current with '?' placeholder
		const current = Math.max(0, status.current_question || 0);
		return current > 0 ? `${current}/?` : '0/?';
	}

	function getBgProgress(subjectId: string): number {
		const status = getSubjectBgStatus(subjectId);
		if (!status || !status.in_progress) return 0;
		const rawProgress = Math.max(0, Math.min(100, status.progress || 0));
		const total = status.total_questions ?? 0;
		const current = Math.max(0, status.current_question || 0);
		
		if (total > 0) {
			const ratioProgress = Math.max(0, Math.min(100, Math.round((current / total) * 100)));
			return Math.max(rawProgress, ratioProgress);
		}
		return rawProgress;
	}

	function getBgStatusLabel(subjectId: string): string {
		const status = getSubjectBgStatus(subjectId);
		if (!status || !status.in_progress) return '';
		const state = (status.status || '').toLowerCase();
		if (state === 'waiting_for_documents') return 'Waiting for docs';
		if (state === 'queued') return `Queued #${status.message?.match(/position (\d+)/)?.[1] || '?'}`;
		if (state === 'scheduled') return 'Scheduled';
		if (state === 'processing') return 'Preparing';
		if (state === 'error' || state === 'failed') return 'Generation failed';
		if (state === 'complete' || state === 'completed') return 'Complete';
		return 'Generating';
	}

	let bgPolling = false;
	let bgSubjectRefreshTimer: ReturnType<typeof setTimeout> | null = null;
	let bgMissCountBySubject = $state<Record<string, number>>({});

	async function refreshBackgroundStatuses() {
		// Concurrency guard — skip if a previous poll is still in-flight
		if (bgPolling) return;
		bgPolling = true;
		try {
			if (!subjects.length) {
				bgStatusBySubject = readCachedBgStatuses();
				bgMissCountBySubject = {};
				return;
			}

			// Only poll for subjects that are visible or have active status
			const subjectIds = subjects.filter(s => {
				const status = bgStatusBySubject[s.id];
				return status?.in_progress || !status; // Include unknown status
			}).map(s => s.id);

			if (subjectIds.length === 0) {
				// No active subjects, reduce polling frequency
				console.log('[bg-gen] No active subjects, skipping poll');
				return;
			}

			const res = await getBackgroundGenerationStatuses(subjectIds);
			const live = res.statuses || {};
			const subjectTotalById = Object.fromEntries(subjects.map((s) => [s.id, s.total_questions]));

			// console.log('[bg-gen] Polling statuses', {
			// 	subjectCount: subjectIds.length,
			// 	wasInProgressCount: Object.keys(bgStatusBySubject).filter(id => bgStatusBySubject[id]?.in_progress).length,
			// 	liveStatusCount: Object.keys(live).length,
			// });

			// Simple, robust state update strategy
			const updated: Record<string, BackgroundGenerationStatusItem> = { ...bgStatusBySubject };
			const nowMs = Date.now();
			
			// Track state changes before updating
			const wasInProgressCount = Object.keys(bgStatusBySubject).filter(id => bgStatusBySubject[id]?.in_progress).length;

			for (const subjectId of subjectIds) {
				const serverStatus = live[subjectId];
				const currentStatus = updated[subjectId];

				// Handle completed indicators - auto dismiss after 3 seconds
				if (currentStatus?._completedAt && nowMs - currentStatus._completedAt > 3000) {
					delete updated[subjectId];
					continue;
				}

				if (serverStatus) {
					// Server has data - use it, but preserve some client-side state
					const shouldPreserveCompleted = currentStatus?._completedAt && 
						!serverStatus.in_progress && 
						serverStatus.status === 'completed';
					
					updated[subjectId] = {
						...serverStatus,
						// Preserve client-side completed timestamp if server says completed but we had it first
						_completedAt: shouldPreserveCompleted ? currentStatus._completedAt : undefined,
					};
					
					// If we just preserved a completed state, set a timer to remove it
					if (shouldPreserveCompleted && !updated[subjectId]._completedAt) {
						updated[subjectId]._completedAt = nowMs;
					}
					
					// Clear optimistic flag when we get server data
					if (optimisticUpdates[subjectId]) {
						delete optimisticUpdates[subjectId];
					}
				} else if (currentStatus?.in_progress) {
					// Server has no data but we have an in-progress status
					// Keep it unless it's very old or completed
					const ageMs = currentStatus.updated_at ? nowMs - Date.parse(currentStatus.updated_at) : 0;
					
					// Remove if it's completed (no longer in_progress on server) and old enough
					if (!optimisticUpdates[subjectId] && ageMs > 30000) { // 30 seconds for non-optimistic
						// console.log('[bg-gen] Removing old in-progress status', { subjectId, ageMs });
						delete updated[subjectId];
					}
					// Keep optimistic updates for longer (5 minutes)
					else if (optimisticUpdates[subjectId] && ageMs > 300000) { // 5 minutes
						console.log('[bg-gen] Removing old optimistic status', { subjectId, ageMs });
						delete updated[subjectId];
						delete optimisticUpdates[subjectId];
					}
				}
				// If no server status and no current status, do nothing
			}

			// Single atomic state update
			bgStatusBySubject = updated;
			writeCachedBgStatuses(updated);

			const nowInProgressCount = Object.keys(updated).filter(id => updated[id]?.in_progress).length;
			// console.log('[bg-gen] Status update complete', {
			// 	nowInProgressCount,
			// 	wasInProgressCount,
			// 	optimisticRemaining: Object.keys(optimisticUpdates).length,
			// });

			// Restart polling if state changed significantly (e.g., new in-progress started)
			if (nowInProgressCount !== wasInProgressCount) {
				// console.log('[bg-gen] State changed, restarting polling');
				ensureBackgroundStatusPolling();
			}

		} catch (error) {
			console.error('[bg-gen] Error refreshing statuses', error);
			// Keep existing state on error to avoid flicker
		} finally {
			bgPolling = false;
		}
	}

	function ensureBackgroundStatusPolling() {
		clearBackgroundStatusPolling();
		if (bgSubjectRefreshTimer) { clearInterval(bgSubjectRefreshTimer); bgSubjectRefreshTimer = null; }
		if (!subjects.length) return;
		
		const hasInProgress = Object.keys(bgStatusBySubject).some(id => bgStatusBySubject[id]?.in_progress);
		// Further reduced polling frequency for mobile devices
		const isMobile = window.innerWidth <= 768;
		const pollInterval = hasInProgress 
			? (isMobile ? 6000 : 4000)  // 6s mobile, 4s desktop when active
			: (isMobile ? 10000 : 6000); // 10s mobile, 6s desktop when idle
		
		bgStatusPollTimer = setInterval(() => {
			void refreshBackgroundStatuses();
		}, pollInterval);
		
		// Further reduced frequency for subject refresh on mobile
		const subjectRefreshInterval = isMobile ? 20000 : 15000; // 20s mobile, 15s desktop
		bgSubjectRefreshTimer = setInterval(() => {
			for (const [subjectId, status] of Object.entries(bgStatusBySubject)) {
				if (status.in_progress) {
					void refreshSubject(subjectId);
				}
			}
		}, subjectRefreshInterval);
		
		// console.log('[bg-gen] Started polling', { pollInterval, hasInProgress, isMobile });
	}

	function allReferenceDocs() {
		return [...referenceBooks, ...templatePapers, ...referenceQuestions];
	}

	function isDocProcessing(status: string) {
		return PROCESSING_DOC_STATUSES.has((status || '').toLowerCase());
	}

	function hasAnyProcessingDocs() {
		return allReferenceDocs().some((doc) => isDocProcessing(doc.processing_status));
	}

	async function refreshReferenceProgressForProcessingDocs() {
		const processingDocs = allReferenceDocs().filter((doc) => isDocProcessing(doc.processing_status));
		if (processingDocs.length === 0) return;

		const updates = await Promise.all(
			processingDocs.map(async (doc) => {
				try {
					const status = await getDocumentStatus(doc.id);
					return {
						id: doc.id,
						progress: status.processing_progress ?? 0,
						detail: status.processing_detail ?? status.processing_step ?? '',
					};
				} catch {
					return {
						id: doc.id,
						progress: 0,
						detail: '',
					};
				}
			})
		);

		const nextProgress = { ...referenceProgressByDoc };
		const nextDetail = { ...referenceProgressDetailByDoc };
		for (const update of updates) {
			nextProgress[update.id] = update.progress;
			nextDetail[update.id] = update.detail;
		}
		referenceProgressByDoc = nextProgress;
		referenceProgressDetailByDoc = nextDetail;
	}

	function ensureReferenceProgressPolling() {
		clearReferencePolling();
		if (!showReferenceModal || !hasAnyProcessingDocs()) return;
		// Further reduced polling frequency on mobile
		const isMobile = window.innerWidth <= 768;
		const pollInterval = isMobile ? 7000 : 5000; // 7s mobile, 5s desktop
		referencePollTimer = setInterval(() => {
			void loadReferenceMaterials(referenceSubjectId, false);
		}, pollInterval);
	}

	// Debounced search query to reduce filtering frequency
	let debouncedSearchQuery = $state('');
	let searchDebounceTimer: ReturnType<typeof setTimeout> | null = null;
	
	// Optimized filtering with memoization
	let filteredSubjects = $derived.by(() => {
		const query = debouncedSearchQuery.toLowerCase().trim();
		if (!query) {
			return subjects.map((subject) => ({
				subject,
				filteredTopics: topicsMap[subject.id] || [],
				subjectMatches: true
			}));
		}
		
		return subjects.map((subject) => {
			const subjectMatches = 
				subject.name.toLowerCase().includes(query) ||
				subject.code.toLowerCase().includes(query);
			
			const topics = topicsMap[subject.id] || [];
			const filteredTopics = topics.filter((topic) =>
				topic.name.toLowerCase().includes(query) ||
				(topic.syllabus_content && topic.syllabus_content.toLowerCase().includes(query))
			);
			
			return { subject, filteredTopics, subjectMatches };
		}).filter((item) => item.subjectMatches || item.filteredTopics.length > 0);
	});
	
	// Debounced search handler
	function handleSearchChange(value: string) {
		searchQuery = value;
		if (searchDebounceTimer) clearTimeout(searchDebounceTimer);
		// Longer debounce on mobile for better performance
		const isMobile = window.innerWidth <= 768;
		const debounceTime = isMobile ? 250 : 150; // 250ms mobile, 150ms desktop
		searchDebounceTimer = setTimeout(() => {
			debouncedSearchQuery = value;
		}, debounceTime);
	}

	async function loadSubjects() {
		loading = true;
		error = '';
		try {
			const res = await listSubjects(1, 100);
			subjects = res.subjects;
			await refreshBackgroundStatuses();
			ensureBackgroundStatusPolling();
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to load subjects';
		} finally {
			loading = false;
		}
	}

	async function refreshSubject(subjectId: string) {
		try {
			const detail = await getSubject(subjectId);
			topicsMap = { ...topicsMap, [subjectId]: detail.topics };
			subjects = subjects.map((s) =>
				s.id === subjectId
					? {
						...s,
						total_topics: detail.total_topics,
						total_questions: detail.total_questions,
					}
					: s
			);
		} catch {
			// keep stale view on refresh failure
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

	async function ensureReadyToGenerate(subject: SubjectResponse): Promise<boolean> {
		try {
			const refs = await listReferenceDocuments(subject.id);
			referenceBooks = refs.reference_books || [];
			templatePapers = refs.template_papers || [];
			referenceQuestions = refs.reference_questions || [];
			await refreshReferenceProgressForProcessingDocs();
			if (hasAnyProcessingDocs()) {
				referenceError = 'Some reference files are still processing. Please wait for completion.';
				referenceSubjectId = subject.id;
				referenceSubjectName = subject.name;
				referenceTab = 'pdfs';
				showReferenceModal = true;
				ensureReferenceProgressPolling();
				return false;
			}
			return true;
		} catch {
			return true;
		}
	}

	async function trainTopic(subject: SubjectResponse, topicId: string) {
		await openGenerateModeModal(subject, 'topic', topicId);
	}

	async function trainSubjectMixed(subject: SubjectResponse) {
		await openGenerateModeModal(subject, 'mixed');
	}

	function normalizedGenerateCount() {
		const safe = Number.isFinite(generateQuestionCount) ? generateQuestionCount : 10;
		return Math.max(1, Math.min(200, Math.trunc(safe)));
	}

	function chooseVetNow() {
		if (!generateTargetSubject) return;
		const topicScoped = generateTargetMode === 'topic' ? generateTargetTopicId : null;
		const existingProgress = findTeacherVettingProgressForSubject(
			teacherVettingProgressStore,
			generateTargetSubject.id,
			topicScoped
		);

		if (existingProgress) {
			const shouldResume = confirm(
				'There is an existing vetting progress for this subject or topic. Would you like to resume?'
			);
			if (shouldResume) {
				goto(createTeacherVettingLoopUrl(existingProgress, { resume: true, resumeKey: existingProgress.key }));
				return;
			}
		}

		goto(buildVetNowUrl(generateTargetSubject.id, topicScoped, false));
	}

	function chooseVetLater() {
		// Transition to step 2 — show the full config form
		generateModalStep = 'config';
	}

	async function chooseGenAndVetLater() {
		if (!generateTargetSubject || schedulingBulk) return;
		const count = normalizedGenerateCount();
		const topicScoped = generateTargetMode === 'topic' ? generateTargetTopicId : null;
		const selectedTopicIds =
			generateTargetMode === 'mixed' && generateTopicScope === 'selected'
				? generateSelectedTopicIds
				: [];

		if (generateTargetMode === 'topic' && !topicScoped) {
			generateModeError = 'Please select a topic.';
			return;
		}
		if (generateTargetMode === 'mixed' && generateTopicScope === 'selected' && selectedTopicIds.length === 0) {
			generateModeError = 'Select at least one topic.';
			return;
		}
		schedulingBulk = true;
		generateModeError = '';
		generateModeSuccess = '';
		try {
			const scheduleRes = await scheduleBackgroundGeneration({
				subjectId: generateTargetSubject.id,
				count,
				types: 'mcq',
				difficulty: 'medium',
				topicId: topicScoped || (selectedTopicIds.length === 1 ? selectedTopicIds[0] : undefined),
				topicIds: !topicScoped && selectedTopicIds.length > 1 ? selectedTopicIds : undefined,
			});
			// Handle different response statuses
			let statusMessage = '';
			let optimisticStatus = 'scheduled';
			
			if (scheduleRes.status === 'queued') {
				statusMessage = `Background generation queued for ${generateTargetSubject.name} (${count} questions). Position: ${scheduleRes.queue_position ?? '?'}.`;
				optimisticStatus = 'queued';
			} else if (scheduleRes.status === 'already_running') {
				statusMessage = `Background generation already running for ${generateTargetSubject.name}.`;
				optimisticStatus = 'generating';
			} else {
				statusMessage = `Background generation started for ${generateTargetSubject.name} (${count} questions). You can vet later.`;
			}
			
			const optimistic = {
				...bgStatusBySubject,
				[generateTargetSubject.id]: {
					in_progress: true,
					run_id: scheduleRes.run_id || `${Date.now()}-${generateTargetSubject.id}`,
					status: optimisticStatus,
					progress: optimisticStatus === 'queued' ? 0 : 1,
					current_question: 0,
					total_questions: count,
					started_total_questions: generateTargetSubject.total_questions,
					target_total_questions: generateTargetSubject.total_questions + count,
					message: scheduleRes.message || 'Background generation scheduled',
					updated_at: new Date().toISOString(),
				},
			};
			bgStatusBySubject = optimistic;
			optimisticUpdates[generateTargetSubject.id] = true;
			writeCachedBgStatuses(optimistic);
			generateModeSuccess = statusMessage;
			closeGenerateModeModal(true);
		} catch (e: unknown) {
			generateModeError = e instanceof Error ? e.message : 'Failed to schedule background generation';
		} finally {
			schedulingBulk = false;
		}
	}

	function openAddTopicModal(subject: SubjectResponse) {
		addTopicSubjectId = subject.id;
		addTopicSubjectName = subject.name;
		addTopicName = '';
		addTopicSyllabus = '';
		error = '';
		showAddTopicModal = true;
	}

	function closeAddTopicModal() {
		showAddTopicModal = false;
		addTopicSubjectId = '';
		addTopicSubjectName = '';
		addTopicName = '';
		addTopicSyllabus = '';
	}

	async function addTopicRow(subjectId: string) {
		const name = addTopicName.trim();
		const syllabus = addTopicSyllabus.trim();
		if (!name || addingTopicFor) return;

		addingTopicFor = subjectId;
		error = '';
		try {
			const currentTopics = topicsMap[subjectId] || [];
			await createTopic(subjectId, {
				name,
				subject_id: subjectId,
				order_index: currentTopics.length,
				syllabus_content: syllabus || undefined,
			});

			closeAddTopicModal();
			await refreshSubject(subjectId);
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to add topic';
		} finally {
			addingTopicFor = '';
		}
	}

	function formatDate(iso: string): string {
		return new Date(iso).toLocaleDateString('en-US', {
			month: 'short',
			day: 'numeric',
			year: 'numeric',
		});
	}

	async function openReferenceModal(subject: SubjectResponse) {
		referenceSubjectId = subject.id;
		referenceSubjectName = subject.name;
		referenceTab = 'pdfs';
		referenceError = '';
		selectedTopicId = '';
		selectedTopicName = '';
		topicDocuments = {};
		showReferenceModal = true;
		
		// Load topics for this subject
		if (!topicsMap[subject.id]) {
			loadingTopics = subject.id;
			try {
				const detail = await getSubject(subject.id);
				topicsMap = { ...topicsMap, [subject.id]: detail.topics };
			} catch {
				topicsMap = { ...topicsMap, [subject.id]: [] };
			} finally {
				loadingTopics = '';
			}
		}
		
		await loadReferenceMaterials(subject.id);
		await refreshBackgroundStatuses();
	}

	function closeReferenceModal() {
		clearReferencePolling();
		showReferenceModal = false;
		referenceSubjectId = '';
		referenceSubjectName = '';
		referenceError = '';
		selectedTopicId = '';
		selectedTopicName = '';
		topicDocuments = {};
		referenceBooks = [];
		templatePapers = [];
		referenceQuestions = [];
		referenceProgressByDoc = {};
		referenceProgressDetailByDoc = {};
	}

	async function loadReferenceMaterials(subjectId: string, withLoader = true) {
		if (withLoader) referenceLoading = true;
		referenceError = '';
		try {
			const res = await listReferenceDocuments(subjectId);
			referenceBooks = res.reference_books || [];
			templatePapers = res.template_papers || [];
			referenceQuestions = res.reference_questions || [];
			await refreshReferenceProgressForProcessingDocs();
			ensureReferenceProgressPolling();
		} catch (e: unknown) {
			referenceError = e instanceof Error ? e.message : 'Failed to load reference materials';
		} finally {
			if (withLoader) referenceLoading = false;
		}
	}

	async function uploadReferenceFile(event: Event, indexType: 'reference_book' | 'template_paper' | 'reference_questions') {
		const input = event.target as HTMLInputElement;
		const file = input.files?.[0];
		if (!file || !referenceSubjectId || referenceUploading) return;

		referenceUploading = true;
		referenceError = '';
		try {
			await uploadDocument(file, referenceSubjectId, indexType);
			await loadReferenceMaterials(referenceSubjectId);
			await refreshSubject(referenceSubjectId);
			await refreshBackgroundStatuses();
		} catch (e: unknown) {
			referenceError = e instanceof Error ? e.message : 'Upload failed';
		} finally {
			referenceUploading = false;
			input.value = '';
		}
	}

	async function deleteReference(docId: string) {
		if (!referenceSubjectId || deletingRefId) return;
		deletingRefId = docId;
		referenceError = '';
		try {
			await deleteDocumentById(docId);
			await loadReferenceMaterials(referenceSubjectId);
			await refreshBackgroundStatuses();
		} catch (e: unknown) {
			referenceError = e instanceof Error ? e.message : 'Delete failed';
		} finally {
			deletingRefId = '';
		}
	}

	// New functions for per-topic PDF management
	function selectTopic(topicId: string, topicName: string) {
		selectedTopicId = topicId;
		selectedTopicName = topicName;
		loadTopicDocuments(topicId);
	}

	async function loadTopicDocuments(topicId: string) {
		if (topicDocuments[topicId]) {
			return; // Already loaded
		}
		
		loadingTopicDocuments = topicId;
		try {
			// Filter documents from the main reference lists that belong to this topic
			const topicDocs = [...referenceBooks, ...templatePapers].filter(doc => doc.topic_id === topicId);
			topicDocuments = { ...topicDocuments, [topicId]: topicDocs };
		} catch (e: unknown) {
			console.error('Failed to load topic documents:', e);
		} finally {
			loadingTopicDocuments = '';
		}
	}

	async function uploadTopicPdf(event: Event, indexType: 'reference_book' | 'template_paper' | 'reference_questions') {
		const input = event.target as HTMLInputElement;
		const file = input.files?.[0];
		if (!file || !referenceSubjectId || !selectedTopicId || referenceUploading) return;

		referenceUploading = true;
		referenceError = '';
		try {
			await uploadDocument(file, referenceSubjectId, indexType, selectedTopicId);
			await loadReferenceMaterials(referenceSubjectId);
			topicDocuments = {};
			await loadTopicDocuments(selectedTopicId);
			await refreshSubject(referenceSubjectId);
			await refreshBackgroundStatuses();
		} catch (e: unknown) {
			referenceError = e instanceof Error ? e.message : 'Upload failed';
		} finally {
			referenceUploading = false;
			input.value = '';
		}
	}

	async function deleteSubjectCard(subject: SubjectResponse) {
		if (deletingSubjectId) return;
		const confirmed = window.confirm(
			`Delete subject "${subject.name}"? This will remove its topics and cannot be undone.`
		);
		if (!confirmed) return;

		deletingSubjectId = subject.id;
		error = '';
		try {
			await deleteSubject(subject.id);
			subjects = subjects.filter((s) => s.id !== subject.id);
			const nextTopicsMap = { ...topicsMap };
			delete nextTopicsMap[subject.id];
			topicsMap = nextTopicsMap;
			const nextBgStatus = { ...bgStatusBySubject };
			delete nextBgStatus[subject.id];
			bgStatusBySubject = nextBgStatus;
			if (expandedId === subject.id) {
				expandedId = '';
			}
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to delete subject';
		} finally {
			deletingSubjectId = '';
		}
	}
</script>

<svelte:head>
	<title>Existing Topics — VQuest Trainer</title>
</svelte:head>

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
				Create New Topic
			</button>
		</div>
	{:else}
		{#if generateModeSuccess}
			<p class="success-banner">
				<span>{generateModeSuccess}</span>
				<button class="success-dismiss" onclick={() => (generateModeSuccess = '')}>✕</button>
			</p>
		{/if}
		<div class="search-container">
			<input
				type="text"
				class="search-input"
				placeholder="Search here..."
				value={searchQuery}
				oninput={(e) => handleSearchChange((e.target as HTMLInputElement).value)}
			/>
			{#if searchQuery}
				<button class="clear-search-btn" onclick={() => handleSearchChange('')}>✕</button>
			{/if}
		</div>

		{#if filteredSubjects.length === 0}
			<div class="center-state" style="padding-top: 2rem;">
				<span class="empty-icon">🔍</span>
				<p>No results found for "{searchQuery}"</p>
				<button class="glass-btn" onclick={() => handleSearchChange('')}>Clear Search</button>
			</div>
		{:else}
			<div class="subject-list">
				{#each filteredSubjects as { subject: s, filteredTopics, subjectMatches }}
					{@const savedProgress = getSavedProgressForSubject(s.id)}
				<div class="subject-card glass-card" class:expanded={expandedId === s.id}>
					<div class="subject-card-row">
						<button class="sc-header" onclick={() => toggleSubject(s.id)}>
							<div class="sc-top">
								<span class="sc-code">{s.code}</span>
								<span class="sc-arrow">{expandedId === s.id ? '▼' : '▶'}</span>
							</div>
							<h2 class="sc-name">{s.name}</h2>
							<div class="sc-stats">
								<span class="sc-stat">📝 {s.total_questions} questions</span>
								<span class="sc-stat">📚 {s.total_topics} topics</span>
								{#if getSubjectBgStatus(s.id)?.in_progress}
										<span class="sc-stat sc-stat-gen" title={getSubjectBgStatus(s.id)?.message || 'Background generation in progress'}>
											<span class="bg-live-dot"></span>
											<span class="bg-status-label">{getBgStatusLabel(s.id)}</span>
										<span class="bg-progress-circle" style="--progress: {getBgProgress(s.id)}%"></span>
										<span class="bg-progress-count">{getBgCounter(s.id)}</span>
									</span>
								{/if}
							</div>
						</button>

						<div class="subject-quick-actions">
							{#if savedProgress}
								<button
									type="button"
									class="quick-continue-btn"
									onclick={() => continueSavedProgress(savedProgress)}
									title={`Continue vetting (${formatSavedProgressCounter(savedProgress)})`}
								>
									Continue {formatSavedProgressCounter(savedProgress)}
								</button>
							{/if}
							<button
								type="button"
								class="quick-generate-btn"
								onclick={() => trainSubjectMixed(s)}
								aria-label="Generate mixed questions"
								title="Generate mixed questions"
							>
								<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
									<path d="m12 3 1.8 4.8L18.5 10l-4.7 2.2L12 17l-1.8-4.8L5.5 10l4.7-2.2L12 3Z"></path>
									<path d="M19 14v3"></path>
									<path d="M17.5 15.5h3"></path>
								</svg>
							</button>
						</div>
					</div>

					{#if expandedId === s.id}
						<div class="topics-panel">
							<div class="subject-actions">
								<button class="glass-btn small-btn" onclick={() => openAddTopicModal(s)}>Add Topic</button>
								<button class="glass-btn small-btn" onclick={() => openReferenceModal(s)}>Reference</button>
								<!-- <button
									class="danger-btn subject-delete-btn"
									disabled={deletingSubjectId === s.id}
									onclick={() => deleteSubjectCard(s)}
								>
									{deletingSubjectId === s.id ? 'Deleting...' : 'Delete Subject'}
								</button> -->
							</div>

							{#if loadingTopics === s.id}
								<div class="topics-loading">
									<div class="spinner-sm"></div>
									<span>Loading topics…</span>
								</div>
							{:else if searchQuery && filteredTopics.length > 0}
								{#each filteredTopics as topic}
									<button class="topic-row" onclick={() => trainTopic(s, topic.id)}>
										<div class="tr-left">
											<span class="tr-name">{topic.name}</span>
										</div>
										<div class="tr-right">
											<span class="tr-qs">{topic.total_questions} Qs</span>
											<span class="tr-arrow">→</span>
										</div>
									</button>
								{/each}
							{:else if searchQuery && filteredTopics.length === 0}
								<p class="topics-empty">No matching topics in this subject</p>
							{:else if topicsMap[s.id]?.length}
								{#each topicsMap[s.id] as topic}
									<button class="topic-row" onclick={() => trainTopic(s, topic.id)}>
										<div class="tr-left">
											<span class="tr-name">{topic.name}</span>
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
	{/if}

	{#if showReferenceModal}
		<div class="modal-backdrop" role="button" tabindex="0" aria-label="Close" onclick={closeReferenceModal} onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && closeReferenceModal()}>
			<div
				class="modal reference-modal"
				role="dialog"
				aria-modal="true"
				tabindex="0"
				onclick={(e) => e.stopPropagation()}
				onkeydown={(e) => e.stopPropagation()}
			>
				<div class="modal-header">
					<h3>Reference Materials • {referenceSubjectName}</h3>
					<button class="close-btn" onclick={closeReferenceModal}>✕</button>
				</div>

				{#if referenceError}
					<p class="modal-error">{referenceError}</p>
				{/if}

				{#if referenceLoading}
					<div class="topics-loading"><div class="spinner-sm"></div><span>Loading materials…</span></div>
				{:else}
					<div class="topic-accordion-list">
						{#if topicsMap[referenceSubjectId]?.length}
							{#each topicsMap[referenceSubjectId] as topic, index}
								<div class="topic-accordion-panel glass-panel-frosted" class:expanded={selectedTopicId === topic.id}>
									<button
										type="button"
										class="topic-accordion-header"
										aria-expanded={selectedTopicId === topic.id}
										onclick={() =>
											selectedTopicId === topic.id
												? ((selectedTopicId = ''), (selectedTopicName = ''))
												: selectTopic(topic.id, topic.name)}
									>
										<div class="topic-accordion-title-wrap">
											<span class="topic-accordion-index">{index + 1}</span>
											<span class="topic-accordion-title">{topic.name}</span>
										</div>
										<div class="topic-accordion-header-right">
											<span class="topic-status-pill">
												{#if ((topicDocuments[topic.id]?.length ?? 0) + referenceQuestions.filter((doc) => doc.topic_id === topic.id).length) > 0}
													Ready
												{:else}
													Empty
												{/if}
											</span>
											<span class="topic-accordion-chevron" class:expanded={selectedTopicId === topic.id}>
												▾
											</span>
										</div>
									</button>

									{#if selectedTopicId === topic.id}
										<div class="topic-accordion-body">
											<div class="syllabus-block">
												<h4>Syllabus Content</h4>
												<div class="syllabus-preview">
													{topic.syllabus_content || `Paste or type the syllabus content for this topic...`}
												</div>
											</div>

											<div class="topic-material-tabs">
												<button type="button" class="topic-material-tab" class:active={referenceTab === 'pdfs'} onclick={() => (referenceTab = 'pdfs')}>
													📚 Reference Books
												</button>
												<button type="button" class="topic-material-tab" class:active={referenceTab === 'questions'} onclick={() => (referenceTab = 'questions')}>
													❖ Reference Questions
													<span class="optional-copy">optional</span>
												</button>
											</div>

											{#if referenceTab === 'pdfs'}
												<p class="topic-upload-copy">Upload textbooks or notes for &quot;{topic.name}&quot;</p>
												<label class="upload-dropzone glass-panel-frosted">
													<input type="file" accept=".pdf,.doc,.docx,.txt" oninput={(e) => uploadTopicPdf(e, pdfUploadType)} disabled={referenceUploading} />
													<div class="upload-dropzone-icon">📁</div>
													<div class="upload-dropzone-title">{referenceUploading ? 'Uploading…' : 'Drop files or click to upload'}</div>
													<div class="upload-dropzone-subtitle">PDF, Word, PowerPoint, or Text</div>
												</label>
												<div class="upload-type-row">
													<select bind:value={pdfUploadType} class="select-input topic-inline-select">
														<option value="reference_book">Reference Book PDF</option>
														<option value="template_paper">Template Paper PDF</option>
													</select>
												</div>
												<div class="doc-list topic-doc-list">
													{#if loadingTopicDocuments === topic.id}
														<div class="topics-loading"><div class="spinner-sm"></div><span>Loading PDFs…</span></div>
													{:else if topicDocuments[topic.id]?.length}
														{#each topicDocuments[topic.id] as doc}
															<div class="doc-row">
																<div class="doc-main">
																	<div class="doc-name">{doc.filename}</div>
																	<div class="doc-meta">{doc.index_type.replace('_', ' ')} • {doc.processing_status}</div>
																	{#if isDocProcessing(doc.processing_status)}
																		<div class="doc-progress-track">
																			<div class="doc-progress-fill" style:width="{referenceProgressByDoc[doc.id] ?? 0}%"></div>
																		</div>
																		{#if referenceProgressDetailByDoc[doc.id]}
																			<div class="doc-progress-detail">{referenceProgressDetailByDoc[doc.id]}</div>
																		{/if}
																	{/if}
																</div>
																<button class="danger-btn" disabled={deletingRefId === doc.id} onclick={() => deleteReference(doc.id)}>
																	{deletingRefId === doc.id ? 'Deleting...' : 'Delete'}
																</button>
															</div>
														{/each}
													{:else}
														<p class="topics-empty">No reference books uploaded yet.</p>
													{/if}
												</div>
											{:else}
												<p class="topic-upload-copy">Upload question files for &quot;{topic.name}&quot;</p>
												<label class="upload-dropzone glass-panel-frosted question-dropzone">
													<input type="file" accept=".pdf,.xlsx,.csv" oninput={(e) => uploadTopicPdf(e, 'reference_questions')} disabled={referenceUploading} />
													<div class="upload-dropzone-icon">❖</div>
													<div class="upload-dropzone-title">{referenceUploading ? 'Uploading…' : 'Drop files or click to upload'}</div>
													<div class="upload-dropzone-subtitle">PDF, XLSX, or CSV</div>
												</label>
												<div class="doc-list topic-doc-list">
													{#each referenceQuestions.filter((doc) => doc.topic_id === topic.id) as doc}
														<div class="doc-row">
															<div class="doc-main">
																<div class="doc-name">{doc.filename}</div>
																<div class="doc-meta">
																	{doc.processing_status}
																	{#if doc.parsed_question_count !== null && doc.parsed_question_count !== undefined}
																		• {doc.parsed_question_count} parsed
																	{/if}
																</div>
																{#if isDocProcessing(doc.processing_status)}
																	<div class="doc-progress-track">
																		<div class="doc-progress-fill" style:width="{referenceProgressByDoc[doc.id] ?? 0}%"></div>
																	</div>
																	{#if referenceProgressDetailByDoc[doc.id]}
																		<div class="doc-progress-detail">{referenceProgressDetailByDoc[doc.id]}</div>
																	{/if}
																{/if}
															</div>
															<button class="danger-btn" disabled={deletingRefId === doc.id} onclick={() => deleteReference(doc.id)}>
																{deletingRefId === doc.id ? 'Deleting...' : 'Delete'}
															</button>
														</div>
													{:else}
														<p class="topics-empty">No reference question files uploaded yet.</p>
													{/each}
												</div>
											{/if}
										</div>
									{/if}
								</div>
							{/each}
						{:else}
							<div class="empty-state">
								<div class="empty-icon">📚</div>
								<p>No topics found. Please add topics first.</p>
							</div>
						{/if}
					</div>
				{/if}
			</div>
		</div>
	{/if}

	{#if showGenerateModeModal}
		<div class="modal-backdrop" role="button" tabindex="0" aria-label="Close" onclick={() => closeGenerateModeModal()} onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && closeGenerateModeModal()}>
			<div
				class="modal generate-choice-modal"
				role="dialog"
				aria-modal="true"
				tabindex="0"
				onclick={(e) => e.stopPropagation()}
				onkeydown={(e) => e.stopPropagation()}
			>
				<div class="modal-header">
					<h3>{generateModalStep === 'choice' ? generateTargetSubject?.name : 'Schedule Generation'}</h3>
					<button class="close-btn" onclick={() => closeGenerateModeModal()}>✕</button>
				</div>

				<div class="generate-choice-body">
					{#if generateModalStep === 'choice'}
						<!-- Step 1: Simple two-button choice -->
						<div class="generate-initial-choice">
							<button class="choice-card" onclick={chooseVetNow}>
								<span class="choice-icon">⚡</span>
								<span class="choice-title">Vet Now</span>
								<span class="choice-desc">Review & approve existing unvetted questions</span>
							</button>
							<button class="choice-card" onclick={chooseVetLater}>
								<span class="choice-icon">🕐</span>
								<span class="choice-title">Vet Later</span>
								<span class="choice-desc">Generate questions in the background & vet later</span>
							</button>
						</div>

					{:else}
						<!-- Step 2: Full config for background generation -->
						<p class="generate-choice-copy">
							{generateTargetSubject?.name}
							{#if generateTargetMode === 'topic'}
								• Single Topic
							{:else}
								• Mixed Topics
							{/if}
						</p>

						<div class="generate-form-grid">
							<label class="generate-field">
								<span>Questions to generate</span>
								<input
									type="number"
									min="1"
									max="200"
									bind:value={generateQuestionCount}
									class="search-input"
								/>
								{#if loadingCapacity}
									<small class="capacity-loading">Loading capacity...</small>
								{:else if capacityEstimate}
									<small class="capacity-info">
										📊 {capacityEstimate.completed_documents} docs ({capacityEstimate.total_chunks} chunks)
									</small>
								{/if}
							</label>

							{#if generateTargetMode === 'mixed'}
								<label class="generate-field">
									<span>Topic scope</span>
									<select class="search-input" bind:value={generateTopicScope} disabled={loadingGenerateTopics}>
										<option value="all">All topics (mixed)</option>
										<option value="selected">Selected topics</option>
									</select>
								</label>
							{/if}

							{#if generateTargetMode === 'topic'}
								<label class="generate-field generate-field-full">
									<span>Select topic</span>
									<select class="search-input" bind:value={generateTargetTopicId} disabled={loadingGenerateTopics || generateModalTopics.length === 0}>
										{#each generateModalTopics as topic}
											<option value={topic.id}>{topic.name}</option>
										{/each}
									</select>
								</label>
							{:else if generateTopicScope === 'selected'}
								<div class="generate-field generate-field-full">
									<span>Select topics</span>
									<div class="topic-multi-toolbar">
										<span class="topic-multi-count">{generateSelectedTopicIds.length} selected</span>
										<div class="topic-multi-toolbar-actions">
											<button type="button" class="topic-chip-btn" onclick={selectAllGenerateTopics} disabled={loadingGenerateTopics || generateModalTopics.length === 0}>Select all</button>
											<button type="button" class="topic-chip-btn" onclick={clearGenerateTopics} disabled={loadingGenerateTopics || generateSelectedTopicIds.length === 0}>Clear</button>
										</div>
									</div>
									<div class="topic-multi-list">
										{#each generateModalTopics as topic}
											<label class="topic-multi-item">
												<input
													type="checkbox"
													checked={generateSelectedTopicIds.includes(topic.id)}
													onchange={() => toggleGenerateTopicSelection(topic.id)}
													disabled={loadingGenerateTopics}
												/>
												<span>{topic.name}</span>
											</label>
										{/each}
									</div>
								</div>
							{/if}
						</div>

						{#if loadingGenerateTopics}
							<p class="generate-choice-copy">Loading topics...</p>
						{/if}
						{#if generateModeError}
							<p class="modal-error">{generateModeError}</p>
						{/if}

						<div class="generate-choice-actions">
							<button class="glass-btn" onclick={() => (generateModalStep = 'choice')} disabled={schedulingBulk}>
								← Back
							</button>
							<button class="glass-btn generate-choice-btn" onclick={chooseGenAndVetLater} disabled={schedulingBulk}>
								{schedulingBulk ? 'Scheduling...' : 'Schedule Generation'}
							</button>
						</div>
					{/if}
				</div>
			</div>
		</div>
	{/if}

	{#if showAddTopicModal}
		<div class="modal-backdrop" role="button" tabindex="0" aria-label="Close" onclick={closeAddTopicModal} onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && closeAddTopicModal()}>
			<div
				class="modal add-topic-modal"
				role="dialog"
				aria-modal="true"
				tabindex="0"
				onclick={(e) => e.stopPropagation()}
				onkeydown={(e) => e.stopPropagation()}
			>
				<div class="modal-header">
					<h3>Add Topic • {addTopicSubjectName}</h3>
					<button class="close-btn" onclick={closeAddTopicModal}>✕</button>
				</div>

				<div class="topic-create-fields topic-create-modal-fields">
					<input
						class="topic-input"
						type="text"
						placeholder="Add new topic"
						value={addTopicName}
						oninput={(e) => {
							addTopicName = (e.currentTarget as HTMLInputElement).value;
						}}
					/>
					<textarea
						class="syllabus-input"
						rows="3"
						placeholder="Syllabus content for this topic"
						value={addTopicSyllabus}
						oninput={(e) => {
							addTopicSyllabus = (e.currentTarget as HTMLTextAreaElement).value;
						}}
					></textarea>
				</div>

				<div class="modal-actions">
					<button class="glass-btn small-btn modal-cancel-btn" onclick={closeAddTopicModal}>Cancel</button>
					<button
						class="glass-btn small-btn modal-submit-btn"
						disabled={addingTopicFor === addTopicSubjectId || !addTopicName.trim()}
						onclick={() => addTopicRow(addTopicSubjectId)}
					>
						{addingTopicFor === addTopicSubjectId ? 'Adding...' : 'Add Topic'}
					</button>
				</div>
			</div>
		</div>
	{/if}
</div>

<style>
	.page {
		max-width: 980px;
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

	.success-banner {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 0.75rem;
		margin: 0 0 1rem;
		padding: 0.65rem 0.8rem;
		border-radius: 10px;
		background: rgba(49, 208, 161, 0.14);
		border: 1px solid rgba(49, 208, 161, 0.35);
		color: #bff9df;
		font-size: 0.85rem;
	}

	.success-dismiss {
		background: none;
		border: none;
		color: inherit;
		cursor: pointer;
		font-size: 1rem;
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
		/* Performance optimizations */
		contain: layout style paint;
		will-change: auto; /* Remove will-change for better performance */
	}

	.subject-card {
		padding: 0;
		width: 100%;
		overflow: hidden;
		transition: all 0.2s;
		/* Performance optimizations */
		contain: layout style paint;
		transform: translateZ(0); /* Hardware acceleration without will-change */
		/* Enhanced blur effect - force override */
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

	.subject-card.expanded {
		border-color: rgba(var(--theme-primary-rgb), 0.3);
		/* Maintain blur on expanded - force override */
		backdrop-filter: blur(10px) saturate(150%) brightness(1.02) !important;
		-webkit-backdrop-filter: blur(10px) saturate(150%) brightness(1.02) !important;
	}

	.subject-card-row {
		display: grid;
		grid-template-columns: minmax(0, 1fr) auto;
		gap: 0.75rem;
		padding: 0.75rem;
		align-items: stretch;
	}

	.subject-quick-actions {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 0.45rem;
	}

	.quick-continue-btn {
		min-height: 3.5rem;
		padding: 0 0.9rem;
		border-radius: 999px;
		border: 1px solid rgba(var(--theme-primary-rgb), 0.35);
		background: rgba(var(--theme-primary-rgb), 0.15);
		color: var(--theme-text);
		cursor: pointer;
		font-size: 0.74rem;
		font-weight: 700;
		white-space: nowrap;
		transition: transform 0.15s ease, border-color 0.15s ease, background 0.15s ease;
	}

	.quick-continue-btn:hover {
		background: rgba(var(--theme-primary-rgb), 0.23);
		border-color: rgba(var(--theme-primary-rgb), 0.52);
		transform: translateY(-1px);
	}

	.quick-continue-btn:focus-visible {
		outline: 2px solid rgba(var(--theme-primary-rgb), 0.55);
		outline-offset: 1px;
	}

	.quick-generate-btn {
		width: 3.5rem;
		height: 3.5rem;
		border-radius: 999px;
		border: 1px solid rgba(255, 255, 255, 0.22);
		background: rgba(255, 255, 255, 0.08);
		color: rgba(255, 255, 255, 0.92);
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		transition: transform 0.15s ease, border-color 0.15s ease, background 0.15s ease;
	}

	.quick-generate-btn:hover {
		background: rgba(255, 255, 255, 0.14);
		border-color: rgba(255, 255, 255, 0.35);
		transform: translateY(-1px);
	}

	.quick-generate-btn:focus-visible {
		outline: 2px solid rgba(255, 255, 255, 0.35);
		outline-offset: 1px;
	}

	.sc-header {
		display: block;
		text-align: left;
		cursor: pointer;
		padding: 0.9rem 1rem;
		min-height: 96px;
		width: 100%;
		border-radius: 14px;
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
		font-size: 0.82rem;
		color: var(--theme-text-muted);
	}

	.sc-stat-gen {
		display: inline-flex;
		align-items: center;
		gap: 0.42rem;
		font-weight: 600;
		color: var(--theme-text);
		padding: 0.18rem 0.55rem;
		border-radius: 999px;
		border: 1px solid rgba(var(--theme-primary-rgb), 0.35);
		background: rgba(var(--theme-primary-rgb), 0.14);
	}

	.bg-live-dot {
		width: 0.45rem;
		height: 0.45rem;
		border-radius: 50%;
		background: var(--theme-primary);
		box-shadow: 0 0 0 0 rgba(var(--theme-primary-rgb), 0.55);
		animation: bg-pulse 1.3s ease-out infinite;
	}

	@keyframes bg-pulse {
		0% { box-shadow: 0 0 0 0 rgba(var(--theme-primary-rgb), 0.55); }
		100% { box-shadow: 0 0 0 8px rgba(var(--theme-primary-rgb), 0); }
	}

	.bg-status-label {
		font-size: 0.74rem;
		line-height: 1;
	}

	.bg-progress-circle {
		--progress: 0%;
		width: 1rem;
		height: 1rem;
		border-radius: 50%;
		background: conic-gradient(var(--theme-primary) var(--progress), rgba(255, 255, 255, 0.18) 0);
		position: relative;
		flex-shrink: 0;
	}

	.bg-progress-circle::after {
		content: '';
		position: absolute;
		inset: 2px;
		border-radius: 50%;
		background: rgba(8, 16, 30, 0.95);
	}

	.bg-progress-count {
		font-size: 0.78rem;
		line-height: 1;
		letter-spacing: 0.02em;
	}

	.topics-panel {
		border-top: 0.5px solid rgba(255, 255, 255, 0.08);
		padding: 0.5rem 0;
	}

	.subject-actions {
		display: flex;
		justify-content: space-evenly;
		gap: 0.75rem;
		padding: 0.5rem 1.5rem 0.25rem;
		flex-wrap: wrap;
	}

	.subject-actions .small-btn {
		flex: 1 1 150px;
		max-width: 220px;
		text-align: center;
		align-self: stretch;
	}

	/* .subject-delete-btn {
		flex: 1 1 150px;
		min-height: 36px;
		max-width: 220px;
	}

	.subject-delete-btn:disabled {
		opacity: 0.65;
		cursor: not-allowed;
	} */

	.topic-create-fields {
		flex: 1;
		display: flex;
		flex-direction: column;
		gap: 0.45rem;
	}

	.topic-create-modal-fields {
		padding: 0.9rem 1rem 0.25rem;
	}

	.topic-input,
	.syllabus-input {
		width: 100%;
		padding: 0.75rem 0.9rem;
		border-radius: 10px;
		border: 1px solid rgba(255, 255, 255, 0.2);
		background: rgba(9, 16, 32, 0.7);
		color: var(--theme-text);
		font: inherit;
		transition: border-color 0.2s ease, box-shadow 0.2s ease, background 0.2s ease;
	}

	.topic-input::placeholder,
	.syllabus-input::placeholder {
		color: rgba(230, 235, 245, 0.5);
	}

	.topic-input:focus,
	.syllabus-input:focus {
		outline: none;
		border-color: rgba(84, 160, 255, 0.7);
		box-shadow: 0 0 0 2px rgba(84, 160, 255, 0.2);
		background: rgba(12, 22, 42, 0.8);
	}

	.syllabus-input {
		resize: vertical;
		min-height: 140px;
		line-height: 1.4;
	}

.topic-chip-btn {
	padding: 0.4rem 0.8rem;
	font-size: 0.85rem;
}

.capacity-loading {
	color: var(--theme-text-muted);
	font-size: 0.8rem;
	margin-top: 0.25rem;
}

.capacity-info {
	color: rgba(var(--theme-primary-rgb), 0.8);
	font-size: 0.8rem;
	margin-top: 0.25rem;
	display: block;
}

	.topics-empty {
		padding: 1rem 1.5rem;
		color: var(--theme-text-muted);
		font-size: 0.85rem;
		margin: 0;
	}

	.topic-row {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		text-align: left;
		width: 100%;
		padding: 0.8rem 1.5rem;
		background: none;
		border: none;
		border-bottom: 0.5px solid rgba(255, 255, 255, 0.04);
		color: var(--theme-text);
		cursor: pointer;
		font-family: inherit;
		font-size: 0.95rem;
		transition: background 0.15s;
		gap: 0.75rem;
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
		gap: 0.6rem;
		flex: 1;
		min-width: 0;
	}

	.tr-name {
		font-weight: 600;
		white-space: normal;
		word-break: break-word;
		line-height: 1.35;
	}

	/* .tr-badge {
		font-size: 0.75rem;
		padding: 0.16rem 0.48rem;
		background: rgba(var(--theme-primary-rgb), 0.12);
		border-radius: 999px;
		color: var(--theme-primary);
		flex-shrink: 0;
	} */

	.tr-right {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding-top: 0.1rem;
		flex-shrink: 0;
	}

	.tr-qs {
		font-size: 0.9rem;
		color: var(--theme-text-muted);
	}

	.tr-arrow {
		color: var(--theme-primary);
		font-weight: 700;
		font-size: 1.05rem;
	}

	.modal-backdrop {
		position: fixed;
		inset: 0;
		background: var(--theme-modal-backdrop);
		backdrop-filter: var(--theme-modal-backdrop-blur);
		-webkit-backdrop-filter: var(--theme-modal-backdrop-blur);
		display: grid;
		place-items: center;
		z-index: 80;
		padding: 1rem;
	}

	.modal {
		width: min(820px, 96vw);
		max-height: 86vh;
		overflow: auto;
		border-radius: 16px;
		border: 1px solid var(--theme-modal-border);
		background: var(--theme-modal-surface);
		box-shadow: var(--theme-modal-shadow);
	}

	.reference-modal {
		width: min(900px, 96vw);
		max-height: 90vh;
		border-radius: 20px;
		border: 2px solid rgba(255, 255, 255, 0.15);
		background:
			radial-gradient(circle at 15% 15%, rgba(84, 160, 255, 0.12), transparent 40%),
			radial-gradient(circle at 85% 85%, rgba(255, 126, 66, 0.08), transparent 35%),
			linear-gradient(140deg, rgba(8, 16, 33, 0.98), rgba(18, 24, 40, 0.98));
		box-shadow: 
			0 30px 60px rgba(0, 0, 0, 0.4),
			0 0 0 1px rgba(255, 255, 255, 0.1) inset,
			inset 0 1px 0 rgba(255, 255, 255, 0.15);
	}

	.add-topic-modal {
		width: min(560px, 94vw);
		border-radius: 20px;
		border: 2px solid rgba(84, 160, 255, 0.85);
		background:
			radial-gradient(circle at 18% 12%, rgba(40, 88, 163, 0.28), transparent 46%),
			radial-gradient(circle at 85% 88%, rgba(255, 126, 66, 0.18), transparent 42%),
			linear-gradient(140deg, rgba(8, 16, 33, 0.96), rgba(18, 24, 40, 0.96));
		box-shadow: 0 26px 55px rgba(0, 0, 0, 0.48), 0 0 0 1px rgba(255, 255, 255, 0.15) inset;
	}

	.add-topic-modal .modal-header {
		padding: 1.05rem 1.15rem;
		border-bottom: 1px solid rgba(255, 255, 255, 0.12);
	}

	.add-topic-modal .modal-header h3 {
		font-size: 1.95rem;
		font-weight: 700;
		letter-spacing: 0.01em;
	}

	.add-topic-modal .close-btn {
		color: rgba(255, 255, 255, 0.9);
		font-size: 1.55rem;
		line-height: 1;
		padding: 0.1rem 0.3rem;
	}

	.add-topic-modal .close-btn:hover {
		color: #ffffff;
	}

	.add-topic-modal .topic-create-modal-fields {
		gap: 0.95rem;
		padding: 1rem 1.1rem 0.35rem;
	}

	.modal-cancel-btn {
		background: rgba(255, 255, 255, 0.1);
		border-color: rgba(255, 255, 255, 0.25);
	}

	.modal-submit-btn {
		background: linear-gradient(135deg, #f49e58, #d9642f);
		color: #fff;
		border-color: rgba(255, 190, 120, 0.9);
	}

	.modal-submit-btn:disabled {
		opacity: 0.65;
	}

	.generate-choice-modal {
		width: min(520px, 94vw);
	}

	.generate-choice-body {
		padding: 1rem;
		display: flex;
		flex-direction: column;
		gap: 0.8rem;
	}

	.generate-choice-copy {
		margin: 0;
		color: var(--theme-text-muted);
		font-size: 0.9rem;
	}

	.generate-initial-choice {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 0.75rem;
		padding: 0.25rem 0;
	}

	.choice-card {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.5rem;
		padding: 1.4rem 1rem;
		border-radius: 14px;
		border: 1px solid rgba(255, 255, 255, 0.12);
		background: rgba(255, 255, 255, 0.06);
		cursor: pointer;
		transition: all 0.25s ease;
		text-align: center;
		color: var(--theme-text);
	}

	.choice-card:hover {
		background: rgba(var(--theme-primary-rgb), 0.15);
		border-color: rgba(var(--theme-primary-rgb), 0.4);
		transform: translateY(-2px);
		box-shadow: 0 4px 20px rgba(var(--theme-primary-rgb), 0.15);
	}

	.choice-card:active {
		transform: translateY(0);
	}

	.choice-icon {
		font-size: 1.6rem;
		line-height: 1;
	}

	.choice-title {
		font-size: 1rem;
		font-weight: 700;
		letter-spacing: 0.01em;
	}

	.choice-desc {
		font-size: 0.72rem;
		color: var(--theme-text-muted);
		line-height: 1.35;
	}

	.generate-choice-actions {
		display: grid;
		grid-template-columns: auto 1fr;
		gap: 0.6rem;
	}

	.generate-form-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 1rem;
		align-items: start;
	}

	.generate-field {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.generate-field span {
		font-size: 0.85rem;
		color: var(--theme-text-muted);
		font-weight: 500;
		letter-spacing: 0.01em;
	}

	.generate-field input,
	.generate-field select {
		width: 100%;
		min-height: 44px;
		padding: 0.75rem 1rem;
		border-radius: 12px;
		border: 1px solid rgba(255, 255, 255, 0.15);
		background: rgba(255, 255, 255, 0.08);
		color: var(--theme-text);
		font-size: 0.95rem;
		transition: all 0.2s ease;
	}

	.generate-field input:focus,
	.generate-field select:focus {
		outline: none;
		border-color: rgba(var(--theme-primary-rgb), 0.5);
		background: rgba(255, 255, 255, 0.12);
		box-shadow: 0 0 0 3px rgba(var(--theme-primary-rgb), 0.1);
	}

	.generate-field-full {
		grid-column: 1 / -1;
	}

	.topic-multi-list {
		max-height: 220px;
		overflow: auto;
		display: grid;
		grid-template-columns: 1fr;
		gap: 0.45rem;
		padding: 0.5rem;
		border-radius: 10px;
		border: 1px solid rgba(255, 255, 255, 0.12);
		background: rgba(255, 255, 255, 0.03);
	}

	.topic-multi-toolbar {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
	}

	.topic-multi-count {
		font-size: 0.78rem;
		color: var(--theme-text-muted);
	}

	.topic-multi-toolbar-actions {
		display: flex;
		gap: 0.4rem;
	}

	.topic-chip-btn {
		height: 2rem;
		padding: 0 0.7rem;
		border-radius: 999px;
		border: 1px solid rgba(255, 255, 255, 0.18);
		background: rgba(255, 255, 255, 0.06);
		color: var(--theme-text);
		font-size: 0.76rem;
		cursor: pointer;
	}

	.topic-chip-btn:disabled {
		opacity: 0.45;
		cursor: not-allowed;
	}

	.topic-multi-item {
		display: flex;
		align-items: center;
		gap: 0.65rem;
		font-size: 0.9rem;
		color: var(--theme-text);
		padding: 0.55rem 0.6rem;
		border-radius: 10px;
		background: rgba(255, 255, 255, 0.05);
		min-height: 44px;
		cursor: pointer;
	}

	.topic-multi-item input[type='checkbox'] {
		width: 1.1rem;
		height: 1.1rem;
		accent-color: var(--theme-primary);
		flex-shrink: 0;
	}

	.generate-choice-btn {
		width: 100%;
		text-align: center;
		min-height: 46px;
	}

	.modal-actions {
		display: flex;
		justify-content: flex-end;
		gap: 0.55rem;
		padding: 0.65rem 1rem 1rem;
	}

	.modal-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 0.9rem 1rem;
		border-bottom: 1px solid rgba(255, 255, 255, 0.08);
	}

	.modal-header h3 {
		margin: 0;
		font-size: 1rem;
	}

	.close-btn {
		background: none;
		border: none;
		color: var(--theme-text-muted);
		font-size: 1rem;
		cursor: pointer;
	}

	.doc-list {
		padding: 0.35rem 0 0.8rem;
	}

	.doc-row {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.75rem;
		padding: 0.65rem 1rem;
		border-top: 1px solid rgba(255, 255, 255, 0.06);
	}

	.doc-main {
		flex: 1;
		min-width: 0;
	}

	.doc-name {
		font-weight: 600;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.doc-meta {
		color: var(--theme-text-muted);
		font-size: 0.82rem;
	}

	.doc-progress-track {
		margin-top: 0.45rem;
		height: 6px;
		border-radius: 999px;
		overflow: hidden;
		background: rgba(255, 255, 255, 0.12);
	}

	.doc-progress-fill {
		height: 100%;
		background: linear-gradient(90deg, var(--theme-primary), var(--theme-primary-hover));
		transition: width 0.3s ease;
	}

	.doc-progress-detail {
		margin-top: 0.35rem;
		font-size: 0.76rem;
		color: var(--theme-text-muted);
	}

	.danger-btn {
		padding: 0.4rem 0.72rem;
		border-radius: 10px;
		border: 1px solid rgba(233, 69, 96, 0.45);
		background: rgba(233, 69, 96, 0.14);
		color: #ffb4c1;
		cursor: pointer;
		font: inherit;
		font-size: 0.82rem;
	}

	.modal-error {
		margin: 0 1rem 0.8rem;
		padding: 0.55rem 0.65rem;
		border-radius: 10px;
		background: rgba(233, 69, 96, 0.12);
		border: 1px solid rgba(233, 69, 96, 0.3);
		color: #ff9dad;
		font-size: 0.85rem;
	}

	.search-container {
		position: relative;
		margin-bottom: 1.5rem;
		display: flex;
		align-items: center;
		margin-top: 50px;
	}

	.search-input {
		width: 100%;
		padding: 0.75rem 2.5rem 0.75rem 1rem;
		border-radius: 12px;
		border: 1px solid rgba(255, 255, 255, 0.14);
		background: rgba(255, 255, 255, 0.06);
		color: var(--theme-text);
		font: inherit;
		font-size: 0.95rem;
		transition: all 0.2s;
	}

	.search-input:focus {
		outline: none;
		border-color: rgba(var(--theme-primary-rgb), 0.5);
		background: rgba(255, 255, 255, 0.08);
		box-shadow: 0 0 0 2px rgba(var(--theme-primary-rgb), 0.1);
	}

	.search-input::placeholder {
		color: rgba(255, 255, 255, 0.4);
	}

	.clear-search-btn {
		position: absolute;
		right: 0.75rem;
		background: linear-gradient(
			145deg,
			rgba(255,255,255,0.03) 0%,
			rgba(255,255,255,0.02) 50%,
			rgba(255,255,255,0.025) 100%
		);
		backdrop-filter: blur(10px) saturate(150%) brightness(1.02);
		-webkit-backdrop-filter: blur(10px) saturate(150%) brightness(1.02);
		border: 0.5px solid rgba(255, 255, 255, 0.12);
		border-radius: 0.5rem;
		color: var(--theme-text-muted);
		cursor: pointer;
		font-size: 1.1rem;
		padding: 0.35rem 0.5rem;
		display: flex;
		align-items: center;
		justify-content: center;
		transition: all 0.15s;
		box-shadow:
			0 4px 20px rgba(0, 0, 0, 0.15),
			inset 0 1px 1px rgba(255, 255, 255, 0.25),
			inset 0 -1px 1px rgba(255, 255, 255, 0.08);
	}

	.clear-search-btn:hover {
		color: var(--theme-text);
		background: linear-gradient(
			145deg,
			rgba(255,255,255,0.05) 0%,
			rgba(255,255,255,0.03) 50%,
			rgba(255,255,255,0.04) 100%
		);
		transform: translateY(-1px);
		box-shadow:
			0 6px 25px rgba(0, 0, 0, 0.2),
			inset 0 1px 1px rgba(255, 255, 255, 0.3),
			inset 0 -1px 1px rgba(255, 255, 255, 0.1);
	}

	@media (max-width: 768px) {
		.page {
			padding-top: 1rem;
		}

		.modal-backdrop {
			padding: 0.35rem;
		}

		.generate-choice-modal {
			width: 100%;
			max-height: 92vh;
		}

		.generate-choice-body {
			padding: 0.8rem;
			gap: 0.7rem;
		}

		.subject-card-row {
			gap: 0.55rem;
			padding: 0.6rem;
		}

		.quick-generate-btn {
			width: 3.25rem;
			height: 3.25rem;
		}

		.quick-continue-btn {
			min-height: 3.25rem;
			padding: 0 0.7rem;
			font-size: 0.7rem;
		}

		.sc-header {
			min-height: 84px;
			padding: 0.75rem 0.85rem;
		}

		.generate-choice-actions {
			position: sticky;
			bottom: -1px;
			padding-top: 0.55rem;
			background: linear-gradient(180deg, rgba(10, 18, 32, 0), rgba(10, 18, 32, 0.75) 24%, rgba(var(--theme-primary-rgb), 0.2) 100%);
		}

		.topic-multi-toolbar {
			flex-direction: column;
			align-items: flex-start;
		}

		.topic-multi-toolbar-actions {
			width: 100%;
		}

		.topic-chip-btn {
			flex: 1;
		}

		.generate-form-grid {
			grid-template-columns: 1fr;
			gap: 0.75rem;
		}

		.generate-field input,
		.generate-field select {
			min-height: 40px;
			padding: 0.6rem 0.8rem;
		}
	}

	/* Reference modal accordion redesign */
	.topic-accordion-list {
		display: flex;
		flex-direction: column;
		gap: 0.9rem;
		padding: 0.5rem 0 0.25rem;
	}

	.topic-accordion-panel {
		padding: 0;
		border-radius: 1.5rem;
		overflow: hidden;
		border: 1px solid rgba(255, 255, 255, 0.14);
		background: linear-gradient(145deg, rgba(255, 255, 255, 0.08), rgba(255, 255, 255, 0.04));
	}

	.topic-accordion-panel.expanded {
		border-color: rgba(255, 146, 76, 0.55);
		box-shadow:
			0 16px 44px rgba(0, 0, 0, 0.26),
			0 0 0 1px rgba(255, 146, 76, 0.18),
			inset 0 1px 0 rgba(255, 255, 255, 0.18);
	}

	.topic-accordion-header {
		width: 100%;
		padding: 1.15rem 1.35rem;
		border: 0;
		background: transparent;
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1rem;
		color: inherit;
		font: inherit;
		text-align: left;
		cursor: pointer;
	}

	.topic-accordion-title-wrap {
		display: flex;
		align-items: center;
		gap: 0.95rem;
		min-width: 0;
	}

	.topic-accordion-index {
		font-size: 1.65rem;
		font-weight: 800;
		color: #ff8a3d;
		line-height: 1;
	}

	.topic-accordion-title {
		font-size: 1.15rem;
		font-weight: 700;
		color: var(--theme-text);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.topic-accordion-header-right {
		display: flex;
		align-items: center;
		gap: 0.85rem;
		flex-shrink: 0;
	}

	.topic-status-pill {
		padding: 0.42rem 0.9rem;
		border-radius: 999px;
		background: rgba(255, 255, 255, 0.12);
		color: rgba(255, 255, 255, 0.92);
		font-size: 0.85rem;
		font-weight: 700;
	}

	.topic-accordion-chevron {
		font-size: 1rem;
		color: rgba(255, 255, 255, 0.92);
		transition: transform 0.2s ease;
	}

	.topic-accordion-chevron.expanded {
		transform: rotate(180deg);
	}

	.topic-accordion-body {
		padding: 0 1.35rem 1.35rem;
		display: flex;
		flex-direction: column;
		gap: 1.2rem;
	}

	.syllabus-block h4 {
		margin: 0 0 0.8rem;
		font-size: 1.1rem;
		font-weight: 800;
		color: var(--theme-text);
	}

	.syllabus-preview {
		min-height: 140px;
		padding: 1.2rem 1.3rem;
		border-radius: 1.3rem;
		background: linear-gradient(180deg, rgba(76, 116, 140, 0.22), rgba(42, 74, 92, 0.18));
		border: 1px solid rgba(255, 255, 255, 0.12);
		box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.08);
		font-size: 1rem;
		line-height: 1.65;
		color: rgba(255, 255, 255, 0.78);
		white-space: pre-wrap;
	}

	.topic-material-tabs {
		display: grid;
		grid-template-columns: 1fr 1fr;
		align-items: end;
		border-bottom: 1px solid rgba(255, 255, 255, 0.14);
	}

	.topic-material-tab {
		border: 0;
		background: transparent;
		padding: 1rem 1rem 0.9rem;
		color: rgba(255, 255, 255, 0.95);
		font: inherit;
		font-size: 1rem;
		font-weight: 800;
		text-align: left;
		cursor: pointer;
		border-bottom: 3px solid transparent;
		opacity: 0.7;
	}

	.topic-material-tab.active {
		background: rgba(23, 37, 42, 0.38);
		border-bottom-color: #ff8a3d;
		opacity: 1;
		color: #ff8a3d;
	}

	.optional-copy {
		margin-left: 0.55rem;
		font-size: 0.9rem;
		font-style: italic;
		font-weight: 400;
		color: rgba(255, 255, 255, 0.68);
	}

	.topic-upload-copy {
		margin: 0;
		font-size: 0.98rem;
		color: rgba(255, 255, 255, 0.72);
	}

	.upload-dropzone {
		position: relative;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 0.7rem;
		min-height: 230px;
		padding: 1.75rem;
		border-radius: 1.7rem;
		border: 2px dashed rgba(255, 255, 255, 0.28);
		background: linear-gradient(180deg, rgba(112, 138, 145, 0.15), rgba(183, 203, 208, 0.12));
		text-align: center;
		cursor: pointer;
		overflow: hidden;
	}

	.upload-dropzone input {
		position: absolute;
		inset: 0;
		opacity: 0;
		cursor: pointer;
	}

	.upload-dropzone-icon {
		font-size: 2.8rem;
		line-height: 1;
	}

	.upload-dropzone-title {
		font-size: 1.1rem;
		font-weight: 800;
		color: rgba(255, 255, 255, 0.96);
	}

	.upload-dropzone-subtitle {
		font-size: 0.95rem;
		color: rgba(255, 255, 255, 0.76);
	}

	.upload-type-row {
		display: flex;
		justify-content: flex-start;
	}

	.topic-inline-select {
		width: min(280px, 100%);
	}

	.topic-doc-list {
		margin-top: 0.25rem;
	}

	.empty-state {
		text-align: center;
		padding: 3rem 2rem;
		color: var(--theme-text-muted);
	}

	.empty-icon {
		font-size: 2.5rem;
		margin-bottom: 1rem;
		opacity: 0.6;
	}

	.empty-state p {
		margin: 0;
		font-size: 0.95rem;
		font-style: italic;
	}

	/* Mobile responsive */
	@media (max-width: 768px) {
		.topic-accordion-header {
			padding: 1rem 1rem 0.95rem;
		}

		.topic-accordion-title-wrap {
			gap: 0.75rem;
		}

		.topic-accordion-index {
			font-size: 1.35rem;
		}

		.topic-accordion-title {
			font-size: 1rem;
		}

		.topic-status-pill {
			padding: 0.34rem 0.72rem;
			font-size: 0.78rem;
		}

		.topic-accordion-body {
			padding: 0 1rem 1rem;
		}

		.syllabus-preview {
			min-height: 120px;
			padding: 1rem;
			font-size: 0.95rem;
		}

		.topic-material-tabs {
			grid-template-columns: 1fr;
		}

		.topic-material-tab {
			padding: 0.85rem 0.85rem 0.75rem;
			font-size: 0.95rem;
		}

		.upload-dropzone {
			min-height: 190px;
			padding: 1.2rem;
		}

		.upload-dropzone-title {
			font-size: 1rem;
		}

		.upload-dropzone-subtitle {
			font-size: 0.85rem;
		}

		.empty-state {
			padding: 2rem 1rem;
		}

		.empty-icon {
			font-size: 2rem;
		}

		.empty-state p {
			font-size: 0.85rem;
		}
	}
</style>
