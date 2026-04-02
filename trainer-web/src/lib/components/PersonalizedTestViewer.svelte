<script lang="ts">
	import { CheckCircle, XCircle, ChevronDown, ChevronUp, Clock } from 'lucide-svelte';
	import { completePersonalizedItem, type PersonalizedItemResponse } from '$lib/api/tutor';

	interface Props {
		item: PersonalizedItemResponse;
		onComplete?: () => void;
	}

	let { item, onComplete }: Props = $props();

	interface TestQuestion {
		question_id: string;
		question_text: string;
		question_type: string;
		options: string[] | null;
		correct_answer: string;
		explanation: string;
		difficulty_level: string;
		topic_id?: string;
	}

	const questions: TestQuestion[] = $derived(
		(item.generated_content?.questions as TestQuestion[]) ?? []
	);

	let answers = $state<Record<number, string>>({});
	let submitted = $state(false);
	let score = $state(0);
	let showExplanation = $state<Record<number, boolean>>({});
	let isCompleting = $state(false);

	function selectAnswer(qi: number, answer: string) {
		if (submitted) return;
		answers = { ...answers, [qi]: answer };
	}

	async function submit() {
		if (submitted) return;
		submitted = true;

		let correct = 0;
		for (let i = 0; i < questions.length; i++) {
			const q = questions[i];
			const userAnswer = answers[i];
			if (!userAnswer) continue;
			// Extract letter from option (e.g. "A) ..." → "A")
			const userLetter = userAnswer.charAt(0).toUpperCase();
			const correctLetter = q.correct_answer.charAt(0).toUpperCase();
			if (userLetter === correctLetter) correct++;
		}
		score = correct;

		// Mark item as completed
		try {
			isCompleting = true;
			await completePersonalizedItem(item.id);
			onComplete?.();
		} catch {
			// Ignore API errors on completion
		} finally {
			isCompleting = false;
		}
	}

	function toggleExplanation(qi: number) {
		showExplanation = { ...showExplanation, [qi]: !showExplanation[qi] };
	}

	function isCorrect(qi: number): boolean | null {
		if (!submitted) return null;
		const q = questions[qi];
		const userAnswer = answers[qi];
		if (!userAnswer) return false;
		return userAnswer.charAt(0).toUpperCase() === q.correct_answer.charAt(0).toUpperCase();
	}

	const answeredCount = $derived(Object.keys(answers).length);
	const percentage = $derived(questions.length > 0 ? Math.round((score / questions.length) * 100) : 0);
</script>

