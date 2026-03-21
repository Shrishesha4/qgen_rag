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
	<section class="landing-shell animate-fade-in">
		<div class="hero">
			<div class="hero-icon">
				<svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
					<path d="M12 2a7.5 7.5 0 0 0-5.5 12.5l.5.5V20h10v-5l.5-.5A7.5 7.5 0 0 0 12 2z"></path>
					<path d="M9 22h6"></path>
				</svg>
			</div>
			<p class="hero-kicker">Adaptive Content Studio</p>
			<h1 class="hero-title font-serif">VQuest</h1>
			<p class="hero-sub">
				Self-correcting AI for educational content, refined by teacher and vetter feedback loops.
			</p>
		</div>

		<div class="cards animate-slide-up">
			<a href="/teacher/login" class="role-card glass-panel teacher-card">
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

			<a href="/vetter/login" class="role-card glass-panel vetter-card">
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
	</section>
</div>

<style>
	.landing {
		min-height: 100vh;
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 1.5rem 1rem;
	}

	.landing-shell {
		width: min(980px, 100%);
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}

	.hero {
		text-align: center;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 0.75rem;
		padding: clamp(1.1rem, 2.5vw, 1.7rem);
		border-radius: 0;
		background: transparent;
		border: none;
		box-shadow: none;
		backdrop-filter: none;
		-webkit-backdrop-filter: none;
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
		margin-bottom: 0.3rem;
	}

	.hero-kicker {
		margin: 0;
		font-size: 0.76rem;
		font-weight: 700;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: var(--theme-primary);
	}

	.hero-title {
		font-size: clamp(2.4rem, 5vw, 3.4rem);
		font-weight: 800;
		letter-spacing: -0.02em;
		margin: 0;
		color: var(--theme-text-primary);
	}

	.hero-sub {
		font-size: 1rem;
		color: var(--theme-text-secondary);
		margin: 0;
		line-height: 1.55;
		max-width: 48ch;
	}

	.cards {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 1rem;
		align-items: stretch;
	}

	.role-card {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		justify-content: space-between;
		gap: 0.75rem;
		text-align: left;
		padding: 2rem 1.5rem;
		text-decoration: none;
		color: inherit;
		border-radius: 1.5rem;
		transition: all 0.3s ease;
		cursor: pointer;
		min-height: 260px;
		width: 100%;
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

	.teacher-card {
		background: linear-gradient(160deg, rgba(var(--theme-primary-rgb), 0.16), rgba(255, 255, 255, 0.76));
	}

	.vetter-card {
		background: linear-gradient(160deg, rgba(var(--theme-primary-rgb), 0.1), rgba(255, 255, 255, 0.76));
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
		background: rgba(var(--theme-primary-rgb), 0.2);
		color: var(--theme-primary);
		border: 1px solid rgba(var(--theme-primary-rgb), 0.42);
	}

	.vetter-icon {
		background: rgba(var(--theme-primary-rgb), 0.14);
		color: var(--theme-primary-hover);
		border: 1px solid rgba(var(--theme-primary-rgb), 0.35);
	}

	/* .admin-icon {
		background: rgba(245, 158, 11, 0.2);
		color: #fbbf24;
		border: 1px solid rgba(245, 158, 11, 0.3);
	} */

	.card-title {
		font-size: 1.35rem;
		font-weight: 700;
		margin: 0;
		color: var(--theme-text-primary);
	}

	.card-desc {
		font-size: 0.9rem;
		color: var(--theme-text-secondary);
		margin: 0;
		line-height: 1.5;
	}

	.card-cta {
		font-size: 0.9rem;
		font-weight: 700;
		color: var(--theme-primary);
		margin-top: 0.25rem;
	}

	@media (max-width: 768px) {
		.landing {
			padding: 1rem 0.85rem;
		}

		.hero {
			text-align: center;
			align-items: center;
			padding: 0.35rem 0.15rem;
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
			font-size: 0.95rem;
			max-width: 100%;
		}

		.role-card {
			padding: 1.2rem 1rem;
			min-height: 220px;
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

		.cards {
			grid-template-columns: 1fr;
		}
	}

	@media (max-width: 480px) {
		.landing {
			padding: 0.85rem 0.65rem;
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
