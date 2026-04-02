<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';

	onMount(() => {
		goto('/teacher/train');
	});
</script>

<svelte:head>
	<title>Vetting - Teacher Console</title>
</svelte:head>

<div class="redirect-state">
	<div class="spinner"></div>
	<p>Redirecting to Vetting...</p>
</div>

<style>
	.redirect-state {
		min-height: 56vh;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 0.8rem;
		color: var(--theme-text-muted);
	}

	.spinner {
		width: 28px;
		height: 28px;
		border-radius: 50%;
		border: 3px solid rgba(255, 255, 255, 0.15);
		border-top-color: var(--theme-primary);
		animation: spin 0.8s linear infinite;
	}

	@keyframes spin {
		to { transform: rotate(360deg); }
	}
</style>
