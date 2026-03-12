<script lang="ts">
	import './layout.css';
	import { onMount } from 'svelte';
	import { initTheme } from '$lib/theme';

	let { children } = $props();

	onMount(() => {
		initTheme();
	});
</script>

<div class="bg-image-layer" aria-hidden="true"></div>
<div class="bg-overlay-layer" aria-hidden="true"></div>

<div class="app-shell">
	{@render children()}
</div>

<style>
	.app-shell {
		min-height: 100vh;
		color: var(--theme-text);
		position: relative;
		z-index: 0;
	}
</style>
