<script lang="ts">
	import { onMount } from 'svelte';
	import { apiFetch } from '$lib/api/client';
	import { Search, RefreshCw, AlertCircle, Plus, ClipboardCheck, ListChecks } from 'lucide-svelte';

	type EvaluationItem = {
		id: string;
		question_id: string;
		subject_id?: string | null;
		topic_id?: string | null;
		rubric_id?: string | null;
		status: string;
		difficulty_label?: string | null;
		bloom_level?: string | null;
		is_control_item?: boolean;
		control_type?: string | null;
		created_at?: string;
	};

	let items: EvaluationItem[] = [];
	let isLoading = true;
	let error: string | null = null;
	let searchQuery = '';
	let statusFilter = '';

	onMount(loadItems);

	async function loadItems() {
		isLoading = true;
		error = null;
		try {
			const params = new URLSearchParams();
			if (statusFilter) params.append('status', statusFilter);
			const response = await apiFetch<{ items: EvaluationItem[] }>(`/gel/evaluation-items?${params.toString()}`);
			items = response.items || [];
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to load evaluation items';
		} finally {
			isLoading = false;
		}
	}

	function statusBadge(status: string): string {
		switch (status) {
			case 'draft':
				return 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300';
			case 'active':
				return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200';
			case 'retired':
				return 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200';
			default:
				return 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300';
		}
	}

	function short(id: string) {
		return id ? `${id.slice(0, 6)}…${id.slice(-4)}` : '—';
	}

	$: filteredItems = items.filter((item) => {
		const q = searchQuery.toLowerCase();
		return (
			item.id.toLowerCase().includes(q) ||
			item.question_id?.toLowerCase().includes(q) ||
			(item.difficulty_label || '').toLowerCase().includes(q) ||
			(item.bloom_level || '').toLowerCase().includes(q)
		);
	});

	$: stats = {
		total: items.length,
		active: items.filter((i) => i.status === 'active').length,
		draft: items.filter((i) => i.status === 'draft').length,
		control: items.filter((i) => i.is_control_item).length,
	};

	function copyId(id: string) {
		if (!navigator?.clipboard) return;
		navigator.clipboard.writeText(id).catch(() => {});
	}
</script>

<svelte:head>
	<title>GEL Evaluation Items | Teacher Dashboard</title>
</svelte:head>

