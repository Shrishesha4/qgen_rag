<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { apiFetch } from '$lib/api/client';
	import { ArrowLeft, AlertCircle, Calendar, ClipboardList, Play, Pause, CheckCircle2 } from 'lucide-svelte';

	type AssignmentItem = {
		id: string;
		evaluation_item_id: string;
		sequence_number?: number;
		weight?: number;
		time_limit_override?: number | null;
	};

	type Assignment = {
		id: string;
		title: string;
		description?: string | null;
		status: string;
		subject_id?: string | null;
		topic_id?: string | null;
		cohort?: string | null;
		grade?: string | null;
		scheduled_start?: string | null;
		scheduled_end?: string | null;
		actual_start?: string | null;
		actual_end?: string | null;
		max_attempts_per_item?: number;
		time_limit_minutes?: number | null;
		shuffle_items?: boolean;
		show_feedback_immediately?: boolean;
		rubric_id?: string | null;
		passing_score?: number | null;
		item_count?: number;
		attempt_count?: number;
		items?: AssignmentItem[];
	};

	let assignment: Assignment | null = null;
	let isLoading = true;
	let error: string | null = null;

	onMount(loadAssignment);

	async function loadAssignment() {
		isLoading = true;
		error = null;
		try {
			const id = $page.params.id;
			assignment = await apiFetch<Assignment>(`/gel/assignments/${id}`);
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to load assignment';
		} finally {
			isLoading = false;
		}
	}

	async function activate() {
		if (!assignment) return;
		await apiFetch(`/gel/assignments/${assignment.id}/activate`, { method: 'POST' });
		await loadAssignment();
	}

	async function closeAssignment() {
		if (!assignment) return;
		await apiFetch(`/gel/assignments/${assignment.id}/close`, { method: 'POST' });
		await loadAssignment();
	}

	function badge(status: string) {
		switch (status) {
			case 'draft':
				return 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200';
			case 'scheduled':
				return 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200';
			case 'active':
				return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200';
			case 'closed':
				return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200';
			default:
				return 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200';
		}
	}

	function fmt(date?: string | null) {
		return date ? new Date(date).toLocaleString() : '—';
	}
</script>

<svelte:head>
	<title>GEL Assignment | Teacher Dashboard</title>
</svelte:head>

