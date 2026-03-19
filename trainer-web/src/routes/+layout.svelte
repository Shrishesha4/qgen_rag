<script lang="ts">
	import './layout.css';
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { initTheme } from '$lib/theme';
	import { warmVettingTaxonomy } from '$lib/api/vetting';
	import { initAiOps } from '$lib/api/ops';

	let { children } = $props();

	// Cache-busting for CSS - force reload on every page load
	onMount(() => {
		if (typeof window !== 'undefined') {
			// Force CSS reload by updating link tags
			const links = document.querySelectorAll('link[rel="stylesheet"]');
			links.forEach(link => {
				const href = link.getAttribute('href');
				if (href && href.includes('layout.css')) {
					const timestamp = Date.now();
					const newHref = href.split('?')[0] + '?t=' + timestamp;
					link.setAttribute('href', newHref);
				}
			});
		}
	});

	let pathname = $derived($page.url.pathname);
	const hideGlobalBackPrefixes = ['/teacher/train/loop'];
	let showGlobalBack = $derived.by(() => {
		if (
			pathname === '/' ||
			pathname.includes('/login') ||
			pathname.includes('/dashboard') ||
			pathname.includes('/ops') ||
			pathname.includes('/profile') 
		) {
			return false;
		}
		if (pathname.startsWith('/teacher/train/new')) {
			return true;
		}
		return !hideGlobalBackPrefixes.some((prefix) => pathname.startsWith(prefix));
	});

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
		if (import.meta.env.PROD && 'serviceWorker' in navigator && window.location.pathname === '/') {
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
	<meta name="theme-color" content="transparent" />
	<meta name="application-name" content="VQuest Trainer" />
	<meta name="apple-mobile-web-app-capable" content="yes" />
	<meta name="apple-mobile-web-app-title" content="VQuest Trainer" />
	<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent" />
	<link rel="apple-touch-icon" sizes="180x180" href="/icons/icon-180.png" />
</svelte:head>

<div class="bg-image-layer" aria-hidden="true"></div>
<div class="bg-overlay-layer" aria-hidden="true"></div>

{#if showGlobalBack}
	<button class="global-back-btn" aria-label="Go back" onclick={goBack}>
		<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
			<path d="M19 12H5M5 12L12 19M5 12L12 5"/>
		</svg>
	</button>
{/if}

<div class="app-shell">
	{@render children()}
</div>

<style>
	.global-back-btn {
		position: fixed;
		top: calc(env(safe-area-inset-top) + 0.75rem);
		left: calc(env(safe-area-inset-left) + 0.75rem);
		z-index: 70;
		width: 48px;
		height: 48px;
		padding: 0;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		line-height: 1;
		aspect-ratio: 1 / 1;
		border-radius: 50%;
		border: 1px solid rgba(255, 255, 255, 0.2);
		background: rgba(10, 18, 34, 0.8);
		backdrop-filter: blur(12px);
		-webkit-backdrop-filter: blur(12px);
		color: var(--theme-text);
		font-size: 1.1rem;
		font-weight: 600;
		cursor: pointer;
		box-shadow: 
			0 4px 20px rgba(0, 0, 0, 0.3),
			0 0 0 1px rgba(255, 255, 255, 0.1),
			inset 0 1px 1px rgba(255, 255, 255, 0.2);
		transition: all 0.2s cubic-bezier(0.23, 1, 0.32, 1);
		/* Android optimization */
		touch-action: manipulation;
		-webkit-tap-highlight-color: transparent;
	}

	.global-back-btn:hover {
		transform: translateY(-2px) scale(1.05);
		background: rgba(var(--theme-primary-rgb), 0.25);
		border-color: rgba(var(--theme-primary-rgb), 0.4);
		box-shadow: 
			0 8px 30px rgba(var(--theme-primary-rgb), 0.3),
			0 0 0 1px rgba(var(--theme-primary-rgb), 0.2),
			inset 0 1px 1px rgba(255, 255, 255, 0.3);
	}

	.global-back-btn:active {
		transform: translateY(0) scale(0.95);
		transition: all 0.1s ease;
	}

	/* Mobile optimizations */
	@media (max-width: 768px) {
		.global-back-btn {
			width: 44px;
			height: 44px;
			backdrop-filter: none;
			-webkit-backdrop-filter: none;
			background: rgba(10, 18, 34, 0.9);
			box-shadow: 
				0 4px 16px rgba(0, 0, 0, 0.4),
				0 0 0 1px rgba(255, 255, 255, 0.15);
		}

		.global-back-btn:hover {
			transform: translateY(-1px) scale(1.02);
		}

		.global-back-btn svg {
			width: 18px;
			height: 18px;
		}
	}

	/* Touch device optimizations */
	@media (hover: none) and (pointer: coarse) {
		.global-back-btn {
			transition: all 0.1s ease;
		}

		.global-back-btn:hover {
			transform: none;
		}

		.global-back-btn:active {
			transform: scale(0.95);
		}
	}

	.app-shell {
		min-height: 100dvh;
		color: var(--theme-text);
		position: relative;
		z-index: 2;
		padding-top: calc(env(safe-area-inset-top) + 0.25rem);
		padding-right: env(safe-area-inset-right);
		padding-bottom: env(safe-area-inset-bottom);
		padding-left: env(safe-area-inset-left);
	}

	@media (max-width: 640px) {
		.global-back-btn {
			top: calc(env(safe-area-inset-top) + 0.5rem);
			left: calc(env(safe-area-inset-left) + 0.5rem);
			width: 40px;
			height: 40px;
			border-radius: 50%;
		}
	}
</style>
