<script lang="ts">
	import { onMount } from 'svelte';
	import { apiFetch } from '$lib/api/client';
	import { 
		Plus, Search, Calendar, Users, MoreVertical,
		Play, Pause, Archive, Trash2, AlertCircle
	} from 'lucide-svelte';

	interface Assignment {
		id: string;
		title: string;
		description: string | null;
		status: string;
		cohort: string | null;
		grade: string | null;
		scheduled_start: string | null;
		scheduled_end: string | null;
		item_count: number;
		attempt_count: number;
		created_at: string;
	}

	let assignments: Assignment[] = [];
	let isLoading = true;
	let error: string | null = null;
	let searchQuery = '';
	let statusFilter = '';
	let showCreateModal = false;

	// Create form
	let newAssignment = {
		title: '',
		description: '',
		cohort: '',
		grade: '',
		scheduled_start: '',
		scheduled_end: '',
		max_attempts_per_item: 1,
		time_limit_minutes: null as number | null,
		shuffle_items: true,
		show_feedback_immediately: false,
	};

	onMount(async () => {
		await loadAssignments();
	});

	async function loadAssignments() {
		isLoading = true;
		error = null;
		try {
			const params = new URLSearchParams();
			if (statusFilter) params.append('status', statusFilter);
			const response = await apiFetch<{items: Assignment[]}>(`/gel/assignments?${params}`);
			assignments = response.items;
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to load assignments';
		} finally {
			isLoading = false;
		}
	}

	async function createAssignment() {
		try {
			await apiFetch('/gel/assignments', {
				method: 'POST',
				body: JSON.stringify({
					...newAssignment,
					scheduled_start: newAssignment.scheduled_start || null,
					scheduled_end: newAssignment.scheduled_end || null,
					time_limit_minutes: newAssignment.time_limit_minutes || null,
				}),
			});
			showCreateModal = false;
			resetForm();
			await loadAssignments();
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to create assignment';
		}
	}

	async function activateAssignment(id: string) {
		try {
			await apiFetch(`/gel/assignments/${id}/activate`, { method: 'POST' });
			await loadAssignments();
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to activate assignment';
		}
	}

	async function closeAssignment(id: string) {
		try {
			await apiFetch(`/gel/assignments/${id}/close`, { method: 'POST' });
			await loadAssignments();
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to close assignment';
		}
	}

	function resetForm() {
		newAssignment = {
			title: '',
			description: '',
			cohort: '',
			grade: '',
			scheduled_start: '',
			scheduled_end: '',
			max_attempts_per_item: 1,
			time_limit_minutes: null,
			shuffle_items: true,
			show_feedback_immediately: false,
		};
	}

	function getStatusBadge(status: string): string {
		switch (status) {
			case 'draft': return 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300';
			case 'scheduled': return 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300';
			case 'active': return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300';
			case 'closed': return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300';
			case 'archived': return 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300';
			default: return 'bg-gray-100 text-gray-800';
		}
	}

	$: filteredAssignments = assignments.filter(a => 
		a.title.toLowerCase().includes(searchQuery.toLowerCase())
	);
</script>

<svelte:head>
	<title>GEL Assignments | Teacher Dashboard</title>
</svelte:head>

