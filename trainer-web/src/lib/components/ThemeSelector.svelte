<script lang="ts">
	import { currentThemeName, setTheme } from '$lib/theme';
	import { themeNamesStore, themes } from '$lib/theme/themes';
	import type { ThemeName } from '$lib/theme/themes';

	let expanded = $state(false);

	function toggleExpanded() {
		expanded = !expanded;
	}

	function selectTheme(name: ThemeName) {
		setTheme(name);
		expanded = false;
	}
</script>

<div class="theme-selector glass-panel" class:expanded>
	<button class="selector-toggle" onclick={toggleExpanded} title="Theme selector">
		<svg class="selector-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
			<rect width="18" height="18" x="3" y="3" rx="2" ry="2"></rect>
			<circle cx="9" cy="9" r="2"></circle>
			<path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"></path>
		</svg>
	</button>
	<div class="selector-thumbs">
		{#each $themeNamesStore as name, i}
			<button
				class="thumb"
				class:active={$currentThemeName === name}
				onclick={() => selectTheme(name)}
				title={themes[name].label}
				style:--index={i}
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

<style>
	.theme-selector {
		position: fixed;
		bottom: 1.5rem;
		right: 1.5rem;
		z-index: 50;
		display: flex;
		align-items: center;
		gap: 0.75rem;
		padding: 0.5rem 1rem;
		border-radius: 999px;
	}

	.selector-toggle {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		background: none;
		border: none;
		cursor: pointer;
		padding: 0;
		color: inherit;
	}

	.selector-icon {
		color: rgba(255, 255, 255, 0.7);
		flex-shrink: 0;
	}

	.selector-thumbs {
		display: flex;
		gap: 0.5rem;
	}

	.thumb {
		width: 1.5rem;
		height: 1.5rem;
		border-radius: 50%;
		border: 2px solid rgba(255, 255, 255, 0.2);
		overflow: hidden;
		cursor: pointer;
		transition: all 0.3s ease;
		padding: 0;
		background: none;
		opacity: 0.7;
		flex-shrink: 0;
	}

	.thumb:hover {
		border-color: rgba(255, 255, 255, 0.5);
		opacity: 1;
	}

	.thumb.active {
		border-color: white;
		transform: scale(1.1);
		box-shadow: 0 0 10px rgba(255, 255, 255, 0.5);
		opacity: 1;
	}

	.thumb img {
		width: 100%;
		height: 100%;
		object-fit: cover;
		display: block;
	}

	@media (max-width: 768px) {
		.theme-selector {
			bottom: 1.25rem;
			right: 1.25rem;
			padding: 0.45rem 0.85rem;
			gap: 0.6rem;
		}

		.selector-icon {
			width: 14px;
			height: 14px;
		}

		.thumb {
			width: 1.35rem;
			height: 1.35rem;
		}
	}

	@media (max-width: 480px) {
		.theme-selector {
			bottom: 1rem;
			right: 1rem;
			padding: 0;
			width: 3.5rem;
			height: 3.5rem;
			border-radius: 50%;
			justify-content: center;
			align-items: center;
			transition: all 0.4s cubic-bezier(0.68, -0.55, 0.265, 1.55);
			overflow: visible;
			background: transparent;
			backdrop-filter: none;
			border: none;
			box-shadow: none;
		}

		.theme-selector.expanded {
			width: auto;
			border-radius: 999px;
			justify-content: flex-end;
			padding: 0.5rem 0.5rem 0.5rem 0.75rem;
			gap: 0.5rem;
			background: var(--glass-bg);
			backdrop-filter: var(--glass-blur);
			border: 1px solid var(--glass-border);
			box-shadow: var(--glass-shadow);
		}

		.theme-selector::before,
		.theme-selector::after {
			display: none;
		}

		.selector-toggle {
			width: 3.5rem;
			height: 3.5rem;
			justify-content: center;
			align-items: center;
			border-radius: 50%;
			flex-shrink: 0;
			order: 2;
			background: var(--glass-bg);
			backdrop-filter: var(--glass-blur);
			border: 1px solid var(--glass-border);
			box-shadow: var(--glass-shadow);
			transition: transform 0.3s ease;
		}

		.selector-icon {
			width: 20px;
			height: 20px;
		}

		.selector-thumbs {
			display: flex;
			flex-direction: row;
			order: 1;
			gap: 0.5rem;
			width: 0;
			opacity: 0;
			transform: translateX(20px);
			transition: all 0.4s cubic-bezier(0.68, -0.55, 0.265, 1.55);
			pointer-events: none;
			overflow: hidden;
		}

		.theme-selector.expanded .selector-thumbs {
			width: auto;
			opacity: 1;
			transform: translateX(0);
			pointer-events: all;
		}

		.thumb {
			width: 2.75rem;
			height: 2.75rem;
			border-width: 2px;
			flex-shrink: 0;
			opacity: 0;
			transform: scale(0.5);
			transition: all 0.3s cubic-bezier(0.68, -0.55, 0.265, 1.55);
			transition-delay: calc(var(--index) * 0.05s);
			box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
		}

		.theme-selector.expanded .thumb {
			opacity: 1;
			transform: scale(1);
		}

		.thumb:hover,
		.thumb.active {
			transform: scale(1.1);
		}

		.theme-selector:not(.expanded) .thumb {
			transition-delay: calc((4 - var(--index)) * 0.03s);
		}
	}
</style>
