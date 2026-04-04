<script lang="ts">
	import { onMount } from 'svelte';
	import { currentColorMode, setColorMode, currentThemeName, setTheme, zenMode, toggleZenMode, type ColorMode } from '$lib/theme';
	import { themeNames, themes } from '$lib/theme/themes';

	let open = $state(false);
	let rootEl: HTMLDivElement | null = null;

	function handleGlobalPointerDown(event: PointerEvent) {
		if (!open || !rootEl) return;
		const target = event.target as Node | null;
		if (target && !rootEl.contains(target)) {
			open = false;
		}
	}

	onMount(() => {
		document.addEventListener('pointerdown', handleGlobalPointerDown, true);
		return () => {
			document.removeEventListener('pointerdown', handleGlobalPointerDown, true);
		};
	});

	function select(name: (typeof themeNames)[number]) {
		setTheme(name);
		open = false;
	}

	function selectColorMode(mode: ColorMode) {
		setColorMode(mode);
	}

	function handleZenToggle() {
		toggleZenMode();
	}
</script>

<div class="theme-picker" bind:this={rootEl}>
	<button
		class="picker-toggle"
		onclick={() => (open = !open)}
		aria-label="Change theme"
		title="Change theme"
	>
		<span class="toggle-icon" style="background-image: url('{themes[$currentThemeName].bgImage}')"></span>
	</button>

	{#if open}
		<!-- svelte-ignore a11y_click_events_have_key_events -->
		<!-- svelte-ignore a11y_no_static_element_interactions -->
		<div class="picker-backdrop" onclick={() => (open = false)}></div>
		<div class="picker-menu" role="menu">
			<div class="mode-section">
				<p class="mode-label">Appearance</p>
				<div class="mode-switch" role="group" aria-label="Select color mode">
					<button
						type="button"
						class="mode-option"
						class:active={$currentColorMode === 'light'}
						onclick={() => selectColorMode('light')}
					>
						Light
					</button>
					<button
						type="button"
						class="mode-option"
						class:active={$currentColorMode === 'dark'}
						onclick={() => selectColorMode('dark')}
					>
						Dark
					</button>
				</div>
			</div>

			<div class="zen-section">
				<button
					type="button"
					class="zen-toggle"
					class:active={$zenMode}
					onclick={handleZenToggle}
					aria-pressed={$zenMode}
				>
					<span class="zen-icon">{$zenMode ? '✨' : '🧘'}</span>
					<span class="zen-label">Zen Mode</span>
					<span class="zen-badge">{$zenMode ? 'ON' : 'OFF'}</span>
				</button>
			</div>

			<div class="menu-divider" aria-hidden="true"></div>

			{#each themeNames as name}
				<button
					class="picker-option"
					class:active={$currentThemeName === name}
					onclick={() => select(name)}
					role="menuitem"
				>
					<span class="option-icon" style="background-image: url('{themes[name].bgImage}')"></span>
					<span class="option-label">{themes[name].label}</span>
				</button>
			{/each}
		</div>
	{/if}
</div>

<style>
	.theme-picker {
		position: relative;
		z-index: 100;
	}

	.picker-toggle {
		width: 2.5rem;
		height: 2.5rem;
		border-radius: 50%;
		background: var(--theme-nav-glass);
		border: 1px solid var(--theme-glass-border);
		cursor: pointer;
		font-size: 1.2rem;
		display: flex;
		align-items: center;
		justify-content: center;
		transition: all 0.2s ease;
		box-shadow: 0 4px 14px rgba(0, 0, 0, 0.18);
	}

	.picker-toggle:hover {
		background: var(--theme-surface-hover);
		transform: scale(1.1);
		box-shadow: 0 4px 16px var(--theme-glow);
	}

	.toggle-icon {
		width: 100%;
		height: 100%;
		border-radius: 50%;
		background-size: cover;
		background-position: center;
		display: inline-flex;
		align-items: center;
		justify-content: center;
	}

	.picker-backdrop {
		position: fixed;
		inset: 0;
		z-index: 99;
	}

	.picker-menu {
		position: absolute;
		bottom: calc(100% + 1.5rem);
		top: auto;
		right: 0;
		background: var(--theme-nav-glass);
		border: 1px solid var(--theme-glass-border);
		border-radius: 0.75rem;
		padding: 0.5rem;
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		box-shadow: 0 14px 36px rgba(0, 0, 0, 0.28);
		min-width: 12.5rem;
		z-index: 100;
		transform-origin: bottom right;
		backdrop-filter: blur(14px) saturate(130%);
		-webkit-backdrop-filter: blur(14px) saturate(130%);
	}

	:global([data-color-mode='light']) .picker-menu {
		backdrop-filter: blur(20px) saturate(140%);
		-webkit-backdrop-filter: blur(20px) saturate(140%);
		background: rgba(255, 255, 255, 0.65);
	}

	.mode-section {
		display: grid;
		gap: 0.5rem;
		padding: 0.35rem 0.25rem 0.45rem;
	}

	.mode-label {
		margin: 0;
		font-size: 0.7rem;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		font-weight: 700;
		color: var(--theme-text-secondary);
	}

	.mode-switch {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 0.35rem;
	}

	.mode-option {
		padding: 0.38rem 0.45rem;
		border-radius: 0.5rem;
		border: 1px solid rgba(255, 255, 255, 0.16);
		background: rgba(255, 255, 255, 0.06);
		color: var(--theme-text);
		font-size: 0.76rem;
		font-weight: 700;
		letter-spacing: 0.02em;
		cursor: pointer;
		transition: 120ms ease;
	}

	.mode-option:hover {
		background: rgba(255, 255, 255, 0.12);
	}

	.mode-option.active {
		background: linear-gradient(180deg, rgba(var(--theme-primary-rgb), 0.95), rgba(var(--theme-primary-rgb), 0.7));
		border-color: rgba(var(--theme-primary-rgb), 0.9);
		color: #ffffff;
	}

	.menu-divider {
		height: 1px;
		background: rgba(255, 255, 255, 0.16);
		margin: 0.15rem 0 0.2rem;
	}

	/* Zen Mode Toggle */
	.zen-section {
		padding: 0.25rem;
	}

	.zen-toggle {
		width: 100%;
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.5rem 0.6rem;
		border-radius: 0.5rem;
		border: 1px solid rgba(255, 255, 255, 0.12);
		background: rgba(255, 255, 255, 0.04);
		color: var(--theme-text);
		font-size: 0.8rem;
		font-weight: 600;
		cursor: pointer;
		transition: all 0.15s ease;
	}

	.zen-toggle:hover {
		background: rgba(255, 255, 255, 0.1);
		border-color: rgba(255, 255, 255, 0.2);
	}

	.zen-toggle.active {
		background: linear-gradient(135deg, rgba(16, 185, 129, 0.2), rgba(59, 130, 246, 0.15));
		border-color: rgba(16, 185, 129, 0.5);
	}

	.zen-icon {
		font-size: 1rem;
		line-height: 1;
	}

	.zen-label {
		flex: 1;
		text-align: left;
	}

	.zen-badge {
		font-size: 0.65rem;
		font-weight: 700;
		letter-spacing: 0.05em;
		padding: 0.15rem 0.4rem;
		border-radius: 0.25rem;
		background: rgba(255, 255, 255, 0.1);
		color: var(--theme-text-secondary);
	}

	.zen-toggle.active .zen-badge {
		background: rgba(16, 185, 129, 0.3);
		color: #10b981;
	}

	:global([data-color-mode='light']) .zen-toggle.active .zen-badge {
		background: rgba(16, 185, 129, 0.15);
		color: #059669;
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
		width: 1.8rem;
		height: 1.8rem;
		border-radius: 50%;
		background-size: cover;
		background-position: center;
		border: 2px solid var(--theme-glass-border);
		display: inline-flex;
		align-items: center;
		justify-content: center;
		overflow: hidden;
	}

	/* On mobile, open menu downward since the picker is in the top nav bar */
	@media (max-width: 959px) {
		.picker-menu {
			bottom: auto;
			top: calc(100% + 0.5rem);
			transform-origin: top right;
			background: var(--theme-nav-glass);
			backdrop-filter: blur(16px) saturate(150%);
			-webkit-backdrop-filter: blur(16px) saturate(150%);
			border-color: var(--theme-glass-border);
			box-shadow: 0 8px 32px rgba(0, 0, 0, 0.18);
		}

		.picker-option {
			color: var(--theme-text);
		}

		.picker-option:hover {
			background: var(--theme-surface-hover);
		}

		.picker-option.active {
			background: var(--theme-primary);
			color: white;
		}
	}
</style>
