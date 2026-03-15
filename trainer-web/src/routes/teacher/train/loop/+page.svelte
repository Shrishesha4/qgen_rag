<script lang="ts">
	import { onMount, onDestroy, tick } from 'svelte';
	import { goto, beforeNavigate } from '$app/navigation';
	import { page } from '$app/stores';
	import { session } from '$lib/session';
	import VoiceRecorder from '$lib/components/VoiceRecorder.svelte';
	import {
		getQuestionsForVetting,
		submitVetting,
		rejectWithFeedback,
		type QuestionForVetting,
	} from '$lib/api/vetting';
	import {
		generateFromSubject,
		generateChapter,
		cancelGeneration,
		listReferenceDocuments,
		scheduleBackgroundGeneration,
		type GenerationEvent,
	} from '$lib/api/documents';
	import { deleteSubject, getSubject, type SubjectDetailResponse } from '$lib/api/subjects';

	const READY_DOC_STATUSES = new Set(['completed', 'complete', 'processed', 'ready', 'indexed']);
	const FAILED_DOC_STATUSES = new Set(['failed', 'error']);
	const WAIT_POLL_MS = 1500;
	const WAIT_DOCS_TIMEOUT_MS = 3 * 60 * 1000;
	const DEFAULT_BATCH_SIZE = 10;
	const MIN_BATCH_SIZE = 5;
	const MAX_BATCH_SIZE = 100;

	function parseBatchSizeParam(raw: string | null) {
		if (raw == null || raw.trim() === '') return DEFAULT_BATCH_SIZE;
		const parsed = Number(raw);
		if (!Number.isFinite(parsed) || parsed <= 0) return DEFAULT_BATCH_SIZE;
		return Math.max(MIN_BATCH_SIZE, Math.min(MAX_BATCH_SIZE, Math.trunc(parsed)));
	}

	let subjectId = $state('');
	let topicId = $state('');
	let mixedTopicsMode = $state(false);
	let provisionalSubject = $state(false);
	let firstQuestionGenerated = $state(false);
	let generationBatchSize = $state(DEFAULT_BATCH_SIZE);

	// Confirm + cleanup before any SvelteKit navigation
	beforeNavigate(({ cancel, to }) => {
		const isActive = generating || submitting || (totalReviewed > 0 && !batchComplete);
		if (isActive) {
			const msg = generating
				? 'Generation is still running. Leave and stop generation?'
				: 'You have unsaved vetting progress. Leave and discard?';
			if (!confirm(msg)) {
				cancel();
				return;
			}
			// User confirmed — stop generation cleanly
			stopBackgroundGen();
		}
	});

	onMount(() => {
		const unsub = session.subscribe((s) => {
			if (!s) goto('/teacher/login');
		});
		const unsubPage = page.subscribe((p) => {
			const nextSubjectId = p.url.searchParams.get('subject') ?? '';
			const nextTopicId = p.url.searchParams.get('topic') ?? '';
			const nextMixedTopicsMode = p.url.searchParams.get('mode') === 'mixed-topics';
			const nextProvisionalSubject = p.url.searchParams.get('provisional') === '1';
			const nextGenerationBatchSize = parseBatchSizeParam(p.url.searchParams.get('count'));

			if (nextSubjectId !== subjectId || nextMixedTopicsMode !== mixedTopicsMode || nextProvisionalSubject !== provisionalSubject) {
				topicCycleIds = [];
				topicCycleCursor = 0;
				subjectDetail = null;
				genCtx = '';
				firstQuestionGenerated = false;
			}

			subjectId = nextSubjectId;
			topicId = nextTopicId;
			mixedTopicsMode = nextMixedTopicsMode;
			provisionalSubject = nextProvisionalSubject;
			generationBatchSize = nextGenerationBatchSize;
		});
		loadAndStream();

		// Block browser reload / tab close during active work
		function handleBeforeUnload(e: BeforeUnloadEvent) {
			if (generating || submitting || (totalReviewed > 0 && !batchComplete)) {
				e.preventDefault();
				stopBackgroundGen();
			}
		}
		window.addEventListener('beforeunload', handleBeforeUnload);

		return () => {
			unsub();
			unsubPage();
			window.removeEventListener('beforeunload', handleBeforeUnload);
			stopBackgroundGen();
		};
	});

	// Core state
	let questions = $state<QuestionForVetting[]>([]);
	let loading = $state(true);
	let error = $state('');
	let currentIndex = $state(0);
	let approved = $state<Set<string>>(new Set());
	let rejected = $state<Set<string>>(new Set());
	let submitting = $state(false);
	let regenerating = $state(false);

	// Background generation
	let generating = $state(false);
	let genAbortController = $state<AbortController | null>(null);
	let genCount = $state(0);
	let genMessage = $state('');
	let docProcessingProgress = $state<number | null>(null);
	let docProcessingStep = $state('');
	let docProcessingDetail = $state('');
	let docProcessingDocument = $state('');
	let docProcessingDocumentsTotal = $state(0);
	let batchComplete = $state(false);
	let showBatchCompleteNotice = $state(false);
	let subjectDetail = $state<SubjectDetailResponse | null>(null);
	let genCtx = $state('');
	let nextGenAt = $state(0); // totalReviewed count that triggers next batch (0 = disarmed)
	let topicCycleIds = $state<string[]>([]);
	let topicCycleCursor = $state(0);

	// Trigger next generation when user has vetted ≥70% of current questions
	$effect(() => {
		if (batchComplete || generating || regenerating || voiceAction?.kind === 'reject' || !subjectId) return;
		if (nextGenAt === 0) return;
		if (totalReviewed >= nextGenAt) {
			nextGenAt = 0; // disarm before async to prevent double-trigger
			void doNextBatch();
		}
	});

	// Edit mode
	let editing = $state(false);
	let editText = $state('');
	let editOptions = $state<string[]>([]);
	let editAnswer = $state('');
	let editExplanation = $state('');
	let optionInputRefs = $state<Array<HTMLInputElement | null>>([]);
	let activeOptionEditIndex = $state<number | null>(null);
	type ApprovalDifficulty = 'easy' | 'medium' | 'hard';
	type PendingVoiceAction = { kind: 'approve'; level: ApprovalDifficulty } | { kind: 'reject' };

	// Source references
	let showSources = $state(false);
	let selectedOptionIndex = $state<number | null>(null);
	let showAnswerModal = $state(false);
	let handingOffGeneration = $state(false);

	let voiceAction = $state<PendingVoiceAction | null>(null);

	let currentQuestion = $derived(questions[currentIndex]);
	let totalReviewed = $derived(approved.size + rejected.size);
	let progressPct = $derived(questions.length > 0 ? Math.round((totalReviewed / questions.length) * 100) : 0);
	let isReviewed = $derived(
		currentQuestion ? approved.has(currentQuestion.id) || rejected.has(currentQuestion.id) : false
	);
	let showAllCaughtUp = $derived(questions.length > 0 && batchComplete && totalReviewed >= questions.length);
	let showBatchCompletePanel = $derived(showBatchCompleteNotice || showAllCaughtUp);
	let voiceRecorderTitle = $derived.by(() => {
		if (!voiceAction) return '';
		if (voiceAction.kind === 'reject') return 'Reject Question';
		return `Grade as ${voiceAction.level[0].toUpperCase()}${voiceAction.level.slice(1)}`;
	});
	let voiceRecorderAccent = $derived.by(() => {
		if (!voiceAction) return 'blue';
		if (voiceAction.kind === 'reject') return 'rose';
		return voiceAction.level === 'easy' ? 'emerald' : voiceAction.level === 'medium' ? 'amber' : 'rose';
	});
	let voiceRecorderSubmitLabel = $derived(voiceAction?.kind === 'reject' ? 'Reject & Regenerate' : 'Approve & Next');

	// Load existing pending questions, then start background generation
	async function loadAndStream() {
		loading = true;
		error = '';
		showBatchCompleteNotice = false;
		try {
			const res = await getQuestionsForVetting({
				status: 'pending',
				subject_id: subjectId || undefined,
				topic_id: topicId || undefined,
				limit: 100,
			});
			questions = res.questions;
			currentIndex = 0;
			approved = new Set();
			rejected = new Set();
			if (questions.length > 0) {
				firstQuestionGenerated = true;
				provisionalSubject = false;
			}
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to load questions';
		} finally {
			loading = false;
		}

		// Start or arm generation
		if (subjectId && !batchComplete) {
			if (questions.length === 0) {
				// No pending questions — generate first batch immediately
				startBackgroundGeneration();
			} else {
				// Existing questions — wait until 70% are vetted before generating more
				armNextGen();
			}
		}
	}

	async function startBackgroundGeneration() {
		if (generating || batchComplete || !subjectId) return;
		generating = true;
		genCount = 0;
		genMessage = 'Checking document readiness...';
		resetDocumentProcessingState();

		try {
			await ensureDocumentsReadyForGeneration();

			if (!subjectDetail) {
				try { subjectDetail = await getSubject(subjectId); } catch { /* ignore */ }
			}
			genCtx = subjectDetail
				? `${subjectDetail.name}: ${subjectDetail.topics.map(t => t.name).join(', ')}`
				: 'General questions';

			if (mixedTopicsMode && !topicId) {
				await generateMixedTopicBatch(genCtx, generationBatchSize);
			} else {
				await generateBatch(genCtx, generationBatchSize, topicId || undefined);
			}

			// Arm threshold: next batch triggers when 70% of current questions are vetted
			if (!batchComplete) armNextGen();
		} catch (e: unknown) {
			await rollbackProvisionalSubjectIfNeeded();
			if (!batchComplete) {
				error = e instanceof Error ? e.message : 'Generation failed';
			}
		} finally {
			generating = false;
			genMessage = '';
		}
	}

	async function generateBatch(ctx: string, count: number, forTopicId?: string) {
		const abort = new AbortController();
		genAbortController = abort;
		try {
			const gen = forTopicId
				? generateChapter({
						topicId: forTopicId,
						count,
						types: 'mcq',
						difficulty: 'medium',
						signal: abort.signal,
				  })
				: generateFromSubject({
						subjectId,
						context: ctx,
						count,
						types: 'mcq',
						difficulty: 'medium',
						signal: abort.signal,
				  });
			for await (const evt of gen) {
				// Hard stop — aborted externally
				if (batchComplete) break;

				if (evt.status === 'error') {
					throw new Error(evt.message || 'Generation failed');
				}
				applyGenerationEvent(evt);
				if (evt.message) genMessage = evt.message;
				if (evt.question) {
					resetDocumentProcessingState();
					genCount++;
					firstQuestionGenerated = true;
					provisionalSubject = false;
					// genMessage = `Generated ${genCount} question${genCount > 1 ? 's' : ''} in background...`;
					const q = evt.question as unknown as QuestionForVetting;
					if (q && q.id) {
						questions = [...questions, q];
					}
				}
				if (evt.status === 'complete') {
					genCount = evt.questions_generated ?? genCount;
					resetDocumentProcessingState();
					break;
				}
			}
		} catch (e: unknown) {
			// Ignore AbortError — that's us cancelling intentionally
			if (e instanceof Error && e.name === 'AbortError') return;
			throw e;
		} finally {
			genAbortController = null;
		}
	}

	async function ensureTopicCycleIds(): Promise<string[]> {
		if (topicCycleIds.length > 0) return topicCycleIds;
		if (!subjectDetail && subjectId) {
			try {
				subjectDetail = await getSubject(subjectId);
			} catch {
				return [];
			}
		}

		const topicIds = (subjectDetail?.topics ?? []).map((topic) => topic.id);
		topicCycleIds = topicIds;
		return topicIds;
	}

	async function generateMixedTopicBatch(ctx: string, count: number) {
		const topicIds = await ensureTopicCycleIds();
		if (topicIds.length === 0) {
			await generateBatch(ctx, count, undefined);
			return;
		}

		let remaining = count;
		while (remaining > 0 && !batchComplete) {
			const topicIdForQuestion = topicIds[topicCycleCursor % topicIds.length];
			topicCycleCursor = (topicCycleCursor + 1) % topicIds.length;
			await generateBatch(ctx, 1, topicIdForQuestion);
			remaining -= 1;
		}
	}

	function armNextGen() {
		nextGenAt = Math.max(1, Math.floor(questions.length * 0.7));
	}

	async function doNextBatch() {
		if (generating || batchComplete || !subjectId) return;
		generating = true;
		genMessage = 'Checking document readiness...';
		resetDocumentProcessingState();
		try {
			await ensureDocumentsReadyForGeneration();

			if (!genCtx) {
				if (!subjectDetail) {
					try { subjectDetail = await getSubject(subjectId); } catch { /* ignore */ }
				}
				genCtx = subjectDetail
					? `${subjectDetail.name}: ${subjectDetail.topics.map(t => t.name).join(', ')}`
					: 'General questions';
			}
			if (mixedTopicsMode && !topicId) {
				await generateMixedTopicBatch(genCtx, generationBatchSize);
			} else {
				await generateBatch(genCtx, generationBatchSize, topicId || undefined);
			}
			if (!batchComplete) armNextGen();
		} catch (e: unknown) {
			await rollbackProvisionalSubjectIfNeeded();
			if (!batchComplete) {
				error = e instanceof Error ? e.message : 'Generation failed';
			}
		} finally {
			generating = false;
			genMessage = '';
		}
	}

	function stopBackgroundGen() {
		batchComplete = true;
		genAbortController?.abort();
		genAbortController = null;
		resetDocumentProcessingState();
		if (subjectId) cancelGeneration(subjectId);
	}

	async function rollbackProvisionalSubjectIfNeeded() {
		if (!subjectId || !provisionalSubject || firstQuestionGenerated) return;
		try {
			await deleteSubject(subjectId);
		} catch {
			// Ignore rollback failure and preserve original generation error
		}
	}

	function sleep(ms: number) {
		return new Promise((resolve) => setTimeout(resolve, ms));
	}

	async function ensureDocumentsReadyForGeneration() {
		if (!subjectId) return;

		const startedAt = Date.now();
		while (!batchComplete && Date.now() - startedAt < WAIT_DOCS_TIMEOUT_MS) {
			const refs = await listReferenceDocuments(subjectId);
			const docs = [
				...(refs.reference_books ?? []),
				...(refs.reference_questions ?? []),
				...(refs.template_papers ?? []),
			];

			if (docs.length === 0) {
				genMessage = 'Waiting for uploaded documents...';
				docProcessingStep = 'waiting';
				docProcessingDetail = 'No subject documents found yet.';
				docProcessingDocument = '';
				docProcessingDocumentsTotal = 0;
				docProcessingProgress = 0;
				await sleep(WAIT_POLL_MS);
				continue;
			}

			const processedCount = docs.filter((doc) => READY_DOC_STATUSES.has((doc.processing_status || '').toLowerCase())).length;
			const failedCount = docs.filter((doc) => FAILED_DOC_STATUSES.has((doc.processing_status || '').toLowerCase())).length;

			if (processedCount > 0) {
				resetDocumentProcessingState();
				return;
			}

			if (failedCount === docs.length) {
				throw new Error('All uploaded documents failed processing. Please re-upload a PDF and try again.');
			}

			const elapsed = Date.now() - startedAt;
			docProcessingDocumentsTotal = docs.length;
			docProcessingStep = 'processing';
			docProcessingDetail = `Processing ${docs.length} document(s)...`;
			docProcessingDocument = docs.length === 1 ? docs[0].filename : '';
			docProcessingProgress = Math.min(95, Math.max(5, Math.round((elapsed / WAIT_DOCS_TIMEOUT_MS) * 100)));
			genMessage = 'Waiting for document processing to complete...';
			await sleep(WAIT_POLL_MS);
		}

		throw new Error('Documents are still processing. Please wait a moment and retry generation.');
	}

	function completeBatch() {
		stopBackgroundGen();
		generating = false;
		genMessage = '';
		showBatchCompleteNotice = true;
	}

	function resetDocumentProcessingState() {
		docProcessingProgress = null;
		docProcessingStep = '';
		docProcessingDetail = '';
		docProcessingDocument = '';
		docProcessingDocumentsTotal = 0;
	}

	function applyGenerationEvent(evt: GenerationEvent) {
		if (evt.status !== 'processing' && evt.processing_progress === undefined) {
			return;
		}

		docProcessingProgress = evt.processing_progress ?? Math.max(0, evt.progress ?? 0);
		docProcessingStep = evt.processing_step ?? '';
		docProcessingDetail = evt.processing_detail ?? evt.message ?? '';
		docProcessingDocument = evt.processing_document ?? '';
		docProcessingDocumentsTotal = evt.processing_documents_total ?? 0;
	}

	function replaceCurrentQuestion(replacement: QuestionForVetting) {
		questions = questions.map((question, index) => (index === currentIndex ? replacement : question));
		showSources = false;
		editing = false;
		selectedOptionIndex = null;
		showAnswerModal = false;
		activeOptionEditIndex = null;
	}

	function getOptionIdentifier(option: string, index: number): string {
		return option.trim().match(/^([A-Z])[).:\s]/)?.[1]?.toUpperCase() ?? String.fromCharCode(65 + index);
	}

	function getOptionEditableText(option: string, index: number): string {
		const identifier = getOptionIdentifier(option, index);
		return option.trim().replace(new RegExp(`^${identifier}[).:\\s]+`, 'i'), '').trim();
	}

	function updateOptionText(index: number, text: string) {
		const identifier = getOptionIdentifier(editOptions[index] ?? '', index);
		editOptions[index] = text.trim().length > 0 ? `${identifier}) ${text}` : `${identifier})`;
		editOptions = [...editOptions];
	}

	async function enableOptionEditing(index: number) {
		activeOptionEditIndex = index;
		await tick();
		optionInputRefs[index]?.focus();
		optionInputRefs[index]?.select();
	}

	function disableOptionEditing(index: number) {
		if (activeOptionEditIndex === index) {
			activeOptionEditIndex = null;
		}
	}

	function selectCorrectOption(index: number) {
		editAnswer = getOptionIdentifier(editOptions[index], index);
	}

	function normalizeCorrectAnswer(answer: string | null | undefined, options: string[] = []): string {
		const value = answer?.trim();
		if (!value) return '';
		const label = value.match(/^([A-Z])[).:\s]?$/i)?.[1]?.toUpperCase();
		if (label) return label;

		const matchedIndex = options.findIndex((option, index) => {
			const normalizedOption = option.trim();
			const optionLabel = getOptionIdentifier(option, index);
			const optionText = normalizedOption.replace(/^[A-Z][).:\s]+/i, '').trim();
			return (
				normalizedOption.toLowerCase() === value.toLowerCase() ||
				optionText.toLowerCase() === value.toLowerCase() ||
				optionLabel === value.toUpperCase()
			);
		});

		return matchedIndex >= 0 ? getOptionIdentifier(options[matchedIndex], matchedIndex) : value.toUpperCase();
	}

	// Edit mode
	function startEdit() {
		if (!currentQuestion) return;
		editing = true;
		editText = currentQuestion.question_text;
		editOptions = currentQuestion.options ? [...currentQuestion.options] : [];
		optionInputRefs = [];
		activeOptionEditIndex = null;
		editAnswer = normalizeCorrectAnswer(currentQuestion.correct_answer, editOptions);
		editExplanation = currentQuestion.explanation ?? '';
	}

	function cancelEdit() {
		editing = false;
		activeOptionEditIndex = null;
	}

	async function submitEdit() {
		if (!currentQuestion || submitting) return;
		submitting = true;
		try {
			const normalizedAnswer = normalizeCorrectAnswer(editAnswer, editOptions);
			const originalAnswer = normalizeCorrectAnswer(currentQuestion.correct_answer, currentQuestion.options ?? []);
			await submitVetting({
				question_id: currentQuestion.id,
				decision: 'edit',
				edited_text: editText !== currentQuestion.question_text ? editText : undefined,
				edited_options: JSON.stringify(editOptions) !== JSON.stringify(currentQuestion.options) ? editOptions : undefined,
				edited_answer: normalizedAnswer !== originalAnswer ? normalizedAnswer : undefined,
				edited_explanation: editExplanation !== currentQuestion.explanation ? editExplanation : undefined,
			});
			approved = new Set([...approved, currentQuestion.id]);
			editing = false;
			activeOptionEditIndex = null;
			advance();
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to submit edit';
		} finally {
			submitting = false;
		}
	}

	function openApprovalRecorder(level: ApprovalDifficulty) {
		if (!currentQuestion || submitting) return;
		voiceAction = { kind: 'approve', level };
	}

	function openRejectRecorder() {
		if (!currentQuestion || submitting) return;
		voiceAction = { kind: 'reject' };
	}

	function closeVoiceRecorder() {
		if (submitting) return;
		voiceAction = null;
	}

	async function submitApproval(level: ApprovalDifficulty, transcript: string) {
		if (!currentQuestion || submitting) return;
		submitting = true;
		error = '';
		try {
			await submitVetting({
				question_id: currentQuestion.id,
				decision: 'approve',
				approved_difficulty: level,
				feedback: transcript,
				notes: transcript,
			});
			questions = questions.map((question, index) =>
				index === currentIndex ? { ...question, difficulty_level: level } : question
			);
			approved = new Set([...approved, currentQuestion.id]);
			voiceAction = null;
			advance();
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to submit';
		} finally {
			submitting = false;
		}
	}

	async function submitRejection(transcript: string) {
		if (!currentQuestion || submitting) return;
		const questionToReplace = currentQuestion;
		submitting = true;
		error = '';
		voiceAction = null;
		regenerating = true;
		try {
			const res = await rejectWithFeedback(questionToReplace.id, {
				feedback: transcript,
			});

			if (res.improved) {
				replaceCurrentQuestion({
					...questionToReplace,
					question_text: res.improved_text ?? questionToReplace.question_text,
					options: res.improved_options ?? questionToReplace.options,
					correct_answer: res.improved_answer ?? questionToReplace.correct_answer,
					explanation: res.improved_explanation ?? questionToReplace.explanation,
				});
				return;
			}

			if (res.regenerated && res.new_question) {
				replaceCurrentQuestion(res.new_question);
				return;
			}

			rejected = new Set([...rejected, questionToReplace.id]);
			advance();
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to submit rejection';
		} finally {
			submitting = false;
			regenerating = false;
		}
	}

	async function handleVoiceRecorderSubmit(transcript: string) {
		if (!voiceAction) return;
		const action = voiceAction;
		if (action.kind === 'reject') {
			await submitRejection(transcript);
			return;
		}
		await submitApproval(action.level, transcript);
	}

	function formatRelativeTime(iso: string): string {
		const timestamp = new Date(iso).getTime();
		if (!Number.isFinite(timestamp)) return 'just now';
		const diff = Date.now() - timestamp;
		const mins = Math.floor(diff / 60000);
		if (mins < 1) return 'just now';
		if (mins < 60) return `${mins} min ago`;
		const hrs = Math.floor(mins / 60);
		if (hrs < 24) return `${hrs} hours ago`;
		return `${Math.floor(hrs / 24)} days ago`;
	}

	function advance() {
		showSources = false;
		editing = false;
		selectedOptionIndex = null;
		showAnswerModal = false;
		voiceAction = null;
		// Find next unreviewed question
		for (let i = currentIndex + 1; i < questions.length; i++) {
			if (!approved.has(questions[i].id) && !rejected.has(questions[i].id)) {
				currentIndex = i;
				return;
			}
		}
		// If no unreviewed after current, try from start
		for (let i = 0; i < currentIndex; i++) {
			if (!approved.has(questions[i].id) && !rejected.has(questions[i].id)) {
				currentIndex = i;
				return;
			}
		}
		// All reviewed
		if (currentIndex < questions.length - 1) {
			currentIndex++;
		}
	}

	function finish() {
		stopBackgroundGen();
		goto('/teacher/dashboard');
	}

	function isCorrectOption(opt: string, correctAnswer: string | null): boolean {
		return normalizeCorrectAnswer(correctAnswer, currentQuestion?.options ?? []) === normalizeCorrectAnswer(opt, [opt]);
	}

	function selectOption(index: number) {
		selectedOptionIndex = selectedOptionIndex === index ? null : index;
	}

	function openAnswerModal() {
		if (selectedOptionIndex === null) return;
		showAnswerModal = true;
	}

	function closeAnswerModal() {
		showAnswerModal = false;
	}

	function selectedOptionIsCorrect(): boolean {
		if (!currentQuestion?.options || selectedOptionIndex === null) return false;
		const selectedOpt = currentQuestion.options[selectedOptionIndex];
		return isCorrectOption(selectedOpt, currentQuestion.correct_answer);
	}

	async function continueGenerationInBackground() {
		if (!subjectId || handingOffGeneration) return;
		handingOffGeneration = true;
		error = '';
		try {
			stopBackgroundGen();
			await scheduleBackgroundGeneration({
				subjectId,
				count: generationBatchSize,
				types: 'mcq',
				difficulty: 'medium',
			});
			goto('/teacher/dashboard');
		} catch (e: unknown) {
			batchComplete = false;
			error = e instanceof Error ? e.message : 'Failed to move generation to background';
		} finally {
			handingOffGeneration = false;
		}
	}
