<script lang="ts">
	import { onMount } from 'svelte';
	import { AlertCircle, Calendar, ClipboardList, MoreVertical, Pause, Play, Plus, Search } from 'lucide-svelte';
	import { apiFetch } from '$lib/api/client';

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

	function closeCreateModal() {
		showCreateModal = false;
		resetForm();
	}

	function handleCreateModalBackdropKeydown(event: KeyboardEvent) {
		if (event.key === 'Enter' || event.key === ' ') {
			event.preventDefault();
			closeCreateModal();
		}
	}

	function handleCreateModalWindowKeydown(event: KeyboardEvent) {
		if (showCreateModal && event.key === 'Escape') {
			event.preventDefault();
			closeCreateModal();
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

	function getStatusTone(status: string): string {
		switch (status) {
			case 'draft': return 'draft';
			case 'scheduled': return 'scheduled';
			case 'active': return 'active';
			case 'closed': return 'closed';
			case 'archived': return 'archived';
			default: return 'muted';
		}
	}

	function formatTarget(assignment: Assignment): string {
		if (assignment.cohort || assignment.grade) {
			return [assignment.cohort, assignment.grade].filter(Boolean).join(' • ');
		}
		return 'All students';
	}

	function formatDateTime(value: string | null): string {
		if (!value) return '—';
		return new Date(value).toLocaleString();
	}

	$: filteredAssignments = assignments.filter(a => 
		a.title.toLowerCase().includes(searchQuery.toLowerCase())
	);
</script>

<svelte:head>
	<title>GEL Assignments | Teacher Dashboard</title>
</svelte:head>

<svelte:window on:keydown={handleCreateModalWindowKeydown} />

<div class="gel-page">
	<section class="gel-panel gel-toolbar gel-toolbar--single-row">
		<div class="gel-toolbar__grow gel-search">
			<Search class="h-5 w-5" />
			<input class="gel-input" type="text" bind:value={searchQuery} placeholder="Search assignments" />
		</div>
		<div class="gel-toolbar__controls">
			<select class="gel-select" bind:value={statusFilter} on:change={loadAssignments}>
				<option value="">All Statuses</option>
				<option value="draft">Draft</option>
				<option value="scheduled">Scheduled</option>
				<option value="active">Active</option>
				<option value="closed">Closed</option>
			</select>
			<button on:click={() => (showCreateModal = true)} class="gel-button gel-button--primary">
				<Plus class="h-5 w-5" />
				<span>Create Assignment</span>
			</button>
		</div>
	</section>

	{#if error}
		<div class="gel-alert gel-panel">
			<AlertCircle class="h-5 w-5" />
			<span>{error}</span>
		</div>
	{/if}

	{#if isLoading}
		<div class="gel-panel gel-loading">
			<div class="gel-spinner"></div>
			<p>Loading assignments...</p>
		</div>
	{:else if filteredAssignments.length === 0}
		<div class="gel-panel gel-empty">
			<ClipboardList class="h-12 w-12" />
			<h3>No assignments yet</h3>
			<p>Create your first assignment to get started with GEL evaluation workflows.</p>
		</div>
	{:else}
		<section class="gel-panel gel-table-shell">
			<div class="gel-table-scroll">
				<table class="gel-table">
					<thead>
						<tr>
							<th>Assignment</th>
							<th>Status</th>
							<th>Audience</th>
							<th>Schedule</th>
							<th>Items</th>
							<th>Attempts</th>
							<th></th>
						</tr>
					</thead>
					<tbody>
						{#each filteredAssignments as assignment}
							<tr>
								<td>
									<a href="/teacher/gel/assignments/{assignment.id}" class="gel-table__link">
										<p class="gel-table__title">{assignment.title}</p>
										<p class="gel-table__subcopy">{assignment.description || 'No description added yet.'}</p>
									</a>
								</td>
								<td>
									<span class={`gel-status gel-status--${getStatusTone(assignment.status)}`}>
										{assignment.status}
									</span>
								</td>
								<td>
									<p class="gel-table__title">{formatTarget(assignment)}</p>
									<p class="gel-table__subcopy">
										Created {formatDateTime(assignment.created_at)}
									</p>
								</td>
								<td>
									<p class="gel-table__title">{formatDateTime(assignment.scheduled_start)}</p>
									<p class="gel-table__subcopy">Ends {formatDateTime(assignment.scheduled_end)}</p>
								</td>
								<td>{assignment.item_count}</td>
								<td>{assignment.attempt_count}</td>
								<td>
									<div class="gel-table__actions">
										{#if assignment.status === 'draft'}
											<button on:click={() => activateAssignment(assignment.id)} class="gel-button gel-button--quiet gel-button--sm" title="Activate assignment">
												<Play class="h-4 w-4" />
												<span>Activate</span>
											</button>
										{:else if assignment.status === 'active'}
											<button on:click={() => closeAssignment(assignment.id)} class="gel-button gel-button--quiet gel-button--sm" title="Close assignment">
												<Pause class="h-4 w-4" />
												<span>Close</span>
											</button>
										{/if}
										<a href="/teacher/gel/assignments/{assignment.id}" class="gel-button gel-button--quiet gel-button--sm" title="Open assignment details">
											<MoreVertical class="h-4 w-4" />
											<span>Details</span>
										</a>
									</div>
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</section>
	{/if}
</div>

<!-- Create Modal -->
{#if showCreateModal}
	<div
		class="gel-modal-backdrop"
		role="button"
		tabindex="0"
		aria-label="Close assignment modal"
		on:click|self={closeCreateModal}
		on:keydown|self={handleCreateModalBackdropKeydown}
	>
		<div class="gel-panel gel-modal" role="dialog" aria-modal="true" aria-labelledby="create-assignment-title">
			<div class="gel-modal__header">
				<h2 id="create-assignment-title" class="gel-modal__title">Create Assignment</h2>
			</div>

			<form on:submit|preventDefault={createAssignment} class="gel-stack">
				<div class="gel-field">
					<label for="title">Title</label>
					<input id="title" class="gel-input" type="text" bind:value={newAssignment.title} required />
				</div>

				<div class="gel-field">
					<label for="description">Description</label>
					<textarea id="description" class="gel-textarea" bind:value={newAssignment.description} rows="4"></textarea>
				</div>

				<div class="gel-form-grid gel-form-grid--two">
					<div class="gel-field">
						<label for="cohort">Cohort</label>
						<input id="cohort" class="gel-input" type="text" bind:value={newAssignment.cohort} placeholder="e.g. Spring-2026" />
					</div>
					<div class="gel-field">
						<label for="grade">Grade</label>
						<input id="grade" class="gel-input" type="text" bind:value={newAssignment.grade} placeholder="e.g. Year 2" />
					</div>
				</div>

				<div class="gel-form-grid gel-form-grid--two">
					<div class="gel-field">
						<label for="start">Start Date</label>
						<input id="start" class="gel-input" type="datetime-local" bind:value={newAssignment.scheduled_start} />
					</div>
					<div class="gel-field">
						<label for="end">End Date</label>
						<input id="end" class="gel-input" type="datetime-local" bind:value={newAssignment.scheduled_end} />
					</div>
				</div>

				<div class="gel-form-grid gel-form-grid--two">
					<div class="gel-field">
						<label for="attempts">Max Attempts per Item</label>
						<input id="attempts" class="gel-input" type="number" bind:value={newAssignment.max_attempts_per_item} min="1" max="10" />
					</div>
					<div class="gel-field">
						<label for="time">Time Limit (minutes)</label>
						<input id="time" class="gel-input" type="number" bind:value={newAssignment.time_limit_minutes} min="1" placeholder="No limit" />
					</div>
				</div>

				<div class="gel-stack">
					<label class="gel-check-row">
						<input type="checkbox" bind:checked={newAssignment.shuffle_items} />
						<span>Shuffle items for each student</span>
					</label>
					<label class="gel-check-row">
						<input type="checkbox" bind:checked={newAssignment.show_feedback_immediately} />
						<span>Show feedback immediately after submission</span>
					</label>
				</div>

				<div class="gel-modal__actions">
					<button type="button" on:click={closeCreateModal} class="gel-button gel-button--ghost">Cancel</button>
					<button type="submit" class="gel-button gel-button--primary">Create Assignment</button>
				</div>
			</form>
		</div>
	</div>
{/if}
