<script lang="ts">
	import { page } from '$app/stores';
	import { setTheme, currentThemeName } from '$lib/theme';
	import { themes, themeNames, type ThemeName } from '$lib/theme/themes';
	import { session } from '$lib/session';
	import { logout } from '$lib/api/auth';
	import { goto } from '$app/navigation';

	interface NavItem {
		label: string;
		icon: string;
		href: string;
	}

	interface Props {
		items?: NavItem[];
		isOpen?: boolean;
		onClose?: () => void;
	}

	let { items = [], isOpen = false, onClose = () => {} }: Props = $props();

	let showThemeMenu = $state(false);

	const defaultTeacherItems: NavItem[] = [
		{ label: 'Home', icon: '🏠', href: '/teacher/dashboard' },
		{ label: 'Train Topic', icon: '📚', href: '/teacher/train' },
		{ label: 'Verifier Mode', icon: '🔍', href: '/teacher/verify' }
	];

	let navItems = $derived(items.length > 0 ? items : defaultTeacherItems);

	function isActive(href: string): boolean {
		const path = $page.url.pathname;
		if (href === '/teacher/dashboard') return path === href;
		return path.startsWith(href);
	}

	function pickTheme(name: ThemeName) {
		setTheme(name);
		showThemeMenu = false;
	}

	async function handleLogout() {
		await logout();
		session.clear();
		goto('/');
	}
</script>

<aside class="sidebar glass-sidebar" class:open={isOpen}>
	<div class="sidebar-inner">
		<!-- Logo -->
		<div class="logo-section">
			<div class="logo-icon">🧠</div>
			<div class="logo-text">
				<span class="logo-title">AI Training</span>
				<span class="logo-sub">Knowledge Engine</span>
			</div>
		</div>

		<!-- Navigation -->
		<nav class="nav-section">
			{#each navItems as item}
				<a
					href={item.href}
					class="nav-item"
					class:nav-active={isActive(item.href)}
					onclick={onClose}
				>
					<span class="nav-icon">{item.icon}</span>
					<span class="nav-label">{item.label}</span>
				</a>
			{/each}
		</nav>

		<!-- Footer: Theme + Logout -->
		<div class="sidebar-footer">
			<div class="theme-section">
				<button class="theme-trigger" onclick={() => showThemeMenu = !showThemeMenu}>
					<span class="theme-label-text">THEME</span>
					<span class="theme-current">
						{themes[$currentThemeName].icon}
						{themes[$currentThemeName].label}
						<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
							<polyline points="9 18 15 12 9 6"></polyline>
						</svg>
					</span>
				</button>

				{#if showThemeMenu}
					<div class="theme-menu">
						{#each themeNames as name}
							<button
								class="theme-opt"
								class:active={$currentThemeName === name}
								onclick={() => pickTheme(name)}
							>
								<span>{themes[name].icon}</span>
								<span>{themes[name].label}</span>
							</button>
						{/each}
					</div>
				{/if}
			</div>

			<button class="logout-btn" onclick={handleLogout}>
				<span>🚪</span>
				<span>Sign Out</span>
			</button>
		</div>
	</div>
</aside>

<style>
	.sidebar {
		width: 260px;
		height: 100vh;
		position: fixed;
		top: 0;
		left: 0;
		display: flex;
		flex-direction: column;
		z-index: 30;
		overflow-y: auto;
		transform: translateX(-100%);
		transition: transform 0.3s ease;
	}

	.sidebar.open {
		transform: translateX(0);
	}

	@media (max-width: 1024px) {
		.sidebar {
			width: min(260px, calc(100vw - 3rem));
		}
	}



	.sidebar-inner {
		display: flex;
		flex-direction: column;
		height: 100%;
		padding: 1.5rem 1rem;
	}

	/* Logo */
	.logo-section {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		padding: 0.5rem;
		margin-bottom: 2rem;
	}

	.logo-icon {
		font-size: 1.75rem;
		width: 44px;
		height: 44px;
		display: flex;
		align-items: center;
		justify-content: center;
		background: rgba(255, 255, 255, 0.1);
		border-radius: 12px;
		border: 0.5px solid rgba(255, 255, 255, 0.12);
	}

	.logo-text {
		display: flex;
		flex-direction: column;
	}

	.logo-title {
		font-weight: 700;
		font-size: 1rem;
		color: var(--theme-text);
		line-height: 1.2;
	}

	.logo-sub {
		font-size: 0.75rem;
		color: var(--theme-text-muted);
		line-height: 1.2;
	}

	/* Navigation */
	.nav-section {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		flex: 1;
	}

	.nav-item {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		padding: 0.75rem 0.75rem;
		border-radius: 12px;
		color: var(--theme-text-muted);
		text-decoration: none;
		font-size: 0.95rem;
		font-weight: 500;
		transition: all 0.2s ease;
	}

	.nav-item:hover {
		background: rgba(255, 255, 255, 0.08);
		color: var(--theme-text);
	}

	.nav-active {
		background: rgba(var(--theme-primary-rgb), 0.15);
		color: var(--theme-primary);
		font-weight: 600;
	}

	.nav-active:hover {
		background: rgba(var(--theme-primary-rgb), 0.2);
		color: var(--theme-primary);
	}

	.nav-icon {
		font-size: 1.2rem;
		width: 28px;
		text-align: center;
	}

	/* Footer */
	.sidebar-footer {
		margin-top: auto;
		padding-top: 1rem;
		border-top: 0.5px solid rgba(255, 255, 255, 0.08);
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.theme-section {
		position: relative;
	}

	.theme-trigger {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		width: 100%;
		padding: 0.5rem 0.75rem;
		border: none;
		border-radius: 10px;
		background: transparent;
		color: var(--theme-text);
		cursor: pointer;
		text-align: left;
		transition: background 0.15s;
	}

	.theme-trigger:hover {
		background: rgba(255, 255, 255, 0.06);
	}

	.theme-label-text {
		font-size: 0.65rem;
		font-weight: 700;
		letter-spacing: 0.08em;
		color: var(--theme-text-muted);
		text-transform: uppercase;
	}

	.theme-current {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		font-size: 0.9rem;
		font-weight: 500;
	}

	.theme-current svg {
		margin-left: auto;
		opacity: 0.5;
	}

	.theme-menu {
		position: absolute;
		bottom: calc(100% + 8px);
		left: 0;
		right: 0;
		padding: 0.4rem;
		background: rgba(30, 30, 50, 0.9);
		backdrop-filter: blur(24px);
		-webkit-backdrop-filter: blur(24px);
		border: 0.5px solid rgba(255, 255, 255, 0.15);
		border-radius: 12px;
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
		z-index: 40;
	}

	.theme-opt {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.5rem 0.75rem;
		border: none;
		border-radius: 8px;
		background: transparent;
		color: var(--theme-text);
		font-size: 0.9rem;
		cursor: pointer;
		transition: background 0.15s;
	}

	.theme-opt:hover {
		background: rgba(255, 255, 255, 0.1);
	}

	.theme-opt.active {
		background: rgba(var(--theme-primary-rgb), 0.2);
		color: var(--theme-primary);
	}

	.logout-btn {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		width: 100%;
		padding: 0.6rem 0.75rem;
		border: none;
		border-radius: 10px;
		background: transparent;
		color: var(--theme-text-muted);
		font-size: 0.9rem;
		cursor: pointer;
		transition: all 0.15s;
	}

	.logout-btn:hover {
		background: rgba(233, 69, 96, 0.15);
		color: #e94560;
	}
</style>
