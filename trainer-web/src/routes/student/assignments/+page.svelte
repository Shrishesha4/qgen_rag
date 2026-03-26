<script lang="ts">
	import { onMount } from 'svelte';
	import { apiFetch } from '$lib/api/client';
	import { ClipboardCheck, Calendar, Clock, ArrowRight, AlertCircle } from 'lucide-svelte';

	interface Assignment {
		id: string;
		title: string;
		description: string | null;
		scheduled_end: string | null;
		item_count: number;
		attempts_made: number;
	}

	let assignments: Assignment[] = [];
	let isLoading = true;
	let error: string | null = null;

	onMount(async () => {
		await loadAssignments();
	});

	async function loadAssignments() {
		isLoading = true;
		error = null;
		try {
			assignments = await apiFetch<Assignment[]>('/gel/student/assignments');
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to load assignments';
		} finally {
			isLoading = false;
		}
	}

	function formatDate(dateStr: string | null): string {
		if (!dateStr) return 'No deadline';
		return new Date(dateStr).toLocaleDateString('en-US', {
			month: 'short',
			day: 'numeric',
			year: 'numeric',
			hour: '2-digit',
			minute: '2-digit',
		});
	}

	function getDaysRemaining(dateStr: string | null): { text: string; urgent: boolean } {
		if (!dateStr) return { text: 'No deadline', urgent: false };
		const date = new Date(dateStr);
		const now = new Date();
		const diff = date.getTime() - now.getTime();
		const days = Math.ceil(diff / (1000 * 60 * 60 * 24));
		
		if (days < 0) return { text: 'Overdue', urgent: true };
		if (days === 0) return { text: 'Due today', urgent: true };
		if (days === 1) return { text: 'Due tomorrow', urgent: true };
		if (days <= 3) return { text: `${days} days left`, urgent: true };
		return { text: `${days} days left`, urgent: false };
	}
</script>

<svelte:head>
	<title>Assignments | GELTrain</title>
</svelte:head>

