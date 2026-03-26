<script lang="ts">
	import { onMount } from 'svelte';
	import { apiFetch } from '$lib/api/client';
	import { AlertCircle, Clock, BookOpenCheck, Hash, ListChecks } from 'lucide-svelte';

	type HistoryItem = {
		attempt_id: string;
		evaluation_item_id: string;
		assignment_id?: string | null;
		assignment_title?: string | null;
		question_text: string;
		question_type: string | null;
		difficulty_label: string | null;
		bloom_level: string | null;
		status: string;
		score: number | null;
		submitted_at: string | null;
		updated_at: string | null;
		attempt_number: number;
	};

	type HistoryResponse = {
		items: HistoryItem[];
		total: number;
	};

	let data: HistoryResponse | null = null;
	let isLoading = true;
	let error: string | null = null;

	onMount(async () => {
		await loadHistory();
	});

	async function loadHistory() {
		isLoading = true;
		error = null;
		try {
			data = await apiFetch<HistoryResponse>('/gel/student/history');
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to load history';
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

	function formatScore(score: number | null): string {
		if (score === null || Number.isNaN(score)) return '—';
		return `${score.toFixed(0)}%`;
	}

	function statusLabel(status: string): string {
		const map: Record<string, string> = {
			not_started: 'Not started',
			in_progress: 'In progress',
			submitted: 'Submitted',
			scored: 'Scored',
			reviewed: 'Reviewed',
		};
		return map[status] ?? status;
	}
</script>

<div class="page-container student-shell space-y-6">
	<section class="glass-panel gradient-card">
		<div>
			<p class="eyebrow">History</p>
			<h1 class="hero">Your attempts</h1>
			<p class="muted">Review what you completed and how you scored.</p>
		</div>
		<div class="summary">
			<div>
				<p class="summary-value">{data?.total ?? 0}</p>
				<p class="summary-label">Total attempts</p>
			</div>
		</div>
	</section>

	{#if isLoading}
		<div class="center-state">
			<div class="spinner"></div>
			<p class="muted">Loading history...</p>
		</div>
	{:else if error}
		<div class="glass-panel error-panel">
			<div class="flex gap-2 items-center text-red-200">
				<AlertCircle class="h-5 w-5" />
				<span>{error}</span>
			</div>
			<button class="pill ghost" on:click={loadHistory}>Try again</button>
		</div>
	{:else if data && data.items.length === 0}
		<div class="glass-panel center-state">
			<BookOpenCheck class="h-10 w-10 text-emerald-300" />
			<h3 class="text-white">No history yet</h3>
			<p class="muted">Start an assignment to see it here.</p>
		</div>
	{:else if data}
		<div class="glass-panel table-card">
			<div class="table-head">
				<div class="col wide">Assignment</div>
				<div class="col">Attempt</div>
				<div class="col">Status</div>
				<div class="col">Score</div>
				<div class="col">Updated</div>
			</div>
			<div class="divider"></div>
			<div class="table-body">
				{#each data.items as item}
					<div class="row">
						<div class="col wide">
							<p class="text-white font-semibold truncate">{item.assignment_title ?? 'Ungrouped item'}</p>
							<p class="muted truncate">{item.question_text}</p>
							<div class="chips">
								<span class="chip"><Hash class="h-3 w-3" />#{item.attempt_number}</span>
								{#if item.difficulty_label}<span class="chip subtle">{item.difficulty_label}</span>{/if}
								{#if item.bloom_level}<span class="chip subtle">{item.bloom_level}</span>{/if}
							</div>
						</div>
						<div class="col">{item.attempt_number}</div>
						<div class="col status">{statusLabel(item.status)}</div>
						<div class="col score">{formatScore(item.score)}</div>
						<div class="col">{formatDate(item.updated_at || item.submitted_at)}</div>
					</div>
				{/each}
			</div>
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
	}

	.gradient-card {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1.25rem;
		background: radial-gradient(circle at 18% 18%, rgba(147, 51, 234, 0.28), transparent 32%),
			radial-gradient(circle at 82% 12%, rgba(34, 197, 235, 0.22), transparent 34%),
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

	.summary {
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

	.table-card {
		padding: 0;
	}

	.table-head,
	.table-body .row {
		display: grid;
		grid-template-columns: 1.4fr 0.6fr 0.7fr 0.7fr 0.9fr;
		align-items: center;
		gap: 0.75rem;
		padding: 12px 16px;
	}

	.table-head {
		color: rgba(255, 255, 255, 0.72);
		font-weight: 700;
		font-size: 0.95rem;
	}

	.table-body .row {
		border-bottom: 1px solid rgba(255, 255, 255, 0.06);
	}

	.table-body .row:last-child {
		border-bottom: none;
	}

	.col.wide {
		min-width: 0;
	}

	.divider {
		height: 1px;
		background: rgba(255, 255, 255, 0.08);
	}

	.status {
		text-transform: capitalize;
	}

	.score {
		font-weight: 700;
	}

	.chips {
		display: flex;
		flex-wrap: wrap;
		gap: 6px;
		margin-top: 6px;
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

	.chip.subtle {
		background: rgba(255, 255, 255, 0.04);
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

	.error-panel {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.75rem;
	}

	@keyframes spin {
		to { transform: rotate(360deg); }
	}

	@media (max-width: 900px) {
		.table-head,
		.table-body .row {
			grid-template-columns: 1fr 0.6fr 0.7fr 0.6fr 0.9fr;
			font-size: 0.95rem;
		}
	}

	@media (max-width: 720px) {
		.table-head { display: none; }
		.divider { display: none; }
		.table-body .row {
			grid-template-columns: 1fr;
			align-items: flex-start;
			gap: 8px;
			padding: 14px 16px;
		}
		.col { width: 100%; }
		.col.wide { order: -1; }
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
	:global([data-color-mode='light']) .student-shell .summary-value {
		color: #0f172a;
	}

	:global([data-color-mode='light']) .student-shell .eyebrow,
	:global([data-color-mode='light']) .student-shell .muted,
	:global([data-color-mode='light']) .student-shell .summary-label,
	:global([data-color-mode='light']) .student-shell .table-head,
	:global([data-color-mode='light']) .student-shell .status,
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

	:global([data-color-mode='light']) .student-shell .ghost {
		border-color: rgba(15, 23, 42, 0.12);
		background: rgba(15, 23, 42, 0.04);
		color: #0f172a;
	}
</style>
