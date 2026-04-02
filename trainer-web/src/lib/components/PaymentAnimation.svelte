<script lang="ts">
	import { Check, CreditCard } from 'lucide-svelte';

	let {
		onComplete,
	}: {
		onComplete: () => void;
	} = $props();

	let phase = $state<'processing' | 'success'>('processing');

	$effect(() => {
		const timer1 = setTimeout(() => {
			phase = 'success';
		}, 1800);

		const timer2 = setTimeout(() => {
			onComplete();
		}, 3000);

		return () => {
			clearTimeout(timer1);
			clearTimeout(timer2);
		};
	});
</script>

<div class="payment-overlay">
	<div class="payment-card">
		{#if phase === 'processing'}
			<div class="processing-animation">
				<div class="pulse-ring"></div>
				<CreditCard class="h-10 w-10 card-icon" />
			</div>
			<p class="payment-text">Securing your enrollment…</p>
		{:else}
			<div class="success-animation">
				<div class="confetti-burst"></div>
				<div class="check-circle">
					<Check class="h-8 w-8" />
				</div>
			</div>
			<p class="payment-text success">You're enrolled!</p>
		{/if}
	</div>
</div>

<style>
	.payment-overlay {
		position: fixed;
		inset: 0;
		z-index: 1000;
		display: grid;
		place-items: center;
		background: rgba(0, 0, 0, 0.6);
		backdrop-filter: blur(8px);
		animation: fadeIn 0.2s ease-out;
	}

	@keyframes fadeIn {
		from { opacity: 0; }
		to { opacity: 1; }
	}

	.payment-card {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 1.5rem;
		padding: 3rem;
		border-radius: 24px;
		background: color-mix(in srgb, var(--theme-nav-glass) 95%, transparent);
		border: 1px solid var(--theme-glass-border);
		box-shadow: 0 24px 64px rgba(0, 0, 0, 0.25);
		min-width: 280px;
	}

	.processing-animation {
		position: relative;
		display: grid;
		place-items: center;
		width: 80px;
		height: 80px;
	}

	.pulse-ring {
		position: absolute;
		inset: 0;
		border-radius: 50%;
		border: 3px solid rgba(var(--theme-primary-rgb), 0.3);
		animation: pulse 1.2s ease-in-out infinite;
	}

	@keyframes pulse {
		0%, 100% { transform: scale(0.85); opacity: 1; }
		50% { transform: scale(1.15); opacity: 0.4; }
	}

	.processing-animation :global(.card-icon) {
		color: rgba(var(--theme-primary-rgb), 0.8);
		animation: cardFloat 1.5s ease-in-out infinite;
	}

	@keyframes cardFloat {
		0%, 100% { transform: translateY(0); }
		50% { transform: translateY(-6px); }
	}

	.payment-text {
		font-size: 1rem;
		font-weight: 700;
		color: var(--theme-text-secondary);
		margin: 0;
	}

	.payment-text.success {
		color: rgb(34, 197, 94);
		font-size: 1.15rem;
	}

	.success-animation {
		position: relative;
		display: grid;
		place-items: center;
	}

	.check-circle {
		width: 72px;
		height: 72px;
		border-radius: 50%;
		background: rgba(34, 197, 94, 0.15);
		border: 2px solid rgb(34, 197, 94);
		display: grid;
		place-items: center;
		color: rgb(34, 197, 94);
		animation: popIn 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
	}

	@keyframes popIn {
		from { transform: scale(0); }
		to { transform: scale(1); }
	}

	.confetti-burst {
		position: absolute;
		width: 120px;
		height: 120px;
		border-radius: 50%;
		background: radial-gradient(
			circle,
			rgba(34, 197, 94, 0.2) 0%,
			rgba(168, 85, 247, 0.1) 40%,
			transparent 70%
		);
		animation: burstOut 0.8s ease-out forwards;
	}

	@keyframes burstOut {
		from { transform: scale(0.5); opacity: 1; }
		to { transform: scale(2.5); opacity: 0; }
	}
</style>
