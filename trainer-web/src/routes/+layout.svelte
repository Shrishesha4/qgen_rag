<script lang="ts">
	import './layout.css';
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { initTheme, zenMode, toggleZenMode } from '$lib/theme';
	import ThemePicker from '$lib/components/ThemePicker.svelte';
	import MobileNavBar from '$lib/components/MobileNavBar.svelte';
	import { warmVettingTaxonomy } from '$lib/api/vetting';
	import { initAiOps } from '$lib/api/ops';
	import { session, currentUser } from '$lib/session';

	let { children } = $props();

	// Desktop sidebar — hidden by default
	let sidebarVisible = $state(true);
	let isCollapsing = $state(false);
	let isExpanding = $state(false);

	// Derived: sidebar is fully collapsed (not visible, not animating)
	let sidebarCollapsed = $derived(!sidebarVisible && !isExpanding);

	// Hover preview — floating panel shown on logo hover when collapsed
	let sidebarHoverOpen = $state(false);
	let _hoverCloseTimer: ReturnType<typeof setTimeout> | null = null;

	function onSidebarHoverEnter() {
		if (_hoverCloseTimer) { clearTimeout(_hoverCloseTimer); _hoverCloseTimer = null; }
		sidebarHoverOpen = true;
	}

	function onSidebarHoverLeave() {
		_hoverCloseTimer = setTimeout(() => { sidebarHoverOpen = false; }, 200);
	}

	// Logo click when collapsed → toggle hover menu (not expand)
	function handleLogoClick() {
		sidebarHoverOpen = !sidebarHoverOpen;
	}

	// Logo click when expanded → collapse
	function handleCollapseClick() {
		if (isCollapsing || isExpanding) return;
		isCollapsing = true;
		sidebarHoverOpen = false;
	}

	function handleCollapseAnimationEnd() {
		if (isCollapsing) {
			isCollapsing = false;
			sidebarVisible = false;
		}
	}

	function handleExpandAnimationEnd() {
		if (isExpanding) {
			isExpanding = false;
		}
	}

	// Pin button in hover panel → expand full sidebar
	function handlePinClick() {
		if (isCollapsing || isExpanding) return;
		sidebarHoverOpen = false;
		sidebarVisible = true;
		requestAnimationFrame(() => {
			isExpanding = true;
		});
	}

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
		return pathname.startsWith('/teacher') || pathname.startsWith('/vetter') || pathname.startsWith('/admin');
	});
	let navItems = $derived.by(() => {
		if (pathname.startsWith('/teacher')) {
			return [
				{ href: '/teacher/subjects', label: 'Subjects', icon: '🧾' },
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
				// { href: '/vetter/subjects', label: 'Subjects', icon: '📚' },
				{ href: '/vetter/profile', label: 'Profile', icon: '👤' },
				// { href: '/vetter/loop', label: 'Vetting Loop', icon: '🎙️' }
			];
		}
		if (pathname.startsWith('/admin')) {
			return [
				{ href: '/admin/dashboard', label: 'Dashboard', icon: '📊' },
				{ href: '/admin/notifications', label: 'Notifications', icon: '🔔' },
				{ href: '/admin/users', label: 'User Management', icon: '👥' },
				{ href: '/admin/subjects', label: 'Subjects', icon: '🧾' },
				{ href: '/admin/teachers', label: 'Teachers', icon: '🧑‍🏫' },
				{ href: '/admin/vetters', label: 'Vetters', icon: '✅' },
				{ href: '/admin/analytics', label: 'Analytics', icon: '📊' },
				{ href: '/admin/logs', label: 'Logs', icon: '🧾' },
				{ href: '/admin/settings', label: 'Settings', icon: '⚙️' },
				{ href: '/admin/profile', label: 'Profile', icon: '👤' },
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

	let enableVettingLoopScroll = $derived(
		pathname.startsWith('/teacher/train/loop') ||
		pathname.startsWith('/vetter/dashboard/loop') ||
		pathname.startsWith('/vetter/loop')
	);
	let enableAdminWindowScroll = $derived(pathname.startsWith('/admin') && !pathname.includes('/login'));

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

<div class="app-shell" class:with-desktop-chrome={showDesktopChrome} class:sidebar-collapsed={sidebarCollapsed} class:profile-window-scroll={pathname.endsWith('/profile')} class:vetting-loop-scroll={enableVettingLoopScroll} class:admin-window-scroll={enableAdminWindowScroll} class:admin-ui={pathname.startsWith('/admin')}>
	{#if showDesktopChrome}
		<!-- Floating logo button + hover preview panel (shown when sidebar is collapsed) -->
		{#if !sidebarVisible && !isExpanding}
			<img src="/logo.png" alt="VQuest logo" class="collapsed-logo-img" />
			<!-- <button
				class="collapsed-logo-btn"
				// onclick={handleLogoClick}
				// onmouseenter={onSidebarHoverEnter}
				// onmouseleave={onSidebarHoverLeave}
				aria-label="Open navigation"
			>
				<img src="/logo.png" alt="VQuest logo" class="collapsed-logo-img" />
			</button> -->

			{#if sidebarHoverOpen}
				<div
					class="sidebar-hover-panel glass-panel"
					// onmouseenter={onSidebarHoverEnter}
					// onmouseleave={onSidebarHoverLeave}
					role="complementary"
					aria-label="Navigation preview"
				>
					<div class="sidebar-brand">
						<div class="brand-icon">
							<img src="/logo.png" alt="VQuest logo" class="brand-logo-img" loading="eager" />
						</div>
						<div class="brand-text">
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
								onclick={() => { sidebarHoverOpen = false; }}
							>
								<span class="sidebar-link-icon">{item.icon}</span>
								<span>{item.label}</span>
							</a>
						{/each}
					</nav>
					<button class="hover-pin-btn" onclick={handlePinClick}>
						<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
							<line x1="12" y1="17" x2="12" y2="22"/>
							<path d="M5 17h14v-1.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V6h1a2 2 0 0 0 0-4H8a2 2 0 0 0 0 4h1v4.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24Z"/>
						</svg>
						Pin sidebar
					</button>
					<div class="sidebar-footer hover-footer">
						<div class="theme-row">
							<span class="theme-label">Theme</span>
							<ThemePicker />
						</div>
					</div>
				</div>
			{/if}
		{/if}

		{#if sidebarVisible || isCollapsing}
			<aside 
				class="desktop-sidebar glass-panel" 
				class:collapsing={isCollapsing}
				class:expanding={isExpanding}
				onanimationend={isCollapsing ? handleCollapseAnimationEnd : handleExpandAnimationEnd}
			>
				<div class="sidebar-brand">
					<img src="/logo.png" alt="VQuest logo" class="brand-logo-img" loading="eager" decoding="async" />
					<!-- <button class="brand-icon" onclick={handleCollapseClick} aria-label="Collapse sidebar" title="Collapse sidebar">
						<img src="/logo.png" alt="VQuest logo" class="brand-logo-img" loading="eager" decoding="async" />
					</button> -->
					<div class="brand-text">
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
		{/if}

		<section class="desktop-window-wrap" class:expanded={sidebarCollapsed}>
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
			--shell-hpad: clamp(0.9rem, 1.8vw, 1.5rem);
			display: grid;
			/* Start in collapsed state (0px sidebar) so first render matches sidebarVisible=false */
			grid-template-columns: 0px minmax(0, 1fr);
			gap: 0;
			padding: calc(env(safe-area-inset-top) + var(--desktop-shell-vpad-top)) var(--shell-hpad) calc(env(safe-area-inset-bottom) + var(--desktop-shell-vpad-bottom));
			height: 100dvh;
			max-width: 100%;
			margin: 0 auto;
			/* Animate layout changes without any transform (preserves backdrop-filter) */
			transition:
				grid-template-columns 0.45s cubic-bezier(0.16, 1, 0.3, 1),
				gap 0.45s cubic-bezier(0.16, 1, 0.3, 1);
		}

		/* Expanded state */
		.app-shell.with-desktop-chrome:not(.sidebar-collapsed) {
			grid-template-columns: clamp(250px, 24vw, 300px) minmax(0, 1fr);
			gap: clamp(1rem, 2.5vw, 2.5rem);
			max-width: 1500px;
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
			cursor: pointer;
			transition: all 0.25s cubic-bezier(0.34, 1.56, 0.64, 1);
			padding: 0;
			font-size: inherit;
			font-family: inherit;
		}

		.brand-icon:hover {
			transform: scale(1.08);
			box-shadow: 0 4px 16px rgba(var(--theme-primary-rgb), 0.25);
			border-color: rgba(var(--theme-primary-rgb), 0.5);
		}

		.brand-icon:active {
			transform: scale(0.95);
		}

		.brand-logo-img {
			width: 52px;
			height: 52px;
			object-fit: contain;
		}

		.brand-text {
			transition: opacity 0.2s ease, transform 0.2s ease;
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

		/* ===== SIDEBAR COLLAPSE/EXPAND ANIMATIONS ===== */

		/* Collapsing sidebar - swoops into the top-left corner logo */
		.desktop-sidebar.collapsing {
			animation: sidebarSwoopOut 0.45s cubic-bezier(0.4, 0, 0.2, 1) forwards;
			pointer-events: none;
			transform-origin: top left;
		}

		@keyframes sidebarSwoopOut {
			0% {
				opacity: 1;
				transform: scale(1) translate(0, 0);
				border-radius: 1.25rem;
			}
			30% {
				opacity: 0.9;
				transform: scale(0.7, 0.7) translate(-5%, -5%);
				border-radius: 1rem;
			}
			60% {
				opacity: 0.5;
				transform: scale(0.35, 0.35) translate(-30%, -30%);
				border-radius: 0.75rem;
			}
			100% {
				opacity: 0;
				transform: scale(0.12, 0.12) translate(-85%, -85%);
				border-radius: 50%;
			}
		}

		/* Elements inside sidebar fade out during collapse */
		.desktop-sidebar.collapsing .sidebar-nav,
		.desktop-sidebar.collapsing .sidebar-footer,
		.desktop-sidebar.collapsing .brand-text {
			animation: fadeOutQuick 0.15s ease forwards;
		}

		@keyframes fadeOutQuick {
			to {
				opacity: 0;
				transform: scale(0.9) translateX(-10px);
			}
		}

		/* Expanding sidebar - smooth entrance from top-left (no bounce) */
		.desktop-sidebar.expanding {
			animation: sidebarSwoopIn 0.5s cubic-bezier(0.16, 1, 0.3, 1) forwards;
			transform-origin: top left;
		}

		@keyframes sidebarSwoopIn {
			0% {
				opacity: 0;
				transform: scale(0.12, 0.12) translate(-85%, -85%);
				border-radius: 50%;
			}
			45% {
				opacity: 0.85;
				transform: scale(0.55, 0.55) translate(-25%, -25%);
				border-radius: 0.8rem;
			}
			100% {
				opacity: 1;
				transform: scale(1) translate(0, 0);
				border-radius: 1.25rem;
			}
		}

		/* Elements inside sidebar fade in during expand */
		.desktop-sidebar.expanding .sidebar-nav,
		.desktop-sidebar.expanding .sidebar-footer,
		.desktop-sidebar.expanding .brand-text {
			animation: fadeInQuick 0.35s ease 0.15s forwards;
			opacity: 0;
		}

		@keyframes fadeInQuick {
			from {
				opacity: 0;
				transform: translateX(-10px);
			}
			to {
				opacity: 1;
				transform: translateX(0);
			}
		}

		/* Floating collapsed logo button */
		/* Logo sits in the top-left corner of the glass content panel.
		   Panel top = safe-area + 4rem, panel left = --shell-hpad.
		   Inset 0.7rem inside the panel to clear the border-radius. */
		/* .collapsed-logo-btn {
			position: fixed;
			top: calc(env(safe-area-inset-top) + 4rem + 0.7rem);
			left: calc(clamp(0.9rem, 1.8vw, 1.5rem) + 0.7rem);
			z-index: 100;
			width: 56px;
			height: 56px;
			border-radius: 14px;
			background: rgba(255, 255, 255, 0.18);
			border: 1px solid rgba(255, 255, 255, 0.28);
			box-shadow:
				0 2px 12px rgba(0, 0, 0, 0.1),
				inset 0 1px 0 rgba(255, 255, 255, 0.35);
			backdrop-filter: blur(8px);
			-webkit-backdrop-filter: blur(8px);
			display: grid;
			place-items: center;
			cursor: pointer;
			padding: 0;
			animation: logoAppear 0.35s cubic-bezier(0.16, 1, 0.3, 1) forwards;
			transition: background 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
		} */

		@keyframes logoAppear {
			from { opacity: 0; transform: scale(0.7); }
			to   { opacity: 1; transform: scale(1); }
		}

		/* .collapsed-logo-btn:hover {
			background: rgba(255, 255, 255, 0.32);
			border-color: rgba(255, 255, 255, 0.5);
			box-shadow:
				0 4px 20px rgba(var(--theme-primary-rgb), 0.18),
				inset 0 1px 0 rgba(255, 255, 255, 0.5);
			transform: scale(1.06);
		}

		.collapsed-logo-btn:active {
			transform: scale(0.94);
		} */

		.collapsed-logo-img {
			width: 34px;
			height: 34px;
			object-fit: contain;
		}

		/* :global([data-color-mode='dark']) .collapsed-logo-btn {
			background: rgba(15, 23, 42, 0.4);
			border-color: rgba(255, 255, 255, 0.12);
			box-shadow:
				0 2px 12px rgba(0, 0, 0, 0.3),
				inset 0 1px 0 rgba(255, 255, 255, 0.06);
		}

		:global([data-color-mode='dark']) .collapsed-logo-btn:hover {
			background: rgba(var(--theme-primary-rgb), 0.18);
			border-color: rgba(var(--theme-primary-rgb), 0.35);
		} */

		/* Grid transition moved to app-shell.with-desktop-chrome above */

		/* Collapsed state — window spans full grid */
		.app-shell.with-desktop-chrome.sidebar-collapsed {
			grid-template-columns: 0px minmax(0, 1fr);
			gap: 0;
			max-width: 100%;
		}

		.app-shell.with-desktop-chrome.sidebar-collapsed .desktop-window-wrap {
			grid-column: 1 / -1;
		}

		/* Inner page containers: lift max-width cap when sidebar is gone */
		:global(.app-shell.sidebar-collapsed .page) {
			max-width: 100% !important;
		}

		/* Nudge page headings right to clear the 56px logo (at 0.7rem inset + 56px = ~4.2rem from panel edge, page padding = 1.5rem) */
		:global(.app-shell.sidebar-collapsed .hero-intro) {
			padding-left: 3rem;
		}

		/* ===== HOVER SIDEBAR PANEL ===== */
		/* Opens below the logo button: logo top = safe-area + 4rem + 0.7rem, logo height = 56px */
		.sidebar-hover-panel {
			position: fixed;
			top: calc(env(safe-area-inset-top) + 4rem + 0.7rem + 56px + 0.5rem);
			left: clamp(0.9rem, 1.8vw, 1.5rem);
			width: clamp(250px, 24vw, 300px);
			max-height: calc(100dvh - env(safe-area-inset-top) - env(safe-area-inset-bottom) - 5.5rem);
			z-index: 200;
			display: flex;
			flex-direction: column;
			padding: 1rem;
			border-radius: 1.25rem;
			/* overflow must be visible so the ThemePicker dropdown can escape the panel.
			   glass-panel sets overflow:hidden globally; we override via the rule below. */
			overflow: visible;
			/* Slide-in only — no opacity trick so backdrop-filter is undisturbed after entry */
			animation: hoverPanelIn 0.22s cubic-bezier(0.16, 1, 0.3, 1) forwards;
			box-shadow:
				0 24px 64px rgba(0, 0, 0, 0.22),
				0 8px 24px rgba(0, 0, 0, 0.12),
				inset 0 1px 0 rgba(255, 255, 255, 0.4);
		}

		/* Clip only the nav scroll area, not the footer where the dropdown lives */
		.sidebar-hover-panel .sidebar-nav {
			overflow-y: auto;
			overflow-x: hidden;
		}

		/* Beat the global glass-panel overflow:hidden so the ThemePicker dropdown escapes */
		:global(.sidebar-hover-panel.glass-panel) {
			overflow: visible !important;
		}

		/* Force the ThemePicker dropdown to open RIGHTWARD inside the hover panel */
		:global(.sidebar-hover-panel .picker-menu) {
			bottom: auto !important;
			top: 0 !important;
			right: auto !important;
			left: calc(100% + 0.75rem) !important;
			transform-origin: top left !important;
		}

		.hover-footer {
			margin-top: 0.5rem;
		}

		@keyframes hoverPanelIn {
			from {
				opacity: 0;
				transform: translateX(-18px);
			}
			to {
				opacity: 1;
				transform: translateX(0);
			}
		}

		.hover-pin-btn {
			display: flex;
			align-items: center;
			gap: 0.5rem;
			width: 100%;
			padding: 0.52rem 0.75rem;
			margin-top: 0.6rem;
			border-radius: 10px;
			border: 1px solid rgba(var(--theme-primary-rgb), 0.28);
			background: rgba(var(--theme-primary-rgb), 0.07);
			color: rgb(var(--theme-primary-rgb));
			font-size: 0.78rem;
			font-weight: 600;
			cursor: pointer;
			transition: all 0.18s ease;
			letter-spacing: 0.02em;
		}

		.hover-pin-btn:hover {
			background: rgba(var(--theme-primary-rgb), 0.14);
			border-color: rgba(var(--theme-primary-rgb), 0.5);
		}

		:global([data-color-mode='dark']) .hover-pin-btn {
			color: rgba(var(--theme-primary-rgb), 0.9);
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
