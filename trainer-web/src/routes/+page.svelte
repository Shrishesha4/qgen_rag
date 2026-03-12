<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { session } from '$lib/session';
	import GlassCard from '$lib/components/GlassCard.svelte';
	import IconBadge from '$lib/components/IconBadge.svelte';
	import ThemePicker from '$lib/components/ThemePicker.svelte';

	onMount(() => {
		const unsub = session.subscribe((s) => {
			if (s) {
				goto(s.user.role === 'vetter' ? '/vetter/dashboard' : '/teacher/dashboard');
			}
		});
		return unsub;
	});
</script>

<div class="landing">
	<div class="theme-corner">
		<ThemePicker />
	</div>

	<div class="hero">
		<IconBadge emoji="🧠" size="lg" />
		<h1 class="hero-title">QGen <span class="accent">Trainer</span></h1>
		<p class="hero-sub">
			Self-correcting AI for educational content — powered by human feedback.
		</p>
	</div>

	<div class="cards">
		<GlassCard href="/teacher/login" padding="2rem 1.5rem">
			<div class="role-inner">
				<IconBadge emoji="📝" />
				<h2 class="card-title">Teacher</h2>
				<p class="card-desc">
					Generate high-quality questions from your course materials with AI assistance.
				</p>
				<span class="card-cta">Sign in as Teacher →</span>
			</div>
		</GlassCard>

		<GlassCard href="/vetter/login" padding="2rem 1.5rem">
			<div class="role-inner">
				<IconBadge emoji="🔍" />
				<h2 class="card-title">Vetter</h2>
				<p class="card-desc">
					Review, approve, and improve AI-generated questions to train the model.
				</p>
				<span class="card-cta">Sign in as Vetter →</span>
			</div>
		</GlassCard>
	</div>

	<p class="footer-note">
		Every review you make teaches the AI to generate better questions next time.
	</p>
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

	.theme-corner {
		position: fixed;
		top: 1rem;
		right: 1rem;
		z-index: 100;
	}

	.hero {
		text-align: center;
		max-width: 36rem;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.75rem;
	}

	.hero-title {
		font-size: 3rem;
		font-weight: 800;
		letter-spacing: -0.02em;
		margin: 0;
		color: var(--theme-text);
	}

	.accent {
		color: var(--theme-primary);
	}

	.hero-sub {
		font-size: 1.1rem;
		color: var(--theme-text-muted);
		margin: 0;
		line-height: 1.6;
	}

	.cards {
		display: grid;
		grid-template-columns: 1fr;
		gap: 1rem;
		width: 100%;
		max-width: 42rem;
	}

	@media (min-width: 640px) {
		.cards {
			grid-template-columns: 1fr 1fr;
		}
	}

	.role-inner {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.75rem;
		text-align: center;
	}

	.card-title {
		font-size: 1.4rem;
		font-weight: 700;
		margin: 0;
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

	.footer-note {
		font-size: 0.85rem;
		color: var(--theme-text-muted);
		text-align: center;
		max-width: 28rem;
		line-height: 1.5;
	}
</style>
