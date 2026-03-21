<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { session } from '$lib/session';

	onMount(() => {
		const unsub = session.subscribe((s) => {
			if (s) {
				goto(s.user.role === 'admin' ? '/admin/dashboard' : s.user.role === 'vetter' ? '/vetter/dashboard' : '/teacher/train');
			}
		});
		return unsub;
	});
</script>

<div class="landing">
	<div class="hero animate-fade-in">
		<div class="hero-icon">
			<svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
				<path d="M12 2a7.5 7.5 0 0 0-5.5 12.5l.5.5V20h10v-5l.5-.5A7.5 7.5 0 0 0 12 2z"></path>
				<path d="M9 22h6"></path>
			</svg>
		</div>
		<h1 class="hero-title font-serif">VQuest</h1>
		<p class="hero-sub">
			Self-correcting AI for educational content — powered by human feedback.
		</p>
	</div>

	<div class="cards animate-slide-up">
		<a href="/teacher/login" class="role-card glass-panel">
			<div class="role-icon teacher-icon">
				<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
					<path d="M12 20h9"></path>
					<path d="M16.5 3.5a 2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"></path>
				</svg>
			</div>
			<h2 class="card-title">Teacher</h2>
			<p class="card-desc">
				Generate high-quality questions from your course materials with AI assistance.
			</p>
			<span class="card-cta">Sign in as Teacher →</span>
		</a>

		<a href="/vetter/login" class="role-card glass-panel">
			<div class="role-icon vetter-icon">
				<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
					<circle cx="11" cy="11" r="8"></circle>
					<path d="m21 21-4.3-4.3"></path>
				</svg>
			</div>
			<h2 class="card-title">Vetter</h2>
			<p class="card-desc">
				Review, approve, and improve AI-generated questions to train the model.
			</p>
			<span class="card-cta">Sign in as Vetter →</span>
		</a>

		<!-- <a href="/admin/login" class="role-card glass-panel">
			<div class="role-icon admin-icon">
				<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
					<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
				</svg>
			</div>
			<h2 class="card-title">Admin</h2>
			<p class="card-desc">
				Monitor platform stats, users, and vetting activity at a glance.
			</p>
			<span class="card-cta">Sign in as Admin →</span>
		</a> -->
	</div>
</div>

