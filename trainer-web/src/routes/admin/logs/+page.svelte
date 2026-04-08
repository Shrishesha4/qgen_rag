<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { session } from '$lib/session';
	import {
		getActivityLogFilterOptions,
		listActivityLogs,
		type ActivityFilterOption,
		type ActivityLogFilterOptionsResponse,
		type ActivityLogSummary
	} from '$lib/api/activity';

	const PAGE_SIZE = 25;

	let loading = $state(true);
	let loadingFilters = $state(true);
	let error = $state('');
	let logs = $state<ActivityLogSummary[]>([]);
	let pagination = $state({
		page: 1,
		limit: PAGE_SIZE,
		total: 0,
		total_pages: 1
	});
	let filters = $state<ActivityLogFilterOptionsResponse>({
		actions: [],
		source_areas: [],
		actor_roles: [],
		entity_types: [],
		categories: []
	});

	let searchInput = $state('');
	let appliedSearch = $state('');
	let selectedAction = $state('');
	let selectedRole = $state('');
	let selectedSourceArea = $state('');
	let selectedEntityType = $state('');
	let selectedCategory = $state('');
	let selectedSuccess = $state<'all' | 'success' | 'failure'>('all');

	onMount(() => {
		const unsub = session.subscribe((s) => {
			if (!s || s.user.role !== 'admin') {
				goto('/admin/login');
			}
		});
		void initialize();
		return unsub;
	});

	async function initialize() {
		await Promise.all([loadFilterOptions(), loadLogs(1)]);
	}

	async function loadFilterOptions() {
		loadingFilters = true;
		try {
			filters = await getActivityLogFilterOptions();
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to load log filters';
		} finally {
			loadingFilters = false;
		}
	}

	function getSuccessFilter(): boolean | null {
		if (selectedSuccess === 'success') return true;
		if (selectedSuccess === 'failure') return false;
		return null;
	}

	async function loadLogs(page = 1) {
		loading = true;
		error = '';
		try {
			const response = await listActivityLogs({
				page,
				limit: PAGE_SIZE,
				q: appliedSearch || undefined,
				action_key: selectedAction || undefined,
				actor_role: selectedRole || undefined,
				source_area: selectedSourceArea || undefined,
				entity_type: selectedEntityType || undefined,
				category: selectedCategory || undefined,
				success: getSuccessFilter()
			});
			logs = response.items;
			pagination = response.pagination;
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to load activity logs';
		} finally {
			loading = false;
		}
	}

	async function applyFilters() {
		appliedSearch = searchInput.trim();
		await loadLogs(1);
	}

	async function clearFilters() {
		searchInput = '';
		appliedSearch = '';
		selectedAction = '';
		selectedRole = '';
		selectedSourceArea = '';
		selectedEntityType = '';
		selectedCategory = '';
		selectedSuccess = 'all';
		await loadLogs(1);
	}

	async function refreshLogs() {
		await Promise.all([loadFilterOptions(), loadLogs(pagination.page || 1)]);
	}

	async function handlePageChange(nextPage: number) {
		if (nextPage < 1 || nextPage > pagination.total_pages || nextPage === pagination.page) return;
		await loadLogs(nextPage);
	}

	function formatDate(value: string | null): string {
		if (!value) return 'Unknown time';
		return new Date(value).toLocaleString();
	}

	function formatValue(value: string | null | undefined): string {
		if (!value) return '—';
		return value
			.replace(/_/g, ' ')
			.replace(/\b\w/g, (char) => char.toUpperCase());
	}

	function actorLabel(log: ActivityLogSummary): string {
		return log.actor_name || log.actor_email || log.actor_user_id || 'Unknown user';
	}

	function targetLabel(log: ActivityLogSummary): string {
		return log.entity_name || log.topic_name || log.group_name || log.subject_name || 'Unnamed target';
	}

	function targetMeta(log: ActivityLogSummary): string[] {
		const values = [
			log.entity_type ? formatValue(log.entity_type) : '',
			log.subject_name ? `Subject: ${log.subject_name}` : '',
			log.topic_name ? `Topic: ${log.topic_name}` : '',
			log.group_name ? `Group: ${log.group_name}` : ''
		].filter(Boolean);
		return Array.from(new Set(values));
	}

	function actionOptionLabel(actionKey: string): string {
		const match = filters.actions.find((action) => action.key === actionKey);
		return match?.label || formatValue(actionKey);
	}

	function formatDetails(details: Record<string, unknown> | null): string {
		if (!details || Object.keys(details).length === 0) return '';
		return JSON.stringify(details, null, 2);
	}

	const hasActiveFilters = $derived.by(() => {
		return Boolean(
			appliedSearch ||
			selectedAction ||
			selectedRole ||
			selectedSourceArea ||
			selectedEntityType ||
			selectedCategory ||
			selectedSuccess !== 'all'
		);
	});

	const visibleRangeLabel = $derived.by(() => {
		if (pagination.total === 0) return 'No results';
		const start = (pagination.page - 1) * pagination.limit + 1;
		const end = Math.min(pagination.page * pagination.limit, pagination.total);
		return `${start}-${end} of ${pagination.total}`;
	});
