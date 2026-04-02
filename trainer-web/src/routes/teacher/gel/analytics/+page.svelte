<script lang="ts">
	import { onMount } from 'svelte';
	import { AlertCircle, BarChart3, RefreshCw } from 'lucide-svelte';
	import { apiFetch } from '$lib/api/client';

	type GELStatistics = {
		total_evaluation_items: number;
		active_evaluation_items: number;
		total_assignments: number;
		active_assignments: number;
		total_attempts: number;
		completed_attempts: number;
		average_score: number | null;
		score_distribution: Record<string, number>;
		common_issues: { category: string; count: number }[];
		confidence_calibration: Record<string, number>;
	};

	let stats: GELStatistics | null = null;
	let isLoading = true;
	let error: string | null = null;
	let subjectId = '';
	let cohort = '';

	onMount(loadStats);

	async function loadStats() {
		isLoading = true;
		error = null;
		try {
			const params = new URLSearchParams();
			if (subjectId) params.append('subject_id', subjectId);
			if (cohort) params.append('cohort', cohort);
			stats = await apiFetch<GELStatistics>(`/gel/statistics?${params.toString()}`);
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to load analytics';
			stats = null;
		} finally {
			isLoading = false;
		}
	}

	function pct(part: number, total: number) {
		if (!total) return 0;
		return Math.round((part / total) * 100);
	}

	function maxRecordCount(record: Record<string, number>) {
		const values = Object.values(record || {});
		return values.length ? Math.max(...values) : 0;
	}

	function maxIssueCount(issues: { category: string; count: number }[]) {
		return issues.length ? Math.max(...issues.map((issue) => issue.count)) : 0;
	}

	function formatAverageScore(value: number | null) {
		return value == null ? '—' : value.toFixed(1);
	}
</script>

<svelte:head>
	<title>GEL Analytics | Teacher Dashboard</title>
</svelte:head>

<div class="gel-page">
	<section class="gel-panel gel-toolbar gel-toolbar--single-row">
		<div class="gel-toolbar__filters">
			<div class="gel-field">
				<label for="subject-filter">Subject ID</label>
				<input id="subject-filter" class="gel-input" placeholder="Filter by subject UUID" bind:value={subjectId} />
			</div>
			<div class="gel-field">
				<label for="cohort-filter">Cohort</label>
				<input id="cohort-filter" class="gel-input" placeholder="e.g. Spring-2026" bind:value={cohort} />
			</div>
		</div>
		<div class="gel-toolbar__controls">
			<button on:click={loadStats} class="gel-button gel-button--primary">
				<BarChart3 class="h-5 w-5" />
				<span>Apply Filters</span>
			</button>
		</div>
	</section>

	{#if error}
		<div class="gel-alert gel-panel">
			<AlertCircle class="h-5 w-5" />
			<span>{error}</span>
		</div>
	{:else if isLoading}
		<div class="gel-panel gel-loading">
			<div class="gel-spinner"></div>
			<p>Loading GEL analytics...</p>
		</div>
	{:else if !stats}
		<div class="gel-panel gel-empty">
			<BarChart3 class="h-12 w-12" />
			<h3>No analytics available</h3>
			<p>Create assignments and collect attempts to start seeing performance and reliability trends.</p>
		</div>
	{:else}
		<section class="gel-stat-grid">
			<div class="gel-panel gel-stat-card">
				<div class="gel-stat-card__head"><span>Evaluation Items</span></div>
				<p class="gel-stat-card__value">{stats.total_evaluation_items}</p>
				<p class="gel-stat-card__meta">{stats.active_evaluation_items} active right now</p>
			</div>
			<div class="gel-panel gel-stat-card">
				<div class="gel-stat-card__head"><span>Assignments</span></div>
				<p class="gel-stat-card__value">{stats.total_assignments}</p>
				<p class="gel-stat-card__meta">{stats.active_assignments} currently active</p>
			</div>
			<div class="gel-panel gel-stat-card">
				<div class="gel-stat-card__head"><span>Attempts</span></div>
				<p class="gel-stat-card__value">{stats.total_attempts}</p>
				<p class="gel-stat-card__meta">{stats.completed_attempts} marked complete</p>
			</div>
			<div class="gel-panel gel-stat-card">
				<div class="gel-stat-card__head"><span>Average Score</span></div>
				<p class="gel-stat-card__value">{formatAverageScore(stats.average_score)}</p>
				<p class="gel-stat-card__meta">Completed attempts only</p>
			</div>
		</section>

		<section class="gel-grid-2">
			<div class="gel-panel gel-card">
				<div class="gel-card__header">
					<h3 class="gel-card__title">Score Distribution</h3>
				</div>
				{#if Object.keys(stats.score_distribution || {}).length === 0}
					<p class="gel-card__copy">No scores have been recorded yet.</p>
				{:else}
					<div class="gel-stack">
						{#each Object.entries(stats.score_distribution) as [bucket, count]}
							<div class="gel-kv">
								<div class="gel-stat-card__head">
									<span>{bucket}</span>
									<strong>{count}</strong>
								</div>
								<div class="gel-bar-track">
									<div class="gel-bar-fill" style={`width: ${pct(count, maxRecordCount(stats.score_distribution))}%`}></div>
								</div>
							</div>
						{/each}
					</div>
				{/if}
			</div>

			<div class="gel-panel gel-card">
				<div class="gel-card__header">
					<h3 class="gel-card__title">Common Issues</h3>
				</div>
				{#if (stats.common_issues || []).length === 0}
					<p class="gel-card__copy">No issues have been logged yet.</p>
				{:else}
					<div class="gel-stack">
						{#each stats.common_issues as issue}
							<div class="gel-kv">
								<div class="gel-stat-card__head">
									<span class="capitalize">{issue.category.replace('_', ' ')}</span>
									<strong>{issue.count}</strong>
								</div>
								<div class="gel-bar-track">
									<div class="gel-bar-fill gel-bar-fill--amber" style={`width: ${pct(issue.count, maxIssueCount(stats.common_issues))}%`}></div>
								</div>
							</div>
						{/each}
					</div>
				{/if}
			</div>
		</section>

		<section class="gel-panel gel-card">
			<div class="gel-card__header">
				<h3 class="gel-card__title">Confidence Calibration</h3>
			</div>
			{#if Object.keys(stats.confidence_calibration || {}).length === 0}
				<p class="gel-card__copy">No confidence data has been captured yet.</p>
			{:else}
				<div class="gel-grid-3">
					{#each Object.entries(stats.confidence_calibration) as [label, count]}
						<div class="gel-panel gel-stat-card">
							<div class="gel-stat-card__head">
								<span class="capitalize">{label}</span>
							</div>
							<p class="gel-stat-card__value">{count}</p>
							<p class="gel-stat-card__meta">Recorded confidence selections</p>
						</div>
					{/each}
				</div>
			{/if}
		</section>
	{/if}
</div>
