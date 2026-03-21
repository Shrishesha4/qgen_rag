<script lang="ts">
	interface Props {
		emoji: string;
		size?: 'sm' | 'md' | 'lg';
	}

	let { emoji, size = 'md' }: Props = $props();
</script>

<div class="badge badge-{size}">
	<span>{emoji}</span>
</div>

<style>
	.badge {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		border-radius: 14px;
		background: rgba(255, 255, 255, 0.1);
		backdrop-filter: blur(8px);
		-webkit-backdrop-filter: blur(8px);
		border: 0.5px solid rgba(255, 255, 255, 0.12);
		flex-shrink: 0;
	}

	.badge-sm {
		width: 36px;
		height: 36px;
		font-size: 1.1rem;
		border-radius: 10px;
	}

	.badge-md {
		width: 52px;
		height: 52px;
		font-size: 1.6rem;
		border-radius: 14px;
	}

	.badge-lg {
		width: 72px;
		height: 72px;
		font-size: 2.2rem;
		border-radius: 18px;
	}
</style>