<style>
	.landing {
		min-height: 100vh;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		padding: 2rem 1rem;
		gap: 2.5rem;
	}

	.hero {
		text-align: center;
		max-width: 36rem;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.75rem;
	}

	.hero-icon {
		width: 72px;
		height: 72px;
		border-radius: 50%;
		background: rgba(255, 255, 255, 0.1);
		border: 1px solid rgba(255, 255, 255, 0.15);
		display: flex;
		align-items: center;
		justify-content: center;
		color: var(--theme-primary);
		margin-bottom: 0.5rem;
	}

	.hero-title {
		font-size: 3rem;
		font-weight: 800;
		letter-spacing: -0.02em;
		margin: 0;
		color: var(--theme-text);
	}

	.hero-sub {
		font-size: 1.1rem;
		color: var(--theme-text-muted);
		margin: 0;
		line-height: 1.6;
		max-width: 28rem;
	}

	.cards {
		display: flex;
		gap: 1rem;
		width: 100%;
		max-width: 56rem;
		flex-direction: column;
	}

	@media (min-width: 640px) {
		.cards {
			flex-direction: row;
		}
	}

	.role-card {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.75rem;
		text-align: center;
		padding: 2rem 1.5rem;
		text-decoration: none;
		color: inherit;
		border-radius: 1.5rem;
		transition: all 0.3s ease;
		cursor: pointer;
		/* Enhanced blur effect */
		backdrop-filter: blur(10px) saturate(150%) brightness(1.02);
		-webkit-backdrop-filter: blur(10px) saturate(150%) brightness(1.02);
		background: linear-gradient(
			145deg,
			rgba(255,255,255,0.1) 0%,
			rgba(255,255,255,0.05) 50%,
			rgba(255,255,255,0.08) 100%
		);
		box-shadow:
			0 8px 40px rgba(0, 0, 0, 0.25),
			inset 0 1px 1px rgba(255, 255, 255, 0.25),
			inset 0 -1px 1px rgba(255, 255, 255, 0.08),
			0 0 0 1px rgba(255, 255, 255, 0.12);
	}

	.role-card:hover {
		transform: translateY(-4px);
		background: linear-gradient(
			145deg,
			rgba(255,255,255,0.18) 0%,
			rgba(255,255,255,0.12) 50%,
			rgba(255,255,255,0.15) 100%
		);
		box-shadow: 
			0 12px 40px rgba(0, 0, 0, 0.3),
			inset 0 1px 1px rgba(255, 255, 255, 0.3),
			inset 0 -1px 1px rgba(255, 255, 255, 0.12),
			0 0 0 1px rgba(255, 255, 255, 0.18);
		/* Maintain blur on hover */
		backdrop-filter: blur(10px) saturate(150%) brightness(1.02);
		-webkit-backdrop-filter: blur(10px) saturate(150%) brightness(1.02);
	}

	.role-icon {
		width: 56px;
		height: 56px;
		border-radius: 50%;
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.teacher-icon {
		background: rgba(59, 130, 246, 0.2);
		color: #93c5fd;
		border: 1px solid rgba(59, 130, 246, 0.3);
	}

	.vetter-icon {
		background: rgba(16, 185, 129, 0.2);
		color: #6ee7b7;
		border: 1px solid rgba(16, 185, 129, 0.3);
	}

	/* .admin-icon {
		background: rgba(245, 158, 11, 0.2);
		color: #fbbf24;
		border: 1px solid rgba(245, 158, 11, 0.3);
	} */

	.card-title {
		font-size: 1.4rem;
		font-weight: 700;
		margin: 0;
		color: var(--theme-text);
	}

	.card-desc {
		font-size: 0.92rem;
		color: var(--theme-text-muted);
		margin: 0;
		line-height: 1.5;
	}

	.card-cta {
		font-size: 0.9rem;
		font-weight: 600;
		color: var(--theme-primary);
		margin-top: 0.25rem;
	}

	@media (max-width: 768px) {
		.landing {
			padding: 1.5rem 1rem;
			gap: 2rem;
		}

		.hero-icon {
			width: 64px;
			height: 64px;
		}

		.hero-icon svg {
			width: 32px;
			height: 32px;
		}

		.hero-title {
			font-size: 2.5rem;
		}

		.hero-sub {
			font-size: 1rem;
		}

		.role-card {
			padding: 1.5rem 1.25rem;
		}

		.role-icon {
			width: 50px;
			height: 50px;
		}

		.role-icon svg {
			width: 22px;
			height: 22px;
		}

		.card-title {
			font-size: 1.25rem;
		}

		.card-desc {
			font-size: 0.88rem;
		}

		.card-cta {
			font-size: 0.85rem;
		}
	}

	@media (max-width: 480px) {
		.landing {
			padding: 1.25rem 0.75rem;
			gap: 1.5rem;
		}

		.hero {
			gap: 0.5rem;
		}

		.hero-icon {
			width: 52px;
			height: 52px;
			margin-bottom: 0.25rem;
		}

		.hero-icon svg {
			width: 26px;
			height: 26px;
		}

		.hero-title {
			font-size: 2rem;
		}

		.hero-sub {
			font-size: 0.92rem;
		}

		.cards {
			gap: 0.75rem;
		}

		.role-card {
			padding: 1.25rem 1rem;
			border-radius: 1.25rem;
			gap: 0.5rem;
		}

		.role-icon {
			width: 46px;
			height: 46px;
		}

		.role-icon svg {
			width: 20px;
			height: 20px;
		}

		.card-title {
			font-size: 1.15rem;
		}

		.card-desc {
			font-size: 0.82rem;
		}

		.card-cta {
			font-size: 0.8rem;
		}
	}
</style>