<div class="page-container student-shell space-y-8">
	<section class="glass-panel gradient-card">
		<div>
			<p class="eyebrow">Assignments</p>
			<h1 class="hero">Your assignments</h1>
			<p class="muted">Stay on top of due dates and progress.</p>
		</div>
		<div class="hero-metrics">
			<div>
				<p class="summary-value">{assignments.length}</p>
				<p class="summary-label">Open assignments</p>
			</div>
		</div>
	</section>

	{#if isLoading}
		<div class="center-state">
			<div class="spinner"></div>
			<p class="muted">Loading assignments...</p>
		</div>
	{:else if error}
		<div class="glass-panel error-panel">
			<div class="flex-row">
				<AlertCircle class="h-5 w-5" />
				<span>{error}</span>
			</div>
			<button class="pill ghost" on:click={loadAssignments}>Try again</button>
		</div>
	{:else if assignments.length === 0}
		<div class="glass-panel center-state">
			<ClipboardCheck class="h-10 w-10 text-emerald-300" />
			<h3 class="text-white">No assignments yet</h3>
			<p class="muted">Check back later for new assignments from your teachers.</p>
		</div>
	{:else}
		<div class="grid gap-4">
			{#each assignments as assignment}
				{@const remaining = getDaysRemaining(assignment.scheduled_end)}
				<a class="glass-panel assignment-card" href="/student/assignments/{assignment.id}">
					<div class="card-head">
						<div class="title-block">
							<p class="title">{assignment.title}</p>
							{#if assignment.description}
								<p class="muted line-clamp">{assignment.description}</p>
							{/if}
						</div>
						<div class="badges">
							<span class={`chip ${remaining.urgent ? 'warn' : ''}`}>
								<Clock class="h-4 w-4" /> {remaining.text}
							</span>
							<span class="chip subtle">
								<Calendar class="h-4 w-4" /> {formatDate(assignment.scheduled_end)}
							</span>
						</div>
					</div>

					<div class="card-body">
						<div class="meta">
							<ClipboardCheck class="h-4 w-4" />
							<span>{assignment.attempts_made} / {assignment.item_count} completed</span>
						</div>
						<div class="progress-stats">
							<div class="percent">{Math.round((assignment.attempts_made / assignment.item_count) * 100)}%</div>
							<div class="muted small">complete</div>
						</div>
						<ArrowRight class="h-5 w-5 text-white/60" />
					</div>

					<div class="progress">
						<div
							class="progress-bar"
							style={`width: ${(assignment.attempts_made / assignment.item_count) * 100}%`}
						></div>
					</div>
				</a>
			{/each}
		</div>
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
		color: #fff;
		text-decoration: none;
	}

	.gradient-card {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1.25rem;
		background: radial-gradient(circle at 18% 18%, rgba(99, 102, 241, 0.3), transparent 32%),
			radial-gradient(circle at 82% 12%, rgba(45, 212, 191, 0.28), transparent 34%),
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

	.muted.small {
		font-size: 0.9rem;
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

	.error-panel {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.75rem;
	}

	.flex-row {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		color: #fca5a5;
	}

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

	.assignment-card {
		display: flex;
		flex-direction: column;
		gap: 12px;
		transition: transform 0.15s ease, border-color 0.15s ease;
	}

	.assignment-card:hover {
		transform: translateY(-2px);
		border-color: rgba(255, 255, 255, 0.16);
	}

	.card-head {
		display: flex;
		justify-content: space-between;
		gap: 1rem;
		align-items: flex-start;
	}

	.title-block { flex: 1; min-width: 0; }

	.title {
		margin: 0 0 4px;
		font-size: 1.15rem;
		font-weight: 700;
		color: #fff;
	}

	.badges {
		display: flex;
		gap: 8px;
		flex-wrap: wrap;
		justify-content: flex-end;
	}

	.chip {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		padding: 6px 12px;
		border-radius: 999px;
		border: 1px solid rgba(255, 255, 255, 0.14);
		color: rgba(255, 255, 255, 0.9);
		font-weight: 600;
		font-size: 0.9rem;
		background: rgba(255, 255, 255, 0.06);
	}

	.chip.subtle { background: rgba(255, 255, 255, 0.04); }
	.chip.warn { border-color: rgba(248, 113, 113, 0.4); color: #fecaca; background: rgba(248, 113, 113, 0.12); }

	.card-body {
		display: grid;
		grid-template-columns: 1.3fr 0.5fr auto;
		align-items: center;
		gap: 0.75rem;
	}

	.meta {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		color: rgba(255, 255, 255, 0.85);
	}

	.progress-stats { text-align: right; }
	.progress-stats .percent { font-size: 1.35rem; font-weight: 700; color: #fff; }

	.progress {
		width: 100%;
		height: 8px;
		background: rgba(255, 255, 255, 0.08);
		border-radius: 999px;
		overflow: hidden;
	}

	.progress-bar {
		height: 100%;
		background: linear-gradient(90deg, rgba(94, 234, 212, 0.9), rgba(59, 130, 246, 0.9));
		border-radius: 999px;
		transition: width 0.2s ease;
	}

	.line-clamp {
		display: -webkit-box;
		line-clamp: 2;
		-webkit-line-clamp: 2;
		-webkit-box-orient: vertical;
		overflow: hidden;
	}

	@keyframes spin { to { transform: rotate(360deg); } }

	@media (max-width: 900px) {
		.hero-metrics { flex-wrap: wrap; }
		.card-head { flex-direction: column; }
		.card-body { grid-template-columns: 1fr; align-items: flex-start; }
		.progress-stats { text-align: left; }
		.badges { justify-content: flex-start; }
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

	:global([data-color-mode='light']) .student-shell .title,
	:global([data-color-mode='light']) .student-shell .progress-stats .percent,
	:global([data-color-mode='light']) .student-shell h1,
	:global([data-color-mode='light']) .student-shell h3 {
		color: #0f172a;
	}

	:global([data-color-mode='light']) .student-shell .muted,
	:global([data-color-mode='light']) .student-shell .summary-label,
	:global([data-color-mode='light']) .student-shell .meta,
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

	:global([data-color-mode='light']) .student-shell .chip.subtle { background: #f1f5f9; }
	:global([data-color-mode='light']) .student-shell .chip.warn { color: #b91c1c; border-color: rgba(185, 28, 28, 0.35); background: rgba(248, 113, 113, 0.16); }

	:global([data-color-mode='light']) .student-shell .progress {
		background: rgba(15, 23, 42, 0.08);
	}

	:global([data-color-mode='light']) .student-shell .icon-pill,
	:global([data-color-mode='light']) .student-shell .pill,
	:global([data-color-mode='light']) .student-shell .ghost {
		border-color: rgba(15, 23, 42, 0.12);
		color: #0f172a;
	}

	:global([data-color-mode='light']) .student-shell .ghost {
		background: rgba(15, 23, 42, 0.04);
	}
</style>
