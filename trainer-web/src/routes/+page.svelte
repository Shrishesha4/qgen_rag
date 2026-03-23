<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import { login } from '$lib/api/auth';
	import { session } from '$lib/session';

	let introReady = $state(false);
	let email = $state('');
	let password = $state('');
	let signingIn = $state(false);
	let signInError = $state('');

	function redirectByRole(role: string) {
		switch (role) {
			case 'admin':
				goto('/admin/dashboard');
				break;
			case 'vetter':
				goto('/vetter/dashboard');
				break;
			case 'teacher':
			default:
				goto('/teacher/subjects');
				break;
		}
	}

	async function handleLandingSignIn() {
		signInError = '';
		signingIn = true;
		try {
			const response = await login({ email, password });
			session.refresh();
			redirectByRole(response.user.role);
		} catch (e: unknown) {
			signInError = e instanceof Error ? e.message : 'Sign in failed';
		} finally {
			signingIn = false;
		}
	}

	onMount(() => {
		const rafId = requestAnimationFrame(() => {
			introReady = true;
		});

		return () => {
			cancelAnimationFrame(rafId);
		};
	});
</script>

<div class="landing">
	<section class="landing-shell" class:intro-ready={introReady}>
		<div class="hero">
			<div class="hero-icon">
				<img src="/logo.png" alt="VQuest logo" class="hero-logo-img" loading="eager" decoding="async" />
			</div>
			<h1 class="hero-title font-serif">VQuest</h1>
			<p class="hero-sub">
				Self-correcting AI for educational content, refined by teacher and vetter feedback loops.
			</p>
		</div>

		<div class="signin-wrap">
			<form class="signin-form" onsubmit={(e) => { e.preventDefault(); handleLandingSignIn(); }}>
				{#if signInError}
					<p class="signin-error" role="alert">{signInError}</p>
				{/if}
				<label class="signin-field">
					<span class="signin-label">Email</span>
					<input
						type="email"
						class="signin-input"
						bind:value={email}
						placeholder="your email address"
						autocomplete="email"
						required
					/>
				</label>
				<label class="signin-field">
					<span class="signin-label">Password</span>
					<input
						type="password"
						class="signin-input"
						bind:value={password}
						placeholder="••••••••"
						autocomplete="current-password"
						required
					/>
				</label>
				<button type="submit" class="signin-submit" disabled={signingIn}>
					{signingIn ? 'Signing In...' : 'Sign In'}
				</button>
			</form>
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
		min-height: clamp(500px, 64vh, 640px);
		display: flex;
		flex-direction: column;
		gap: 1rem;
		position: relative;
		isolation: isolate;
		padding: clamp(0.7rem, 1.5vw, 1rem);
		border-radius: 1.7rem;
		overflow: hidden;
	}

	.landing-shell::before,
	.landing-shell::after {
		content: '';
		position: absolute;
		pointer-events: none;
	}

	/* Phase 1: Painterly mask-based white reveal */
	.landing-shell::before {
		inset: -12% -10%;
		z-index: 1;
		background:
			radial-gradient(120% 90% at 16% 32%, rgba(255, 255, 255, 0.98) 0%, rgba(255, 255, 255, 0.94) 40%, rgba(255, 255, 255, 0.84) 72%, rgba(255, 255, 255, 0.35) 100%),
			linear-gradient(115deg, rgba(255, 255, 255, 1) 0%, rgba(255, 255, 255, 0.92) 55%, rgba(255, 255, 255, 0.5) 100%);
		transform: translateX(-118%) translateY(-3%) rotate(-4.5deg);
		opacity: 0;
		filter: blur(1px);
		mask-image:
			radial-gradient(70% 96% at 8% 50%, #000 42%, transparent 84%),
			radial-gradient(56% 86% at 32% 46%, #000 50%, transparent 82%),
			radial-gradient(68% 88% at 58% 58%, #000 46%, transparent 83%),
			radial-gradient(72% 98% at 90% 48%, #000 45%, transparent 82%),
			linear-gradient(90deg, transparent 0%, #000 18%, #000 84%, transparent 100%);
		-webkit-mask-image:
			radial-gradient(70% 96% at 8% 50%, #000 42%, transparent 84%),
			radial-gradient(56% 86% at 32% 46%, #000 50%, transparent 82%),
			radial-gradient(68% 88% at 58% 58%, #000 46%, transparent 83%),
			radial-gradient(72% 98% at 90% 48%, #000 45%, transparent 82%),
			linear-gradient(90deg, transparent 0%, #000 18%, #000 84%, transparent 100%);
		mask-repeat: no-repeat;
		-webkit-mask-repeat: no-repeat;
	}

	/* Phase 2: Morph target - glass panel that settles and remains */
	.landing-shell::after {
		inset: 0;
		z-index: 1;
		opacity: 0;
		border-radius: inherit;
		background: linear-gradient(
			155deg,
			rgba(255, 255, 255, 0.48) 0%,
			rgba(255, 255, 255, 0.34) 42%,
			rgba(255, 255, 255, 0.22) 100%
		);
		border: 1px solid rgba(255, 255, 255, 0.56);
		box-shadow:
			0 16px 42px rgba(0, 0, 0, 0.22),
			inset 0 1px 0 rgba(255, 255, 255, 0.68),
			inset 0 -1px 0 rgba(255, 255, 255, 0.18);
		backdrop-filter: blur(16px) saturate(145%);
		-webkit-backdrop-filter: blur(16px) saturate(145%);
	}

	.landing-shell > * {
		position: relative;
		z-index: 2;
	}

	.landing-shell.intro-ready::before {
		animation: paintSweep 0.92s cubic-bezier(0.2, 0.86, 0.22, 1) both;
	}

	.landing-shell.intro-ready::after {
		animation: glassSettle 0.9s cubic-bezier(0.2, 0.7, 0.12, 1) 0.56s both;
	}

	/* Phase 3: Staggered content reveal once glass is legible */
	.hero-icon,
	.hero-title,
	.hero-sub,
	.signin-wrap {
		opacity: 0;
		transform: translateY(14px);
		filter: blur(8px);
	}

	.landing-shell.intro-ready .hero-icon {
		animation: contentFadeUp 0.55s ease 0.94s both;
	}

	.landing-shell.intro-ready .hero-title {
		animation: contentFadeUp 0.58s ease 1.12s both;
	}

	.landing-shell.intro-ready .hero-sub {
		animation: contentFadeUp 0.6s ease 1.22s both;
	}

	.landing-shell.intro-ready .signin-wrap {
		animation: contentFadeUp 0.62s ease 1.34s both;
	}

	@keyframes paintSweep {
		0% {
			opacity: 0;
			transform: translateX(-118%) translateY(-3%) rotate(-4.5deg);
			filter: blur(2px);
		}
		8% {
			opacity: 0.96;
		}
		58% {
			opacity: 0.9;
			transform: translateX(0%) translateY(0) rotate(-1.1deg);
			filter: blur(0);
		}
		100% {
			opacity: 0;
			transform: translateX(24%) translateY(0) rotate(0deg);
			filter: blur(1px);
		}
	}

	@keyframes glassSettle {
		0% {
			opacity: 0;
			transform: scale(1.02);
			filter: blur(4px);
		}
		100% {
			opacity: 1;
			transform: scale(1);
			filter: blur(0);
		}
	}

	@keyframes contentFadeUp {
		0% {
			opacity: 0;
			transform: translateY(14px);
			filter: blur(8px);
		}
		100% {
			opacity: 1;
			transform: translateY(0);
			filter: blur(0);
		}
	}

	@supports not ((mask-image: linear-gradient(#000, #000)) or (-webkit-mask-image: linear-gradient(#000, #000))) {
		.landing-shell::before {
			mask-image: none;
			-webkit-mask-image: none;
			border-radius: inherit;
		}
	}

	@media (prefers-reduced-motion: reduce) {
		.landing-shell::before,
		.landing-shell::after {
			animation: none !important;
		}

		.hero-icon,
		.hero-title,
		.hero-sub,
		.signin-wrap {
			opacity: 1;
			transform: none;
			filter: none;
			animation: none !important;
		}

		.landing-shell::after {
			opacity: 1;
		}
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
		width: auto;
		height: auto;
		display: flex;
		align-items: center;
		justify-content: center;
		background: transparent;
		border: none;
		margin-bottom: 0.3rem;
	}

	.hero-logo-img {
		width: 100px;
		height: 100px;
		object-fit: contain;
	}

	.hero-title {
		font-size: clamp(2.4rem, 5vw, 3.4rem);
		font-weight: 800;
		letter-spacing: -0.02em;
		margin: 0;
		/* color: var(--theme-text-primary); */
		color: black;
	}

	.hero-sub {
		font-size: 1.2rem;
		color: black;
		/* color: var(--theme-text-secondary); */
		margin: 0;
		line-height: 1.55;
		max-width: 48ch;
	}

	.signin-wrap {
		display: flex;
		justify-content: center;
		margin-top: 0.55rem;
	}

	.signin-form {
		width: min(360px, 94vw);
		display: flex;
		flex-direction: column;
		gap: 0.56rem;
	}

	.signin-field {
		display: flex;
		flex-direction: column;
		gap: 0.2rem;
	}

	.signin-label {
		font-size: 0.74rem;
		font-weight: 700;
		color: rgba(15, 23, 42, 0.78);
	}

	.signin-input {
		padding: 0.62rem 0.74rem;
		border-radius: 0.7rem;
		border: 1px solid rgba(255, 255, 255, 0.55);
		background: linear-gradient(
			160deg,
			rgba(255, 255, 255, 0.5) 0%,
			rgba(255, 255, 255, 0.34) 100%
		);
		color: #111827;
		font-size: 0.9rem;
		outline: none;
		backdrop-filter: blur(12px) saturate(135%);
		-webkit-backdrop-filter: blur(12px) saturate(135%);
		box-shadow:
			inset 0 1px 0 rgba(255, 255, 255, 0.65),
			inset 0 -1px 0 rgba(255, 255, 255, 0.2);
		transition: border-color 0.18s ease, box-shadow 0.18s ease, background 0.18s ease;
	}

	.signin-input::placeholder {
		color: rgba(31, 41, 55, 0.48);
	}

	.signin-input:hover {
		background: linear-gradient(
			160deg,
			rgba(255, 255, 255, 0.56) 0%,
			rgba(255, 255, 255, 0.38) 100%
		);
	}

	.signin-input:focus {
		border-color: rgba(255, 255, 255, 0.8);
		background: linear-gradient(
			160deg,
			rgba(255, 255, 255, 0.62) 0%,
			rgba(255, 255, 255, 0.44) 100%
		);
		box-shadow:
			0 0 0 3px rgba(255, 255, 255, 0.28),
			0 0 0 5px rgba(var(--theme-primary-rgb), 0.14);
	}

	.signin-submit {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		font-size: 0.98rem;
		font-weight: 700;
		color: var(--theme-primary);
		margin-top: 0.2rem;
		padding: 0.72rem 1.1rem;
		border-radius: 999px;
		border: 1px solid rgba(var(--theme-primary-rgb), 0.28);
		background: rgba(255, 255, 255, 0.3);
		cursor: pointer;
		backdrop-filter: blur(6px);
		-webkit-backdrop-filter: blur(6px);
		transition: transform 0.2s ease, background 0.2s ease;
	}

	.signin-submit:hover:enabled {
		transform: translateY(-1px);
		background: rgba(255, 255, 255, 0.38);
	}

	.signin-submit:disabled {
		opacity: 0.7;
		cursor: wait;
	}

	.signin-error {
		margin: 0;
		padding: 0.48rem 0.6rem;
		font-size: 0.78rem;
		color: #b91c1c;
		background: rgba(254, 226, 226, 0.6);
		border: 1px solid rgba(239, 68, 68, 0.24);
		border-radius: 0.62rem;
	}

	@media (max-width: 768px) {
		.landing {
			padding: 1rem 0.85rem;
		}

		.landing-shell {
			min-height: clamp(440px, 60vh, 560px);
		}

		.hero {
			text-align: center;
			align-items: center;
			padding: 0.35rem 0.15rem;
		}

		.hero-logo-img {
			width: 64px;
			height: 64px;
		}

		.hero-title {
			font-size: 2.5rem;
		}

		.hero-sub {
			font-size: 0.95rem;
			max-width: 100%;
		}

		.signin-form {
			width: min(350px, 94vw);
		}

		.signin-submit {
			font-size: 0.92rem;
			padding: 0.64rem 1.02rem;
		}
	}

	@media (max-width: 480px) {
		.landing {
			padding: 0.85rem 0.65rem;
		}

		.landing-shell {
			min-height: 420px;
		}

		.hero {
			gap: 0.5rem;
		}

		.hero-icon {
			margin-bottom: 0.25rem;
		}

		.hero-logo-img {
			width: 64px;
			height: 64px;
		}

		.hero-title {
			font-size: 2rem;
		}

		.hero-sub {
			font-size: 0.92rem;
		}

		.signin-form {
			width: min(320px, 95vw);
		}

		.signin-submit {
			font-size: 0.84rem;
			padding: 0.56rem 0.92rem;
		}
	}
</style>
