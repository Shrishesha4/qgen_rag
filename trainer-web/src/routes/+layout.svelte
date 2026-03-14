<script lang="ts">
	import './layout.css';
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { initTheme } from '$lib/theme';
	import { warmVettingTaxonomy } from '$lib/api/vetting';
	import { initAiOps } from '$lib/api/ops';

	let { children } = $props();

	let pathname = $derived($page.url.pathname);
	let showGlobalBack = $derived(
		pathname !== '/' &&
		!pathname.includes('/login') &&
		!pathname.includes('/dashboard') &&
		!pathname.includes('/ops')
	);

	function goBack() {
		if (typeof window !== 'undefined' && window.history.length > 1) {
			window.history.back();
			return;
		}
		goto('/');
	}

	onMount(() => {
		initTheme();
		warmVettingTaxonomy().catch(() => {
			// Non-blocking; adapter will retry on demand.
		});
		initAiOps();
		if (import.meta.env.PROD && 'serviceWorker' in navigator) {
			navigator.serviceWorker.register('/service-worker.js', { type: 'module' });
		}
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

<svelte:head>
	<link rel="manifest" href="/manifest.webmanifest" />
	<meta name="theme-color" content="#1f4268" />
	<meta name="application-name" content="QGen Trainer" />
	<meta name="apple-mobile-web-app-capable" content="yes" />
	<meta name="apple-mobile-web-app-title" content="QGen Trainer" />
	<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent" />
	<link rel="apple-touch-icon" sizes="180x180" href="/icons/icon-180.png" />
</svelte:head>

<div class="bg-image-layer" aria-hidden="true"></div>
<div class="bg-overlay-layer" aria-hidden="true"></div>

{#if showGlobalBack}
	<button class="global-back-btn" aria-label="Go back" onclick={goBack}>←</button>
{/if}

<div class="app-shell">
	{@render children()}
</div>

<style>
	.global-back-btn {
		position: fixed;
		top: 1rem;
		left: 1rem;
		z-index: 70;
		width: 42px;
		height: 42px;
		padding: 0;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		line-height: 1;
		aspect-ratio: 1 / 1;
		border-radius: 50%;
		border: 1px solid rgba(255, 255, 255, 0.24);
		background: rgba(10, 18, 34, 0.56);
		backdrop-filter: blur(8px);
		-webkit-backdrop-filter: blur(8px);
		color: var(--theme-text);
		font-size: 1.05rem;
		font-weight: 700;
		cursor: pointer;
		box-shadow: 0 8px 18px rgba(0, 0, 0, 0.28);
		transition: transform 0.16s ease, background 0.16s ease, border-color 0.16s ease;
	}

	.global-back-btn:hover {
		transform: translateY(-1px);
		background: rgba(var(--theme-primary-rgb), 0.22);
		border-color: rgba(var(--theme-primary-rgb), 0.52);
	}

	.global-back-btn:active {
		transform: translateY(0);
	}

	.app-shell {
		min-height: 100vh;
		color: var(--theme-text);
		position: relative;
		z-index: 2;
	}

	@media (max-width: 640px) {
		.global-back-btn {
			top: 0.75rem;
			left: 0.75rem;
			width: 40px;
			height: 40px;
			border-radius: 50%;
		}
	}
</style>
