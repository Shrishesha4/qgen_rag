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
		background: linear-gradient(145deg, rgba(255, 255, 255, 0.78), rgba(255, 255, 255, 0.62));
		border: 1px solid rgba(255, 255, 255, 0.45);
		border-radius: 1rem;
		padding: 1.5rem;
		margin-bottom: 1.5rem;
		transition: all 0.3s ease;
		backdrop-filter: blur(10px);
		-webkit-backdrop-filter: blur(10px);
		box-shadow: 0 8px 24px rgba(10, 17, 29, 0.12);
	}

	.step-card.active {
		background: linear-gradient(145deg, rgba(var(--theme-primary-rgb), 0.2), rgba(255, 255, 255, 0.72));
		border-color: rgba(var(--theme-primary-rgb), 0.35);
		box-shadow: 0 12px 28px rgba(var(--theme-primary-rgb), 0.2);
	}

	.step-card.completed {
		background: linear-gradient(145deg, rgba(16, 185, 129, 0.15), rgba(255, 255, 255, 0.7));
		border-color: rgba(16, 185, 129, 0.32);
	}

	.step-card.error {
		background: linear-gradient(145deg, rgba(239, 68, 68, 0.16), rgba(255, 255, 255, 0.72));
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
		color: var(--theme-text-primary, #1a1a2e);
		line-height: 1.3;
	}

	.step-description {
		margin: 0;
		font-size: 0.9rem;
		color: var(--theme-text-secondary, rgba(0, 0, 0, 0.58));
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
		background: rgba(107, 114, 128, 0.14);
		color: #4b5563;
		border: 1px solid rgba(107, 114, 128, 0.3);
	}

	.step-content {
		margin-bottom: 1rem;
	}

	.step-actions {
		display: flex;
		justify-content: flex-end;
		padding-top: 1rem;
		border-top: 1px solid rgba(18, 28, 45, 0.12);
	}

	.action-btn {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.72rem 1.4rem;
		border-radius: 0.65rem;
		border: 1px solid transparent;
		font-size: 0.9rem;
		font-weight: 700;
		cursor: pointer;
		transition: all 0.3s ease;
		min-width: 140px;
		justify-content: center;
	}

	.action-btn.primary {
		background: linear-gradient(180deg, rgba(var(--theme-primary-rgb), 0.94), rgba(var(--theme-primary-rgb), 0.76));
		color: white;
		border-color: rgba(var(--theme-primary-rgb), 0.6);
		box-shadow: 0 8px 18px rgba(var(--theme-primary-rgb), 0.3);
	}

	.action-btn.primary:hover:not(:disabled) {
		filter: brightness(1.06);
		transform: translateY(-1px);
		box-shadow: 0 10px 22px rgba(var(--theme-primary-rgb), 0.32);
	}

	.action-btn.danger {
		background: linear-gradient(180deg, rgba(220, 38, 38, 0.92), rgba(153, 27, 27, 0.86));
		color: white;
		border-color: rgba(239, 68, 68, 0.55);
		box-shadow: 0 8px 18px rgba(239, 68, 68, 0.28);
	}

	.action-btn.danger:hover:not(:disabled) {
		filter: brightness(1.06);
		transform: translateY(-1px);
		box-shadow: 0 10px 22px rgba(239, 68, 68, 0.34);
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