<div class="glass-panel p-6 space-y-6 border border-white/10 shadow-2xl text-slate-100">
	<div class="flex items-center justify-between">
		<div>
			<p class="text-xs uppercase tracking-[0.2em] text-slate-300">GEL</p>
			<h1 class="text-3xl font-semibold text-white">Evaluation Items</h1>
			<p class="text-slate-200/80">Review and curate items available for assignments.</p>
		</div>
		<div class="flex items-center space-x-3">
			<button
				on:click={loadItems}
				class="inline-flex items-center space-x-2 px-3 py-2 rounded-lg border border-white/15 text-white hover:bg-white/5"
			>
				<RefreshCw class="h-4 w-4" />
				<span>Refresh</span>
			</button>
			<button
				on:click={() => alert('Use the API to bulk-create evaluation items from questions.')}
				class="inline-flex items-center space-x-2 px-4 py-2 rounded-xl bg-rose-500 hover:bg-rose-400 text-white shadow-lg shadow-rose-500/20"
			>
				<Plus class="h-5 w-5" />
				<span>Create Items</span>
			</button>
		</div>
	</div>

	<div class="grid grid-cols-2 md:grid-cols-4 gap-4">
		<div class="glass-panel border border-white/10 p-4 rounded-xl">
			<div class="flex items-center justify-between text-sm text-slate-300">
				<span>Total Items</span>
				<ListChecks class="h-4 w-4" />
			</div>
			<p class="mt-2 text-2xl font-semibold text-white">{stats.total}</p>
		</div>
		<div class="glass-panel border border-white/10 p-4 rounded-xl">
			<div class="flex items-center justify-between text-sm text-slate-300">
				<span>Active</span>
				<ClipboardCheck class="h-4 w-4" />
			</div>
			<p class="mt-2 text-2xl font-semibold text-white">{stats.active}</p>
		</div>
		<div class="glass-panel border border-white/10 p-4 rounded-xl">
			<div class="flex items-center justify-between text-sm text-slate-300">
				<span>Draft</span>
				<ClipboardCheck class="h-4 w-4 rotate-45" />
			</div>
			<p class="mt-2 text-2xl font-semibold text-white">{stats.draft}</p>
		</div>
		<div class="glass-panel border border-white/10 p-4 rounded-xl">
			<div class="flex items-center justify-between text-sm text-slate-300">
				<span>Control Items</span>
				<ClipboardCheck class="h-4 w-4" />
			</div>
			<p class="mt-2 text-2xl font-semibold text-white">{stats.control}</p>
		</div>
	</div>

	<div class="flex items-center gap-3">
		<div class="flex-1 relative">
			<Search class="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-slate-400" />
			<input
				class="w-full pl-10 pr-4 py-2 rounded-lg bg-white/5 border border-white/10 text-white placeholder:text-slate-400 focus:border-rose-400/60 focus:ring-0"
				placeholder="Search by ID, difficulty, or bloom level"
				type="text"
				bind:value={searchQuery}
			/>
		</div>
		<select
			bind:value={statusFilter}
			on:change={loadItems}
			class="px-4 py-2 rounded-lg bg-white/5 border border-white/10 text-white focus:border-rose-400/60 focus:ring-0"
		>
			<option value="">All Status</option>
			<option value="draft">Draft</option>
			<option value="active">Active</option>
			<option value="retired">Retired</option>
		</select>
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
	{:else if filteredItems.length === 0}
		<div class="glass-panel border border-white/10 rounded-xl p-10 text-center space-y-2">
			<p class="text-lg font-semibold text-white">No evaluation items found</p>
			<p class="text-slate-300/80">Adjust your filters or create new items.</p>
		</div>
	{:else}
		<div class="glass-panel border border-white/10 rounded-2xl overflow-hidden shadow-xl">
			<table class="min-w-full divide-y divide-white/10">
				<thead class="bg-white/5 text-slate-200">
					<tr>
						<th class="px-6 py-3 text-left text-xs font-semibold text-gray-500 dark:text-gray-300 uppercase">Item</th>
						<th class="px-6 py-3 text-left text-xs font-semibold text-gray-500 dark:text-gray-300 uppercase">Question</th>
						<th class="px-6 py-3 text-left text-xs font-semibold text-gray-500 dark:text-gray-300 uppercase">Difficulty / Bloom</th>
						<th class="px-6 py-3 text-left text-xs font-semibold text-gray-500 dark:text-gray-300 uppercase">Status</th>
						<th class="px-6 py-3 text-left text-xs font-semibold text-gray-500 dark:text-gray-300 uppercase">Control</th>
						<th class="px-6 py-3 text-left text-xs font-semibold text-gray-500 dark:text-gray-300 uppercase">Created</th>
						<th class="px-6 py-3"></th>
					</tr>
				</thead>
				<tbody class="divide-y divide-white/8 bg-white/2">
					{#each filteredItems as item}
						<tr>
							<td class="px-6 py-4 whitespace-nowrap text-sm font-semibold text-white">{short(item.id)}</td>
							<td class="px-6 py-4 whitespace-nowrap text-sm text-slate-200/90">{short(item.question_id)}</td>
							<td class="px-6 py-4 text-sm text-slate-200/90">{item.difficulty_label || '—'} / {item.bloom_level || '—'}</td>
							<td class="px-6 py-4 whitespace-nowrap text-sm">
								<span class={`px-2 py-1 rounded-full text-xs font-semibold ${statusBadge(item.status)}`}>{item.status}</span>
							</td>
							<td class="px-6 py-4 text-sm text-slate-200/90">{item.is_control_item ? item.control_type || 'control' : '—'}</td>
							<td class="px-6 py-4 text-sm text-slate-200/90">{item.created_at ? new Date(item.created_at).toLocaleString() : '—'}</td>
							<td class="px-6 py-4 text-right text-sm">
								<button
									on:click={() => copyId(item.id)}
									class="text-rose-200 hover:underline"
								>
									Copy ID
								</button>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}
</div>