</script>

<svelte:head>
	<title>Activity Logs — Admin</title>
</svelte:head>

<div class="page">
	<div class="header glass-panel">
		<div>
			<p class="eyebrow">Admin Console</p>
			<h1 class="title">Activity Logs</h1>
			<p class="subtitle">Review filterable records for subject, topic, document, generation, and vetting actions across the app.</p>
		</div>
		<div class="header-meta">
			<span class="count-pill">{visibleRangeLabel}</span>
			<button class="action-btn secondary" onclick={refreshLogs} disabled={loading || loadingFilters}>
				{loading || loadingFilters ? 'Refreshing...' : 'Refresh'}
			</button>
		</div>
	</div>

	<div class="toolbar glass-panel">
		<div class="search-row">
			<input
				class="search-input"
				type="search"
				placeholder="Search actor, action, subject, topic, group, or target"
				bind:value={searchInput}
				onkeydown={async (event) => {
					if (event.key === 'Enter') {
						event.preventDefault();
						await applyFilters();
					}
				}}
			/>
			<button class="action-btn" onclick={applyFilters} disabled={loading}>Apply Filters</button>
			<button class="action-btn secondary" onclick={clearFilters} disabled={loading && !hasActiveFilters}>Clear</button>
		</div>

		<div class="filter-grid">
			<label class="filter-field">
				<span>Action</span>
				<select bind:value={selectedAction} disabled={loadingFilters}>
					<option value="">All actions</option>
					{#each filters.actions as action}
						<option value={action.key}>{action.label}</option>
					{/each}
				</select>
			</label>
			<label class="filter-field">
				<span>Role</span>
				<select bind:value={selectedRole} disabled={loadingFilters}>
					<option value="">All roles</option>
					{#each filters.actor_roles as role}
						<option value={role}>{formatValue(role)}</option>
					{/each}
				</select>
			</label>
			<label class="filter-field">
				<span>Area</span>
				<select bind:value={selectedSourceArea} disabled={loadingFilters}>
					<option value="">All areas</option>
					{#each filters.source_areas as sourceArea}
						<option value={sourceArea}>{formatValue(sourceArea)}</option>
					{/each}
				</select>
			</label>
			<label class="filter-field">
				<span>Entity Type</span>
				<select bind:value={selectedEntityType} disabled={loadingFilters}>
					<option value="">All entities</option>
					{#each filters.entity_types as entityType}
						<option value={entityType}>{formatValue(entityType)}</option>
					{/each}
				</select>
			</label>
			<label class="filter-field">
				<span>Category</span>
				<select bind:value={selectedCategory} disabled={loadingFilters}>
					<option value="">All categories</option>
					{#each filters.categories as category}
						<option value={category}>{formatValue(category)}</option>
					{/each}
				</select>
			</label>
			<label class="filter-field">
				<span>Result</span>
				<select bind:value={selectedSuccess}>
					<option value="all">All results</option>
					<option value="success">Success</option>
					<option value="failure">Failure</option>
				</select>
			</label>
		</div>
	</div>

	{#if error}
		<div class="error-banner" role="alert">{error}</div>
	{/if}

	{#if loading}
		<div class="center-state glass-panel">
			<div class="spinner"></div>
			<p>Loading activity logs...</p>
		</div>
	{:else if logs.length === 0}
		<div class="center-state glass-panel">
			<p>{hasActiveFilters ? 'No logs matched the current filters.' : 'No activity logs recorded yet.'}</p>
		</div>
	{:else}
		<div class="log-list">
			{#each logs as log}
				<section class="log-card glass-panel" class:is-failure={!log.success}>
					<div class="log-top">
						<div class="log-heading">
							<div class="title-row">
								<h2>{log.action_label || actionOptionLabel(log.action_key)}</h2>
								<span class:status-pill={true} class:failure={!log.success} class:success={log.success}>
									{log.success ? 'Success' : 'Failed'}
								</span>
							</div>
							<p class="log-summary">
								<strong>{actorLabel(log)}</strong>
								<span>performed this action in</span>
								<strong>{log.source_area ? formatValue(log.source_area) : 'Unknown area'}</strong>
								<span>against</span>
								<strong>{targetLabel(log)}</strong>
							</p>
						</div>
						<div class="timestamp">{formatDate(log.created_at)}</div>
					</div>

					<div class="chip-row">
						<span class="meta-chip">Role: {log.actor_role ? formatValue(log.actor_role) : 'Unknown'}</span>
						<span class="meta-chip">Category: {log.category ? formatValue(log.category) : 'Uncategorized'}</span>
						<span class="meta-chip">Action: {log.action_key}</span>
						{#each targetMeta(log) as meta}
							<span class="meta-chip">{meta}</span>
						{/each}
					</div>

					<div class="details-grid">
						<div class="detail-block">
							<span class="detail-label">Target</span>
							<p>{targetLabel(log)}</p>
						</div>
						<div class="detail-block">
							<span class="detail-label">Endpoint</span>
							<p>{log.http_method || '—'} {log.endpoint || ''}</p>
						</div>
						<div class="detail-block">
							<span class="detail-label">Actor Email</span>
							<p>{log.actor_email || '—'}</p>
						</div>
						<div class="detail-block">
							<span class="detail-label">IP Address</span>
							<p>{log.ip_address || '—'}</p>
						</div>
					</div>

					{#if log.error_message}
						<div class="error-inline" role="alert">{log.error_message}</div>
					{/if}

					{#if log.details && Object.keys(log.details).length > 0}
						<details class="details-panel">
							<summary>View metadata</summary>
							<pre>{formatDetails(log.details)}</pre>
						</details>
					{/if}
				</section>
			{/each}
		</div>

		<div class="pagination glass-panel">
			<button class="action-btn secondary" onclick={() => handlePageChange(pagination.page - 1)} disabled={loading || pagination.page <= 1}>
				Previous
			</button>
			<span class="pagination-label">Page {pagination.page} of {Math.max(1, pagination.total_pages)}</span>
			<button class="action-btn secondary" onclick={() => handlePageChange(pagination.page + 1)} disabled={loading || pagination.page >= pagination.total_pages}>
				Next
			</button>
		</div>
	{/if}
</div>

<style>
	.page {
		max-width: 1180px;
		margin: 0 auto;
		padding: 2rem 1.25rem 2.25rem;
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}

	.header,
	.toolbar,
	.log-card,
	.center-state,
	.pagination {
		padding: 1rem;
		border-radius: 1rem;
	}

	.header {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		gap: 1rem;
	}

	.eyebrow {
		margin: 0;
		font-size: 0.75rem;
		font-weight: 700;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--theme-text-muted);
	}

	.title {
		margin: 0.3rem 0 0;
		font-size: 1.55rem;
		color: var(--theme-text);
	}

	.subtitle {
		margin: 0.4rem 0 0;
		color: var(--theme-text-muted);
		max-width: 60rem;
	}

	.header-meta {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		flex-wrap: wrap;
	}

	.count-pill,
	.meta-chip,
	.status-pill {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		border-radius: 999px;
		padding: 0.4rem 0.7rem;
		font-size: 0.82rem;
		font-weight: 700;
	}

	.count-pill,
	.meta-chip {
		background: rgba(255, 255, 255, 0.08);
		border: 1px solid rgba(255, 255, 255, 0.08);
		color: var(--theme-text-muted);
	}

	.toolbar {
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}

	.search-row {
		display: flex;
		gap: 0.75rem;
		flex-wrap: wrap;
	}

	.search-input,
	.filter-field select {
		width: 100%;
		border-radius: 0.85rem;
		border: 1px solid rgba(255, 255, 255, 0.12);
		background: rgba(255, 255, 255, 0.04);
		color: var(--theme-text);
		padding: 0.8rem 0.95rem;
		outline: none;
	}

	.search-input {
		flex: 1 1 24rem;
		min-width: 16rem;
	}

	.filter-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
		gap: 0.85rem;
	}

	.filter-field {
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
		font-size: 0.84rem;
		color: var(--theme-text-muted);
	}

	.action-btn {
		border: 0;
		border-radius: 0.85rem;
		padding: 0.8rem 1rem;
		font-weight: 700;
		cursor: pointer;
		background: linear-gradient(135deg, rgba(245, 158, 11, 0.95), rgba(249, 115, 22, 0.95));
		color: #1b1205;
	}

	.action-btn.secondary {
		background: rgba(255, 255, 255, 0.06);
		color: var(--theme-text);
		border: 1px solid rgba(255, 255, 255, 0.1);
	}

	.action-btn:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}

	.error-banner,
	.error-inline {
		border-radius: 0.9rem;
		padding: 0.85rem 1rem;
		background: rgba(220, 38, 38, 0.12);
		border: 1px solid rgba(248, 113, 113, 0.2);
		color: #fecaca;
	}

	.center-state {
		display: grid;
		place-items: center;
		min-height: 220px;
		text-align: center;
		color: var(--theme-text-muted);
		gap: 0.75rem;
	}

	.spinner {
		width: 36px;
		height: 36px;
		border-radius: 999px;
		border: 3px solid rgba(255, 255, 255, 0.12);
		border-top-color: rgba(245, 158, 11, 0.9);
		animation: spin 0.9s linear infinite;
	}

	.log-list {
		display: flex;
		flex-direction: column;
		gap: 0.9rem;
	}

	.log-card {
		display: flex;
		flex-direction: column;
		gap: 0.9rem;
	}

	.log-card.is-failure {
		border: 1px solid rgba(248, 113, 113, 0.18);
	}

	.log-top {
		display: flex;
		justify-content: space-between;
		gap: 1rem;
		align-items: flex-start;
	}

	.log-heading {
		display: flex;
		flex-direction: column;
		gap: 0.45rem;
	}

	.title-row {
		display: flex;
		gap: 0.65rem;
		align-items: center;
		flex-wrap: wrap;
	}

	.title-row h2 {
		margin: 0;
		font-size: 1.05rem;
		color: var(--theme-text);
	}

	.status-pill.success {
		background: rgba(34, 197, 94, 0.14);
		color: #bbf7d0;
	}

	.status-pill.failure {
		background: rgba(239, 68, 68, 0.14);
		color: #fecaca;
	}

	.log-summary {
		margin: 0;
		line-height: 1.5;
		color: var(--theme-text-muted);
	}

	.log-summary strong {
		color: var(--theme-text);
	}

	.timestamp {
		white-space: nowrap;
		font-size: 0.82rem;
		color: var(--theme-text-muted);
	}

	.chip-row {
		display: flex;
		gap: 0.5rem;
		flex-wrap: wrap;
	}

	.details-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
		gap: 0.85rem;
	}

	.detail-block {
		padding: 0.85rem 0.95rem;
		border-radius: 0.9rem;
		background: rgba(255, 255, 255, 0.04);
		border: 1px solid rgba(255, 255, 255, 0.06);
	}

	.detail-label {
		display: block;
		margin-bottom: 0.35rem;
		font-size: 0.74rem;
		font-weight: 700;
		letter-spacing: 0.04em;
		text-transform: uppercase;
		color: var(--theme-text-muted);
	}

	.detail-block p {
		margin: 0;
		color: var(--theme-text);
		word-break: break-word;
	}

	.details-panel {
		border-radius: 0.9rem;
		padding: 0.1rem 0;
	}

	.details-panel summary {
		cursor: pointer;
		font-weight: 700;
		color: var(--theme-text);
	}

	.details-panel pre {
		margin: 0.8rem 0 0;
		padding: 0.9rem;
		border-radius: 0.85rem;
		background: rgba(15, 23, 42, 0.55);
		color: #dbeafe;
		overflow-x: auto;
		font-size: 0.8rem;
		line-height: 1.45;
	}

	.pagination {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 1rem;
	}

	.pagination-label {
		color: var(--theme-text-muted);
		font-size: 0.92rem;
	}

	@keyframes spin {
		from {
			transform: rotate(0deg);
		}
		to {
			transform: rotate(360deg);
		}
	}

	@media (max-width: 720px) {
		.page {
			padding: 1.2rem 0.9rem 2rem;
		}

		.header,
		.log-top,
		.pagination {
			flex-direction: column;
			align-items: stretch;
		}

		.header-meta {
			justify-content: space-between;
		}

		.search-row {
			flex-direction: column;
		}

		.search-input {
			min-width: 0;
		}

		.timestamp {
			white-space: normal;
		}
	}
</style>