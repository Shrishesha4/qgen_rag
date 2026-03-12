<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { session } from '$lib/session';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import { getQuestionsForVetting, getVetterDashboard, type QuestionForVetting, type VetterDashboard } from '$lib/api/vetting';

	onMount(() => {
		const unsub = session.subscribe((s) => {
			if (!s) goto('/teacher/login');
		});
		loadData();
		return unsub;
	});

	let loading = $state(true);
	let error = $state('');
	let queue = $state<QuestionForVetting[]>([]);
	let stats = $state<VetterDashboard | null>(null);

	async function loadData() {
		loading = true;
		error = '';
		try {
			const [dashRes, qRes] = await Promise.all([
				getVetterDashboard(),
				getQuestionsForVetting({ status: 'pending', limit: 50 })
			]);
			stats = dashRes;
			queue = qRes.questions;
		} catch (e: any) {
			error = e?.message || 'Failed to load review queue';
		} finally {
			loading = false;
		}
	}

	function startVerifying(q: QuestionForVetting) {
		const params = q.subject_id ? `?subject=${q.subject_id}` : '';
		goto(`/teacher/train/loop${params}`);
	}

	function formatTime(iso: string): string {
		const diff = Date.now() - new Date(iso).getTime();
		const mins = Math.floor(diff / 60000);
		if (mins < 1) return 'just now';
		if (mins < 60) return `${mins} min ago`;
		const hrs = Math.floor(mins / 60);
		if (hrs < 24) return `${hrs}h ago`;
		return `${Math.floor(hrs / 24)}d ago`;
	}

	function typeLabel(t: string): string {
		if (t === 'mcq') return 'MCQ';
		if (t === 'true_false') return 'True/False';
		return 'Short Answer';
	}
</script>

<svelte:head>
	<title>Verifier Mode — QGen Trainer</title>
</svelte:head>

<PageHeader title="Verifier Mode" backHref="/teacher/dashboard" />

<div class="verify-page">
	<div class="header">
		<h1 class="title">Verifier Mode</h1>
		<p class="subtitle">Review AI-generated questions for quality</p>
	</div>

	<div class="stats-row">
		<div class="stat glass">
			<span class="stat-value">{stats?.total_pending ?? '—'}</span>
			<span class="stat-label">Pending</span>
		</div>
		<div class="stat glass">
			<span class="stat-value">{stats?.total_approved ?? '—'}</span>
			<span class="stat-label">Approved</span>
		</div>
		<div class="stat glass">
			<span class="stat-value">{stats?.total_rejected ?? '—'}</span>
			<span class="stat-label">Rejected</span>
		</div>
	</div>

	{#if loading}
		<div class="empty">
			<div class="spinner"></div>
			<p>Loading review queue…</p>
		</div>
	{:else if error}
		<div class="empty">
			<span class="empty-icon">⚠️</span>
			<p>{error}</p>
			<button class="glass-btn" onclick={loadData}>Retry</button>
		</div>
	{:else if queue.length === 0}
		<div class="empty">
			<span class="empty-icon">✅</span>
			<p>All caught up! No questions to review.</p>
		</div>
	{:else}
		<div class="queue-section">
			<h2 class="section-title">Review Queue</h2>
			<div class="queue-list">
				{#each queue as item}
					<button class="queue-item glass-card" onclick={() => startVerifying(item)}>
						<div class="qi-top">
							<span class="qi-type">{typeLabel(item.question_type)}</span>
							{#if item.topic_name}
								<span class="qi-topic">{item.topic_name}</span>
							{/if}
						</div>
						<p class="qi-text">{item.question_text}</p>
						<span class="qi-time">{formatTime(item.generated_at)}</span>
					</button>
				{/each}
			</div>
		</div>
	{/if}
</div>

<style>
	.verify-page {
		max-width: 600px;
		margin: 0 auto;
		padding: 2rem 1.5rem;
		display: flex;
		flex-direction: column;
		gap: 1.5rem;
		min-height: 100vh;
	}

	.header {
		text-align: center;
	}

	.title {
		font-size: 1.75rem;
		font-weight: 800;
		margin: 0 0 0.35rem;
		color: var(--theme-text);
	}

	.subtitle {
		font-size: 0.95rem;
		color: var(--theme-text-muted);
		margin: 0;
	}

	.stats-row {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: 0.75rem;
	}

	.stat {
		display: flex;
		flex-direction: column;
		align-items: center;
		padding: 1rem;
		gap: 0.25rem;
	}

	.stat-value {
		font-size: 1.5rem;
		font-weight: 800;
		color: var(--theme-text);
	}

	.stat-label {
		font-size: 0.75rem;
		font-weight: 600;
		color: var(--theme-text-muted);
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}

	.section-title {
		font-size: 1rem;
		font-weight: 700;
		color: var(--theme-text-muted);
		margin: 0;
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}

	.queue-list {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
		margin-top: 0.75rem;
	}

	.queue-item {
		text-align: left;
		cursor: pointer;
		padding: 1rem 1.25rem;
		width: 100%;
		font-family: inherit;
	}

	.qi-top {
		display: flex;
		gap: 0.5rem;
		margin-bottom: 0.5rem;
	}

	.qi-type {
		font-size: 0.7rem;
		font-weight: 700;
		padding: 0.15rem 0.5rem;
		background: rgba(var(--theme-primary-rgb), 0.15);
		color: var(--theme-primary);
		border-radius: 4px;
		text-transform: uppercase;
	}

	.qi-topic {
		font-size: 0.7rem;
		font-weight: 600;
		padding: 0.15rem 0.5rem;
		background: rgba(255, 255, 255, 0.08);
		color: var(--theme-text-muted);
		border-radius: 4px;
	}

	.qi-text {
		font-size: 0.92rem;
		color: var(--theme-text);
		margin: 0;
		line-height: 1.4;
		display: -webkit-box;
		-webkit-line-clamp: 2;
		line-clamp: 2;
		-webkit-box-orient: vertical;
		overflow: hidden;
	}

	.qi-time {
		font-size: 0.75rem;
		color: var(--theme-text-muted);
		margin-top: 0.5rem;
		display: block;
	}

	.empty {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.75rem;
		padding: 3rem;
		text-align: center;
	}

	.empty-icon {
		font-size: 3rem;
	}

	.empty p {
		color: var(--theme-text-muted);
		margin: 0;
	}

	.spinner {
		width: 2rem;
		height: 2rem;
		border: 3px solid rgba(var(--theme-primary-rgb), 0.2);
		border-top-color: var(--theme-primary);
		border-radius: 50%;
		animation: spin 0.7s linear infinite;
	}

	@keyframes spin {
		to { transform: rotate(360deg); }
	}

	@media (max-width: 768px) {
		.verify-page {
			padding-top: 1rem;
		}

		.title {
			font-size: 1.4rem;
		}
	}
</style>
