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

	const defaultTeacherItems: NavItem[] = [
		{ label: 'Home', icon: 'home', href: '/teacher/dashboard' },
		{ label: 'Train Topic', icon: 'book', href: '/teacher/train' },
		{ label: 'Verifier Mode', icon: 'search', href: '/teacher/verify' }
	];

	let navItems = $derived(items.length > 0 ? items : defaultTeacherItems);

	function isActive(href: string): boolean {
		const path = $page.url.pathname;
		if (href === '/teacher/dashboard') return path === href;
		return path.startsWith(href);
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
			<div class="logo-icon">
				<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
					<path d="M12 2a7.5 7.5 0 0 0-5.5 12.5l.5.5V20h10v-5l.5-.5A7.5 7.5 0 0 0 12 2z"></path>
					<path d="M9 22h6"></path>
				</svg>
			</div>
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
					<span class="nav-icon-wrap">
						{#if item.icon === 'home'}
							<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path><polyline points="9 22 9 12 15 12 15 22"></polyline></svg>
						{:else if item.icon === 'book'}
							<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1 0-5H20"></path></svg>
						{:else if item.icon === 'search'}
							<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"></circle><path d="m21 21-4.3-4.3"></path></svg>
						{:else}
							<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle></svg>
						{/if}
					</span>
					<span class="nav-label">{item.label}</span>
				</a>
			{/each}
		</nav>

		<!-- Footer: Theme thumbnails + Logout -->
		<div class="sidebar-footer">
			<div class="theme-section">
				<span class="theme-label-text">THEME</span>
				<div class="theme-thumbs">
					{#each themeNames as name}
						<button
							class="theme-thumb"
							class:active={$currentThemeName === name}
							onclick={() => setTheme(name)}
							title={themes[name].label}
							aria-label={themes[name].label}
						>
							<img
								src={themes[name].bgImage}
								alt={themes[name].label}
								loading="lazy"
							/>
						</button>
					{/each}
				</div>
			</div>

			<button class="logout-btn" onclick={handleLogout}>
				<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
					<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
					<polyline points="16 17 21 12 16 7"></polyline>
					<line x1="21" y1="12" x2="9" y2="12"></line>
				</svg>
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
			top: calc(env(safe-area-inset-top, 0px) + 4.25rem);
			height: calc(100dvh - env(safe-area-inset-top, 0px) - 4.25rem);
			width: min(260px, calc(100vw - 3rem));
			border-top-right-radius: 22px;
			border-bottom-right-radius: 22px;
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
		width: 44px;
		height: 44px;
		display: flex;
		align-items: center;
		justify-content: center;
		background: rgba(255, 255, 255, 0.1);
		border-radius: 12px;
		border: 0.5px solid rgba(255, 255, 255, 0.12);
		color: var(--theme-primary);
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

	.nav-icon-wrap {
		width: 28px;
		display: flex;
		align-items: center;
		justify-content: center;
	}

	/* Footer */
	.sidebar-footer {
		margin-top: auto;
		padding-top: 1rem;
		border-top: 0.5px solid rgba(255, 255, 255, 0.08);
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}

	.theme-section {
		padding: 0 0.5rem;
	}

	.theme-label-text {
		display: block;
		font-size: 0.65rem;
		font-weight: 700;
		letter-spacing: 0.08em;
		color: var(--theme-text-muted);
		text-transform: uppercase;
		margin-bottom: 0.5rem;
	}

	.theme-thumbs {
		display: flex;
		gap: 0.5rem;
	}

	.theme-thumb {
		width: 36px;
		height: 36px;
		border-radius: 50%;
		overflow: hidden;
		border: 2px solid transparent;
		cursor: pointer;
		transition: all 0.2s ease;
		padding: 0;
		background: none;
		flex-shrink: 0;
	}

	.theme-thumb img {
		width: 100%;
		height: 100%;
		object-fit: cover;
	}

	.theme-thumb:hover {
		transform: scale(1.1);
		border-color: rgba(255, 255, 255, 0.4);
	}

	.theme-thumb.active {
		border-color: white;
		transform: scale(1.1);
		box-shadow: 0 0 8px rgba(255, 255, 255, 0.3);
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
		font-family: inherit;
	}

	.logout-btn:hover {
		background: rgba(233, 69, 96, 0.15);
		color: #e94560;
	}
</style>
