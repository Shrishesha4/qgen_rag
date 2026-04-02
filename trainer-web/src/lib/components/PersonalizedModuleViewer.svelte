<script lang="ts">
	import { CheckCircle, ChevronDown, ChevronUp, BookOpen } from 'lucide-svelte';
	import { completePersonalizedItem, type PersonalizedItemResponse } from '$lib/api/tutor';

	interface Props {
		item: PersonalizedItemResponse;
		onComplete?: () => void;
	}

	let { item, onComplete }: Props = $props();

	const content = $derived(item.generated_content ?? {});
	const conceptRecap = $derived((content.concept_recap as string) ?? '');
	const misconceptionCorrection = $derived((content.misconception_correction as string) ?? '');
	const workedExamples = $derived(
		(content.worked_examples as Array<{ problem: string; solution: string; key_insight: string }>) ?? []
	);
	const practiceProblems = $derived(
		(content.practice_problems as Array<{
			question_text: string;
			options: string[];
			correct_answer: string;
			explanation: string;
		}>) ?? []
	);
	const recapSummary = $derived((content.recap_summary as string[]) ?? []);
	const topicName = $derived((content.topic_name as string) ?? 'Study Module');

	let expandedSections = $state<Record<string, boolean>>({
		recap: true,
		misconception: false,
		examples: false,
		practice: false,
		summary: false,
	});

	// Practice problem state
	let practiceAnswers = $state<Record<number, string>>({});
	let practiceSubmitted = $state<Record<number, boolean>>({});
	let isCompleting = $state(false);
	let manuallyCompleted = $state(false);
	let isCompleted = $derived(manuallyCompleted || item.status === 'completed');

	function toggleSection(key: string) {
		expandedSections = { ...expandedSections, [key]: !expandedSections[key] };
	}

	function selectPracticeAnswer(qi: number, answer: string) {
		if (practiceSubmitted[qi]) return;
		practiceAnswers = { ...practiceAnswers, [qi]: answer };
	}

	function submitPractice(qi: number) {
		practiceSubmitted = { ...practiceSubmitted, [qi]: true };
	}

	function isPracticeCorrect(qi: number): boolean | null {
		if (!practiceSubmitted[qi]) return null;
		const p = practiceProblems[qi];
		const ans = practiceAnswers[qi];
		if (!ans || !p) return false;
		return ans.charAt(0).toUpperCase() === p.correct_answer.charAt(0).toUpperCase();
	}

	async function markDone() {
		if (isCompleted || isCompleting) return;
		isCompleting = true;
		try {
			await completePersonalizedItem(item.id);
			manuallyCompleted = true;
			onComplete?.();
		} catch {
			// Ignore
		} finally {
			isCompleting = false;
		}
	}
</script>

