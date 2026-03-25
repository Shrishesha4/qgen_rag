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

<div class="space-y-6">
	<div class="flex items-center justify-between">
		<h1 class="text-2xl font-bold text-gray-900 dark:text-white">Your Assignments</h1>
	</div>

	{#if isLoading}
		<div class="flex items-center justify-center py-12">
			<div class="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
		</div>
	{:else if error}
		<div class="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
			<div class="flex items-center space-x-2 text-red-700 dark:text-red-400">
				<AlertCircle class="h-5 w-5" />
				<span>{error}</span>
			</div>
		</div>
	{:else if assignments.length === 0}
		<div class="bg-white dark:bg-gray-800 rounded-lg shadow p-8 text-center">
			<ClipboardCheck class="h-12 w-12 text-gray-400 mx-auto mb-4" />
			<h3 class="text-lg font-medium text-gray-900 dark:text-white">No assignments yet</h3>
			<p class="mt-1 text-gray-500 dark:text-gray-400">
				Check back later for new assignments from your teachers.
			</p>
		</div>
	{:else}
		<div class="grid gap-4">
			{#each assignments as assignment}
				{@const remaining = getDaysRemaining(assignment.scheduled_end)}
				<a
					href="/student/assignments/{assignment.id}"
					class="block bg-white dark:bg-gray-800 rounded-lg shadow hover:shadow-md transition-shadow"
				>
					<div class="p-6">
						<div class="flex items-start justify-between">
							<div class="flex-1">
								<h3 class="text-lg font-semibold text-gray-900 dark:text-white">
									{assignment.title}
								</h3>
								{#if assignment.description}
									<p class="mt-1 text-sm text-gray-500 dark:text-gray-400 line-clamp-2">
										{assignment.description}
									</p>
								{/if}
								
								<div class="mt-4 flex items-center space-x-4 text-sm">
									<div class="flex items-center space-x-1 text-gray-500 dark:text-gray-400">
										<ClipboardCheck class="h-4 w-4" />
										<span>{assignment.attempts_made} / {assignment.item_count} completed</span>
									</div>
									<div class="flex items-center space-x-1 {remaining.urgent ? 'text-red-600 dark:text-red-400' : 'text-gray-500 dark:text-gray-400'}">
										<Clock class="h-4 w-4" />
										<span>{remaining.text}</span>
									</div>
								</div>
							</div>
							
							<div class="ml-4 flex items-center">
								<div class="text-right mr-4">
									<div class="text-2xl font-bold text-primary-600 dark:text-primary-400">
										{Math.round((assignment.attempts_made / assignment.item_count) * 100)}%
									</div>
									<div class="text-xs text-gray-500 dark:text-gray-400">complete</div>
								</div>
								<ArrowRight class="h-6 w-6 text-gray-400" />
							</div>
						</div>
						
						<!-- Progress bar -->
						<div class="mt-4 h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
							<div
								class="h-full bg-primary-600 rounded-full transition-all"
								style="width: {(assignment.attempts_made / assignment.item_count) * 100}%"
							></div>
						</div>
					</div>
				</a>
			{/each}
		</div>
	{/if}
</div>
