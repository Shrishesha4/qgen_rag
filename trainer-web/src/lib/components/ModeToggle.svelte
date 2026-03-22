<script lang="ts">
	export let isAdvanced = false;
	
	function toggleMode() {
		isAdvanced = !isAdvanced;
	}
</script>

<div class="mode-toggle">
	<button 
		type="button"
		class="toggle-btn" 
		class:advanced={isAdvanced}
		onclick={toggleMode}
		aria-label="Toggle between simple and advanced mode"
	>
		{#if isAdvanced}
			<span class="toggle-icon">⚙️</span>
			<span class="toggle-text">Advanced Mode</span>
		{:else}
			<span class="toggle-icon">👩‍🏫</span>
			<span class="toggle-text">Simple Mode</span>
		{/if}
	</button>
</div>

<style>
	.mode-toggle {
		display: flex;
		justify-content: flex-end;
		margin-bottom: 1rem;
	}

	.toggle-btn {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.52rem 1rem;
		border-radius: 2rem;
		border: 1px solid rgba(255, 255, 255, 0.28);
		background: linear-gradient(160deg, rgba(51, 65, 85, 0.9), rgba(30, 41, 59, 0.84));
		color: #f8fafc;
		font-size: 0.85rem;
		font-weight: 600;
		cursor: pointer;
		transition: all 0.3s ease;
		backdrop-filter: blur(12px);
		box-shadow: 0 8px 20px rgba(9, 15, 27, 0.2);
	}

	.toggle-btn:hover {
		background: linear-gradient(160deg, rgba(71, 85, 105, 0.95), rgba(51, 65, 85, 0.88));
		border-color: rgba(255, 255, 255, 0.42);
		transform: translateY(-1px);
	}

	.toggle-btn.advanced {
		background: linear-gradient(160deg, rgba(var(--theme-primary-rgb), 0.95), rgba(var(--theme-primary-rgb), 0.78));
		border-color: rgba(var(--theme-primary-rgb), 0.95);
		color: #ffffff;
	}

	.toggle-btn.advanced:hover {
		background: linear-gradient(160deg, rgba(var(--theme-primary-rgb), 1), rgba(var(--theme-primary-rgb), 0.86));
		border-color: rgba(var(--theme-primary-rgb), 1);
	}

	.toggle-icon {
		font-size: 1rem;
	}

	.toggle-text {
		font-size: 0.8rem;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}

	@media (max-width: 640px) {
		.toggle-btn {
			padding: 0.48rem 0.78rem;
			min-width: auto;
			font-size: 0.76rem;
			gap: 0.4rem;
		}

		.toggle-text {
			font-size: 0.72rem;
		}
	}
</style>
