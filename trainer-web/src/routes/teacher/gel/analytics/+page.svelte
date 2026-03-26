<script lang="ts">
	import { onMount } from 'svelte';
	import { apiFetch } from '$lib/api/client';
	import { BarChart3, RefreshCw, AlertCircle } from 'lucide-svelte';

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
</script>

<svelte:head>
	<title>GEL Analytics | Teacher Dashboard</title>
</svelte:head>

<div class="glass-panel p-6 space-y-6 border border-white/10 shadow-2xl text-slate-100">
	<div class="flex items-center justify-between">
		<div>
			<p class="text-xs uppercase tracking-[0.2em] text-slate-300">GEL</p>
			<h1 class="text-3xl font-semibold text-white">Analytics</h1>
			<p class="text-slate-200/80">Monitor activity, completion, and issue patterns across GEL assignments.</p>
		</div>
		<button
			on:click={loadStats}
			class="inline-flex items-center space-x-2 px-4 py-2 rounded-lg border border-white/15 text-white hover:bg-white/5"
		>
			<RefreshCw class="h-4 w-4" />
			<span>Refresh</span>
		</button>
	</div>

	<!-- svelte-ignore a11y_label_has_associated_control -->
	<div class="grid md:grid-cols-3 gap-4">
		<div class="glass-panel border border-white/10 p-4 rounded-xl">
			<label class="text-sm font-semibold text-slate-200">Subject ID (optional)</label>
			<input
				class="mt-2 w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white placeholder:text-slate-400 focus:border-rose-400/60 focus:ring-0"
				placeholder="Filter by subject UUID"
				bind:value={subjectId}
			/>
		</div>
		<div class="glass-panel border border-white/10 p-4 rounded-xl">
			<label class="text-sm font-semibold text-slate-200">Cohort (optional)</label>
			<input
				class="mt-2 w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white placeholder:text-slate-400 focus:border-rose-400/60 focus:ring-0"
				placeholder="e.g., Spring-2026"
				bind:value={cohort}
			/>
		</div>
		<div class="glass-panel border border-white/10 p-4 rounded-xl flex items-end">
			<button
				on:click={loadStats}
				class="w-full inline-flex items-center justify-center space-x-2 px-4 py-2 rounded-xl bg-rose-500 hover:bg-rose-400 text-white shadow-lg shadow-rose-500/20"
			>
				<BarChart3 class="h-5 w-5" />
				<span>Apply filters</span>
			</button>
		</div>
	</div>

	{#if error}
		<div class="glass-panel p-4 border border-red-500/30 text-red-200 bg-red-900/20 flex items-center space-x-2">
			<AlertCircle class="h-5 w-5" />
			<span>{error}</span>
		</div>
	{:else if isLoading}
		<div class="flex items-center justify-center py-12">
			<div class="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
		</div>
	{:else if !stats}
		<div class="glass-panel border border-white/10 rounded-xl p-10 text-center space-y-2">
			<p class="text-lg font-semibold text-white">No analytics available</p>
			<p class="text-slate-300/80">Create assignments and collect attempts to see insights.</p>
		</div>
	{:else}
		<div class="grid md:grid-cols-2 lg:grid-cols-4 gap-4">
			<div class="glass-panel border border-white/10 p-4 rounded-xl">
				<p class="text-sm text-slate-300">Evaluation Items</p>
				<p class="text-3xl font-semibold text-white">{stats.total_evaluation_items}</p>
				<p class="text-sm text-emerald-300/80">{stats.active_evaluation_items} active</p>
			</div>
			<div class="glass-panel border border-white/10 p-4 rounded-xl">
				<p class="text-sm text-slate-300">Assignments</p>
				<p class="text-3xl font-semibold text-white">{stats.total_assignments}</p>
				<p class="text-sm text-emerald-300/80">{stats.active_assignments} active</p>
			</div>
			<div class="glass-panel border border-white/10 p-4 rounded-xl">
				<p class="text-sm text-slate-300">Attempts</p>
				<p class="text-3xl font-semibold text-white">{stats.total_attempts}</p>
				<p class="text-sm text-indigo-200/90">{stats.completed_attempts} completed</p>
			</div>
			<div class="glass-panel border border-white/10 p-4 rounded-xl">
				<p class="text-sm text-slate-300">Average Score</p>
				<p class="text-3xl font-semibold text-white">{stats.average_score ?? '—'}</p>
				<p class="text-sm text-slate-300/80">Completed attempts only</p>
			</div>
		</div>

		<div class="grid md:grid-cols-2 gap-6">
			<div class="glass-panel border border-white/10 rounded-xl shadow p-5 space-y-4">
				<div class="flex items-center justify-between">
					<h3 class="text-lg font-semibold text-white">Score distribution</h3>
				</div>
				{#if Object.keys(stats.score_distribution || {}).length === 0}
					<p class="text-sm text-slate-300/80">No scores yet.</p>
				{:else}
					{#each Object.entries(stats.score_distribution) as [bucket, count]}
						<div class="space-y-1">
							<div class="flex justify-between text-sm text-slate-200/80">
								<span>{bucket}</span>
								<span>{count}</span>
							</div>
							<div class="w-full bg-white/10 rounded-full h-2">
								<div
									class="h-2 rounded-full bg-rose-400"
									style={`width: ${pct(count, Math.max(...Object.values(stats.score_distribution)))}%`}
								></div>
							</div>
						</div>
					{/each}
				{/if}
			</div>

			<div class="glass-panel border border-white/10 rounded-xl shadow p-5 space-y-4">
				<div class="flex items-center justify-between">
					<h3 class="text-lg font-semibold text-white">Common issues</h3>
				</div>
				{#if (stats.common_issues || []).length === 0}
					<p class="text-sm text-slate-300/80">No issues logged yet.</p>
				{:else}
					{#each stats.common_issues as issue}
						<div class="space-y-1">
							<div class="flex justify-between text-sm text-slate-200/80">
								<span class="capitalize">{issue.category.replace('_', ' ')}</span>
								<span>{issue.count}</span>
							</div>
							<div class="w-full bg-white/10 rounded-full h-2">
								<div
									class="h-2 rounded-full bg-amber-400"
									style={`width: ${pct(issue.count, Math.max(...stats.common_issues.map((i) => i.count)))}%`}
								></div>
							</div>
						</div>
					{/each}
				{/if}
			</div>
		</div>

		<div class="glass-panel border border-white/10 rounded-xl shadow p-5 space-y-3">
			<div class="flex items-center justify-between">
				<h3 class="text-lg font-semibold text-white">Confidence calibration</h3>
			</div>
			{#if Object.keys(stats.confidence_calibration || {}).length === 0}
				<p class="text-sm text-slate-300/80">No confidence data yet.</p>
			{:else}
				<div class="grid md:grid-cols-3 gap-4">
					{#each Object.entries(stats.confidence_calibration) as [label, count]}
						<div class="p-4 rounded-lg bg-white/5 border border-white/10">
							<p class="text-sm text-slate-200/80 capitalize">{label}</p>
							<p class="text-xl font-semibold text-white">{count}</p>
						</div>
					{/each}
				</div>
			{/if}
		</div>
	{/if}
</div>