<div class="glass-panel p-6 space-y-6 border border-white/10 shadow-2xl text-slate-100">
	<!-- Header -->
	<div class="flex items-center justify-between">
		<div>
			<p class="text-xs uppercase tracking-[0.2em] text-slate-300">GEL</p>
			<h1 class="text-3xl font-semibold text-white">Assignments</h1>
		</div>
		<button
			on:click={() => showCreateModal = true}
			class="flex items-center space-x-2 px-4 py-2 rounded-xl bg-rose-500 hover:bg-rose-400 text-white shadow-lg shadow-rose-500/20 transition"
		>
			<Plus class="h-5 w-5" />
			<span>Create Assignment</span>
		</button>
	</div>

	<!-- Filters -->
	<div class="flex items-center gap-3">
		<div class="flex-1 relative">
			<Search class="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-slate-400" />
			<input
				type="text"
				bind:value={searchQuery}
				placeholder="Search assignments..."
				class="w-full pl-10 pr-4 py-2 rounded-lg bg-white/5 border border-white/10 text-white placeholder:text-slate-400 focus:border-rose-400/60 focus:ring-0"
			/>
		</div>
		<select
			bind:value={statusFilter}
			on:change={loadAssignments}
			class="px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white focus:border-rose-400/60 focus:ring-0"
		>
			<option value="">All Status</option>
			<option value="draft">Draft</option>
			<option value="scheduled">Scheduled</option>
			<option value="active">Active</option>
			<option value="closed">Closed</option>
		</select>
	</div>

	{#if error}
		<div class="glass-panel p-4 border border-red-500/30 text-red-200 bg-red-900/20">
			<div class="flex items-center space-x-2">
				<AlertCircle class="h-5 w-5" />
				<span>{error}</span>
			</div>
		</div>
	{/if}

	{#if isLoading}
		<div class="flex items-center justify-center py-12">
			<div class="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
		</div>
	{:else if filteredAssignments.length === 0}
		<div class="glass-panel border border-white/10 rounded-xl p-10 text-center space-y-3">
			<Calendar class="h-12 w-12 text-slate-300 mx-auto" />
			<h3 class="text-xl font-semibold text-white">No assignments yet</h3>
			<p class="text-slate-300/80">Create your first assignment to get started with GEL evaluations.</p>
		</div>
	{:else}
		<div class="glass-panel border border-white/10 rounded-2xl overflow-hidden shadow-xl">
			<table class="min-w-full divide-y divide-white/10">
				<thead class="bg-white/5 text-slate-200">
					<tr>
						<th class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
							Assignment
						</th>
						<th class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
							Status
						</th>
						<th class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
							Target
						</th>
						<th class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
							Items
						</th>
						<th class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
							Attempts
						</th>
						<th class="px-6 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
							Actions
						</th>
					</tr>
				</thead>
				<tbody class="divide-y divide-white/5 bg-white/2">
					{#each filteredAssignments as assignment}
						<tr class="hover:bg-white/5 transition">
							<td class="px-6 py-4">
								<a href="/teacher/gel/assignments/{assignment.id}" class="block">
									<div class="text-sm font-semibold text-white">
										{assignment.title}
									</div>
									{#if assignment.description}
										<div class="text-xs text-slate-300/80 truncate max-w-xs">
											{assignment.description}
										</div>
									{/if}
								</a>
							</td>
							<td class="px-6 py-4">
								<span class="px-2 py-1 text-xs rounded-full {getStatusBadge(assignment.status)}">
									{assignment.status}
								</span>
							</td>
							<td class="px-6 py-4 text-sm text-slate-200/80">
								{#if assignment.cohort || assignment.grade}
									{assignment.cohort || ''} {assignment.grade || ''}
								{:else}
									All students
								{/if}
							</td>
							<td class="px-6 py-4 text-sm text-white">
								{assignment.item_count}
							</td>
							<td class="px-6 py-4 text-sm text-white">
								{assignment.attempt_count}
							</td>
							<td class="px-6 py-4 text-right">
								<div class="flex items-center justify-end space-x-2">
									{#if assignment.status === 'draft'}
										<button
											on:click={() => activateAssignment(assignment.id)}
											class="p-1 text-green-600 hover:bg-green-100 dark:hover:bg-green-900 rounded"
											title="Activate"
										>
											<Play class="h-4 w-4" />
										</button>
									{:else if assignment.status === 'active'}
										<button
											on:click={() => closeAssignment(assignment.id)}
											class="p-1 text-yellow-600 hover:bg-yellow-100 dark:hover:bg-yellow-900 rounded"
											title="Close"
										>
											<Pause class="h-4 w-4" />
										</button>
									{/if}
									<a
										href="/teacher/gel/assignments/{assignment.id}"
										class="p-1 text-gray-600 hover:bg-gray-100 dark:hover:bg-gray-700 rounded"
									>
										<MoreVertical class="h-4 w-4" />
									</a>
								</div>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}
</div>

<!-- Create Modal -->
{#if showCreateModal}
	<div class="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
		<div class="glass-panel bg-slate-900/80 border border-white/15 rounded-2xl shadow-2xl max-w-lg w-full mx-4 max-h-[90vh] overflow-y-auto">
			<div class="p-6 border-b border-white/10">
				<h2 class="text-lg font-semibold text-white">Create Assignment</h2>
			</div>
			
			<form on:submit|preventDefault={createAssignment} class="p-6 space-y-4 text-slate-100">
				<div>
					<label for="title" class="block text-sm font-semibold text-slate-200 mb-1">
						Title *
					</label>
					<input
						id="title"
						type="text"
						bind:value={newAssignment.title}
						required
						class="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/15 text-white placeholder:text-slate-400 focus:border-rose-400/60 focus:ring-0"
					/>
				</div>

				<div>
					<label for="description" class="block text-sm font-semibold text-slate-200 mb-1">
						Description
					</label>
					<textarea
						id="description"
						bind:value={newAssignment.description}
						rows="3"
						class="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/15 text-white placeholder:text-slate-400 focus:border-rose-400/60 focus:ring-0"
					></textarea>
				</div>

				<div class="grid grid-cols-2 gap-4">
					<div>
						<label for="cohort" class="block text-sm font-semibold text-slate-200 mb-1">
							Cohort
						</label>
						<input
							id="cohort"
							type="text"
							bind:value={newAssignment.cohort}
							placeholder="e.g., 2024-Spring"
							class="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/15 text-white placeholder:text-slate-400 focus:border-rose-400/60 focus:ring-0"
						/>
					</div>
					<div>
						<label for="grade" class="block text-sm font-semibold text-slate-200 mb-1">
							Grade
						</label>
						<input
							id="grade"
							type="text"
							bind:value={newAssignment.grade}
							placeholder="e.g., 10, 11, 12"
							class="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/15 text-white placeholder:text-slate-400 focus:border-rose-400/60 focus:ring-0"
						/>
					</div>
				</div>

				<div class="grid grid-cols-2 gap-4">
					<div>
						<label for="start" class="block text-sm font-semibold text-slate-200 mb-1">
							Start Date
						</label>
						<input
							id="start"
							type="datetime-local"
							bind:value={newAssignment.scheduled_start}
							class="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/15 text-white placeholder:text-slate-400 focus:border-rose-400/60 focus:ring-0"
						/>
					</div>
					<div>
						<label for="end" class="block text-sm font-semibold text-slate-200 mb-1">
							End Date
						</label>
						<input
							id="end"
							type="datetime-local"
							bind:value={newAssignment.scheduled_end}
							class="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/15 text-white placeholder:text-slate-400 focus:border-rose-400/60 focus:ring-0"
						/>
					</div>
				</div>

				<div class="grid grid-cols-2 gap-4">
					<div>
						<label for="attempts" class="block text-sm font-semibold text-slate-200 mb-1">
							Max Attempts per Item
						</label>
						<input
							id="attempts"
							type="number"
							bind:value={newAssignment.max_attempts_per_item}
							min="1"
							max="10"
							class="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/15 text-white placeholder:text-slate-400 focus:border-rose-400/60 focus:ring-0"
						/>
					</div>
					<div>
						<label for="time" class="block text-sm font-semibold text-slate-200 mb-1">
							Time Limit (minutes)
						</label>
						<input
							id="time"
							type="number"
							bind:value={newAssignment.time_limit_minutes}
							min="1"
							placeholder="No limit"
							class="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/15 text-white placeholder:text-slate-400 focus:border-rose-400/60 focus:ring-0"
						/>
					</div>
				</div>

				<div class="space-y-2">
					<label class="flex items-center space-x-2">
						<input
							type="checkbox"
							bind:checked={newAssignment.shuffle_items}
							class="rounded border-white/30 bg-white/10"
						/>
						<span class="text-sm text-slate-200">Shuffle items for each student</span>
					</label>
					<label class="flex items-center space-x-2">
						<input
							type="checkbox"
							bind:checked={newAssignment.show_feedback_immediately}
							class="rounded border-white/30 bg-white/10"
						/>
						<span class="text-sm text-slate-200">Show feedback immediately after submission</span>
					</label>
				</div>

				<div class="flex justify-end space-x-3 pt-4 border-t border-white/10">
					<button
						type="button"
						on:click={() => { showCreateModal = false; resetForm(); }}
						class="px-4 py-2 text-slate-200 hover:bg-white/5 rounded-lg"
					>
						Cancel
					</button>
					<button
						type="submit"
						class="px-4 py-2 bg-rose-500 hover:bg-rose-400 text-white rounded-lg shadow-md shadow-rose-500/20"
					>
						Create Assignment
					</button>
				</div>
			</form>
		</div>
	</div>
{/if}
