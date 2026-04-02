<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { apiFetch } from '$lib/api/client';
	import { 
		AlertTriangle, CheckCircle, XCircle, HelpCircle,
		Clock, Save, Send, ArrowLeft, Plus, Trash2
	} from 'lucide-svelte';

	interface EvaluationItem {
		id: string;
		question_id: string;
		difficulty_label: string | null;
		bloom_level: string | null;
	}

	interface Question {
		question_text: string;
		question_type: string | null;
		options: string[] | null;
		correct_answer: string | null;
		difficulty_level: string | null;
		bloom_taxonomy_level: string | null;
	}

	interface Issue {
		category: string;
		severity: string;
		description: string;
		location_field: string | null;
	}

	interface Attempt {
		id: string;
		status: string;
		has_issues_detected: boolean | null;
		reasoning_text: string | null;
		correction_text: string | null;
		confidence_score: number | null;
		issues: Issue[];
		is_draft: boolean;
	}

	const ISSUE_CATEGORIES = [
		{ value: 'factual_error', label: 'Factual Error', description: 'Contains incorrect information' },
		{ value: 'ambiguous', label: 'Ambiguous', description: 'Question or options are unclear' },
		{ value: 'incomplete', label: 'Incomplete', description: 'Missing necessary information' },
		{ value: 'misleading', label: 'Misleading', description: 'Could lead to wrong conclusions' },
		{ value: 'off_topic', label: 'Off Topic', description: 'Not relevant to the subject' },
		{ value: 'difficulty_mismatch', label: 'Difficulty Mismatch', description: 'Harder/easier than labeled' },
		{ value: 'bloom_mismatch', label: 'Bloom Level Mismatch', description: 'Wrong cognitive level' },
		{ value: 'poor_distractor', label: 'Poor Distractor', description: 'MCQ options are too obvious' },
		{ value: 'answer_revealed', label: 'Answer Revealed', description: 'Correct answer is obvious' },
		{ value: 'formatting', label: 'Formatting Issue', description: 'Grammar, spelling, or layout' },
		{ value: 'other', label: 'Other', description: 'Other issue not listed' },
	];

	const SEVERITY_LEVELS = [
		{ value: 'minor', label: 'Minor', color: 'bg-yellow-100 text-yellow-800' },
		{ value: 'moderate', label: 'Moderate', color: 'bg-orange-100 text-orange-800' },
		{ value: 'major', label: 'Major', color: 'bg-red-100 text-red-800' },
		{ value: 'critical', label: 'Critical', color: 'bg-red-200 text-red-900' },
	];

	let itemId: string;
	let assignmentId: string | null;
	let evaluationItem: EvaluationItem | null = null;
	let question: Question | null = null;
	let attempt: Attempt | null = null;
	
	let isLoading = true;
	let isSaving = false;
	let isSubmitting = false;
	let error: string | null = null;
	let saveMessage: string | null = null;

	// Form state
	let hasIssuesDetected: boolean | null = null;
	let issues: Issue[] = [];
	let reasoningText = '';
	let correctionText = '';
	let confidenceScore = 0.5;

	// Auto-save timer
	let autoSaveTimer: ReturnType<typeof setInterval> | null = null;
	let lastSavedAt: Date | null = null;

	$: itemId = $page.params.item_id as string;
	$: assignmentId = $page.url.searchParams.get('assignment');

	onMount(async () => {
		await loadEvaluationItem();
		await startOrResumeAttempt();
		
		// Set up auto-save every 30 seconds
		autoSaveTimer = setInterval(saveDraft, 30000);
	});

	onDestroy(() => {
		if (autoSaveTimer) {
			clearInterval(autoSaveTimer);
		}
	});

	async function loadEvaluationItem() {
		try {
			evaluationItem = await apiFetch<EvaluationItem>(`/gel/evaluation-items/${itemId}`);
			
			// Load question details
			if (evaluationItem?.question_id) {
				question = await apiFetch<Question>(`/questions/${evaluationItem.question_id}`);
			}
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to load evaluation item';
		}
	}

	async function startOrResumeAttempt() {
		isLoading = true;
		try {
			attempt = await apiFetch<Attempt>('/gel/attempts', {
				method: 'POST',
				body: JSON.stringify({
					evaluation_item_id: itemId,
					assignment_id: assignmentId,
				}),
			});
			
			// Restore form state from attempt
			if (attempt) {
				hasIssuesDetected = attempt.has_issues_detected;
				issues = attempt.issues || [];
				reasoningText = attempt.reasoning_text || '';
				correctionText = attempt.correction_text || '';
				confidenceScore = attempt.confidence_score ?? 0.5;
			}
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to start attempt';
		} finally {
			isLoading = false;
		}
	}

	async function saveDraft() {
		if (!attempt || isSubmitting) return;
		
		isSaving = true;
		saveMessage = null;
		
		try {
			await apiFetch(`/gel/attempts/${attempt.id}/draft`, {
				method: 'PATCH',
				body: JSON.stringify({
					has_issues_detected: hasIssuesDetected,
					issues: issues,
					reasoning_text: reasoningText,
					correction_text: correctionText,
					confidence_score: confidenceScore,
				}),
			});
			lastSavedAt = new Date();
			saveMessage = 'Draft saved';
			setTimeout(() => saveMessage = null, 2000);
		} catch (e: any) {
			console.error('Auto-save failed:', e);
		} finally {
			isSaving = false;
		}
	}

	async function submitAttempt() {
		if (!attempt) return;
		
		// Validation
		if (hasIssuesDetected === null) {
			error = 'Please indicate whether you found any issues';
			return;
		}
		
		if (hasIssuesDetected && issues.length === 0) {
			error = 'Please add at least one issue';
			return;
		}
		
		if (!reasoningText.trim()) {
			error = 'Please provide your reasoning';
			return;
		}
		
		isSubmitting = true;
		error = null;
		
		try {
			const response = await apiFetch<{ show_feedback?: boolean }>(`/gel/attempts/${attempt.id}/submit`, {
				method: 'POST',
				body: JSON.stringify({
					has_issues_detected: hasIssuesDetected,
					issues: issues,
					reasoning_text: reasoningText,
					correction_text: correctionText,
					confidence_score: confidenceScore,
					is_draft: false,
				}),
			});
			
			// Navigate to feedback page or back to dashboard
			if (response?.show_feedback) {
				goto(`/student/feedback/${attempt.id}`);
			} else {
				goto('/student?submitted=true');
			}
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to submit';
		} finally {
			isSubmitting = false;
		}
	}

	function addIssue() {
		issues = [...issues, {
			category: 'other',
			severity: 'moderate',
			description: '',
			location_field: null,
		}];
	}

	function removeIssue(index: number) {
		issues = issues.filter((_, i) => i !== index);
	}

	function updateIssue(index: number, field: string, value: string) {
		issues = issues.map((issue, i) => 
			i === index ? { ...issue, [field]: value } : issue
		);
	}

	function getCategoryLabel(value: string): string {
		return ISSUE_CATEGORIES.find(c => c.value === value)?.label || value;
	}
