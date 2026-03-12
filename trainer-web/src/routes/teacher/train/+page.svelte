<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { session } from '$lib/session';
	import GlassCard from '$lib/components/GlassCard.svelte';
	import IconBadge from '$lib/components/IconBadge.svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';

	onMount(() => {
		const unsub = session.subscribe((s) => {
			if (!s) goto('/teacher/login');
		});
		return unsub;
	});
</script>

<svelte:head>
	<title>Train Topic — QGen Trainer</title>
</svelte:head>

<PageHeader title="Train Topic" backHref="/teacher/dashboard" />

<div class="page">
	<div class="header">
		<h1 class="title">Train Topic</h1>
		<p class="subtitle">Choose how to proceed</p>
	</div>

	<div class="cards">
		<GlassCard href="/teacher/train/new" padding="2rem">
			<div class="card-row">
				<IconBadge emoji="✨" />
				<div class="card-info">
					<h2 class="card-title">New Topic</h2>
					<p class="card-desc">Start from scratch with a new discipline, syllabus, and reference materials</p>
				</div>
				<svg class="arrow" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
					<polyline points="9 18 15 12 9 6"></polyline>
				</svg>
			</div>
		</GlassCard>

		<GlassCard href="/teacher/train/existing" padding="2rem">
			<div class="card-row">
				<IconBadge emoji="🔄" />
				<div class="card-info">
					<h2 class="card-title">Existing Topic</h2>
					<p class="card-desc">Continue training with a previously configured topic and materials</p>
				</div>
				<svg class="arrow" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
					<polyline points="9 18 15 12 9 6"></polyline>
				</svg>
			</div>
		</GlassCard>
	</div>
</div>

<style>
	.page {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		min-height: 100vh;
		padding: 2rem 1.5rem;
		gap: 2rem;
	}

	.header {
		text-align: center;
	}

	.title {
		font-size: 2rem;
		font-weight: 800;
		margin: 0 0 0.5rem;
		color: var(--theme-text);
	}

	.subtitle {
		font-size: 1rem;
		color: var(--theme-text-muted);
		margin: 0;
	}

	.cards {
		display: flex;
		flex-direction: column;
		gap: 1rem;
		width: 100%;
		max-width: 480px;
	}

	.card-row {
		display: flex;
		align-items: center;
		gap: 1rem;
	}

	.card-info {
		flex: 1;
	}

	.card-title {
		font-size: 1.1rem;
		font-weight: 700;
		margin: 0 0 0.25rem;
		color: var(--theme-text);
	}

	.card-desc {
		font-size: 0.85rem;
		color: var(--theme-text-muted);
		margin: 0;
		line-height: 1.4;
	}

	.arrow {
		opacity: 0.4;
		flex-shrink: 0;
	}

	@media (max-width: 768px) {
		.page {
			padding-top: 1rem;
			min-height: calc(100vh - 60px);
		}

		.title {
			font-size: 1.5rem;
		}
	}
</style>
