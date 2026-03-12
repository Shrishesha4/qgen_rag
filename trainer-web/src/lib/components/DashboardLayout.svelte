<script lang="ts">
	import type { Snippet } from 'svelte';
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
</script>

<div class="layout">
	<Sidebar items={navItems} />
	<main class="content">
		{@render children()}
	</main>
</div>

<style>
	.layout {
		display: flex;
		min-height: 100vh;
	}

	.content {
		flex: 1;
		margin-left: 260px;
		min-height: 100vh;
	}

	@media (max-width: 768px) {
		.content {
			margin-left: 0;
		}
	}
</style>
