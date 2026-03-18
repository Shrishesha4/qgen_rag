<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { session, currentUser } from '$lib/session';
	import ThemeSelector from '$lib/components/ThemeSelector.svelte';

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
	<title>Home — VQuest Trainer</title>
</svelte:head>

<ThemeSelector />

<div class="home">
	<div class="dashboard-topbar animate-fade-in">
		<button class="profile-shortcut glass-card subject-card" onclick={() => goto('/teacher/profile')} aria-label="Open profile">
			{#if $currentUser}
				<span class="profile-avatar">{($currentUser.full_name || $currentUser.username || 'T').slice(0, 1).toUpperCase()}</span>
			{:else}
				<span class="profile-avatar">T</span>
			{/if}
		</button>
	</div>

	<!-- Hero -->
	<div class="hero animate-fade-in">
		<div class="hero-icon">
			<svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
				<path d="M12 2a7.5 7.5 0 0 0-5.5 12.5l.5.5V20h10v-5l.5-.5A7.5 7.5 0 0 0 12 2z"></path>
				<path d="M9 22h6"></path>
			</svg>
		</div>
		<h1 class="hero-title font-serif">VQuest</h1>
		<p class="hero-sub">Select a mode to begin</p>
	</div>

	<!-- Mode Cards -->
	<div class="mode-cards animate-slide-up">
		<a href="/teacher/train" class="mode-card glass-panel">
			<div class="mode-icon blue">
				<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
					<path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1 0-5H20"></path>
				</svg>
			</div>
			<div class="mode-info">
				<h2 class="mode-title">Train Topic</h2>
				<p class="mode-desc">Create new or continue with existing topics</p>
			</div>
			<svg class="mode-arrow" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
				<polyline points="9 18 15 12 9 6"></polyline>
			</svg>
		</a>

		<a href="/teacher/verify" class="mode-card glass-panel">
			<div class="mode-icon emerald">
				<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
					<circle cx="11" cy="11" r="8"></circle>
					<path d="m21 21-4.3-4.3"></path>
				</svg>
			</div>
			<div class="mode-info">
				<h2 class="mode-title">Verifier Mode</h2>
				<p class="mode-desc">Review questions one-by-one with voice comments</p>
			</div>
			<svg class="mode-arrow" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
				<polyline points="9 18 15 12 9 6"></polyline>
			</svg>
		</a>
	</div>

	{#if $currentUser}
		<h1 class="hero-title font-serif animate-fade-in" style="animation-delay: 0.3s; font-size: 1.25rem; font-style: italic;">Welcome back, {$currentUser.full_name || $currentUser.username}</h1>
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
		position: relative;
	}

	.dashboard-topbar {
		position: absolute;
		top: max(1.25rem, env(safe-area-inset-top));
		right: 1.5rem;
		z-index: 10;
	}

	.profile-shortcut {
		width: 52px;
		height: 52px;
		border: none;
		border-radius: 999px;
		padding: 0;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		background: transparent;
		cursor: pointer;
		color: var(--theme-text);
		box-shadow: 0 14px 32px rgba(0, 0, 0, 0.18);
	}

	.profile-avatar {
		width: 38px;
		height: 38px;
		border-radius: 999px;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		background: rgba(var(--theme-primary-rgb), 0.24);
		border: 1px solid rgba(255, 255, 255, 0.2);
		font-size: 0.95rem;
		font-weight: 800;
		letter-spacing: 0.08em;
	}

	.hero {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.75rem;
		text-align: center;
	}

	.hero-icon {
		width: 64px;
		height: 64px;
		border-radius: 50%;
		background: rgba(255, 255, 255, 0.1);
		border: 1px solid rgba(255, 255, 255, 0.15);
		display: flex;
		align-items: center;
		justify-content: center;
		color: var(--theme-primary);
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

	.mode-card {
		display: flex;
		align-items: center;
		gap: 1rem;
		padding: 1.5rem;
		border-radius: 1.25rem;
		text-decoration: none;
		color: inherit;
		transition: all 0.3s ease;
		cursor: pointer;
		/* Enhanced blur effect - force override */
		backdrop-filter: blur(50px) saturate(200%) brightness(1.05) !important;
		-webkit-backdrop-filter: blur(50px) saturate(200%) brightness(1.05) !important;
		background: linear-gradient(
			145deg,
			rgba(255,255,255,0.03) 0%,
			rgba(255,255,255,0.02) 50%,
			rgba(255,255,255,0.025) 100%
		) !important;
		box-shadow:
			0 8px 40px rgba(0, 0, 0, 0.25),
			inset 0 1px 1px rgba(255, 255, 255, 0.25),
			inset 0 -1px 1px rgba(255, 255, 255, 0.08),
			0 0 0 1px rgba(255, 255, 255, 0.12) !important;
		/* Force hardware acceleration for Chromium */
		transform: translateZ(0) scale(1);
		backface-visibility: hidden;
		perspective: 1000px;
		-webkit-font-smoothing: subpixel-antialiased;
	}

	.mode-card:hover {
		background: linear-gradient(
			145deg,
			rgba(255,255,255,0.05) 0%,
			rgba(255,255,255,0.04) 50%,
			rgba(255,255,255,0.045) 100%
		) !important;
		transform: translateY(-2px) translateZ(0);
		box-shadow: 
			0 12px 40px rgba(0, 0, 0, 0.3),
			inset 0 1px 1px rgba(255, 255, 255, 0.3),
			inset 0 -1px 1px rgba(255, 255, 255, 0.12),
			0 0 0 1px rgba(255, 255, 255, 0.18) !important;
		/* Maintain blur on hover - force override */
		backdrop-filter: blur(50px) saturate(200%) brightness(1.05) !important;
		-webkit-backdrop-filter: blur(50px) saturate(200%) brightness(1.05) !important;
	}

	.mode-icon {
		width: 48px;
		height: 48px;
		border-radius: 50%;
		display: flex;
		align-items: center;
		justify-content: center;
		flex-shrink: 0;
	}

	.mode-icon.blue {
		background: rgba(59, 130, 246, 0.2);
		color: #93c5fd;
		border: 1px solid rgba(59, 130, 246, 0.3);
	}

	.mode-icon.emerald {
		background: rgba(16, 185, 129, 0.2);
		color: #6ee7b7;
		border: 1px solid rgba(16, 185, 129, 0.3);
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
		color: var(--theme-text);
	}

	/* .welcome-text {
		font-size: 0.85rem;
		color: var(--theme-text-muted);
		text-align: center;
		margin: 0;
	} */

	@media (max-width: 768px) {
		.home {
			padding: 4.5rem 1rem 2rem;
			min-height: 100vh;
			gap: 1.5rem;
		}

		.dashboard-topbar {
			right: 1rem;
		}

		.profile-shortcut {
			width: 46px;
			height: 46px;
		}

		.profile-avatar {
			width: 34px;
			height: 34px;
			font-size: 0.88rem;
		}

		.hero {
			gap: 0.6rem;
		}

		.hero-icon {
			width: 56px;
			height: 56px;
		}

		.hero-icon svg {
			width: 28px;
			height: 28px;
		}

		.hero-title {
			font-size: 1.85rem;
		}

		.hero-sub {
			font-size: 0.95rem;
		}

		.mode-cards {
			max-width: 100%;
			gap: 0.85rem;
		}

		.mode-card {
			padding: 1.25rem;
			gap: 0.85rem;
		}

		.mode-icon {
			width: 44px;
			height: 44px;
		}

		.mode-title {
			font-size: 1rem;
		}

		.mode-desc {
			font-size: 0.82rem;
		}
	}

	@media (max-width: 480px) {
		.home {
			padding: 4rem 0.75rem 1.5rem;
			gap: 1.25rem;
		}

		.dashboard-topbar {
			top: max(1rem, env(safe-area-inset-top));
			right: 0.75rem;
		}

		.profile-shortcut {
			width: 42px;
			height: 42px;
		}

		.profile-avatar {
			width: 30px;
			height: 30px;
			font-size: 0.82rem;
		}

		.hero {
			gap: 0.45rem;
		}

		.hero-icon {
			width: 50px;
			height: 50px;
		}

		.hero-icon svg {
			width: 24px;
			height: 24px;
		}

		.hero-title {
			font-size: 1.6rem;
		}

		.hero-sub {
			font-size: 0.88rem;
		}

		.mode-cards {
			gap: 0.7rem;
		}

		.mode-card {
			padding: 1rem;
			border-radius: 1rem;
			gap: 0.75rem;
		}

		.mode-icon {
			width: 40px;
			height: 40px;
		}

		.mode-icon svg {
			width: 18px;
			height: 18px;
		}

		.mode-title {
			font-size: 0.95rem;
			margin-bottom: 0.15rem;
		}

		.mode-desc {
			font-size: 0.78rem;
		}

		/* .welcome-text {
			font-size: 0.78rem;
		} */
	}
</style>
