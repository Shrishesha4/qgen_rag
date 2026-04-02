<script lang="ts">
	import { onMount } from 'svelte';
	import { apiFetch } from '$lib/api/client';
	import { AlertCircle, TrendingUp, Flame, Target, BarChart3, Clock, Trophy, Activity, CheckCircle } from 'lucide-svelte';

	type RecentAttempt = {
		attempt_id: string;
		assignment_title?: string | null;
		question_text: string;
		status: string;
		score: number | null;
		submitted_at: string | null;
	};

	type ProgressResponse = {
		total_assignments: number;
		total_items_assigned: number;
		attempted_items: number;
		in_progress_attempts: number;
		completed_attempts: number;
		average_score: number | null;
		best_score: number | null;
		completion_rate: number | null;
		streak_days: number;
		last_activity_at: string | null;
		recent_attempts: RecentAttempt[];
	};

	let data: ProgressResponse | null = null;
	let isLoading = true;
	let error: string | null = null;

	onMount(async () => {
		await loadProgress();
	});

	async function loadProgress() {
		isLoading = true;
		error = null;
		try {
			data = await apiFetch<ProgressResponse>('/gel/student/progress');
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to load progress';
		} finally {
			isLoading = false;
		}
	}

	function formatDate(value: string | null): string {
		if (!value) return '—';
		return new Date(value).toLocaleString(undefined, {
			month: 'short',
			day: 'numeric',
			hour: '2-digit',
			minute: '2-digit',
		});
	}

	function formatScore(value: number | null): string {
		if (value === null || Number.isNaN(value)) return '—';
		return `${value.toFixed(0)}%`;
	}
</script>

