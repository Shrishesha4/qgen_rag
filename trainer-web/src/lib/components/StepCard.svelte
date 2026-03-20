<script lang="ts">
	export let stepNumber = 1;
	export let title = "";
	export let description = "";
	export let icon = "";
	export let isActive = false;
	export let isCompleted = false;
	export let isInProgress = false;
	export let hasError = false;
	export let canProceed = false;
	export let isBusy = false;
	export let buttonText = "";
	export let onAction: (() => Promise<void>) | null = null;

	async function handleAction() {
		console.log('StepCard.handleAction called', { onAction: !!onAction, isBusy, canProceed, buttonText });
		if (onAction && !isBusy && canProceed) {
			await onAction();
		} else {
			console.log('Action blocked', { onAction: !!onAction, isBusy, canProceed });
		}
	}

	function getStepColor() {
		if (hasError) return '#ef4444';
		if (isCompleted) return '#10b981';
		if (isInProgress) return '#3b82f6';
		if (isActive) return '#3b82f6';
		return '#6b7280';
	}

	function getButtonStyle() {
		if (!canProceed) return 'disabled';
		if (hasError) return 'danger';
		return 'primary';
	}
</script>

<div class="step-card" class:active={isActive} class:completed={isCompleted} class:error={hasError}>
	<div class="step-header">
		<div class="step-icon" style="border-color: {getStepColor()}; color: {getStepColor()}">
			{#if isCompleted}
				✓
			{:else if isInProgress}
				⟳
			{:else if hasError}
				✕
			{:else}
				{icon}
			{/if}
		</div>
		<div class="step-info">
			<h3 class="step-title">Step {stepNumber}: {title}</h3>
			<p class="step-description">{description}</p>
		</div>
		<div class="step-status">
			{#if isCompleted}
				<span class="status-badge completed">Completed</span>
			{:else if isInProgress}
				<span class="status-badge active">In Progress</span>
			{:else if hasError}
				<span class="status-badge error">Needs Attention</span>
			{:else if isActive}
				<span class="status-badge active">Current Step</span>
			{:else}
				<span class="status-badge waiting">Waiting</span>
			{/if}
		</div>
	</div>

	<div class="step-content">
		<slot />
	</div>

	{#if onAction && isActive}
		<div class="step-actions">
			<button 
				type="button"
				class="action-btn {getButtonStyle()}"
				disabled={isBusy || !canProceed}
				onclick={handleAction}
			>
				{#if isBusy}
					<div class="btn-spinner">⟳</div>
					Processing...
				{:else}
					{buttonText}
				{/if}
			</button>
		</div>
	{/if}
</div>

<style>
	.step-card {
		background: rgba(255, 255, 255, 0.03);
		border: 1px solid rgba(255, 255, 255, 0.1);
		border-radius: 1rem;
		padding: 1.5rem;
		margin-bottom: 1.5rem;
		transition: all 0.3s ease;
		backdrop-filter: blur(10px);
	}

	.step-card.active {
		background: rgba(59, 130, 246, 0.1);
		border-color: rgba(59, 130, 246, 0.3);
		box-shadow: 0 0 20px rgba(59, 130, 246, 0.2);
	}

	.step-card.completed {
		background: rgba(16, 185, 129, 0.05);
		border-color: rgba(16, 185, 129, 0.2);
	}

	.step-card.error {
		background: rgba(239, 68, 68, 0.1);
		border-color: rgba(239, 68, 68, 0.3);
	}

	.step-header {
		display: flex;
		align-items: flex-start;
		gap: 1rem;
		margin-bottom: 1rem;
	}

	.step-icon {
		width: 48px;
		height: 48px;
		border-radius: 50%;
		border: 2px solid #6b7280;
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 1.5rem;
		font-weight: bold;
		flex-shrink: 0;
		transition: all 0.3s ease;
	}

	.step-info {
		flex: 1;
		min-width: 0;
	}

	.step-title {
		margin: 0 0 0.5rem 0;
		font-size: 1.1rem;
		font-weight: 600;
		color: rgba(255, 255, 255, 0.95);
		line-height: 1.3;
	}

	.step-description {
		margin: 0;
		font-size: 0.9rem;
		color: rgba(255, 255, 255, 0.7);
		line-height: 1.4;
	}

	.step-status {
		flex-shrink: 0;
	}

	.status-badge {
		display: inline-block;
		padding: 0.25rem 0.75rem;
		border-radius: 1rem;
		font-size: 0.7rem;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}

	.status-badge.completed {
		background: rgba(16, 185, 129, 0.2);
		color: #6ee7b7;
		border: 1px solid rgba(16, 185, 129, 0.3);
	}

	.status-badge.active {
		background: rgba(59, 130, 246, 0.2);
		color: #93c5fd;
		border: 1px solid rgba(59, 130, 246, 0.3);
	}

	.status-badge.error {
		background: rgba(239, 68, 68, 0.2);
		color: #fca5a5;
		border: 1px solid rgba(239, 68, 68, 0.3);
	}

	.status-badge.waiting {
		background: rgba(107, 114, 128, 0.2);
		color: #9ca3af;
		border: 1px solid rgba(107, 114, 128, 0.3);
	}

	.step-content {
		margin-bottom: 1rem;
	}

	.step-actions {
		display: flex;
		justify-content: flex-end;
		padding-top: 1rem;
		border-top: 1px solid rgba(255, 255, 255, 0.1);
	}

	.action-btn {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.75rem 1.5rem;
		border-radius: 0.5rem;
		border: 1px solid rgba(255, 255, 255, 0.2);
		font-size: 0.9rem;
		font-weight: 600;
		cursor: pointer;
		transition: all 0.3s ease;
		min-width: 140px;
		justify-content: center;
	}

	.action-btn.primary {
		background: linear-gradient(135deg, rgba(59, 130, 246, 0.5), rgba(59, 130, 246, 0.3));
		color: white;
		border-color: rgba(59, 130, 246, 0.5);
	}

	.action-btn.primary:hover:not(:disabled) {
		background: linear-gradient(135deg, rgba(59, 130, 246, 0.6), rgba(59, 130, 246, 0.4));
		transform: translateY(-1px);
		box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
	}

	.action-btn.danger {
		background: linear-gradient(135deg, rgba(239, 68, 68, 0.5), rgba(239, 68, 68, 0.3));
		color: white;
		border-color: rgba(239, 68, 68, 0.5);
	}

	.action-btn.danger:hover:not(:disabled) {
		background: linear-gradient(135deg, rgba(239, 68, 68, 0.6), rgba(239, 68, 68, 0.4));
		transform: translateY(-1px);
		box-shadow: 0 4px 12px rgba(239, 68, 68, 0.3);
	}

	.action-btn:disabled {
		opacity: 0.5;
		cursor: not-allowed;
		transform: none;
		box-shadow: none;
	}

	.btn-spinner {
		animation: spin 1s linear infinite;
	}

	@keyframes spin {
		from { transform: rotate(0deg); }
		to { transform: rotate(360deg); }
	}

	@media (max-width: 640px) {
		.step-card {
			padding: 1rem;
		}

		.step-header {
			flex-direction: column;
			gap: 0.75rem;
		}

		.step-icon {
			width: 40px;
			height: 40px;
			font-size: 1.2rem;
		}

		.step-title {
			font-size: 1rem;
		}

		.step-description {
			font-size: 0.85rem;
		}

		.step-status {
			align-self: flex-start;
		}

		.action-btn {
			padding: 0.6rem 1rem;
			font-size: 0.85rem;
			min-width: 120px;
		}
	}
</style>
