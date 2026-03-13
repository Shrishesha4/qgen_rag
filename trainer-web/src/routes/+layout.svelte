<script lang="ts">
	import './layout.css';
	import { onMount } from 'svelte';
	import { initTheme } from '$lib/theme';

	let { children } = $props();

	onMount(() => {
		initTheme();
		const root = document.documentElement;
		const forceRepaint = () => {
			root.classList.add('bf-repaint');
			requestAnimationFrame(() => {
				requestAnimationFrame(() => {
					root.classList.remove('bf-repaint');
				});
			});
		};
		forceRepaint();
		const onVisibility = () => {
			if (!document.hidden) forceRepaint();
		};
		document.addEventListener('visibilitychange', onVisibility);
		return () => document.removeEventListener('visibilitychange', onVisibility);
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
		z-index: 2;
	}
</style>