<div class="page-container student-shell space-y-8">
	<section class="glass-panel gradient-card">
		<div>
			<p class="eyebrow">Progress</p>
			<h1 class="hero">Your learning journey</h1>
			<p class="muted">Track completions, streaks, and scores.</p>
		</div>
		<div class="hero-metrics">
			<div>
				<p class="summary-value">{formatScore(data?.average_score ?? null)}</p>
				<p class="summary-label">Average score</p>
			</div>
			<div>
				<p class="summary-value">{data?.streak_days ?? 0}</p>
				<p class="summary-label">Day streak</p>
			</div>
			<div>
				<p class="summary-value">{data?.completion_rate !== null ? `${data?.completion_rate.toFixed(0)}%` : '—'}</p>
				<p class="summary-label">Completion rate</p>
			</div>
		</div>
	</section>

	{#if isLoading}
		<div class="center-state">
			<div class="spinner"></div>
			<p class="muted">Loading progress...</p>
		</div>
	{:else if error}
		<div class="glass-panel error-panel">
			<div class="flex gap-2 items-center text-red-200">
				<AlertCircle class="h-5 w-5" />
				<span>{error}</span>
			</div>
			<button class="pill ghost" on:click={loadProgress}>Try again</button>
		</div>
	{:else if data}
		<div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
			<div class="glass-panel stat-card">
				<div class="icon-pill"><TrendingUp class="h-5 w-5" /></div>
				<div>
					<p class="stat-value">{data.total_assignments}</p>
					<p class="stat-label">Assignments</p>
				</div>
			</div>
			<div class="glass-panel stat-card">
				<div class="icon-pill"><Target class="h-5 w-5" /></div>
				<div>
					<p class="stat-value">{data.total_items_assigned}</p>
					<p class="stat-label">Items assigned</p>
				</div>
			</div>
			<div class="glass-panel stat-card">
				<div class="icon-pill"><BarChart3 class="h-5 w-5" /></div>
				<div>
					<p class="stat-value">{data.attempted_items}</p>
					<p class="stat-label">Items attempted</p>
				</div>
			</div>
			<div class="glass-panel stat-card">
				<div class="icon-pill"><Clock class="h-5 w-5" /></div>
				<div>
					<p class="stat-value">{data.in_progress_attempts}</p>
					<p class="stat-label">In progress</p>
				</div>
			</div>
			<div class="glass-panel stat-card">
				<div class="icon-pill"><CheckCircle class="h-5 w-5" /></div>
				<div>
					<p class="stat-value">{data.completed_attempts}</p>
					<p class="stat-label">Completed attempts</p>
				</div>
			</div>
			<div class="glass-panel stat-card">
				<div class="icon-pill"><Trophy class="h-5 w-5" /></div>
				<div>
					<p class="stat-value">{formatScore(data.best_score)}</p>
					<p class="stat-label">Best score</p>
				</div>
			</div>
		</div>

		<section class="glass-panel recent">
			<header class="section-head">
				<div>
					<p class="text-white font-semibold">Recent attempts</p>
					<p class="muted">Your latest submissions</p>
				</div>
				<p class="muted">Last activity: {formatDate(data.last_activity_at)}</p>
			</header>
			{#if data.recent_attempts.length === 0}
				<div class="center-state">
					<Flame class="h-8 w-8 text-emerald-300" />
					<p class="muted">No attempts yet.</p>
				</div>
			{:else}
				<ul class="divide">
					{#each data.recent_attempts as attempt}
						<li class="row">
							<div class="flex-1 min-w-0">
								<p class="text-white font-semibold truncate">{attempt.assignment_title ?? 'Ungrouped item'}</p>
								<p class="muted truncate">{attempt.question_text}</p>
							</div>
							<div class="tags">
								<span class="chip">{attempt.status}</span>
								<span class="chip subtle">{formatScore(attempt.score)}</span>
							</div>
							<div class="muted">{formatDate(attempt.submitted_at)}</div>
						</li>
					{/each}
				</ul>
			{/if}
		</section>
	{/if}
</div>

<style>
	.page-container {
		max-width: 1180px;
		margin: 0 auto;
		padding: clamp(1rem, 2vw, 1.5rem) clamp(1.25rem, 3vw, 2.25rem) clamp(2rem, 3vw, 2.75rem);
	}

	.glass-panel {
		background: rgba(255, 255, 255, 0.04);
		border: 1px solid rgba(255, 255, 255, 0.08);
		border-radius: 18px;
		padding: 18px;
		box-shadow: 0 20px 60px rgba(0, 0, 0, 0.35);
		backdrop-filter: blur(18px);
	}

	.gradient-card {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1.25rem;
		background: radial-gradient(circle at 18% 18%, rgba(236, 72, 153, 0.26), transparent 32%),
			radial-gradient(circle at 82% 12%, rgba(56, 189, 248, 0.2), transparent 34%),
			linear-gradient(135deg, rgba(17, 24, 39, 0.92), rgba(15, 23, 42, 0.86));
	}

	.eyebrow {
		margin: 0;
		text-transform: uppercase;
		letter-spacing: 0.14em;
		font-size: 0.75rem;
		color: rgba(255, 255, 255, 0.72);
	}

	.hero {
		margin: 2px 0 6px;
		color: #fff;
		font-size: clamp(1.75rem, 2.2vw, 2.2rem);
		font-weight: 700;
	}

	.muted {
		color: rgba(255, 255, 255, 0.72);
		margin: 0;
	}

	.hero-metrics {
		display: flex;
		gap: 1.5rem;
		align-items: center;
	}

	.summary-value {
		margin: 0;
		font-size: 1.9rem;
		font-weight: 700;
		color: #fff;
	}

	.summary-label {
		margin: 0;
		color: rgba(255, 255, 255, 0.7);
		font-size: 0.95rem;
	}

	.center-state {
		display: grid;
		place-items: center;
		gap: 0.5rem;
		padding: 2rem 1.5rem;
		text-align: center;
	}

	.spinner {
		width: 44px;
		height: 44px;
		border-radius: 50%;
		border: 3px solid rgba(255, 255, 255, 0.18);
		border-top-color: rgba(255, 255, 255, 0.8);
		animation: spin 0.8s linear infinite;
	}

	.stat-card {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		padding: 16px;
	}

	.stat-value {
		margin: 0;
		font-size: 1.6rem;
		font-weight: 700;
		color: #fff;
	}

	.stat-label {
		margin: 0;
		color: rgba(255, 255, 255, 0.72);
		font-size: 0.95rem;
	}

	.icon-pill {
		width: 44px;
		height: 44px;
		border-radius: 14px;
		display: grid;
		place-items: center;
		background: rgba(255, 255, 255, 0.06);
		border: 1px solid rgba(255, 255, 255, 0.14);
		color: #fff;
	}

	.section-head {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1rem;
		margin-bottom: 0.5rem;
	}

	.recent {
		padding: 18px;
	}

	.divide {
		list-style: none;
		margin: 0;
		padding: 0;
	}

	.divide .row {
		display: grid;
		grid-template-columns: 1fr auto auto;
		align-items: center;
		gap: 0.75rem;
		padding: 12px 0;
		border-bottom: 1px solid rgba(255, 255, 255, 0.06);
	}

	.divide .row:last-child {
		border-bottom: none;
	}

	.tags {
		display: flex;
		gap: 6px;
		flex-wrap: wrap;
		justify-content: flex-end;
	}

	.chip {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		padding: 4px 10px;
		border-radius: 999px;
		border: 1px solid rgba(255, 255, 255, 0.14);
		color: rgba(255, 255, 255, 0.9);
		font-weight: 600;
		font-size: 0.85rem;
		background: rgba(255, 255, 255, 0.06);
	}

	.chip.subtle { background: rgba(255, 255, 255, 0.04); }

	.pill {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		padding: 0.55rem 0.9rem;
		border-radius: 12px;
		font-weight: 600;
	}

	.ghost {
		border: 1px solid rgba(255, 255, 255, 0.14);
		background: rgba(255, 255, 255, 0.04);
		color: #fff;
		cursor: pointer;
		transition: 140ms ease;
	}

	.ghost:hover {
		border-color: rgba(var(--theme-primary-rgb), 0.5);
		background: rgba(var(--theme-primary-rgb), 0.12);
	}

	.error-panel {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.75rem;
	}

	@keyframes spin { to { transform: rotate(360deg); } }

	@media (max-width: 900px) {
		.hero-metrics { flex-wrap: wrap; }
		.divide .row { grid-template-columns: 1fr; gap: 0.35rem; }
		.tags { justify-content: flex-start; }
	}

	:global([data-color-mode='light']) .student-shell {
		color: #0f172a;
	}

	:global([data-color-mode='light']) .student-shell .gradient-card {
		background: linear-gradient(135deg, #f8fafc, #e0f2fe);
	}

	:global([data-color-mode='light']) .student-shell .glass-panel {
		background: rgba(255, 255, 255, 0.92);
		border-color: rgba(15, 23, 42, 0.08);
		box-shadow: 0 18px 50px rgba(15, 23, 42, 0.14);
		color: #0f172a;
	}

	:global([data-color-mode='light']) .student-shell .hero,
	:global([data-color-mode='light']) .student-shell .summary-value,
	:global([data-color-mode='light']) .student-shell .stat-value {
		color: #0f172a;
	}

	:global([data-color-mode='light']) .student-shell .eyebrow,
	:global([data-color-mode='light']) .student-shell .muted,
	:global([data-color-mode='light']) .student-shell .summary-label,
	:global([data-color-mode='light']) .student-shell .stat-label,
	:global([data-color-mode='light']) .student-shell .divide .row,
	:global([data-color-mode='light']) :global(.student-shell) :global(.text-white\/60),
	:global([data-color-mode='light']) :global(.student-shell) :global(.text-white\/70),
	:global([data-color-mode='light']) :global(.student-shell) :global(.text-white\/80),
	:global([data-color-mode='light']) :global(.student-shell) :global(.text-white\/50) {
		color: #475569;
	}

	:global([data-color-mode='light']) :global(.student-shell) :global(.text-white) {
		color: #0f172a !important;
	}

	:global([data-color-mode='light']) .student-shell .chip {
		border-color: rgba(15, 23, 42, 0.12);
		background: #e2e8f0;
		color: #0f172a;
	}

	:global([data-color-mode='light']) .student-shell .chip.subtle {
		background: #f1f5f9;
	}

	:global([data-color-mode='light']) .student-shell .icon-pill {
		background: #e2e8f0;
		border-color: rgba(15, 23, 42, 0.12);
		color: #0f172a;
	}

	:global([data-color-mode='light']) .student-shell .ghost {
		border-color: rgba(15, 23, 42, 0.12);
		background: rgba(15, 23, 42, 0.04);
		color: #0f172a;
	}
</style>
