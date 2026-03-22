<script lang="ts">
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { logout } from '$lib/api/auth';
	import { session } from '$lib/session';
	import ThemePicker from './ThemePicker.svelte';

	interface NavItem {
		href: string;
		label: string;
		icon: string;
	}

	let { navItems = [] }: { navItems: NavItem[] } = $props();

	let drawerOpen = $state(false);
	let pathname = $derived($page.url.pathname);

	let pageTitle = $derived.by(() => {
		// Teacher routes
		if (pathname === '/teacher' || pathname === '/teacher/dashboard') return 'Home';
		if (pathname === '/teacher/subjects/new') return 'New Subject';
		if (pathname.startsWith('/teacher/subjects/')) return 'Subject';
		if (pathname === '/teacher/subjects') return 'Subjects';
		if (pathname === '/teacher/train/loop') return 'Vetting';
		if (pathname.startsWith('/teacher/train/existing')) return 'Train Topic';
		if (pathname.startsWith('/teacher/train/new')) return 'New Topic';
		if (pathname === '/teacher/train') return 'Training';
		if (pathname === '/teacher/verify') return 'Verify';
		if (pathname === '/teacher/profile') return 'Profile';
		if (pathname === '/teacher/ops') return 'Operations';
		if (pathname === '/teacher/ab-test') return 'A/B Test';
		// Vetter routes
		if (pathname === '/vetter' || pathname === '/vetter/dashboard') return 'Home';
		if (pathname.startsWith('/vetter/subjects/')) return 'Subject';
		if (pathname === '/vetter/subjects') return 'Subjects';
		if (pathname === '/vetter/loop') return 'Vetting';
		if (pathname === '/vetter/profile') return 'Profile';
		// Admin routes
		if (pathname === '/admin/dashboard') return 'Dashboard';
		if (pathname.startsWith('/admin/subjects/')) return 'Subject';
		if (pathname === '/admin/subjects') return 'Subjects';
		return 'VQuest';
	});

	const rootPages = new Set([
		'/teacher', '/teacher/dashboard', '/teacher/subjects', '/teacher/train',
		'/teacher/profile', '/teacher/ops', '/teacher/verify', '/teacher/ab-test',
		'/vetter', '/vetter/dashboard', '/vetter/subjects', '/vetter/profile',
		'/admin/dashboard', '/admin/subjects',
	]);

	let showBack = $derived(!rootPages.has(pathname));

	let activeNavHref = $derived.by(() => {
		const matches = navItems.filter(
			(item) => pathname === item.href || pathname.startsWith(`${item.href}/`)
		);
		if (matches.length === 0) return '';
		return matches.reduce((best, cur) =>
			cur.href.length > best.href.length ? cur : best
		).href;
	});

	function goBack() {
		if (typeof window !== 'undefined' && window.history.length > 1) {
			window.history.back();
			return;
		}
		goto('/');
	}

	function handleNavClick(href: string) {
		drawerOpen = false;
		goto(href);
	}

	function closeDrawer() {
		drawerOpen = false;
	}

	async function handleSignOut() {
		drawerOpen = false;
		await logout();
		session.clear();
		goto('/');
	}
</script>

