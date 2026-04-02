<script lang="ts">
	import type { Snippet } from 'svelte';

	let {
		leftWidth = $bindable(50),
		minLeft = 300,
		minRight = 300,
		left,
		right,
	}: {
		leftWidth: number;
		minLeft?: number;
		minRight?: number;
		left: Snippet;
		right: Snippet;
	} = $props();

	let container = $state<HTMLDivElement | null>(null);
	let isDragging = $state(false);

	function onPointerDown(e: PointerEvent) {
		isDragging = true;
		(e.target as HTMLElement).setPointerCapture(e.pointerId);
	}

	function onPointerMove(e: PointerEvent) {
		if (!isDragging || !container) return;
		const rect = container.getBoundingClientRect();
		const totalWidth = rect.width;
		const x = e.clientX - rect.left;
		const pct = (x / totalWidth) * 100;
		const minLeftPct = (minLeft / totalWidth) * 100;
		const minRightPct = 100 - (minRight / totalWidth) * 100;
		leftWidth = Math.min(Math.max(pct, minLeftPct), minRightPct);
	}

	function onPointerUp() {
		isDragging = false;
	}
</script>

<div
	class="splitter-container"
	bind:this={container}
	class:dragging={isDragging}
>
	<div class="splitter-left" style="width: {leftWidth}%">
		{@render left()}
	</div>
	<!-- svelte-ignore a11y_no_noninteractive_tabindex a11y_no_noninteractive_element_interactions a11y_no_static_element_interactions -->
	<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
	<div
		class="splitter-handle"
		role="separator"
		aria-valuenow={Math.round(leftWidth)}
		tabindex="0"
		onpointerdown={onPointerDown}
		onpointermove={onPointerMove}
		onpointerup={onPointerUp}
		onkeydown={(e) => {
			if (e.key === 'ArrowLeft') leftWidth = Math.max(leftWidth - 2, (minLeft / (container?.offsetWidth ?? 800)) * 100);
			if (e.key === 'ArrowRight') leftWidth = Math.min(leftWidth + 2, 100 - (minRight / (container?.offsetWidth ?? 800)) * 100);
		}}
	>
		<div class="handle-grip"></div>
	</div>
	<div class="splitter-right" style="width: {100 - leftWidth}%">
		{@render right()}
	</div>
</div>

<style>
	.splitter-container {
		display: flex;
		width: 100%;
		height: 100%;
		overflow: hidden;
	}

	.splitter-container.dragging {
		cursor: col-resize;
		user-select: none;
	}

	.splitter-left,
	.splitter-right {
		overflow: auto;
		height: 100%;
	}

	.splitter-handle {
		flex-shrink: 0;
		width: 8px;
		cursor: col-resize;
		display: flex;
		align-items: center;
		justify-content: center;
		background: color-mix(in srgb, var(--theme-glass-border) 40%, transparent);
		transition: background 0.15s;
	}

	.splitter-handle:hover,
	.splitter-handle:focus-visible {
		background: color-mix(in srgb, var(--theme-glass-border) 80%, transparent);
	}

	.handle-grip {
		width: 3px;
		height: 32px;
		border-radius: 2px;
		background: var(--theme-text-secondary);
		opacity: 0.45;
	}

	.splitter-handle:hover .handle-grip {
		opacity: 0.8;
	}

	@media (max-width: 768px) {
		.splitter-container {
			flex-direction: column;
		}

		.splitter-left,
		.splitter-right {
			width: 100% !important;
			height: auto;
		}

		.splitter-handle {
			display: none;
		}
	}
</style>
