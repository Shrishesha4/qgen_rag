<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { session } from '$lib/session';

	onMount(() => {
		const unsub = session.subscribe((s) => {
			if (!s) goto('/teacher/login');
		});
		return unsub;
	});
</script>

<svelte:head>
	<title>Train Topic — VQuest Trainer</title>
</svelte:head>

<div class="page">
	<div class="header animate-fade-in">
		<h1 class="title font-serif">Train Topic</h1>
		<p class="subtitle">Choose how to proceed</p>
	</div>

	<div class="cards animate-slide-up">
		<a href="/teacher/train/new" class="card-link glass-panel">
			<div class="card-row">
				<div class="card-icon amber">
					<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
						<path d="M12 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
						<path d="M18.375 2.625a1 1 0 0 1 3 3l-9.013 9.014a2 2 0 0 1-.853.505l-2.873.84a.5.5 0 0 1-.62-.62l.84-2.873a2 2 0 0 1 .506-.852z"></path>
					</svg>
				</div>
				<div class="card-info">
					<h2 class="card-title">New Topic</h2>
					<p class="card-desc">Start from scratch with a new discipline, syllabus, and reference materials</p>
				</div>
				<svg class="arrow" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
					<polyline points="9 18 15 12 9 6"></polyline>
				</svg>
			</div>
		</a>

		<a href="/teacher/train/existing" class="card-link glass-panel">
			<div class="card-row">
				<div class="card-icon blue">
					<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
						<path d="M21 12a9 9 0 1 1-9-9c2.52 0 4.93 1 6.74 2.74L21 8"></path>
						<path d="M21 3v5h-5"></path>
					</svg>
				</div>
				<div class="card-info">
					<h2 class="card-title">Existing Topic</h2>
					<p class="card-desc">Continue training with a previously configured topic and materials</p>
				</div>
				<svg class="arrow" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
					<polyline points="9 18 15 12 9 6"></polyline>
				</svg>
			</div>
		</a>
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

	.card-link {
		text-decoration: none;
		color: inherit;
		padding: 1.5rem;
		border-radius: 1rem;
		transition: transform 0.2s, box-shadow 0.2s;
	}
	.card-link:hover {
		transform: translateY(-2px);
		box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
	}

	.card-row {
		display: flex;
		align-items: center;
		gap: 1rem;
	}

	.card-icon {
		width: 48px;
		height: 48px;
		border-radius: 50%;
		display: flex;
		align-items: center;
		justify-content: center;
		flex-shrink: 0;
	}
	.card-icon.amber {
		background: rgba(245, 158, 11, 0.2);
		color: #f59e0b;
	}
	.card-icon.blue {
		background: rgba(59, 130, 246, 0.2);
		color: #3b82f6;
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
			padding: 1.5rem 1rem;
			min-height: calc(100vh - 60px);
			gap: 1.5rem;
		}

		.title {
			font-size: 1.65rem;
		}

		.subtitle {
			font-size: 0.95rem;
		}

		.cards {
			max-width: 100%;
			gap: 0.85rem;
		}

		.card-link {
			padding: 1.25rem;
		}

		.card-row {
			gap: 0.85rem;
		}

		.card-icon {
			width: 42px;
			height: 42px;
		}

		.card-icon svg {
			width: 18px;
			height: 18px;
		}

		.card-title {
			font-size: 1rem;
		}

		.card-desc {
			font-size: 0.82rem;
		}
	}

	@media (max-width: 480px) {
		.page {
			padding: 1.25rem 0.75rem;
			gap: 1.25rem;
		}

		.header {
			gap: 0.35rem;
		}

		.title {
			font-size: 1.45rem;
		}

		.subtitle {
			font-size: 0.88rem;
		}

		.cards {
			gap: 0.7rem;
		}

		.card-link {
			padding: 1rem;
			border-radius: 0.85rem;
		}

		.card-row {
			gap: 0.75rem;
		}

		.card-icon {
			width: 38px;
			height: 38px;
		}

		.card-icon svg {
			width: 16px;
			height: 16px;
		}

		.card-title {
			font-size: 0.95rem;
			margin-bottom: 0.15rem;
		}

		.card-desc {
			font-size: 0.78rem;
		}

		.arrow {
			width: 16px;
			height: 16px;
		}
	}
</style>
