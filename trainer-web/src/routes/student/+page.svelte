<script lang="ts">
	import { onMount } from 'svelte';
	import { apiFetch } from '$lib/api/client';
	import { currentUser } from '$lib/session';
	import { 
		ClipboardCheck, Clock, CheckCircle, AlertCircle, 
		TrendingUp, Calendar, ArrowRight 
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

	let dashboard: DashboardData | null = null;
	let isLoading = true;
	let error: string | null = null;

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
		if (days <= 7) return `Due in ${days} days`;
		return date.toLocaleDateString();
	}

	function getDifficultyColor(difficulty: string | null): string {
		switch (difficulty?.toLowerCase()) {
			case 'easy': return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300';
			case 'medium': return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300';
			case 'hard': return 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300';
			default: return 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300';
		}
	}

	function getStatusColor(status: string | null): string {
		switch (status) {
			case 'scored':
			case 'reviewed': return 'text-green-600 dark:text-green-400';
			case 'in_progress': return 'text-yellow-600 dark:text-yellow-400';
			case 'submitted': return 'text-blue-600 dark:text-blue-400';
			default: return 'text-gray-600 dark:text-gray-400';
		}
	}

	$: pendingItems = dashboard?.assigned_items.filter(
		item => !item.last_attempt_status || item.last_attempt_status === 'in_progress'
	) || [];
	
	$: completedItems = dashboard?.assigned_items.filter(
		item => item.last_attempt_status === 'scored' || item.last_attempt_status === 'reviewed'
	) || [];
</script>

<svelte:head>
	<title>Student Dashboard | GELTrain</title>
</svelte:head>

