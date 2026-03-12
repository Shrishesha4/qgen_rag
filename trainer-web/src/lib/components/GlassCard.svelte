<script lang="ts">
	import type { Snippet } from 'svelte';

	interface Props {
		active?: boolean;
		href?: string;
		onclick?: () => void;
		padding?: string;
		children: Snippet;
	}

	let { active = false, href, onclick, padding = '1.5rem', children }: Props = $props();
</script>

{#if href}
	<a {href} class="gc" class:gc-active={active} style:padding={padding}>
		{@render children()}
	</a>
{:else}
	<button class="gc" class:gc-active={active} style:padding={padding} {onclick} type="button">
		{@render children()}
	</button>
{/if}

<style>
	.gc {
		display: flex;
		flex-direction: column;
		background: linear-gradient(135deg, rgba(255,255,255,0.12) 0%, rgba(255,255,255,0.06) 100%);
		backdrop-filter: var(--glass-blur);
		-webkit-backdrop-filter: var(--glass-blur);
		border: 0.5px solid var(--glass-border);
		border-radius: var(--glass-radius);
		box-shadow:
			inset 0 1px 0 0 rgba(255,255,255,0.1),
			var(--glass-shadow);
		color: var(--theme-text);
		text-decoration: none;
		text-align: left;
		cursor: pointer;
		transition: all 0.3s ease;
		width: 100%;
		font: inherit;
	}

	.gc:hover {
		background: linear-gradient(135deg, rgba(255,255,255,0.18) 0%, rgba(255,255,255,0.1) 100%);
		border-color: rgba(255,255,255,0.25);
		box-shadow:
			inset 0 1px 0 0 rgba(255,255,255,0.15),
			var(--glass-shadow-lg);
		transform: translateY(-2px);
	}

	.gc-active {
		background: linear-gradient(135deg, rgba(var(--theme-primary-rgb),0.3) 0%, rgba(var(--theme-primary-rgb),0.15) 100%);
		border: 1px solid rgba(var(--theme-primary-rgb),0.4);
		box-shadow:
			inset 0 1px 0 0 rgba(255,255,255,0.15),
			0 4px 24px rgba(var(--theme-primary-rgb),0.15);
	}

	.gc-active:hover {
		background: linear-gradient(135deg, rgba(var(--theme-primary-rgb),0.4) 0%, rgba(var(--theme-primary-rgb),0.2) 100%);
	}
</style>