</script>

<svelte:head>
	<title>Evaluate Question | GELTrain</title>
</svelte:head>

<div class="max-w-4xl mx-auto space-y-6">
	<!-- Header -->
	<div class="flex items-center justify-between">
		<button
			on:click={() => goto('/student')}
			class="flex items-center space-x-2 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white"
		>
			<ArrowLeft class="h-5 w-5" />
			<span>Back to Dashboard</span>
		</button>
		
		<div class="flex items-center space-x-4">
			{#if saveMessage}
				<span class="text-sm text-green-600 dark:text-green-400 flex items-center space-x-1">
					<CheckCircle class="h-4 w-4" />
					<span>{saveMessage}</span>
				</span>
			{/if}
			{#if lastSavedAt}
				<span class="text-sm text-gray-500 dark:text-gray-400">
					Last saved: {lastSavedAt.toLocaleTimeString()}
				</span>
			{/if}
		</div>
	</div>

	{#if isLoading}
		<div class="flex items-center justify-center py-12">
			<div class="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
		</div>
	{:else if error && !question}
		<div class="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
			<p class="text-red-700 dark:text-red-400">{error}</p>
		</div>
	{:else if question}
		<!-- Question Display -->
		<div class="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6">
			<div class="flex items-start justify-between mb-4">
				<h2 class="text-lg font-semibold text-gray-900 dark:text-white">Question to Evaluate</h2>
				<div class="flex items-center space-x-2">
					{#if evaluationItem?.difficulty_label}
						<span class="px-2 py-1 text-xs rounded-full bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300">
							{evaluationItem.difficulty_label}
						</span>
					{/if}
					{#if evaluationItem?.bloom_level}
						<span class="px-2 py-1 text-xs rounded-full bg-primary-100 dark:bg-primary-900 text-primary-700 dark:text-primary-300">
							{evaluationItem.bloom_level}
						</span>
					{/if}
				</div>
			</div>
			
			<div class="prose dark:prose-invert max-w-none">
				<p class="text-gray-900 dark:text-white whitespace-pre-wrap">{question.question_text}</p>
			</div>
			
			{#if question.options && question.options.length > 0}
				<div class="mt-4 space-y-2">
					<p class="text-sm font-medium text-gray-700 dark:text-gray-300">Options:</p>
					{#each question.options as option, i}
						<div class="flex items-start space-x-2 p-2 bg-gray-50 dark:bg-gray-700 rounded">
							<span class="font-medium text-gray-600 dark:text-gray-400">
								{String.fromCharCode(65 + i)}.
							</span>
							<span class="text-gray-900 dark:text-white">{option}</span>
						</div>
					{/each}
				</div>
			{/if}
			
			{#if question.correct_answer}
				<div class="mt-4 p-3 bg-green-50 dark:bg-green-900/20 rounded-lg">
					<p class="text-sm font-medium text-green-700 dark:text-green-400">
						Correct Answer: {question.correct_answer}
					</p>
				</div>
			{/if}
		</div>

		<!-- Evaluation Form -->
		<div class="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6 space-y-6">
			<h3 class="text-lg font-semibold text-gray-900 dark:text-white">Your Evaluation</h3>
			
			{#if error}
				<div class="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-3">
					<p class="text-sm text-red-700 dark:text-red-400">{error}</p>
				</div>
			{/if}

			<!-- Issue Detection -->
			<div>
				<p class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
					Does this question have any issues?
				</p>
				<div class="flex space-x-4">
					<button
						type="button"
						on:click={() => hasIssuesDetected = true}
						class="flex-1 flex items-center justify-center space-x-2 px-4 py-3 rounded-lg border-2 transition-colors
							{hasIssuesDetected === true 
								? 'border-red-500 bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400' 
								: 'border-gray-200 dark:border-gray-600 hover:border-gray-300 dark:hover:border-gray-500'}"
					>
						<XCircle class="h-5 w-5" />
						<span>Yes, I found issues</span>
					</button>
					<button
						type="button"
						on:click={() => hasIssuesDetected = false}
						class="flex-1 flex items-center justify-center space-x-2 px-4 py-3 rounded-lg border-2 transition-colors
							{hasIssuesDetected === false 
								? 'border-green-500 bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400' 
								: 'border-gray-200 dark:border-gray-600 hover:border-gray-300 dark:hover:border-gray-500'}"
					>
						<CheckCircle class="h-5 w-5" />
						<span>No issues found</span>
					</button>
				</div>
			</div>

			<!-- Issues List -->
			{#if hasIssuesDetected}
				<div class="space-y-4">
					<div class="flex items-center justify-between">
						<p class="block text-sm font-medium text-gray-700 dark:text-gray-300">
							Issues Identified
						</p>
						<button
							type="button"
							on:click={addIssue}
							class="flex items-center space-x-1 text-sm text-primary-600 dark:text-primary-400 hover:underline"
						>
							<Plus class="h-4 w-4" />
							<span>Add Issue</span>
						</button>
					</div>
					
					{#each issues as issue, index}
						<div class="p-4 bg-gray-50 dark:bg-gray-700 rounded-lg space-y-3">
							<div class="flex items-start justify-between">
								<span class="text-sm font-medium text-gray-700 dark:text-gray-300">
									Issue #{index + 1}
								</span>
								<button
									type="button"
									on:click={() => removeIssue(index)}
									class="text-red-500 hover:text-red-700"
								>
									<Trash2 class="h-4 w-4" />
								</button>
							</div>
							
							<div class="grid grid-cols-2 gap-3">
								<div>
									<p class="block text-xs text-gray-500 dark:text-gray-400 mb-1">Category</p>
									<select
										value={issue.category}
										on:change={(e) => updateIssue(index, 'category', e.currentTarget.value)}
										class="w-full px-3 py-2 rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm"
									>
										{#each ISSUE_CATEGORIES as cat}
											<option value={cat.value}>{cat.label}</option>
										{/each}
									</select>
								</div>
								<div>
									<p class="block text-xs text-gray-500 dark:text-gray-400 mb-1">Severity</p>
									<select
										value={issue.severity}
										on:change={(e) => updateIssue(index, 'severity', e.currentTarget.value)}
										class="w-full px-3 py-2 rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm"
									>
										{#each SEVERITY_LEVELS as sev}
											<option value={sev.value}>{sev.label}</option>
										{/each}
									</select>
								</div>
							</div>
							
							<div>
								<p class="block text-xs text-gray-500 dark:text-gray-400 mb-1">Description</p>
								<input
									type="text"
									value={issue.description}
									on:input={(e) => updateIssue(index, 'description', e.currentTarget.value)}
									placeholder="Briefly describe the issue..."
									class="w-full px-3 py-2 rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm"
								/>
							</div>
						</div>
					{/each}
					
					{#if issues.length === 0}
						<button
							type="button"
							on:click={addIssue}
							class="w-full py-8 border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-lg text-gray-500 dark:text-gray-400 hover:border-primary-500 hover:text-primary-500 transition-colors"
						>
							Click to add an issue
						</button>
					{/if}
				</div>
			{/if}

			<!-- Reasoning -->
			<div>
				<!-- svelte-ignore a11y_label_has_associated_control -->
				<label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
					Your Reasoning <span class="text-red-500">*</span>
				</label>
				<textarea
					bind:value={reasoningText}
					rows="4"
					placeholder="Explain why you believe this question has issues (or doesn't). Be specific about what you observed..."
					class="w-full px-3 py-2 rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 focus:ring-2 focus:ring-primary-500"
				></textarea>
				<p class="mt-1 text-xs text-gray-500 dark:text-gray-400">
					{reasoningText.length} characters
				</p>
			</div>

			<!-- Correction (if issues found) -->
			{#if hasIssuesDetected}
				<div>
					<label for="correction-text" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
						Suggested Correction
					</label>
					<textarea
						id="correction-text"
						bind:value={correctionText}
						rows="3"
						placeholder="How would you fix the issues you identified?"
						class="w-full px-3 py-2 rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 focus:ring-2 focus:ring-primary-500"
					></textarea>
				</div>
			{/if}

			<!-- Confidence Slider -->
			<div>
				<p class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
					How confident are you in your evaluation?
				</p>
				<div class="flex items-center space-x-4">
					<span class="text-sm text-gray-500 dark:text-gray-400">Not sure</span>
					<input
						type="range"
						bind:value={confidenceScore}
						min="0"
						max="1"
						step="0.1"
						class="flex-1 h-2 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer"
					/>
					<span class="text-sm text-gray-500 dark:text-gray-400">Very confident</span>
				</div>
				<p class="mt-1 text-center text-sm font-medium text-gray-700 dark:text-gray-300">
					{Math.round(confidenceScore * 100)}%
				</p>
			</div>

			<!-- Actions -->
			<div class="flex items-center justify-between pt-4 border-t border-gray-200 dark:border-gray-700">
				<button
					type="button"
					on:click={saveDraft}
					disabled={isSaving}
					class="flex items-center space-x-2 px-4 py-2 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
				>
					<Save class="h-5 w-5" />
					<span>{isSaving ? 'Saving...' : 'Save Draft'}</span>
				</button>
				
				<button
					type="button"
					on:click={submitAttempt}
					disabled={isSubmitting}
					class="flex items-center space-x-2 px-6 py-2 bg-primary-600 hover:bg-primary-700 text-white rounded-lg transition-colors disabled:opacity-50"
				>
					<Send class="h-5 w-5" />
					<span>{isSubmitting ? 'Submitting...' : 'Submit Evaluation'}</span>
				</button>
			</div>
		</div>
	{/if}
</div>
