<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';

	onMount(() => {
		goto('/login', { replaceState: true });
	});
</script>

<svelte:head>
	<title>Redirecting… — VQuest</title>
</svelte:head>

<div style="display: flex; justify-content: center; align-items: center; min-height: 100vh; color: var(--theme-text-muted);">
	Redirecting to login…
</div>
