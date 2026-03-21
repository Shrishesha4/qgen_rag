<script lang="ts">
	import { currentThemeName, setTheme } from '$lib/theme';
	import { themeNames, themes } from '$lib/theme/themes';

	let open = $state(false);

	function select(name: (typeof themeNames)[number]) {
		setTheme(name);
		open = false;
	}
</script>

<div class="theme-picker">
	<button
		class="picker-toggle"
		onclick={() => (open = !open)}
		aria-label="Change theme"
		title="Change theme"
	>
		{themes[$currentThemeName].icon}
	</button>

	{#if open}
		<!-- svelte-ignore a11y_click_events_have_key_events -->
		<!-- svelte-ignore a11y_no_static_element_interactions -->
		<div class="picker-backdrop" onclick={() => (open = false)}></div>
		<div class="picker-menu" role="menu">
			{#each themeNames as name}
				<button
					class="picker-option"
					class:active={$currentThemeName === name}
					onclick={() => select(name)}
					role="menuitem"
				>
					<span class="option-icon">{themes[name].icon}</span>
					<span class="option-label">{themes[name].label}</span>
				</button>
			{/each}
		</div>
	{/if}
</div>

<style>
	.theme-picker {
		position: relative;
		z-index: 50;
	}

	.picker-toggle {
		width: 2.5rem;
		height: 2.5rem;
		border-radius: 50%;
		background: var(--theme-surface);
		border: 1px solid var(--theme-border);
		cursor: pointer;
		font-size: 1.2rem;
		display: flex;
		align-items: center;
		justify-content: center;
		transition: all 0.2s ease;
		box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
	}

	.picker-toggle:hover {
		background: var(--theme-surface-hover);
		transform: scale(1.1);
		box-shadow: 0 4px 16px var(--theme-glow);
	}

	.picker-backdrop {
		position: fixed;
		inset: 0;
		z-index: 40;
	}

	.picker-menu {
		position: absolute;
		bottom: calc(100% + 0.5rem);
		top: auto;
		right: 0;
		background: var(--theme-surface);
		border: 1px solid var(--theme-border);
		border-radius: 0.75rem;
		padding: 0.5rem;
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		box-shadow: 0 8px 32px rgba(0, 0, 0, 0.15);
		min-width: 9rem;
		z-index: 50;
		transform-origin: bottom right;
	}

	.picker-option {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.5rem 0.75rem;
		border: none;
		background: transparent;
		border-radius: 0.5rem;
		cursor: pointer;
		color: var(--theme-text);
		font-size: 0.9rem;
		transition: background 0.15s ease;
	}

	.picker-option:hover {
		background: var(--theme-surface-hover);
	}

	.picker-option.active {
		background: var(--theme-primary);
		color: white;
	}

	.option-icon {
		font-size: 1.1rem;
	}
</style>
