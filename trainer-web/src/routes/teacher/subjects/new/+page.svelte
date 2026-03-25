<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
	import { browser } from '$app/environment';
	import { beforeNavigate } from '$app/navigation';
	import { goto } from '$app/navigation';
	import { apiFetch } from '$lib/api/client';
	import { session } from '$lib/session';
	import FileUploadZone from '$lib/components/FileUploadZone.svelte';
	import { createSubject, createTopic, extractChapters, getSubject, updateTopic, type TopicResponse } from '$lib/api/subjects';
	import {
		deleteDocumentById,
		getDocumentStatus,
		listReferenceDocuments,
		scheduleBackgroundGeneration,
		uploadDocument,
	} from '$lib/api/documents';

	const DRAFT_STORAGE_KEY = 'qgen:new-topic-wizard:draft:v1';
	const MIN_QUESTION_COUNT = 1;
	const DEFAULT_QUESTION_COUNT = 30;

	interface GenerationLimitsResponse {
		max_batch_size: number;
	}

	let maxQuestionCount = $state(DEFAULT_QUESTION_COUNT);

	function clampStep(value: number) {
		if (!Number.isFinite(value)) return 1;
		return Math.max(1, Math.min(6, Math.trunc(value)));
	}

	function clampQuestionCount(value: number) {
		const safeMax = Math.max(MIN_QUESTION_COUNT, Math.trunc(maxQuestionCount));
		if (!Number.isFinite(value)) return Math.min(DEFAULT_QUESTION_COUNT, safeMax);
		return Math.max(MIN_QUESTION_COUNT, Math.min(safeMax, Math.trunc(value)));
	}

	onMount(() => {
		const unsub = session.subscribe((s) => {
			if (!s) goto('/teacher/login');
		});

		void loadGenerationLimitsAndRestoreDraft();
		return unsub;
	});

	async function loadGenerationLimitsAndRestoreDraft() {
		try {
			const limits = await apiFetch<GenerationLimitsResponse>('/settings/generation-limits');
			const maxBatch = Number(limits?.max_batch_size ?? DEFAULT_QUESTION_COUNT);
			maxQuestionCount = maxBatch > 0 ? maxBatch : DEFAULT_QUESTION_COUNT;
		} catch {
			maxQuestionCount = DEFAULT_QUESTION_COUNT;
		}

		desiredQuestionCount = clampQuestionCount(desiredQuestionCount);
		await restoreDraftAndResume();
	}

	beforeNavigate(({ to }) => {
		const staying = to?.url?.pathname?.startsWith('/teacher/train/new');
		const goingToLoop = to?.url?.pathname?.startsWith('/teacher/train/loop');
		if (!staying && !goingToLoop) {
			clearDraft();
		}
	});

	// ── Wizard state ──
	let step = $state(1);
	const totalSteps = 5;

	// Step 1: Subject/Discipline
	const presetDisciplines = [
		{ name: 'Engineering', icon: '⚙️' },
		{ name: 'Medicine', icon: '🩺' },
		{ name: 'Dental', icon: '🦷' },
		{ name: 'Business', icon: '📊' },
		{ name: 'Law', icon: '⚖️' },
		{ name: 'Arts & Humanities', icon: '🎨' }
	] as const;
	let selectedDiscipline = $state('');
	let useCustomDiscipline = $state(false);
	let disciplineName = $state('');
	let disciplineCode = $state('');

	// Custom discipline modal
	let showCustomDisciplineModal = $state(false);
	let customDisciplineInput = $state('');

	// Step 2: Topics
	interface TopicDocItem {
		id: string;
		filename: string;
		file_size_bytes: number;
		processing_status: string;
		processing_progress: number;
		processing_step?: string;
		processing_detail?: string;
	}
	interface TopicItem {
		name: string;
		syllabusContent: string;
		serverId?: string;
		files: File[];
		docs: TopicDocItem[];
		uploading: boolean;
		uploadError: string;
		refFiles: File[];
		refDocs: TopicDocItem[];
		uploadingRef: boolean;
		refUploadError: string;
		activeTab: 'book' | 'questions';
	}
	let topics = $state<TopicItem[]>([]);
	let topicInput = $state('');
	let topicError = $state('');
	let importingPdf = $state(false);
	let importError = $state('');
	// We need a temp subject to use extractChapters — we'll create it lazily
	let tempSubjectId = $state('');

	// Step 3: Syllabus per topic (with per-topic PDF uploads)
	let expandedTopic = $state(0);
	let topicDocPollTimer: ReturnType<typeof setInterval> | null = null;

	// Reference state (now per-topic, kept minimal for setup flow)
	let skipReferencePdf = $state(false);
	let materialPollTimer: ReturnType<typeof setInterval> | null = null;

	// Step 4/5: Setup & generation
	let isSettingUp = $state(false);
	let setupProgress = $state(0);
	let setupStatus = $state('');
	let setupError = $state('');
	let completeOnlyMode = $state(false);
	let backgroundGenerationScheduled = $state(false);
	let backgroundGenerationMessage = $state('');
	let desiredQuestionCount = $state(DEFAULT_QUESTION_COUNT);
	let draftHydrated = $state(false);

	// ── Derived ──
	let allTopicDocs = $derived(topics.flatMap(t => t.docs));
	let allTopicRefDocs = $derived(topics.flatMap(t => t.refDocs));
	let totalBookDocs = $derived(allTopicDocs.length);
	let totalRefDocs = $derived(allTopicRefDocs.length);
	let hasAnyDocs = $derived(totalBookDocs > 0 || totalRefDocs > 0);

	function isDocProcessing(doc: TopicDocItem) {
		const s = doc.processing_status.toLowerCase();
		return s === 'pending' || s === 'processing';
	}
	function isDocFailed(doc: TopicDocItem) {
		const s = doc.processing_status.toLowerCase();
		return s === 'failed' || s === 'error';
	}
	function isDocComplete(doc: TopicDocItem) {
		const s = doc.processing_status.toLowerCase();
		return s === 'completed' || s === 'complete' || s === 'processed';
	}

	let anyDocsProcessing = $derived([...allTopicDocs, ...allTopicRefDocs].some(isDocProcessing));
	let anyDocsFailed = $derived([...allTopicDocs, ...allTopicRefDocs].some(isDocFailed));
	let allDocsReady = $derived(hasAnyDocs && !anyDocsProcessing && !anyDocsFailed);
	let hasReferenceUploads = $derived(totalBookDocs > 0 || totalRefDocs > 0);

	$effect(() => {
		if (hasReferenceUploads && skipReferencePdf) {
			skipReferencePdf = false;
		}
	});

	let canProceed = $derived.by(() => {
		switch (step) {
			case 1: return disciplineName.trim().length > 0;
			case 2: return topics.length > 0;
			case 3:
				return (skipReferencePdf || hasReferenceUploads) &&
					desiredQuestionCount >= MIN_QUESTION_COUNT &&
					desiredQuestionCount <= maxQuestionCount &&
					!anyDocsFailed;
			case 4: return true; // review
			case 5: return true;
			default: return false;
		}
	});

	let stepTitle = $derived.by(() => {
		switch (step) {
			case 1: return 'Subject';
			case 2: return 'Topics';
			case 3: return 'Topic Content & References';
			case 4: return 'Review';
			case 5: return 'Setting Up';
			default: return '';
		}
	});

	let topicsWithSyllabus = $derived(topics.filter(t => t.syllabusContent.trim().length > 0).length);

	function saveDraft() {
		if (!browser || !draftHydrated) return;
		const draft = {
			step,
			selectedDiscipline,
			useCustomDiscipline,
			disciplineName,
			disciplineCode,
			topics,
			expandedTopic,
			tempSubjectId,
			backgroundGenerationScheduled,
			backgroundGenerationMessage,
			desiredQuestionCount,
			skipReferencePdf,
		};
		localStorage.setItem(DRAFT_STORAGE_KEY, JSON.stringify(draft));
	}

	function clearDraft() {
		if (!browser) return;
		localStorage.removeItem(DRAFT_STORAGE_KEY);
	}

	async function restoreDraftAndResume() {
		if (!browser) return;
		const raw = localStorage.getItem(DRAFT_STORAGE_KEY);
		if (!raw) {
			draftHydrated = true;
			return;
		}

		try {
			const parsed = JSON.parse(raw) as Partial<{
				step: number;
				selectedDiscipline: string;
				useCustomDiscipline: boolean;
				disciplineName: string;
				disciplineCode: string;
				topics: TopicItem[];
				expandedTopic: number;
				tempSubjectId: string;
				backgroundGenerationScheduled: boolean;
				backgroundGenerationMessage: string;
				desiredQuestionCount: number;
				skipReferencePdf: boolean;
			}>;

			step = clampStep(parsed.step ?? 1);
			selectedDiscipline = parsed.selectedDiscipline ?? '';
			useCustomDiscipline = parsed.useCustomDiscipline ?? false;
			disciplineName = parsed.disciplineName ?? '';
			disciplineCode = parsed.disciplineCode ?? '';
			topics = Array.isArray(parsed.topics) ? parsed.topics : [];
			expandedTopic = Math.max(0, Math.min(topics.length - 1, parsed.expandedTopic ?? 0));
			tempSubjectId = parsed.tempSubjectId ?? '';
			backgroundGenerationScheduled = parsed.backgroundGenerationScheduled ?? false;
			backgroundGenerationMessage = parsed.backgroundGenerationMessage ?? '';
			desiredQuestionCount = clampQuestionCount(parsed.desiredQuestionCount ?? DEFAULT_QUESTION_COUNT);
			skipReferencePdf = parsed.skipReferencePdf ?? false;

			if (tempSubjectId) {
				await refreshAllTopicDocStatuses();
				if (anyDocsProcessing) {
					startTopicDocPolling();
				}
			}
		} catch {
			clearDraft();
		}

		draftHydrated = true;
	}

	$effect(() => {
		saveDraft();
	});

	// ── Functions ──
	function syncDisciplineName(value: string) {
		disciplineName = value;
	}

	function handleDisciplineSelection(value: string) {
		useCustomDiscipline = false;
		selectedDiscipline = value;
		syncDisciplineName(value);
		step = 2;
	}

	function activateCustomDiscipline() {
		selectedDiscipline = '';
		customDisciplineInput = '';
		showCustomDisciplineModal = true;
	}

	function closeCustomDisciplineModal() {
		showCustomDisciplineModal = false;
		customDisciplineInput = '';
	}

	function submitCustomDiscipline() {
		const trimmed = customDisciplineInput.trim();
		if (trimmed) {
			disciplineName = trimmed;
			useCustomDiscipline = true;
			selectedDiscipline = '';
			showCustomDisciplineModal = false;
			customDisciplineInput = '';
			step = 2;
		}
	}

	function handleCustomDisciplineKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter') {
			e.preventDefault();
			submitCustomDiscipline();
		} else if (e.key === 'Escape') {
			e.preventDefault();
			closeCustomDisciplineModal();
		}
	}

	function focusInput(element: HTMLInputElement) {
		element.focus();
	}

	function normalizeTopicName(value: string) {
		return value.trim().replace(/\s+/g, ' ');
	}

	function topicKey(value: string) {
		return normalizeTopicName(value).toLowerCase();
	}

	function handleTopicInput(e: Event) {
		topicInput = (e.currentTarget as HTMLInputElement).value;
		topicError = '';
	}

	function addTopic() {
		const normalized = normalizeTopicName(topicInput);
		if (!normalized) return;

		const exists = topics.some((t) => topicKey(t.name) === topicKey(normalized));
		if (exists) {
			topicError = 'This topic is already in the list.';
			return;
		}

		topics = [...topics, {
			name: normalized,
			syllabusContent: '',
			serverId: undefined,
			files: [],
			docs: [],
			uploading: false,
			uploadError: '',
			refFiles: [],
			refDocs: [],
			uploadingRef: false,
			refUploadError: '',
			activeTab: 'book',
		}];
		topicInput = '';
		topicError = '';
	}

	function removeTopic(index: number) {
		topics = topics.filter((_, i) => i !== index);
		if (expandedTopic >= topics.length) expandedTopic = Math.max(0, topics.length - 1);
	}

	function handleTopicKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter') { e.preventDefault(); addTopic(); }
	}

	function clearTopicDocPolling() {
		if (topicDocPollTimer) {
			clearInterval(topicDocPollTimer);
			topicDocPollTimer = null;
		}
	}

	function isSubjectNotFoundError(error: unknown) {
		if (!(error instanceof Error)) return false;
		const msg = error.message.toLowerCase();
		return msg.includes('subject not found') || msg.includes('404') || msg.includes('not found');
	}

	onDestroy(() => {
		clearTopicDocPolling();
	});

	async function ensureSubjectId(): Promise<string> {
		if (tempSubjectId) {
			try {
				await getSubject(tempSubjectId);
				return tempSubjectId;
			} catch {
				tempSubjectId = '';
			}
		}

		const code =
			disciplineCode.trim() ||
			disciplineName.trim().slice(0, 6).toUpperCase().replace(/\s+/g, '') + String(Date.now()).slice(-4);
		const subj = await createSubject({
			name: disciplineName.trim(),
			code,
		});
		tempSubjectId = subj.id;
		return subj.id;
	}

	function fileKey(file: File) {
		return `${file.name}::${file.size}`;
	}

	function docKey(doc: { filename: string; file_size_bytes: number }) {
		return `${doc.filename}::${doc.file_size_bytes}`;
	}

	function subtractFiles(base: File[], subtract: File[]) {
		const counts = new Map<string, number>();
		for (const file of subtract) {
			const key = fileKey(file);
			counts.set(key, (counts.get(key) || 0) + 1);
		}

		const remaining: File[] = [];
		for (const file of base) {
			const key = fileKey(file);
			const count = counts.get(key) || 0;
			if (count > 0) {
				counts.set(key, count - 1);
			} else {
				remaining.push(file);
			}
		}

		return remaining;
	}

	async function deleteMatchingDocs(
		removedFiles: File[],
		docs: Array<{ id: string; filename: string; file_size_bytes: number }>,
	) {
		if (!removedFiles.length || !docs.length) return;

		const remainingDocs = [...docs];
		const idsToDelete: string[] = [];

		for (const file of removedFiles) {
			const exactIndex = remainingDocs.findIndex((doc) => docKey(doc) === fileKey(file));
			const nameOnlyIndex = exactIndex === -1
				? remainingDocs.findIndex((doc) => doc.filename === file.name)
				: -1;

			const matchedIndex = exactIndex !== -1 ? exactIndex : nameOnlyIndex;
			if (matchedIndex !== -1) {
				idsToDelete.push(remainingDocs[matchedIndex].id);
				remainingDocs.splice(matchedIndex, 1);
			}
		}

		for (const id of idsToDelete) {
			await deleteDocumentById(id);
		}
	}

	function toggleSkipReferencePdf() {
		skipReferencePdf = !skipReferencePdf;
	}

	async function ensureTopicOnServer(topicIndex: number): Promise<string> {
		const topic = topics[topicIndex];
		if (topic.serverId) return topic.serverId;

		const subjectId = await ensureSubjectId();
		const created = await createTopic(subjectId, {
			name: topic.name,
			order_index: topicIndex,
			subject_id: subjectId,
			syllabus_content: topic.syllabusContent || undefined,
		});
		topics[topicIndex] = { ...topic, serverId: created.id };
		return created.id;
	}

	async function handleTopicFilesSelected(topicIndex: number, files: File[]) {
		const topic = topics[topicIndex];
		if (topic.uploading) return;
		if (!files.length && topic.files.length === 0) return;

		topics[topicIndex] = { ...topic, uploadError: '' };

		const isRemovalUpdate = files.length <= topic.files.length
			&& files.every((file) => topic.files.some((existing) => fileKey(existing) === fileKey(file)));

		if (isRemovalUpdate) {
			const removedFiles = subtractFiles(topic.files, files);
			topics[topicIndex] = { ...topics[topicIndex], files };
			try {
				await deleteMatchingDocs(removedFiles, topic.docs);
				await refreshTopicDocStatuses(topicIndex);
			} catch (e: unknown) {
				topics[topicIndex] = { ...topics[topicIndex], uploadError: e instanceof Error ? e.message : 'Failed to remove file' };
			}
			return;
		}

		const newFiles = subtractFiles(files, topic.files);
		if (!newFiles.length) return;

		topics[topicIndex] = { ...topics[topicIndex], uploading: true, files: [...topic.files, ...newFiles] };

		try {
			const subjectId = await ensureSubjectId();
			const topicId = await ensureTopicOnServer(topicIndex);
			for (const file of newFiles) {
				await uploadDocument(file, subjectId, 'reference_book', topicId);
			}
			await refreshTopicDocStatuses(topicIndex);
			startTopicDocPolling();
		} catch (e: unknown) {
			topics[topicIndex] = { ...topics[topicIndex], uploadError: e instanceof Error ? e.message : 'Failed to upload file' };
		} finally {
			topics[topicIndex] = { ...topics[topicIndex], uploading: false };
		}
	}

	async function handleTopicRefQuestionsSelected(topicIndex: number, files: File[]) {
		const topic = topics[topicIndex];
		if (topic.uploadingRef) return;
		if (!files.length && topic.refFiles.length === 0) return;

		topics[topicIndex] = { ...topic, refUploadError: '' };

		const isRemovalUpdate = files.length <= topic.refFiles.length
			&& files.every((file) => topic.refFiles.some((existing) => fileKey(existing) === fileKey(file)));

		if (isRemovalUpdate) {
			const removedFiles = subtractFiles(topic.refFiles, files);
			topics[topicIndex] = { ...topics[topicIndex], refFiles: files };
			try {
				await deleteMatchingDocs(removedFiles, topic.refDocs);
				await refreshTopicDocStatuses(topicIndex);
			} catch (e: unknown) {
				topics[topicIndex] = { ...topics[topicIndex], refUploadError: e instanceof Error ? e.message : 'Failed to remove file' };
			}
			return;
		}

		const newFiles = subtractFiles(files, topic.refFiles);
		if (!newFiles.length) return;

		topics[topicIndex] = { ...topics[topicIndex], uploadingRef: true, refFiles: [...topic.refFiles, ...newFiles] };

		try {
			const subjectId = await ensureSubjectId();
			const topicId = await ensureTopicOnServer(topicIndex);
			for (const file of newFiles) {
				await uploadDocument(file, subjectId, 'reference_questions', topicId);
			}
			await refreshTopicDocStatuses(topicIndex);
			startTopicDocPolling();
		} catch (e: unknown) {
			topics[topicIndex] = { ...topics[topicIndex], refUploadError: e instanceof Error ? e.message : 'Failed to upload file' };
		} finally {
			topics[topicIndex] = { ...topics[topicIndex], uploadingRef: false };
		}
	}

	async function enrichDocStatuses(baseDocs: TopicDocItem[]): Promise<TopicDocItem[]> {
		return Promise.all(
			baseDocs.map(async (doc) => {
				const status = doc.processing_status.toLowerCase();
				if (status === 'completed' || status === 'complete' || status === 'processed') {
					return { ...doc, processing_progress: 100, processing_step: 'completed', processing_detail: 'Processing complete' };
				}
				if (status === 'failed' || status === 'error') {
					return { ...doc, processing_progress: 100, processing_step: 'failed', processing_detail: 'Processing failed' };
				}
				try {
					const statusRes = await getDocumentStatus(doc.id);
					return {
						...doc,
						processing_progress: statusRes.processing_progress ?? doc.processing_progress,
						processing_step: statusRes.processing_step ?? '',
						processing_detail: statusRes.processing_detail ?? '',
					};
				} catch {
					return doc;
				}
			})
		);
	}

	function toBaseDocItems(docs: Array<{ id: string; filename: string; file_size_bytes: number; processing_status: string }>): TopicDocItem[] {
		return docs.map((doc) => ({
			id: doc.id,
			filename: doc.filename,
			file_size_bytes: doc.file_size_bytes,
			processing_status: doc.processing_status,
			processing_progress: doc.processing_status.toLowerCase() === 'completed' ? 100 : 0,
			processing_step: '',
			processing_detail: '',
		}));
	}

	async function refreshTopicDocStatuses(topicIndex: number) {
		const topic = topics[topicIndex];
		if (!topic.serverId || !tempSubjectId) return;

		const res = await listReferenceDocuments(tempSubjectId, topic.serverId);
		const bookDocs = await enrichDocStatuses(toBaseDocItems(res.reference_books || []));
		const refDocs = await enrichDocStatuses(toBaseDocItems(res.reference_questions || []));

		topics[topicIndex] = { ...topics[topicIndex], docs: bookDocs, refDocs };
	}

	async function refreshAllTopicDocStatuses() {
		for (let i = 0; i < topics.length; i++) {
			if (topics[i].serverId) {
				await refreshTopicDocStatuses(i);
			}
		}
		const stillProcessing = topics.some(t =>
			[...t.docs, ...t.refDocs].some(isDocProcessing)
		);
		if (!stillProcessing) {
			clearTopicDocPolling();
		}
	}

	function startTopicDocPolling() {
		clearTopicDocPolling();
		topicDocPollTimer = setInterval(() => {
			void refreshAllTopicDocStatuses().catch(() => {});
		}, 3000);
	}

	let topicsWithDocs = $derived(topics.filter(t => t.docs.length > 0).length);
	let topicsWithRefDocs = $derived(topics.filter(t => t.refDocs.length > 0).length);

	async function importFromPdf() {
		const input = document.createElement('input');
		input.type = 'file';
		input.accept = '.pdf,.doc,.docx';
		input.onchange = async () => {
			const file = input.files?.[0];
			if (!file) return;
			importingPdf = true;
			importError = '';
			try {
				// Need a subject to extract chapters — create temp one if needed
				let subjectId = await ensureSubjectId();
				let result: { message: string; chapters_created: number; topics: TopicResponse[] };
				try {
					result = await extractChapters(subjectId, file);
				} catch (extractError) {
					if (!isSubjectNotFoundError(extractError)) throw extractError;
					// Subject can be deleted between restore and upload; recreate and retry once.
					tempSubjectId = '';
					subjectId = await ensureSubjectId();
					result = await extractChapters(subjectId, file);
				}
				if (result.topics && result.topics.length > 0) {
					const existingKeys = new Set(topics.map((existing) => topicKey(existing.name)));
					const newTopics = result.topics
						.filter((t) => !existingKeys.has(topicKey(t.name)))
						.map(t => ({
							name: normalizeTopicName(t.name),
							syllabusContent: t.syllabus_content || '',
							serverId: t.id,
							files: [] as File[],
							docs: [] as TopicDocItem[],
							uploading: false,
							uploadError: '',
							refFiles: [] as File[],
							refDocs: [] as TopicDocItem[],
							uploadingRef: false,
							refUploadError: '',
							activeTab: 'book' as const,
						}));
					topics = [...topics, ...newTopics];
				}
			} catch (e: unknown) {
				importError = e instanceof Error ? e.message : 'Failed to import chapters';
			} finally {
				importingPdf = false;
			}
		};
		input.click();
	}

	function nextStep() {
		if (step < totalSteps && canProceed) step++;
	}

	function prevStep() {
		if (step > 1 && !isSettingUp) step--;
		topicError = '';
	}

	async function startSetup(startTraining = true) {
		isSettingUp = true;
		completeOnlyMode = !startTraining;
		backgroundGenerationMessage = '';
		setupProgress = 0;
		setupError = '';
		setupStatus = 'Creating Subject...';

		try {
			// 1. Create subject (or reuse tempSubjectId)
			let subjectId = tempSubjectId;
			if (!subjectId) {
				subjectId = await ensureSubjectId();
			}
			setupProgress = 10;

			// 2. Create topics (or update existing from PDF import)
			setupStatus = 'Adding topics...';
			// Get existing topics from pdf import (already created by extractChapters)
			const existingTopicNames = new Set<string>();
			const topicIdByName = new Map<string, string>();
			if (tempSubjectId) {
				// Topics from extractChapters are already created — just need to update syllabus content
				try {
					const detail = await getSubject(subjectId);
					for (const t of detail.topics) {
						existingTopicNames.add(t.name);
						topicIdByName.set(topicKey(t.name), t.id);
						// Update syllabus if user edited it
						const local = topics.find(lt => lt.name === t.name);
						if (local && local.syllabusContent.trim() && local.syllabusContent !== (t.syllabus_content || '')) {
							await updateTopic(subjectId, t.id, {
								syllabus_content: local.syllabusContent,
								has_syllabus: true,
							});
						}
					}
				} catch { /* ignore */ }
			}
			// Create any manually-added topics not yet on server
			for (let i = 0; i < topics.length; i++) {
				if (!existingTopicNames.has(topics[i].name)) {
					const created = await createTopic(subjectId, {
						name: topics[i].name,
						order_index: i,
						subject_id: subjectId,
						syllabus_content: topics[i].syllabusContent || undefined,
					});
					topicIdByName.set(topicKey(topics[i].name), created.id);
				}
			}
			setupProgress = 40;

			// 3. Queue one batch per topic after setup completion.
			setupStatus = 'Scheduling first question batches...';
			const questionsPerTopic = clampQuestionCount(desiredQuestionCount);
			const topicIdsForGeneration = topics
				.map((topic) => topicIdByName.get(topicKey(topic.name)))
				.filter((id): id is string => Boolean(id));
			if (topicIdsForGeneration.length === 1) {
				await scheduleBackgroundGeneration({
					subjectId,
					topicId: topicIdsForGeneration[0],
					count: questionsPerTopic,
					types: 'mcq',
					difficulty: 'medium',
					allowWithoutReference: skipReferencePdf,
				});
			} else if (topicIdsForGeneration.length > 1) {
				await scheduleBackgroundGeneration({
					subjectId,
					topicIds: topicIdsForGeneration,
					count: questionsPerTopic * topicIdsForGeneration.length,
					types: 'mcq',
					difficulty: 'medium',
					allowWithoutReference: skipReferencePdf,
				});
			}
			backgroundGenerationScheduled = true;
			backgroundGenerationMessage = `Scheduled ${questionsPerTopic} questions for ${topicIdsForGeneration.length} topic${topicIdsForGeneration.length === 1 ? '' : 's'}.`;

			// 4. Reference materials are already uploaded per-topic in Step 3.
			setupProgress = 80;

			setupProgress = 100;
			setupStatus = 'Setup complete. Redirecting to subjects...';
			await new Promise(r => setTimeout(r, 600));
			clearDraft();
			goto(`/teacher/train/existing?subject=${encodeURIComponent(subjectId)}`);
		} catch (e: unknown) {
			setupError = e instanceof Error ? e.message : 'Setup failed';
			setupStatus = '';
			isSettingUp = false;
		}
	}

	function handleQuestionCountInput(e: Event) {
		const target = e.currentTarget as HTMLInputElement;
		desiredQuestionCount = clampQuestionCount(Number(target.value));
	}
