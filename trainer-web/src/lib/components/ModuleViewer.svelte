<script lang="ts">
	import { BookOpen, ClipboardList, FileQuestion, PlayCircle } from 'lucide-svelte';
	import MarkdownContent from './MarkdownContent.svelte';
	import type { CourseModuleResponse } from '$lib/api/courses';

	type ModuleQuestionItem = {
		prompt: string;
		options: string[];
		correctIndex: number | null;
		correctAnswer: string;
		explanation: string;
		questionType: string;
		sampleAnswer: string;
		marks: number | null;
		difficulty: string | null;
	};

	let {
		module: mod,
		onComplete,
	}: {
		module: CourseModuleResponse;
		onComplete?: () => void;
	} = $props();

	let quizAnswers = $state<Record<number, string>>({});
	let quizSubmitted = $state(false);

	function normalizeQuestion(item: Record<string, unknown>): ModuleQuestionItem {
		const options = Array.isArray(item.options) ? item.options.map((option) => String(option)) : [];
		const correctAnswer = typeof item.correct_answer === 'string'
			? item.correct_answer
			: typeof item.answer === 'string'
				? item.answer
				: '';
		let correctIndex = typeof item.correct === 'number' ? item.correct : null;

		if (correctIndex === null && options.length && correctAnswer) {
			const normalizedCorrect = correctAnswer.trim().toUpperCase();
			const matchedIndex = options.findIndex((option) => {
				const normalizedOption = option.trim().toUpperCase();
				return (
					normalizedOption === normalizedCorrect ||
					normalizedOption.startsWith(`${normalizedCorrect})`) ||
					normalizedOption.startsWith(`${normalizedCorrect}.`) ||
					normalizedOption.startsWith(`${normalizedCorrect}:`)
				);
			});
			correctIndex = matchedIndex >= 0 ? matchedIndex : null;
		}

		return {
			prompt: String(item.question ?? item.question_text ?? '').trim(),
			options,
			correctIndex,
			correctAnswer: correctAnswer.trim(),
			explanation: String(item.explanation ?? '').trim(),
			questionType: String(item.question_type ?? (options.length ? 'mcq' : 'short_answer')),
			sampleAnswer: String(item.sample_answer ?? item.correct_answer ?? item.answer ?? '').trim(),
			marks: typeof item.marks === 'number' ? item.marks : null,
			difficulty: typeof item.difficulty_level === 'string' ? item.difficulty_level : null,
		};
	}

	const contentData = $derived((mod.content_data ?? {}) as Record<string, unknown>);
	const summary = $derived(typeof contentData.summary === 'string' ? contentData.summary : '');
	const learningObjectives = $derived(
		Array.isArray(contentData.learning_objectives)
			? contentData.learning_objectives.map((item) => String(item)).filter(Boolean)
			: []
	);

	const contentMarkdown = $derived(
		typeof contentData.markdown === 'string'
			? contentData.markdown
			: typeof contentData.body_markdown === 'string'
				? contentData.body_markdown
				: typeof contentData.text === 'string'
					? contentData.text
					: ''
	);
	const assignmentPrompt = $derived(typeof contentData.assignment_prompt === 'string' ? contentData.assignment_prompt : '');
	const videoUrl = $derived(typeof contentData.video_url === 'string' ? contentData.video_url : '');
	const moduleQuestions = $derived(
		Array.isArray(contentData.questions)
			? contentData.questions
				.filter((item): item is Record<string, unknown> => !!item && typeof item === 'object')
				.map(normalizeQuestion)
				.filter((item) => item.prompt)
			: []
	);
	const interactiveQuestionCount = $derived(moduleQuestions.filter((question) => question.options.length > 0).length);

	function submitQuiz() {
		quizSubmitted = true;
	}

	function getScore(): number {
		const interactiveQuestions = moduleQuestions.filter((question) => question.options.length > 0);
		if (!interactiveQuestions.length) return 0;
		let correct = 0;
		for (let i = 0; i < moduleQuestions.length; i++) {
			if (moduleQuestions[i].options.length > 0 && quizAnswers[i] === String(moduleQuestions[i].correctIndex)) {
				correct++;
			}
		}
		return Math.round((correct / interactiveQuestions.length) * 100);
	}
</script>

