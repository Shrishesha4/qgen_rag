<script lang="ts">
	import { onDestroy, onMount, tick } from 'svelte';
	import {
		AlertCircle,
		ArrowLeft,
		BookOpen,
		Brain,
		ChevronRight,
		RefreshCw,
		Send,
		Sparkles,
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
			if (questionStartIndex > 0) {
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

	let messageViewport = $state<HTMLDivElement | null>(null);
	let streamAbortController: AbortController | null = null;

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
	const filteredSubjects = $derived.by(() => {
		const query = subjectSearch.trim().toLowerCase();
		if (!query) return subjects;
		return subjects.filter((subject) =>
			[
				subject.name,
				subject.code,
				subject.description ?? '',
				subject.groupLabel ?? '',
			]
				.join(' ')
				.toLowerCase()
				.includes(query)
		);
	});

	onMount(() => {
		void loadSubjects();
	});

	onDestroy(() => {
		abortActiveStream();
	});

	$effect(() => {
		messages.length;
		void tick().then(() => {
			messageViewport?.scrollTo({ top: messageViewport.scrollHeight, behavior: 'smooth' });
		});
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
		await openLevel();
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
		}
	}

	async function requestNextQuestion(history: InquiryMessage[] = messages) {
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

		if (nextCompletedTurnCount >= activeLevel.targetTurns) {
			return;
		}

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

		const advanced = reasoningResult.directive === 'advance' || nextAttempt >= MAX_EXPLANATION_ATTEMPTS;
		if (!advanced) {
			currentQuestionAttempt = nextAttempt;
			sessionHint = null;
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
		await requestNextQuestion([]);
	}
</script>

<svelte:head>
	<title>GEL Train | Student Console</title>
</svelte:head>

<div class="page-container student-shell train-shell" class:in-session={!!selectedTopic}>
	<!-- {#if !selectedTopic}
		<section class="glass-panel gradient-card hero-card">
			<div>
				<p class="eyebrow">GEL Train</p>
				<h1 class="hero">Guided practice from your configured AI providers</h1>
				<p class="muted hero-copy">
					Move from subject to topic into a live tutoring session while staying inside the current VQuest shell and using only the Admin-configured provider stack.
				</p>
			</div>
			<div class="hero-metrics">
				<div>
					<p class="summary-value">{subjects.length}</p>
					<p class="summary-label">Subjects ready</p>
				</div>
				<div>
					<p class="summary-value provider-label">{providerMeta ? providerMeta.name : 'Admin'}</p>
					<p class="summary-label">{providerMeta ? providerMeta.model || 'Configured connector' : 'Provider source'}</p>
				</div>
				<div>
					<p class="summary-value">{completedLevelCount}/3</p>
					<p class="summary-label">Stages cleared</p>
				</div>
			</div>
		</section>
	{/if} -->

	{#if !selectedSubject}
		<section class="glass-panel chooser-panel space-y-5">
			<header class="panel-header">
				<div class="section-title-wrap">
					<div class="icon-pill"><Sparkles class="h-5 w-5" /></div>
					<div>
						<p class="panel-label">Step 1</p>
						<h2 class="panel-title">Choose a subject</h2>
						<p class="muted">Subjects come from the trainer backend, not the reference app's hardcoded list.</p>
					</div>
				</div>
				<div class="search-box">
					<input
						type="text"
						bind:value={subjectSearch}
						placeholder="Search by subject, code, or group"
					/>
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
			{:else if filteredSubjects.length === 0}
				<div class="center-state large-state">
					<BookOpen class="h-10 w-10 icon-muted" />
					<h3 class="empty-title">No subjects found</h3>
					<p class="muted">Add or search for subjects in the main trainer workspace, then return here.</p>
				</div>
			{:else}
				<div class="subject-grid">
					{#each filteredSubjects as subject}
						<button class="selection-card subject-card" onclick={() => selectSubject(subject)}>
							<div class="card-topline">
								<span class="pill subtle">{subject.code}</span>
								{#if subject.groupLabel}
									<span class="group-pill">{subject.groupLabel}</span>
								{/if}
							</div>
							<h3>{subject.name}</h3>
							<p>{subject.description || 'Open this subject to choose a topic or study across the full subject.'}</p>
							<div class="card-meta">
								<span>{subject.total_topics} topics</span>
								<span>{subject.total_questions} generated items</span>
							</div>
						</button>
					{/each}
				</div>
			{/if}
		</section>
	{:else if !selectedTopic}
		<section class="glass-panel chooser-panel space-y-5">
			<header class="panel-header with-action">
				<div class="section-title-wrap">
					<button class="back-chip" onclick={backToSubjects} aria-label="Back to subjects">
						<ArrowLeft class="h-4 w-4" />
					</button>
					<div class="icon-pill secondary"><BookOpen class="h-5 w-5" /></div>
					<div>
						<p class="panel-label">Step 2</p>
						<h2 class="panel-title">Choose a topic for {selectedSubject.name}</h2>
						<p class="muted">Pick a specific topic or start broad across the entire subject.</p>
					</div>
				</div>
				<div class="subject-summary">
					<span>{selectedSubject.code}</span>
					<span>{selectedSubject.total_topics} topics</span>
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
			{:else}
				<div class="topic-grid">
					{#each topics as topic}
						<button class="selection-card topic-card" onclick={() => startTopicSession(topic)}>
							<div class="card-topline">
								<span class="pill subtle">{topic.scope === 'subject' ? 'Broad mode' : 'Topic mode'}</span>
								{#if topic.total_questions !== null}
									<span class="group-pill">{topic.total_questions} items</span>
								{/if}
							</div>
							<h3>{topic.name}</h3>
							<p>{topic.description || 'Start a guided practice session in this scope.'}</p>
							<div class="card-link">
								<span>Start session</span>
								<ChevronRight class="h-4 w-4" />
							</div>
						</button>
					{/each}
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
				{#if messages.length === 0 && isStreaming}
					<div class="center-state large-state inline-state">
						<div class="spinner"></div>
						<p class="muted">Generating your first question...</p>
					</div>
				{:else if messages.length === 0}
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
	.selection-card p,
	.card-meta,
	.card-link,
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

	.search-box {
		flex: 0 1 320px;
	}

	.search-box input,
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

	:global([data-color-mode='dark']) .search-box input,
	:global([data-color-mode='dark']) .composer textarea {
		border-color: var(--theme-glass-border);
		background: color-mix(in srgb, var(--theme-input-bg) 55%, var(--theme-surface) 45%);
	}

	.search-box input::placeholder,
	.composer textarea::placeholder {
		color: var(--theme-text-secondary);
	}

	.search-box input:focus,
	.composer textarea:focus {
		outline: none;
		border-color: rgba(var(--theme-primary-rgb), 0.42);
		box-shadow: 0 0 0 3px rgba(var(--theme-primary-rgb), 0.12);
	}

	.subject-grid,
	.topic-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
		gap: 1rem;
	}

	.selection-card {
		text-align: left;
		padding: 1.1rem;
		border-radius: 18px;
		border: 1px solid var(--theme-glass-border);
		background: color-mix(in srgb, var(--theme-surface) 90%, transparent);
		color: var(--theme-text-primary);
		transition: transform 0.18s ease, border-color 0.18s ease, background 0.18s ease;
		cursor: pointer;
	}

	.selection-card:hover {
		transform: translateY(-2px);
		border-color: rgba(var(--theme-primary-rgb), 0.38);
		background: color-mix(in srgb, var(--theme-surface) 84%, rgba(var(--theme-primary-rgb), 0.08));
	}

	.selection-card h3 {
		margin: 0.45rem 0 0.45rem;
		font-size: 1.08rem;
		font-weight: 700;
		color: var(--theme-text-primary);
	}

	.card-topline,
	.card-meta,
	.card-link,
	.subject-summary,
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

	.card-topline,
	.card-meta,
	.subject-summary,
	.session-header,
	.stage-banner {
		justify-content: space-between;
		flex-wrap: wrap;
	}

	.card-link {
		justify-content: flex-end;
		margin-top: 0.9rem;
		font-weight: 600;
	}

	.group-pill,
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