<div class="space-y-6">
	<!-- Welcome Header -->
	<div class="bg-gradient-to-r from-primary-600 to-primary-700 rounded-lg shadow-lg p-6 text-white">
		<h1 class="text-2xl font-bold">
			Welcome back, {$currentUser?.full_name || $currentUser?.username}!
		</h1>
		<p class="mt-1 text-primary-100">
			Continue your learning journey by evaluating AI-generated questions.
		</p>
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
			<button
				on:click={loadDashboard}
				class="mt-2 text-sm text-red-600 dark:text-red-400 hover:underline"
			>
				Try again
			</button>
		</div>
	{:else if dashboard}
		<!-- Stats Cards -->
		<div class="grid grid-cols-2 md:grid-cols-4 gap-4">
			<div class="bg-white dark:bg-gray-800 rounded-lg shadow p-4">
				<div class="flex items-center space-x-3">
					<div class="p-2 bg-yellow-100 dark:bg-yellow-900 rounded-lg">
						<Clock class="h-6 w-6 text-yellow-600 dark:text-yellow-400" />
					</div>
					<div>
						<p class="text-2xl font-bold text-gray-900 dark:text-white">
							{dashboard.in_progress_count}
						</p>
						<p class="text-sm text-gray-500 dark:text-gray-400">In Progress</p>
					</div>
				</div>
			</div>

			<div class="bg-white dark:bg-gray-800 rounded-lg shadow p-4">
				<div class="flex items-center space-x-3">
					<div class="p-2 bg-green-100 dark:bg-green-900 rounded-lg">
						<CheckCircle class="h-6 w-6 text-green-600 dark:text-green-400" />
					</div>
					<div>
						<p class="text-2xl font-bold text-gray-900 dark:text-white">
							{dashboard.completed_count}
						</p>
						<p class="text-sm text-gray-500 dark:text-gray-400">Completed</p>
					</div>
				</div>
			</div>

			<div class="bg-white dark:bg-gray-800 rounded-lg shadow p-4">
				<div class="flex items-center space-x-3">
					<div class="p-2 bg-red-100 dark:bg-red-900 rounded-lg">
						<Calendar class="h-6 w-6 text-red-600 dark:text-red-400" />
					</div>
					<div>
						<p class="text-2xl font-bold text-gray-900 dark:text-white">
							{dashboard.due_soon_count}
						</p>
						<p class="text-sm text-gray-500 dark:text-gray-400">Due Soon</p>
					</div>
				</div>
			</div>

			<div class="bg-white dark:bg-gray-800 rounded-lg shadow p-4">
				<div class="flex items-center space-x-3">
					<div class="p-2 bg-primary-100 dark:bg-primary-900 rounded-lg">
						<TrendingUp class="h-6 w-6 text-primary-600 dark:text-primary-400" />
					</div>
					<div>
						<p class="text-2xl font-bold text-gray-900 dark:text-white">
							{dashboard.average_score !== null ? `${dashboard.average_score.toFixed(0)}%` : '-'}
						</p>
						<p class="text-sm text-gray-500 dark:text-gray-400">Avg Score</p>
					</div>
				</div>
			</div>
		</div>

		<!-- Pending Items -->
		{#if pendingItems.length > 0}
			<div class="bg-white dark:bg-gray-800 rounded-lg shadow">
				<div class="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
					<h2 class="text-lg font-semibold text-gray-900 dark:text-white flex items-center space-x-2">
						<ClipboardCheck class="h-5 w-5 text-primary-600" />
						<span>Pending Evaluations</span>
					</h2>
				</div>
				<div class="divide-y divide-gray-200 dark:divide-gray-700">
					{#each pendingItems.slice(0, 5) as item}
						<a
							href="/student/evaluate/{item.evaluation_item_id}?assignment={item.assignment_id}"
							class="block px-6 py-4 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
						>
							<div class="flex items-center justify-between">
								<div class="flex-1 min-w-0">
									<p class="text-sm font-medium text-gray-900 dark:text-white truncate">
										{item.question_text.slice(0, 100)}{item.question_text.length > 100 ? '...' : ''}
									</p>
									<div class="mt-1 flex items-center space-x-2 text-sm">
										<span class="text-gray-500 dark:text-gray-400">
											{item.assignment_title}
										</span>
										{#if item.difficulty_label}
											<span class="px-2 py-0.5 rounded-full text-xs {getDifficultyColor(item.difficulty_label)}">
												{item.difficulty_label}
											</span>
										{/if}
										{#if item.last_attempt_status === 'in_progress'}
											<span class="text-yellow-600 dark:text-yellow-400 text-xs">
												• In Progress
											</span>
										{/if}
									</div>
								</div>
								<div class="ml-4 flex items-center space-x-4">
									<span class="text-sm text-gray-500 dark:text-gray-400">
										{formatDate(item.due_date)}
									</span>
									<ArrowRight class="h-5 w-5 text-gray-400" />
								</div>
							</div>
						</a>
					{/each}
				</div>
				{#if pendingItems.length > 5}
					<div class="px-6 py-3 bg-gray-50 dark:bg-gray-700/50 border-t border-gray-200 dark:border-gray-700">
						<a
							href="/student/assignments"
							class="text-sm text-primary-600 dark:text-primary-400 hover:underline"
						>
							View all {pendingItems.length} pending items →
						</a>
					</div>
				{/if}
			</div>
		{:else}
			<div class="bg-white dark:bg-gray-800 rounded-lg shadow p-8 text-center">
				<CheckCircle class="h-12 w-12 text-green-500 mx-auto mb-4" />
				<h3 class="text-lg font-medium text-gray-900 dark:text-white">All caught up!</h3>
				<p class="mt-1 text-gray-500 dark:text-gray-400">
					You have no pending evaluations. Check back later for new assignments.
				</p>
			</div>
		{/if}

		<!-- Recent Completions -->
		{#if completedItems.length > 0}
			<div class="bg-white dark:bg-gray-800 rounded-lg shadow">
				<div class="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
					<h2 class="text-lg font-semibold text-gray-900 dark:text-white flex items-center space-x-2">
						<CheckCircle class="h-5 w-5 text-green-600" />
						<span>Recent Completions</span>
					</h2>
				</div>
				<div class="divide-y divide-gray-200 dark:divide-gray-700">
					{#each completedItems.slice(0, 3) as item}
						<a
							href="/student/history/{item.evaluation_item_id}"
							class="block px-6 py-4 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
						>
							<div class="flex items-center justify-between">
								<div class="flex-1 min-w-0">
									<p class="text-sm font-medium text-gray-900 dark:text-white truncate">
										{item.question_text.slice(0, 80)}{item.question_text.length > 80 ? '...' : ''}
									</p>
									<p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
										{item.assignment_title}
									</p>
								</div>
								<div class="ml-4 flex items-center space-x-2">
									{#if item.last_attempt_score !== null}
										<span class="text-lg font-semibold {item.last_attempt_score >= 60 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}">
											{item.last_attempt_score.toFixed(0)}%
										</span>
									{/if}
									<ArrowRight class="h-5 w-5 text-gray-400" />
								</div>
							</div>
						</a>
					{/each}
				</div>
				{#if completedItems.length > 3}
					<div class="px-6 py-3 bg-gray-50 dark:bg-gray-700/50 border-t border-gray-200 dark:border-gray-700">
						<a
							href="/student/history"
							class="text-sm text-primary-600 dark:text-primary-400 hover:underline"
						>
							View all history →
						</a>
					</div>
				{/if}
			</div>
		{/if}
	{/if}
</div>
