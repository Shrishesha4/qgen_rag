<script lang="ts">
	import type { Snippet } from 'svelte';
	import { setContext } from 'svelte';
	import Sidebar from './Sidebar.svelte';

	interface NavItem {
		label: string;
		icon: string;
		href: string;
	}

	interface Props {
		navItems?: NavItem[];
		children: Snippet;
	}

	let { navItems = [], children }: Props = $props();

	let sidebarOpen = $state(false);

	function toggleSidebar() {
		sidebarOpen = !sidebarOpen;
	}

	function closeSidebar() {
		sidebarOpen = false;
	}

	// Provide hamburger context for PageHeader
	setContext('hamburger', { toggleSidebar });
</script>

<div class="layout layout-with-hamburger">
	<Sidebar items={navItems} isOpen={sidebarOpen} onClose={closeSidebar} />
	{#if sidebarOpen}
		<div class="sidebar-overlay" role="button" tabindex="0" onclick={closeSidebar} onkeydown={(e) => { if (e.key === 'Escape') closeSidebar(); }}></div>
	{/if}
	<main class="content" class:sidebar-open={sidebarOpen}>
		{@render children()}
	</main>
</div>

<style>
	.layout {
		display: flex;
		min-height: 100vh;
	}

	.layout :global(.sidebar.open) {
		transform: translateX(0);
	}

	.sidebar-overlay {
		display: none;
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.5);
		z-index: 29;
	}

	.content {
		flex: 1;
		margin-left: 0;
		min-height: 100vh;
		transition: margin-left 0.3s ease;
	}

	.content.sidebar-open {
		margin-left: 260px;
	}

	@media (max-width: 1024px) {
		.content {
			margin-left: 0;
		}

		.content.sidebar-open {
			margin-left: 0;
		}

		.sidebar-overlay {
			display: block;
		}
	}
</style>
