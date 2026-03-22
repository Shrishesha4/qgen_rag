<script lang="ts">
	import { fade, scale } from 'svelte/transition';

	export let open = false;
	export let title = 'Confirm Action';
	export let message = '';
	export let confirmText = 'Confirm';
	export let cancelText = 'Cancel';
	export let tone: 'neutral' | 'warning' = 'neutral';
	export let onConfirm: () => void | Promise<void> = () => {};
	export let onCancel: () => void = () => {};

	let pending = false;

	async function handleConfirm() {
		if (pending) return;
		pending = true;
		try {
			await onConfirm();
		} finally {
			pending = false;
		}
	}
</script>

{#if open}
	<div class="dialog-overlay" role="button" tabindex="0" aria-label="Close confirm" onclick={onCancel} onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && onCancel()} transition:fade={{ duration: 120 }}>
		<div class="dialog-card" class:warning={tone === 'warning'} role="dialog" aria-modal="true" tabindex="-1" onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.stopPropagation()} transition:scale={{ duration: 140, start: 0.96 }}>
			<div class="dialog-header">
				<h3>{title}</h3>
			</div>
			<p class="dialog-message">{message}</p>
			<div class="dialog-actions">
				<button class="dialog-btn cancel" onclick={onCancel} disabled={pending}>{cancelText}</button>
				<button class="dialog-btn confirm" onclick={handleConfirm} disabled={pending}>{pending ? 'Please wait...' : confirmText}</button>
			</div>
		</div>
	</div>
{/if}

<style>
	.dialog-overlay {
		position: fixed;
		inset: 0;
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 1rem;
		z-index: 1300;
		background: var(--theme-modal-backdrop);
		backdrop-filter: var(--theme-modal-backdrop-blur);
		-webkit-backdrop-filter: var(--theme-modal-backdrop-blur);
	}

	.dialog-card {
		width: min(520px, 100%);
		border-radius: 16px;
		border: 1px solid rgba(17, 24, 39, 0.16);
		background: rgba(245, 249, 255, 0.97);
		box-shadow: 0 24px 54px rgba(15, 23, 42, 0.24);
		padding: 1rem;
		display: flex;
		flex-direction: column;
		gap: 0.8rem;
	}

	.dialog-card.warning {
		border-color: rgba(245, 158, 11, 0.36);
	}

	.dialog-header h3 {
		margin: 0;
		font-size: 1.45rem;
		line-height: 1.1;
		color: #0f172a;
	}

	.dialog-message {
		margin: 0;
		font-size: 1rem;
		line-height: 1.55;
		color: #1f2937;
	}

	.dialog-actions {
		display: flex;
		justify-content: flex-end;
		gap: 0.6rem;
	}

	.dialog-btn {
		min-width: 132px;
		height: 44px;
		padding: 0.7rem 1rem;
		border-radius: 999px;
		border: 1px solid transparent;
		font: inherit;
		font-weight: 800;
		cursor: pointer;
	}

	.dialog-btn.cancel {
		background: rgba(15, 23, 42, 0.08);
		border-color: rgba(15, 23, 42, 0.2);
		color: #0f172a;
	}

	.dialog-btn.confirm {
		background: rgba(var(--theme-primary-rgb), 0.24);
		border-color: rgba(var(--theme-primary-rgb), 0.5);
		color: #0f172a;
	}

	.dialog-btn:disabled {
		opacity: 0.7;
		cursor: not-allowed;
	}

</style>
