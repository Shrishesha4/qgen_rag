<script lang="ts">
	import { onMount } from 'svelte';
	import { apiFetch } from '$lib/api/client';
	import { currentUser } from '$lib/session';
	import {
		ClipboardCheck,
		Clock,
		CheckCircle,
		AlertCircle,
		TrendingUp,
		Calendar,
		ArrowRight,
		History
	} from 'lucide-svelte';

	interface AssignedItem {
		evaluation_item_id: string;
		assignment_id: string;
		assignment_title: string;
		question_text: string;
		question_type: string | null;
		difficulty_label: string | null;
		bloom_level: string | null;
		due_date: string | null;
		time_limit_minutes: number | null;
		attempts_used: number;
		max_attempts: number;
		last_attempt_status: string | null;
		last_attempt_score: number | null;
	}

	interface DashboardData {
		assigned_items: AssignedItem[];
		in_progress_count: number;
		completed_count: number;
		due_soon_count: number;
		average_score: number | null;
	}

	let dashboard = $state<DashboardData | null>(null);
	let isLoading = $state(true);
	let error = $state<string | null>(null);

	onMount(async () => {
		await loadDashboard();
	});

	async function loadDashboard() {
		isLoading = true;
		error = null;
		try {
			dashboard = await apiFetch<DashboardData>('/gel/student/dashboard');
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to load dashboard';
			console.error('Dashboard error:', e);
		} finally {
			isLoading = false;
		}
	}

	function formatDate(dateStr: string | null): string {
		if (!dateStr) return 'No deadline';
		const date = new Date(dateStr);
		const now = new Date();
		const diff = date.getTime() - now.getTime();
		const days = Math.ceil(diff / (1000 * 60 * 60 * 24));

		if (days < 0) return 'Overdue';
		if (days === 0) return 'Due today';
		if (days === 1) return 'Due tomorrow';
		if (days <= 7) return `Due in ${days} day${days === 1 ? '' : 's'}`;
		return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
	}

	const completedStatuses = new Set(['completed', 'reviewed', 'scored', 'graded']);
	const pendingItems = $derived(
		dashboard?.assigned_items.filter((item: AssignedItem) => !completedStatuses.has(item.last_attempt_status ?? '')) ?? []
	);
	const completedItems = $derived(
		dashboard?.assigned_items
			.filter((item: AssignedItem) => completedStatuses.has(item.last_attempt_status ?? ''))
			.slice()
			.sort((a: AssignedItem, b: AssignedItem) => {
				const aDate = a.due_date ? new Date(a.due_date).getTime() : 0;
				const bDate = b.due_date ? new Date(b.due_date).getTime() : 0;
				return bDate - aDate;
			}) ?? []
	);

	function getDifficultyColor(label: string | null) {
		switch (label) {
			case 'advanced':
				return 'bg-rose-500/20 text-rose-100 border border-rose-400/30';
			case 'intermediate':
				return 'bg-amber-500/20 text-amber-100 border border-amber-400/30';
			case 'beginner':
				return 'bg-emerald-500/20 text-emerald-100 border border-emerald-400/30';
			default:
				return 'bg-white/10 text-white border border-white/20';
		}
	}
</script>