</script>

<svelte:head>
	<title>Training Loop — VQuest Trainer</title>
</svelte:head>

<div class="loop-page">
	<div class="loop-hero animate-fade-in">
		<div class="hero-copy">
			<h1 class="hero-title font-serif">Question Vetting</h1>
		</div>
		{#if questions.length > 0}
			<div class="progress-pill">
				<span class="progress-pill-count">{currentIndex + 1}/{questions.length}</span>
				<div class="progress-pill-track">
					<div class="progress-pill-fill" style:width="{progressPct}%"></div>
				</div>
			</div>
		{/if}
	</div>

	{#if loading}
		<div class="center-state">
			<div class="spinner"></div>
			<p>Loading questions…</p>
		</div>
	{:else if error && questions.length === 0}
		<div class="center-state">
			<span class="err-icon">⚠️</span>
			<p class="err-msg">{error}</p>
			<button class="glass-btn" onclick={loadAndStream}>Retry</button>
		</div>
	{:else if questions.length === 0 && generating}
		<div class="center-state">
			<div class="spinner"></div>
			<p>{genMessage || 'Generating questions…'}</p>
			{#if docProcessingProgress !== null}
				<div class="gen-progress-card standalone">
					<div class="gen-progress-head">
						<!-- <span class="gen-progress-label">{docProcessingDocument || 'Document processing'}</span> -->
						<!-- <span class="gen-progress-value">{docProcessingProgress}%</span> -->
					</div>
					<div class="gen-progress-track">
						<div class="gen-progress-fill" style:width="{docProcessingProgress}%"></div>
					</div>
					{#if docProcessingDetail}
						<!-- <p class="gen-progress-detail">{docProcessingDetail}</p> -->
					{/if}
				</div>
			{/if}
			<p class="sub-text">Please Wait...</p>
			<button class="glass-btn secondary-btn" onclick={continueGenerationInBackground} disabled={handingOffGeneration}>
				{handingOffGeneration ? 'Switching…' : 'Generate In Background'}
			</button>
		</div>
	{:else if questions.length === 0}
		<div class="empty-state">
			<span class="empty-icon">📭</span>
			<p>No questions to review</p>
			{#if subjectId}
				<p class="sub-text">Generate a new batch of questions from this subject's documents</p>
				<button class="glass-btn" onclick={startBackgroundGeneration}>🔄 Generate Questions</button>
			{:else}
				<p class="sub-text">Generate questions first using the new topic wizard</p>
			{/if}
			<button class="glass-btn secondary-btn" onclick={() => goto('/teacher/dashboard')}>
				Back to Home
			</button>
		</div>
	{:else if showBatchCompletePanel}
		<div class="caught-up-panel glass-panel animate-fade-in">
			<span class="caught-up-kicker">Batch complete</span>
			<h2 class="caught-up-title font-serif">All Caught Up</h2>
			<p class="caught-up-copy">You finished reviewing this batch and paused generation for now.</p>
			<div class="caught-up-stats">
				<div class="caught-up-stat">
					<span class="caught-up-value">{approved.size}</span>
					<span class="caught-up-label">Approved</span>
				</div>
				<div class="caught-up-stat">
					<span class="caught-up-value">{rejected.size}</span>
					<span class="caught-up-label">Rejected</span>
				</div>
			</div>
			<div class="caught-up-actions">
				<button class="glass-btn finish-btn" onclick={finish}>Back to dashboard</button>
			</div>
		</div>
	{:else}
	{#if generating}
		<div class="gen-progress-card hero-status">
			<div class="gen-indicator">
				<div class="gen-dot"></div>
				<span class="gen-text">{genMessage || 'Generating...'}</span>
			</div>
			{#if docProcessingProgress !== null}
				<div class="gen-progress-head">
					<span class="gen-progress-label">
						{docProcessingDocument || 'Document processing'}
						{#if docProcessingDocumentsTotal > 1}
							({docProcessingDocumentsTotal} docs)
						{/if}
					</span>
					<span class="gen-progress-value">{docProcessingProgress}%</span>
				</div>
				<div class="gen-progress-track">
					<div class="gen-progress-fill" style:width="{docProcessingProgress}%"></div>
				</div>
				{#if docProcessingDetail}
					<p class="gen-progress-detail">{docProcessingDetail}</p>
				{/if}
			{/if}
			<div class="gen-background-action">
				<button class="glass-btn secondary-btn" onclick={continueGenerationInBackground} disabled={handingOffGeneration}>
					{handingOffGeneration ? 'Switching…' : 'Generate In Background'}
				</button>
			</div>
		</div>
	{/if}

	{#if error}
		<div class="err-banner">
			<span class="err-msg">{error}</span>
			<button class="err-dismiss" onclick={() => error = ''}>✕</button>
		</div>
	{/if}

	{#if currentQuestion}
		{#if regenerating}
			<div class="regen-overlay glass-panel animate-fade-in">
				<div class="regen-spinner"></div>
				<p class="regen-text">Regenerating question with your feedback…</p>
			</div>
		{/if}
		<!-- Question card -->
		<div class="question-card glass-panel animate-scale-in" class:hidden-during-regen={regenerating}>
			<div class="q-context">
				{#if currentQuestion.subject_name}
					<span class="q-pill">{currentQuestion.subject_name}</span>
				{/if}
				{#if currentQuestion.teacher_name}
					<span class="q-meta-inline">{currentQuestion.teacher_name}</span>
				{/if}
				<span class="q-meta-inline">{formatRelativeTime(currentQuestion.generated_at)}</span>
			</div>

			{#if currentQuestion.topic_name}
				<p class="q-topic-label">{currentQuestion.topic_name}</p>
			{/if}

			{#if editing}
				<!-- Edit mode -->
				<div class="edit-section">
					<span class="edit-label">Question Text</span>
					<textarea class="edit-textarea" bind:value={editText} rows="3"></textarea>

					{#if editOptions.length > 0}
						<span class="edit-label">Options</span>
						{#each editOptions as opt, i}
							<div class="edit-option-row">
								<button
									type="button"
									class="opt-correct-btn"
									class:active={editAnswer === getOptionIdentifier(editOptions[i], i)}
									onclick={() => selectCorrectOption(i)}
									title="Mark as correct"
								>✓</button>
								<button
									type="button"
									class="edit-option-field"
									class:selected={editAnswer === getOptionIdentifier(editOptions[i], i)}
									onclick={() => selectCorrectOption(i)}
									aria-label={`Select option ${getOptionIdentifier(editOptions[i], i)}`}
								>
									<span class="edit-option-prefix">{getOptionIdentifier(editOptions[i], i)})</span>
									<input
										class="edit-input edit-option-input"
										class:is-editing={activeOptionEditIndex === i}
										value={getOptionEditableText(editOptions[i], i)}
										readonly={activeOptionEditIndex !== i}
										onclick={(e) => {
											if (activeOptionEditIndex !== i) {
												e.preventDefault();
												selectCorrectOption(i);
											}
										}}
										onfocus={(e) => {
											if (activeOptionEditIndex !== i) {
												e.currentTarget.blur();
											}
										}}
										oninput={(e) => updateOptionText(i, (e.currentTarget as HTMLInputElement).value)}
										onblur={() => disableOptionEditing(i)}
										bind:this={optionInputRefs[i]}
									/>
								</button>
								<button
									type="button"
									class="edit-option-pencil"
									onclick={() => enableOptionEditing(i)}
									aria-label="Edit option text"
									title="Edit option text"
								>
									<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
										<path d="M12 20h9"></path>
										<path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"></path>
									</svg>
								</button>
							</div>
						{/each}
					{/if}

					<span class="edit-label">Correct Answer</span>
					<input class="edit-input" bind:value={editAnswer} maxlength="1" oninput={() => editAnswer = normalizeCorrectAnswer(editAnswer, editOptions)} />

					<span class="edit-label">Explanation</span>
					<textarea class="edit-textarea" bind:value={editExplanation} rows="4"></textarea>

					<div class="edit-actions">
						<button class="edit-footer-btn edit-cancel-btn" onclick={cancelEdit}>Cancel</button>
						<button class="edit-footer-btn edit-save-btn" onclick={submitEdit} disabled={submitting}>
							{submitting ? 'Saving...' : 'Save'}
						</button>
					</div>
				</div>
			{:else}
				<!-- View mode -->
				<p class="q-text font-serif">{currentQuestion.question_text}</p>

				{#if currentQuestion.options}
					<div class="answer-panel glass-panel">
						<div class="answer-panel-head">
							<span class="answer-panel-title">Answer Options</span>
						</div>
						<div class="options">
						{#each currentQuestion.options as opt, idx}
							<button class="option selectable" class:selected={selectedOptionIndex === idx} onclick={() => selectOption(idx)}>
								<span class="opt-marker">{getOptionIdentifier(opt, idx)}</span>
								<span>{opt}</span>
							</button>
						{/each}
						</div>
						{#if selectedOptionIndex !== null}
							<div class="answer-check-actions">
								<button class="glass-btn check-answer-btn" onclick={openAnswerModal}>
									Check Answer
								</button>
							</div>
						{/if}
					</div>
				{/if}

				<!-- Source References -->
				{#if currentQuestion.source_info?.sources?.length}
					<button class="sources-toggle" onclick={() => showSources = !showSources}>
						📚 {showSources ? 'Hide' : 'Show'} Sources ({currentQuestion.source_info.sources.length})
					</button>

					{#if showSources}
						<div class="sources-section">
							{#if currentQuestion.source_info.generation_reasoning}
								<p class="source-reasoning">{currentQuestion.source_info.generation_reasoning}</p>
							{/if}
							{#each currentQuestion.source_info.sources as src}
								<div class="source-card">
									{#if src.document_name}
										<div class="source-doc">
											📄 {src.document_name}
											{#if src.page_number}
												<span class="source-page">p. {src.page_number}</span>
											{:else if src.page_range}
												<span class="source-page">pp. {src.page_range[0]}–{src.page_range[1]}</span>
											{/if}
										</div>
									{/if}
									{#if src.section_heading}
										<div class="source-heading">§ {src.section_heading}</div>
									{/if}
									{#if src.highlighted_phrase}
										<p class="source-highlight">"{src.highlighted_phrase}"</p>
									{:else if src.content_snippet}
										<p class="source-snippet">{src.content_snippet}</p>
									{/if}
									{#if src.relevance_reason}
										<p class="source-reason">{src.relevance_reason}</p>
									{/if}
								</div>
							{/each}
						</div>
					{/if}
				{/if}
			{/if}
		</div>

	{:else}
		<div class="empty-state">
			<span class="empty-icon">📭</span>
			<p>No questions to review in this batch</p>
			{#if subjectId}
				<button class="glass-btn" onclick={startBackgroundGeneration}>🔄 Generate Questions</button>
			{/if}
			<button class="glass-btn secondary-btn" onclick={() => goto('/teacher/dashboard')}>
				Back to Home
			</button>
		</div>
	{/if}
	{/if}
</div>

{#if showAnswerModal && currentQuestion}
	<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
	<div class="answer-modal-overlay" onclick={closeAnswerModal} role="button" tabindex="0" aria-label="Close answer">
		<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
		<div class="answer-modal glass-panel" onclick={(e) => e.stopPropagation()} role="dialog" aria-modal="true" tabindex="-1">
			<div class="answer-modal-head">
				<h3>Answer Check</h3>
				<button class="answer-modal-close" onclick={closeAnswerModal} aria-label="Close">✕</button>
			</div>
			{#if currentQuestion.options && selectedOptionIndex !== null}
				<p class="answer-result" class:correct={selectedOptionIsCorrect()} class:wrong={!selectedOptionIsCorrect()}>
					{selectedOptionIsCorrect() ? 'Correct selection' : 'Incorrect selection'}
				</p>
				<p class="answer-chosen">Your choice: {currentQuestion.options[selectedOptionIndex]}</p>
			{/if}
			{#if currentQuestion.correct_answer}
				<div class="answer-box">
					<span class="answer-label">Correct Answer</span>
					<span class="answer-text">{currentQuestion.correct_answer}</span>
				</div>
			{/if}
			{#if currentQuestion.explanation}
				<div class="explanation">
					<span class="expl-label">Explanation</span>
					<p class="expl-text">{currentQuestion.explanation}</p>
				</div>
			{/if}
		</div>
	</div>
{/if}

{#if questions.length > 0 && !showBatchCompletePanel}
	<div class="floating-stack">
		{#if !isReviewed && !editing && !regenerating}
			<!-- <div class="edit-inline-row">
				<button class="edit-inline-btn" onclick={startEdit}>Edit question</button>
			</div> -->
			<div class="grading-grid">
				<button class="glass-panel grade-card easy" onclick={() => openApprovalRecorder('easy')} disabled={submitting}>
					<span class="grade-badge">E</span>
					<span class="grade-label">Easy</span>
				</button>
				<button class="glass-panel grade-card medium" onclick={() => openApprovalRecorder('medium')} disabled={submitting}>
					<span class="grade-badge">M</span>
					<span class="grade-label">Medium</span>
				</button>
				<button class="glass-panel grade-card hard" onclick={() => openApprovalRecorder('hard')} disabled={submitting}>
					<span class="grade-badge">H</span>
					<span class="grade-label">Hard</span>
				</button>
				<button class="glass-panel grade-card reject" onclick={openRejectRecorder} disabled={submitting}>
					<span class="grade-badge">×</span>
					<span class="grade-label">Reject</span>
				</button>
			</div>
		{:else if isReviewed && currentIndex < questions.length - 1}
			<div class="actions actions-single">
				<!-- <button class="glass-btn next-question-btn" onclick={() => { advance(); }}>
					Next Question →
				</button> -->
				<h2>Generating</h2>
			</div>
		{/if}

		{#if !editing && !generating && !batchComplete && subjectId}
			<button class="complete-batch-fab" onclick={completeBatch}>
				✓ Complete Batch
			</button>
		{/if}
	</div>
{/if}

{#if voiceAction}
	<VoiceRecorder
		title={voiceRecorderTitle}
		accent={voiceRecorderAccent}
		submitLabel={voiceRecorderSubmitLabel}
		onSubmit={handleVoiceRecorderSubmit}
		onCancel={closeVoiceRecorder}
	/>
{/if}

<style>
	.loop-page {
		max-width: 600px;
		margin: 0 auto;
		padding: 2rem 1.5rem 10rem;
		display: flex;
		flex-direction: column;
		gap: 1.5rem;
		padding-bottom: 12rem;
	}

	/* Question card */
	.question-card {
		padding: 1.5rem;
	}

	.q-text {
		font-size: 1.25rem;
		line-height: 1.2;
		color: var(--theme-text);
		margin: 0 0 1.25rem;
		font-weight: 500;
	}

	/* Options */
	.options {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.option {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		padding: 0.6rem 0.8rem;
		background: rgba(255, 255, 255, 0.04);
		border-radius: 10px;
		font-size: 0.9rem;
		color: var(--theme-text);
		transition: background 0.15s;
	}

	.option.selectable {
		cursor: pointer;
		border: 0.5px solid transparent;
	}

	.option.selectable.selected {
		background: rgba(var(--theme-primary-rgb), 0.2);
		border-color: rgba(var(--theme-primary-rgb), 0.45);
	}

	.opt-marker {
		width: 20px;
		text-align: center;
		font-weight: 700;
		flex-shrink: 0;
	}

	.answer-check-actions {
		margin-top: 0.85rem;
		display: flex;
		justify-content: flex-end;
	}

	.answer-modal-overlay {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.55);
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 1rem;
		z-index: 1200;
	}

	.answer-modal {
		width: min(520px, 100%);
		padding: 1rem;
		border-radius: 14px;
		display: flex;
		flex-direction: column;
		gap: 0.6rem;
	}

	.answer-modal-head {
		display: flex;
		justify-content: space-between;
		align-items: center;
	}

	.answer-modal-head h3 {
		margin: 0;
		font-size: 1rem;
	}

	.answer-modal-close {
		border: none;
		background: rgba(255, 255, 255, 0.1);
		color: var(--theme-text);
		width: 28px;
		height: 28px;
		border-radius: 999px;
		cursor: pointer;
	}

	.answer-result {
		margin: 0;
		font-weight: 700;
	}

	.answer-result.correct {
		color: #48c050;
	}

	.answer-result.wrong {
		color: #f59aa8;
	}

	.answer-chosen {
		margin: 0;
		font-size: 0.9rem;
	}

	/* Answer box */
	.answer-box {
		padding: 0.75rem 1rem;
		background: rgba(72, 192, 80, 0.1);
		border-radius: 10px;
		border: 0.5px solid rgba(72, 192, 80, 0.2);
	}

	.answer-label {
		font-size: 0.75rem;
		font-weight: 600;
		color: var(--theme-text-muted);
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}

	.answer-text {
		display: block;
		margin-top: 0.25rem;
		font-weight: 600;
		color: var(--theme-text);
	}

	/* Explanation */
	.explanation {
		margin-top: 1rem;
		padding: 0.75rem 1rem;
		background: rgba(255, 255, 255, 0.04);
		border-radius: 10px;
		border-left: 3px solid rgba(var(--theme-primary-rgb), 0.4);
	}

	.expl-label {
		font-size: 0.7rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: var(--theme-text-muted);
	}

	.expl-text {
		margin: 0.3rem 0 0;
		font-size: 0.88rem;
		line-height: 1.5;
		color: var(--theme-text-muted);
	}

	/* Actions */
	.floating-stack {
		position: fixed;
		left: 50%;
		bottom: 1rem;
		transform: translateX(-50%);
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.75rem;
		z-index: 100;
		width: min(calc(100vw - 2rem), 640px);
		pointer-events: none;
	}

	.actions {
		display: flex;
		gap: 1rem;
		justify-content: center;
		padding: 0.75rem 1rem;
		background: rgba(20, 20, 30, 0.8);
		backdrop-filter: blur(12px);
		-webkit-backdrop-filter: blur(12px);
		border-radius: 12px;
		border: 1px solid rgba(255, 255, 255, 0.08);
		pointer-events: auto;
		width: fit-content;
	}

	.actions-single {
		width: auto;
	}

	/* .next-question-btn {
		padding: 0.75rem 2rem;
	} */

	/* Finish */
	.complete-batch-fab {
		pointer-events: auto;
		padding: 0.85rem 1.5rem;
		border: 1px solid rgba(72, 192, 80, 0.4);
		border-radius: 999px;
		background: rgba(72, 192, 80, 0.3);
		color: #6ee87a;
		font-size: 0.95rem;
		font-weight: 700;
		cursor: pointer;
		backdrop-filter: blur(12px);
		-webkit-backdrop-filter: blur(12px);
		transition: all 0.2s ease;
		font-family: inherit;
	}

	.complete-batch-fab:hover {
		background: rgba(72, 192, 80, 0.45);
		transform: translateY(-2px);
		box-shadow: 0 4px 16px rgba(72, 192, 80, 0.2);
	}


	.finish-btn {
		padding: 0.85rem 2.5rem;
		font-size: 1rem;
	}

	.caught-up-panel {
		padding: 2rem 1.5rem;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 1rem;
		text-align: center;
	}

	.caught-up-kicker {
		font-size: 0.75rem;
		font-weight: 700;
		letter-spacing: 0.16em;
		text-transform: uppercase;
		color: rgba(110, 232, 122, 0.82);
	}

	.caught-up-title {
		margin: 0;
		font-size: clamp(2.1rem, 6vw, 3.25rem);
		color: var(--theme-text);
	}

	.caught-up-copy {
		margin: 0;
		max-width: 30rem;
		font-size: 0.98rem;
		line-height: 1.6;
		color: var(--theme-text-muted);
	}

	.caught-up-stats {
		width: 100%;
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 0.85rem;
	}

	.caught-up-stat {
		padding: 1rem;
		border-radius: 1rem;
		background: rgba(255, 255, 255, 0.05);
		border: 1px solid rgba(255, 255, 255, 0.08);
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
	}

	.caught-up-value {
		font-size: 1.8rem;
		font-weight: 700;
		color: var(--theme-text);
	}

	.caught-up-label {
		font-size: 0.82rem;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: var(--theme-text-muted);
	}

	.caught-up-actions {
		display: flex;
		justify-content: center;
		width: 100%;
	}

	/* Edit mode */
	.edit-section {
		display: flex;
		flex-direction: column;
		gap: 0.6rem;
	}

	.edit-label {
		font-size: 0.75rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: var(--theme-text-muted);
		margin-top: 0.25rem;
	}

	.edit-textarea {
		width: 100%;
		padding: 0.6rem 0.8rem;
		background: rgba(255, 255, 255, 0.06);
		border: 1px solid rgba(255, 255, 255, 0.12);
		border-radius: 8px;
		color: var(--theme-text);
		font-family: inherit;
		font-size: 0.92rem;
		line-height: 1.5;
		resize: vertical;
	}

	.edit-textarea:focus {
		outline: none;
		border-color: var(--theme-primary);
		box-shadow: 0 0 0 2px rgba(var(--theme-primary-rgb), 0.15);
	}

	.edit-input {
		width: 100%;
		padding: 0.5rem 0.8rem;
		background: rgba(255, 255, 255, 0.06);
		border: 1px solid rgba(255, 255, 255, 0.12);
		border-radius: 8px;
		color: var(--theme-text);
		font-family: inherit;
		font-size: 0.92rem;
	}

	.edit-input:focus {
		outline: none;
		border-color: var(--theme-primary);
		box-shadow: 0 0 0 2px rgba(var(--theme-primary-rgb), 0.15);
	}

	.edit-option-row {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	.edit-option-field {
		flex: 1;
		display: flex;
		align-items: center;
		gap: 0.65rem;
		padding: 0.5rem 0.8rem;
		background: rgba(255, 255, 255, 0.06);
		border: 1px solid rgba(255, 255, 255, 0.12);
		border-radius: 8px;
		cursor: pointer;
		transition: all 0.15s ease;
	}

	.edit-option-field:hover {
		background: rgba(255, 255, 255, 0.1);
	}

	.edit-option-field.selected {
		border-color: rgba(72, 192, 80, 0.45);
		background: rgba(72, 192, 80, 0.1);
	}

	.edit-option-row .edit-input {
		flex: 1;
	}

	.edit-option-prefix {
		min-width: 2rem;
		font-size: 0.9rem;
		font-weight: 700;
		color: var(--theme-text-muted);
		text-align: center;
	}

	.edit-option-input {
		padding: 0;
		background: transparent;
		border: none;
		border-radius: 0;
		cursor: pointer;
		box-shadow: none;
	}

	.edit-option-input[readonly] {
		pointer-events: none;
		caret-color: transparent;
	}

	.edit-option-input.is-editing {
		cursor: text;
		pointer-events: auto;
		caret-color: auto;
	}

	.edit-option-input:focus {
		outline: none;
		box-shadow: none;
	}

	.opt-correct-btn {
		min-width: 40px;
		height: 32px;
		flex-shrink: 0;
		padding: 0 0.75rem;
		border-radius: 999px;
		border: 1.5px solid rgba(255, 255, 255, 0.15);
		background: rgba(255, 255, 255, 0.04);
		color: var(--theme-text-muted);
		font-size: 0.85rem;
		font-weight: 700;
		cursor: pointer;
		transition: all 0.15s;
		display: flex;
		align-items: center;
		justify-content: center;
		font-family: inherit;
	}

	.opt-correct-btn.active {
		background: rgba(72, 192, 80, 0.3);
		border-color: rgba(72, 192, 80, 0.6);
		color: #6ee87a;
	}

	.edit-option-pencil {
		width: 34px;
		height: 34px;
		flex-shrink: 0;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: 10px;
		border: 1px solid rgba(56, 178, 230, 0.3);
		background: rgba(56, 178, 230, 0.12);
		color: #86e0f7;
		cursor: pointer;
		transition: all 0.2s ease;
	}

	.edit-option-pencil:hover {
		background: rgba(56, 178, 230, 0.22);
		transform: translateY(-1px);
	}

	.edit-actions {
		display: flex;
		gap: 0.75rem;
		justify-content: flex-end;
		margin-top: 0.5rem;
	}

	.edit-footer-btn {
		min-width: 120px;
		padding: 0.85rem 1.4rem;
		border-radius: 16px;
		border: 1px solid transparent;
		font-size: 0.98rem;
		font-weight: 700;
		cursor: pointer;
		transition: all 0.2s ease;
		font-family: inherit;
	}

	.edit-footer-btn:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}

	.edit-cancel-btn {
		background: rgba(233, 69, 96, 0.3);
		border-color: rgba(233, 69, 96, 0.4);
		color: #f4c7cf;
	}

	.edit-cancel-btn:hover {
		background: rgba(233, 69, 96, 0.42);
	}

	.edit-save-btn {
		background: rgba(56, 178, 230, 0.3);
		border-color: rgba(56, 178, 230, 0.45);
		color: #86e0f7;
	}

	.edit-save-btn:hover {
		background: rgba(56, 178, 230, 0.42);
		transform: translateY(-1px);
		box-shadow: 0 4px 16px rgba(56, 178, 230, 0.2);
	}

	@media (max-width: 768px) {
		.loop-page {
			padding: 1.25rem 1rem 11.5rem;
		}

		.caught-up-stats {
			grid-template-columns: 1fr;
		}

		.floating-stack {
			width: calc(100vw - 1rem);
		}

		.actions {
			gap: 0.75rem;
			padding: 0.65rem 0.75rem;
			width: calc(100vw - 2rem);
		}

		.edit-option-row {
			gap: 0.4rem;
		}

		.edit-option-prefix {
			min-width: 1.7rem;
		}

		.complete-batch-fab {
			width: calc(100vw - 2rem);
		}

		.edit-actions {
			justify-content: stretch;
		}

		.edit-footer-btn {
			flex: 1;
		}
	}

	/* Source references */
	.sources-toggle {
		margin-top: 1rem;
		padding: 0.5rem 0.8rem;
		background: rgba(255, 255, 255, 0.04);
		border: 1px solid rgba(255, 255, 255, 0.08);
		border-radius: 8px;
		color: var(--theme-text-muted);
		font-size: 0.82rem;
		cursor: pointer;
		transition: all 0.15s;
		font-family: inherit;
		width: 100%;
		text-align: left;
	}

	.sources-toggle:hover {
		background: rgba(255, 255, 255, 0.08);
	}

	.sources-section {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		margin-top: 0.5rem;
	}

	.source-reasoning {
		font-size: 0.82rem;
		color: var(--theme-text-muted);
		font-style: italic;
		margin: 0 0 0.25rem;
		line-height: 1.4;
	}

	.source-card {
		padding: 0.6rem 0.8rem;
		background: rgba(255, 255, 255, 0.03);
		border: 1px solid rgba(255, 255, 255, 0.06);
		border-radius: 8px;
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		overflow: hidden;
		word-break: break-word;
	}

	.source-doc {
		font-size: 0.82rem;
		font-weight: 600;
		color: var(--theme-text);
		display: flex;
		align-items: baseline;
		gap: 0.4rem;
		flex-wrap: wrap;
		word-break: break-all;
	}

	.source-page {
		font-size: 0.75rem;
		color: var(--theme-text-muted);
		font-weight: 400;
	}

	.source-heading {
		font-size: 0.8rem;
		color: var(--theme-primary);
		font-weight: 500;
	}

	.source-highlight {
		font-size: 0.82rem;
		color: #f0c060;
		font-style: italic;
		margin: 0;
		line-height: 1.4;
		overflow-wrap: break-word;
	}

	.source-snippet {
		font-size: 0.8rem;
		color: var(--theme-text-muted);
		margin: 0;
		line-height: 1.4;
		overflow-wrap: break-word;
	}

	.source-reason {
		font-size: 0.75rem;
		color: var(--theme-text-muted);
		opacity: 0.7;
		margin: 0;
	}

	/* Generation progress */
	.gen-indicator {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.4rem 0;
	}

	.gen-progress-card {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		padding: 0.75rem 0.9rem;
		border: 1px solid rgba(255, 255, 255, 0.08);
		border-radius: 12px;
		background: rgba(255, 255, 255, 0.04);
	}

	.gen-progress-card.standalone {
		width: min(100%, 420px);
	}

	.gen-progress-head {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 0.75rem;
	}

	.gen-progress-label,
	.gen-progress-value {
		font-size: 0.78rem;
		color: var(--theme-text-muted);
	}

	.gen-progress-label {
		font-weight: 600;
		word-break: break-word;
	}

	.gen-progress-value {
		font-variant-numeric: tabular-nums;
	}

	.gen-progress-track {
		width: 100%;
		height: 6px;
		background: rgba(255, 255, 255, 0.08);
		border-radius: 999px;
		overflow: hidden;
	}

	.gen-progress-fill {
		height: 100%;
		background: linear-gradient(90deg, rgba(var(--theme-primary-rgb), 0.55), var(--theme-primary));
		border-radius: inherit;
		transition: width 0.3s ease;
	}

	.gen-progress-detail {
		margin: 0;
		font-size: 0.78rem;
		line-height: 1.45;
		color: var(--theme-text-muted);
	}

	.gen-dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		background: var(--theme-primary);
		animation: pulse 1.5s ease-in-out infinite;
	}

	@keyframes pulse {
		0%, 100% { opacity: 0.4; transform: scale(0.8); }
		50% { opacity: 1; transform: scale(1.2); }
	}

	.gen-text {
		font-size: 0.78rem;
		color: var(--theme-text-muted);
		flex: 1;
	}

	/* Error banner */
	.err-banner {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.5rem 0.75rem;
		background: rgba(233, 69, 96, 0.15);
		border: 1px solid rgba(233, 69, 96, 0.25);
		border-radius: 8px;
	}

	.err-banner .err-msg {
		flex: 1;
		font-size: 0.82rem;
	}

	.err-dismiss {
		background: none;
		border: none;
		color: var(--theme-text-muted);
		cursor: pointer;
		font-size: 1rem;
		padding: 0.2rem;
		font-family: inherit;
	}

	/* Center state */
	.center-state {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.75rem;
		padding: 4rem 1rem;
		text-align: center;
	}

	.center-state p {
		color: var(--theme-text-muted);
		margin: 0;
	}

	.sub-text {
		font-size: 0.85rem;
		color: var(--theme-text-muted);
		opacity: 0.7;
		margin: 0;
	}

	.secondary-btn {
		opacity: 0.6;
		font-size: 0.88rem;
	}

	.secondary-btn:hover {
		opacity: 0.85;
	}

	.err-icon {
		font-size: 2rem;
	}

	.err-msg {
		color: #f07888;
	}

	/* Spinner */
	.spinner {
		width: 32px;
		height: 32px;
		border: 3px solid rgba(255, 255, 255, 0.1);
		border-top-color: var(--theme-primary);
		border-radius: 50%;
		animation: spin 0.7s linear infinite;
	}

	@keyframes spin {
		to { transform: rotate(360deg); }
	}

	/* Empty */
	.empty-state {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 1rem;
		padding: 4rem 1rem;
		text-align: center;
	}

	.empty-icon {
		font-size: 3rem;
	}

	.empty-state p {
		color: var(--theme-text-muted);
		margin: 0;
	}

	.regen-overlay {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 1rem;
		padding: 3rem 2rem;
		border-radius: 2rem;
		text-align: center;
	}

	.regen-spinner {
		width: 36px;
		height: 36px;
		border: 3px solid rgba(255, 255, 255, 0.1);
		border-top-color: var(--theme-primary);
		border-radius: 50%;
		animation: spin 0.7s linear infinite;
	}

	.regen-text {
		margin: 0;
		font-size: 0.95rem;
		color: var(--theme-text-muted);
	}

	.hidden-during-regen {
		display: none;
	}

	@media (max-width: 768px) {
		.loop-page {
			padding-top: 1rem;
			padding-bottom: 10rem;
		}

		.actions {
			bottom: 0.5rem;
		}
	}

	.loop-page {
		max-width: 1024px;
		padding-top: 2rem;
		padding-bottom: 1rem;
	}

	.loop-hero {
		display: flex;
		justify-content: center;
		align-items: center;
		gap: 1rem;
		flex-wrap: wrap;
	}

	.hero-copy {
		display: flex;
		flex-direction: column;
		gap: 0;
		align-items: center;
		width: auto;
	}

	/* .back-link {
		align-self: flex-start;
		padding: 0;
		border: none;
		background: transparent;
		font: inherit;
		font-size: 0.82rem;
		font-weight: 700;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--theme-primary);
		cursor: pointer;
	} */

	.hero-title {
		margin: 0;
		font-size: clamp(2.8rem, 6vw, 4rem);
		line-height: 0.95;
		color: var(--theme-text);
	}

	.progress-pill {
		min-width: 11rem;
		padding: 0.95rem 1.1rem;
		border-radius: 999px;
		background: rgba(255, 255, 255, 0.12);
		border: 1px solid rgba(255, 255, 255, 0.12);
		display: flex;
		align-items: center;
		gap: 0.85rem;
	}

	.progress-pill-count {
		font-size: 1.35rem;
		font-weight: 700;
		color: var(--theme-text);
		font-variant-numeric: tabular-nums;
	}

	.progress-pill-track {
		flex: 1;
		height: 0.5rem;
		border-radius: 999px;
		background: rgba(255, 255, 255, 0.12);
		overflow: hidden;
	}

	.progress-pill-fill {
		height: 100%;
		background: linear-gradient(90deg, rgba(var(--theme-primary-rgb), 0.55), var(--theme-primary));
		border-radius: inherit;
	}

	.hero-status {
		max-width: 760px;
	}

	.question-card {
		padding: 2rem;
		border-radius: 2rem;
	}

	.q-context {
		display: flex;
		align-items: center;
		gap: 1rem;
		flex-wrap: wrap;
		margin-bottom: 1.25rem;
	}

	.q-pill,
	.q-meta-inline {
		display: inline-flex;
		align-items: center;
		gap: 0.45rem;
		font-size: 0.95rem;
		color: rgba(255, 255, 255, 0.72);
	}

	.q-pill {
		padding: 0.7rem 1rem;
		border-radius: 999px;
		background: rgba(255, 255, 255, 0.12);
		border: 1px solid rgba(255, 255, 255, 0.14);
	}

	.q-topic-label {
		margin: 0 0 1rem;
		font-size: 0.82rem;
		font-weight: 700;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: var(--theme-primary);
	}

	.q-text {
		font-size: clamp(0.9rem, 3.3vw, 1.8rem);
		line-height: 1.12;
		margin-bottom: 1.75rem;
	}

	.answer-panel {
		padding: 1.25rem;
		border-radius: 1.75rem;
		background: rgba(255, 255, 255, 0.08);
	}

	.answer-panel-head {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 1rem;
		margin-bottom: 1rem;
	}

	.answer-panel-title {
		font-size: 0.88rem;
		font-weight: 700;
		letter-spacing: 0.12em;
		text-transform: uppercase;
		color: rgba(255, 255, 255, 0.65);
	}

	.options {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 0.8rem;
	}

	.option {
		min-height: 5.5rem;
		padding: 1.2rem 1.35rem;
		border-radius: 1rem;
		border: 1px solid rgba(255, 255, 255, 0.12);
		background: rgba(255, 255, 255, 0.05);
		font-size: 1.05rem;
	}

	.opt-marker {
		width: 2.2rem;
		height: 2.2rem;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		border-radius: 999px;
		background: rgba(255, 255, 255, 0.406);
	}

	.option.selectable.selected {
		background: rgba(var(--theme-primary-rgb), 0.2);
		border-color: rgba(var(--theme-primary-rgb), 0.55);
	}

	.floating-stack {
		position: static;
		transform: none;
		width: min(100%, 1024px);
		margin: 0 auto 4rem;
		padding: 0 1.5rem;
		align-items: stretch;
		pointer-events: auto;
	}
/* 
	.edit-inline-row {
		display: flex;
		justify-content: flex-end;
	}

	.edit-inline-btn {
		border: none;
		background: transparent;
		font: inherit;
		font-size: 0.9rem;
		font-weight: 700;
		color: var(--theme-text-muted);
		cursor: pointer;
	} */

	.grading-grid {
		display: grid;
		grid-template-columns: repeat(4, minmax(0, 1fr));
		gap: 0.9rem;
	}

	.grade-card {
		min-height: 9rem;
		border-radius: 1.4rem;
		border: 1px solid rgba(255, 255, 255, 0.12);
		background: rgba(255, 255, 255, 0.08);
		color: var(--theme-text);
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 0.9rem;
		font: inherit;
		font-weight: 700;
		cursor: pointer;
		transition: transform 0.2s ease, border-color 0.2s ease, background 0.2s ease;
	}

	.grade-card:hover {
		transform: translateY(-2px);
	}

	.grade-badge {
		width: 3.15rem;
		height: 3.15rem;
		border-radius: 999px;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		font-size: 1.9rem;
		font-weight: 800;
	}

	.grade-card.easy .grade-badge,
	.grade-card.easy {
		color: #7df0ca;
	}

	.grade-card.easy .grade-badge {
		background: rgba(49, 208, 161, 0.2);
	}

	.grade-card.medium .grade-badge,
	.grade-card.medium {
		color: #ffd76b;
	}

	.grade-card.medium .grade-badge {
		background: rgba(245, 179, 62, 0.2);
	}

	.grade-card.hard .grade-badge,
	.grade-card.hard {
		color: #ff899d;
	}

	.grade-card.hard .grade-badge {
		background: rgba(244, 63, 94, 0.2);
	}

	.grade-card.reject .grade-badge,
	.grade-card.reject {
		color: #ff728f;
	}

	.grade-card.reject .grade-badge {
		background: rgba(233, 69, 96, 0.18);
	}

	@media (max-width: 1200px) {
		.floating-stack {
			margin: 0.5rem auto 2rem;
			padding: 0 1rem;
		}

		.grading-grid {
			grid-template-columns: repeat(2, minmax(0, 1fr));
			gap: 0.65rem;
		}

		.grade-card {
			min-height: 6rem;
			gap: 0.6rem;
		}
	}

	.complete-batch-fab {
		width: 100%;
		border-radius: 1rem;
		background: rgba(255, 255, 255, 0.08);
		border: 1px solid rgba(255, 255, 255, 0.12);
		color: var(--theme-text);
	}

	@media (max-width: 768px) {
		.loop-page {
			padding: 1.25rem 1rem;
			padding-bottom: 0.5rem;
			gap: 1rem;
		}

		.floating-stack {
			margin: 0.55rem auto 1.9rem;
			padding: 0 1.35rem;
			box-sizing: border-box;
		}

		.loop-hero {
			justify-content: center;
			align-items: center;
			gap: 0.65rem;
		}

		.hero-title {
			font-size: clamp(1rem, 2vw, 1.6rem);
			white-space: nowrap;
		}

		.progress-pill {
			position: static;
			flex-shrink: 0;
			min-width: auto;
			padding: 0.7rem 0.9rem;
		}

		.progress-pill-count {
			font-size: 1.1rem;
		}

		.question-card {
			padding: 1.25rem;
			border-radius: 1.5rem;
		}

		.q-text {
			font-size: clamp(1.4rem, 5vw, 2rem);
			line-height: 1.25;
			margin-bottom: 1.25rem;
		}

		.options {
			grid-template-columns: 1fr;
			gap: 0.6rem;
		}

		.option {
			min-height: auto;
			padding: 0.9rem 1rem;
			font-size: 0.95rem;
		}

		.grading-grid {
			grid-template-columns: repeat(2, 1fr);
			gap: 0.5rem;
			margin-top: 0.25rem;
		}

		.grade-card {
			min-height: 5.2rem;
			padding: 0.75rem;
			gap: 0.45rem;
		}

		.grade-badge {
			width: 2.5rem;
			height: 2.5rem;
			font-size: 1.4rem;
		}

		.grade-label {
			font-size: 0.85rem;
		}

		.answer-panel-head {
			flex-direction: column;
			align-items: flex-start;
		}
	}

	@media (max-width: 480px) {
		.loop-page {
			padding: 1rem 0.75rem 0.35rem;
			gap: 0.85rem;
		}

		.floating-stack {
			margin: 0.45rem auto 1.6rem;
			padding: 0 0.9rem;
			box-sizing: border-box;
		}

		.hero-copy {
			gap: 0.35rem;
		}
/* 
		.back-link {
			font-size: 0.75rem;
		} */

		.hero-title {
			font-size: 1.75rem;
		}

		.progress-pill {
			position: static;
			padding: 0.55rem 0.75rem;
			gap: 0.6rem;
		}

		.progress-pill-count {
			font-size: 0.95rem;
		}

		.progress-pill-track {
			height: 0.35rem;
		}

		.question-card {
			padding: 1rem;
			border-radius: 1.25rem;
		}

		.q-context {
			flex-wrap: wrap;
			gap: 0.5rem;
			margin-bottom: 0.75rem;
		}

		.q-pill {
			padding: 0.4rem 0.6rem;
			font-size: 0.75rem;
		}

		.q-meta-inline {
			font-size: 0.75rem;
		}

		.q-topic-label {
			font-size: 0.72rem;
			margin-bottom: 0.6rem;
		}

		.q-text {
			font-size: 1.15rem;
			line-height: 1.35;
			margin-bottom: 1rem;
		}

		.answer-panel {
			padding: 0.85rem;
			border-radius: 1rem;
		}

		.answer-panel-title {
			font-size: 0.75rem;
		}

		.options {
			gap: 0.5rem;
		}

		.option {
			padding: 0.75rem 0.85rem;
			font-size: 0.88rem;
			gap: 0.5rem;
		}

		.opt-marker {
			width: 1.6rem;
			height: 1.6rem;
			font-size: 0.75rem;
		}

		.grading-grid {
			gap: 0.5rem;
			margin-top: 0.15rem;
		}

		.grade-card {
			min-height: 4.65rem;
			border-radius: 0.85rem;
			gap: 0.35rem;
		}

		.grade-badge {
			width: 2rem;
			height: 2rem;
			font-size: 1.15rem;
		}

		.grade-label {
			font-size: 0.75rem;
		}
	}

	@media (max-width: 380px) {
		.loop-hero {
			transform: translateX(0.35rem);
		}
	}
</style>