<div class="glass-panel p-6 space-y-6 border border-white/10 shadow-2xl text-slate-100">
	<div class="flex items-center space-x-3">
		<a href="/teacher/gel" class="inline-flex items-center text-sm text-rose-200 hover:underline">
			<ArrowLeft class="h-4 w-4 mr-1" /> Back to assignments
		</a>
	</div>

	{#if error}
		<div class="bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 rounded-lg p-4 flex items-center space-x-2 text-red-700 dark:text-red-300">
			<AlertCircle class="h-5 w-5" />
			<span>{error}</span>
		</div>
	{:else if isLoading}
		<div class="flex items-center justify-center py-12">
			<div class="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
		</div>
	{:else if !assignment}
		<div class="bg-white dark:bg-gray-800 rounded-lg shadow p-8 text-center">
			<p class="text-lg font-medium text-gray-900 dark:text-white">Assignment not found</p>
		</div>
	{:else}
		<div class="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
			<div>
				<p class="text-xs uppercase tracking-[0.2em] text-slate-300">GEL Assignment</p>
				<h1 class="text-3xl font-semibold text-white">{assignment.title}</h1>
				<p class="text-slate-200/85 max-w-3xl">{assignment.description || 'No description provided.'}</p>
			</div>
			<div class="flex items-center space-x-3">
				<span class={`px-3 py-1 rounded-full text-sm font-semibold ${badge(assignment.status)}`}>{assignment.status}</span>
				{#if assignment.status !== 'active'}
					<button on:click={activate} class="inline-flex items-center space-x-2 px-3 py-2 rounded-lg bg-rose-500 hover:bg-rose-400 text-white shadow-lg shadow-rose-500/20">
						<Play class="h-4 w-4" />
						<span>Activate</span>
					</button>
				{/if}
				{#if assignment.status === 'active'}
					<button on:click={closeAssignment} class="inline-flex items-center space-x-2 px-3 py-2 rounded-lg bg-white/10 text-white border border-white/10">
						<Pause class="h-4 w-4" />
						<span>Close</span>
					</button>
				{/if}
			</div>
		</div>

		<div class="grid md:grid-cols-4 gap-4">
			<div class="glass-panel border border-white/10 p-4 rounded-xl">
				<p class="text-sm text-slate-300">Cohort</p>
				<p class="text-xl font-semibold text-white">{assignment.cohort || '—'}</p>
			</div>
			<div class="glass-panel border border-white/10 p-4 rounded-xl">
				<p class="text-sm text-slate-300">Grade</p>
				<p class="text-xl font-semibold text-white">{assignment.grade || '—'}</p>
			</div>
			<div class="glass-panel border border-white/10 p-4 rounded-xl">
				<p class="text-sm text-slate-300">Items</p>
				<p class="text-xl font-semibold text-white">{assignment.item_count ?? (assignment.items?.length ?? 0)}</p>
			</div>
			<div class="glass-panel border border-white/10 p-4 rounded-xl">
				<p class="text-sm text-slate-300">Attempts</p>
				<p class="text-xl font-semibold text-white">{assignment.attempt_count ?? 0}</p>
			</div>
		</div>

		<div class="grid md:grid-cols-2 gap-6">
			<div class="glass-panel border border-white/10 rounded-xl shadow p-5 space-y-3">
				<div class="flex items-center space-x-2">
					<Calendar class="h-5 w-5 text-rose-200" />
					<h3 class="text-lg font-semibold text-white">Schedule</h3>
				</div>
				<div class="grid grid-cols-2 gap-4 text-sm text-slate-200/85">
					<div>
						<p class="font-semibold">Scheduled start</p>
						<p>{fmt(assignment.scheduled_start)}</p>
					</div>
					<div>
						<p class="font-semibold">Scheduled end</p>
						<p>{fmt(assignment.scheduled_end)}</p>
					</div>
					<div>
						<p class="font-semibold">Actual start</p>
						<p>{fmt(assignment.actual_start)}</p>
					</div>
					<div>
						<p class="font-semibold">Actual end</p>
						<p>{fmt(assignment.actual_end)}</p>
					</div>
				</div>
			</div>

			<div class="glass-panel border border-white/10 rounded-xl shadow p-5 space-y-3">
				<div class="flex items-center space-x-2">
					<ClipboardList class="h-5 w-5 text-rose-200" />
					<h3 class="text-lg font-semibold text-white">Rules</h3>
				</div>
				<div class="grid grid-cols-2 gap-4 text-sm text-slate-200/85">
					<div>
						<p class="font-semibold">Max attempts</p>
						<p>{assignment.max_attempts_per_item ?? 1}</p>
					</div>
					<div>
						<p class="font-semibold">Time limit (min)</p>
						<p>{assignment.time_limit_minutes ?? '—'}</p>
					</div>
					<div>
						<p class="font-semibold">Shuffle items</p>
						<p>{assignment.shuffle_items ? 'Yes' : 'No'}</p>
					</div>
					<div>
						<p class="font-semibold">Feedback immediately</p>
						<p>{assignment.show_feedback_immediately ? 'Yes' : 'No'}</p>
					</div>
				</div>
			</div>
		</div>

		<div class="glass-panel border border-white/10 rounded-xl shadow p-5 space-y-4">
			<div class="flex items-center justify-between">
				<h3 class="text-lg font-semibold text-white">Assigned items</h3>
				{#if (assignment.items?.length || 0) === 0}
					<span class="text-sm text-slate-300/80">Add items via the API to see them here.</span>
				{/if}
			</div>
			{#if assignment.items && assignment.items.length > 0}
				<div class="overflow-x-auto">
					<table class="min-w-full divide-y divide-white/10">
						<thead class="bg-white/5 text-slate-200">
							<tr>
								<th class="px-4 py-2 text-left text-xs font-semibold text-gray-500 dark:text-gray-300 uppercase">Sequence</th>
								<th class="px-4 py-2 text-left text-xs font-semibold text-gray-500 dark:text-gray-300 uppercase">Evaluation Item</th>
								<th class="px-4 py-2 text-left text-xs font-semibold text-gray-500 dark:text-gray-300 uppercase">Weight</th>
								<th class="px-4 py-2 text-left text-xs font-semibold text-gray-500 dark:text-gray-300 uppercase">Time limit</th>
							</tr>
						</thead>
						<tbody class="divide-y divide-white/8 bg-white/2">
							{#each assignment.items as item}
								<tr>
									<td class="px-4 py-2 text-sm text-white">{item.sequence_number ?? '—'}</td>
									<td class="px-4 py-2 text-sm text-slate-200/85">{item.evaluation_item_id}</td>
									<td class="px-4 py-2 text-sm text-slate-200/85">{item.weight ?? 1}</td>
									<td class="px-4 py-2 text-sm text-slate-200/85">{item.time_limit_override ?? '—'}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{:else}
				<div class="rounded-lg border border-dashed border-white/20 p-6 text-center text-sm text-slate-200/80">
					No items attached yet. Use the API (POST /gel/assignments/:id/items) to attach evaluation items.
				</div>
			{/if}
		</div>
	{/if}
</div>
