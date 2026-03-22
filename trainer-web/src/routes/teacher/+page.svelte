<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { session } from '$lib/session';

	onMount(() => {
		const unsub = session.subscribe((s) => {
			if (!s) {
				goto('/teacher/login');
			} else if (s.user.role === 'teacher') {
				goto('/teacher/subjects');
			} else {
				goto('/');
			}
		});
		return unsub;
	});
</script>

<svelte:head>
	<title>Teacher — VQuest Trainer</title>
</svelte:head>

<div class="loading">
	<div class="spinner"></div>
	<p>Loading...</p>
</div>

<style>
	.loading {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		min-height: 100vh;
		gap: 1rem;
		color: var(--theme-text);
	}

	.spinner {
		width: 2rem;
		height: 2rem;
		border: 2px solid rgba(255, 255, 255, 0.1);
		border-top: 2px solid var(--theme-primary);
		border-radius: 50%;
		animation: spin 1s linear infinite;
	}

	@keyframes spin {
		0% { transform: rotate(0deg); }
		100% { transform: rotate(360deg); }
	}
</style>
