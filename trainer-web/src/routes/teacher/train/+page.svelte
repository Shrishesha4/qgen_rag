<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { session } from '$lib/session';

	onMount(() => {
		const unsub = session.subscribe((s) => {
			if (!s) {
				goto('/teacher/login');
				return;
			}
			goto('/teacher/train/existing');
		});
		return unsub;
	});
</script>

<svelte:head>
	<title>Train Topic — VQuest Trainer</title>
</svelte:head>

<div class="redirect-state">
	<div class="spinner"></div>
	<p>Opening subjects…</p>
</div>

<style>
	.redirect-state {
		min-height: 100vh;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 0.9rem;
		color: var(--theme-text-muted);
	}

	.spinner {
		width: 30px;
		height: 30px;
		border-radius: 50%;
		border: 3px solid rgba(255,255,255,0.2);
		border-top-color: var(--theme-primary);
		animation: spin 0.8s linear infinite;
	}

	@keyframes spin {
		to { transform: rotate(360deg); }
	}
</style>
