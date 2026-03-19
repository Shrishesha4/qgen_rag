<script lang="ts">
	export let currentStep = 0;
	export let totalSteps = 5;
	export let stepStatuses: ('waiting' | 'in-progress' | 'completed' | 'error')[] = [];

	const steps = [
		{ number: 1, name: 'Prepare Materials', icon: '📚' },
		{ number: 2, name: 'Train AI', icon: '🧠' },
		{ number: 3, name: 'Check Quality', icon: '✅' },
		{ number: 4, name: 'Classroom Trial', icon: '🧪' },
		{ number: 5, name: 'Use with Students', icon: '🚀' }
	];

	function getStepStatus(stepIndex: number) {
		return stepStatuses[stepIndex] || 'waiting';
	}

	function getStepColor(status: string) {
		switch (status) {
			case 'completed': return '#10b981';
			case 'in-progress': return '#3b82f6';
			case 'error': return '#ef4444';
			default: return '#6b7280';
		}
	}

	function getStepIcon(status: string) {
		switch (status) {
			case 'completed': return '✓';
			case 'in-progress': return '⟳';
			case 'error': return '✕';
			default: return '';
		}
	}
</script>

<div class="progress-indicator">
	<div class="progress-bar">
		<div class="progress-fill" style="width: {(currentStep / (totalSteps - 1)) * 100}%"></div>
	</div>
	
	<div class="steps">
		{#each steps as step, i}
			<div class="step" class:active={i === currentStep} class:completed={getStepStatus(i) === 'completed'} class:error={getStepStatus(i) === 'error'}>
				<div class="step-circle" style="border-color: {getStepColor(getStepStatus(i))}; background: {getStepStatus(i) === 'in-progress' ? getStepColor(getStepStatus(i)) : 'transparent'}">
					{#if getStepStatus(i) === 'completed' || getStepStatus(i) === 'error'}
						<span class="step-status-icon" style="color: {getStepColor(getStepStatus(i))}">{getStepIcon(getStepStatus(i))}</span>
					{:else}
						<span class="step-number">{step.icon}</span>
					{/if}
				</div>
				<div class="step-label">
					<div class="step-name">{step.name}</div>
					<div class="step-status" style="color: {getStepColor(getStepStatus(i))}">
						{#if getStepStatus(i) === 'completed'}
							Done
						{:else if getStepStatus(i) === 'in-progress'}
							In Progress
						{:else if getStepStatus(i) === 'error'}
							Needs Fix
						{:else}
							Waiting
						{/if}
					</div>
				</div>
			</div>
		{/each}
	</div>
</div>

<style>
	.progress-indicator {
		margin-bottom: 2rem;
	}

	.progress-bar {
		width: 100%;
		height: 4px;
		background: rgba(255, 255, 255, 0.1);
		border-radius: 2px;
		margin-bottom: 1.5rem;
		overflow: hidden;
	}

	.progress-fill {
		height: 100%;
		background: linear-gradient(90deg, #3b82f6, #10b981);
		border-radius: 2px;
		transition: width 0.5s ease;
	}

	.steps {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		gap: 0.5rem;
		position: relative;
	}

	.step {
		display: flex;
		flex-direction: column;
		align-items: center;
		flex: 1;
		min-width: 0;
	}

	.step-circle {
		width: 48px;
		height: 48px;
		border-radius: 50%;
		border: 2px solid #6b7280;
		display: flex;
		align-items: center;
		justify-content: center;
		background: transparent;
		transition: all 0.3s ease;
		margin-bottom: 0.5rem;
	}

	.step.active .step-circle {
		border-width: 3px;
		transform: scale(1.1);
	}

	.step-number {
		font-size: 1.2rem;
	}

	.step-status-icon {
		font-weight: bold;
		font-size: 1.1rem;
	}

	.step-label {
		text-align: center;
		width: 100%;
	}

	.step-name {
		font-size: 0.75rem;
		font-weight: 600;
		color: rgba(255, 255, 255, 0.9);
		margin-bottom: 0.2rem;
		line-height: 1.2;
	}

	.step-status {
		font-size: 0.65rem;
		font-weight: 500;
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}

	@media (max-width: 640px) {
		.step-circle {
			width: 40px;
			height: 40px;
		}

		.step-number {
			font-size: 1rem;
		}

		.step-name {
			font-size: 0.65rem;
		}

		.step-status {
			font-size: 0.55rem;
		}
	}
</style>
