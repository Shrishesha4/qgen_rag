<script lang="ts">
	import { currentThemeName, setTheme } from '$lib/theme';
	import { themeNames, themes } from '$lib/theme/themes';
</script>

<div class="theme-selector glass-panel">
	<svg class="selector-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
		<rect width="18" height="18" x="3" y="3" rx="2" ry="2"></rect>
		<circle cx="9" cy="9" r="2"></circle>
		<path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"></path>
	</svg>
	<span class="selector-label">Theme</span>
	<div class="selector-thumbs">
		{#each themeNames as name}
			<button
				class="thumb"
				class:active={$currentThemeName === name}
				onclick={() => setTheme(name)}
				title={themes[name].label}
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

	.selector-icon {
		color: rgba(255, 255, 255, 0.7);
		flex-shrink: 0;
	}

	.selector-label {
		font-size: 0.875rem;
		font-weight: 500;
		color: rgba(255, 255, 255, 0.7);
		margin-right: 0.25rem;
		white-space: nowrap;
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

	@media (max-width: 480px) {
		.theme-selector {
			bottom: 1rem;
			right: 1rem;
			padding: 0.4rem 0.75rem;
			gap: 0.5rem;
		}

		.selector-label {
			display: none;
		}
	}
</style>
