<script lang="ts">
	import ProgressIndicator from './ProgressIndicator.svelte';
	import StepCard from './StepCard.svelte';

	export let currentStep = 0;
	export let stepStatuses: ('waiting' | 'in-progress' | 'completed' | 'error')[] = [];
	export let busy = false;
	export let error = '';
	export let stepSummaries: string[] = [];

	// Step configurations
	const steps = [
		{
			id: 'prepare',
			title: 'Prepare Training Materials',
			description: 'Gather and organize the questions and answers your AI will learn from.',
			icon: '📚'
		},
		{
			id: 'train',
			title: 'Train Your AI Assistant',
			description: 'Teach the AI using your prepared materials to create a smart question generator.',
			icon: '🧠'
		},
		{
			id: 'evaluate',
			title: 'Check Quality',
			description: 'Test how well your AI performs and make sure it meets your standards.',
			icon: '✅'
		},
		{
			id: 'canary',
			title: 'Try with Few Students',
			description: 'Test the AI with a small group before using it with your entire class.',
			icon: '🧪'
		},
		{
			id: 'promote',
			title: 'Use with All Students (Optional)',
			description: 'Deploy your trained AI for use with all your students.',
			icon: '🚀'
		}
	];

	// Step state
	export let days = 30;
	export let confidenceMin = 0.0;
	export let trainingMethod = 'sft+dpo';
	export let selectedVersionId = '';
	export let selectedDatasetTag = '';

	// Data from parent
	export let versions: any[] = [];
	export let onBuildDataset: (() => Promise<void>) | null = null;
	export let onTriggerTraining: (() => Promise<void>) | null = null;
	export let onEvaluate: (() => Promise<void>) | null = null;
	export let onCanary: (() => Promise<void>) | null = null;
	export let onPromote: (() => Promise<void>) | null = null;

	function canProceedToStep(stepIndex: number): boolean {
		if (stepIndex === 0) return true; // Can always start with dataset prep
		if (stepIndex === 1) return stepStatuses[0] === 'completed'; // Need dataset ready
		if (stepIndex === 2) return stepStatuses[1] === 'completed'; // Need training done
		if (stepIndex === 3) return stepStatuses[2] === 'completed'; // Need evaluation done
		if (stepIndex === 4) return stepStatuses[3] === 'completed'; // Need canary done
		return false;
	}

	function getButtonText(stepIndex: number): string {
		switch (stepIndex) {
			case 0: return 'Build Dataset';
			case 1: return 'Start Training';
			case 2: return 'Run Quality Check';
			case 3: return 'Start Classroom Trial';
			case 4: return 'Deploy to Students';
			default: return 'Continue';
		}
	}

	function getActionHandler(stepIndex: number) {
		switch (stepIndex) {
			case 0: return onBuildDataset;
			case 1: return onTriggerTraining;
			case 2: return onEvaluate;
			case 3: return onCanary;
			case 4: return onPromote;
			default: return null;
		}
	}

	function goToNextStep() {
		if (currentStep < steps.length - 1 && canProceedToStep(currentStep + 1)) {
			currentStep++;
		}
	}

	function goToPreviousStep() {
		if (currentStep > 0) {
			currentStep--;
		}
	}

	function getSummary(stepIndex: number): string {
		return stepSummaries[stepIndex] ?? '';
	}

	$: canGoNext = currentStep < steps.length - 1 && canProceedToStep(currentStep + 1);
	$: canGoPrevious = currentStep > 0;
</script>

