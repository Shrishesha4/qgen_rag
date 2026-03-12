<script lang="ts">
	import { goto } from '$app/navigation';
	import { getContext } from 'svelte';

	interface Props {
		title: string;
		backHref?: string;
		step?: number;
		totalSteps?: number;
	}

	let { title, backHref, step, totalSteps }: Props = $props();

	// Get hamburger context if available
	let hamburgerContext: any = $state();
	try {
		hamburgerContext = getContext('hamburger');
	} catch (e) {
		hamburgerContext = null;
	}

	function goBack() {
		if (backHref) goto(backHref);
		else history.back();
	}
</script>

<header class="page-header">
	<div class="header-left">
		{#if hamburgerContext?.toggleSidebar}
			<button class="header-icon-btn" onclick={hamburgerContext.toggleSidebar} aria-label="Toggle sidebar">
				<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
					<line x1="3" y1="6" x2="21" y2="6"></line>
					<line x1="3" y1="12" x2="21" y2="12"></line>
					<line x1="3" y1="18" x2="21" y2="18"></line>
				</svg>
			</button>
		{/if}
		<button class="header-icon-btn" onclick={goBack} aria-label="Go back">
			<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
				<polyline points="15 18 9 12 15 6"></polyline>
			</svg>
		</button>
	</div>

	<div class="header-center">
		<span class="header-title">{title}</span>
		{#if step && totalSteps}
			<span class="step-badge">{step}/{totalSteps}</span>
		{/if}
	</div>

	<!-- Spacer to keep title centered -->
	<div class="header-right"></div>
</header>

<style>
	.page-header {
		display: flex;
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

	.header-left {
		display: flex;
		align-items: center;
		gap: 0.25rem;
		min-width: 72px;
	}

	.header-icon-btn {
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
		transition: all 0.2s;
	}

	.header-icon-btn:hover {
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
		min-width: 72px;
	}
</style>
