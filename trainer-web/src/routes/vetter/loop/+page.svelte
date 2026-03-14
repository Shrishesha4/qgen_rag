<script lang="ts">
	import { onMount, tick } from 'svelte';
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

	let subjectId = $state('');
	let topicId = $state('');

	// Confirm before navigating away with unfinished work
	beforeNavigate(({ cancel }) => {
		if (submitting || (totalReviewed > 0 && totalReviewed < questions.length)) {
			if (!confirm('You have unfinished vetting progress. Leave and discard?')) {
				cancel();
				return;
			}
		}
	});

	onMount(() => {
		const unsub = session.subscribe((s) => {
			if (!s || s.user.role !== 'vetter') goto('/vetter/login');
		});
		const unsubPage = page.subscribe((p) => {
			subjectId = p.url.searchParams.get('subject') ?? '';
			topicId = p.url.searchParams.get('topic') ?? '';
		});
		loadQuestions();

		function handleBeforeUnload(e: BeforeUnloadEvent) {
			if (submitting || (totalReviewed > 0 && totalReviewed < questions.length)) {
				e.preventDefault();
			}
		}
		window.addEventListener('beforeunload', handleBeforeUnload);

		return () => {
			unsub();
			unsubPage();
			window.removeEventListener('beforeunload', handleBeforeUnload);
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

	// Regeneration state
	let regenerating = $state(false);

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

	let voiceAction = $state<PendingVoiceAction | null>(null);

	let currentQuestion = $derived(questions[currentIndex]);
	let totalReviewed = $derived(approved.size + rejected.size);
	let progressPct = $derived(questions.length > 0 ? Math.round((totalReviewed / questions.length) * 100) : 0);
	let isReviewed = $derived(
		currentQuestion ? approved.has(currentQuestion.id) || rejected.has(currentQuestion.id) : false
	);
	let showAllCaughtUp = $derived(questions.length > 0 && totalReviewed >= questions.length);
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

	async function loadQuestions() {
		loading = true;
		error = '';
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
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to load questions';
		} finally {
			loading = false;
		}
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
			error = e instanceof Error ? e.message : 'Failed to regenerate question';
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

	function replaceCurrentQuestion(replacement: QuestionForVetting) {
		questions = questions.map((question, index) => (index === currentIndex ? replacement : question));
		showSources = false;
		editing = false;
		activeOptionEditIndex = null;
	}

	function advance() {
		showSources = false;
		editing = false;
		voiceAction = null;
		for (let i = currentIndex + 1; i < questions.length; i++) {
			if (!approved.has(questions[i].id) && !rejected.has(questions[i].id)) {
				currentIndex = i;
				return;
			}
		}
		for (let i = 0; i < currentIndex; i++) {
			if (!approved.has(questions[i].id) && !rejected.has(questions[i].id)) {
				currentIndex = i;
				return;
			}
		}
		if (currentIndex < questions.length - 1) {
			currentIndex++;
		}
	}

	function finish() {
		goto('/vetter/dashboard');
	}

	function goBack() {
		if (subjectId) {
			goto(`/vetter/subjects/${subjectId}`);
		} else {
			goto('/vetter/subjects');
		}
	}

	function isCorrectOption(opt: string, correctAnswer: string | null): boolean {
		return normalizeCorrectAnswer(correctAnswer, currentQuestion?.options ?? []) === normalizeCorrectAnswer(opt, [opt]);
	}
</script>

<svelte:head>
	<title>Vetting — QGen Vetter</title>
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
			<button class="glass-btn" onclick={loadQuestions}>Retry</button>
		</div>
	{:else if questions.length === 0}
		<div class="empty-state">
			<span class="empty-icon">✅</span>
			<p>No pending questions to review</p>
			<p class="sub-text">All questions have been vetted</p>
			<button class="glass-btn" onclick={goBack}>← Go Back</button>
		</div>
	{:else if showAllCaughtUp}
		<div class="caught-up-panel glass-panel animate-fade-in">
			<span class="caught-up-kicker">Review complete</span>
			<h2 class="caught-up-title font-serif">All Caught Up</h2>
			<p class="caught-up-copy">Every question in this queue has been reviewed.</p>
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
						<textarea class="edit-textarea" bind:value={editExplanation} rows="2"></textarea>

						<div class="edit-actions">
							<button class="edit-footer-btn edit-cancel-btn" onclick={cancelEdit}>Cancel</button>
							<button class="edit-footer-btn edit-save-btn" onclick={submitEdit} disabled={submitting}>
								{submitting ? 'Saving...' : 'Save'}
							</button>
						</div>
					</div>
				{:else}
					<p class="q-text font-serif">{currentQuestion.question_text}</p>

					{#if currentQuestion.options}
						<div class="answer-panel glass-panel">
							<div class="answer-panel-head">
								<span class="answer-panel-title">Answer Options</span>
							</div>
							<div class="options">
							{#each currentQuestion.options as opt, idx}
								<div class="option" class:correct={isCorrectOption(opt, currentQuestion.correct_answer)}>
									<span class="opt-marker">{isCorrectOption(opt, currentQuestion.correct_answer) ? '✓' : getOptionIdentifier(opt, idx)}</span>
									<span>{opt}</span>
								</div>
							{/each}
							</div>
						</div>
					{:else if currentQuestion.correct_answer}
						<div class="answer-box">
							<span class="answer-label">Answer:</span>
							<span class="answer-text">{currentQuestion.correct_answer}</span>
						</div>
					{/if}

					{#if currentQuestion.explanation}
						<div class="explanation">
							<span class="expl-label">Explanation</span>
							<p class="expl-text">{currentQuestion.explanation}</p>
						</div>
					{/if}

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

			<!-- Action buttons -->
			{#if !isReviewed && !editing && !regenerating}
				<!-- <div class="edit-inline-row">
					<button class="edit-inline-btn" onclick={startEdit}>Edit question</button>
				</div> -->
				<div class="grading-grid">
					<button class="grade-card easy" onclick={() => openApprovalRecorder('easy')} disabled={submitting}>
						<span class="grade-badge">E</span>
						<span class="grade-label">Easy</span>
					</button>
					<button class="grade-card medium" onclick={() => openApprovalRecorder('medium')} disabled={submitting}>
						<span class="grade-badge">M</span>
						<span class="grade-label">Medium</span>
					</button>
					<button class="grade-card hard" onclick={() => openApprovalRecorder('hard')} disabled={submitting}>
						<span class="grade-badge">H</span>
						<span class="grade-label">Hard</span>
					</button>
					<button class="grade-card reject" onclick={openRejectRecorder} disabled={submitting}>
						<span class="grade-badge">×</span>
						<span class="grade-label">Reject</span>
					</button>
				</div>
			{:else if isReviewed}
				<div class="actions">
					{#if currentIndex < questions.length - 1}
						<button class="glass-btn" onclick={() => { advance(); }} style="padding: 0.75rem 2rem;">
							Next Question →
						</button>
					{/if}
				</div>
			{/if}

		{:else}
			<div class="empty-state">
				<span class="empty-icon">✅</span>
				<p>No more questions to review</p>
				<button class="glass-btn" onclick={goBack}>← Go Back</button>
			</div>
		{/if}
	{/if}
</div>

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
		padding: 2rem 1.5rem;
		display: flex;
		flex-direction: column;
		gap: 1.5rem;
		min-height: 100vh;
	}

	.q-text {
		font-size: 1.05rem;
		line-height: 1.6;
		color: var(--theme-text);
		margin: 0 0 1.25rem;
		font-weight: 500;
	}

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

	.option.correct {
		background: rgba(72, 192, 80, 0.15);
		border: 0.5px solid rgba(72, 192, 80, 0.3);
	}

	.opt-marker {
		width: 20px;
		text-align: center;
		font-weight: 700;
		flex-shrink: 0;
	}

	.option.correct .opt-marker {
		color: #2cda38;
	}

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
	.actions {
		display: flex;
		gap: 1rem;
		justify-content: center;
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

	.edit-option-row .edit-input { flex: 1; }

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
		.edit-actions {
			justify-content: stretch;
		}

		.caught-up-stats {
			grid-template-columns: 1fr;
		}

		.edit-footer-btn {
			flex: 1;
		}
	}

	/* Sources */
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

	.sources-toggle:hover { background: rgba(255, 255, 255, 0.08); }

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


	/* States */
	.center-state {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.75rem;
		padding: 4rem 1rem;
		text-align: center;
	}

	.center-state p { color: var(--theme-text-muted); margin: 0; }
	.sub-text { font-size: 0.85rem; color: var(--theme-text-muted); opacity: 0.7; margin: 0; }
	.err-icon { font-size: 2rem; }
	.err-msg { color: #f07888; }

	.spinner {
		width: 32px; height: 32px;
		border: 3px solid rgba(255, 255, 255, 0.1);
		border-top-color: var(--theme-primary);
		border-radius: 50%;
		animation: spin 0.7s linear infinite;
	}
	@keyframes spin { to { transform: rotate(360deg); } }

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

	.empty-state {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 1rem;
		padding: 4rem 1rem;
		text-align: center;
	}
	.empty-icon { font-size: 3rem; }
	.empty-state p { color: var(--theme-text-muted); margin: 0; }

	.err-banner {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.5rem 0.75rem;
		background: rgba(233, 69, 96, 0.15);
		border: 1px solid rgba(233, 69, 96, 0.25);
		border-radius: 8px;
	}

	.err-banner .err-msg { flex: 1; font-size: 0.82rem; }

	.err-dismiss {
		background: none;
		border: none;
		color: var(--theme-text-muted);
		cursor: pointer;
		font-size: 1rem;
		padding: 0.2rem;
		font-family: inherit;
	}

	.loop-page {
		max-width: 1024px;
		padding-top: 2rem;
		padding-bottom: 3rem;
	}

	.loop-hero {
		display: flex;
		justify-content: center;
		align-items: center;
		gap: 1rem;
		flex-wrap: wrap;
		padding-top: 0.15rem;
	}

	.hero-copy {
		display: flex;
		flex-direction: column;
		gap: 0;
		align-items: center;
		width: auto;
	}
/* 
	.back-link {
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
		display: flex;
		align-items: center;
		gap: 0.4rem;
	}

	.back-link svg {
		flex-shrink: 0;
	} */

	.hero-title {
		margin: 0;
		font-size: clamp(2.8rem, 6vw, 4rem);
		line-height: 0.95;
		color: var(--theme-text);
		text-align: center;
	}


	.progress-pill {
		position: static;
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
		font-size: clamp(2.1rem, 3.3vw, 3.2rem);
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
		background: rgba(255, 255, 255, 0.1);
	}

	.option.correct {
		background: rgba(62, 153, 117, 0.24);
		border-color: rgba(49, 208, 161, 0.4);
	}

	.option.correct .opt-marker {
		background: rgba(49, 208, 161, 0.22);
		color: #d3fff1;
	}
/* 
	.edit-inline-row {
		display: flex;
		justify-content: flex-end;
		margin-top: 1rem;
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
		margin-top: 1rem;
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

	@media (max-width: 768px) {
		.loop-page {
			padding: 1.25rem 1rem;
			padding-bottom: 2rem;
			gap: 1rem;
		}

		.loop-hero {
			justify-content: center;
			align-items: center;
			gap: 0.65rem;
			padding-top: 0;
		}
/* 
		.back-link {
			flex-shrink: 0;
			width: 2.25rem;
			height: 2.25rem;
			padding: 0.5rem;
			border-radius: 0.5rem;
			background: rgba(255, 255, 255, 0.1);
			border: 1px solid rgba(255, 255, 255, 0.15);
			justify-content: center;
		}

		.back-link-text {
			display: none;
		} */

		.hero-copy {
			min-width: 0;
			gap: 0;
			width: auto;
		}

		.hero-title {
			font-size: clamp(0.75rem, 4vw, 2rem);
			white-space: nowrap;
		}

		.progress-pill {
			position: static;
			flex-shrink: 0;
			min-width: auto;
			padding: 0.55rem 0.75rem;
		}

		.progress-pill-count {
			font-size: 0.95rem;
		}

		.progress-pill-track {
			min-width: 2.5rem;
		}

		.question-card {
			padding: 1.25rem;
			border-radius: 1.5rem;
		}

		.q-context {
			gap: 0.6rem;
			margin-bottom: 1rem;
		}

		.q-pill {
			padding: 0.5rem 0.75rem;
			font-size: 0.85rem;
		}

		.q-meta-inline {
			font-size: 0.8rem;
		}

		.q-text {
			font-size: clamp(1.4rem, 5vw, 2rem);
			line-height: 1.25;
			margin-bottom: 1.25rem;
		}

		.answer-panel {
			padding: 1rem;
			border-radius: 1.25rem;
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

		.opt-marker {
			width: 1.8rem;
			height: 1.8rem;
			font-size: 0.85rem;
		}

		.grading-grid {
			grid-template-columns: repeat(2, 1fr);
			gap: 0.6rem;
		}

		.grade-card {
			min-height: 6rem;
			border-radius: 1rem;
			padding: 0.75rem;
		}

		.grade-badge {
			width: 2.5rem;
			height: 2.5rem;
			font-size: 1.4rem;
		}

		.grade-label {
			font-size: 0.85rem;
		}

		.caught-up-panel {
			padding: 1.5rem 1rem;
		}

		.caught-up-title {
			font-size: clamp(1.75rem, 6vw, 2.5rem);
		}

		.caught-up-stats {
			grid-template-columns: repeat(3, 1fr);
			gap: 0.5rem;
		}

		.caught-up-stat {
			padding: 0.75rem 0.5rem;
		}

		.caught-up-value {
			font-size: 1.4rem;
		}

		.caught-up-label {
			font-size: 0.7rem;
		}

		.edit-actions {
			flex-direction: column;
			gap: 0.5rem;
		}

		.edit-footer-btn {
			width: 100%;
			min-width: auto;
		}

		.explanation {
			padding: 0.65rem 0.85rem;
		}

		.expl-text {
			font-size: 0.85rem;
		}
	}

	@media (max-width: 480px) {
		.loop-page {
			padding: 0.75rem 0.75rem;
			gap: 0.85rem;
		}

		.loop-hero {
			gap: 0.5rem;
		}

		/* .back-link {
			width: 2rem;
			height: 2rem;
			padding: 0.45rem;
			border-radius: 0.4rem;
		}

		.back-link svg {
			width: 14px;
			height: 14px;
		} */

		.hero-copy {
			overflow: hidden;
		}

		.hero-title {
			font-size: 1.1rem;
			line-height: 1;
			white-space: normal;
		}

		.progress-pill {
			position: static;
			padding: 0.4rem 0.55rem;
			gap: 0.4rem;
			min-width: auto;
		}

		.progress-pill-count {
			font-size: 0.8rem;
		}

		.progress-pill-track {
			height: 0.25rem;
			min-width: 2rem;
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
			grid-template-columns: repeat(2, 1fr);
			gap: 0.5rem;
			margin-top: 0.75rem;
		}

		.grade-card {
			min-height: 5rem;
			border-radius: 0.85rem;
			gap: 0.5rem;
		}

		.grade-badge {
			width: 2rem;
			height: 2rem;
			font-size: 1.15rem;
		}

		.grade-label {
			font-size: 0.75rem;
		}

		.caught-up-panel {
			padding: 1.25rem 0.85rem;
			border-radius: 1.25rem;
		}

		.caught-up-kicker {
			font-size: 0.65rem;
		}

		.caught-up-title {
			font-size: 1.5rem;
		}

		.caught-up-copy {
			font-size: 0.85rem;
		}

		.caught-up-stats {
			gap: 0.4rem;
		}

		.caught-up-stat {
			padding: 0.6rem 0.4rem;
			border-radius: 0.75rem;
		}

		.caught-up-value {
			font-size: 1.2rem;
		}

		.caught-up-label {
			font-size: 0.65rem;
		}

		.finish-btn {
			padding: 0.7rem 1.5rem;
			font-size: 0.9rem;
		}

		.edit-section {
			gap: 0.5rem;
		}

		.edit-label {
			font-size: 0.7rem;
		}

		.edit-textarea,
		.edit-input {
			font-size: 0.85rem;
			padding: 0.5rem 0.7rem;
		}

		.edit-option-row {
			gap: 0.35rem;
		}

		.opt-correct-btn {
			min-width: 32px;
			height: 28px;
			font-size: 0.75rem;
		}

		.edit-option-pencil {
			width: 28px;
			height: 28px;
		}

		.edit-footer-btn {
			padding: 0.7rem 1rem;
			font-size: 0.9rem;
			border-radius: 12px;
		}

		.explanation {
			padding: 0.6rem 0.75rem;
			margin-top: 0.75rem;
		}

		.expl-label {
			font-size: 0.65rem;
		}

		.expl-text {
			font-size: 0.82rem;
		}

		.sources-toggle {
			font-size: 0.75rem;
			padding: 0.4rem 0.6rem;
		}

		.source-card {
			padding: 0.5rem 0.65rem;
		}

		.source-doc {
			font-size: 0.75rem;
		}

		.source-highlight,
		.source-snippet {
			font-size: 0.75rem;
		}

		.center-state,
		.empty-state {
			padding: 3rem 0.75rem;
		}

		.empty-icon {
			font-size: 2.5rem;
		}

		.regen-overlay {
			padding: 2rem 1rem;
			border-radius: 1.25rem;
		}

		.regen-text {
			font-size: 0.88rem;
		}
	}

	@media (max-width: 380px) {
		.loop-hero {
			transform: translateX(0.35rem);
		}
	}
</style>
