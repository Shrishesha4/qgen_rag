<script lang="ts">
	import './layout.css';
	import { onMount } from 'svelte';
	import { initTheme } from '$lib/theme';

	let { children } = $props();

	onMount(() => {
		initTheme();
	});
</script>

<div class="app-shell">
	{@render children()}
</div>

<style>
	.app-shell {
		min-height: 100vh;
		background: var(--theme-bg);
		background-color: var(--theme-bg-color);
		color: var(--theme-text);
		transition:
			background 0.5s ease,
			color 0.3s ease;
	}
</style>
