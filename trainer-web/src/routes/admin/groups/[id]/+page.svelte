<script lang="ts">
	import { get } from 'svelte/store';
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { session } from '$lib/session';
	import {
		getSubjectsTree,
		type SubjectGroupTreeNode,
		type SubjectResponse,
		type SubjectTreeResponse
	} from '$lib/api/subjects';

	type SubjectSortKey =
		| 'name'
		| 'code'
		| 'creator_username'
		| 'groupPath'
		| 'total_topics'
		| 'total_questions'
		| 'total_approved'
		| 'total_rejected'
		| 'total_pending';
	type SortDirection = 'asc' | 'desc';

	type GroupSubjectRow = SubjectResponse & {
		groupPath: string;
		depth: number;
	};

	let loading = $state(true);
	let error = $state('');
	let query = $state('');
	let treeData = $state<SubjectTreeResponse | null>(null);
	let selectedGroup = $state<SubjectGroupTreeNode | null>(null);
	let groupTrail = $state<string[]>([]);
	let sortKey = $state<SubjectSortKey>('name');
	let sortDirection = $state<SortDirection>('asc');

	onMount(() => {
		const unsub = session.subscribe((s) => {
			if (!s || s.user.role !== 'admin') {
				goto('/admin/login');
			}
		});
		void loadGroupView();
		return unsub;
	});

	async function loadGroupView() {
		loading = true;
		error = '';
		try {
			const nextTree = await getSubjectsTree();
			treeData = nextTree;
			const groupId = get(page).params.id;
			if (!groupId) {
				error = 'Group not found';
				selectedGroup = null;
				groupTrail = [];
				return;
			}
			const match = findGroup(nextTree.groups, groupId);
			if (!match) {
				error = 'Group not found';
				selectedGroup = null;
				groupTrail = [];
				return;
			}
			selectedGroup = match.node;
			groupTrail = match.trail;
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to load group';
		} finally {
			loading = false;
		}
	}

	function findGroup(
		nodes: SubjectGroupTreeNode[],
		groupId: string,
		ancestors: string[] = []
	): { node: SubjectGroupTreeNode; trail: string[] } | null {
		for (const node of nodes) {
			const nextTrail = [...ancestors, node.name];
			if (node.id === groupId) {
				return { node, trail: nextTrail };
			}
			const match = findGroup(node.children, groupId, nextTrail);
			if (match) return match;
		}
		return null;
	}

	function collectSubjects(node: SubjectGroupTreeNode, path: string[] = []): GroupSubjectRow[] {
		const currentPath = [...path, node.name];
		const currentRows = node.subjects.map((subject) => ({
			...subject,
			groupPath: currentPath.join(' / '),
			depth: currentPath.length - 1
		}));
		return [
			...currentRows,
			...node.children.flatMap((child) => collectSubjects(child, currentPath))
		];
	}

	const allSubjects = $derived.by(() => (selectedGroup ? collectSubjects(selectedGroup) : []));

	const filteredSubjects = $derived.by(() => {
		const search = query.trim().toLowerCase();
		if (!search) return allSubjects;
		return allSubjects.filter((subject) => {
			return [
				subject.name,
				subject.code,
				subject.creator_username ?? '',
				subject.groupPath
			].some((value) => value.toLowerCase().includes(search));
		});
	});

	const sortedSubjects = $derived.by(() => {
		return [...filteredSubjects].sort((left, right) => compareSubjects(left, right, sortKey, sortDirection));
	});

	function compareSubjects(
		left: GroupSubjectRow,
		right: GroupSubjectRow,
		key: SubjectSortKey,
		direction: SortDirection
	): number {
		const multiplier = direction === 'asc' ? 1 : -1;
		const leftValue = left[key] ?? '';
		const rightValue = right[key] ?? '';

		if (typeof leftValue === 'string' && typeof rightValue === 'string') {
			return leftValue.localeCompare(rightValue) * multiplier;
		}

		return ((Number(leftValue) || 0) - (Number(rightValue) || 0)) * multiplier;
	}

	function toggleSort(key: SubjectSortKey) {
		if (sortKey === key) {
			sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
			return;
		}
		sortKey = key;
		sortDirection = key === 'name' || key === 'code' || key === 'creator_username' || key === 'groupPath' ? 'asc' : 'desc';
	}

	function sortIndicator(key: SubjectSortKey): string {
		if (sortKey !== key) return '↕';
		return sortDirection === 'asc' ? '↑' : '↓';
	}

	function openSubject(subjectId: string) {
		goto(`/admin/subjects/${subjectId}`);
	}