<div class="module-viewer">
	<header class="module-header">
		<div class="module-type-badge">
			{#if mod.module_type === 'content'}
				<BookOpen class="h-4 w-4" />
			{:else if mod.module_type === 'quiz'}
				<FileQuestion class="h-4 w-4" />
			{:else}
				<PlayCircle class="h-4 w-4" />
			{/if}
			<span>{mod.module_type}</span>
		</div>
		<h2 class="module-title">{mod.title}</h2>
		{#if mod.description}
			<p class="module-description">{mod.description}</p>
		{/if}
		{#if summary}
			<p class="module-summary">{summary}</p>
		{/if}
	</header>

	<div class="module-content">
		{#if learningObjectives.length > 0}
			<section class="objectives-card">
				<h3>Learning objectives</h3>
				<ul>
					{#each learningObjectives as objective}
						<li>{objective}</li>
					{/each}
				</ul>
			</section>
		{/if}

		{#if videoUrl}
			<div class="video-wrapper">
				<!-- svelte-ignore a11y_media_has_caption -->
				<video controls src={videoUrl} class="video-player">
					<track kind="captions" />
				</video>
			</div>
		{/if}

		{#if mod.module_type === 'assignment' && assignmentPrompt}
			<section class="assignment-brief">
				<div class="assignment-heading">
					<ClipboardList class="h-4 w-4" />
					<h3>Assignment brief</h3>
				</div>
				<MarkdownContent content={assignmentPrompt} />
			</section>
		{/if}

		{#if contentMarkdown}
			<div class="content-body">
				<MarkdownContent content={contentMarkdown} />
			</div>
		{/if}

		{#if mod.module_type === 'quiz' && moduleQuestions.length > 0}
			<div class="quiz-section">
				{#each moduleQuestions as q, i}
					<div
						class="quiz-question"
						class:correct={quizSubmitted && q.options.length > 0 && quizAnswers[i] === String(q.correctIndex)}
						class:incorrect={quizSubmitted && q.options.length > 0 && quizAnswers[i] !== undefined && quizAnswers[i] !== String(q.correctIndex)}
					>
						<p class="q-text">{i + 1}. {q.prompt}</p>
						{#if q.marks || q.difficulty}
							<p class="q-meta">
								{#if q.marks}{q.marks} marks{/if}
								{#if q.marks && q.difficulty} • {/if}
								{#if q.difficulty}{q.difficulty}{/if}
							</p>
						{/if}

						{#if q.options.length > 0}
							<div class="q-options">
								{#each q.options as opt, oi}
									<label class="q-option" class:selected={quizAnswers[i] === String(oi)}>
										<input
											type="radio"
											name="q{i}"
											value={String(oi)}
											bind:group={quizAnswers[i]}
											disabled={quizSubmitted}
										/>
										<span>{opt}</span>
									</label>
								{/each}
							</div>
						{:else}
							<p class="open-ended-note">Write your answer before revealing the reference answer.</p>
							{#if quizSubmitted && q.sampleAnswer}
								<p class="q-reference"><strong>Suggested answer:</strong> {q.sampleAnswer}</p>
							{/if}
						{/if}

						{#if quizSubmitted && q.explanation}
							<p class="q-explanation">{q.explanation}</p>
						{/if}
					</div>
				{/each}

				{#if !quizSubmitted}
					<button class="quiz-submit" onclick={submitQuiz} disabled={interactiveQuestionCount > 0 && Object.keys(quizAnswers).length < interactiveQuestionCount}>
						{interactiveQuestionCount > 0 ? 'Submit Quiz' : 'Reveal Answers'}
					</button>
				{:else}
					<div class="quiz-result">
						{#if interactiveQuestionCount > 0}
							<p>Score: <strong>{getScore()}%</strong></p>
						{:else}
							<p>Reference answers revealed.</p>
						{/if}
					</div>
				{/if}
			</div>
		{/if}

		{#if mod.module_type === 'assignment' && moduleQuestions.length > 0}
			<section class="assignment-questions">
				<h3>Assignment questions</h3>
				<div class="assignment-list">
					{#each moduleQuestions as question, index}
						<article class="assignment-card">
							<p class="q-text">{index + 1}. {question.prompt}</p>
							{#if question.sampleAnswer}
								<p class="q-reference"><strong>Suggested answer:</strong> {question.sampleAnswer}</p>
							{/if}
							{#if question.explanation}
								<p class="q-explanation">{question.explanation}</p>
							{/if}
						</article>
					{/each}
				</div>
			</section>
		{/if}
	</div>

	{#if onComplete}
		<footer class="module-footer">
			<button class="complete-btn" onclick={onComplete}>
				Mark as Complete & Continue
			</button>
		</footer>
	{/if}
</div>

<style>
	.module-viewer {
		display: flex;
		flex-direction: column;
		height: 100%;
		overflow-y: auto;
		padding: 1.5rem;
	}

	.module-header {
		margin-bottom: 1.5rem;
	}

	.module-type-badge {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		font-size: 0.72rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		color: var(--theme-text-secondary);
		padding: 0.25rem 0.65rem;
		border-radius: 999px;
		border: 1px solid var(--theme-glass-border);
		background: var(--theme-input-bg);
		margin-bottom: 0.75rem;
	}

	.module-title {
		font-size: 1.35rem;
		font-weight: 800;
		margin: 0 0 0.35rem;
		color: var(--theme-text-primary);
	}

	.module-description {
		font-size: 0.88rem;
		color: var(--theme-text-secondary);
		margin: 0;
	}

	.module-summary {
		margin: 0.6rem 0 0;
		font-size: 0.9rem;
		line-height: 1.6;
		color: var(--theme-text-secondary);
	}

	.module-content {
		flex: 1;
	}

	.objectives-card,
	.assignment-brief,
	.assignment-questions {
		margin-bottom: 1.25rem;
		padding: 1rem 1.1rem;
		border-radius: 14px;
		border: 1px solid var(--theme-glass-border);
		background: var(--theme-input-bg);
	}

	.objectives-card h3,
	.assignment-heading h3,
	.assignment-questions h3 {
		margin: 0 0 0.75rem;
		font-size: 0.96rem;
		font-weight: 700;
		color: var(--theme-text-primary);
	}

	.objectives-card ul {
		margin: 0;
		padding-left: 1.1rem;
		display: grid;
		gap: 0.45rem;
		color: var(--theme-text-secondary);
	}

	.assignment-heading {
		display: inline-flex;
		align-items: center;
		gap: 0.5rem;
	}

	.video-wrapper {
		margin-bottom: 1.5rem;
		border-radius: 14px;
		overflow: hidden;
		border: 1px solid var(--theme-glass-border);
	}

	.video-player {
		width: 100%;
		display: block;
	}

	.content-body {
		line-height: 1.7;
	}

	.quiz-section {
		display: flex;
		flex-direction: column;
		gap: 1.25rem;
		margin-top: 1rem;
	}

	.quiz-question {
		padding: 1rem;
		border-radius: 14px;
		border: 1px solid var(--theme-glass-border);
		background: var(--theme-input-bg);
	}

	.quiz-question.correct {
		border-color: rgba(34, 197, 94, 0.5);
		background: rgba(34, 197, 94, 0.06);
	}

	.quiz-question.incorrect {
		border-color: rgba(239, 68, 68, 0.5);
		background: rgba(239, 68, 68, 0.06);
	}

	.q-text {
		font-weight: 600;
		margin: 0 0 0.75rem;
	}

	.q-meta,
	.open-ended-note {
		margin: -0.3rem 0 0.75rem;
		font-size: 0.8rem;
		color: var(--theme-text-secondary);
	}

	.q-options {
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
	}

	.q-option {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.5rem 0.75rem;
		border-radius: 10px;
		cursor: pointer;
		font-size: 0.88rem;
		transition: background 0.1s;
	}

	.q-option:hover {
		background: rgba(var(--theme-primary-rgb), 0.06);
	}

	.q-option.selected {
		background: rgba(var(--theme-primary-rgb), 0.1);
	}

	.q-explanation {
		margin-top: 0.75rem;
		font-size: 0.84rem;
		color: var(--theme-text-secondary);
		padding: 0.5rem 0.75rem;
		border-left: 3px solid rgba(var(--theme-primary-rgb), 0.4);
	}

	.q-reference {
		margin-top: 0.75rem;
		font-size: 0.84rem;
		line-height: 1.6;
		color: var(--theme-text-primary);
		padding: 0.65rem 0.75rem;
		border-radius: 12px;
		background: rgba(var(--theme-primary-rgb), 0.08);
	}

	.quiz-submit {
		padding: 0.75rem 1.5rem;
		border-radius: 12px;
		border: 1px solid rgba(var(--theme-primary-rgb), 0.3);
		background: rgba(var(--theme-primary-rgb), 0.1);
		color: var(--theme-text-primary);
		font-weight: 700;
		cursor: pointer;
		align-self: flex-start;
	}

	.quiz-submit:disabled {
		opacity: 0.45;
		cursor: not-allowed;
	}

	.quiz-result {
		font-size: 1.1rem;
		padding: 0.75rem;
	}

	.assignment-list {
		display: grid;
		gap: 0.85rem;
	}

	.assignment-card {
		padding: 1rem;
		border-radius: 14px;
		border: 1px solid var(--theme-glass-border);
		background: rgba(var(--theme-primary-rgb), 0.04);
	}

	.module-footer {
		padding-top: 1rem;
		border-top: 1px solid var(--theme-glass-border);
		margin-top: 1.5rem;
	}

	.complete-btn {
		padding: 0.75rem 1.5rem;
		border-radius: 14px;
		border: 1px solid rgba(var(--theme-primary-rgb), 0.3);
		background: rgba(var(--theme-primary-rgb), 0.1);
		color: var(--theme-text-primary);
		font-weight: 700;
		cursor: pointer;
		width: 100%;
	}

	.complete-btn:hover {
		background: rgba(var(--theme-primary-rgb), 0.18);
	}
</style>
