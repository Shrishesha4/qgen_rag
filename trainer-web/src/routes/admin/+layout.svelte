<script lang="ts">
	import { page } from '$app/stores';

	let { children } = $props();

	let isLoginPage = $derived($page.url.pathname.includes('/login'));
	let navItems = $derived([
		{ href: '/admin/dashboard', label: 'Dashboard' },
		{ href: '/admin/subjects', label: 'Subjects' }
	]);
</script>

{#if isLoginPage}
	{@render children()}
{:else}
	<div class="admin-shell-nav">
		{#each navItems as item}
			<a href={item.href} class="nav-link" class:active={$page.url.pathname === item.href || $page.url.pathname.startsWith(`${item.href}/`)}>
				{item.label}
			</a>
		{/each}
	</div>
	{@render children()}
{/if}

<style>
	.admin-shell-nav {
		position: sticky;
		top: calc(env(safe-area-inset-top) + 0.75rem);
		z-index: 60;
		display: flex;
		gap: 0.4rem;
		justify-content: center;
		width: fit-content;
		margin: 0 auto;
		padding: 0.35rem;
		border-radius: 999px;
		background: linear-gradient(
			145deg,
			rgba(255,255,255,0.08) 0%,
			rgba(255,255,255,0.04) 50%,
			rgba(255,255,255,0.06) 100%
		);
		backdrop-filter: blur(10px) saturate(150%) brightness(1.02);
		-webkit-backdrop-filter: blur(10px) saturate(150%) brightness(1.02);
		box-shadow:
			0 8px 32px rgba(0, 0, 0, 0.2),
			inset 0 1px 1px rgba(255, 255, 255, 0.2),
			0 0 0 1px rgba(255, 255, 255, 0.12);
	}

	.nav-link {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		padding: 0.6rem 1rem;
		border-radius: 999px;
		color: var(--theme-text-muted);
		text-decoration: none;
		font-size: 0.85rem;
		font-weight: 700;
		transition: all 0.2s ease;
	}

	.nav-link:hover {
		color: var(--theme-text);
		background: rgba(255, 255, 255, 0.06);
	}

	.nav-link.active {
		background: rgba(245, 158, 11, 0.2);
		color: #fbbf24;
		box-shadow: inset 0 1px 1px rgba(255, 255, 255, 0.15);
	}

	@media (max-width: 640px) {
		.admin-shell-nav {
			top: calc(env(safe-area-inset-top) + 0.5rem);
		}

		.nav-link {
			padding: 0.55rem 0.85rem;
			font-size: 0.8rem;
		}
	}
</style>
