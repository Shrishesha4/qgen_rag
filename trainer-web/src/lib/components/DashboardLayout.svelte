<script lang="ts">
	import type { Snippet } from 'svelte';

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
		min-height: 100vh;
	}
</style>
