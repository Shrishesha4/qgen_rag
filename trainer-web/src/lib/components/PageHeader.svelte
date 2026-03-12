<script lang="ts">
	interface Props {
		title: string;
		backHref?: string;
		step?: number;
		totalSteps?: number;
	}

	let { title, backHref, step, totalSteps }: Props = $props();

	import { goto } from '$app/navigation';
	import { setTheme, currentThemeName } from '$lib/theme';
	import { themes, themeNames, type ThemeName } from '$lib/theme/themes';

	let showThemeMenu = $state(false);

	function pickTheme(name: ThemeName) {
		setTheme(name);
		showThemeMenu = false;
	}

	function goBack() {
		if (backHref) goto(backHref);
		else history.back();
	}
</script>

<header class="page-header">
	<button class="back-btn" onclick={goBack} aria-label="Go back">
		<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
			<polyline points="15 18 9 12 15 6"></polyline>
		</svg>
	</button>

	<div class="header-center">
		<span class="header-title">{title}</span>
		{#if step && totalSteps}
			<span class="step-badge">{step}/{totalSteps}</span>
		{/if}
	</div>

	<div class="header-right">
		<button class="theme-toggle" onclick={() => showThemeMenu = !showThemeMenu} aria-label="Change theme">
			{themes[$currentThemeName].icon}
		</button>
		{#if showThemeMenu}
		<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
		<div class="theme-dropdown glass" role="menu" tabindex="-1" onclick={(e) => e.stopPropagation()}>
				{#each themeNames as name}
					<button
						class="theme-option"
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
</header>

{#if showThemeMenu}
	<!-- svelte-ignore a11y_no_static_element_interactions a11y_click_events_have_key_events -->
	<div class="backdrop" role="presentation" onclick={() => showThemeMenu = false}></div>
{/if}

<style>
	.page-header {
		display: none;
		align-items: center;
		justify-content: space-between;
		padding: 0.75rem 1rem;
		position: sticky;
		top: 0;
		z-index: 50;
		background: rgba(0, 0, 0, 0.15);
		backdrop-filter: blur(20px) saturate(180%);
		-webkit-backdrop-filter: blur(20px) saturate(180%);
		border-bottom: 0.5px solid rgba(255, 255, 255, 0.08);
	}

	@media (max-width: 768px) {
		.page-header {
			display: flex;
		}
	}

	.back-btn {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 36px;
		height: 36px;
		border: none;
		border-radius: 10px;
		background: rgba(255, 255, 255, 0.1);
		color: var(--theme-text);
		cursor: pointer;
		transition: background 0.2s;
	}

	.back-btn:hover {
		background: rgba(255, 255, 255, 0.18);
	}

	.header-center {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	.header-title {
		font-weight: 600;
		font-size: 1rem;
		color: var(--theme-text);
	}

	.step-badge {
		font-size: 0.75rem;
		font-weight: 600;
		padding: 0.15rem 0.5rem;
		border-radius: 8px;
		background: rgba(var(--theme-primary-rgb), 0.25);
		color: var(--theme-primary);
	}

	.header-right {
		position: relative;
	}

	.theme-toggle {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 36px;
		height: 36px;
		border: none;
		border-radius: 10px;
		background: rgba(255, 255, 255, 0.1);
		font-size: 1.2rem;
		cursor: pointer;
		transition: background 0.2s;
	}

	.theme-toggle:hover {
		background: rgba(255, 255, 255, 0.18);
	}

	.theme-dropdown {
		position: absolute;
		top: calc(100% + 8px);
		right: 0;
		padding: 0.5rem;
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		min-width: 140px;
		z-index: 60;
	}

	.theme-option {
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

	.theme-option:hover {
		background: rgba(255, 255, 255, 0.1);
	}

	.theme-option.active {
		background: rgba(var(--theme-primary-rgb), 0.2);
		color: var(--theme-primary);
	}

	.backdrop {
		position: fixed;
		inset: 0;
		z-index: 40;
	}
</style>
