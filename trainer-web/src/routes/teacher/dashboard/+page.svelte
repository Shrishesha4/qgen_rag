<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { session, currentUser } from '$lib/session';
	import GlassCard from '$lib/components/GlassCard.svelte';
	import IconBadge from '$lib/components/IconBadge.svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';

	onMount(() => {
		const unsub = session.subscribe((s) => {
			if (!s || s.user.role !== 'teacher') {
				goto('/teacher/login');
			}
		});
		return unsub;
	});
</script>

<svelte:head>
	<title>Home — QGen Trainer</title>
</svelte:head>

<PageHeader title="Home" />

<div class="home">
	<!-- Hero -->
	<div class="hero">
		<IconBadge emoji="🧠" size="lg" />
		<h1 class="hero-title">AI Training</h1>
		<p class="hero-sub">Select a mode to begin</p>
	</div>

	<!-- Mode Cards -->
	<div class="mode-cards">
		<GlassCard href="/teacher/train" padding="1.75rem">
			<div class="mode-row">
				<IconBadge emoji="📚" />
				<div class="mode-info">
					<h2 class="mode-title">Train Topic</h2>
					<p class="mode-desc">Create new or continue with existing topics</p>
				</div>
				<svg class="mode-arrow" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
					<polyline points="9 18 15 12 9 6"></polyline>
				</svg>
			</div>
		</GlassCard>

		<GlassCard href="/teacher/verify" padding="1.75rem" active>
			<div class="mode-row">
				<IconBadge emoji="🔍" />
				<div class="mode-info">
					<h2 class="mode-title">Verifier Mode</h2>
					<p class="mode-desc">Review questions one-by-one with voice comments</p>
				</div>
				<svg class="mode-arrow" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
					<polyline points="9 18 15 12 9 6"></polyline>
				</svg>
			</div>
		</GlassCard>
	</div>

	<!-- Stats (optional future) -->
	{#if $currentUser}
		<p class="welcome-text">
			Welcome back, {$currentUser.full_name || $currentUser.username}
		</p>
	{/if}
</div>

<style>
	.home {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		min-height: 100vh;
		padding: 2rem 1.5rem;
		gap: 2rem;
	}

	.hero {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.75rem;
		text-align: center;
	}

	.hero-title {
		font-size: 2.25rem;
		font-weight: 800;
		margin: 0;
		letter-spacing: -0.02em;
		color: var(--theme-text);
	}

	.hero-sub {
		font-size: 1.05rem;
		color: var(--theme-text-muted);
		margin: 0;
	}

	.mode-cards {
		display: flex;
		flex-direction: column;
		gap: 1rem;
		width: 100%;
		max-width: 480px;
	}

	.mode-row {
		display: flex;
		align-items: center;
		gap: 1rem;
	}

	.mode-info {
		flex: 1;
	}

	.mode-title {
		font-size: 1.1rem;
		font-weight: 700;
		margin: 0 0 0.25rem;
		color: var(--theme-text);
	}

	.mode-desc {
		font-size: 0.85rem;
		color: var(--theme-text-muted);
		margin: 0;
		line-height: 1.4;
	}

	.mode-arrow {
		opacity: 0.4;
		flex-shrink: 0;
	}

	.welcome-text {
		font-size: 0.85rem;
		color: var(--theme-text-muted);
		text-align: center;
		margin: 0;
	}

	@media (max-width: 768px) {
		.home {
			padding-top: 1rem;
			min-height: calc(100vh - 60px);
		}

		.hero-title {
			font-size: 1.75rem;
		}
	}
</style>
