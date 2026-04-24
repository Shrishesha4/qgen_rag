<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { session } from '$lib/session';
	import {
		getSubjectsTree,
		type SubjectGroupTreeNode,
		type SubjectResponse,
		type SubjectTreeResponse
	} from '$lib/api/subjects';
	import { buildSubjectGroupMetaById, getSubjectGroupPath, matchesSubjectSearch } from '$lib/subject-group-search';

	let loading = $state(true);
	let error = $state('');
	let treeData = $state<SubjectTreeResponse | null>(null);
	let query = $state('');
	let selectedGroupId = $state<string | null>(null);
	let expandedGroups = $state<Set<string>>(new Set());
	let sortColumn = $state<'name' | 'questions' | 'pending' | 'approved' | 'rejected'>('questions');
	let sortDirection = $state<'asc' | 'desc'>('desc');

	onMount(() => {
		const unsub = session.subscribe((s) => {
			if (!s || s.user.role !== 'admin') {
				goto('/admin/login');
			}
		});
		void loadGroups();
		return unsub;
	});

	async function loadGroups() {
		loading = true;
		error = '';
		try {
			treeData = await getSubjectsTree();
			expandedGroups = new Set();
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to load groups';
		} finally {
			loading = false;
		}
	}

	function setSortColumn(column: typeof sortColumn) {
		if (sortColumn === column) {
			sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
		} else {
			sortColumn = column;
			sortDirection = 'desc';
		}
	}

	const subjectGroupMetaById = $derived.by(() => buildSubjectGroupMetaById(treeData?.groups ?? []));

	const filteredGroupsView = $derived.by(() => {
		const search = query.trim().toLowerCase();
		if (!search) return null;

		const groupedSubjects: SubjectResponse[] = [];
		function walk(groups: SubjectGroupTreeNode[]) {
			for (const group of groups) {
				groupedSubjects.push(...group.subjects);
				walk(group.children);
			}
		}
		walk(treeData?.groups ?? []);

		const filtered = groupedSubjects.filter((subject) => matchesSubjectSearch(subject, search, subjectGroupMetaById));

		const sorted = [...filtered].sort((a, b) => {
			let aVal: number | string = 0;
			let bVal: number | string = 0;

			switch (sortColumn) {
				case 'name':
					aVal = a.name;
					bVal = b.name;
					break;
				case 'questions':
					aVal = a.total_questions;
					bVal = b.total_questions;
					break;
				case 'pending':
					aVal = a.total_pending ?? 0;
					bVal = b.total_pending ?? 0;
					break;
				case 'approved':
					aVal = a.total_approved ?? 0;
					bVal = b.total_approved ?? 0;
					break;
				case 'rejected':
					aVal = a.total_rejected ?? 0;
					bVal = b.total_rejected ?? 0;
					break;
			}

			if (typeof aVal === 'string' && typeof bVal === 'string') {
				return sortDirection === 'asc' 
					? aVal.localeCompare(bVal)
					: bVal.localeCompare(aVal);
			}

			return sortDirection === 'asc' 
				? (aVal as number) - (bVal as number) 
				: (bVal as number) - (aVal as number);
		});

		return sorted;
	});

	const totals = $derived.by(() => {
		if (!treeData) {
			return { totalSubjects: 0, totalQuestions: 0, totalPending: 0, totalApproved: 0, totalRejected: 0 };
		}

		if (filteredGroupsView !== null) {
			return filteredGroupsView.reduce(
				(acc, subject) => {
					acc.totalSubjects += 1;
					acc.totalQuestions += subject.total_questions;
					acc.totalPending += subject.total_pending ?? 0;
					acc.totalApproved += subject.total_approved ?? 0;
					acc.totalRejected += subject.total_rejected ?? 0;
					return acc;
				},
				{ totalSubjects: 0, totalQuestions: 0, totalPending: 0, totalApproved: 0, totalRejected: 0 }
			);
		}

		return {
			totalSubjects: treeData.totals.total_subjects,
			totalQuestions: treeData.totals.total_questions,
			totalPending: treeData.totals.total_pending,
			totalApproved: treeData.totals.total_approved,
			totalRejected: treeData.totals.total_rejected
		};
	});

	function toggleGroup(groupId: string) {
		const next = new Set(expandedGroups);
		if (next.has(groupId)) {
			next.delete(groupId);
		} else {
			next.add(groupId);
		}
		expandedGroups = next;
	}

	function selectGroup(groupId: string, event: MouseEvent) {
		event.stopPropagation();
		selectedGroupId = selectedGroupId === groupId ? null : groupId;
	}

	function openSubject(subjectId: string) {
		goto(`/admin/subjects/${subjectId}`);
	}
