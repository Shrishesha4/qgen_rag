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
		padding: 0.5rem 1rem;
		border-radius: 2rem;
		border: 1px solid rgba(255, 255, 255, 0.2);
		background: rgba(255, 255, 255, 0.1);
		color: rgba(255, 255, 255, 0.9);
		font-size: 0.85rem;
		font-weight: 500;
		cursor: pointer;
		transition: all 0.3s ease;
		backdrop-filter: blur(10px);
	}

	.toggle-btn:hover {
		background: rgba(255, 255, 255, 0.15);
		border-color: rgba(255, 255, 255, 0.3);
		transform: translateY(-1px);
	}

	.toggle-btn.advanced {
		background: rgba(59, 130, 246, 0.2);
		border-color: rgba(59, 130, 246, 0.4);
		color: #93c5fd;
	}

	.toggle-btn.advanced:hover {
		background: rgba(59, 130, 246, 0.3);
		border-color: rgba(59, 130, 246, 0.6);
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
		.toggle-text {
			display: none;
		}

		.toggle-btn {
			padding: 0.5rem;
			min-width: auto;
		}
	}
</style>
