<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
	import { browser } from '$app/environment';
	import { goto } from '$app/navigation';
	import { session } from '$lib/session';
	import FileUploadZone from '$lib/components/FileUploadZone.svelte';
	import { createSubject, createTopic, extractChapters, getSubject, updateTopic, type TopicResponse } from '$lib/api/subjects';
	import { getDocumentStatus, listReferenceDocuments, scheduleBackgroundGeneration, uploadDocument } from '$lib/api/documents';

	const DRAFT_STORAGE_KEY = 'qgen:new-topic-wizard:draft:v1';
	const MIN_QUESTION_COUNT = 1;
	const MAX_QUESTION_COUNT = 100;

	function clampStep(value: number) {
		if (!Number.isFinite(value)) return 1;
		return Math.max(1, Math.min(6, Math.trunc(value)));
	}

	function clampQuestionCount(value: number) {
		if (!Number.isFinite(value)) return 10;
		return Math.max(MIN_QUESTION_COUNT, Math.min(MAX_QUESTION_COUNT, Math.trunc(value)));
	}

	onMount(() => {
		const unsub = session.subscribe((s) => {
			if (!s) goto('/teacher/login');
		});

		void restoreDraftAndResume();
		return unsub;
	});

	// ── Wizard state ──
	let step = $state(1);
	const totalSteps = 6;

	// Step 1: Discipline
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
	interface TopicItem { name: string; syllabusContent: string; }
	let topics = $state<TopicItem[]>([]);
	let topicInput = $state('');
	let topicError = $state('');
	let importingPdf = $state(false);
	let importError = $state('');
	// We need a temp subject to use extractChapters — we'll create it lazily
	let tempSubjectId = $state('');

	// Step 3: Syllabus per topic
	let expandedTopic = $state(0);

	// Step 4: Reference materials
	let materials = $state<File[]>([]);
	let materialDocs = $state<Array<{
		id: string;
		filename: string;
		file_size_bytes: number;
		processing_status: string;
		processing_progress: number;
		processing_step?: string;
		processing_detail?: string;
	}>>([]);
	let uploadingMaterials = $state(false);
	let uploadProgress = $state(0);
	let uploadTotal = $state(0);
	let uploadCurrent = $state(0);
	let materialsStatusError = $state('');
	let materialsStatusMessage = $state('');
	let skipReferencePdf = $state(false);
	let materialPollTimer: ReturnType<typeof setInterval> | null = null;

	// Optional reference questions (shown in Step 4)
	let refQuestions = $state<File[]>([]);
	let refQuestionDocs = $state<Array<{
		id: string;
		filename: string;
		file_size_bytes: number;
		processing_status: string;
		processing_progress: number;
		processing_step?: string;
		processing_detail?: string;
	}>>([]);
	let uploadingRefQuestions = $state(false);
	let refQuestionsStatusError = $state('');
	let refQuestionsStatusMessage = $state('');

	// Step 5/6: Setup & generation
	let isSettingUp = $state(false);
	let setupProgress = $state(0);
	let setupStatus = $state('');
	let setupError = $state('');
	let completeOnlyMode = $state(false);
	let backgroundGenerationScheduled = $state(false);
	let backgroundGenerationMessage = $state('');
	let desiredQuestionCount = $state(10);
	let draftHydrated = $state(false);

	// ── Derived ──
	let canProceed = $derived.by(() => {
		switch (step) {
			case 1: return disciplineName.trim().length > 0;
			case 2: return topics.length > 0;
			case 3: return true; // syllabus is optional per topic
			case 4:
				return (skipReferencePdf || materialDocs.length > 0) &&
					desiredQuestionCount >= MIN_QUESTION_COUNT &&
					desiredQuestionCount <= MAX_QUESTION_COUNT &&
					(skipReferencePdf || materialsFailedCount === 0) &&
					refQuestionsReadyForNext;
			case 5: return true; // review
			case 6: return true;
			default: return false;
		}
	});

	let stepTitle = $derived.by(() => {
		switch (step) {
			case 1: return 'Discipline';
			case 2: return 'Topics';
			case 3: return 'Syllabus Content';
			case 4: return 'References';
			case 5: return 'Review';
			case 6: return 'Setting Up';
			default: return '';
		}
	});

	let topicsWithSyllabus = $derived(topics.filter(t => t.syllabusContent.trim().length > 0).length);
	let materialsProcessingCount = $derived(
		materialDocs.filter((doc) => {
			const status = doc.processing_status.toLowerCase();
			return status === 'pending' || status === 'processing';
		}).length
	);
	let materialsFailedCount = $derived(
		materialDocs.filter((doc) => {
			const status = doc.processing_status.toLowerCase();
			return status === 'failed' || status === 'error';
		}).length
	);
	let materialsReadyForNext = $derived(
		materialDocs.length > 0 && materialsProcessingCount === 0 && materialsFailedCount === 0
	);
	let materialsAverageProgress = $derived.by(() => {
		if (materialDocs.length === 0) return 0;
		const total = materialDocs.reduce((sum, doc) => {
			const status = doc.processing_status.toLowerCase();
			if (status === 'completed' || status === 'complete' || status === 'processed') return sum + 100;
			if (status === 'failed' || status === 'error') return sum + 100;
			return sum + Math.max(0, Math.min(100, doc.processing_progress || 0));
		}, 0);
		return Math.round(total / materialDocs.length);
	});

	let refQuestionsProcessingCount = $derived(
		refQuestionDocs.filter((doc) => {
			const status = doc.processing_status.toLowerCase();
			return status === 'pending' || status === 'processing';
		}).length
	);
	let refQuestionsFailedCount = $derived(
		refQuestionDocs.filter((doc) => {
			const status = doc.processing_status.toLowerCase();
			return status === 'failed' || status === 'error';
		}).length
	);
	let refQuestionsReadyForNext = $derived(
		refQuestionDocs.length === 0 || (refQuestionsProcessingCount === 0 && refQuestionsFailedCount === 0)
	);
	let refQuestionsAverageProgress = $derived.by(() => {
		if (refQuestionDocs.length === 0) return 0;
		const total = refQuestionDocs.reduce((sum, doc) => {
			const status = doc.processing_status.toLowerCase();
			if (status === 'completed' || status === 'complete' || status === 'processed') return sum + 100;
			if (status === 'failed' || status === 'error') return sum + 100;
			return sum + Math.max(0, Math.min(100, doc.processing_progress || 0));
		}, 0);
		return Math.round(total / refQuestionDocs.length);
	});

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
			desiredQuestionCount = clampQuestionCount(parsed.desiredQuestionCount ?? 10);
			skipReferencePdf = parsed.skipReferencePdf ?? false;

			if (tempSubjectId) {
				await refreshMaterialStatuses();
				const hasPending = materialDocs.some((doc) => {
					const status = doc.processing_status.toLowerCase();
					return status === 'pending' || status === 'processing';
				});
				if (hasPending) {
					startMaterialPolling();
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

		topics = [...topics, { name: normalized, syllabusContent: '' }];
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

	function clearMaterialPolling() {
		if (materialPollTimer) {
			clearInterval(materialPollTimer);
			materialPollTimer = null;
		}
	}

	function isSubjectNotFoundError(error: unknown) {
		if (!(error instanceof Error)) return false;
		const msg = error.message.toLowerCase();
		return msg.includes('subject not found') || msg.includes('404') || msg.includes('not found');
	}

	onDestroy(() => {
		clearMaterialPolling();
	});

	async function ensureSubjectId(): Promise<string> {
		if (tempSubjectId) {
			try {
				await getSubject(tempSubjectId);
				return tempSubjectId;
			} catch {
				// Stale/deleted id from draft restore; recreate lazily.
				tempSubjectId = '';
				materialDocs = [];
				refQuestionDocs = [];
				materialsStatusMessage = '';
				refQuestionsStatusMessage = '';
				materialsStatusError = '';
				refQuestionsStatusError = '';
				clearMaterialPolling();
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

	async function refreshMaterialStatuses() {
		if (!tempSubjectId) return;

		const res = await listReferenceDocuments(tempSubjectId);
		const baseDocs = (res.reference_books || []).map((doc) => ({
			id: doc.id,
			filename: doc.filename,
			file_size_bytes: doc.file_size_bytes,
			processing_status: doc.processing_status,
			processing_progress: doc.processing_status.toLowerCase() === 'completed' ? 100 : 0,
			processing_step: '',
			processing_detail: '',
		}));
		const baseRefQuestionDocs = (res.reference_questions || []).map((doc) => ({
			id: doc.id,
			filename: doc.filename,
			file_size_bytes: doc.file_size_bytes,
			processing_status: doc.processing_status,
			processing_progress: doc.processing_status.toLowerCase() === 'completed' ? 100 : 0,
			processing_step: '',
			processing_detail: '',
		}));

		const withStatus = await Promise.all(
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
		const withRefQuestionStatus = await Promise.all(
			baseRefQuestionDocs.map(async (doc) => {
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

		materialDocs = withStatus;
		refQuestionDocs = withRefQuestionStatus;

		const processingCount = materialDocs.filter((doc) => {
			const status = doc.processing_status.toLowerCase();
			return status === 'pending' || status === 'processing';
		}).length;

		const failedCount = materialDocs.filter((doc) => {
			const status = doc.processing_status.toLowerCase();
			return status === 'failed' || status === 'error';
		}).length;

		if (materialDocs.length === 0) {
			materialsStatusMessage = 'Upload at least one reference material.';
		} else if (processingCount > 0) {
			materialsStatusMessage = `${processingCount} file${processingCount > 1 ? 's are' : ' is'} still processing in background...`;
		} else if (failedCount > 0) {
			materialsStatusMessage = `${failedCount} file${failedCount > 1 ? 's failed' : ' failed'}. Re-upload failed files to continue.`;
		} else {
			materialsStatusMessage = 'All reference materials are processed. You can continue.';
		}

		const refProcessingCount = refQuestionDocs.filter((doc) => {
			const status = doc.processing_status.toLowerCase();
			return status === 'pending' || status === 'processing';
		}).length;
		const refFailedCount = refQuestionDocs.filter((doc) => {
			const status = doc.processing_status.toLowerCase();
			return status === 'failed' || status === 'error';
		}).length;

		if (refQuestionDocs.length === 0) {
			refQuestionsStatusMessage = 'Reference questions are optional.';
		} else if (refProcessingCount > 0) {
			refQuestionsStatusMessage = `${refProcessingCount} reference question file${refProcessingCount > 1 ? 's are' : ' is'} still processing...`;
		} else if (refFailedCount > 0) {
			refQuestionsStatusMessage = `${refFailedCount} reference question file${refFailedCount > 1 ? 's failed' : ' failed'}. Re-upload failed files to continue.`;
		} else {
			refQuestionsStatusMessage = 'All reference questions are processed.';
		}

		if (processingCount === 0 && refProcessingCount === 0) {
			clearMaterialPolling();
		}
	}

	function startMaterialPolling() {
		clearMaterialPolling();
		materialPollTimer = setInterval(() => {
			void refreshMaterialStatuses().catch(() => {
				materialsStatusError = 'Failed to refresh material processing status';
			});
		}, 3000);
	}

	async function handleMaterialsSelected(files: File[]) {
		if (!files.length || uploadingMaterials) return;

		uploadingMaterials = true;
		materialsStatusError = '';
		skipReferencePdf = false;
		materials = [...materials, ...files];
		uploadTotal = files.length;
		uploadCurrent = 0;
		uploadProgress = 0;

		try {
			const subjectId = await ensureSubjectId();
			for (let i = 0; i < files.length; i++) {
				uploadCurrent = i + 1;
				uploadProgress = Math.round(((i + 0.5) / files.length) * 100);
				await uploadDocument(files[i], subjectId, 'reference_book');
				uploadProgress = Math.round(((i + 1) / files.length) * 100);
			}
			await refreshMaterialStatuses();
			startMaterialPolling();
		} catch (e: unknown) {
			materialsStatusError = e instanceof Error ? e.message : 'Failed to upload reference materials';
		} finally {
			uploadingMaterials = false;
			uploadProgress = 0;
			uploadTotal = 0;
			uploadCurrent = 0;
		}
	}

	async function handleRefQuestionsSelected(files: File[]) {
		if (!files.length || uploadingRefQuestions) return;

		uploadingRefQuestions = true;
		refQuestionsStatusError = '';
		refQuestions = [...refQuestions, ...files];

		try {
			const subjectId = await ensureSubjectId();
			for (const file of files) {
				await uploadDocument(file, subjectId, 'reference_questions');
			}
			await refreshMaterialStatuses();
			startMaterialPolling();
		} catch (e: unknown) {
			refQuestionsStatusError = e instanceof Error ? e.message : 'Failed to upload reference questions';
		} finally {
			uploadingRefQuestions = false;
		}
	}

	function toggleSkipReferencePdf() {
		skipReferencePdf = !skipReferencePdf;
		materialsStatusError = '';
		if (skipReferencePdf) {
			clearMaterialPolling();
			materialsStatusMessage = 'PDF upload skipped for this subject. You can continue to the next step.';
		} else if (materialDocs.length === 0) {
			materialsStatusMessage = 'Upload at least one reference material.';
		}
	}

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
		setupStatus = completeOnlyMode ? 'Completing setup...' : 'Creating discipline...';

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
			if (tempSubjectId) {
				// Topics from extractChapters are already created — just need to update syllabus content
				try {
					const detail = await getSubject(subjectId);
					for (const t of detail.topics) {
						existingTopicNames.add(t.name);
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
					await createTopic(subjectId, {
						name: topics[i].name,
						order_index: i,
						subject_id: subjectId,
						syllabus_content: topics[i].syllabusContent || undefined,
					});
				}
			}
			setupProgress = 30;

			// 3. Reference materials are uploaded/processed in Step 4 itself.
			setupProgress = 55;

			// 4. Reference questions are uploaded/processed in Step 4 itself.
			setupProgress = 80;

			if (completeOnlyMode) {
				setupStatus = 'Scheduling background generation...';
				const scheduleRes = await scheduleBackgroundGeneration({
					subjectId,
					count: desiredQuestionCount,
					types: 'mcq',
					difficulty: 'medium',
					allowWithoutReference: skipReferencePdf && materialDocs.length === 0,
				});
				backgroundGenerationScheduled = true;
				backgroundGenerationMessage = scheduleRes.message;
			}

			setupProgress = 100;
			setupStatus = completeOnlyMode ? 'Setup completed. Redirecting to dashboard...' : 'Setup complete! Redirecting...';
			await new Promise(r => setTimeout(r, 600));
			clearDraft();
			if (completeOnlyMode || !materialsReadyForNext) {
				goto('/teacher/dashboard');
			} else {
				const noPdfParam = skipReferencePdf && materialDocs.length === 0 ? '&noPdf=1' : '';
				goto(`/teacher/train/loop?subject=${subjectId}&provisional=1&count=${encodeURIComponent(String(desiredQuestionCount))}${noPdfParam}`);
			}
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
		<div class="wizard-progress-pill">{step}/{totalSteps}</div>
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
				<span class="field-label">Discipline Name *</span>
				<div class="discipline-grid" role="list" aria-label="Choose a discipline">
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
								Add Custom Discipline
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

		<!-- Step 3: Syllabus per topic -->
		{:else if step === 3}
			<p class="step-desc">Review and edit syllabus content for each topic</p>
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
									<textarea
										class="glass-input syl-textarea"
										placeholder="Paste or type the syllabus content for this topic..."
										bind:value={topics[i].syllabusContent}
										rows="8"
									></textarea>
								</div>
							{/if}
						</div>
					{/each}
				</div>
				<p class="step-hint">{topicsWithSyllabus} of {topics.length} topics have syllabus content</p>
			{/if}

		<!-- Step 4: References -->
		{:else if step === 4}
			<!-- Reference Materials Section -->
			<div class="upload-section">
				<div class="upload-section-header">
					<h3 class="upload-section-title">📚 Reference Materials</h3>
					<span class="upload-section-badge">{materialDocs.length > 0 ? `${materialDocs.length} file${materialDocs.length !== 1 ? 's' : ''}` : 'Required'}</span>
				</div>
				<p class="upload-section-desc">Upload textbooks, notes, or study materials to generate questions from.</p>
				
				<FileUploadZone
					accept=".pdf,.doc,.docx,.txt,.pptx"
					label="Drop files here or click to browse"
					hint="PDF, Word, PowerPoint, or Text"
					files={materials}
					onfilesSelected={handleMaterialsSelected}
				/>

				{#if uploadingMaterials}
					<div class="upload-progress-card">
						<div class="upload-progress-header">
							<span class="upload-progress-label">📤 Uploading {uploadCurrent} of {uploadTotal}...</span>
							<span class="upload-progress-pct">{uploadProgress}%</span>
						</div>
						<div class="upload-progress-track">
							<div class="upload-progress-fill" style:width="{uploadProgress}%"></div>
						</div>
					</div>
				{/if}

				<button
					type="button"
					class="glass-btn skip-pdf-btn"
					class:active={skipReferencePdf}
					onclick={toggleSkipReferencePdf}
				>
					{#if skipReferencePdf}
						✓ Generate without reference materials
					{:else}
						Generate without reference materials
					{/if}
				</button>

				{#if skipReferencePdf}
					<p class="step-hint success-hint">✓ Will use topic and syllabus content only.</p>
				{:else if materialsStatusMessage && !uploadingMaterials}
					<p class="step-hint">{materialsStatusMessage}</p>
				{/if}
			</div>

			<!-- Reference Questions Section -->
			<div class="upload-section">
				<div class="upload-section-header">
					<h3 class="upload-section-title">📝 Reference Questions</h3>
					<span class="upload-section-badge optional">Optional</span>
				</div>
				<p class="upload-section-desc">Upload past papers or question banks to help match question style.</p>
				
				<FileUploadZone
					accept=".pdf,.doc,.docx,.txt,.csv,.xlsx,.xls"
					label="Drop files here or click to browse"
					hint="PDF, Word, Excel, or CSV"
					files={refQuestions}
					onfilesSelected={handleRefQuestionsSelected}
				/>

				{#if uploadingRefQuestions}
					<p class="step-hint">📤 Uploading reference questions...</p>
				{/if}
				{#if refQuestionsStatusMessage && !uploadingRefQuestions}
					<p class="step-hint">{refQuestionsStatusMessage}</p>
				{/if}
			</div>

			<!-- Generation Settings -->
			<div class="upload-section settings-section">
				<div class="upload-section-header">
					<h3 class="upload-section-title">⚙️ Generation Settings</h3>
				</div>
				<div class="question-count-card">
					<label class="field-label" for="question-count-input">Questions To Generate</label>
					<div class="question-count-row">
						<input
							id="question-count-input"
							class="glass-input question-count-input"
							type="number"
							min={MIN_QUESTION_COUNT}
							max={MAX_QUESTION_COUNT}
							bind:value={desiredQuestionCount}
							oninput={handleQuestionCountInput}
						/>
						<span class="question-count-unit">questions</span>
					</div>
					<p class="question-count-hint">This count will be used when training starts.</p>
				</div>
			</div>

			{#if tempSubjectId}
				<p class="step-hint resume-note">💾 Progress saved. You can leave and return later.</p>
			{/if}
			{#if materialDocs.length > 0 && !materialsReadyForNext}
				<div class="material-progress-wrap">
					<div class="material-progress-head">
						<span>Processing Progress</span>
						<span>{materialsAverageProgress}%</span>
					</div>
					<div class="material-progress-track">
						<div class="material-progress-fill" style:width="{materialsAverageProgress}%"></div>
					</div>
				</div>
			{:else if materialDocs.length > 0 && materialsReadyForNext}
				<div class="material-progress-wrap material-progress-complete">
					<div class="material-progress-head">
						<span>Processing Completed</span>
						<span>100%</span>
					</div>
				</div>
			{/if}
			{#if refQuestionDocs.length > 0 && !refQuestionsReadyForNext}
				<div class="material-progress-wrap">
					<div class="material-progress-head">
						<span>Reference Questions Progress</span>
						<span>{refQuestionsAverageProgress}%</span>
					</div>
					<div class="material-progress-track">
						<div class="material-progress-fill" style:width="{refQuestionsAverageProgress}%"></div>
					</div>
				</div>
			{:else if refQuestionDocs.length > 0 && refQuestionsReadyForNext}
				<div class="material-progress-wrap material-progress-complete">
					<div class="material-progress-head">
						<span>Reference Questions Completed</span>
						<span>100%</span>
					</div>
				</div>
			{/if}
			{#if materialsStatusError}
				<p class="inline-error">⚠️ {materialsStatusError}</p>
			{/if}
			{#if refQuestionsStatusError}
				<p class="inline-error">⚠️ {refQuestionsStatusError}</p>
			{/if}
			{#if materialDocs.length > 0}
				<div class="file-list">
					{#each materialDocs as doc}
						<div class="file-item">
							<span class="file-icon">📁</span>
							<span class="file-name">{doc.filename}</span>
							<span class="file-size">{(doc.file_size_bytes / 1024 / 1024).toFixed(1)} MB</span>
							<span class="file-status">
								{#if ['completed', 'complete', 'processed'].includes(doc.processing_status.toLowerCase())}
									Completed
								{:else if ['failed', 'error'].includes(doc.processing_status.toLowerCase())}
									Failed
								{:else}
									{doc.processing_status} ({doc.processing_progress}%)
								{/if}
							</span>
						</div>
						{#if doc.processing_detail}
							<p class="file-progress-detail">{doc.processing_detail}</p>
						{/if}
					{/each}
				</div>
			{/if}
			{#if refQuestionDocs.length > 0}
				<div class="file-list">
					{#each refQuestionDocs as doc}
						<div class="file-item">
							<span class="file-icon">📝</span>
							<span class="file-name">{doc.filename}</span>
							<span class="file-size">{(doc.file_size_bytes / 1024 / 1024).toFixed(1)} MB</span>
							<span class="file-status">
								{#if ['completed', 'complete', 'processed'].includes(doc.processing_status.toLowerCase())}
									Completed
								{:else if ['failed', 'error'].includes(doc.processing_status.toLowerCase())}
									Failed
								{:else}
									{doc.processing_status} ({doc.processing_progress}%)
								{/if}
							</span>
						</div>
						{#if doc.processing_detail}
							<p class="file-progress-detail">{doc.processing_detail}</p>
						{/if}
					{/each}
				</div>
			{/if}
			{#if refQuestions.length > 0}
				<div class="file-list">
					{#each refQuestions as file, i}
						<div class="file-item">
							<span class="file-icon">📋</span>
							<span class="file-name">{file.name}</span>
							<span class="file-size">{(file.size / 1024 / 1024).toFixed(1)} MB</span>
							<button class="file-remove" onclick={() => refQuestions = refQuestions.filter((_, j) => j !== i)}>×</button>
						</div>
					{/each}
				</div>
			{/if}

		<!-- Step 5: Review -->
		{:else if step === 5}
			<div class="review-card glass">
				<h2 class="review-title">Review Setup</h2>
				{#if skipReferencePdf && materialDocs.length === 0}
					<p class="step-hint">Reference PDF is marked as not required for this subject.</p>
				{:else if completeOnlyMode || !materialsReadyForNext}
					<p class="step-hint">Reference materials are still processing. You can complete setup now and continue from dashboard later.</p>
				{/if}
				{#if !skipReferencePdf && !materialsReadyForNext}
					<p class="step-hint">On Complete, background generation for {desiredQuestionCount} question{desiredQuestionCount !== 1 ? 's' : ''} will run automatically once processing is ready.</p>
				{/if}
				{#if backgroundGenerationMessage}
					<p class="step-hint">{backgroundGenerationMessage}</p>
				{/if}
				<div class="review-sections">
					<div class="review-section">
						<span class="rs-label">Discipline</span>
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
							{#if skipReferencePdf && materialDocs.length === 0}
								Not required for this subject
							{:else}
								{materialDocs.length} file{materialDocs.length !== 1 ? 's' : ''}
							{/if}
						</span>
					</div>
					<div class="review-section">
						<span class="rs-label">Reference Questions</span>
						<span class="rs-value">{refQuestions.length} file{refQuestions.length !== 1 ? 's' : ''}</span>
					</div>
					<div class="review-section">
						<span class="rs-label">Questions To Generate</span>
						<span class="rs-value">{desiredQuestionCount}</span>
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
						<button class="glass-btn step-next-btn step-train-btn" onclick={() => { step = 6; startSetup(!completeOnlyMode && materialsReadyForNext); }}>
							{#if !completeOnlyMode && materialsReadyForNext}
								⚡ Start Training
							{:else}
								✓ Complete
							{/if}
						</button>
					</div>
				{/if}
			</div>

		<!-- Step 6: Setting up -->
		{:else if step === 6}
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
					<button class="glass-btn" onclick={() => { step = 5; }}>← Back to Review</button>
				{/if}
			</div>
		{/if}
	</div>

	{#if step >= 2 && step <= 4}
		<div class="step-actions">
			<button class="glass-btn step-back-btn" onclick={prevStep}>← Back</button>
			{#if step === 2}
				<button class="glass-btn step-next-btn" onclick={nextStep} disabled={!canProceed}>Next: Add Content →</button>
			{:else if step === 3}
				<button class="glass-btn step-next-btn" onclick={nextStep}>Next: Add References →</button>
			{:else if step === 4}
				<button class="glass-btn step-next-btn" onclick={nextStep} disabled={!canProceed}>Next: Review →</button>
			{:else}
				<button class="glass-btn step-next-btn" onclick={nextStep}>Next: Review →</button>
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
				<h3 class="modal-title">Add Custom Discipline</h3>
				<button class="modal-close" onclick={closeCustomDisciplineModal} aria-label="Close">
					<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
						<line x1="18" y1="6" x2="6" y2="18"></line>
						<line x1="6" y1="6" x2="18" y2="18"></line>
					</svg>
				</button>
			</div>

			<!-- Content -->
			<div class="modal-body">
				<p class="modal-description">Enter the name of your custom discipline</p>
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
					Add Discipline
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

	.wizard-progress-pill {
		min-width: 4.75rem;
		padding: 0.8rem 1rem;
		border-radius: 999px;
		background: rgba(255, 255, 255, 0.12);
		border: 1px solid rgba(255, 255, 255, 0.12);
		color: var(--theme-text);
		font-size: 0.95rem;
		font-weight: 700;
		text-align: center;
	}

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
		background: rgba(255, 255, 255, 0.2);
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
		background: rgba(255, 255, 255, 0.15);
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

	/* Step 4/5: File list */
	.file-list {
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
		margin-top: 1rem;
	}

	.file-item {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.5rem 0.75rem;
		border-radius: var(--glass-radius-sm, 8px);
		background: rgba(255, 255, 255, 0.04);
		border: 0.5px solid rgba(255, 255, 255, 0.08);
		font-size: 0.85rem;
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

	.file-icon {
		font-size: 1rem;
	}

	.file-name {
		flex: 1;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		color: var(--theme-text);
	}

	.file-size {
		color: var(--theme-text-muted);
		font-size: 0.75rem;
		flex-shrink: 0;
	}

	.file-remove {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 20px;
		height: 20px;
		border: none;
		border-radius: 50%;
		background: rgba(255, 255, 255, 0.1);
		color: var(--theme-text-muted);
		font-size: 0.85rem;
		cursor: pointer;
		padding: 0;
		flex-shrink: 0;
	}

	.file-remove:hover {
		background: rgba(233, 69, 96, 0.35);
		color: #fff;
	}

	.file-status {
		font-size: 0.75rem;
		color: var(--theme-text-muted);
		text-transform: capitalize;
		flex-shrink: 0;
	}

	.file-progress-detail {
		margin: -0.2rem 0 0.35rem 2.2rem;
		font-size: 0.75rem;
		color: var(--theme-text-muted);
	}

	.material-progress-wrap {
		margin-top: 0.85rem;
		padding: 0.75rem;
		border: 1px solid rgba(255, 255, 255, 0.12);
		border-radius: 10px;
		background: rgba(255, 255, 255, 0.05);
	}

	.material-progress-head {
		display: flex;
		justify-content: space-between;
		align-items: center;
		font-size: 0.8rem;
		color: var(--theme-text-muted);
		margin-bottom: 0.4rem;
	}

	.material-progress-track {
		height: 7px;
		border-radius: 999px;
		background: rgba(255, 255, 255, 0.1);
		overflow: hidden;
	}

	.material-progress-fill {
		height: 100%;
		background: linear-gradient(90deg, var(--theme-primary), var(--theme-primary-hover));
		transition: width 0.3s ease;
	}

	.material-progress-complete {
		border-color: rgba(95, 212, 152, 0.35);
		background: rgba(95, 212, 152, 0.08);
	}

	.material-progress-complete .material-progress-head {
		margin-bottom: 0;
		color: #9be4b9;
		font-weight: 600;
	}

	.question-count-card {
		margin-top: 0.85rem;
		padding: 0.8rem;
		border: 1px solid rgba(var(--theme-primary-rgb), 0.28);
		border-radius: var(--glass-radius);
		background: rgba(var(--theme-primary-rgb), 0.08);
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

	/* Upload section styles */
	.upload-section {
		margin-bottom: 1.5rem;
		padding: 1rem;
		border-radius: var(--glass-radius);
		background: rgba(255, 255, 255, 0.03);
		border: 1px solid rgba(255, 255, 255, 0.08);
	}

	.upload-section-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		margin-bottom: 0.5rem;
	}

	.upload-section-title {
		font-size: 1rem;
		font-weight: 700;
		margin: 0;
		color: var(--theme-text);
	}

	.upload-section-badge {
		font-size: 0.7rem;
		font-weight: 600;
		padding: 0.2rem 0.6rem;
		border-radius: 12px;
		background: rgba(var(--theme-primary-rgb), 0.2);
		color: var(--theme-primary);
		text-transform: uppercase;
		letter-spacing: 0.03em;
	}

	.upload-section-badge.optional {
		background: rgba(255, 255, 255, 0.1);
		color: var(--theme-text-muted);
	}

	.upload-section-desc {
		font-size: 0.85rem;
		color: var(--theme-text-muted);
		margin: 0 0 0.75rem;
	}

	.settings-section {
		background: rgba(var(--theme-primary-rgb), 0.05);
		border-color: rgba(var(--theme-primary-rgb), 0.15);
	}

	.settings-section .question-count-card {
		margin-top: 0;
		padding: 0;
		border: none;
		background: none;
		box-shadow: none !important;
	}

	/* Upload progress card */
	.upload-progress-card {
		margin-top: 0.75rem;
		padding: 0.75rem 1rem;
		border-radius: 10px;
		background: rgba(var(--theme-primary-rgb), 0.1);
		border: 1px solid rgba(var(--theme-primary-rgb), 0.25);
	}

	.upload-progress-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 0.5rem;
	}

	.upload-progress-label {
		font-size: 0.85rem;
		font-weight: 600;
		color: var(--theme-text);
	}

	.upload-progress-pct {
		font-size: 0.85rem;
		font-weight: 700;
		color: var(--theme-primary);
	}

	.upload-progress-track {
		height: 6px;
		border-radius: 3px;
		background: rgba(255, 255, 255, 0.1);
		overflow: hidden;
	}

	.upload-progress-fill {
		height: 100%;
		background: linear-gradient(90deg, var(--theme-primary), var(--theme-primary-hover));
		border-radius: 3px;
		transition: width 0.3s ease;
	}

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
		cursor: pointer;
		border-style: solid;
		border-width: 1px;
		border-color: rgba(255, 255, 255, 0.32);
		background: linear-gradient(135deg, rgba(255, 255, 255, 0.12), rgba(255, 255, 255, 0.06));
		box-shadow: 0 10px 20px rgba(0, 0, 0, 0.16);
		transition: transform 0.16s ease, border-color 0.16s ease, background 0.16s ease;
	}

	.skip-pdf-btn:hover {
		transform: translateY(-1px);
		border-color: rgba(var(--theme-primary-rgb), 0.55);
		background: linear-gradient(135deg, rgba(var(--theme-primary-rgb), 0.18), rgba(255, 255, 255, 0.08));
	}

	.skip-pdf-btn.active {
		background: linear-gradient(135deg, rgba(95, 212, 152, 0.28), rgba(95, 212, 152, 0.14));
		border-color: rgba(95, 212, 152, 0.62);
		color: #d8ffe9;
		box-shadow: 0 10px 22px rgba(51, 153, 105, 0.22);
	}

	.question-count-row {
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
	}

	.question-count-hint {
		margin: 0.5rem 0 0;
		font-size: 0.78rem;
		color: var(--theme-text-muted);
	}

	/* Step 6: Review */
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

		.question-count-row {
			flex-wrap: wrap;
		}

		.question-count-input {
			width: 100%;
			max-width: 160px;
		}

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
</style>