<div class="test-viewer">
	<div class="test-header glass-panel">
		<h3>Personalized Test</h3>
		<div class="test-meta">
			<span class="badge">{questions.length} questions</span>
			{#if !submitted}
				<span class="badge progress-badge">{answeredCount}/{questions.length} answered</span>
			{:else}
				<span class="badge score-badge" class:pass={percentage >= 60} class:fail={percentage < 60}>
					{score}/{questions.length} ({percentage}%)
				</span>
			{/if}
		</div>
	</div>

	<div class="questions-list">
		{#each questions as q, i (q.question_id ?? i)}
			{@const result = isCorrect(i)}
			<div class="question-card glass-panel" class:correct={result === true} class:incorrect={result === false}>
				<div class="q-number">Q{i + 1}</div>
				<p class="q-text">{q.question_text}</p>

				{#if q.options}
					<div class="options">
						{#each q.options as opt, oi}
							{@const isSelected = answers[i] === opt}
							{@const optLetter = opt.charAt(0).toUpperCase()}
							{@const isCorrectOpt = submitted && optLetter === q.correct_answer.charAt(0).toUpperCase()}
							<button
								class="option"
								class:selected={isSelected}
								class:correct-opt={submitted && isCorrectOpt}
								class:wrong-opt={submitted && isSelected && !isCorrectOpt}
								onclick={() => selectAnswer(i, opt)}
								disabled={submitted}
							>
								{opt}
								{#if submitted && isCorrectOpt}
									<CheckCircle class="h-4 w-4 check-icon" />
								{:else if submitted && isSelected && !isCorrectOpt}
									<XCircle class="h-4 w-4 x-icon" />
								{/if}
							</button>
						{/each}
					</div>
				{/if}

				{#if submitted && q.explanation}
					<button class="explanation-toggle" onclick={() => toggleExplanation(i)}>
						{showExplanation[i] ? 'Hide' : 'Show'} Explanation
						{#if showExplanation[i]}
							<ChevronUp class="h-4 w-4" />
						{:else}
							<ChevronDown class="h-4 w-4" />
						{/if}
					</button>
					{#if showExplanation[i]}
						<div class="explanation">{q.explanation}</div>
					{/if}
				{/if}
			</div>
		{/each}
	</div>

	{#if !submitted}
		<button class="submit-btn" onclick={submit} disabled={answeredCount === 0}>
			Submit Test ({answeredCount}/{questions.length})
		</button>
	{/if}
</div>

<style>
	.test-viewer {
		display: flex;
		flex-direction: column;
		gap: 0.85rem;
	}

	.test-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 0.85rem 1.1rem;
		border-radius: 14px;
	}

	.test-header h3 {
		font-size: 0.95rem;
		font-weight: 700;
		margin: 0;
	}

	.glass-panel {
		background: color-mix(in srgb, var(--theme-nav-glass) 88%, transparent);
		border: 1px solid var(--theme-glass-border);
		backdrop-filter: blur(18px);
	}

	.test-meta {
		display: flex;
		gap: 0.5rem;
	}

	.badge {
		font-size: 0.72rem;
		padding: 0.2rem 0.55rem;
		border-radius: 8px;
		background: var(--theme-input-bg);
		color: var(--theme-text-secondary);
		font-weight: 600;
	}

	.score-badge.pass {
		background: rgba(34, 197, 94, 0.12);
		color: rgb(34, 197, 94);
	}

	.score-badge.fail {
		background: rgba(239, 68, 68, 0.12);
		color: #ef4444;
	}

	.questions-list {
		display: flex;
		flex-direction: column;
		gap: 0.65rem;
	}

	.question-card {
		padding: 1rem;
		border-radius: 14px;
		transition: border-color 0.2s;
	}

	.question-card.correct {
		border-color: rgba(34, 197, 94, 0.4);
	}

	.question-card.incorrect {
		border-color: rgba(239, 68, 68, 0.4);
	}

	.q-number {
		font-size: 0.7rem;
		font-weight: 700;
		text-transform: uppercase;
		color: var(--theme-text-secondary);
		margin-bottom: 0.35rem;
	}

	.q-text {
		font-size: 0.9rem;
		line-height: 1.5;
		margin: 0 0 0.65rem;
	}

	.options {
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
	}

	.option {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 0.55rem 0.75rem;
		border-radius: 10px;
		border: 1px solid var(--theme-glass-border);
		background: var(--theme-input-bg);
		color: var(--theme-text-primary);
		cursor: pointer;
		text-align: left;
		font-size: 0.85rem;
		transition: all 0.15s;
	}

	.option:hover:not(:disabled) {
		border-color: rgba(var(--theme-primary-rgb), 0.4);
	}

	.option.selected {
		border-color: rgba(var(--theme-primary-rgb), 0.6);
		background: rgba(var(--theme-primary-rgb), 0.08);
	}

	.option.correct-opt {
		border-color: rgba(34, 197, 94, 0.6);
		background: rgba(34, 197, 94, 0.08);
	}

	.option.wrong-opt {
		border-color: rgba(239, 68, 68, 0.6);
		background: rgba(239, 68, 68, 0.08);
	}

	.option:disabled {
		cursor: default;
	}

	.explanation-toggle {
		display: inline-flex;
		align-items: center;
		gap: 0.25rem;
		margin-top: 0.5rem;
		padding: 0.3rem 0.6rem;
		border: none;
		background: transparent;
		color: rgba(var(--theme-primary-rgb), 0.85);
		font-size: 0.78rem;
		font-weight: 600;
		cursor: pointer;
	}

	.explanation {
		margin-top: 0.35rem;
		padding: 0.65rem;
		border-radius: 10px;
		background: rgba(var(--theme-primary-rgb), 0.04);
		border: 1px solid rgba(var(--theme-primary-rgb), 0.1);
		font-size: 0.82rem;
		line-height: 1.55;
		color: var(--theme-text-secondary);
	}

	.submit-btn {
		padding: 0.7rem 1.2rem;
		border-radius: 12px;
		border: none;
		background: rgba(var(--theme-primary-rgb), 0.9);
		color: white;
		font-weight: 700;
		font-size: 0.88rem;
		cursor: pointer;
		align-self: center;
	}

	.submit-btn:disabled {
		opacity: 0.45;
	}
</style>