<div class="workflow-wizard">
	<ProgressIndicator 
		currentStep={currentStep}
		totalSteps={steps.length}
		stepStatuses={stepStatuses}
	/>

	<div class="wizard-content">
		{#each steps as step, i}
			<StepCard
				stepNumber={i + 1}
				title={step.title}
				description={step.description}
				icon={step.icon}
				isActive={i === currentStep}
				isCompleted={stepStatuses[i] === 'completed'}
 				isInProgress={stepStatuses[i] === 'in-progress'}
				hasError={stepStatuses[i] === 'error'}
				canProceed={canProceedToStep(i)}
				isBusy={busy && i === currentStep}
				buttonText={getButtonText(i)}
				onAction={getActionHandler(i)}
			>
				{#if i === 0}
					<!-- Dataset Preparation Step -->
					{#if currentStep === 0}
						<div class="step-form">
							<div class="form-row">
								<label for="dataset-days">Time Period</label>
								<div class="input-group">
									<input 
										id="dataset-days" 
										type="number" 
										min="1" 
										max="365" 
										bind:value={days} 
										disabled={busy}
									/>
									<span class="input-suffix">days</span>
								</div>
								<small>How many recent days of materials to include</small>
							</div>
							<div class="form-row">
								<label for="confidence-min">Quality Filter</label>
								<div class="input-group">
									<input 
										id="confidence-min" 
										type="number" 
										min="0" 
										max="1" 
										step="0.05" 
										bind:value={confidenceMin}
										disabled={busy}
									/>
									<span class="input-suffix">confidence</span>
								</div>
								<small>Minimum quality level (0.0 = include all, 1.0 = only best)</small>
							</div>
						</div>
					{/if}
					{#if getSummary(i)}
						<div class="summary-box" class:summary-success={stepStatuses[i] === 'completed'} class:summary-progress={stepStatuses[i] === 'in-progress'}>
							<div class="summary-title">Current status</div>
							<p class="summary-text">{getSummary(i)}</p>
						</div>
					{/if}
				{:else if i === 1}
					<!-- Training Step -->
					{#if currentStep === 1}
						<div class="step-form">
							<div class="form-row">
								<label for="training-method">Training Method</label>
								<select id="training-method" bind:value={trainingMethod} disabled={busy}>
									<option value="sft">Basic Training (SFT)</option>
									<option value="dpo">Advanced Training (DPO)</option>
									<option value="sft+dpo">Complete Training (SFT + DPO)</option>
								</select>
								<small>Recommended: Complete Training for best results</small>
							</div>
						</div>
					{/if}
					{#if getSummary(i)}
						<div class="summary-box" class:summary-success={stepStatuses[i] === 'completed'} class:summary-progress={stepStatuses[i] === 'in-progress'}>
							<div class="summary-title">Current status</div>
							<p class="summary-text">{getSummary(i)}</p>
						</div>
					{/if}
				{:else if i === 2}
					<!-- Evaluation Step -->
					{#if currentStep === 2}
						<div class="step-form">
							<div class="form-row">
								<label for="selected-version">AI Version</label>
								<select id="selected-version" bind:value={selectedVersionId} disabled={busy}>
									{#each versions as v}
										<option value={v.id}>{v.version_tag}</option>
									{/each}
								</select>
								<small>Choose which AI version to test</small>
							</div>
							<div class="form-row">
								<label for="dataset-tag">Test Dataset</label>
								<input 
									id="dataset-tag" 
									bind:value={selectedDatasetTag} 
									placeholder="latest" 
									disabled={busy}
								/>
								<small>Which dataset to use for testing</small>
							</div>
						</div>
					{/if}
					{#if getSummary(i)}
						<div class="summary-box" class:summary-success={stepStatuses[i] === 'completed'} class:summary-progress={stepStatuses[i] === 'in-progress'}>
							<div class="summary-title">Current status</div>
							<p class="summary-text">{getSummary(i)}</p>
						</div>
					{/if}
				{:else if i === 3}
					<!-- Canary Step -->
					<div class="step-info">
						<div class="info-card">
							<h4>🧪 Classroom Trial</h4>
							<p>This will test your AI with a small group of students (about 10% of your class) to make sure it works well before using it with everyone.</p>
							<div class="info-points">
								<div class="info-point">✅ Safe testing with small group</div>
								<div class="info-point">📊 Real performance feedback</div>
								<div class="info-point">🔄 Easy rollback if needed</div>
							</div>
						</div>
						{#if getSummary(i)}
							<div class="summary-box" class:summary-success={stepStatuses[i] === 'completed'} class:summary-progress={stepStatuses[i] === 'in-progress'}>
								<div class="summary-title">Current status</div>
								<p class="summary-text">{getSummary(i)}</p>
							</div>
						{/if}
					</div>
				{:else if i === 4}
					<!-- Promote Step -->
					<div class="step-info">
						<div class="optional-note">Optional step: you can stop after the classroom trial and deploy later whenever you are ready.</div>
						<div class="info-card">
							<h4>🚀 Ready to Deploy!</h4>
							<p>Your AI has passed all tests and is ready to help all your students generate better questions.</p>
							<div class="info-points">
								<div class="info-point">✨ Quality tested and approved</div>
								<div class="info-point">👥 Available to all students</div>
								<div class="info-point">📈 Improved learning experience</div>
							</div>
						</div>
						{#if getSummary(i)}
							<div class="summary-box" class:summary-success={stepStatuses[i] === 'completed'} class:summary-progress={stepStatuses[i] === 'in-progress'}>
								<div class="summary-title">Current status</div>
								<p class="summary-text">{getSummary(i)}</p>
							</div>
						{/if}
					</div>
				{/if}
			</StepCard>
		{/each}
	</div>

	<div class="wizard-navigation">
		<button 
			type="button"
			class="nav-btn prev"
			disabled={!canGoPrevious || busy}
			onclick={goToPreviousStep}
		>
			← Previous Step
		</button>
		
		<div class="nav-progress">
			Step {currentStep + 1} of {steps.length}
			{#if currentStep >= 3}
				<div class="nav-optional-note">Deployment is optional.</div>
			{/if}
		</div>
		
		<button 
			type="button"
			class="nav-btn next"
			disabled={!canGoNext || busy}
			onclick={goToNextStep}
		>
			Next Step →
		</button>
	</div>

	{#if error}
		<div class="error-message">
			<span class="error-icon">⚠️</span>
			{error}
		</div>
	{/if}
</div>

<style>
	.workflow-wizard {
		max-width: 880px;
		margin: 0 auto;
		padding: 0.8rem 0.4rem;
	}

	.wizard-content {
		margin-bottom: 2rem;
	}

	.step-form {
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}

	.form-row {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.form-row label {
		font-weight: 600;
		color: var(--theme-text-primary, #1a1a2e);
		font-size: 0.9rem;
	}

	.input-group {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	.input-group input,
	.form-row input,
	.form-row select {
		flex: 1;
		padding: 0.75rem;
		border-radius: 0.65rem;
		border: 1px solid rgba(18, 28, 45, 0.14);
		background: rgba(255, 255, 255, 0.75);
		color: var(--theme-text-primary, #1a1a2e);
		font-size: 0.9rem;
		outline: none;
		transition: all 0.3s ease;
	}

	.input-group input:focus,
	.form-row input:focus,
	.form-row select:focus {
		border-color: rgba(var(--theme-primary-rgb), 0.5);
		box-shadow: 0 0 0 3px rgba(var(--theme-primary-rgb), 0.14);
	}

	.input-suffix {
		color: var(--theme-text-secondary, rgba(0, 0, 0, 0.55));
		font-size: 0.8rem;
		font-weight: 500;
	}

	.form-row small {
		color: var(--theme-text-secondary, rgba(0, 0, 0, 0.56));
		font-size: 0.75rem;
		font-style: italic;
	}

	.step-info {
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}

	.info-card {
		background: linear-gradient(140deg, rgba(255, 255, 255, 0.72), rgba(255, 255, 255, 0.6));
		border-radius: 0.75rem;
		padding: 1rem;
		border: 1px solid rgba(255, 255, 255, 0.4);
	}

	.info-card h4 {
		margin: 0 0 0.75rem 0;
		font-size: 1rem;
		font-weight: 600;
		color: var(--theme-text-primary, #1a1a2e);
	}

	.info-card p {
		margin: 0 0 1rem 0;
		font-size: 0.85rem;
		color: var(--theme-text-secondary, rgba(0, 0, 0, 0.62));
		line-height: 1.4;
	}

	.info-points {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.info-point {
		font-size: 0.8rem;
		color: var(--theme-text-secondary, rgba(0, 0, 0, 0.62));
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	.summary-box {
		background: rgba(255, 255, 255, 0.54);
		border: 1px solid rgba(255, 255, 255, 0.46);
		border-radius: 0.75rem;
		padding: 0.9rem;
	}

	.summary-success {
		border-color: rgba(16, 185, 129, 0.25);
		background: rgba(16, 185, 129, 0.08);
	}

	.summary-progress {
		border-color: rgba(59, 130, 246, 0.25);
		background: rgba(59, 130, 246, 0.08);
	}

	.summary-title {
		font-size: 0.75rem;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		font-weight: 700;
		color: var(--theme-text-secondary, rgba(0, 0, 0, 0.62));
		margin-bottom: 0.35rem;
	}

	.summary-text {
		margin: 0;
		font-size: 0.85rem;
		line-height: 1.45;
		color: var(--theme-text-primary, #1a1a2e);
	}

	.optional-note {
		padding: 0.75rem 0.9rem;
		border-radius: 0.75rem;
		background: rgba(245, 158, 11, 0.16);
		border: 1px solid rgba(245, 158, 11, 0.32);
		color: #92400e;
		font-size: 0.82rem;
		line-height: 1.4;
		font-weight: 600;
	}

	.wizard-navigation {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1rem;
		padding: 1rem;
		background: linear-gradient(140deg, rgba(255, 255, 255, 0.72), rgba(255, 255, 255, 0.58));
		border-radius: 0.75rem;
		border: 1px solid rgba(255, 255, 255, 0.45);
	}

	.nav-btn {
		padding: 0.75rem 1.5rem;
		border-radius: 0.65rem;
		border: 1px solid rgba(var(--theme-primary-rgb), 0.45);
		background: linear-gradient(180deg, rgba(var(--theme-primary-rgb), 0.9), rgba(var(--theme-primary-rgb), 0.72));
		color: #ffffff;
		font-size: 0.85rem;
		font-weight: 700;
		cursor: pointer;
		transition: all 0.3s ease;
		box-shadow: 0 8px 18px rgba(var(--theme-primary-rgb), 0.25);
	}

	.nav-btn:hover:not(:disabled) {
		filter: brightness(1.05);
		transform: translateY(-1px);
	}

	.nav-btn:disabled {
		opacity: 0.4;
		cursor: not-allowed;
		transform: none;
	}

	.nav-progress {
		font-size: 0.8rem;
		color: var(--theme-text-secondary, rgba(0, 0, 0, 0.58));
		font-weight: 500;
		text-align: center;
	}

	.nav-optional-note {
		margin-top: 0.25rem;
		font-size: 0.72rem;
		color: #fcd34d;
	}

	.error-message {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 1rem;
		background: rgba(239, 68, 68, 0.14);
		border: 1px solid rgba(239, 68, 68, 0.3);
		border-radius: 0.75rem;
		color: #7f1d1d;
		font-size: 0.85rem;
		margin-top: 1rem;
		font-weight: 600;
	}

	.error-icon {
		font-size: 1.2rem;
	}

	@media (max-width: 640px) {
		.workflow-wizard {
			padding: 0.5rem;
		}

		.wizard-navigation {
			flex-direction: column;
			gap: 0.75rem;
			text-align: center;
		}

		.nav-btn {
			width: 100%;
		}

		.info-points {
			gap: 0.4rem;
		}

		.info-point {
			font-size: 0.75rem;
		}
	}
</style>