<!-- ─── iOS 7-style top nav bar ─── -->
<header class="mnb">
	<div class="mnb-left">
		{#if showBack}
			<button class="mnb-back" onclick={goBack} aria-label="Go back">
				<svg width="10" height="17" viewBox="0 0 10 17" fill="none" aria-hidden="true">
					<path d="M9 1L1.5 8.5L9 16" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>
				</svg>
				<span>Back</span>
			</button>
		{:else}
			<button class="mnb-hamburger" onclick={() => (drawerOpen = true)} aria-label="Open menu">
				<span class="mnb-hamburger-line"></span>
				<span class="mnb-hamburger-line"></span>
				<span class="mnb-hamburger-line"></span>
			</button>
		{/if}
	</div>

	<h1 class="mnb-title">{pageTitle}</h1>

	<div class="mnb-right">
		<ThemePicker />
	</div>
</header>

<!-- ─── Drawer overlay + panel ─── -->
{#if drawerOpen}
	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div class="drawer-backdrop" onclick={closeDrawer}></div>
	<aside class="drawer-panel">
		<div class="drawer-header">
			<div class="drawer-brand">
				<span class="drawer-brand-icon">
					<img src="/logo.png" alt="VQuest logo" class="drawer-brand-logo" loading="eager" decoding="async" />
				</span>
				<div>
					<p class="drawer-brand-title">VQuest</p>
					<p class="drawer-brand-subtitle">Console</p>
				</div>
			</div>
			<button class="drawer-close" onclick={closeDrawer} aria-label="Close menu">
				<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
					<line x1="18" y1="6" x2="6" y2="18"></line>
					<line x1="6" y1="6" x2="18" y2="18"></line>
				</svg>
			</button>
		</div>

		<nav class="drawer-nav">
			{#each navItems as item}
				<button
					class="drawer-link"
					class:active={item.href === activeNavHref}
					onclick={() => handleNavClick(item.href)}
				>
					<span class="drawer-link-icon">{item.icon}</span>
					<span>{item.label}</span>
				</button>
			{/each}
		</nav>

		<div class="drawer-footer">
			<button class="drawer-signout" onclick={handleSignOut}>
				<span class="drawer-link-icon">↪</span>
				<span>Sign Out</span>
			</button>
		</div>
	</aside>
{/if}

<style>
	/* ─── Nav bar ─── */
	.mnb {
		position: fixed;
		top: 0;
		left: 0;
		right: 0;
		z-index: 80;
		display: flex;
		align-items: center;
		justify-content: space-between;
		height: calc(env(safe-area-inset-top, 0px) + 48px);
		padding-top: env(safe-area-inset-top, 0px);
		padding-left: max(0.65rem, env(safe-area-inset-left));
		padding-right: max(0.65rem, env(safe-area-inset-right));
		background: var(--theme-nav-glass);
		backdrop-filter: blur(20px) saturate(180%);
		-webkit-backdrop-filter: blur(20px) saturate(180%);
		border-bottom: 0.5px solid var(--theme-glass-border);
		box-shadow: 0 0.5px 0 rgba(0, 0, 0, 0.06);
	}

	.mnb-left {
		flex: 1 1 0;
		display: flex;
		align-items: center;
		min-width: 0;
	}

	.mnb-right {
		flex: 1 1 0;
		display: flex;
		align-items: center;
		justify-content: flex-end;
		min-width: 0;
	}

	.mnb-title {
		flex: 0 1 auto;
		margin: 0;
		font-size: 1.05rem;
		font-weight: 700;
		color: var(--theme-text-primary);
		text-align: center;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		max-width: 55%;
		letter-spacing: -0.01em;
	}

	/* ─── Back button ─── */
	.mnb-back {
		display: inline-flex;
		align-items: center;
		gap: 0.2rem;
		padding: 0.35rem 0.6rem 0.35rem 0.25rem;
		background: var(--theme-glass-bg);
		border: 1px solid var(--theme-glass-border);
		border-radius: 999px;
		color: var(--theme-primary);
		font-size: 0.92rem;
		font-weight: 600;
		cursor: pointer;
		transition: background 0.15s ease, transform 0.1s ease;
		-webkit-tap-highlight-color: transparent;
		box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
	}

	.mnb-back:active {
		background: var(--theme-surface-hover);
		transform: scale(0.96);
	}

	/* ─── Hamburger ─── */
	.mnb-hamburger {
		display: flex;
		flex-direction: column;
		justify-content: center;
		gap: 4.5px;
		width: 36px;
		height: 36px;
		padding: 8px 6px;
		background: none;
		border: none;
		cursor: pointer;
		-webkit-tap-highlight-color: transparent;
		border-radius: 8px;
		transition: background 0.12s;
	}

	.mnb-hamburger:active {
		background: var(--theme-surface-hover);
	}

	.mnb-hamburger-line {
		display: block;
		width: 100%;
		height: 2px;
		border-radius: 1px;
		background: var(--theme-text-primary);
	}

	/* ─── Drawer backdrop ─── */
	.drawer-backdrop {
		position: fixed;
		inset: 0;
		z-index: 90;
		background: rgba(0, 0, 0, 0.35);
		backdrop-filter: blur(2px);
		-webkit-backdrop-filter: blur(2px);
		animation: fadeInBackdrop 0.2s ease-out both;
	}

	@keyframes fadeInBackdrop {
		from { opacity: 0; }
		to { opacity: 1; }
	}

	/* ─── Drawer panel ─── */
	.drawer-panel {
		position: fixed;
		top: 0;
		left: 0;
		bottom: 0;
		z-index: 95;
		width: min(280px, 80vw);
		background: var(--theme-nav-glass);
		backdrop-filter: blur(30px) saturate(180%);
		-webkit-backdrop-filter: blur(30px) saturate(180%);
		border-right: 0.5px solid var(--theme-glass-border);
		box-shadow: 4px 0 24px rgba(0, 0, 0, 0.12);
		display: flex;
		flex-direction: column;
		padding-top: env(safe-area-inset-top, 0px);
		animation: slideInDrawer 0.25s cubic-bezier(0.32, 0.72, 0, 1) both;
	}

	@keyframes slideInDrawer {
		from { transform: translateX(-100%); }
		to { transform: translateX(0); }
	}

	.drawer-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 1rem 1rem 0.85rem;
		border-bottom: 0.5px solid var(--theme-glass-border);
	}

	.drawer-brand {
		display: flex;
		align-items: center;
		gap: 0.65rem;
	}

	.drawer-brand-icon {
		width: 38px;
		height: 38px;
		border-radius: 10px;
		display: grid;
		place-items: center;
		background: var(--theme-glass-bg);
		border: 1px solid var(--theme-glass-border);
		box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
	}

	.drawer-brand-logo {
		width: 24px;
		height: 24px;
		object-fit: contain;
	}

	.drawer-brand-title {
		margin: 0;
		font-size: 1rem;
		font-weight: 700;
		color: var(--theme-text-primary);
	}

	.drawer-brand-subtitle {
		margin: 0.1rem 0 0;
		font-size: 0.68rem;
		color: var(--theme-text-secondary);
		text-transform: uppercase;
		letter-spacing: 0.06em;
		font-weight: 600;
	}

	.drawer-close {
		width: 32px;
		height: 32px;
		display: flex;
		align-items: center;
		justify-content: center;
		background: rgba(255, 255, 255, 0.08);
		border: none;
		border-radius: 50%;
		color: var(--theme-text-secondary);
		cursor: pointer;
		transition: background 0.12s;
		-webkit-tap-highlight-color: transparent;
	}

	.drawer-close:active {
		background: rgba(255, 255, 255, 0.16);
	}

	.drawer-nav {
		flex: 1;
		padding: 0.65rem 0.6rem;
		display: flex;
		flex-direction: column;
		gap: 0.2rem;
		overflow-y: auto;
		-webkit-overflow-scrolling: touch;
	}

	.drawer-footer {
		padding: 0.7rem 0.6rem calc(0.8rem + env(safe-area-inset-bottom, 0px));
		border-top: 0.5px solid var(--theme-glass-border);
		background: linear-gradient(180deg, rgba(255, 255, 255, 0.06), rgba(255, 255, 255, 0.14));
	}

	.drawer-signout {
		display: flex;
		align-items: center;
		gap: 0.7rem;
		width: 100%;
		padding: 0.72rem 0.75rem;
		border: none;
		border-radius: 12px;
		background: rgba(239, 68, 68, 0.12);
		color: #b91c1c;
		font: inherit;
		font-size: 0.95rem;
		font-weight: 700;
		text-align: left;
		cursor: pointer;
		transition: background 0.12s, transform 0.12s;
		-webkit-tap-highlight-color: transparent;
	}

	.drawer-signout:active {
		background: rgba(239, 68, 68, 0.2);
		transform: scale(0.99);
	}

	.drawer-link {
		display: flex;
		align-items: center;
		gap: 0.7rem;
		padding: 0.7rem 0.75rem;
		border: none;
		background: transparent;
		border-radius: 12px;
		font-size: 0.95rem;
		font-weight: 600;
		color: var(--theme-text-secondary);
		cursor: pointer;
		text-align: left;
		transition: background 0.12s, color 0.12s;
		-webkit-tap-highlight-color: transparent;
	}

	.drawer-link:active {
		background: var(--theme-surface-hover);
	}

	.drawer-link.active {
		background: rgba(var(--theme-primary-rgb, 56, 152, 224), 0.14);
		color: var(--theme-primary);
	}

	.drawer-link-icon {
		width: 1.75rem;
		height: 1.75rem;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		font-size: 1.05rem;
		background: rgba(255, 255, 255, 0.08);
		border: 1px solid var(--theme-glass-border);
		border-radius: 8px;
		box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
		flex-shrink: 0;
	}

	/* ─── Hide on desktop ─── */
	@media (min-width: 960px) {
		.mnb {
			display: none;
		}

		.drawer-backdrop,
		.drawer-panel {
			display: none;
		}
	}
</style>