<div class="page-container student-shell space-y-8">
	<section class="glass-panel gradient-card">
		<div>
			<p class="text-sm text-white/70 uppercase tracking-[0.15em]">Welcome</p>
			<h1 class="text-3xl font-semibold text-white mt-1">
				Hello, {$currentUser?.full_name || $currentUser?.username}
			</h1>
			<p class="text-white/70 mt-2">
				Continue your GEL journey and keep your streak going.
			</p>
		</div>
	</section>

	{#if isLoading}
		<div class="center-state">
			<div class="spinner"></div>
			<p class="text-white/70 mt-3">Loading dashboard...</p>
		</div>
	{:else if error}
		<div class="glass-panel border border-red-500/30 bg-red-500/10">
			<div class="flex items-center gap-3 text-red-100">
				<AlertCircle class="h-5 w-5" />
				<span>{error}</span>
			</div>
			<button class="glass-btn-secondary mt-3" onclick={loadDashboard}>Try again</button>
		</div>
	{:else if dashboard}
		<div class="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
			<div class="glass-panel stat-card">
				<div class="icon-pill bg-amber-500/20 text-amber-200"><Clock class="h-5 w-5" /></div>
				<div>
					<p class="stat-value">{dashboard.in_progress_count}</p>
					<p class="stat-label">In Progress</p>
				</div>
			</div>
			<div class="glass-panel stat-card">
				<div class="icon-pill bg-emerald-500/20 text-emerald-200"><CheckCircle class="h-5 w-5" /></div>
				<div>
					<p class="stat-value">{dashboard.completed_count}</p>
					<p class="stat-label">Completed</p>
				</div>
			</div>
			<div class="glass-panel stat-card">
				<div class="icon-pill bg-rose-500/20 text-rose-200"><Calendar class="h-5 w-5" /></div>
				<div>
					<p class="stat-value">{dashboard.due_soon_count}</p>
					<p class="stat-label">Due Soon</p>
				</div>
			</div>
			<div class="glass-panel stat-card">
				<div class="icon-pill bg-primary-500/25 text-primary-100"><TrendingUp class="h-5 w-5" /></div>
				<div>
					<p class="stat-value">{dashboard.average_score !== null ? `${dashboard.average_score.toFixed(0)}%` : '-'}</p>
					<p class="stat-label">Avg Score</p>
				</div>
			</div>
		</div>

		<section class="glass-panel">
			<header class="section-head">
				<div class="section-title">
					<ClipboardCheck class="h-5 w-5 text-primary-200" />
					<div>
						<p class="text-white font-semibold">Pending Evaluations</p>
						<p class="text-white/60 text-sm">Start where you left off</p>
					</div>
				</div>
				{#if pendingItems.length > 5}
					<a class="glass-pill text-primary-100" href="/student/assignments">View all</a>
				{/if}
			</header>

			{#if pendingItems.length === 0}
				<div class="empty-state">
					<CheckCircle class="h-10 w-10 text-emerald-300" />
					<h3>All caught up!</h3>
					<p>No pending evaluations right now.</p>
				</div>
			{:else}
				<div class="divide-y divide-white/5">
					{#each pendingItems.slice(0, 5) as item}
						<a class="row" href="/student/evaluate/{item.evaluation_item_id}?assignment={item.assignment_id}">
							<div class="flex-1 min-w-0">
								<p class="text-white font-medium truncate">{item.assignment_title}</p>
								<p class="text-white/70 text-sm truncate mt-1">
									{item.question_text.slice(0, 120)}{item.question_text.length > 120 ? '…' : ''}
								</p>
								<div class="mt-2 flex items-center gap-2 text-xs">
									{#if item.difficulty_label}
										<span class={`pill ${getDifficultyColor(item.difficulty_label)}`}>
											{item.difficulty_label}
										</span>
									{/if}
									<span class="text-white/60">{formatDate(item.due_date)}</span>
									{#if item.last_attempt_status === 'in_progress'}
										<span class="text-amber-200">• In Progress</span>
									{/if}
								</div>
							</div>
							<ArrowRight class="h-5 w-5 text-white/50" />
						</a>
					{/each}
				</div>
			{/if}
		</section>

		{#if completedItems.length > 0}
			<section class="glass-panel">
				<header class="section-head">
					<div class="section-title">
						<History class="h-5 w-5 text-primary-200" />
						<div>
							<p class="text-white font-semibold">Recently Completed</p>
							<p class="text-white/60 text-sm">Latest scored or reviewed attempts</p>
						</div>
					</div>
				</header>
				<ul class="divide-y divide-white/5">
					{#each completedItems.slice(0, 5) as item}
						<li class="row">
							<div class="flex-1 min-w-0">
								<p class="text-white font-medium truncate">{item.assignment_title}</p>
								<p class="text-white/70 text-sm truncate mt-1">
									{item.question_text.slice(0, 120)}{item.question_text.length > 120 ? '…' : ''}
								</p>
							</div>
							<div class="flex items-center gap-3 text-sm text-white/80">
								{#if item.last_attempt_score !== null}
									<span class="pill bg-primary-500/20 text-primary-100 border border-primary-400/30">
										{item.last_attempt_score.toFixed(0)}%
									</span>
								{/if}
								<span>{item.last_attempt_status === 'reviewed' ? 'Reviewed' : 'Scored'}</span>
							</div>
						</li>
					{/each}
				</ul>
			</section>
		{/if}
	{/if}
</div>

<style>
	.page-container {
		max-width: 1180px;
		margin: 0 auto;
		padding: clamp(1rem, 2vw, 1.5rem) clamp(1.25rem, 3vw, 2.25rem) clamp(2rem, 3vw, 2.75rem);
	}

	.gradient-card {
		background: radial-gradient(circle at 20% 20%, rgba(99, 102, 241, 0.35), transparent 30%),
			radial-gradient(circle at 80% 0%, rgba(16, 185, 129, 0.3), transparent 30%),
			radial-gradient(circle at 40% 80%, rgba(236, 72, 153, 0.25), transparent 35%),
			linear-gradient(135deg, rgba(23, 23, 40, 0.9), rgba(15, 23, 42, 0.85));
	}

	.glass-panel {
		background: rgba(255, 255, 255, 0.04);
		border: 1px solid rgba(255, 255, 255, 0.08);
		border-radius: 18px;
		padding: 20px;
		box-shadow: 0 20px 70px rgba(0, 0, 0, 0.35);
		backdrop-filter: blur(18px);
	}

	.section-head {
		display: flex;
		align-items: center;
		justify-content: space-between;
		margin-bottom: 14px;
	}

	.section-title {
		display: flex;
		align-items: center;
		gap: 10px;
	}

	.icon-pill {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		padding: 10px;
		border-radius: 12px;
		border: 1px solid rgba(255, 255, 255, 0.1);
	}

	.stat-card {
		display: flex;
		align-items: center;
		gap: 12px;
	}

	.stat-value {
		font-size: 1.8rem;
		font-weight: 700;
		color: #fff;
		line-height: 1.1;
	}

	.stat-label {
		color: rgba(255, 255, 255, 0.7);
		font-size: 0.95rem;
	}

	.row {
		display: flex;
		align-items: center;
		gap: 14px;
		padding: 14px 0;
		transition: transform 0.15s ease, opacity 0.15s ease;
	}

	.row:hover {
		transform: translateY(-2px);
		opacity: 0.96;
	}

	.pill {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		padding: 4px 10px;
		border-radius: 999px;
		border: 1px solid rgba(255, 255, 255, 0.12);
		font-weight: 600;
	}

	.empty-state {
		text-align: center;
		padding: 28px 12px;
		color: rgba(255, 255, 255, 0.8);
		display: grid;
		gap: 8px;
		place-items: center;
	}

	.center-state {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		min-height: 200px;
	}

	.spinner {
		width: 44px;
		height: 44px;
		border-radius: 999px;
		border: 3px solid rgba(255, 255, 255, 0.2);
		border-top-color: rgba(255, 255, 255, 0.8);
		animation: spin 0.8s linear infinite;
	}

	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
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

	:global([data-color-mode='light']) .student-shell .icon-pill {
		border-color: rgba(15, 23, 42, 0.1);
	}

	:global([data-color-mode='light']) .student-shell .stat-value,
	:global([data-color-mode='light']) .student-shell .row .text-white,
	:global([data-color-mode='light']) .student-shell h1,
	:global([data-color-mode='light']) .student-shell h3 {
		color: #0f172a;
	}

	:global([data-color-mode='light']) .student-shell .stat-label,
	:global([data-color-mode='light']) .student-shell .empty-state,
	:global([data-color-mode='light']) :global(.student-shell) :global(.text-white\/60),
	:global([data-color-mode='light']) :global(.student-shell) :global(.text-white\/70),
	:global([data-color-mode='light']) :global(.student-shell) :global(.text-white\/80),
	:global([data-color-mode='light']) :global(.student-shell) :global(.text-white\/50) {
		color: #475569;
	}

	:global([data-color-mode='light']) :global(.student-shell) :global(.text-white) {
		color: #0f172a !important;
	}

	:global([data-color-mode='light']) .student-shell .pill {
		border-color: rgba(15, 23, 42, 0.12);
	}
</style>