</script>

<svelte:head>
	<title>Admin Groups — VQuest Trainer</title>
</svelte:head>

<div class="page">
	<div class="toolbar animate-slide-up">
		<input class="search-input" bind:value={query} placeholder="Search by subject, code, description, or group" />
	</div>

	{#if error}
		<div class="error-banner" role="alert">{error}</div>
	{/if}

	<div class="stats-row animate-slide-up">
		<div class="stat-card glass-panel">
			<span class="stat-value amber-text">{loading ? '...' : totals.totalSubjects}</span>
			<span class="stat-label">Subjects</span>
		</div>
		<div class="stat-card glass-panel">
			<span class="stat-value white-text">{loading ? '...' : totals.totalQuestions}</span>
			<span class="stat-label">Questions</span>
		</div>
		<div class="stat-card glass-panel">
			<span class="stat-value orange-text">{loading ? '...' : totals.totalPending}</span>
			<span class="stat-label">Pending</span>
		</div>
		<div class="stat-card glass-panel">
			<span class="stat-value green-text">{loading ? '...' : totals.totalApproved}</span>
			<span class="stat-label">Approved</span>
		</div>
		<div class="stat-card glass-panel">
			<span class="stat-value red-text">{loading ? '...' : totals.totalRejected}</span>
			<span class="stat-label">Rejected</span>
		</div>
	</div>

	{#if loading}
		<div class="center-state">
			<div class="spinner"></div>
			<p>Loading groups...</p>
		</div>
	{:else}
		<div class="table-shell glass-panel animate-fade-in desktop-only">
			<table class="subjects-table">
				<colgroup>
					<col class="name-col" />
					<col class="num-col" />
					<col class="num-col" />
					<col class="num-col" />
					<col class="num-col" />
				</colgroup>
				<thead>
					<tr>
						<th class="sortable" onclick={() => setSortColumn('name')}>
							Name
							{#if sortColumn === 'name'}
								<span class="sort-indicator">{sortDirection === 'asc' ? '↑' : '↓'}</span>
							{/if}
						</th>
						<th class="sortable" onclick={() => setSortColumn('questions')}>
							Questions
							{#if sortColumn === 'questions'}
								<span class="sort-indicator">{sortDirection === 'asc' ? '↑' : '↓'}</span>
							{/if}
						</th>
						<th class="sortable" onclick={() => setSortColumn('pending')}>
							Pending
							{#if sortColumn === 'pending'}
								<span class="sort-indicator">{sortDirection === 'asc' ? '↑' : '↓'}</span>
							{/if}
						</th>
						<th class="sortable" onclick={() => setSortColumn('approved')}>
							Approved
							{#if sortColumn === 'approved'}
								<span class="sort-indicator">{sortDirection === 'asc' ? '↑' : '↓'}</span>
							{/if}
						</th>
						<th class="sortable" onclick={() => setSortColumn('rejected')}>
							Rejected
							{#if sortColumn === 'rejected'}
								<span class="sort-indicator">{sortDirection === 'asc' ? '↑' : '↓'}</span>
							{/if}
						</th>
					</tr>
				</thead>
				<tbody>
					{#if filteredGroupsView !== null}
						{#if filteredGroupsView.length === 0}
							<tr>
								<td colspan="5" class="empty-cell">No grouped subjects matched your search.</td>
							</tr>
						{:else}
							{#each filteredGroupsView as subject}
								{@const groupPath = getSubjectGroupPath(subject.id, subjectGroupMetaById)}
								<tr
									class="subject-row"
									role="button"
									tabindex="0"
									onclick={() => openSubject(subject.id)}
									onkeydown={(event) => {
										if (event.key === 'Enter' || event.key === ' ') {
											event.preventDefault();
											openSubject(subject.id);
										}
									}}
								>
									<td>
										<div class="name-stack">
											<div class="name-header">
												<strong>{subject.name}</strong>
												<span class="code-chip">{subject.code}</span>
											</div>
											{#if groupPath}
												<span class="group-context">Group: {groupPath}</span>
											{/if}
										</div>
									</td>
									<td>{subject.total_questions}</td>
									<td>{subject.total_pending ?? 0}</td>
									<td class="green-text">{subject.total_approved ?? 0}</td>
									<td class="red-text">{subject.total_rejected ?? 0}</td>
								</tr>
							{/each}
						{/if}
					{:else}
						{#each treeData?.groups ?? [] as group}
							{@render groupRow(group, 0)}
						{/each}

						{#if (treeData?.groups?.length ?? 0) === 0}
							<tr>
								<td colspan="5" class="empty-cell">No groups found.</td>
							</tr>
						{/if}
					{/if}
				</tbody>
			</table>
		</div>

		<div class="subjects-mobile-list mobile-only animate-fade-in">
			{#if filteredGroupsView !== null}
				{#if filteredGroupsView.length === 0}
					<div class="subject-mobile-card glass-panel empty-cell">No grouped subjects matched your search.</div>
				{:else}
					{#each filteredGroupsView as subject}
						{@const groupPath = getSubjectGroupPath(subject.id, subjectGroupMetaById)}
						<div class="subject-mobile-card glass-panel">
							<button class="card-main" onclick={() => openSubject(subject.id)}>
								<div class="name-header">
									<span class="code-chip">{subject.code}</span>
									<strong>{subject.name}</strong>
								</div>
								{#if groupPath}
									<span class="group-context">Group: {groupPath}</span>
								{/if}
								<div class="mobile-metrics">
									<span>Questions <strong>{subject.total_questions}</strong></span>
									<span>Pending <strong>{subject.total_pending ?? 0}</strong></span>
									<span class="green-text">Approved <strong>{subject.total_approved ?? 0}</strong></span>
									<span class="red-text">Rejected <strong>{subject.total_rejected ?? 0}</strong></span>
								</div>
							</button>
						</div>
					{/each}
				{/if}
			{:else}
				{#each treeData?.groups ?? [] as group}
					{@render mobileGroupCard(group, 0)}
				{/each}
				{#if (treeData?.groups?.length ?? 0) === 0}
					<div class="subject-mobile-card glass-panel empty-cell">No groups found.</div>
				{/if}
			{/if}
		</div>
	{/if}
</div>

{#snippet groupRow(group: SubjectGroupTreeNode, depth: number)}
	<tr
		class="group-row"
		class:selected={selectedGroupId === group.id}
		onclick={(e) => {
			toggleGroup(group.id);
			selectGroup(group.id, e);
		}}
	>
		<td>
			<div class="name-stack" style="padding-left: {depth * 1.5}rem">
				<div class="name-header group-header">
					<span class="expand-icon">{expandedGroups.has(group.id) ? '▼' : '▶'}</span>
					<span class="folder-icon">📁</span>
					<strong>{group.name}</strong>
					<span class="group-count">({group.total_subjects})</span>
				</div>
			</div>
		</td>
		<td class="muted-text">{group.total_questions}</td>
		<td class="muted-text">{group.total_pending}</td>
		<td class="muted-text green-text">{group.total_approved}</td>
		<td class="muted-text red-text">{group.total_rejected}</td>
	</tr>
	{#if expandedGroups.has(group.id)}
		{#each group.children as child}
			{@render groupRow(child, depth + 1)}
		{/each}
		{#each group.subjects as subject}
			{@render subjectRow(subject, depth + 1)}
		{/each}
		{#if group.children.length === 0 && group.subjects.length === 0}
			<tr class="empty-group-row">
				<td colspan="5" style="padding-left: {(depth + 1) * 1.5 + 1}rem">
					<span class="empty-hint">Empty group</span>
				</td>
			</tr>
		{/if}
	{/if}
{/snippet}

{#snippet subjectRow(subject: SubjectResponse, depth: number)}
	<tr
		class="subject-row"
		role="button"
		tabindex="0"
		onclick={() => openSubject(subject.id)}
		onkeydown={(event) => {
			if (event.key === 'Enter' || event.key === ' ') {
				event.preventDefault();
				openSubject(subject.id);
			}
		}}
	>
		<td>
			<div class="name-stack" style="padding-left: {depth * 1.5}rem">
				<div class="name-header">
					<strong>{subject.name}</strong>
					<span class="code-chip">{subject.code}</span>
				</div>
			</div>
		</td>
		<td>{subject.total_questions}</td>
		<td>{subject.total_pending ?? 0}</td>
		<td class="green-text">{subject.total_approved ?? 0}</td>
		<td class="red-text">{subject.total_rejected ?? 0}</td>
	</tr>
{/snippet}

{#snippet mobileGroupCard(group: SubjectGroupTreeNode, depth: number)}
	<div
		class="group-mobile-card glass-panel"
		class:selected={selectedGroupId === group.id}
		style="margin-left: {depth * 0.75}rem"
		role="group"
		aria-label="Group: {group.name}"
	>
		<button class="group-header-btn" onclick={(e) => { toggleGroup(group.id); selectGroup(group.id, e); }}>
			<span class="expand-icon">{expandedGroups.has(group.id) ? '▼' : '▶'}</span>
			<span class="folder-icon">📁</span>
			<strong>{group.name}</strong>
			<span class="group-count">({group.total_subjects})</span>
		</button>
		<div class="mobile-metrics muted">
			<span>Questions <strong>{group.total_questions}</strong></span>
			<span>Pending <strong>{group.total_pending}</strong></span>
		</div>
	</div>
	{#if expandedGroups.has(group.id)}
		{#each group.children as child}
			{@render mobileGroupCard(child, depth + 1)}
		{/each}
		{#each group.subjects as subject}
			{@render mobileSubjectCard(subject, depth + 1)}
		{/each}
	{/if}
{/snippet}

{#snippet mobileSubjectCard(subject: SubjectResponse, depth: number)}
	<div class="subject-mobile-card glass-panel" style="margin-left: {depth * 0.75}rem">
		<button class="card-main" onclick={() => openSubject(subject.id)}>
			<div class="name-header">
				<span class="code-chip">{subject.code}</span>
				<strong>{subject.name}</strong>
			</div>
			<div class="mobile-metrics">
				<span>Questions <strong>{subject.total_questions}</strong></span>
				<span>Pending <strong>{subject.total_pending ?? 0}</strong></span>
				<span class="green-text">Approved <strong>{subject.total_approved ?? 0}</strong></span>
				<span class="red-text">Rejected <strong>{subject.total_rejected ?? 0}</strong></span>
			</div>
		</button>
	</div>
{/snippet}

<style>
	.page {
		max-width: 1120px;
		margin: 0 auto;
		padding: 2rem 1.5rem 2.5rem;
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}

	.toolbar {
		display: flex;
		gap: 0.75rem;
		border-radius: 1rem;
	}

	.search-input {
		width: 100%;
		padding: 0.95rem 1rem;
		border-radius: 1rem;
		border: 1px solid rgba(148, 163, 184, 0.24);
		background: rgba(255, 255, 255, 0.06);
		color: var(--theme-text);
		font: inherit;
	}

	.error-banner {
		padding: 0.9rem 1rem;
		border-radius: 1rem;
		background: rgba(239, 68, 68, 0.12);
		border: 1px solid rgba(239, 68, 68, 0.3);
		color: #fca5a5;
	}

	.stats-row {
		display: grid;
		grid-template-columns: repeat(5, minmax(0, 1fr));
		gap: 0.75rem;
	}

	.stat-card {
		padding: 1rem;
		border-radius: 1rem;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.2rem;
	}

	.stat-value {
		font-size: 1.65rem;
		font-weight: 800;
	}

	.stat-label {
		font-size: 0.72rem;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--theme-text-muted);
		font-weight: 700;
	}

	.table-shell {
		overflow: hidden;
		border-radius: 1.2rem;
	}

	.subjects-table {
		width: 100%;
		border-collapse: collapse;
	}

	.name-col {
		width: 52%;
	}

	.num-col {
		width: 12%;
	}

	.subjects-table th,
	.subjects-table td {
		padding: 0.95rem 1rem;
		border-bottom: 1px solid rgba(148, 163, 184, 0.18);
		text-align: left;
		vertical-align: middle;
	}

	.subjects-table th {
		font-size: 0.72rem;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: var(--theme-text-muted);
		background: rgba(255, 255, 255, 0.04);
	}

	.subjects-table th.sortable {
		cursor: pointer;
		user-select: none;
		transition: color 0.2s ease, background-color 0.2s ease;
		position: relative;
	}

	.subjects-table th.sortable:hover {
		color: var(--theme-text);
		background-color: rgba(255, 255, 255, 0.08);
	}

	.sort-indicator {
		margin-left: 0.35rem;
		font-size: 0.9rem;
		color: #fbbf24;
	}

	.group-row,
	.subject-row {
		transition: background 0.18s ease;
	}

	.group-row {
		cursor: pointer;
	}

	.group-row:hover,
	.subject-row:hover,
	.group-row.selected {
		background: rgba(255, 255, 255, 0.05);
	}

	.name-stack {
		display: flex;
		flex-direction: column;
		gap: 0.2rem;
	}

	.name-header {
		display: flex;
		align-items: center;
		gap: 0.55rem;
		flex-wrap: wrap;
	}

	.group-header {
		gap: 0.45rem;
	}

	.group-context,
	.empty-hint,
	.group-count,
	.muted-text {
		color: var(--theme-text-muted);
	}

	.expand-icon,
	.folder-icon {
		color: var(--theme-text-muted);
		font-size: 0.82rem;
	}

	.code-chip {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		font-size: 0.72rem;
		font-weight: 700;
		padding: 0.25rem 0.55rem;
		border-radius: 999px;
		line-height: 1;
		background: color-mix(in srgb, rgba(96, 165, 250, 0.22) 72%, var(--theme-input-bg));
		color: color-mix(in srgb, #60a5fa 78%, var(--theme-text));
	}

	.subject-row {
		cursor: pointer;
	}

	.empty-cell {
		text-align: center !important;
		color: var(--theme-text-muted);
	}

	.subjects-mobile-list {
		display: none;
		gap: 0.75rem;
	}

	.group-mobile-card,
	.subject-mobile-card {
		padding: 0.9rem;
		border-radius: 1rem;
		display: flex;
		flex-direction: column;
		gap: 0.7rem;
	}

	.group-mobile-card.selected {
		outline: 1px solid rgba(251, 191, 36, 0.35);
	}

	.group-header-btn,
	.card-main {
		padding: 0;
		border: 0;
		background: transparent;
		text-align: left;
		display: flex;
		flex-direction: column;
		gap: 0.55rem;
		color: inherit;
		font: inherit;
		cursor: pointer;
	}

	.group-header-btn {
		flex-direction: row;
		align-items: center;
		gap: 0.45rem;
		flex-wrap: wrap;
	}

	.mobile-metrics {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 0.35rem 0.7rem;
		font-size: 0.82rem;
		color: var(--theme-text-muted);
	}

	.mobile-metrics strong {
		color: var(--theme-text);
	}

	.mobile-metrics.muted strong {
		color: var(--theme-text-muted);
	}

	.center-state {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 0.8rem;
		padding: 3rem 1rem;
		text-align: center;
		color: var(--theme-text-muted);
	}

	.spinner {
		width: 30px;
		height: 30px;
		border-radius: 50%;
		border: 3px solid rgba(255,255,255,0.14);
		border-top-color: #fbbf24;
		animation: spin 0.8s linear infinite;
	}

	.amber-text { color: #f59e0b; }
	.white-text { color: var(--theme-text); }
	.orange-text { color: #fb923c; }
	.green-text { color: #34d399; }
	.red-text { color: #f87171; }

	@keyframes spin {
		to { transform: rotate(360deg); }
	}

	.desktop-only {
		display: block;
	}

	.mobile-only {
		display: none;
	}

	@media (max-width: 768px) {
		.page {
			padding: 1.35rem 0.95rem 1.85rem;
		}

		.stats-row {
			grid-template-columns: repeat(2, minmax(0, 1fr));
		}

		.desktop-only {
			display: none;
		}

		.mobile-only,
		.subjects-mobile-list {
			display: grid;
		}

		.mobile-metrics {
			grid-template-columns: 1fr;
		}
	}

	:global([data-color-mode='light']) .search-input,
	:global([data-color-mode='light']) .table-shell,
	:global([data-color-mode='light']) .group-mobile-card,
	:global([data-color-mode='light']) .subject-mobile-card,
	:global([data-color-mode='light']) .stat-card {
		background: #ffffff;
		border: 1px solid rgba(148, 163, 184, 0.28);
		box-shadow: 0 14px 34px rgba(15, 23, 42, 0.08);
	}

	:global([data-color-mode='light']) .subjects-table th,
	:global([data-color-mode='light']) .subjects-table td {
		border-bottom-color: rgba(148, 163, 184, 0.3);
	}

	:global([data-color-mode='light']) .subjects-table th {
		background: rgba(248, 250, 252, 0.95);
	}

	:global([data-color-mode='light']) .subjects-table th.sortable:hover {
		color: #0f172a;
		background-color: rgba(148, 163, 184, 0.15);
	}

	:global([data-color-mode='light']) .search-input {
		color: #0f172a;
	}

	:global([data-color-mode='light']) .code-chip {
		background: rgba(59, 130, 246, 0.14);
		color: #1d4ed8;
	}
</style>