<div class="module-viewer">
	<div class="module-header glass-panel">
		<BookOpen class="h-5 w-5" />
		<h3>{topicName}</h3>
		{#if isCompleted}
			<span class="done-badge"><CheckCircle class="h-4 w-4" /> Done</span>
		{/if}
	</div>

	<!-- Concept Recap -->
	{#if conceptRecap}
		<div class="section glass-panel">
			<button class="section-header" onclick={() => toggleSection('recap')}>
				<span class="section-title">Concept Recap</span>
				{#if expandedSections.recap}<ChevronUp class="h-4 w-4" />{:else}<ChevronDown class="h-4 w-4" />{/if}
			</button>
			{#if expandedSections.recap}
				<div class="section-content prose">{conceptRecap}</div>
			{/if}
		</div>
	{/if}

	<!-- Misconception Correction -->
	{#if misconceptionCorrection}
		<div class="section glass-panel">
			<button class="section-header" onclick={() => toggleSection('misconception')}>
				<span class="section-title">Common Misconceptions</span>
				{#if expandedSections.misconception}<ChevronUp class="h-4 w-4" />{:else}<ChevronDown class="h-4 w-4" />{/if}
			</button>
			{#if expandedSections.misconception}
				<div class="section-content prose">{misconceptionCorrection}</div>
			{/if}
		</div>
	{/if}

	<!-- Worked Examples -->
	{#if workedExamples.length > 0}
		<div class="section glass-panel">
			<button class="section-header" onclick={() => toggleSection('examples')}>
				<span class="section-title">Worked Examples ({workedExamples.length})</span>
				{#if expandedSections.examples}<ChevronUp class="h-4 w-4" />{:else}<ChevronDown class="h-4 w-4" />{/if}
			</button>
			{#if expandedSections.examples}
				<div class="section-content">
					{#each workedExamples as ex, i}
						<div class="example-card">
							<div class="example-problem"><strong>Problem {i + 1}:</strong> {ex.problem}</div>
							<div class="example-solution"><strong>Solution:</strong> {ex.solution}</div>
							{#if ex.key_insight}
								<div class="example-insight">Key insight: {ex.key_insight}</div>
							{/if}
						</div>
					{/each}
				</div>
			{/if}
		</div>
	{/if}

	<!-- Practice Problems -->
	{#if practiceProblems.length > 0}
		<div class="section glass-panel">
			<button class="section-header" onclick={() => toggleSection('practice')}>
				<span class="section-title">Practice Problems ({practiceProblems.length})</span>
				{#if expandedSections.practice}<ChevronUp class="h-4 w-4" />{:else}<ChevronDown class="h-4 w-4" />{/if}
			</button>
			{#if expandedSections.practice}
				<div class="section-content">
					{#each practiceProblems as p, qi}
						{@const result = isPracticeCorrect(qi)}
						<div class="practice-card" class:correct={result === true} class:incorrect={result === false}>
							<p class="practice-q">{qi + 1}. {p.question_text}</p>
							{#if p.options}
								<div class="practice-options">
									{#each p.options as opt}
										{@const isSelected = practiceAnswers[qi] === opt}
										{@const optLetter = opt.charAt(0).toUpperCase()}
										{@const isCorrectOpt = practiceSubmitted[qi] && optLetter === p.correct_answer.charAt(0).toUpperCase()}
										<button
											class="practice-opt"
											class:selected={isSelected}
											class:correct-opt={practiceSubmitted[qi] && isCorrectOpt}
											class:wrong-opt={practiceSubmitted[qi] && isSelected && !isCorrectOpt}
											onclick={() => selectPracticeAnswer(qi, opt)}
											disabled={practiceSubmitted[qi]}
										>{opt}</button>
									{/each}
								</div>
							{/if}
							{#if !practiceSubmitted[qi]}
								<button
									class="check-btn"
									disabled={!practiceAnswers[qi]}
									onclick={() => submitPractice(qi)}
								>Check</button>
							{:else if p.explanation}
								<div class="practice-explanation">{p.explanation}</div>
							{/if}
						</div>
					{/each}
				</div>
			{/if}
		</div>
	{/if}

	<!-- Recap Summary -->
	{#if recapSummary.length > 0}
		<div class="section glass-panel">
			<button class="section-header" onclick={() => toggleSection('summary')}>
				<span class="section-title">Key Takeaways</span>
				{#if expandedSections.summary}<ChevronUp class="h-4 w-4" />{:else}<ChevronDown class="h-4 w-4" />{/if}
			</button>
			{#if expandedSections.summary}
				<ul class="section-content summary-list">
					{#each recapSummary as bullet}
						<li>{bullet}</li>
					{/each}
				</ul>
			{/if}
		</div>
	{/if}

	{#if !isCompleted}
		<button class="done-btn" onclick={markDone} disabled={isCompleting}>
			{isCompleting ? 'Saving…' : 'Mark as Done'}
		</button>
	{/if}
</div>

<style>
	.module-viewer {
		display: flex;
		flex-direction: column;
		gap: 0.65rem;
	}

	.module-header {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.85rem 1.1rem;
		border-radius: 14px;
	}

	.module-header h3 {
		flex: 1;
		font-size: 0.95rem;
		font-weight: 700;
		margin: 0;
	}

	.glass-panel {
		background: color-mix(in srgb, var(--theme-nav-glass) 88%, transparent);
		border: 1px solid var(--theme-glass-border);
		backdrop-filter: blur(18px);
	}

	.done-badge {
		display: inline-flex;
		align-items: center;
		gap: 0.25rem;
		font-size: 0.72rem;
		font-weight: 700;
		color: rgb(34, 197, 94);
	}

	.section {
		border-radius: 14px;
		overflow: hidden;
	}

	.section-header {
		width: 100%;
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 0.75rem 1rem;
		border: none;
		background: transparent;
		color: var(--theme-text-primary);
		cursor: pointer;
		font-family: inherit;
	}

	.section-title {
		font-size: 0.88rem;
		font-weight: 700;
	}

	.section-content {
		padding: 0 1rem 1rem;
		font-size: 0.85rem;
		line-height: 1.65;
		color: var(--theme-text-secondary);
	}

	.section-content.prose {
		white-space: pre-wrap;
	}

	.example-card {
		padding: 0.75rem;
		border-radius: 10px;
		background: var(--theme-input-bg);
		margin-bottom: 0.5rem;
	}

	.example-problem, .example-solution {
		margin-bottom: 0.3rem;
	}

	.example-insight {
		font-size: 0.78rem;
		font-style: italic;
		color: rgba(var(--theme-primary-rgb), 0.85);
	}

	.practice-card {
		padding: 0.75rem;
		border-radius: 10px;
		border: 1px solid var(--theme-glass-border);
		margin-bottom: 0.5rem;
		transition: border-color 0.2s;
	}

	.practice-card.correct {
		border-color: rgba(34, 197, 94, 0.4);
	}

	.practice-card.incorrect {
		border-color: rgba(239, 68, 68, 0.4);
	}

	.practice-q {
		margin: 0 0 0.45rem;
		font-weight: 600;
		font-size: 0.85rem;
	}

	.practice-options {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		margin-bottom: 0.45rem;
	}

	.practice-opt {
		padding: 0.4rem 0.65rem;
		border-radius: 8px;
		border: 1px solid var(--theme-glass-border);
		background: var(--theme-input-bg);
		color: var(--theme-text-primary);
		cursor: pointer;
		text-align: left;
		font-size: 0.82rem;
	}

	.practice-opt.selected {
		border-color: rgba(var(--theme-primary-rgb), 0.6);
		background: rgba(var(--theme-primary-rgb), 0.08);
	}

	.practice-opt.correct-opt {
		border-color: rgba(34, 197, 94, 0.6);
		background: rgba(34, 197, 94, 0.08);
	}

	.practice-opt.wrong-opt {
		border-color: rgba(239, 68, 68, 0.6);
		background: rgba(239, 68, 68, 0.08);
	}

	.practice-opt:disabled {
		cursor: default;
	}

	.check-btn {
		padding: 0.35rem 0.75rem;
		border-radius: 8px;
		border: none;
		background: rgba(var(--theme-primary-rgb), 0.85);
		color: white;
		font-weight: 700;
		font-size: 0.78rem;
		cursor: pointer;
	}

	.check-btn:disabled {
		opacity: 0.4;
	}

	.practice-explanation {
		margin-top: 0.35rem;
		padding: 0.5rem;
		border-radius: 8px;
		background: rgba(var(--theme-primary-rgb), 0.04);
		font-size: 0.78rem;
		line-height: 1.5;
	}

	.summary-list {
		list-style: none;
		padding: 0 1rem 1rem;
	}

	.summary-list li {
		position: relative;
		padding-left: 1.2rem;
		margin-bottom: 0.35rem;
	}

	.summary-list li::before {
		content: '•';
		position: absolute;
		left: 0;
		color: rgba(var(--theme-primary-rgb), 0.7);
		font-weight: 700;
	}

	.done-btn {
		padding: 0.65rem 1.2rem;
		border-radius: 12px;
		border: none;
		background: rgba(var(--theme-primary-rgb), 0.9);
		color: white;
		font-weight: 700;
		font-size: 0.85rem;
		cursor: pointer;
		align-self: center;
	}

	.done-btn:disabled {
		opacity: 0.45;
	}
</style>
