<script lang="ts">
	import { onMount } from 'svelte';
	import { AlertCircle, ClipboardCheck, ListChecks, Plus, RefreshCw, Search } from 'lucide-svelte';
	import { apiFetch } from '$lib/api/client';

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

	function statusTone(status: string): string {
		switch (status) {
			case 'draft':
				return 'draft';
			case 'active':
				return 'active';
			case 'retired':
				return 'retired';
			default:
				return 'muted';
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

	function formatCreated(value?: string) {
		return value ? new Date(value).toLocaleString() : '—';
	}
</script>

<svelte:head>
	<title>GEL Evaluation Items | Teacher Dashboard</title>
</svelte:head>

<div class="gel-page">
	<section class="gel-stat-grid">
		<div class="gel-panel gel-stat-card">
			<div class="gel-stat-card__head">
				<span>Total Items</span>
				<ListChecks class="h-4 w-4" />
			</div>
			<p class="gel-stat-card__value">{stats.total}</p>
			<p class="gel-stat-card__meta">Across the current GEL item bank</p>
		</div>
		<div class="gel-panel gel-stat-card">
			<div class="gel-stat-card__head">
				<span>Active</span>
				<ClipboardCheck class="h-4 w-4" />
			</div>
			<p class="gel-stat-card__value">{stats.active}</p>
			<p class="gel-stat-card__meta">Available to active assignment workflows</p>
		</div>
		<div class="gel-panel gel-stat-card">
			<div class="gel-stat-card__head">
				<span>Draft</span>
				<ClipboardCheck class="h-4 w-4" />
			</div>
			<p class="gel-stat-card__value">{stats.draft}</p>
			<p class="gel-stat-card__meta">Still being reviewed or curated</p>
		</div>
		<div class="gel-panel gel-stat-card">
			<div class="gel-stat-card__head">
				<span>Control Items</span>
				<ClipboardCheck class="h-4 w-4" />
			</div>
			<p class="gel-stat-card__value">{stats.control}</p>
			<p class="gel-stat-card__meta">Benchmark items used for comparison</p>
		</div>
	</section>

	<section class="gel-panel gel-toolbar gel-toolbar--single-row">
		<div class="gel-toolbar__grow gel-search">
			<Search class="h-5 w-5" />
			<input
				class="gel-input"
				placeholder="Search by item ID, question ID, difficulty, or Bloom level"
				type="text"
				bind:value={searchQuery}
			/>
		</div>
		<div class="gel-toolbar__controls">
			<select class="gel-select" bind:value={statusFilter} on:change={loadItems}>
				<option value="">All Statuses</option>
				<option value="draft">Draft</option>
				<option value="active">Active</option>
				<option value="retired">Retired</option>
			</select>
			<button on:click={loadItems} class="gel-button gel-button--ghost">
				<RefreshCw class="h-4 w-4" />
				<span>Refresh</span>
			</button>
			<button on:click={() => alert('Use the API to bulk-create evaluation items from questions.')} class="gel-button gel-button--primary">
				<Plus class="h-5 w-5" />
				<span>Create Items</span>
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
			<p>Loading evaluation items...</p>
		</div>
	{:else if filteredItems.length === 0}
		<div class="gel-panel gel-empty">
			<ListChecks class="h-12 w-12" />
			<h3>No evaluation items found</h3>
			<p>Adjust your filters or create new items to populate the bank.</p>
		</div>
	{:else}
		<section class="gel-panel gel-table-shell">
			<div class="gel-table-scroll">
				<table class="gel-table">
					<thead>
						<tr>
							<th>Item</th>
							<th>Question</th>
							<th>Difficulty / Bloom</th>
							<th>Status</th>
							<th>Control</th>
							<th>Created</th>
							<th></th>
						</tr>
					</thead>
					<tbody>
						{#each filteredItems as item}
							<tr>
								<td>
									<p class="gel-table__title">{short(item.id)}</p>
									<p class="gel-table__subcopy">Subject {short(item.subject_id || '')} • Topic {short(item.topic_id || '')}</p>
								</td>
								<td>
									<p class="gel-table__title">{short(item.question_id)}</p>
									<p class="gel-table__subcopy">Rubric {short(item.rubric_id || '')}</p>
								</td>
								<td>
									<p class="gel-table__title">{item.difficulty_label || 'Unlabelled'}</p>
									<p class="gel-table__subcopy">Bloom {item.bloom_level || 'Not set'}</p>
								</td>
								<td>
									<span class={`gel-status gel-status--${statusTone(item.status)}`}>{item.status}</span>
								</td>
								<td>
									<p class="gel-table__title">{item.is_control_item ? item.control_type || 'control' : 'No'}</p>
									<p class="gel-table__subcopy">{item.is_control_item ? 'Included in benchmarking sets' : 'Standard evaluation item'}</p>
								</td>
								<td>{formatCreated(item.created_at)}</td>
								<td>
									<div class="gel-table__actions">
										<button on:click={() => copyId(item.id)} class="gel-button gel-button--quiet gel-button--sm">Copy ID</button>
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