</script>

<svelte:head>
	<title>{stepTitle} — New Topic — VQuest Trainer</title>
</svelte:head>

<div class="wizard">
	<div class="wizard-meta animate-fade-in">
		<p class="wizard-kicker"></p>
		<!-- <div class="progress-pill" aria-label="Setup progress">
			<span class="progress-pill-count">{step}/{totalSteps}</span>
			<div class="progress-pill-track" aria-hidden="true">
				<div class="progress-pill-fill" style:width={`${(step / totalSteps) * 100}%`}></div>
			</div>
		</div> -->
	</div>
	<!-- Step indicator -->
	<div class="step-bar">
		{#each Array(totalSteps) as _, i}
			<div class="step-dot" class:active={i + 1 === step} class:done={i + 1 < step}></div>
			{#if i < totalSteps - 1}
				<div class="step-line" class:done={i + 1 < step}></div>
			{/if}
		{/each}
	</div>

	<h1 class="step-title">{stepTitle}</h1>

	<div class="step-content">
		<!-- Step 1: Discipline -->
		{#if step === 1}
			<div class="field-group">
				<label class="field-label" for="disc-code">Subject Code <span class="hint">(optional)</span></label>
				<input id="disc-code" class="glass-input" type="text" placeholder="e.g., CS101" bind:value={disciplineCode} />
			</div>
			<div class="field-group">
				<span class="field-label">Subject Name *</span>
				<div class="discipline-grid" role="list" aria-label="Choose a Subject">
					<button
							type="button"
							class="glass-panel discipline-card discipline-card-custom"
							class:selected={useCustomDiscipline}
							onclick={activateCustomDiscipline}
						>
						<span class="discipline-icon">＋</span>
						<span class="discipline-card-name">
							{#if useCustomDiscipline && disciplineName}
								{disciplineName}
							{:else}
								Add Custom Subject
							{/if}
						</span>
					</button>
					{#each presetDisciplines as discipline}
						<button
							type="button"
							class="glass-panel discipline-card"
							class:selected={!useCustomDiscipline && selectedDiscipline === discipline.name}
							onclick={() => handleDisciplineSelection(discipline.name)}
						>
							<span class="discipline-icon">{discipline.icon}</span>
							<span class="discipline-card-name">{discipline.name}</span>
						</button>
					{/each}
				</div>
			</div>

		<!-- Step 2: Topics -->
		{:else if step === 2}
			<p class="step-desc">Add topics manually or import from a syllabus PDF</p>
			<div class="topic-input-row">
				<input
					class="glass-input topic-input"
					type="text"
					placeholder="e.g., Organic Chemistry"
					bind:value={topicInput}
					oninput={handleTopicInput}
					onkeydown={handleTopicKeydown}
				/>
				<button class="glass-btn add-btn" onclick={addTopic} disabled={!topicInput.trim()}>Add</button>
			</div>
			{#if topicError}
				<p class="inline-error">⚠️ {topicError}</p>
			{/if}

			<div class="import-row">
				<button class="glass-btn import-btn" onclick={importFromPdf} disabled={importingPdf || !disciplineName.trim()}>
					{#if importingPdf}
						<span class="btn-spinner"></span> Extracting…
					{:else}
						Import
					{/if}
				</button>
				<span class="import-hint">Import topics from {disciplineName} syllabus PDF.</span>
			</div>
			{#if importError}
				<p class="inline-error">⚠️ {importError}</p>
			{/if}

			{#if topics.length > 0}
				<div class="topic-list">
					{#each topics as topic, i}
						<div class="topic-chip" class:has-syllabus={topic.syllabusContent.trim().length > 0}>
							<span class="topic-number">{i + 1}</span>
							<span class="topic-name">{topic.name}</span>
							{#if topic.syllabusContent.trim()}
								<span class="syllabus-badge">📄</span>
							{/if}
							<button class="chip-remove" onclick={() => removeTopic(i)}>×</button>
						</div>
					{/each}
				</div>
			{/if}

		<!-- Step 3: Topic Content & References -->
		{:else if step === 3}
			<p class="step-desc">Add syllabus, reference books, and optional reference questions for each topic</p>
			{#if topics.length === 0}
				<div class="center-msg">
					<span>📭</span>
					<p>No topics added yet. Go back to add topics.</p>
				</div>
			{:else}
				<div class="syllabus-accordion">
					{#each topics as topic, i}
						<div class="syllabus-item" class:expanded={expandedTopic === i}>
							<button class="syllabus-header" onclick={() => expandedTopic = expandedTopic === i ? -1 : i}>
								<div class="sh-left">
									<span class="sh-number">{i + 1}</span>
									<span class="sh-name">{topic.name}</span>
								</div>
								<div class="sh-right">
									{#if topic.docs.length > 0}
										<span class="sh-badge docs">� {topic.docs.length}</span>
									{/if}
									{#if topic.refDocs.length > 0}
										<span class="sh-badge docs">📝 {topic.refDocs.length}</span>
									{/if}
									{#if topic.syllabusContent.trim()}
										<span class="sh-badge filled">✓ Content</span>
									{:else}
										<span class="sh-badge empty">Empty</span>
									{/if}
									<span class="sh-arrow">{expandedTopic === i ? '▼' : '▶'}</span>
								</div>
							</button>
							{#if expandedTopic === i}
								<div class="syllabus-body">
									<div class="topic-section">
										<span class="topic-section-label">Syllabus Content</span>
										<textarea
											class="glass-input syl-textarea"
											placeholder="Paste or type the syllabus content for this topic..."
											bind:value={topics[i].syllabusContent}
											rows="4"
										></textarea>
									</div>

									<!-- Tabbed reference uploads -->
									<div class="topic-ref-tabs">
										<button
											class="topic-tab" class:active={topic.activeTab === 'book'}
											onclick={() => topics[i] = { ...topics[i], activeTab: 'book' }}
										>
											📚 Reference Books
											{#if topic.docs.length > 0}<span class="tab-count">{topic.docs.length}</span>{/if}
										</button>
										<button
											class="topic-tab" class:active={topic.activeTab === 'questions'}
											onclick={() => topics[i] = { ...topics[i], activeTab: 'questions' }}
										>
											� Reference Questions
											{#if topic.refDocs.length > 0}<span class="tab-count">{topic.refDocs.length}</span>{/if}
											<span class="tab-optional">optional</span>
										</button>
									</div>

									<div class="topic-tab-content">
										{#if topic.activeTab === 'book'}
											<p class="topic-section-hint">Upload textbooks or notes for "{topic.name}"</p>
											<FileUploadZone
												accept=".pdf,.doc,.docx,.txt,.pptx"
												label="Drop files or click to upload"
												hint="PDF, Word, PowerPoint, or Text"
												files={topic.files}
												onfilesSelected={(files) => handleTopicFilesSelected(i, files)}
											/>
											{#if topic.uploading}
												<p class="topic-upload-status">📤 Uploading...</p>
											{/if}
											{#if topic.uploadError}
												<p class="inline-error">⚠️ {topic.uploadError}</p>
											{/if}
											{#if topic.docs.length > 0}
												<div class="topic-doc-list">
													{#each topic.docs as doc}
														<div class="topic-doc-item">
															<span class="topic-doc-icon">📄</span>
															<span class="topic-doc-name">{doc.filename}</span>
															<span class="topic-doc-status" class:completed={isDocComplete(doc)} class:failed={isDocFailed(doc)}>
																{#if isDocComplete(doc)}
																	✓ Ready
																{:else if isDocFailed(doc)}
																	✗ Failed
																{:else}
																	{doc.processing_progress}%
																{/if}
															</span>
														</div>
													{/each}
												</div>
											{/if}
										{:else}
											<p class="topic-section-hint">Upload past papers or question banks for "{topic.name}"</p>
											<FileUploadZone
												accept=".pdf,.doc,.docx,.txt,.csv,.xlsx,.xls"
												label="Drop files or click to upload"
												hint="PDF, Word, Excel, or CSV"
												files={topic.refFiles}
												onfilesSelected={(files) => handleTopicRefQuestionsSelected(i, files)}
											/>
											{#if topic.uploadingRef}
												<p class="topic-upload-status">📤 Uploading...</p>
											{/if}
											{#if topic.refUploadError}
												<p class="inline-error">⚠️ {topic.refUploadError}</p>
											{/if}
											{#if topic.refDocs.length > 0}
												<div class="topic-doc-list">
													{#each topic.refDocs as doc}
														<div class="topic-doc-item">
															<span class="topic-doc-icon">📝</span>
															<span class="topic-doc-name">{doc.filename}</span>
															<span class="topic-doc-status" class:completed={isDocComplete(doc)} class:failed={isDocFailed(doc)}>
																{#if isDocComplete(doc)}
																	✓ Ready
																{:else if isDocFailed(doc)}
																	✗ Failed
																{:else}
																	{doc.processing_progress}%
																{/if}
															</span>
														</div>
													{/each}
												</div>
											{/if}
										{/if}
									</div>
								</div>
							{/if}
						</div>
					{/each}
				</div>

				<!-- Generation settings below the accordion -->
				<div class="step3-footer">
					<p class="step-hint">{topicsWithSyllabus}/{topics.length} topics have syllabus • {topicsWithDocs} have books • {topicsWithRefDocs} have ref questions</p>

					<div class="step3-settings-row">
						{#if !hasReferenceUploads}
						<button
							type="button"
							class="glass-btn skip-pdf-btn"
							class:active={skipReferencePdf}
							onclick={toggleSkipReferencePdf}
						>
							{skipReferencePdf ? '✓ ' : ''}Generate without reference materials
						</button>
						{/if}
					</div>

					{#if skipReferencePdf}
						<p class="step-hint success-hint">✓ Will use topic and syllabus content only.</p>
					{/if}
					{#if anyDocsProcessing}
						<p class="step-hint">Some documents are still processing in the background...</p>
					{/if}
					{#if tempSubjectId}
						<p class="step-hint resume-note">💾 Progress saved. You can leave and return later.</p>
					{/if}
				</div>
			{/if}

		<!-- Step 4: Review -->
		{:else if step === 4}
			<div class="review-card glass">
				<h2 class="review-title">Review Setup</h2>
				{#if skipReferencePdf && totalBookDocs === 0}
					<p class="step-hint">Reference PDF is marked as not required for this subject.</p>
				{:else if completeOnlyMode || !allDocsReady}
					<p class="step-hint">Reference materials are still processing. You can complete setup now and continue from dashboard later.</p>
				{/if}
				<p class="step-hint">On Complete, one {clampQuestionCount(desiredQuestionCount)}-question batch will be scheduled for each topic.</p>
				{#if backgroundGenerationMessage}
					<p class="step-hint">{backgroundGenerationMessage}</p>
				{/if}
				<div class="review-sections">
					<div class="review-section">
						<span class="rs-label">Subject</span>
						<span class="rs-value">{disciplineName}{disciplineCode ? ` (${disciplineCode})` : ''}</span>
					</div>
					<div class="review-section">
						<span class="rs-label">Topics</span>
						<div class="rs-topics">
							{#each topics as t, i}
								<span class="rs-topic-chip">
									{i + 1}. {t.name}
									{#if t.syllabusContent.trim()}<span class="rs-syl">📄</span>{/if}
								</span>
							{/each}
						</div>
					</div>
					<div class="review-section">
						<span class="rs-label">Syllabus</span>
						<span class="rs-value">{topicsWithSyllabus} of {topics.length} topics have content</span>
					</div>
					<div class="review-section">
						<span class="rs-label">Reference Materials</span>
						<span class="rs-value">
							{#if skipReferencePdf && totalBookDocs === 0}
								Not required for this subject
							{:else}
								{totalBookDocs} book{totalBookDocs !== 1 ? 's' : ''} across {topicsWithDocs} topic{topicsWithDocs !== 1 ? 's' : ''}
							{/if}
						</span>
					</div>
					<div class="review-section">
						<span class="rs-label">Reference Questions</span>
						<span class="rs-value">{totalRefDocs} file{totalRefDocs !== 1 ? 's' : ''} across {topicsWithRefDocs} topic{topicsWithRefDocs !== 1 ? 's' : ''}</span>
					</div>
					<div class="review-section">
						<span class="rs-label">Questions To Generate</span>
						<span class="rs-value">{clampQuestionCount(desiredQuestionCount)} per topic (max {maxQuestionCount})</span>
					</div>
				</div>
				{#if setupError}
					<p class="gen-error">⚠️ {setupError}</p>
				{/if}
				{#if !isSettingUp}
					<div class="step-actions review-actions">
						<button class="glass-btn step-back-btn" onclick={prevStep}>
							← Back
						</button>
						<button class="glass-btn step-next-btn step-train-btn" onclick={() => { step = 5; startSetup(false); }}>
							✓ Finish Setup
						</button>
					</div>
				{/if}
			</div>

		<!-- Step 5: Setting up -->
		{:else if step === 5}
			<div class="progress-section">
				<div class="progress-icon">⚡</div>
				<h2 class="progress-title">{completeOnlyMode ? 'Completing Setup' : 'Setting Up'}</h2>
				<p class="progress-status">{setupStatus || 'Initializing...'}</p>
				<div class="progress-bar-wrap">
					<div class="progress-bar" style:width="{setupProgress}%"></div>
				</div>
				<span class="progress-pct">{setupProgress}%</span>
				{#if setupError}
					<p class="gen-error">⚠️ {setupError}</p>
					<button class="glass-btn" onclick={() => { step = 4; }}>← Back to Review</button>
				{/if}
			</div>
		{/if}
	</div>

	{#if step >= 2 && step <= 3}
		<div class="step-actions">
			<button class="glass-btn step-back-btn" onclick={prevStep}>← Back</button>
			{#if step === 2}
				<button class="glass-btn step-next-btn" onclick={nextStep} disabled={!canProceed}>Next: Content & References →</button>
			{:else if step === 3}
				<button class="glass-btn step-next-btn" onclick={nextStep} disabled={!canProceed}>Next: Review →</button>
			{/if}
		</div>
	{/if}
</div>

<!-- Custom Discipline Modal -->
{#if showCustomDisciplineModal}
	<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
	<div
		class="modal-backdrop"
		onclick={closeCustomDisciplineModal}
		role="button"
		tabindex="0"
		aria-label="Close modal"
	>
		<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
		<div class="discipline-modal glass-panel animate-scale-in" onclick={(e) => e.stopPropagation()} role="dialog" aria-modal="true" tabindex="-1">
			<!-- Header -->
			<div class="modal-header">
				<h3 class="modal-title">Add Subject</h3>
				<button class="modal-close" onclick={closeCustomDisciplineModal} aria-label="Close">
					<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
						<line x1="18" y1="6" x2="6" y2="18"></line>
						<line x1="6" y1="6" x2="18" y2="18"></line>
					</svg>
				</button>
			</div>

			<!-- Content -->
			<div class="modal-body">
				<p class="modal-description">Enter the name of your Subject</p>
				<input
					class="glass-input"
					type="text"
					placeholder="e.g., Computer Science"
					bind:value={customDisciplineInput}
					onkeydown={handleCustomDisciplineKeydown}
					use:focusInput
				/>
			</div>

			<!-- Footer -->
			<div class="modal-footer">
				<button class="glass-btn secondary-btn" onclick={closeCustomDisciplineModal}>
					Cancel
				</button>
				<button 
					class="glass-btn primary-btn" 
					onclick={submitCustomDiscipline}
					disabled={!customDisciplineInput.trim()}
				>
					Add Subject
				</button>
			</div>
		</div>
	</div>
{/if}

<style>
	.wizard {
		display: flex;
		flex-direction: column;
		align-items: center;
		min-height: 100vh;
		padding: 2rem 1.5rem max(1.25rem, env(safe-area-inset-bottom));
		max-width: 600px;
		margin: 0 auto;
	}

	.wizard-meta {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1rem;
		width: 100%;
		margin-bottom: 0.5rem;
	}

	.wizard-kicker {
		margin: 0;
		font-size: 0.78rem;
		font-weight: 700;
		letter-spacing: 0.14em;
		text-transform: uppercase;
		color: var(--theme-primary);
	}

	/* .progress-pill {
		min-width: 11rem;
		padding: 0.95rem 1.1rem;
		border-radius: 999px;
		background: linear-gradient(135deg, rgba(255, 255, 255, 0.3), rgba(255, 255, 255, 0.2));
		border: 1px solid rgba(255, 255, 255, 0.34);
		display: flex;
		align-items: center;
		gap: 0.85rem;
		box-shadow: 0 12px 26px rgba(0, 0, 0, 0.22), inset 0 1px 0 rgba(255, 255, 255, 0.45);
		backdrop-filter: blur(10px) saturate(130%);
		-webkit-backdrop-filter: blur(10px) saturate(130%);
	}

	.progress-pill-count {
		font-size: 1.35rem;
		font-weight: 700;
		color: #f8fffa;
		font-variant-numeric: tabular-nums;
		text-shadow: 0 1px 8px rgba(0, 0, 0, 0.38);
	}

	.progress-pill-track {
		flex: 1;
		height: 0.5rem;
		border-radius: 999px;
		background: rgba(10, 22, 16, 0.38);
		border: 1px solid rgba(255, 255, 255, 0.22);
		overflow: hidden;
	}

	.progress-pill-fill {
		height: 100%;
		background: linear-gradient(90deg, rgba(var(--theme-primary-rgb), 0.55), var(--theme-primary));
		border-radius: inherit;
		box-shadow: 0 0 10px rgba(var(--theme-primary-rgb), 0.55);
	} */

	/* Step bar */
	.step-bar {
		display: flex;
		align-items: center;
		gap: 0;
		margin-bottom: 2rem;
		width: 100%;
		max-width: 400px;
	}

	.step-dot {
		width: 10px;
		height: 10px;
		border-radius: 50%;
		background: rgba(30, 30, 30, 0.614);
		flex-shrink: 0;
		transition: all 0.3s;
	}

	.step-dot.active {
		background: var(--theme-primary);
		box-shadow: 0 0 8px var(--theme-glow);
		width: 12px;
		height: 12px;
	}

	.step-dot.done {
		background: var(--theme-primary);
		opacity: 0.6;
	}

	.step-line {
		flex: 1;
		height: 2px;
		background: rgba(54, 54, 54, 0.808);
		transition: background 0.3s;
		
	}

	.step-line.done {
		background: var(--theme-primary);
		opacity: 0.5;
	}

	.step-title {
		font-size: 1.75rem;
		font-weight: 800;
		margin: 0 0 0.5rem;
		color: var(--theme-text);
		text-align: center;
	}

	.step-content {
		width: 100%;
		flex: 1;
		margin-top: 1rem;
	}

	.resume-note {
		font-size: 0.8rem;
	}
	.step-desc {
		text-align: center;
		color: var(--theme-text-muted);
		font-size: 0.95rem;
		margin: 0 0 1.5rem;
	}

	.step-hint {
		text-align: center;
		color: var(--theme-text-muted);
		font-size: 0.85rem;
		margin-top: 1rem;
	}

	/* Step 1: Discipline fields */
	.field-group {
		margin-bottom: 1rem;
	}

	.field-label {
		display: block;
		font-size: 0.85rem;
		font-weight: 600;
		color: var(--theme-text);
		margin-bottom: 0.4rem;
	}

	.field-label .hint {
		font-weight: 400;
		color: var(--theme-text-muted);
		font-size: 0.8rem;
	}

	.discipline-grid {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 0.75rem;
	}

	.discipline-card {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		padding: 0.75rem;
		border-radius: var(--glass-radius);
		border: 1px solid rgba(255, 255, 255, 0.1);
		background: rgba(255, 255, 255, 0.04);
		color: inherit;
		text-align: left;
		text-decoration: none;
		transition: all 0.2s ease;
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

	.discipline-card:hover {
		background: linear-gradient(
			145deg,
			rgba(255,255,255,0.05) 0%,
			rgba(255,255,255,0.04) 50%,
			rgba(255,255,255,0.045) 100%
		) !important;
		border-color: rgba(var(--theme-primary-rgb), 0.28);
		transform: translateY(-1px);
		box-shadow: 
			0 12px 40px rgba(0, 0, 0, 0.3),
			inset 0 1px 1px rgba(255, 255, 255, 0.3),
			inset 0 -1px 1px rgba(255, 255, 255, 0.12),
			0 0 0 1px rgba(255, 255, 255, 0.18) !important;
		/* Maintain blur on hover - force override */
		backdrop-filter: blur(10px) saturate(150%) brightness(1.02) !important;
		-webkit-backdrop-filter: blur(10px) saturate(150%) brightness(1.02) !important;
	}

	.discipline-card.selected {
		background: rgba(var(--theme-primary-rgb), 0.46);
		border-color: rgba(var(--theme-primary-rgb), 0.45);
		box-shadow: 0 0 0 1px rgba(var(--theme-primary-rgb), 0.2);
		/* Maintain blur on selected - force override */
		backdrop-filter: blur(10px) saturate(150%) brightness(1.02) !important;
		-webkit-backdrop-filter: blur(10px) saturate(150%) brightness(1.02) !important;
	}

	.discipline-icon {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 2.5rem;
		height: 2.5rem;
		border-radius: 12px;
		background: rgba(255, 255, 255, 0.08);
		font-size: 1.25rem;
		flex-shrink: 0;
	}

	.discipline-card-name {
		font-size: 0.95rem;
		font-weight: 600;
	}

	.discipline-card-custom {
		border-style: dashed;
	}

	/* Modal Styles */
	.modal-backdrop {
		position: fixed;
		inset: 0;
		background: var(--theme-modal-backdrop);
		backdrop-filter: var(--theme-modal-backdrop-blur);
		-webkit-backdrop-filter: var(--theme-modal-backdrop-blur);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 1000;
		padding: 1rem;
	}

	.discipline-modal {
		width: 100%;
		max-width: 420px;
		border-radius: 1.5rem;
		border: 1px solid var(--theme-modal-border);
		background: var(--theme-modal-surface);
		box-shadow: var(--theme-modal-shadow);
		padding: 1.5rem;
		display: flex;
		flex-direction: column;
		gap: 1.25rem;
	}

	.modal-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
	}

	.modal-title {
		font-size: 1.25rem;
		font-weight: 700;
		margin: 0;
		color: var(--theme-text);
	}

	.modal-close {
		background: none;
		border: none;
		padding: 0.5rem;
		cursor: pointer;
		border-radius: 0.5rem;
		color: var(--theme-text-muted);
		transition: all 0.2s ease;
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.modal-close:hover {
		background: rgba(255, 255, 255, 0.1);
		color: var(--theme-text);
	}

	.modal-body {
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}

	.modal-description {
		margin: 0;
		color: var(--theme-text-muted);
		font-size: 0.95rem;
	}

	.modal-footer {
		display: flex;
		gap: 0.75rem;
		justify-content: flex-end;
	}

	.modal-footer button {
		min-width: 120px;
		padding: 0.75rem 1.5rem;
		font-size: 0.95rem;
		font-weight: 600;
		border-radius: 0.75rem;
		border: none;
		cursor: pointer;
		transition: all 0.2s ease;
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.secondary-btn {
		background: rgba(255, 255, 255, 0.1);
		color: var(--theme-text-muted);
		border: 1px solid rgba(255, 255, 255, 0.12);
	}

	.secondary-btn:hover {
		background: rgba(255, 255, 255, 0.15);
		color: var(--theme-text);
		border: 1px solid rgba(255, 255, 255, 0.2);
		transform: translateY(-1px);
	}

	.primary-btn {
		background: linear-gradient(135deg, var(--theme-primary), rgba(var(--theme-primary-rgb), 0.8));
		color: white;
		box-shadow: 0 2px 8px rgba(var(--theme-primary-rgb), 0.3);
	}

	.primary-btn:hover {
		background: linear-gradient(135deg, rgba(var(--theme-primary-rgb), 0.9), rgba(var(--theme-primary-rgb), 0.7));
		transform: translateY(-1px);
		box-shadow: 0 4px 12px rgba(var(--theme-primary-rgb), 0.4);
	}

	.primary-btn:disabled {
		background: rgba(255, 255, 255, 0.1);
		color: rgba(255, 255, 255, 0.4);
		cursor: not-allowed;
		box-shadow: none;
		transform: none;
	}

	/* Step 2: Topics */
	.topic-input-row {
		display: flex;
		gap: 0.5rem;
	}

	.topic-input {
		flex: 1;
		padding: 0.75rem 1rem;
		font-size: 0.95rem;
	}

	.add-btn {
		padding: 0.75rem 1.35rem;
		font-size: 0.95rem;
		font-weight: 600;
		min-height: 44px;
		border-radius: 0.75rem;
	}

	.add-btn:disabled {
		opacity: 0.4;
		cursor: not-allowed;
	}

	.import-row {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		margin-top: 1rem;
	}

	.import-btn {
		white-space: nowrap;
		padding: 0.75rem 1.5rem;
		font-size: 0.95rem;
		font-weight: 600;
		min-height: 44px;
		border-radius: 0.75rem;
		display: inline-flex;
		align-items: center;
		gap: 0.5rem;
	}

	.import-hint {
		font-size: 0.8rem;
		color: var(--theme-text-muted);
	}

	.inline-error {
		margin: 0.5rem 0 0;
		padding: 0.5rem 0.75rem;
		background: rgba(233, 69, 96, 0.12);
		border-radius: 8px;
		color: #f07888;
		font-size: 0.85rem;
	}

	.btn-spinner {
		display: inline-flex;
		width: 14px;
		height: 14px;
		aspect-ratio: 1 / 1;
		border: 2px solid rgba(255, 255, 255, 0.35);
		border-right-color: transparent;
		border-radius: 999px;
		box-sizing: border-box;
		animation: spin 0.7s linear infinite;
		vertical-align: middle;
	}

	@keyframes spin { to { transform: rotate(360deg); } }

	@media (max-width: 640px) {
		.discipline-grid {
			grid-template-columns: 1fr;
		}
	}

	.topic-list {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
		margin-top: 1rem;
	}

	.topic-chip {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		padding: 0.4rem 0.8rem;
		background: rgba(var(--theme-primary-rgb), 0.15);
		border: 0.5px solid rgba(var(--theme-primary-rgb), 0.3);
		border-radius: 20px;
		font-size: 0.85rem;
		color: var(--theme-text);
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

	.topic-name {
		min-width: 0;
		line-height: 1.25;
		white-space: normal;
		word-break: break-word;
	}

	.topic-chip.has-syllabus {
		border-color: rgba(var(--theme-primary-rgb), 0.5);
	}

	.topic-number {
		font-weight: 700;
		font-size: 0.75rem;
		color: var(--theme-primary);
		min-width: 16px;
		text-align: center;
	}

	.syllabus-badge {
		font-size: 0.75rem;
		margin-left: auto;
	}

	.chip-remove {
		all: unset;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 20px;
		height: 20px;
		border-radius: 50%;
		background: rgba(255, 255, 255, 0.15);
		color: var(--theme-text-muted);
		font-size: 0.9rem;
		line-height: 1;
		flex-shrink: 0;
		cursor: pointer;
	}

	.chip-remove:hover {
		background: rgba(233, 69, 96, 0.4);
		color: #fff;
	}

	/* Step 3: Syllabus accordion */
	.center-msg {
		text-align: center;
		padding: 2rem 0;
		color: var(--theme-text-muted);
	}

	.center-msg span {
		font-size: 2rem;
	}

	.syllabus-accordion {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.syllabus-item {
		background: rgba(255, 255, 255, 0.04);
		border: 0.5px solid rgba(255, 255, 255, 0.1);
		border-radius: var(--glass-radius-sm, 12px);
		overflow: hidden;
		transition: border-color 0.2s;
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

	.syllabus-item.expanded {
		border-color: rgba(var(--theme-primary-rgb), 0.3);
	}

	.syllabus-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		width: 100%;
		padding: 0.75rem 1rem;
		background: none;
		border: none;
		color: var(--theme-text);
		cursor: pointer;
		font-family: inherit;
		font-size: 0.9rem;
	}

	.syllabus-header:hover {
		background: rgba(255, 255, 255, 0.04);
	}

	.sh-left {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	.sh-number {
		font-weight: 700;
		font-size: 0.8rem;
		color: var(--theme-primary);
		min-width: 20px;
	}

	.sh-name {
		font-weight: 600;
	}

	.sh-right {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	.sh-badge {
		font-size: 0.7rem;
		padding: 0.15rem 0.5rem;
		border-radius: 10px;
		font-weight: 600;
	}

	.sh-badge.filled {
		background: rgba(var(--theme-primary-rgb), 0.2);
		color: var(--theme-primary);
	}

	.sh-badge.empty {
		background: rgba(255, 255, 255, 0.08);
		color: var(--theme-text-muted);
	}

	.sh-arrow {
		font-size: 0.7rem;
		color: var(--theme-text-muted);
	}

	.syllabus-body {
		padding: 0 1rem 1rem;
	}

	.syl-textarea {
		width: 100%;
		padding: 0.75rem;
		font-size: 0.9rem;
		resize: vertical;
		min-height: 120px;
		font-family: inherit;
		line-height: 1.5;
	}

	/* Topic tab styles */
	.topic-ref-tabs {
		display: flex;
		gap: 0;
		margin-top: 1rem;
		border-bottom: 1px solid rgba(255, 255, 255, 0.1);
	}

	.topic-tab {
		flex: 1;
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 0.4rem;
		padding: 0.65rem 0.75rem;
		background: none;
		border: none;
		border-bottom: 2px solid transparent;
		color: var(--theme-text-muted);
		font-size: 0.85rem;
		font-weight: 600;
		cursor: pointer;
		transition: color 0.15s, border-color 0.15s, background 0.15s;
	}

	.topic-tab:hover {
		color: var(--theme-text);
		background: rgba(255, 255, 255, 0.03);
	}

	.topic-tab.active {
		color: var(--theme-primary);
		border-bottom-color: var(--theme-primary);
		background: rgba(var(--theme-primary-rgb), 0.06);
	}

	.tab-count {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		min-width: 18px;
		height: 18px;
		padding: 0 5px;
		border-radius: 9px;
		background: rgba(var(--theme-primary-rgb), 0.2);
		color: var(--theme-primary);
		font-size: 0.7rem;
		font-weight: 700;
		line-height: 1;
	}

	.tab-optional {
		font-size: 0.65rem;
		font-weight: 400;
		color: var(--theme-text-muted);
		opacity: 0.7;
		font-style: italic;
	}

	.topic-tab-content {
		padding: 0.85rem 0 0;
	}

	.step3-footer {
		margin-top: 2rem;
		padding-bottom: 1.6rem;
		margin-bottom: 0.8rem;
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}

	.step3-settings-row {
		display: flex;
		align-items: flex-end;
		gap: 1rem;
		flex-wrap: wrap;
	}

	/* .step3-settings-row .question-count-card {
		flex: 0 0 auto;
	} */

	.step3-settings-row .skip-pdf-btn {
		flex: 1;
		margin-top: 0;
		min-width: 220px;
	}

	/* .question-count-card {
		margin-top: 0.85rem;
		padding: 0.8rem;
		border: 1px solid rgba(var(--theme-primary-rgb), 0.28);
		border-radius: var(--glass-radius);
		background: rgba(var(--theme-primary-rgb), 0.08);
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
	} */


	.success-hint {
		color: #9be4b9 !important;
	}

	.skip-pdf-btn {
		margin-top: 0.85rem;
		width: 100%;
		min-height: 46px;
		padding: 0.78rem 1rem;
		justify-content: center;
		font-size: 1rem;
		font-weight: 700;
		letter-spacing: 0.01em;
		color: var(--theme-text-primary);
		cursor: pointer;
		border-style: solid;
		border-width: 1px;
		border-color: rgba(var(--theme-primary-rgb), 0.42);
		background: linear-gradient(135deg, rgba(var(--theme-primary-rgb), 0.2), rgba(var(--theme-primary-rgb), 0.11));
		box-shadow: 0 10px 20px rgba(var(--theme-primary-rgb), 0.2);
		transition: transform 0.16s ease, border-color 0.16s ease, background 0.16s ease;
	}

	.skip-pdf-btn:hover {
		transform: translateY(-1px);
		border-color: rgba(var(--theme-primary-rgb), 0.62);
		background: linear-gradient(135deg, rgba(var(--theme-primary-rgb), 0.3), rgba(var(--theme-primary-rgb), 0.16));
	}

	.skip-pdf-btn.active {
		background: linear-gradient(135deg, rgba(var(--theme-primary-rgb), 0.36), rgba(var(--theme-primary-rgb), 0.22));
		border-color: rgba(var(--theme-primary-rgb), 0.74);
		color: var(--theme-text);
		box-shadow: 0 10px 22px rgba(var(--theme-primary-rgb), 0.3);
	}

	/* .question-count-row {
		display: flex;
		align-items: center;
		gap: 0.6rem;
	}

	.question-count-input {
		width: 120px;
		padding: 0.55rem 0.7rem;
		font-weight: 700;
		text-align: center;
	}

	.question-count-unit {
		font-size: 0.85rem;
		font-weight: 600;
		color: var(--theme-text);
	} */

	/* Step 4: Review */
	.review-card {
		padding: 1.5rem;
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
		border-radius: var(--glass-radius);
	}

	.review-title {
		font-size: 1.25rem;
		font-weight: 700;
		margin: 0 0 1rem;
		text-align: center;
	}

	.review-sections {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}

	.review-section {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		padding: 0.75rem;
		background: rgba(255, 255, 255, 0.04);
		border-radius: 10px;
	}

	.rs-label {
		font-size: 0.75rem;
		color: var(--theme-text-muted);
		text-transform: uppercase;
		letter-spacing: 0.05em;
		font-weight: 600;
	}

	.rs-value {
		font-size: 0.95rem;
		font-weight: 600;
		color: var(--theme-text);
	}

	.rs-topics {
		display: flex;
		flex-wrap: wrap;
		gap: 0.35rem;
	}

	.rs-topic-chip {
		padding: 0.25rem 0.6rem;
		background: rgba(var(--theme-primary-rgb), 0.12);
		border-radius: 12px;
		font-size: 0.8rem;
		color: var(--theme-text);
	}

	.rs-syl {
		font-size: 0.7rem;
	}

	/* Step 7: Progress */
	.progress-section {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.75rem;
		padding: 2rem 0;
	}

	.progress-icon {
		font-size: 2.5rem;
	}

	.progress-title {
		font-size: 1.25rem;
		font-weight: 700;
		margin: 0;
	}

	.progress-status {
		font-size: 0.9rem;
		color: var(--theme-text-muted);
		margin: 0;
		text-align: center;
	}

	.progress-bar-wrap {
		width: 100%;
		max-width: 320px;
		height: 6px;
		background: rgba(255, 255, 255, 0.1);
		border-radius: 3px;
		overflow: hidden;
	}

	.progress-bar {
		height: 100%;
		background: linear-gradient(90deg, var(--theme-primary), var(--theme-primary-hover));
		border-radius: 3px;
		transition: width 0.5s ease;
	}

	.progress-pct {
		font-size: 0.85rem;
		font-weight: 700;
		color: var(--theme-primary);
	}

	.gen-error {
		margin: 1rem 0 0;
		padding: 0.75rem 1rem;
		background: rgba(233, 69, 96, 0.15);
		border: 0.5px solid rgba(233, 69, 96, 0.3);
		border-radius: 10px;
		color: #f07888;
		font-size: 0.88rem;
		text-align: center;
	}

	.step-actions {
		width: 100%;
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 0.75rem;
		margin-top: auto;
		position: sticky;
		bottom: max(0.5rem, env(safe-area-inset-bottom));
		padding: 0.5rem;
		border-radius: 14px;
		background: rgba(11, 18, 32, 0.5);
		backdrop-filter: blur(6px);
		z-index: 15;
	}

	.step-back-btn {
		padding: 0.75rem 1.15rem;
		font-size: 0.95rem;
	}

	.step-next-btn {
		padding: 0.75rem 1.5rem;
		font-size: 0.95rem;
	}

	.step-next-btn:disabled {
		opacity: 0.35;
		cursor: not-allowed;
		transform: none;
		box-shadow: none;
	}

	.step-train-btn {
		padding: 0.75rem 2rem;
	}

	.review-actions {
		justify-content: space-between;
	}

	@media (max-width: 768px) {
		.modal-backdrop {
			align-items: flex-start;
			padding: max(0.6rem, env(safe-area-inset-top)) 0.6rem
				max(0.75rem, env(safe-area-inset-bottom));
			overflow-y: auto;
		}

		.discipline-modal {
			max-height: calc(100dvh - env(safe-area-inset-top) - env(safe-area-inset-bottom) - 1.25rem);
			margin-top: 0.15rem;
			overflow: auto;
		}

		.modal-backdrop:focus-within .discipline-modal {
			max-height: 56dvh;
		}

		.wizard {
			padding-top: 1rem;
		}

		.step-bar {
			display: none;
		}

		.step-title {
			font-size: 1.35rem;
		}

		.topic-list {
			width: 100%;
			flex-direction: column;
			gap: 0.65rem;
		}

		.topic-chip {
			width: 100%;
			align-items: flex-start;
			padding: 0.7rem 0.85rem;
			border-radius: 14px;
			gap: 0.55rem;
		}

		.topic-number {
			margin-top: 0.12rem;
		}

		.topic-name {
			flex: 1;
			line-height: 1.35;
			white-space: normal;
			word-break: break-word;
		}

		.syllabus-badge {
			margin-top: 0.08rem;
		}

		.chip-remove {
			width: 24px;
			height: 24px;
			font-size: 0.95rem;
			flex-shrink: 0;
			border-radius: 999px;
		}

		.rs-topics {
			display: grid;
			grid-template-columns: 1fr;
			gap: 0.45rem;
		}

		.rs-topic-chip {
			display: block;
			line-height: 1.35;
			padding: 0.45rem 0.65rem;
		}

		/* .question-count-row {
			flex-wrap: wrap;
		}

		.question-count-input {
			width: 100%;
			max-width: 160px;
		} */

		/* Modal mobile styles */
		.modal-backdrop {
			padding-left: 0.5rem;
			padding-right: 0.5rem;
		}

		.discipline-modal {
			max-width: none;
			border-radius: 1.25rem;
			padding: 1.25rem;
		}

		.modal-title {
			font-size: 1.1rem;
		}

		.modal-footer {
			flex-direction: column;
			gap: 0.5rem;
			position: sticky;
			bottom: 0;
			padding-top: 0.5rem;
			background: linear-gradient(180deg, rgba(10, 18, 32, 0), rgba(10, 18, 32, 0.72) 26%, rgba(var(--theme-primary-rgb), 0.18) 100%);
		}

		.modal-footer button {
			width: 100%;
			min-width: unset;
			padding: 0.85rem 1rem;
		}
	}

	/* Per-topic PDF upload styles */
	.topic-section {
		margin-bottom: 1rem;
	}

	.topic-section-label {
		display: block;
		font-weight: 600;
		font-size: 0.9rem;
		color: var(--theme-text-primary, #e2e8f0);
		margin-bottom: 0.5rem;
	}

	.topic-section-hint {
		font-size: 0.8rem;
		color: var(--theme-text-secondary, #94a3b8);
		margin: 0 0 0.5rem 0;
	}

	.topic-upload-status {
		font-size: 0.85rem;
		color: var(--theme-accent, #60a5fa);
		margin: 0.5rem 0 0 0;
	}

	.topic-doc-list {
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
		margin-top: 0.75rem;
	}

	.topic-doc-item {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.5rem 0.75rem;
		background: rgba(255, 255, 255, 0.04);
		border-radius: 8px;
		font-size: 0.85rem;
	}

	.topic-doc-icon {
		flex-shrink: 0;
	}

	.topic-doc-name {
		flex: 1;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		color: var(--theme-text-primary, #e2e8f0);
	}

	.topic-doc-status {
		flex-shrink: 0;
		font-size: 0.75rem;
		padding: 0.2rem 0.5rem;
		border-radius: 4px;
		background: rgba(255, 255, 255, 0.08);
		color: var(--theme-text-secondary, #94a3b8);
	}

	.topic-doc-status.completed {
		background: rgba(34, 197, 94, 0.15);
		color: #22c55e;
	}

	.topic-doc-status.failed {
		background: rgba(239, 68, 68, 0.15);
		color: #ef4444;
	}

	.sh-badge.docs {
		background: rgba(96, 165, 250, 0.15);
		color: #60a5fa;
	}
</style>
