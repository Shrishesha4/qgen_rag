<script lang="ts">
	import { onMount } from 'svelte';
	import { goto, beforeNavigate } from '$app/navigation';
	import { page } from '$app/stores';
	import { session } from '$lib/session';
	import PageHeader from '$lib/components/PageHeader.svelte';
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

	// Edit mode
	let editing = $state(false);
	let editText = $state('');
	let editOptions = $state<string[]>([]);
	let editAnswer = $state('');
	let editExplanation = $state('');
	let optionInputRefs = $state<Array<HTMLInputElement | null>>([]);

	// Source references
	let showSources = $state(false);

	// Rejection feedback modal
	let showRejectModal = $state(false);
	let rejectFeedback = $state('');
	let rejectReasons = $state<string[]>([]);
	let rejectGenerateNew = $state(false);
	let rejectSubmitting = $state(false);

	const REJECTION_REASONS = [
		'Incorrect answer',
		'Ambiguous question',
		'Too vague',
		'Out of scope',
		'Poor difficulty level',
		'Grammar/spelling issues',
		'Duplicate concept',
		'Missing key details',
	];

	let currentQuestion = $derived(questions[currentIndex]);
	let totalReviewed = $derived(approved.size + rejected.size);
	let progressPct = $derived(questions.length > 0 ? Math.round((totalReviewed / questions.length) * 100) : 0);
	let isReviewed = $derived(
		currentQuestion ? approved.has(currentQuestion.id) || rejected.has(currentQuestion.id) : false
	);

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

	function focusOptionInput(index: number) {
		optionInputRefs[index]?.focus();
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
		editAnswer = normalizeCorrectAnswer(currentQuestion.correct_answer, editOptions);
		editExplanation = currentQuestion.explanation ?? '';
	}

	function cancelEdit() {
		editing = false;
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
			advance();
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to submit edit';
		} finally {
			submitting = false;
		}
	}

	async function approve() {
		if (!currentQuestion || submitting) return;
		submitting = true;
		try {
			await submitVetting({
				question_id: currentQuestion.id,
				decision: 'approve',
			});
			approved = new Set([...approved, currentQuestion.id]);
			advance();
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to submit';
		} finally {
			submitting = false;
		}
	}

	function openRejectModal() {
		if (!currentQuestion) return;
		rejectFeedback = '';
		rejectReasons = [];
		rejectGenerateNew = false;
		showRejectModal = true;
	}

	function closeRejectModal() {
		showRejectModal = false;
		rejectFeedback = '';
		rejectReasons = [];
		rejectGenerateNew = false;
	}

	function toggleReason(reason: string) {
		if (rejectReasons.includes(reason)) {
			rejectReasons = rejectReasons.filter(r => r !== reason);
		} else {
			rejectReasons = [...rejectReasons, reason];
		}
	}

	async function submitRejection() {
		if (!currentQuestion || rejectSubmitting) return;
		if (!rejectFeedback.trim() && rejectReasons.length === 0) {
			error = 'Please provide feedback or select at least one reason';
			return;
		}
		rejectSubmitting = true;
		error = '';
		try {
			const result = await rejectWithFeedback(currentQuestion.id, {
				feedback: rejectFeedback.trim() || rejectReasons.join('; '),
				rejection_reasons: rejectReasons.length > 0 ? rejectReasons : undefined,
				generate_new: rejectGenerateNew,
			});

			if (result.improved && result.improved_text) {
				const updatedQ = { ...currentQuestion };
				updatedQ.question_text = result.improved_text;
				if (result.improved_options) updatedQ.options = result.improved_options;
				if (result.improved_answer) updatedQ.correct_answer = result.improved_answer;
				if (result.improved_explanation) updatedQ.explanation = result.improved_explanation;
				updatedQ.vetting_status = 'pending';
				questions = questions.map(q => q.id === currentQuestion!.id ? updatedQ : q);
			} else if (result.regenerated && result.new_question_id) {
				rejected = new Set([...rejected, currentQuestion.id]);
				advance();
			} else {
				rejected = new Set([...rejected, currentQuestion.id]);
				advance();
			}
			closeRejectModal();
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to submit rejection';
		} finally {
			rejectSubmitting = false;
		}
	}

	function advance() {
		showSources = false;
		editing = false;
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

<PageHeader title="Vetting" backHref={subjectId ? `/vetter/subjects/${subjectId}` : '/vetter/subjects'} />

<div class="loop-page">
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
	{:else}
		<!-- Progress header -->
		<div class="loop-header">
			<div class="batch-info">
				<span class="batch-label">Review Queue</span>
				<span class="review-count">{totalReviewed}/{questions.length} reviewed</span>
			</div>
			<div class="progress-track">
				<div class="progress-fill" style:width="{progressPct}%"></div>
			</div>
			{#if currentQuestion?.subject_name || currentQuestion?.topic_name}
				<div class="context-info">
					{#if currentQuestion.subject_name}
						<span class="ctx-badge">{currentQuestion.subject_name}</span>
					{/if}
					{#if currentQuestion.topic_name}
						<span class="ctx-badge topic">{currentQuestion.topic_name}</span>
					{/if}
				</div>
			{/if}
		</div>

		{#if error}
			<div class="err-banner">
				<span class="err-msg">{error}</span>
				<button class="err-dismiss" onclick={() => error = ''}>✕</button>
			</div>
		{/if}

		{#if currentQuestion}
			<!-- Question card -->
			<div class="question-card glass">
				<div class="q-header">
					<span class="q-type">
						{#if currentQuestion.question_type === 'mcq'}📝 MCQ
						{:else if currentQuestion.question_type === 'true_false'}✅ True/False
						{:else}✍️ Short Answer
						{/if}
					</span>
					<div class="q-meta">
						{#if currentQuestion.difficulty_level}
							<span class="q-difficulty {currentQuestion.difficulty_level}">{currentQuestion.difficulty_level}</span>
						{/if}
						{#if currentQuestion.marks}
							<span class="q-marks">{currentQuestion.marks} mk{currentQuestion.marks > 1 ? 's' : ''}</span>
						{/if}
						<span class="q-number">#{currentIndex + 1}</span>
					</div>
				</div>

				{#if currentQuestion.topic_name}
					<span class="q-topic">{currentQuestion.topic_name}</span>
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
										onclick={() => editAnswer = getOptionIdentifier(editOptions[i], i)}
										title="Mark as correct"
									>✓</button>
									<span class="edit-option-prefix">{getOptionIdentifier(editOptions[i], i)})</span>
									<input
										class="edit-input edit-option-input"
										value={getOptionEditableText(editOptions[i], i)}
										oninput={(e) => updateOptionText(i, (e.currentTarget as HTMLInputElement).value)}
										bind:this={optionInputRefs[i]}
									/>
									<button
										type="button"
										class="edit-option-pencil"
										onclick={() => focusOptionInput(i)}
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
					<p class="q-text">{currentQuestion.question_text}</p>

					{#if currentQuestion.options}
						<div class="options">
							{#each currentQuestion.options as opt}
								<div class="option" class:correct={isCorrectOption(opt, currentQuestion.correct_answer)}>
									<span class="opt-marker">{isCorrectOption(opt, currentQuestion.correct_answer) ? '✓' : '○'}</span>
									<span>{opt}</span>
								</div>
							{/each}
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
			{#if !isReviewed && !editing}
				<div class="actions">
					<button class="action-btn reject-btn" onclick={openRejectModal} disabled={submitting}>
						<span class="action-icon">✗</span>
						<span>Reject</span>
					</button>
					<button class="action-btn edit-btn" onclick={startEdit}>
						<span class="action-icon">✎</span>
						<span>Edit</span>
					</button>
					<button class="action-btn approve-btn" onclick={approve} disabled={submitting}>
						<span class="action-icon">✓</span>
						<span>Approve</span>
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

			<!-- Finish -->
			{#if totalReviewed >= questions.length}
				<div class="finish-section">
					<button class="glass-btn finish-btn" onclick={finish}>
						🎉 Finish Review
					</button>
					<p class="finish-stats">
						Approved: {approved.size} · Rejected: {rejected.size}
					</p>
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

<!-- Rejection Feedback Modal -->
{#if showRejectModal}
	<!-- svelte-ignore a11y_no_static_element_interactions a11y_click_events_have_key_events a11y_interactive_supports_focus -->
	<div class="modal-overlay" onclick={closeRejectModal} onkeydown={(e) => e.key === 'Escape' && closeRejectModal()}>
		<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
		<div class="modal glass" onclick={(e) => e.stopPropagation()} role="dialog" aria-modal="true" tabindex="-1">
			<div class="modal-header">
				<h3 class="modal-title">Rejection Feedback</h3>
				<button class="modal-close" onclick={closeRejectModal}>✕</button>
			</div>

			<div class="modal-body">
				<p class="modal-desc">Help the AI improve by providing feedback on why this question was rejected.</p>

				<div class="reason-chips">
					{#each REJECTION_REASONS as reason}
						<button
							class="reason-chip"
							class:selected={rejectReasons.includes(reason)}
							onclick={() => toggleReason(reason)}
						>{reason}</button>
					{/each}
				</div>

				<label class="feedback-label" for="reject-feedback">Detailed Feedback</label>
				<textarea
					id="reject-feedback"
					class="feedback-textarea"
					bind:value={rejectFeedback}
					placeholder="Describe what's wrong and how it should be improved..."
					rows="3"
				></textarea>

				<label class="checkbox-row">
					<input type="checkbox" bind:checked={rejectGenerateNew} />
					<span>Generate entirely new question (instead of improving this one)</span>
				</label>
			</div>

			<div class="modal-actions">
				<button class="glass-btn" onclick={closeRejectModal}>Cancel</button>
				<button
					class="action-btn reject-btn"
					onclick={submitRejection}
					disabled={rejectSubmitting || (!rejectFeedback.trim() && rejectReasons.length === 0)}
				>
					{#if rejectSubmitting}
						Submitting...
					{:else if rejectGenerateNew}
						✗ Reject & Replace
					{:else}
						✗ Reject & Improve
					{/if}
				</button>
			</div>
		</div>
	</div>
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

	.loop-header {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.batch-info {
		display: flex;
		justify-content: space-between;
		align-items: center;
	}

	.batch-label {
		font-weight: 700;
		font-size: 1.1rem;
		color: var(--theme-text);
	}

	.review-count {
		font-size: 0.85rem;
		color: var(--theme-text-muted);
	}

	.progress-track {
		width: 100%;
		height: 4px;
		background: rgba(255, 255, 255, 0.1);
		border-radius: 2px;
		overflow: hidden;
	}

	.progress-fill {
		height: 100%;
		background: var(--theme-primary);
		border-radius: 2px;
		transition: width 0.4s ease;
	}

	.context-info {
		display: flex;
		gap: 0.4rem;
		flex-wrap: wrap;
	}

	.ctx-badge {
		font-size: 0.72rem;
		font-weight: 600;
		padding: 0.15rem 0.5rem;
		background: rgba(var(--theme-primary-rgb), 0.1);
		color: var(--theme-primary);
		border-radius: 4px;
	}

	.ctx-badge.topic {
		background: rgba(255, 255, 255, 0.06);
		color: var(--theme-text-muted);
	}

	/* Question card */
	.question-card {
		padding: 1.5rem;
	}

	.q-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 1rem;
	}

	.q-type {
		font-size: 0.8rem;
		font-weight: 600;
		padding: 0.25rem 0.6rem;
		background: rgba(255, 255, 255, 0.08);
		border-radius: 6px;
		color: var(--theme-text-muted);
	}

	.q-number {
		font-size: 0.8rem;
		color: var(--theme-text-muted);
		font-weight: 600;
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
		color: #48c050;
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

	.action-btn {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.85rem 2rem;
		border: none;
		border-radius: var(--glass-radius-sm);
		font-size: 1rem;
		font-weight: 700;
		cursor: pointer;
		transition: all 0.2s;
		backdrop-filter: blur(12px);
		-webkit-backdrop-filter: blur(12px);
		font-family: inherit;
	}

	.approve-btn {
		background: rgba(72, 192, 80, 0.3);
		border: 1px solid rgba(72, 192, 80, 0.4);
		color: #6ee87a;
	}

	.approve-btn:hover {
		background: rgba(72, 192, 80, 0.45);
		transform: translateY(-2px);
		box-shadow: 0 4px 16px rgba(72, 192, 80, 0.2);
	}

	.reject-btn {
		background: rgba(233, 69, 96, 0.3);
		border: 1px solid rgba(233, 69, 96, 0.4);
		color: #f07888;
	}

	.reject-btn:hover {
		background: rgba(233, 69, 96, 0.45);
		transform: translateY(-2px);
		box-shadow: 0 4px 16px rgba(233, 69, 96, 0.2);
	}

	.action-icon {
		font-size: 1.2rem;
		font-weight: 900;
	}

	.edit-btn {
		background: rgba(56, 178, 230, 0.3);
		border: 1px solid rgba(56, 178, 230, 0.4);
		color: #6dd4f0;
	}

	.edit-btn:hover {
		background: rgba(56, 178, 230, 0.45);
		transform: translateY(-2px);
		box-shadow: 0 4px 16px rgba(56, 178, 230, 0.2);
	}

	.finish-section {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.75rem;
		margin-top: 1rem;
	}

	.finish-btn {
		padding: 0.85rem 2.5rem;
		font-size: 1rem;
	}

	.finish-stats {
		font-size: 0.85rem;
		color: var(--theme-text-muted);
		margin: 0;
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

	.edit-option-row .edit-input { flex: 1; }

	.edit-option-prefix {
		min-width: 2rem;
		font-size: 0.9rem;
		font-weight: 700;
		color: var(--theme-text-muted);
		text-align: center;
	}

	.edit-option-input {
		cursor: text;
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

	/* Meta */
	.q-meta {
		display: flex;
		align-items: center;
		gap: 0.4rem;
	}

	.q-difficulty {
		font-size: 0.7rem;
		font-weight: 600;
		padding: 0.15rem 0.5rem;
		border-radius: 6px;
		text-transform: capitalize;
	}

	.q-difficulty.easy { background: rgba(72, 192, 80, 0.15); color: #6ee87a; }
	.q-difficulty.medium { background: rgba(240, 180, 40, 0.15); color: #f0c060; }
	.q-difficulty.hard { background: rgba(233, 69, 96, 0.15); color: #f07888; }

	.q-marks {
		font-size: 0.7rem;
		font-weight: 600;
		padding: 0.15rem 0.5rem;
		background: rgba(255, 255, 255, 0.08);
		border-radius: 6px;
		color: var(--theme-text-muted);
	}

	.q-topic {
		display: inline-block;
		font-size: 0.72rem;
		font-weight: 500;
		padding: 0.2rem 0.6rem;
		background: rgba(var(--theme-primary-rgb), 0.1);
		border-radius: 6px;
		color: var(--theme-primary);
		margin-bottom: 0.75rem;
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

	/* Modal */
	.modal-overlay {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.6);
		backdrop-filter: blur(4px);
		-webkit-backdrop-filter: blur(4px);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 1000;
		padding: 1rem;
	}

	.modal {
		width: 100%;
		max-width: 480px;
		max-height: 90vh;
		overflow-y: auto;
		padding: 1.5rem;
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}

	.modal-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
	}

	.modal-title {
		font-size: 1.1rem;
		font-weight: 700;
		color: var(--theme-text);
		margin: 0;
	}

	.modal-close {
		background: none;
		border: none;
		color: var(--theme-text-muted);
		font-size: 1.2rem;
		cursor: pointer;
		padding: 0.25rem;
		font-family: inherit;
	}

	.modal-body {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}

	.modal-desc {
		font-size: 0.85rem;
		color: var(--theme-text-muted);
		margin: 0;
		line-height: 1.4;
	}

	.reason-chips {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
	}

	.reason-chip {
		padding: 0.3rem 0.65rem;
		font-size: 0.78rem;
		border-radius: 16px;
		border: 1px solid rgba(255, 255, 255, 0.12);
		background: rgba(255, 255, 255, 0.04);
		color: var(--theme-text-muted);
		cursor: pointer;
		transition: all 0.15s;
		font-family: inherit;
	}

	.reason-chip:hover { background: rgba(255, 255, 255, 0.08); }

	.reason-chip.selected {
		background: rgba(233, 69, 96, 0.2);
		border-color: rgba(233, 69, 96, 0.4);
		color: #f07888;
	}

	.feedback-label {
		font-size: 0.75rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: var(--theme-text-muted);
	}

	.feedback-textarea {
		width: 100%;
		padding: 0.6rem 0.8rem;
		background: rgba(255, 255, 255, 0.06);
		border: 1px solid rgba(255, 255, 255, 0.12);
		border-radius: 8px;
		color: var(--theme-text);
		font-family: inherit;
		font-size: 0.9rem;
		line-height: 1.5;
		resize: vertical;
	}

	.feedback-textarea:focus {
		outline: none;
		border-color: var(--theme-primary);
		box-shadow: 0 0 0 2px rgba(var(--theme-primary-rgb), 0.15);
	}

	.checkbox-row {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		font-size: 0.85rem;
		color: var(--theme-text-muted);
		cursor: pointer;
	}

	.checkbox-row input[type="checkbox"] {
		accent-color: var(--theme-primary);
		width: 16px;
		height: 16px;
		cursor: pointer;
	}

	.modal-actions {
		display: flex;
		gap: 0.75rem;
		justify-content: flex-end;
	}

	.modal-actions .reject-btn { padding: 0.65rem 1.5rem; }
	.modal-actions .reject-btn:disabled { opacity: 0.4; cursor: not-allowed; }

	@media (max-width: 768px) {
		.loop-page { padding-top: 1rem; }
		.actions { flex-wrap: wrap; }
		.action-btn { padding: 0.7rem 1.2rem; font-size: 0.9rem; }
	}
</style>
