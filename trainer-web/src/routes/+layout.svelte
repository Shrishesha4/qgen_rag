<script lang="ts">
	import './layout.css';
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { initTheme } from '$lib/theme';
	import ThemePicker from '$lib/components/ThemePicker.svelte';
	import MobileNavBar from '$lib/components/MobileNavBar.svelte';
	import { warmVettingTaxonomy } from '$lib/api/vetting';
	import { initAiOps } from '$lib/api/ops';
	import { session, currentUser } from '$lib/session';

	let { children } = $props();

	// Prevent CSS preload timeout by patching preload links
	onMount(() => {
		if (typeof window !== 'undefined') {
			// Convert failing CSS preload links to regular load (avoid timeout errors)
			const prelinks = document.querySelectorAll('link[rel="preload"][as="style"]');
			prelinks.forEach(link => {
				const href = link.getAttribute('href');
				if (href && href.includes('immutable')) {
					// Remove preload and attach onload to avoid timeout errors
					link.removeAttribute('rel');
					link.setAttribute('rel', 'stylesheet');
				}
			});
			
			// Global handler to suppress unhandled CSS preload errors
			const origError = window.onerror;
			window.onerror = function(msg, url, line, col, error) {
				if (msg && typeof msg === 'string' && msg.includes('Unable to preload CSS')) {
					return true; // Suppress error
				}
				if (origError) return origError(msg, url, line, col, error);
			};
			
			// Also catch unhandled promise rejections from preload
			const origHandler = window.onunhandledrejection;
			window.onunhandledrejection = (evt: PromiseRejectionEvent) => {
				if (evt.reason && evt.reason.message && evt.reason.message.includes('Unable to preload CSS')) {
					evt.preventDefault();
				} else if (origHandler) {
					origHandler.call(window, evt);
				}
			};
		}
	});

	let pathname = $derived($page.url.pathname);
	const currentYear = $derived.by(() => new Date().getFullYear());
	const hideGlobalBackPrefixes = ['/teacher/train/loop', '/privacy-policy', '/disclaimer'];
	let showDesktopChrome = $derived.by(() => {
		if (pathname.includes('/login')) return false;
		return (
			pathname.startsWith('/teacher') ||
			pathname.startsWith('/vetter') ||
			pathname.startsWith('/admin') ||
			pathname.startsWith('/student') ||
			pathname.startsWith('/courses')
		);
	});
	let navItems = $derived.by(() => {
		if (pathname.startsWith('/teacher')) {
			return [
				{ href: '/teacher/subjects', label: 'Subjects', icon: '🧾' },
				{ href: '/teacher/courses', label: 'Courses', icon: '📦' },
				{ href: '/teacher/stats', label: 'Stats', icon: '📈' },
				// { href: '/teacher/train', label: 'Train Topic', icon: '📚' },
				{ href: '/teacher/train', label: 'Vetting', icon: '🪟' },
				// { href: '/teacher/verify', label: 'Verify', icon: '🎙️' },
				{ href: '/teacher/profile', label: 'Profile', icon: '👤' }
			];
		}
		if (pathname.startsWith('/vetter')) {
			return [
				{ href: '/vetter/dashboard', label: 'Home', icon: '🏠' },
				{ href: '/vetter/subjects', label: 'Subjects', icon: '📚' },
				{ href: '/vetter/profile', label: 'Profile', icon: '👤' },
				// { href: '/vetter/loop', label: 'Vetting Loop', icon: '🎙️' }
			];
		}
		if (pathname.startsWith('/admin')) {
			return [
				{ href: '/admin/dashboard', label: 'Dashboard', icon: '📊' },
				{ href: '/admin/courses', label: 'Courses', icon: '📦' },
				{ href: '/admin/users', label: 'User Management', icon: '👥' },
				{ href: '/admin/subjects', label: 'Subjects', icon: '🧾' },
				{ href: '/admin/teachers', label: 'Teachers', icon: '🧑‍🏫' },
				{ href: '/admin/vetters', label: 'Vetters', icon: '✅' },
				{ href: '/admin/settings', label: 'Settings', icon: '⚙️' },
				{ href: '/admin/profile', label: 'Profile', icon: '👤' },
			];
		}
		if (pathname.startsWith('/student')) {
			return [
				{ href: '/student', label: 'Dashboard', icon: '🏠' },
				{ href: '/student/train', label: 'GEL Train', icon: '🧠' },
				{ href: '/student/courses', label: 'Courses', icon: '📦' },
				{ href: '/student/assignments', label: 'Assignments', icon: '🧾' },
				{ href: '/student/history', label: 'History', icon: '🕒' },
				{ href: '/student/progress', label: 'Progress', icon: '📈' },
				// { href: '/student/settings', label: 'Settings', icon: '⚙️' },
				{ href: '/student/profile', label: 'Profile', icon: '👤' },
			];
		}
		return [];
	});

	let activeNavHref = $derived.by(() => {
		const matches = navItems.filter((item) => pathname === item.href || pathname.startsWith(`${item.href}/`));
		if (matches.length === 0) return '';
		return matches.reduce((best, current) => (current.href.length > best.href.length ? current : best)).href;
	});
	
	let showGlobalBack = $derived.by(() => {
		if (showDesktopChrome) return false;
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

	let enableVettingLoopScroll = $derived(pathname.startsWith('/teacher/train/loop'));
	let enableAdminWindowScroll = $derived(pathname.startsWith('/admin') && !pathname.includes('/login'));
	let enableTeacherGelWindowScroll = $derived(
		pathname === '/teacher/gel' || pathname.startsWith('/teacher/gel/')
	);
	let enableStudentTrainWindowScroll = $derived(
		pathname === '/student/train' || pathname.startsWith('/student/train/')
	);
	let enableStandardWindowScroll = $derived(
		pathname.startsWith('/student/courses') ||
		pathname.startsWith('/teacher/courses') ||
		pathname.startsWith('/student/settings') ||
		pathname.startsWith('/courses')
	);

	// Role-based routing: redirect to dashboard on root path
	$effect(() => {
		if (pathname === '/' && $currentUser) {
			const role = $currentUser.role;
			if (role === 'teacher') {
				goto('/teacher/subjects');
			} else if (role === 'vetter') {
				goto('/vetter/dashboard');
			} else if (role === 'admin') {
				goto('/admin/dashboard');
			} else if (role === 'student') {
				goto('/student');
			}
		}
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
		
		// Only initialize authenticated API calls when user is logged in
		let unsubscribe: (() => void) | null = null;
		const stop = session.subscribe(($session) => {
			if ($session) {
				// User is authenticated, initialize API calls
				warmVettingTaxonomy().catch(() => {
					// Non-blocking; adapter will retry on demand.
				});
				initAiOps();
				// Unsubscribe after initialization to avoid repeated calls
				unsubscribe?.();
			}
		});
		unsubscribe = stop;
		
		// Suppress CSS preload timeout errors globally
		window.addEventListener('error', (evt) => {
			if (evt.message && evt.message.includes('Unable to preload CSS')) {
				evt.preventDefault();
			}
		}, true); // capture phase to intercept before other handlers

		// Aggressively clear stale SW/cache state to avoid immutable CSS preload failures.
		if ('serviceWorker' in navigator) {
			navigator.serviceWorker.getRegistrations().then((regs) => {
				regs.forEach((reg) => reg.unregister().catch(() => {}));
			});
		}
		if ('caches' in window) {
			caches.keys().then((keys) => keys.forEach((k) => caches.delete(k))).catch(() => {});
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
		return () => {
			document.removeEventListener('visibilitychange', onVisibility);
			unsubscribe?.();
		};
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
<div class="bg-mobile-frost-layer" aria-hidden="true"></div>

{#if showDesktopChrome}
	<MobileNavBar {navItems} />
{/if}

{#if showGlobalBack}
	<button class="global-back-btn" aria-label="Go back" onclick={goBack}>
		<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
			<path d="M19 12H5M5 12L12 19M5 12L12 5"/>
		</svg>
	</button>
{/if}

<div class="app-shell" class:with-desktop-chrome={showDesktopChrome} class:profile-window-scroll={pathname.endsWith('/profile')} class:vetting-loop-scroll={enableVettingLoopScroll} class:admin-window-scroll={enableAdminWindowScroll} class:teacher-gel-window-scroll={enableTeacherGelWindowScroll} class:train-window-scroll={enableStudentTrainWindowScroll} class:standard-window-scroll={enableStandardWindowScroll} class:admin-ui={pathname.startsWith('/admin')}>
	{#if showDesktopChrome}
		<aside class="desktop-sidebar glass-panel">
			<div class="sidebar-brand">
				<div class="brand-icon">
					<img src="/logo.png" alt="VQuest logo" class="brand-logo-img" loading="eager" decoding="async" />
				</div>
				<div>
					<p class="brand-title">VQuest</p>
					<p class="brand-subtitle">Console</p>
				</div>
			</div>
			<nav class="sidebar-nav">
				{#each navItems as item}
					<a
						href={item.href}
						class="sidebar-link"
						class:active={item.href === activeNavHref}
					>
						<span class="sidebar-link-icon">{item.icon}</span>
						<span>{item.label}</span>
					</a>
				{/each}
			</nav>
			<div class="sidebar-footer">
				<div class="theme-row">
					<span class="theme-label">Theme</span>
					<ThemePicker />
				</div>
				<div class="copyright-row">
					<p class="drawer-copyright-text">
						2023 © Vianasoft Pvt Ltd
					</p>
					<div class="legal-links">
						<a href="/disclaimer" class="privacy-link">Disclaimer</a>
						<a href="/privacy-policy" class="privacy-link">Privacy Policy</a>
					</div>
				</div>
			</div>
		</aside>

		<section class="desktop-window-wrap">
			<div class="desktop-window glass-panel">
				<div class="desktop-window-content">
					{@render children()}
				</div>
			</div>
		</section>
	{:else}
		{@render children()}
	{/if}
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
		z-index: 3;
		padding-top: calc(env(safe-area-inset-top) + 0.25rem);
		padding-right: env(safe-area-inset-right);
		padding-bottom: env(safe-area-inset-bottom);
		padding-left: env(safe-area-inset-left);
	}

	/* When mobile nav bar is present, push content below it */
	@media (max-width: 959px) {
		.app-shell.with-desktop-chrome {
			padding-top: calc(env(safe-area-inset-top) + 52px);
		}

		.global-back-btn {
			display: none;
		}

		/* Reset desktop wrappers on mobile so position:fixed works in children.
		   glass-panel's transform: translateZ(0) creates a containing block
		   that breaks fixed positioning for floating docks, etc. */
		.desktop-window-wrap,
		.desktop-window,
		.desktop-window-content {
			display: block !important;
			position: static !important;
			overflow: visible !important;
			transform: none !important;
			backdrop-filter: none !important;
			-webkit-backdrop-filter: none !important;
			background: transparent !important;
			border: none !important;
			box-shadow: none !important;
			border-radius: 0 !important;
			height: auto !important;
			min-height: 0 !important;
		}

		/* Also kill the glass-panel pseudo-elements on these wrappers */
		.desktop-window::before,
		.desktop-window::after {
			display: none !important;
		}
	}

	.desktop-sidebar {
		display: none;
	}

	@media (min-width: 960px) {
		.app-shell.with-desktop-chrome {
			--desktop-shell-vpad-top: 4rem;
			--desktop-shell-vpad-bottom: 1.5rem;
			--desktop-frame-height: calc(100dvh - env(safe-area-inset-top) - env(safe-area-inset-bottom) - var(--desktop-shell-vpad-top) - var(--desktop-shell-vpad-bottom));
			display: grid;
			grid-template-columns: clamp(250px, 24vw, 300px) minmax(0, 1fr);
			gap: clamp(1rem, 2.5vw, 2.5rem);
			padding: calc(env(safe-area-inset-top) + var(--desktop-shell-vpad-top)) clamp(0.9rem, 1.8vw, 1.5rem) calc(env(safe-area-inset-bottom) + var(--desktop-shell-vpad-bottom));
			height: 100dvh;
			max-width: 1500px;
			margin: 0 auto;
		}

		.desktop-sidebar {
			display: flex;
			flex-direction: column;
			padding: 1rem;
			border-radius: 1.25rem;
			overflow: hidden;
			height: var(--desktop-frame-height);
		}

		.sidebar-brand {
			display: flex;
			align-items: center;
			gap: 0.75rem;
			padding: 0.4rem 0.4rem 1rem;
			border-bottom: 1px solid rgba(255, 255, 255, 0.35);
		}

		.brand-icon {
			width: 42px;
			height: 42px;
			border-radius: 12px;
			display: grid;
			place-items: center;
			background: rgba(255, 255, 255, 0.62);
			border: 1px solid rgba(255, 255, 255, 0.74);
		}

		.brand-logo-img {
			width: 28px;
			height: 28px;
			object-fit: contain;
		}

		.brand-title {
			margin: 0;
			font-size: 1rem;
			font-weight: 700;
			color: var(--theme-text-primary);
		}

		.brand-subtitle {
			margin: 0.1rem 0 0;
			font-size: 0.75rem;
			color: var(--theme-text-secondary);
			text-transform: uppercase;
			letter-spacing: 0.06em;
		}

		.sidebar-nav {
			padding: 0.75rem 0;
			display: flex;
			flex-direction: column;
			gap: 0.35rem;
			flex: 1;
		}

		.sidebar-link {
			display: flex;
			align-items: center;
			gap: 0.65rem;
			padding: 0.7rem 0.8rem;
			border-radius: 15px;
			border: 1px solid rgba(203, 213, 225, 0.9);
			text-decoration: none;
			font-weight: 600;
			color: #475569;
			background: rgba(255, 255, 255, 0.96);
			transition: all 0.18s ease;
		}

		.sidebar-link:hover {
			background: rgba(255, 255, 255, 1);
			border-color: rgba(var(--theme-primary-rgb), 0.4);
			color: #334155;
			transform: translateY(-1px);
		}

		.sidebar-link.active {
			background: linear-gradient(135deg, rgba(var(--theme-primary-rgb), 0.88), rgba(var(--theme-primary-rgb), 0.64));
			border-color: rgba(var(--theme-primary-rgb), 0.9);
			color: #ffffff;
			box-shadow:
				0 8px 18px rgba(var(--theme-primary-rgb), 0.34),
				inset 0 1px 0 rgba(255, 255, 255, 0.2);
		}

		:global([data-color-mode='light']) .sidebar-link.active {
			background: linear-gradient(135deg, rgba(var(--theme-primary-rgb), 0.96), rgba(var(--theme-primary-rgb), 0.78));
			border-color: rgba(var(--theme-primary-rgb), 0.98);
			color: #ffffff;
			box-shadow:
				0 10px 22px rgba(var(--theme-primary-rgb), 0.42),
				inset 0 1px 0 rgba(255, 255, 255, 0.18);
		}

		:global([data-color-mode='light']) .sidebar-link.active .sidebar-link-icon {
			background: rgba(15, 23, 42, 0.24);
			border-color: rgba(255, 255, 255, 0.5);
			color: #ffffff;
		}

		.sidebar-link-icon {
			width: 1.9rem;
			height: 1.9rem;
			display: inline-flex;
			align-items: center;
			justify-content: center;
			font-size: 1.08rem;
			line-height: 1;
			background: rgba(255, 255, 255, 0.9);
			color: #334155;
			border: 1px solid rgba(203, 213, 225, 0.9);
			border-radius: 0.55rem;
			box-shadow: 0 3px 10px rgba(15, 23, 42, 0.16);
			filter: saturate(1.1) contrast(1.06);
			flex-shrink: 0;
		}

		.sidebar-link.active .sidebar-link-icon {
			background: rgba(15, 23, 42, 0.22);
			border-color: rgba(255, 255, 255, 0.45);
			color: #ffffff;
		}

		:global([data-color-mode='dark']) .sidebar-link.active {
			background: linear-gradient(135deg, rgba(var(--theme-primary-rgb), 0.42), rgba(var(--theme-primary-rgb), 0.22));
			border-color: rgba(var(--theme-primary-rgb), 0.75);
			color: #f8fafc;
			box-shadow:
				0 10px 22px rgba(0, 0, 0, 0.48),
				0 0 0 1px rgba(var(--theme-primary-rgb), 0.4),
				inset 0 1px 0 rgba(255, 255, 255, 0.1);
		}

		:global([data-color-mode='dark']) .sidebar-link {
			background: rgba(30, 41, 59, 0.85);
			border-color: rgba(71, 85, 105, 0.6);
			color: #e2e8f0;
		}

		:global([data-color-mode='dark']) .sidebar-link:hover {
			background: rgba(51, 65, 85, 0.95);
			border-color: rgba(var(--theme-primary-rgb), 0.6);
			color: #f1f5f9;
			transform: translateY(-1px);
		}

		:global([data-color-mode='dark']) .sidebar-link-icon {
			background: rgba(15, 23, 42, 0.75);
			border-color: rgba(71, 85, 105, 0.5);
			color: #cbd5e1;
		}

		:global([data-color-mode='dark']) .sidebar-link.active .sidebar-link-icon {
			background: rgba(var(--theme-primary-rgb), 0.35);
			border-color: rgba(var(--theme-primary-rgb), 0.6);
			color: #f8fafc;
		}

		.sidebar-footer {
			padding-top: 0.75rem;
			border-top: 1px solid rgba(255, 255, 255, 0.35);
		}

		.theme-row {
			display: flex;
			align-items: center;
			justify-content: space-between;
		}

		.theme-label {
			font-size: 0.76rem;
			font-weight: 700;
			letter-spacing: 0.08em;
			text-transform: uppercase;
			color: var(--theme-text-secondary);
		}

		.copyright-row {
			display: flex;
			flex-direction: column;
			gap: 0.5rem;
			padding-top: 0.5rem;
			border-top: 1px solid rgba(255, 255, 255, 0.2);
			margin-top: 0.5rem;
		}

		.drawer-copyright-text {
			margin: 0;
			font-size: 0.65rem;
			color: var(--theme-text-muted);
			line-height: 1.4;
		}

		.legal-links {
			display: flex;
			align-items: center;
			gap: 0.5rem;
			flex-wrap: wrap;
		}

		.privacy-link {
			font-size: 0.65rem;
			color: var(--textSecondary);
			text-decoration: none;
			transition: color 0.2s ease;
		}

		.privacy-link:hover {
			color: color-mix(in srgb, var(--theme-primary) 120%, white);
			text-decoration: underline;
		}

		.desktop-window-wrap {
			min-width: 0;
			display: flex;
			min-height: 0;
		}

		.desktop-window {
			display: flex;
			flex-direction: column;
			min-width: 0;
			width: 100%;
			height: var(--desktop-frame-height);
			border-radius: 1.25rem;
			overflow: hidden;
		}

		.desktop-window-content {
			flex: 1;
			min-height: 0;
			overflow: hidden;
		}

		.app-shell.profile-window-scroll .desktop-window-content {
			overflow: auto;
		}

		.app-shell.admin-window-scroll .desktop-window-content {
			overflow-y: auto;
			overflow-x: hidden;
			-webkit-overflow-scrolling: touch;
		}

		.app-shell.teacher-gel-window-scroll .desktop-window-content {
			overflow-y: auto;
			overflow-x: hidden;
			overscroll-behavior-y: contain;
			-webkit-overflow-scrolling: touch;
		}

		.app-shell.train-window-scroll .desktop-window-content {
			overflow-y: auto;
			overflow-x: hidden;
			-webkit-overflow-scrolling: touch;
		}

		.app-shell.standard-window-scroll .desktop-window-content {
			overflow-y: auto;
			overflow-x: hidden;
			-webkit-overflow-scrolling: touch;
		}

		.app-shell.vetting-loop-scroll {
			overflow: hidden;
		}

		.app-shell.vetting-loop-scroll .desktop-window-wrap {
			min-height: 0;
		}

		.app-shell.vetting-loop-scroll .desktop-window {
			overflow: hidden;
		}

		.app-shell.vetting-loop-scroll .desktop-window-content {
			height: 100%;
			overflow-y: auto;
			overflow-x: hidden;
			overscroll-behavior-y: contain;
			-webkit-overflow-scrolling: touch;
		}

		.global-back-btn {
			display: none;
		}
	}

	@media (min-width: 960px) and (max-width: 1180px) {
		.sidebar-link {
			padding: 0.62rem 0.72rem;
			font-size: 0.97rem;
		}

		.sidebar-link-icon {
			width: 1.75rem;
			height: 1.75rem;
			font-size: 1rem;
		}
	}

	@media (min-width: 960px) and (max-height: 760px) {
		.desktop-sidebar {
			padding: 0.8rem;
		}

		.sidebar-nav {
			gap: 0.28rem;
			overflow-y: auto;
			padding-right: 0.15rem;
		}

		.sidebar-link {
			padding: 0.58rem 0.65rem;
		}

		.sidebar-footer {
			padding-top: 0.55rem;
		}
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