</script>

<svelte:head>
	<title>{selectedGroup ? `${selectedGroup.name} Subjects` : 'Group Subjects'} — VQuest Trainer</title>
</svelte:head>

<div class="page">
	<div class="hero glass-panel animate-slide-up">
		<div class="hero-copy">
			<button class="back-link" type="button" onclick={() => goto('/admin/groups')}>← Back to groups</button>
			<h1 class="title">{selectedGroup?.name ?? 'Group subjects'}</h1>
			<p class="subtitle">
				{#if groupTrail.length > 0}
					{groupTrail.join(' / ')}
				{:else}
					Browse every subject nested under this group.
				{/if}
			</p>
		</div>
		{#if selectedGroup}
			<div class="hero-stats">
				<span>{selectedGroup.total_subjects} subjects</span>
				<span>{selectedGroup.total_questions} questions</span>
				<span>{selectedGroup.total_pending} pending</span>
			</div>
		{/if}
	</div>

	<div class="toolbar glass-panel animate-slide-up">
		<input class="search-input" bind:value={query} placeholder="Search by subject, code, teacher, or nested group" />
		<button class="toolbar-btn" type="button" onclick={loadGroupView}>Refresh</button>
	</div>

	{#if error}
		<div class="error-banner" role="alert">{error}</div>
	{/if}

	{#if selectedGroup}
		<div class="stats-row animate-slide-up">
			<div class="stat-card glass-panel">
				<span class="stat-value amber-text">{selectedGroup.children.length}</span>
				<span class="stat-label">Child Groups</span>
			</div>
			<div class="stat-card glass-panel">
				<span class="stat-value blue-text">{selectedGroup.subjects.length}</span>
				<span class="stat-label">Direct Subjects</span>
			</div>
			<div class="stat-card glass-panel">
				<span class="stat-value white-text">{selectedGroup.total_questions}</span>
				<span class="stat-label">Questions</span>
			</div>
			<div class="stat-card glass-panel">
				<span class="stat-value orange-text">{selectedGroup.total_pending}</span>
				<span class="stat-label">Pending</span>
			</div>
		</div>

		{#if selectedGroup.children.length > 0}
			<div class="children-panel glass-panel animate-fade-in">
				<h2 class="section-title">Nested Groups</h2>
				<div class="child-links">
					{#each selectedGroup.children as child}
						<button class="child-link" type="button" onclick={() => goto(`/admin/groups/${child.id}`)}>
							<span>{child.name}</span>
							<small>{child.total_subjects} subjects</small>
						</button>
					{/each}
				</div>
			</div>
		{/if}
	{/if}

	{#if loading}
		<div class="center-state loading-state">
			<div class="spinner"></div>
			<p>Loading group subjects…</p>
		</div>
	{:else if !selectedGroup}
		<div class="center-state glass-panel">
			<p>That group could not be found.</p>
		</div>
	{:else if sortedSubjects.length === 0}
		<div class="center-state glass-panel">
			<p>No subjects matched your search in this group.</p>
		</div>
	{:else}
		<div class="table-wrap glass-panel desktop-only animate-fade-in">
			<div class="table-scroll">
				<table class="data-table">
					<thead>
						<tr>
							<th>S.No</th>
							<th>
								<button class="sort-btn" type="button" onclick={() => toggleSort('name')}>
									Subject <span>{sortIndicator('name')}</span>
								</button>
							</th>
							<th>
								<button class="sort-btn" type="button" onclick={() => toggleSort('creator_username')}>
									Teacher <span>{sortIndicator('creator_username')}</span>
								</button>
							</th>
							<th>
								<button class="sort-btn" type="button" onclick={() => toggleSort('groupPath')}>
									Group Path <span>{sortIndicator('groupPath')}</span>
								</button>
							</th>
							<th class="num">
								<button class="sort-btn numeric" type="button" onclick={() => toggleSort('total_topics')}>
									Topics <span>{sortIndicator('total_topics')}</span>
								</button>
							</th>
							<th class="num">
								<button class="sort-btn numeric" type="button" onclick={() => toggleSort('total_questions')}>
									Questions <span>{sortIndicator('total_questions')}</span>
								</button>
							</th>
							<th class="num">
								<button class="sort-btn numeric" type="button" onclick={() => toggleSort('total_approved')}>
									Approved <span>{sortIndicator('total_approved')}</span>
								</button>
							</th>
							<th class="num">
								<button class="sort-btn numeric" type="button" onclick={() => toggleSort('total_rejected')}>
									Rejected <span>{sortIndicator('total_rejected')}</span>
								</button>
							</th>
							<th class="num">
								<button class="sort-btn numeric" type="button" onclick={() => toggleSort('total_pending')}>
									Pending <span>{sortIndicator('total_pending')}</span>
								</button>
							</th>
							<th></th>
						</tr>
					</thead>
					<tbody>
						{#each sortedSubjects as subject, index}
							<tr>
								<td class="num">{index + 1}</td>
								<td>
									<div class="subject-cell">
										<span class="subject-name">{subject.name}</span>
										<span class="subject-code">{subject.code}</span>
									</div>
								</td>
								<td>
									<div class="teacher-cell">{subject.creator_username || 'Unknown teacher'}</div>
								</td>
								<td>
									<div class="path-cell">{subject.groupPath}</div>
								</td>
								<td class="num">{subject.total_topics}</td>
								<td class="num">{subject.total_questions}</td>
								<td class="num green-text">{subject.total_approved ?? 0}</td>
								<td class="num red-text">{subject.total_rejected ?? 0}</td>
								<td class="num orange-text">{subject.total_pending ?? 0}</td>
								<td>
									<button class="open-btn" type="button" onclick={() => openSubject(subject.id)}>Open</button>
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</div>

		<div class="mobile-list mobile-only animate-fade-in">
			{#each sortedSubjects as subject}
				<div class="mobile-card glass-panel">
					<div class="subject-cell">
						<span class="subject-name">{subject.name}</span>
						<span class="subject-code">{subject.code}</span>
					</div>
					<div class="teacher-cell">{subject.creator_username || 'Unknown teacher'}</div>
					<div class="path-cell">{subject.groupPath}</div>
					<div class="mobile-metrics">
						<span>Topics <strong>{subject.total_topics}</strong></span>
						<span>Questions <strong>{subject.total_questions}</strong></span>
						<span class="green-text">Approved <strong>{subject.total_approved ?? 0}</strong></span>
						<span class="red-text">Rejected <strong>{subject.total_rejected ?? 0}</strong></span>
						<span class="orange-text">Pending <strong>{subject.total_pending ?? 0}</strong></span>
					</div>
					<button class="open-btn" type="button" onclick={() => openSubject(subject.id)}>Open Subject</button>
				</div>
			{/each}
		</div>
	{/if}
</div>

<style>
	.page {
		max-width: 1240px;
		margin: 0 auto;
		padding: 2rem 1.5rem 2.5rem;
		display: flex;
		flex-direction: column;
		gap: 1.25rem;
	}

	.hero,
	.toolbar,
	.children-panel,
	.stat-card,
	.table-wrap,
	.mobile-card {
		border-radius: 1rem;
	}

	.hero {
		padding: 1.15rem 1.1rem;
		display: flex;
		justify-content: space-between;
		gap: 1rem;
		align-items: flex-start;
	}

	.hero-copy {
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
	}

	.back-link {
		padding: 0;
		border: 0;
		background: transparent;
		color: #fbbf24;
		font: inherit;
		font-weight: 700;
		cursor: pointer;
		text-align: left;
	}

	.title {
		margin: 0;
		font-size: 1.9rem;
		font-weight: 800;
		color: var(--theme-text);
	}

	.subtitle {
		margin: 0;
		color: var(--theme-text-muted);
		line-height: 1.55;
	}

	.hero-stats {
		display: flex;
		flex-wrap: wrap;
		justify-content: flex-end;
		gap: 0.5rem;
		font-size: 0.82rem;
		color: var(--theme-text-muted);
	}

	.hero-stats span,
	.child-link {
		padding: 0.55rem 0.8rem;
		border-radius: 999px;
		border: 1px solid rgba(148, 163, 184, 0.24);
		background: rgba(255, 255, 255, 0.03);
	}

	.toolbar {
		display: flex;
		gap: 0.75rem;
		padding: 1rem;
	}

	.search-input {
		flex: 1;
		padding: 0.85rem 1rem;
		border-radius: 0.85rem;
		border: 1px solid var(--theme-glass-border);
		background: var(--theme-input-bg);
		color: var(--theme-text);
		font: inherit;
	}

	.search-input::placeholder {
		color: var(--theme-text-muted);
	}

	.toolbar-btn,
	.open-btn,
	.child-link {
		font: inherit;
		font-weight: 700;
		cursor: pointer;
	}

	.toolbar-btn,
	.open-btn {
		padding: 0.7rem 0.95rem;
		border-radius: 0.8rem;
		border: 1px solid color-mix(in srgb, var(--theme-primary) 45%, var(--theme-glass-border));
		background: color-mix(in srgb, var(--theme-primary) 16%, var(--theme-input-bg));
		color: var(--theme-text);
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
		grid-template-columns: repeat(4, minmax(0, 1fr));
		gap: 0.75rem;
	}

	.stat-card {
		padding: 1rem;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.2rem;
	}

	.stat-value {
		font-size: 1.65rem;
		font-weight: 800;
	}

	.stat-label,
	.section-title {
		font-size: 0.72rem;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--theme-text-muted);
		font-weight: 700;
	}

	.children-panel {
		padding: 1rem;
		display: flex;
		flex-direction: column;
		gap: 0.85rem;
	}

	.section-title {
		margin: 0;
	}

	.child-links {
		display: flex;
		flex-wrap: wrap;
		gap: 0.55rem;
	}

	.child-link {
		display: inline-flex;
		flex-direction: column;
		align-items: flex-start;
		gap: 0.15rem;
		color: var(--theme-text);
	}

	.child-link small {
		font-size: 0.74rem;
		color: var(--theme-text-muted);
	}

	.table-wrap {
		overflow: hidden;
	}

	.table-scroll {
		overflow: auto;
		max-height: min(70vh, 52rem);
	}

	.desktop-only {
		display: block;
	}

	.mobile-only {
		display: none;
	}

	.data-table {
		width: 100%;
		border-collapse: collapse;
		min-width: 1100px;
	}

	.data-table th,
	.data-table td {
		padding: 0.75rem 0.8rem;
		border-bottom: 1px solid rgba(148, 163, 184, 0.24);
		text-align: left;
		font-size: 0.86rem;
		background: transparent;
	}

	.data-table th {
		position: sticky;
		top: 0;
		z-index: 2;
		font-size: 0.72rem;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		font-weight: 700;
		color: var(--theme-text-muted);
		background: color-mix(in srgb, var(--theme-bg) 72%, transparent);
		backdrop-filter: blur(14px);
		-webkit-backdrop-filter: blur(14px);
	}

	.sort-btn {
		padding: 0;
		border: 0;
		background: transparent;
		color: inherit;
		font: inherit;
		font-weight: inherit;
		letter-spacing: inherit;
		text-transform: inherit;
		cursor: pointer;
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
	}

	.sort-btn.numeric {
		justify-content: flex-end;
		width: 100%;
	}

	.subject-cell {
		display: flex;
		flex-direction: column;
		gap: 0.2rem;
	}

	.subject-name {
		font-size: 0.95rem;
		font-weight: 700;
		line-height: 1.35;
		color: var(--theme-text);
	}

	.subject-code {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: fit-content;
		font-size: 0.72rem;
		font-weight: 700;
		padding: 0.25rem 0.55rem;
		border-radius: 999px;
		line-height: 1;
		background: color-mix(in srgb, rgba(96, 165, 250, 0.22) 72%, var(--theme-input-bg));
		color: color-mix(in srgb, #60a5fa 78%, var(--theme-text));
	}

	.teacher-cell,
	.path-cell {
		color: var(--theme-text-muted);
	}

	.num {
		text-align: right;
		font-variant-numeric: tabular-nums;
	}

	.mobile-list {
		display: none;
		gap: 0.75rem;
	}

	.mobile-card {
		padding: 0.9rem;
		display: flex;
		flex-direction: column;
		gap: 0.7rem;
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

	.center-state {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.8rem;
		padding: 3rem 1rem;
		text-align: center;
		color: var(--theme-text-muted);
		border-radius: 1rem;
	}

	.center-state.loading-state {
		min-height: 6rem;
		width: 100%;
		justify-content: center;
		background: transparent !important;
		border: none !important;
		box-shadow: none !important;
		backdrop-filter: none !important;
		-webkit-backdrop-filter: none !important;
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
	.blue-text { color: #60a5fa; }
	.white-text { color: var(--theme-text); }
	.orange-text { color: #fb923c; }
	.green-text { color: #34d399; }
	.red-text { color: #f87171; }

	@keyframes spin {
		to { transform: rotate(360deg); }
	}

	@media (max-width: 768px) {
		.page {
			padding: 1.35rem 0.95rem 1.85rem;
		}

		.hero,
		.toolbar {
			flex-direction: column;
		}

		.hero-stats {
			justify-content: flex-start;
		}

		.desktop-only {
			display: none;
		}

		.mobile-only,
		.mobile-list {
			display: grid;
		}

		.mobile-metrics {
			grid-template-columns: 1fr;
		}
	}

	@media (max-width: 640px) {
		.stats-row {
			grid-template-columns: repeat(2, minmax(0, 1fr));
		}
	}

	:global([data-color-mode='light']) .search-input {
		background: #ffffff;
		border-color: rgba(148, 163, 184, 0.42);
		color: #0f172a;
	}

	:global([data-color-mode='light']) .hero,
	:global([data-color-mode='light']) .toolbar,
	:global([data-color-mode='light']) .children-panel,
	:global([data-color-mode='light']) .stat-card,
	:global([data-color-mode='light']) .center-state.glass-panel,
	:global([data-color-mode='light']) .table-wrap,
	:global([data-color-mode='light']) .mobile-card {
		background: #ffffff;
		border: 1px solid rgba(148, 163, 184, 0.3);
		box-shadow: 0 14px 34px rgba(15, 23, 42, 0.08);
	}

	:global([data-color-mode='light']) .data-table th,
	:global([data-color-mode='light']) .data-table td {
		border-bottom-color: rgba(148, 163, 184, 0.35);
	}

	:global([data-color-mode='light']) .data-table th {
		background: rgba(255, 255, 255, 0.92);
	}

	:global([data-color-mode='light']) .toolbar-btn,
	:global([data-color-mode='light']) .open-btn,
	:global([data-color-mode='light']) .child-link {
		color: #0f172a;
	}

	:global([data-color-mode='light']) .subject-code {
		background: rgba(59, 130, 246, 0.14);
		color: #1d4ed8;
	}
</style>