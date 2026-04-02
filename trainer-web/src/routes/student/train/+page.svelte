<script lang="ts">
	import { onDestroy, onMount, tick } from 'svelte';
	import {
		AlertCircle,
		ArrowLeft,
		BookOpen,
		ChevronRight,
		RefreshCw,
		Send,
		Trophy,
	} from 'lucide-svelte';
	import {
		getSubject,
		getSubjectsTree,
		type SubjectGroupTreeNode,
		type SubjectResponse,
		type TopicResponse,
	} from '$lib/api/subjects';
	import {
		streamConversationalInquiry,
		type InquiryLevel,
		type InquiryMessage,
	} from '$lib/api/inquiry';
	import {
		createInquirySession,
		getActiveInquirySession,
		updateInquirySession,
		type InquirySessionState,
	} from '$lib/api/sessions';
	import MarkdownContent from '$lib/components/MarkdownContent.svelte';

	type SubjectCard = SubjectResponse & { groupLabel: string | null };
	type TopicChoice = {
		id: string | null;
		name: string;
		description: string | null;
		total_questions: number | null;
		scope: 'subject' | 'topic';
	};
	type ProviderMeta = {
		key: string;
		name: string;
		model: string;
	};
	type LevelConfig = {
		key: InquiryLevel;
		label: string;
		sublabel: string;
		targetTurns: number;
		accentClass: string;
	};
	type InquiryTurnMode = 'question' | 'answer_feedback' | 'reasoning_feedback';
	type SessionPhase = 'awaiting-answer' | 'awaiting-reasoning';
	type AssistantDirective = 'advance' | 'hold';
	type AssistantTurnResult = {
		succeeded: boolean;
		directive: AssistantDirective;
		history: InquiryMessage[];
	};

	const LEVELS: LevelConfig[] = [
		{
			key: 'beginner',
			label: 'Foundation',
			sublabel: 'Recall and core understanding',
			targetTurns: 3,
			accentClass: 'foundation',
		},
		{
			key: 'advanced',
			label: 'Deep Dive',
			sublabel: 'Application and causal reasoning',
			targetTurns: 3,
			accentClass: 'advanced',
		},
		{
			key: 'pro',
			label: 'Mastery',
			sublabel: 'Trade-offs, nuance, and judgment',
			targetTurns: 3,
			accentClass: 'pro',
		},
	];

	const MAX_EXPLANATION_ATTEMPTS = 3;
	const UNGROUPED_SUBJECT_LABEL = 'Ungrouped Subjects';
	const PROGRESS_ADVANCE_TAG = /\[\[PROGRESS:ADVANCE\]\]/i;
	const PROGRESS_TAGS = /\[\[PROGRESS:(?:ADVANCE|HOLD)\]\]/gi;
	const PARTIAL_PROGRESS_TAG = /\[\[PROGRESS:[\s\S]*$/i;
	const QUESTION_START_TRANSITION =
		/(?:^|\n\s*\n)(?=(?:Which\b|What\b|How\b|Why\b|When\b|Given\b|Suppose\b|Select\b|Choose\b|Consider\b|Now,\s*consider\b|For the next question\b|In\s+[A-Z]))/i;
	const NEXT_QUESTION_TRANSITION =
		/\n\s*\n(?=(?:Now\b|Next\b|For the next question\b|Consider this\b|New question\b|Question\s+\d+\b))/i;
	const LENIENT_REASONING_POSITIVE_SIGNAL =
		/(?:you(?:'ve| have)? correctly identified|your answer shows you understand|you understand the concept|you're on the right track|that is correct|that's correct|good\. you've correctly|core concept|essential idea)/i;
	const LENIENT_REASONING_NEGATIVE_SIGNAL =
		/(?:incorrect|not correct|wrong|misconception|misunderstand|confused|still missing|missing key|not enough|incomplete reasoning|partially correct)/i;

	function emptyProgress(): Record<InquiryLevel, number> {
		return { beginner: 0, advanced: 0, pro: 0 };
	}

	function stripProgressTags(content: string): string {
		return content.replace(PROGRESS_TAGS, '').replace(PARTIAL_PROGRESS_TAG, '').trim();
	}

	function extractProgressDirective(content: string): AssistantDirective {
		return PROGRESS_ADVANCE_TAG.test(content) ? 'advance' : 'hold';
	}

	function trimUnexpectedQuestionLeadIn(
		content: string,
		mode: InquiryTurnMode,
		directive: AssistantDirective
	): string {
		if (mode === 'question') {
			const questionStartIndex = content.search(QUESTION_START_TRANSITION);
			// Only strip preamble when it's a long paragraph (> 120 chars).
			// Short warm transitions like "Next up:" or "Alright—" are intentional.
			if (questionStartIndex > 120) {
				return content.slice(questionStartIndex).trim();
			}
			return content.trim();
		}

		if (directive !== 'advance') {
			return content.trim();
		}

		const nextQuestionIndex = content.search(NEXT_QUESTION_TRANSITION);
		if (nextQuestionIndex > -1) {
			return content.slice(0, nextQuestionIndex).trim();
		}

		return content.trim();
	}

	function shouldLenientlyAdvance(
		mode: InquiryTurnMode,
		explanationAttempt: number,
		directive: AssistantDirective,
		assistantContent: string
	): boolean {
		if (mode !== 'reasoning_feedback' || directive === 'advance' || explanationAttempt < 2) {
			return false;
		}

		return (
			LENIENT_REASONING_POSITIVE_SIGNAL.test(assistantContent) &&
			!LENIENT_REASONING_NEGATIVE_SIGNAL.test(assistantContent)
		);
	}

	let subjects = $state<SubjectCard[]>([]);
	let topics = $state<TopicChoice[]>([]);
	let isLoadingSubjects = $state(true);
	let isLoadingTopics = $state(false);
	let error = $state<string | null>(null);
	let sessionHint = $state<string | null>(null);
	let selectedSubject = $state<SubjectCard | null>(null);
	let selectedTopic = $state<TopicChoice | null>(null);
	let messages = $state<InquiryMessage[]>([]);
	let draft = $state('');
	let isStreaming = $state(false);
	let providerMeta = $state<ProviderMeta | null>(null);
	let currentLevel = $state<InquiryLevel>('beginner');
	let completedTurnsByLevel = $state<Record<InquiryLevel, number>>(emptyProgress());
	let currentQuestionAttempt = $state(0);
	let currentPhase = $state<SessionPhase>('awaiting-answer');
	let subjectSearch = $state('');
	let selectedGroupFilter = $state('__all__');

	// Session persistence
	let currentSessionId = $state<string | null>(null);
	let pendingResumeSession = $state<InquirySessionState | null>(null);
	let isSavingSession = $state(false);

	let messageViewport = $state<HTMLDivElement | null>(null);
	let streamAbortController: AbortController | null = null;
	let isWaitingForFirstToken = $state(false);
	let transitionMessage = $state<string | null>(null);

	const TRANSITION_PHRASES = [
		'Moving on',
		'Next up',
		'On to the next one',
		'Onwards!',
		"Let's keep going",
		'Nice — next question',
		'One down!',
		'Building momentum',
		'Solid — keep it up',
		'Challenge accepted',
		'Step by step',
	];

	function pickTransitionPhrase(): string {
		return TRANSITION_PHRASES[Math.floor(Math.random() * TRANSITION_PHRASES.length)];
	}

	const activeLevel = $derived(LEVELS.find((level) => level.key === currentLevel) ?? LEVELS[0]);
	const currentTurns = $derived(completedTurnsByLevel[currentLevel] ?? 0);
	const progressPercent = $derived(
		Math.min(100, Math.round((currentTurns / activeLevel.targetTurns) * 100))
	);
	const completedLevelCount = $derived(
		LEVELS.filter((level) => (completedTurnsByLevel[level.key] ?? 0) >= level.targetTurns).length
	);
	const canAdvanceLevel = $derived(
		currentTurns >= activeLevel.targetTurns && currentLevel !== 'pro' && !isStreaming
	);
	const isSessionComplete = $derived(
		currentLevel === 'pro' && currentTurns >= activeLevel.targetTurns && !isStreaming
	);
	const attemptsRemaining = $derived(Math.max(0, MAX_EXPLANATION_ATTEMPTS - currentQuestionAttempt));
	const nextQuestionNumber = $derived(Math.min(activeLevel.targetTurns, currentTurns + 1));
	const isAwaitingReasoning = $derived(currentPhase === 'awaiting-reasoning');
	const sessionInstruction = $derived(
		isAwaitingReasoning
			? 'Respond to the tutor\'s follow-up and explain why your answer works before this step counts toward progress.'
			: 'Answer the current question first. If you already know the reason, include it now and the tutor can accept it immediately.'
	);
	const phaseChipLabel = $derived(
		isAwaitingReasoning ? `${attemptsRemaining} ${attemptsRemaining === 1 ? 'try' : 'tries'} left` : 'Answer step'
	);
	const composerPlaceholder = $derived(
		canAdvanceLevel
			? 'Advance to the next stage to continue the session'
			: isSessionComplete
				? 'Restart this level or choose another topic'
				: isAwaitingReasoning
					? currentQuestionAttempt > 0
						? 'Refine your reasoning based on the tutor\'s last message.'
						: 'Explain why you chose that answer, or what makes the correct option right.'
					: 'Answer the current question. You can include the reasoning now if you want to move faster.'
	);
	const groupFilterOptions = $derived.by(() => {
		const labels = new Set<string>();
		for (const subject of subjects) {
			labels.add(subject.groupLabel ?? UNGROUPED_SUBJECT_LABEL);
		}
		return [...labels].sort((left, right) => {
			if (left === UNGROUPED_SUBJECT_LABEL) return 1;
			if (right === UNGROUPED_SUBJECT_LABEL) return -1;
			return left.localeCompare(right);
		});
	});
	const filteredSubjects = $derived.by(() => {
		const query = subjectSearch.trim().toLowerCase();
		return [...subjects]
			.filter((subject) => {
				const groupLabel = subject.groupLabel ?? UNGROUPED_SUBJECT_LABEL;
				const matchesGroup =
					selectedGroupFilter === '__all__' || groupLabel === selectedGroupFilter;
				const matchesQuery =
					!query ||
					[
						subject.name,
						subject.code,
						subject.description ?? '',
						groupLabel,
					]
						.join(' ')
						.toLowerCase()
						.includes(query);

				return matchesGroup && matchesQuery;
			})
			.sort((left, right) => left.name.localeCompare(right.name));
	});
	const filteredSubjectCount = $derived(filteredSubjects.length);

	onMount(() => {
		void loadSubjects();
	});

	onDestroy(() => {
		abortActiveStream();
	});

	$effect(() => {
		messages.length;
		isWaitingForFirstToken;
		void tick().then(() => {
			messageViewport?.scrollTo({ top: messageViewport.scrollHeight, behavior: 'smooth' });
		});
	});

	$effect(() => {
		groupFilterOptions;
		if (
			selectedGroupFilter !== '__all__' &&
			!groupFilterOptions.includes(selectedGroupFilter)
		) {
			selectedGroupFilter = '__all__';
		}
	});

	function flattenSubjectsFromGroups(
		groups: SubjectGroupTreeNode[],
		lineage: string[] = []
	): SubjectCard[] {
		const cards: SubjectCard[] = [];
		for (const group of groups) {
			const nextLineage = [...lineage, group.name];
			for (const subject of group.subjects) {
				cards.push({ ...subject, groupLabel: nextLineage.join(' / ') });
			}
			cards.push(...flattenSubjectsFromGroups(group.children, nextLineage));
		}
		return cards;
	}

	async function loadSubjects() {
		isLoadingSubjects = true;
		error = null;
		try {
			const tree = await getSubjectsTree();
			subjects = [
				...tree.ungrouped_subjects.map((subject) => ({ ...subject, groupLabel: null })),
				...flattenSubjectsFromGroups(tree.groups),
			].sort((left, right) => left.name.localeCompare(right.name));
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to load subjects';
		} finally {
			isLoadingSubjects = false;
		}
	}

	async function loadTopicsForSubject(subject: SubjectCard) {
		isLoadingTopics = true;
		error = null;
		try {
			const detail = await getSubject(subject.id);
			topics = [
				{
					id: null,
					name: 'Entire subject',
					description:
						subject.description ?? 'Start broad guided practice across this subject.',
					total_questions: subject.total_questions,
					scope: 'subject',
				},
				...detail.topics.map((topic: TopicResponse) => ({
					id: topic.id,
					name: topic.name,
					description: topic.description,
					total_questions: topic.total_questions,
					scope: 'topic' as const,
				})),
			];
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to load topics';
			topics = [];
		} finally {
			isLoadingTopics = false;
		}
	}

	function abortActiveStream() {
		streamAbortController?.abort();
		streamAbortController = null;
		isStreaming = false;
	}

	function resetSessionState() {
		messages = [];
		draft = '';
		providerMeta = null;
		error = null;
		sessionHint = null;
		currentLevel = 'beginner';
		currentQuestionAttempt = 0;
		currentPhase = 'awaiting-answer';
		completedTurnsByLevel = emptyProgress();
		currentSessionId = null;
		pendingResumeSession = null;
	}

	function restoreSessionState(saved: InquirySessionState) {
		currentLevel = (saved.current_level as InquiryLevel) ?? 'beginner';
		completedTurnsByLevel = {
			beginner: saved.completed_turns_by_level?.beginner ?? 0,
			advanced: saved.completed_turns_by_level?.advanced ?? 0,
			pro: saved.completed_turns_by_level?.pro ?? 0,
		};
		messages = (saved.messages ?? []) as InquiryMessage[];
		currentPhase = (saved.current_phase as SessionPhase) ?? 'awaiting-answer';
		currentQuestionAttempt = saved.current_question_attempt ?? 0;
		currentSessionId = saved.id;
		draft = '';
		error = null;
		sessionHint = null;
	}

	async function saveSessionState(isComplete = false) {
		if (!currentSessionId || isSavingSession) return;
		isSavingSession = true;
		try {
			await updateInquirySession(currentSessionId, {
				current_level: currentLevel,
				completed_turns_by_level: completedTurnsByLevel,
				messages: messages as Array<{ role: string; content: string }>,
				current_phase: currentPhase,
				current_question_attempt: currentQuestionAttempt,
				...(isComplete ? { is_complete: true } : {}),
			});
		} catch {
			// Best-effort — don't block UX on save failure
		} finally {
			isSavingSession = false;
		}
	}

	async function selectSubject(subject: SubjectCard) {
		abortActiveStream();
		selectedSubject = subject;
		selectedTopic = null;
		resetSessionState();
		await loadTopicsForSubject(subject);
	}

	async function startTopicSession(topic: TopicChoice) {
		abortActiveStream();
		selectedTopic = topic;
		resetSessionState();

		// Check for an existing resumable session
		if (selectedSubject) {
			try {
				const existing = await getActiveInquirySession(
					selectedSubject.id,
					topic.scope === 'topic' ? topic.id : null
				);
				if (existing && existing.messages && existing.messages.length > 0) {
					pendingResumeSession = existing;
					return; // Wait for user to choose resume or start fresh
				}
			} catch {
				// No active session or network error — start fresh
			}
		}
		await beginFreshSession(topic);
	}

	async function beginFreshSession(topic: TopicChoice) {
		if (!selectedSubject) return;
		try {
			const session = await createInquirySession(
				selectedSubject.id,
				topic.scope === 'topic' ? topic.id : null
			);
			currentSessionId = session.id;
		} catch {
			// Best-effort — tutor still works without persistence
		}
		await openLevel();
	}

	async function resumeExistingSession(saved: InquirySessionState) {
		pendingResumeSession = null;
		restoreSessionState(saved);
		// If the saved session has messages already in progress but no pending question,
		// ask a fresh question at the restored level
		if (messages.length === 0 || currentPhase === 'awaiting-answer' && messages.length > 0) {
			// messages already restored — tutor shows existing conversation
		}
		// The conversation history is already restored; the student can continue typing
	}

	async function dismissResumeAndStartFresh() {
		const topic = selectedTopic;
		if (!topic) return;
		pendingResumeSession = null;
		await beginFreshSession(topic);
	}

	function backToSubjects() {
		abortActiveStream();
		selectedSubject = null;
		selectedTopic = null;
		topics = [];
		resetSessionState();
	}

	function backToTopics() {
		abortActiveStream();
		selectedTopic = null;
		resetSessionState();
	}

	async function openLevel() {
		if (!selectedSubject || !selectedTopic) return;
		messages = [];
		error = null;
		sessionHint = null;
		currentQuestionAttempt = 0;
		currentPhase = 'awaiting-answer';
		await requestNextQuestion([]);
	}

	async function requestAssistantTurn(opts: {
		history: InquiryMessage[];
		mode: InquiryTurnMode;
		questionCycleIndex: number;
		explanationAttempt: number;
	}): Promise<AssistantTurnResult> {
		if (!selectedSubject || !selectedTopic) {
			return { succeeded: false, directive: 'hold', history: opts.history };
		}

		abortActiveStream();
		isStreaming = true;
		isWaitingForFirstToken = true;
		error = null;

		const controller = new AbortController();
		streamAbortController = controller;
		let assistantBuffer = '';

		try {
			for await (const event of streamConversationalInquiry({
				subjectId: selectedSubject.id,
				topicId: selectedTopic.scope === 'topic' ? selectedTopic.id : null,
				level: currentLevel,
				mode: opts.mode,
				questionCycleIndex: opts.questionCycleIndex,
				explanationAttempt: opts.explanationAttempt,
				messages: opts.history,
				signal: controller.signal,
			})) {
				if (event.type === 'meta') {
					providerMeta = {
						key: event.provider_key ?? '',
						name: event.provider_name ?? event.provider_key ?? 'Provider',
						model: event.provider_model ?? '',
					};
					continue;
				}

				if (event.type === 'delta') {
					if (isWaitingForFirstToken) {
						isWaitingForFirstToken = false;
						transitionMessage = null;
					}
					assistantBuffer += event.delta ?? '';
					const assistantMessage: InquiryMessage = {
						role: 'assistant',
						content: stripProgressTags(assistantBuffer),
					};
					messages = opts.history.length > 0 ? [...opts.history, assistantMessage] : [assistantMessage];
					continue;
				}

				if (event.type === 'complete' && event.message && !assistantBuffer) {
					assistantBuffer = event.message;
					const assistantMessage: InquiryMessage = {
						role: 'assistant',
						content: stripProgressTags(assistantBuffer),
					};
					messages = opts.history.length > 0 ? [...opts.history, assistantMessage] : [assistantMessage];
					continue;
				}

				if (event.type === 'error') {
					throw new Error(event.message ?? 'The provider could not continue this session.');
				}
			}

			let directive = extractProgressDirective(assistantBuffer);
			const cleanedAssistant = trimUnexpectedQuestionLeadIn(
				stripProgressTags(assistantBuffer),
				opts.mode,
				directive,
			);
			if (shouldLenientlyAdvance(opts.mode, opts.explanationAttempt, directive, cleanedAssistant)) {
				directive = 'advance';
			}
			if (!cleanedAssistant) {
				throw new Error('The provider returned an empty response.');
			}

			const assistantMessage: InquiryMessage = {
				role: 'assistant',
				content: cleanedAssistant,
			};
			const updatedHistory: InquiryMessage[] =
				opts.history.length > 0 ? [...opts.history, assistantMessage] : [assistantMessage];

			messages = updatedHistory;
			return {
				succeeded: true,
				directive,
				history: updatedHistory,
			};
		} catch (e: unknown) {
			if (e instanceof DOMException && e.name === 'AbortError') {
				return { succeeded: false, directive: 'hold', history: opts.history };
			}
			error = e instanceof Error ? e.message : 'Failed to continue the session';
			messages = opts.history;
			return { succeeded: false, directive: 'hold', history: opts.history };
		} finally {
			if (streamAbortController === controller) {
				streamAbortController = null;
			}
			isStreaming = false;
			isWaitingForFirstToken = false;
		}
	}

	async function requestNextQuestion(history: InquiryMessage[] = messages) {
		transitionMessage = null;
		currentPhase = 'awaiting-answer';
		currentQuestionAttempt = 0;
		sessionHint = null;
		return requestAssistantTurn({
			history,
			mode: 'question',
			questionCycleIndex: completedTurnsByLevel[currentLevel] ?? 0,
			explanationAttempt: 0,
		});
	}

	async function completeAcceptedTurn(result: AssistantTurnResult) {
		const nextCompletedTurnCount = Math.min(
			activeLevel.targetTurns,
			(completedTurnsByLevel[currentLevel] ?? 0) + 1
		);

		completedTurnsByLevel = {
			...completedTurnsByLevel,
			[currentLevel]: nextCompletedTurnCount,
		};
		currentQuestionAttempt = 0;
		currentPhase = 'awaiting-answer';
		sessionHint = null;

		// Session fully complete — all 3 levels done
		const sessionJustCompleted =
			currentLevel === 'pro' && nextCompletedTurnCount >= activeLevel.targetTurns;
		if (sessionJustCompleted) {
			void saveSessionState(true);
			return;
		}

		// Level complete — wait for student to press Continue
		if (nextCompletedTurnCount >= activeLevel.targetTurns) {
			void saveSessionState();
			return;
		}

		transitionMessage = pickTransitionPhrase();
		void saveSessionState();
		await requestNextQuestion(result.history);
	}

	async function submitReply() {
		if (!selectedSubject || !selectedTopic || isStreaming || canAdvanceLevel || isSessionComplete) {
			return;
		}

		const content = draft.trim();
		if (!content) return;

		const history = [...messages, { role: 'user', content } as InquiryMessage];
		messages = history;
		draft = '';

		if (!isAwaitingReasoning) {
			const answerResult = await requestAssistantTurn({
				history,
				mode: 'answer_feedback',
				questionCycleIndex: completedTurnsByLevel[currentLevel] ?? 0,
				explanationAttempt: 0,
			});
			if (!answerResult.succeeded) return;

			if (answerResult.directive === 'advance') {
				await completeAcceptedTurn(answerResult);
				return;
			}

			currentPhase = 'awaiting-reasoning';
			currentQuestionAttempt = 0;
			sessionHint = null;
			void saveSessionState();
			return;
		}

		const nextAttempt = Math.min(MAX_EXPLANATION_ATTEMPTS, currentQuestionAttempt + 1);
		const reasoningResult = await requestAssistantTurn({
			history,
			mode: 'reasoning_feedback',
			questionCycleIndex: completedTurnsByLevel[currentLevel] ?? 0,
			explanationAttempt: nextAttempt,
		});
		if (!reasoningResult.succeeded) return;

		void saveSessionState();
		const advanced = reasoningResult.directive === 'advance' || nextAttempt >= MAX_EXPLANATION_ATTEMPTS;
		if (!advanced) {
			currentQuestionAttempt = nextAttempt;
			sessionHint = null;
			void saveSessionState();
			return;
		}

		await completeAcceptedTurn(reasoningResult);
	}

	function handleComposerKeydown(event: KeyboardEvent) {
		if (event.key === 'Enter' && !event.shiftKey) {
			event.preventDefault();
			void submitReply();
		}
	}

	function handleClickableRowKeydown(event: KeyboardEvent, action: () => void) {
		if (event.key === 'Enter' || event.key === ' ') {
			event.preventDefault();
			action();
		}
	}

	async function retryCurrentLevel() {
		abortActiveStream();
		messages = [];
		error = null;
		sessionHint = null;
		currentQuestionAttempt = 0;
		currentPhase = 'awaiting-answer';
		await requestNextQuestion([]);
	}

	async function advanceLevel() {
		if (!canAdvanceLevel) return;
		const nextIndex = LEVELS.findIndex((level) => level.key === currentLevel) + 1;
		if (nextIndex < 0 || nextIndex >= LEVELS.length) return;
		currentLevel = LEVELS[nextIndex].key;
		messages = [];
		error = null;
		sessionHint = null;
		currentQuestionAttempt = 0;
		currentPhase = 'awaiting-answer';
		void saveSessionState();
		await requestNextQuestion([]);
	}
</script>

<svelte:head>
	<title>GEL Train | Student Console</title>
</svelte:head>

<div class="page-container student-shell train-shell" class:in-session={!!selectedTopic}>
	{#if pendingResumeSession}
		<div class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
			<div class="glass-panel max-w-md w-full p-8 shadow-2xl border border-white/10 animate-in fade-in zoom-in duration-300">
				<div class="mb-6 flex items-center gap-4">
					<div class="w-12 h-12 rounded-full bg-primary/20 flex items-center justify-center text-primary">
						<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-history"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M12 7v5l4 2"/></svg>
					</div>
					<h2 class="text-2xl font-bold tracking-tight">Resume Session?</h2>
				</div>
				<p class="text-muted mb-8 leading-relaxed">
					We found an unfinished practice session. Would you like to pick up where you left off, or start a completely new training session?
				</p>
				<div class="flex flex-col gap-3">
					<button 
						class="btn-primary py-3 font-semibold shadow-lg shadow-primary/20"
						onclick={() => pendingResumeSession && void resumeExistingSession(pendingResumeSession)}
					>
						Resume Session
					</button>
					<button 
						class="btn-secondary py-3 font-medium border-white/5 hover:bg-white/5"
						onclick={() => void dismissResumeAndStartFresh()}
					>
						Start Fresh
					</button>
				</div>
			</div>
		</div>
	{/if}

	{#if !selectedSubject}
		<section class="glass-panel chooser-panel space-y-5">
			<header class="panel-header">
				<div class="search-combo">
					<input
						type="text"
						bind:value={subjectSearch}
						placeholder="Search by subject, code, or group"
					/>
					<div class="search-combo-divider" aria-hidden="true"></div>
					<select bind:value={selectedGroupFilter} aria-label="Filter subjects by group">
						<option value="__all__">All groups</option>
						{#each groupFilterOptions as groupLabel}
							<option value={groupLabel}>{groupLabel}</option>
						{/each}
					</select>
				</div>
			</header>

			{#if error}
				<div class="glass-panel error-panel compact">
					<div class="flex-row">
						<AlertCircle class="h-5 w-5" />
						<span>{error}</span>
					</div>
					<button class="pill ghost" onclick={loadSubjects}>Try again</button>
				</div>
			{/if}

			{#if isLoadingSubjects}
				<div class="center-state large-state">
					<div class="spinner"></div>
					<p class="muted">Loading subjects...</p>
				</div>
			{:else if filteredSubjectCount === 0}
				<div class="center-state large-state">
					<BookOpen class="h-10 w-10 icon-muted" />
					<h3 class="empty-title">No subjects found</h3>
					<p class="muted">Add or search for subjects in the main trainer workspace, then return here.</p>
				</div>
			{:else}
				<div class="table-wrap">
					<table class="chooser-table">
						<colgroup>
							<col class="subject-col" />
							<col class="code-col" />
							<col class="group-col" />
							<col class="count-col" />
							<col class="count-col" />
						</colgroup>
						<thead>
							<tr>
								<th>Subject</th>
								<th>Code</th>
								<th>Group</th>
								<th>Topics</th>
								<th>Questions</th>
							</tr>
						</thead>
						<tbody>
							{#each filteredSubjects as subject}
								<tr
									class="clickable-row"
									role="button"
									tabindex="0"
									aria-label={`Open ${subject.name}`}
									onclick={() => selectSubject(subject)}
									onkeydown={(event) => handleClickableRowKeydown(event, () => selectSubject(subject))}
								>
									<td>
										<div class="table-title-stack">
											<strong class="table-title">{subject.name}</strong>
											<p class="table-description">{subject.description || 'Open this subject to choose a topic or study across the full subject.'}</p>
										</div>
									</td>
									<td><span class="pill subtle">{subject.code}</span></td>
									<td>{subject.groupLabel ?? UNGROUPED_SUBJECT_LABEL}</td>
									<td>{subject.total_topics}</td>
									<td>{subject.total_questions ?? 0}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{/if}
		</section>
	{:else if !selectedTopic}
		<section class="glass-panel chooser-panel space-y-5">
			<header class="panel-header with-action subject-header">
				<div class="subject-header-bar">
					<button class="back-chip" onclick={backToSubjects} aria-label="Back to subjects">
						<ArrowLeft class="h-4 w-4" />
					</button>
					<div class="subject-summary">
						<div class="subject-summary-meta">
							<span class="subject-summary-chip subject-summary-code">{selectedSubject.code}</span>
							{#if selectedSubject.groupLabel}
								<span class="subject-summary-chip subject-summary-group">{selectedSubject.groupLabel}</span>
							{/if}
						</div>
						<span class="subject-summary-chip subject-summary-count">{selectedSubject.total_topics} topics</span>
					</div>
				</div>
			</header>

			{#if error}
				<div class="glass-panel error-panel compact">
					<div class="flex-row">
						<AlertCircle class="h-5 w-5" />
						<span>{error}</span>
					</div>
					<button class="pill ghost" onclick={() => selectedSubject && loadTopicsForSubject(selectedSubject)}>Reload topics</button>
				</div>
			{/if}

			{#if isLoadingTopics}
				<div class="center-state large-state">
					<div class="spinner"></div>
					<p class="muted">Loading topics...</p>
				</div>
			{:else if topics.length === 0}
				<div class="center-state large-state">
					<BookOpen class="h-10 w-10 icon-muted" />
					<h3 class="empty-title">No topics available</h3>
					<p class="muted">This subject does not have topic entries yet. You can still study the entire subject once it becomes available.</p>
				</div>
			{:else}
				<div class="table-wrap">
					<table class="chooser-table topic-table">
						<colgroup>
							<col class="scope-col" />
							<col class="subject-col" />
							<col class="count-col" />
						</colgroup>
						<thead>
							<tr>
								<th>Scope</th>
								<th>Topic</th>
								<th>Questions</th>
							</tr>
						</thead>
						<tbody>
							{#each topics as topic}
								<tr
									class="clickable-row"
									role="button"
									tabindex="0"
									aria-label={`Start ${topic.name}`}
									onclick={() => startTopicSession(topic)}
									onkeydown={(event) => handleClickableRowKeydown(event, () => startTopicSession(topic))}
								>
									<td>
										<span class="scope-pill">{topic.scope === 'subject' ? 'Entire subject' : 'Topic'}</span>
									</td>
									<td>
										<div class="table-title-stack">
											<strong class="table-title">{topic.name}</strong>
											<p class="table-description">{topic.description || 'Start a guided practice session in this scope.'}</p>
										</div>
									</td>
									<td>{topic.total_questions ?? '—'}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{/if}
		</section>
	{:else}
		<section class="glass-panel session-rail">
			<button class="rail-icon-btn" onclick={backToTopics} aria-label="Change topic">
				<ArrowLeft class="h-4 w-4" />
			</button>
			<span class="rail-topic">{selectedTopic.name}</span>
			<div class="rail-level-progress">
				<Trophy class="h-4 w-4 rail-level-icon" />
				<span class="rail-level-name">{activeLevel.label}</span>
				<div class="progress-track rail-track">
					<div class="progress-bar {activeLevel.accentClass}" style={`width: ${progressPercent}%`}></div>
				</div>
				<span class="rail-count">{currentTurns}/{activeLevel.targetTurns}</span>
			</div>
			<button class="rail-icon-btn" onclick={retryCurrentLevel} disabled={isStreaming} aria-label="Restart level">
				<RefreshCw class="h-4 w-4" />
			</button>
		</section>

		<section class="glass-panel session-panel">

			{#if sessionHint}
				<div class="hint-banner">{sessionHint}</div>
			{/if}

			{#if error}
				<div class="glass-panel error-panel compact inside-session">
					<div class="flex-row">
						<AlertCircle class="h-5 w-5" />
						<span>{error}</span>
					</div>
					<button class="pill ghost" onclick={retryCurrentLevel} disabled={isStreaming}>Retry</button>
				</div>
			{/if}

			<div class="message-viewport" bind:this={messageViewport}>
				{#if messages.length === 0 && !isWaitingForFirstToken}
					<div class="center-state large-state inline-state">
						<Trophy class="h-10 w-10 icon-muted" />
						<h3 class="empty-title">Session ready</h3>
						<p class="muted">Start the level to receive a guided question.</p>
					</div>
				{:else}
					{#each messages as message}
						<article class="message-row" class:user={message.role === 'user'}>
							<div class="message-meta">{message.role === 'assistant' ? 'Tutor' : 'You'}</div>
							<div class="message-bubble">
								<MarkdownContent content={message.content} />
							</div>
						</article>
					{/each}

					{#if transitionMessage}
						<div class="session-divider">
							<span class="session-divider-pill">{transitionMessage}</span>
						</div>
					{/if}

					{#if isWaitingForFirstToken}
						<article class="message-row">
							<div class="message-meta">Tutor</div>
							<div class="message-bubble typing-bubble">
								<span class="typing-dot"></span>
								<span class="typing-dot"></span>
								<span class="typing-dot"></span>
							</div>
						</article>
					{/if}
				{/if}
			</div>

			{#if canAdvanceLevel}
				<div class="stage-banner success-banner">
					<div>
						<p class="banner-title">{activeLevel.label} complete</p>
						<p class="muted">Move to the next stage when you are ready.</p>
					</div>
					<button class="pill primary" onclick={advanceLevel}>
						<span>Continue</span>
						<ChevronRight class="h-4 w-4" />
					</button>
				</div>
			{:else if isSessionComplete}
				<div class="stage-banner completion-banner">
					<div>
						<p class="banner-title">Mastery reached</p>
						<p class="muted">Restart this level or switch topics to keep practicing.</p>
					</div>
					<button class="pill ghost" onclick={retryCurrentLevel}>Run it again</button>
				</div>
			{/if}

			<form class="composer" onsubmit={(event) => { event.preventDefault(); void submitReply(); }}>
				<textarea
					bind:value={draft}
					onkeydown={handleComposerKeydown}
					placeholder={composerPlaceholder}
					disabled={isStreaming || canAdvanceLevel || isSessionComplete}
				></textarea>
				<button class="composer-send" type="submit" disabled={isStreaming || !draft.trim() || canAdvanceLevel || isSessionComplete}>
					<Send class="h-4 w-4" />
					<span>{isStreaming ? 'Thinking...' : 'Send'}</span>
				</button>
			</form>
		</section>
	{/if}
</div>

<style>
	.page-container {
		max-width: 1240px;
		margin: 0 auto;
		padding: clamp(1rem, 2vw, 1.5rem) clamp(1.25rem, 3vw, 2.25rem) clamp(2rem, 3vw, 2.75rem);
		color: var(--theme-text-primary);
	}

	.train-shell {
		display: flex;
		flex-direction: column;
		gap: 2rem;
		min-height: 100%;
	}

	.page-container.in-session {
		height: 100%;
		min-height: 0;
		gap: 1rem;
	}

	.glass-panel {
		background: color-mix(in srgb, var(--theme-nav-glass) 88%, transparent);
		border: 1px solid var(--theme-glass-border);
		border-radius: 18px;
		padding: 18px;
		box-shadow: 0 18px 48px rgba(0, 0, 0, 0.18);
		backdrop-filter: blur(18px);
		-webkit-backdrop-filter: blur(18px);
		color: var(--theme-text-primary);
	}

	.gradient-card {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1.25rem;
		background:
			radial-gradient(circle at 18% 18%, rgba(var(--theme-primary-rgb), 0.18), transparent 34%),
			radial-gradient(circle at 82% 12%, rgba(16, 185, 129, 0.12), transparent 30%),
			color-mix(in srgb, var(--theme-nav-glass) 92%, transparent);
	}

	.hero-card {
		padding: 1.4rem 1.5rem;
	}

	.eyebrow,
	.panel-label,
	.message-meta,
	.summary-label,
	.compact-chip,
	.muted,
	.table-description,
	.subject-summary,
	.level-copy {
		margin: 0;
		color: var(--theme-text-secondary);
	}

	.eyebrow,
	.panel-label,
	.message-meta {
		text-transform: uppercase;
		letter-spacing: 0.12em;
		font-size: 0.75rem;
	}

	.hero,
	.panel-title,
	.session-topic,
	.empty-title,
	.banner-title {
		margin: 0;
		color: var(--theme-text-primary);
		font-weight: 700;
	}

	.hero {
		font-size: clamp(1.75rem, 2.2vw, 2.2rem);
		margin-top: 0.15rem;
	}

	.panel-title {
		font-size: 1.45rem;
		margin-bottom: 0.2rem;
	}

	.session-topic {
		font-size: 1.15rem;
		margin-top: 0;
	}

	.hero-metrics {
		display: flex;
		gap: 1rem;
		align-items: stretch;
		justify-content: flex-end;
		flex-wrap: wrap;
	}

	.summary-value {
		margin: 0;
		font-size: 1.8rem;
		font-weight: 700;
		color: var(--theme-text-primary);
	}

	.summary-value.provider-label {
		font-size: 1.05rem;
		line-height: 1.3;
	}

	.chooser-panel {
		padding: 1.35rem;
	}

	.panel-header {
		display: flex;
		flex-wrap: wrap;
		justify-content: space-between;
		gap: 1rem;
		align-items: flex-start;
	}

	.panel-header.with-action {
		align-items: center;
	}

	.section-title-wrap {
		display: flex;
		gap: 0.9rem;
		align-items: flex-start;
	}

	.subject-header {
		align-items: center;
	}

	.subject-header-bar {
		display: flex;
		align-items: center;
		gap: 1rem;
		width: 100%;
		min-width: 0;
	}

	.icon-pill {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 44px;
		height: 44px;
		border-radius: 14px;
		background: rgba(var(--theme-primary-rgb), 0.12);
		color: var(--theme-text-primary);
		border: 1px solid rgba(var(--theme-primary-rgb), 0.18);
	}

	.icon-pill.secondary {
		background: rgba(59, 130, 246, 0.1);
		border-color: rgba(59, 130, 246, 0.18);
	}

	.icon-muted {
		color: rgba(var(--theme-primary-rgb), 0.78);
	}

	.search-combo {
		display: flex;
		align-items: center;
		width: 100%;
		border-radius: 14px;
		border: 1px solid rgba(0, 0, 0, 0.14);
		background: rgba(0, 0, 0, 0.06);
		overflow: hidden;
	}

	.search-combo-divider {
		width: 1px;
		align-self: stretch;
		background: color-mix(in srgb, var(--theme-glass-border) 80%, transparent);
	}

	.search-combo input,
	.search-combo select {
		border: none;
		background: transparent;
		color: var(--theme-text-primary);
		padding: 0.85rem 0.95rem;
		font: inherit;
	}

	.search-combo input {
		flex: 1;
		min-width: 0;
	}

	.search-combo select {
		flex: 0 1 220px;
		min-width: 160px;
		max-width: 45%;
	}

	.composer textarea {
		width: 100%;
		border-radius: 14px;
		border: 1px solid rgba(0, 0, 0, 0.14);
		background: rgba(0, 0, 0, 0.06);
		color: var(--theme-text-primary);
		padding: 0.85rem 0.95rem;
		font: inherit;
		resize: vertical;
	}

	:global([data-color-mode='dark']) .search-combo,
	:global([data-color-mode='dark']) .composer textarea {
		border-color: var(--theme-glass-border);
		background: color-mix(in srgb, var(--theme-input-bg) 55%, var(--theme-surface) 45%);
	}

	.search-combo input::placeholder,
	.composer textarea::placeholder {
		color: var(--theme-text-secondary);
	}

	.search-combo:focus-within,
	.composer textarea:focus {
		outline: none;
		border-color: rgba(var(--theme-primary-rgb), 0.42);
		box-shadow: 0 0 0 3px rgba(var(--theme-primary-rgb), 0.12);
	}

	.search-combo input:focus,
	.search-combo select:focus {
		outline: none;
		box-shadow: none;
	}

	.table-wrap,
	.flex-row,
	.compact-chip,
	.rail-status,
	.rail-actions,
	.progress-meta,
	.stage-banner,
	.session-header {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	.session-header,
	.stage-banner {
		justify-content: space-between;
		flex-wrap: wrap;
	}

	.subject-summary {
		flex: 1;
		min-width: 0;
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.75rem 1rem;
		flex-wrap: wrap;
	}

	.subject-summary-meta {
		display: flex;
		align-items: center;
		gap: 0.65rem;
		flex-wrap: wrap;
		min-width: 0;
	}

	.subject-summary-chip {
		display: inline-flex;
		align-items: center;
		padding: 0.45rem 0.8rem;
		border-radius: 999px;
		border: 1px solid var(--theme-glass-border);
		background: color-mix(in srgb, var(--theme-input-bg) 78%, var(--theme-surface) 22%);
		color: var(--theme-text-primary);
		font-size: 0.86rem;
		font-weight: 600;
		line-height: 1.2;
	}

	.subject-summary-count {
		margin-left: auto;
		white-space: nowrap;
	}

	.table-wrap {
		overflow-x: auto;
		border-radius: 16px;
		border: 1px solid var(--theme-glass-border);
		background: color-mix(in srgb, var(--theme-surface) 88%, transparent);
	}

	.chooser-table {
		width: 100%;
		min-width: 760px;
		border-collapse: collapse;
	}

	.chooser-table th,
	.chooser-table td {
		padding: 0.95rem 1rem;
		text-align: left;
		border-bottom: 1px solid color-mix(in srgb, var(--theme-glass-border) 82%, transparent);
		vertical-align: top;
	}

	.chooser-table th {
		font-size: 0.76rem;
		font-weight: 700;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: var(--theme-text-secondary);
		background: color-mix(in srgb, var(--theme-input-bg) 72%, var(--theme-surface) 28%);
	}

	.chooser-table tbody tr:hover {
		background: color-mix(in srgb, var(--theme-surface) 72%, rgba(var(--theme-primary-rgb), 0.06));
	}

	.clickable-row {
		cursor: pointer;
	}

	.clickable-row:focus-visible {
		outline: 2px solid rgba(var(--theme-primary-rgb), 0.5);
		outline-offset: -2px;
	}

	.chooser-table tbody tr:last-child td {
		border-bottom: none;
	}

	.table-title-stack {
		display: grid;
		gap: 0.3rem;
	}

	.table-title {
		color: var(--theme-text-primary);
		font-size: 0.98rem;
	}

	.table-description {
		font-size: 0.88rem;
		line-height: 1.45;
	}

	.scope-pill,
	.pill,
	.compact-chip {
		padding: 0.4rem 0.72rem;
		border-radius: 999px;
		font-size: 0.78rem;
		font-weight: 600;
		border: 1px solid var(--theme-glass-border);
		background: color-mix(in srgb, var(--theme-input-bg) 78%, var(--theme-surface) 22%);
		color: var(--theme-text-primary);
	}

	.pill.subtle,
	.pill.ghost,
	.back-chip {
		background: color-mix(in srgb, var(--theme-surface) 86%, transparent);
	}

	.pill.primary,
	.pill.strong {
		background: rgba(var(--theme-primary-rgb), 0.14);
		border-color: rgba(var(--theme-primary-rgb), 0.28);
		color: var(--theme-text-primary);
	}

	.pill:disabled,
	.back-chip:disabled,
	.composer-send:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.back-chip {
		display: inline-flex;
		justify-content: center;
		align-items: center;
		width: 40px;
		height: 40px;
		border-radius: 999px;
		border: 1px solid var(--theme-glass-border);
		color: var(--theme-text-primary);
		cursor: pointer;
	}

	.session-rail {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		padding: 0.55rem 0.85rem;
		position: sticky;
		top: 0.35rem;
		z-index: 6;
		border-radius: 14px;
	}

	.rail-icon-btn {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		padding: 0.4rem;
		border-radius: 10px;
		border: 1px solid var(--theme-glass-border);
		background: transparent;
		color: var(--theme-text-secondary);
		cursor: pointer;
		transition: background 0.15s, color 0.15s;
		flex-shrink: 0;
	}

	.rail-icon-btn:hover:not(:disabled) {
		background: color-mix(in srgb, var(--theme-surface) 80%, transparent);
		color: var(--theme-text-primary);
	}

	.rail-icon-btn:disabled {
		opacity: 0.4;
		cursor: not-allowed;
	}

	.rail-topic {
		font-size: 0.88rem;
		font-weight: 600;
		color: var(--theme-text-primary);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		max-width: 200px;
		flex-shrink: 0;
	}

	.rail-level-progress {
		display: flex;
		align-items: center;
		gap: 0.55rem;
		flex: 1;
		min-width: 0;
	}

	.rail-level-icon {
		color: var(--theme-text-secondary);
		flex-shrink: 0;
	}

	.rail-level-name {
		font-size: 0.82rem;
		font-weight: 600;
		color: var(--theme-text-primary);
		white-space: nowrap;
		flex-shrink: 0;
	}

	.rail-track {
		flex: 1;
		min-width: 60px;
	}

	.rail-count {
		font-size: 0.78rem;
		color: var(--theme-text-secondary);
		white-space: nowrap;
		flex-shrink: 0;
	}

	.session-panel {
		display: flex;
		flex-direction: column;
		min-height: 0;
		height: 100%;
		max-height: 100%;
		gap: 1rem;
		overflow: hidden;
	}

	.session-header {
		position: sticky;
		top: 0;
		z-index: 4;
		padding: 0.75rem 0.9rem;
		border: 1px solid var(--theme-glass-border);
		border-radius: 14px;
		background: color-mix(in srgb, var(--theme-input-bg) 74%, var(--theme-surface) 26%);
	}

	.question-copy {
		display: grid;
		gap: 0.25rem;
	}

	.progress-wrap {
		min-width: min(100%, 170px);
		flex: 0 1 170px;
	}

	.progress-meta {
		justify-content: space-between;
		font-size: 0.82rem;
		color: var(--theme-text-secondary);
		margin-bottom: 0.35rem;
	}

	.progress-track {
		height: 7px;
		border-radius: 999px;
		background: rgba(0, 0, 0, 0.15);
		overflow: hidden;
	}

	:global([data-color-mode='dark']) .progress-track {
		background: rgba(255, 255, 255, 0.14);
	}

	.progress-bar {
		height: 100%;
		border-radius: inherit;
		background: rgba(var(--theme-primary-rgb), 0.9);
	}

	.progress-bar.advanced {
		background: rgba(245, 158, 11, 0.9);
	}

	.progress-bar.pro {
		background: rgba(168, 85, 247, 0.9);
	}

	.hint-banner {
		padding: 0.85rem 0.95rem;
		border-radius: 14px;
		background: color-mix(in srgb, var(--theme-input-bg) 78%, rgba(var(--theme-primary-rgb), 0.08));
		border: 1px solid color-mix(in srgb, var(--theme-glass-border) 72%, rgba(var(--theme-primary-rgb), 0.18));
		color: var(--theme-text-primary);
		font-size: 0.92rem;
	}

	.message-viewport {
		flex: 1;
		min-height: 0;
		overflow-y: auto;
		display: flex;
		flex-direction: column;
		gap: 0.85rem;
		padding-right: 0.2rem;
		padding-bottom: 0.4rem;
	}

	.message-row {
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
		max-width: min(84%, 760px);
	}

	.message-row.user {
		align-self: flex-end;
	}

	.message-bubble {
		padding: 0.95rem 1rem;
		border-radius: 18px;
		border: 1px solid rgba(0, 0, 0, 0.1);
		background: rgba(0, 0, 0, 0.07);
		color: var(--theme-text-primary);
		line-height: 1.6;
	}

	.message-row.user .message-bubble {
		background: rgba(var(--theme-primary-rgb), 0.12);
		border-color: rgba(var(--theme-primary-rgb), 0.22);
	}

	:global([data-color-mode='dark']) .message-bubble {
		background: color-mix(in srgb, var(--theme-input-bg) 60%, var(--theme-surface) 40%);
		border-color: var(--theme-glass-border);
	}

	:global([data-color-mode='dark']) .message-row.user .message-bubble {
		background: color-mix(in srgb, rgba(var(--theme-primary-rgb), 0.18) 60%, var(--theme-input-bg) 40%);
		border-color: rgba(var(--theme-primary-rgb), 0.28);
	}

	.stage-banner {
		padding: 0.95rem 1rem;
		border-radius: 16px;
		border: 1px solid var(--theme-glass-border);
		background: color-mix(in srgb, var(--theme-input-bg) 74%, var(--theme-surface) 26%);
	}

	.success-banner {
		background: color-mix(in srgb, rgba(34, 197, 94, 0.12) 44%, var(--theme-input-bg) 56%);
		border-color: rgba(34, 197, 94, 0.22);
	}

	.completion-banner {
		background: color-mix(in srgb, rgba(168, 85, 247, 0.12) 44%, var(--theme-input-bg) 56%);
		border-color: rgba(168, 85, 247, 0.22);
	}

	.composer {
		display: grid;
		grid-template-columns: minmax(0, 1fr) auto;
		gap: 0.85rem;
		align-items: flex-end;
		position: sticky;
		bottom: 0;
		z-index: 5;
		padding-top: 0.9rem;
		background: linear-gradient(
			to top,
			color-mix(in srgb, var(--theme-nav-glass) 98%, transparent),
			color-mix(in srgb, var(--theme-nav-glass) 90%, transparent)
		);
		border-top: 1px solid color-mix(in srgb, var(--theme-glass-border) 72%, transparent);
	}

	.composer textarea {
		height: 96px;
		min-height: 96px;
		resize: none;
	}

	.composer textarea:disabled {
		opacity: 0.55;
	}

	.composer-send {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		gap: 0.45rem;
		padding: 0.85rem 1rem;
		border-radius: 14px;
		border: 1px solid rgba(var(--theme-primary-rgb), 0.24);
		background: color-mix(in srgb, var(--theme-surface) 82%, rgba(var(--theme-primary-rgb), 0.12));
		color: var(--theme-text-primary);
		font-weight: 700;
		cursor: pointer;
		min-width: 120px;
		box-shadow: none;
	}

	.center-state {
		display: grid;
		place-items: center;
		gap: 0.55rem;
		text-align: center;
	}

	.large-state {
		padding: 2.6rem 1.5rem;
	}

	.inline-state {
		border: 1px dashed var(--theme-glass-border);
		border-radius: 18px;
	}

	.error-panel {
		justify-content: space-between;
		gap: 0.8rem;
		background: rgba(239, 68, 68, 0.08);
		border-color: rgba(248, 113, 113, 0.24);
	}

	.error-panel.compact {
		padding: 0.9rem 1rem;
	}

	.error-panel.inside-session {
		margin-bottom: 0.1rem;
	}

	.flex-row {
		color: #b91c1c;
	}

	.spinner {
		width: 42px;
		height: 42px;
		border-radius: 50%;
		border: 3px solid rgba(var(--theme-primary-rgb), 0.14);
		border-top-color: rgba(var(--theme-primary-rgb), 0.84);
		animation: spin 0.8s linear infinite;
	}

	/* ── Typing indicator (iMessage-style bouncing dots) ── */
	.typing-bubble {
		display: flex;
		align-items: center;
		gap: 5px;
		min-width: 58px;
	}

	.typing-dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		background: var(--theme-text-secondary);
		opacity: 0.55;
		animation: typing-bounce 1.3s ease-in-out infinite;
		flex-shrink: 0;
	}

	.typing-dot:nth-child(2) { animation-delay: 0.18s; }
	.typing-dot:nth-child(3) { animation-delay: 0.36s; }

	@keyframes typing-bounce {
		0%, 55%, 100% { transform: translateY(0); opacity: 0.55; }
		28% { transform: translateY(-7px); opacity: 1; }
	}

	/* ── Session progress divider ("Moving on", "Next up", …) ── */
	.session-divider {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		align-self: stretch;
		margin: 0.35rem 0;
	}

	.session-divider::before,
	.session-divider::after {
		content: '';
		flex: 1;
		height: 1px;
		background: color-mix(in srgb, var(--theme-glass-border) 80%, transparent);
	}

	.session-divider-pill {
		font-size: 0.74rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.1em;
		white-space: nowrap;
		color: var(--theme-text-secondary);
		padding: 0.28rem 0.82rem;
		border-radius: 999px;
		border: 1px solid var(--theme-glass-border);
		background: color-mix(in srgb, var(--theme-input-bg) 78%, var(--theme-surface) 22%);
	}

	@keyframes spin {
		0% { transform: rotate(0deg); }
		100% { transform: rotate(360deg); }
	}

	@media (max-width: 900px) {
		.rail-row,
		.panel-header,
		.session-header,
		.stage-banner {
			flex-direction: column;
			align-items: stretch;
		}

		.subject-header-bar {
			flex-direction: column;
			align-items: stretch;
		}

		.subject-summary {
			width: 100%;
		}

		.subject-summary-count {
			margin-left: 0;
		}

		.search-combo {
			flex-direction: column;
			align-items: stretch;
		}

		.search-combo-divider {
			width: auto;
			height: 1px;
		}

		.search-combo select {
			max-width: none;
			min-width: 0;
		}

		.rail-actions,
		.rail-status {
			justify-content: flex-start;
		}
	}

	@media (max-width: 768px) {
		.gradient-card {
			flex-direction: column;
		}

		.hero-metrics {
			width: 100%;
			justify-content: stretch;
		}

		.chooser-table {
			min-width: 640px;
		}

		.composer {
			grid-template-columns: 1fr;
		}

		.composer-send {
			width: 100%;
		}

		.message-row {
			max-width: 100%;
		}
	}
</style>
