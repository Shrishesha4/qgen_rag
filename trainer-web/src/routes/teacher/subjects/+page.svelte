<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { session } from '$lib/session';
	import {
		createSubject,
		createGroup,
		getSubjectsTree,
		moveSubject,
		moveGroup,
		deleteGroup,
		type SubjectResponse,
		type SubjectGroupTreeNode,
		type SubjectTreeResponse
	} from '$lib/api/subjects';

	let loading = $state(true);
	let error = $state('');
	let treeData = $state<SubjectTreeResponse | null>(null);
	let query = $state('');
	
	// Add subject state
	let addingSubject = $state(false);
	let draftCode = $state('');
	let draftName = $state('');
	let savingSubject = $state(false);
	let addSubjectError = $state('');
	
	// Add group state
	let addingGroup = $state(false);
	let draftGroupName = $state('');
	let savingGroup = $state(false);
	let addGroupError = $state('');
	
	// Selection and expansion state
	let selectedGroupId = $state<string | null>(null);
	let expandedGroups = $state<Set<string>>(new Set());
	
	// Move modal state
	let showMoveModal = $state(false);
	let moveTargetType = $state<'subject' | 'group'>('subject');
	let moveTargetId = $state<string>('');
	let moveTargetName = $state<string>('');
	let movingItem = $state(false);
	
	// Drag state
	let draggedItem = $state<{ type: 'subject' | 'group'; id: string; name: string } | null>(null);
	let dragOverGroupId = $state<string | null>(null);
	let dragOverRoot = $state(false);
	
	// Context menu state
	let contextMenuGroupId = $state<string | null>(null);
	let contextMenuPosition = $state<{ x: number; y: number } | null>(null);

	onMount(() => {
		const unsub = session.subscribe((s) => {
			if (!s || s.user.role !== 'teacher') {
				goto('/teacher/login');
			}
		});
		void loadTree();
		return unsub;
	});

	async function loadTree() {
		loading = true;
		error = '';
		try {
			treeData = await getSubjectsTree();
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to load subjects';
		} finally {
			loading = false;
		}
	}

	// Flatten tree for search
	function flattenSubjects(groups: SubjectGroupTreeNode[], ungrouped: SubjectResponse[]): SubjectResponse[] {
		const result: SubjectResponse[] = [...ungrouped];
		function traverse(group: SubjectGroupTreeNode) {
			result.push(...group.subjects);
			group.children.forEach(traverse);
		}
		groups.forEach(traverse);
		return result;
	}

	const allSubjects = $derived.by(() => {
		if (!treeData) return [];
		return flattenSubjects(treeData.groups, treeData.ungrouped_subjects);
	});

	const filteredSubjects = $derived.by(() => {
		const search = query.trim().toLowerCase();
		if (!search) return null; // null means show tree view
		return allSubjects.filter((subject) => {
			return [subject.name, subject.code, subject.description ?? ''].some((value) =>
				value.toLowerCase().includes(search)
			);
		});
	});

	const totals = $derived.by(() => {
		if (!treeData) return { totalSubjects: 0, totalQuestions: 0, totalPending: 0, totalApproved: 0, totalRejected: 0 };
		return {
			totalSubjects: treeData.totals.total_subjects,
			totalQuestions: treeData.totals.total_questions,
			totalPending: treeData.totals.total_pending,
			totalApproved: treeData.totals.total_approved,
			totalRejected: treeData.totals.total_rejected,
		};
	});

	function openSubject(subjectId: string) {
		goto(`/teacher/subjects/${subjectId}`);
	}

	function toggleGroup(groupId: string) {
		const newSet = new Set(expandedGroups);
		if (newSet.has(groupId)) {
			newSet.delete(groupId);
		} else {
			newSet.add(groupId);
		}
		expandedGroups = newSet;
	}

	function selectGroup(groupId: string, event: MouseEvent) {
		event.stopPropagation();
		selectedGroupId = selectedGroupId === groupId ? null : groupId;
	}

	// Context menu handlers
	function showContextMenu(event: MouseEvent, groupId: string) {
		event.preventDefault();
		event.stopPropagation();
		
		// Calculate position with viewport boundary detection
		const menuWidth = 180; // min-width from CSS
		const menuHeight = 100; // approximate height
		const padding = 8;
		const offset = 4; // Small offset from cursor
		
		let x = event.clientX + offset;
		let y = event.clientY + offset;
		
		// Prevent overflow on right
		if (x + menuWidth + padding > window.innerWidth) {
			x = event.clientX - menuWidth - offset;
		}
		
		// Prevent overflow on bottom
		if (y + menuHeight + padding > window.innerHeight) {
			y = event.clientY - menuHeight - offset;
		}
		
		// Prevent overflow on left
		if (x < padding) {
			x = padding;
		}
		
		// Prevent overflow on top
		if (y < padding) {
			y = padding;
		}
		
		// Set state after calculating position
		contextMenuGroupId = groupId;
		contextMenuPosition = { x, y };
		
		console.log('Context menu opened:', { groupId, x, y, clientX: event.clientX, clientY: event.clientY });
	}

	function hideContextMenu() {
		contextMenuGroupId = null;
		contextMenuPosition = null;
	}

	function handleContextMenuMove(groupId: string, groupName: string) {
		hideContextMenu();
		openMoveModal('group', groupId, groupName);
	}

	function handleContextMenuDelete(groupId: string, groupName: string) {
		hideContextMenu();
		handleDeleteGroup(groupId, groupName);
	}

	// Add Subject
	function startAddSubject() {
		if (savingSubject) return;
		addingSubject = true;
		addSubjectError = '';
	}

	function cancelAddSubject() {
		if (savingSubject) return;
		addingSubject = false;
		draftCode = '';
		draftName = '';
		addSubjectError = '';
	}

	async function saveAddSubject() {
		if (savingSubject) return;
		const code = draftCode.trim().toUpperCase();
		const name = draftName.trim();
		if (!code || !name) {
			addSubjectError = 'Enter both subject code and name.';
			return;
		}

		savingSubject = true;
		addSubjectError = '';
		try {
			const newSubject = await createSubject({ code, name });
			// If a group is selected, move the subject to that group
			if (selectedGroupId) {
				await moveSubject(newSubject.id, selectedGroupId);
			}
			addingSubject = false;
			draftCode = '';
			draftName = '';
			await loadTree();
		} catch (e: unknown) {
			addSubjectError = e instanceof Error ? e.message : 'Failed to create subject';
		} finally {
			savingSubject = false;
		}
	}

	// Add Group
	function startAddGroup() {
		if (savingGroup) return;
		addingGroup = true;
		addGroupError = '';
	}

	function cancelAddGroup() {
		if (savingGroup) return;
		addingGroup = false;
		draftGroupName = '';
		addGroupError = '';
	}

	async function saveAddGroup() {
		if (savingGroup) return;
		const name = draftGroupName.trim();
		if (!name) {
			addGroupError = 'Enter a group name.';
			return;
		}

		savingGroup = true;
		addGroupError = '';
		try {
			await createGroup({ name, parent_id: selectedGroupId });
			addingGroup = false;
			draftGroupName = '';
			// Expand parent if creating subgroup
			if (selectedGroupId) {
				expandedGroups = new Set([...expandedGroups, selectedGroupId]);
			}
			await loadTree();
		} catch (e: unknown) {
			addGroupError = e instanceof Error ? e.message : 'Failed to create group';
		} finally {
			savingGroup = false;
		}
	}

	// Move Modal
	function openMoveModal(type: 'subject' | 'group', id: string, name: string) {
		moveTargetType = type;
		moveTargetId = id;
		moveTargetName = name;
		showMoveModal = true;
	}

	function closeMoveModal() {
		showMoveModal = false;
		moveTargetId = '';
		moveTargetName = '';
	}

	async function handleMoveToGroup(groupId: string | null) {
		if (movingItem) return;
		movingItem = true;
		try {
			if (moveTargetType === 'subject') {
				await moveSubject(moveTargetId, groupId);
			} else {
				await moveGroup(moveTargetId, groupId);
			}
			closeMoveModal();
			await loadTree();
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to move item';
		} finally {
			movingItem = false;
		}
	}

	// Drag and Drop
	function handleDragStart(event: DragEvent, type: 'subject' | 'group', id: string, name: string) {
		draggedItem = { type, id, name };
		if (event.dataTransfer) {
			event.dataTransfer.effectAllowed = 'move';
			event.dataTransfer.setData('text/plain', id);
		}
	}

	function handleDragEnd() {
		draggedItem = null;
		dragOverGroupId = null;
		dragOverRoot = false;
	}

	function handleDragOver(event: DragEvent, groupId: string | null) {
		event.preventDefault();
		if (!draggedItem) return;
		// Prevent dropping group into itself or its descendants
		if (draggedItem.type === 'group' && draggedItem.id === groupId) return;
		if (groupId === null) {
			dragOverRoot = true;
			dragOverGroupId = null;
		} else {
			dragOverGroupId = groupId;
			dragOverRoot = false;
		}
	}

	function handleDragLeave() {
		dragOverGroupId = null;
		dragOverRoot = false;
	}

	async function handleDrop(event: DragEvent, targetGroupId: string | null) {
		event.preventDefault();
		if (!draggedItem) return;
		
		// Prevent dropping group into itself
		if (draggedItem.type === 'group' && draggedItem.id === targetGroupId) {
			handleDragEnd();
			return;
		}

		try {
			if (draggedItem.type === 'subject') {
				await moveSubject(draggedItem.id, targetGroupId);
			} else {
				await moveGroup(draggedItem.id, targetGroupId);
			}
			await loadTree();
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to move item';
		} finally {
			handleDragEnd();
		}
	}

	// Delete group
	async function handleDeleteGroup(groupId: string, groupName: string) {
		if (!confirm(`Delete group "${groupName}"? Subjects will be moved to root.`)) return;
		try {
			await deleteGroup(groupId, true);
			if (selectedGroupId === groupId) selectedGroupId = null;
			await loadTree();
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to delete group';
		}
	}

	// Get all groups for move modal
	function getAllGroups(groups: SubjectGroupTreeNode[]): { id: string; name: string; depth: number }[] {
		const result: { id: string; name: string; depth: number }[] = [];
		function traverse(group: SubjectGroupTreeNode, depth: number) {
			result.push({ id: group.id, name: group.name, depth });
			group.children.forEach(c => traverse(c, depth + 1));
		}
		groups.forEach(g => traverse(g, 0));
		return result;
	}

	// Find group by ID in tree
	function findGroupById(groups: SubjectGroupTreeNode[], id: string): SubjectGroupTreeNode | null {
		for (const group of groups) {
			if (group.id === id) return group;
			const found = findGroupById(group.children, id);
			if (found) return found;
		}
		return null;
	}
</script>

<svelte:head>
	<title>Subjects - Teacher Console</title>
</svelte:head>

<div class="page">
	<div class="hero animate-fade-in">
		<div>
			<p class="eyebrow">Teacher Console</p>
			<h1 class="title font-serif">Subjects</h1>
		</div>
		<div class="hero-actions">
			{#if selectedGroupId}
				<button class="add-btn" onclick={startAddSubject} disabled={savingSubject || addingSubject}>+ Add Subject</button>
				<button class="add-btn secondary" onclick={startAddGroup} disabled={savingGroup || addingGroup}>+ Add Subgroup</button>
			{:else}
				<button class="add-btn secondary" onclick={startAddGroup} disabled={savingGroup || addingGroup}>+ Add Group</button>
			{/if}
		</div>
	</div>

	<div class="toolbar animate-slide-up">
		<input class="search-input" bind:value={query} placeholder="Search by subject, code, or description" />
	</div>

	{#if error}
		<div class="error-banner" role="alert">{error}</div>
	{/if}

	{#if addSubjectError}
		<div class="error-banner" role="alert">{addSubjectError}</div>
	{/if}

	{#if addGroupError}
		<div class="error-banner" role="alert">{addGroupError}</div>
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
			<p>Loading subjects...</p>
		</div>
	{:else if treeData}
		<!-- Desktop Table View -->
		<div class="table-shell glass-panel animate-fade-in desktop-only">
			<table class="subjects-table">
				<colgroup>
					<col class="name-col" />
					<col class="num-col" />
					<col class="num-col" />
					<col class="num-col" />
					<col class="num-col" />
					<col class="action-col" />
				</colgroup>
				<thead>
					<tr>
						<th>Name</th>
						<th>Questions</th>
						<th>Pending</th>
						<th>Approved</th>
						<th>Rejected</th>
						<th></th>
					</tr>
				</thead>
				<tbody>
					<!-- Add Subject Row -->
					{#if addingSubject}
						<tr class="add-row">
							<td>
								<div class="name-stack" style="padding-left: {selectedGroupId ? '2rem' : '0'}">
									<div class="inline-inputs">
										<input class="cell-input code-input" bind:value={draftCode} placeholder="SUB101" maxlength="24" />
										<input class="cell-input" bind:value={draftName} placeholder="Subject Name" maxlength="120" />
									</div>
									<div class="inline-actions">
										<button class="table-btn primary" onclick={saveAddSubject} disabled={savingSubject}>{savingSubject ? 'Saving...' : 'Save'}</button>
										<button class="table-btn" onclick={cancelAddSubject} disabled={savingSubject}>Cancel</button>
									</div>
								</div>
							</td>
							<td>-</td>
							<td>-</td>
							<td>-</td>
							<td>-</td>
							<td></td>
						</tr>
					{/if}

					<!-- Add Group Row -->
					{#if addingGroup}
						<tr class="add-row">
							<td>
								<div class="name-stack" style="padding-left: {selectedGroupId ? '2rem' : '0'}">
									<div class="inline-inputs single">
										<span class="folder-icon">📁</span>
										<input class="cell-input" bind:value={draftGroupName} placeholder="Group Name" maxlength="120" />
									</div>
									<div class="inline-actions">
										<button class="table-btn primary" onclick={saveAddGroup} disabled={savingGroup}>{savingGroup ? 'Saving...' : 'Save'}</button>
										<button class="table-btn" onclick={cancelAddGroup} disabled={savingGroup}>Cancel</button>
									</div>
								</div>
							</td>
							<td>-</td>
							<td>-</td>
							<td>-</td>
							<td>-</td>
							<td></td>
						</tr>
					{/if}

					<!-- Search Results (flat list) -->
					{#if filteredSubjects !== null}
						{#if filteredSubjects.length === 0}
							<tr>
								<td colspan="6" class="empty-cell">No subjects matched your search.</td>
							</tr>
						{:else}
							{#each filteredSubjects as subject}
								<tr 
									class="subject-row" 
									role="button" 
									tabindex="0" 
									draggable="true"
									ondragstart={(e) => handleDragStart(e, 'subject', subject.id, subject.name)}
									ondragend={handleDragEnd}
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
										</div>
									</td>
									<td>{subject.total_questions}</td>
									<td>{subject.total_pending ?? 0}</td>
									<td class="green-text">{subject.total_approved ?? 0}</td>
									<td class="red-text">{subject.total_rejected ?? 0}</td>
									<td>
										<button class="icon-btn" title="Move" onclick={(e) => { e.stopPropagation(); openMoveModal('subject', subject.id, subject.name); }}>↔</button>
									</td>
								</tr>
							{/each}
						{/if}
					{:else}
						<!-- Tree View -->
						<!-- Root drop zone -->
						<tr 
							class="drop-zone-row" 
							class:drag-over={dragOverRoot}
							ondragover={(e) => handleDragOver(e, null)}
							ondragleave={handleDragLeave}
							ondrop={(e) => handleDrop(e, null)}
						>
							<td colspan="6" class="drop-zone-cell">
								{#if draggedItem}
									<span class="drop-hint">Drop here to move to root</span>
								{/if}
							</td>
						</tr>

						<!-- Groups -->
						{#each treeData.groups as group}
							{@render groupRow(group, 0)}
						{/each}

						<!-- Ungrouped Subjects -->
						{#each treeData.ungrouped_subjects as subject}
							{@render subjectRow(subject, 0)}
						{/each}

						{#if treeData.groups.length === 0 && treeData.ungrouped_subjects.length === 0}
							<tr>
								<td colspan="6" class="empty-cell">No subjects yet. Create a group or add a subject to get started.</td>
							</tr>
						{/if}
					{/if}
				</tbody>
			</table>
		</div>

		<!-- Mobile View -->
		<div class="subjects-mobile-list mobile-only animate-fade-in">
			{#if addingSubject}
				<div class="subject-mobile-card glass-panel">
					<div class="inline-inputs">
						<input class="cell-input code-input" bind:value={draftCode} placeholder="SUB101" maxlength="24" />
						<input class="cell-input" bind:value={draftName} placeholder="Subject Name" maxlength="120" />
					</div>
					<div class="inline-actions">
						<button class="table-btn primary" onclick={saveAddSubject} disabled={savingSubject}>{savingSubject ? 'Saving...' : 'Save'}</button>
						<button class="table-btn" onclick={cancelAddSubject} disabled={savingSubject}>Cancel</button>
					</div>
				</div>
			{/if}

			{#if addingGroup}
				<div class="subject-mobile-card glass-panel">
					<div class="inline-inputs single">
						<span class="folder-icon">📁</span>
						<input class="cell-input" bind:value={draftGroupName} placeholder="Group Name" maxlength="120" />
					</div>
					<div class="inline-actions">
						<button class="table-btn primary" onclick={saveAddGroup} disabled={savingGroup}>{savingGroup ? 'Saving...' : 'Save'}</button>
						<button class="table-btn" onclick={cancelAddGroup} disabled={savingGroup}>Cancel</button>
					</div>
				</div>
			{/if}

			{#if filteredSubjects !== null}
				{#if filteredSubjects.length === 0}
					<div class="subject-mobile-card glass-panel empty-cell">No subjects matched your search.</div>
				{:else}
					{#each filteredSubjects as subject}
						<button class="subject-mobile-card glass-panel" onclick={() => openSubject(subject.id)}>
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
					{/each}
				{/if}
			{:else}
				<!-- Mobile Tree View -->
				{#each treeData.groups as group}
					{@render mobileGroupCard(group, 0)}
				{/each}
				{#each treeData.ungrouped_subjects as subject}
					{@render mobileSubjectCard(subject, 0)}
				{/each}
				{#if treeData.groups.length === 0 && treeData.ungrouped_subjects.length === 0}
					<div class="subject-mobile-card glass-panel empty-cell">No subjects yet.</div>
				{/if}
			{/if}
		</div>
	{/if}
</div>

<!-- Move Modal -->
{#if showMoveModal && treeData}
	<div class="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="move-modal-title" tabindex="-1" onclick={closeMoveModal} onkeydown={(e) => { if (e.key === 'Escape') closeMoveModal(); }}>
		<section class="modal-content glass-panel" aria-label="Move options">
			<h3 id="move-modal-title">Move "{moveTargetName}"</h3>
			<p class="modal-hint">Select destination group:</p>
			<div class="modal-options">
				<button 
					class="modal-option" 
					onclick={() => handleMoveToGroup(null)}
					disabled={movingItem}
				>
					📂 Root (No Group)
				</button>
				{#each getAllGroups(treeData.groups) as group}
					{#if !(moveTargetType === 'group' && moveTargetId === group.id)}
						<button 
							class="modal-option" 
							style="padding-left: {1 + group.depth * 1.5}rem"
							onclick={() => handleMoveToGroup(group.id)}
							disabled={movingItem}
						>
							📁 {group.name}
						</button>
					{/if}
				{/each}
			</div>
			<div class="modal-actions">
				<button class="table-btn" onclick={closeMoveModal} disabled={movingItem}>Cancel</button>
			</div>
		</section>
	</div>
{/if}

<!-- Context Menu -->
{#if contextMenuGroupId && contextMenuPosition && treeData}
	{@const group = findGroupById(treeData.groups, contextMenuGroupId)}
	{#if group}
		<!-- svelte-ignore a11y_click_events_have_key_events -->
		<!-- svelte-ignore a11y_no_static_element_interactions -->
		<div class="context-menu-overlay" onclick={hideContextMenu}>
			<div 
				class="context-menu glass-panel" 
				style="left: {contextMenuPosition.x}px; top: {contextMenuPosition.y}px"
				onclick={(e) => e.stopPropagation()}
			>
				<button class="context-menu-item" onclick={() => handleContextMenuMove(group.id, group.name)}>
					<span class="context-menu-icon">↔</span>
					Move Group
				</button>
				<button class="context-menu-item danger" onclick={() => handleContextMenuDelete(group.id, group.name)}>
					<span class="context-menu-icon">✕</span>
					Delete Group
				</button>
			</div>
		</div>
	{/if}
{/if}

<!-- Snippet: Group Row (recursive) -->
{#snippet groupRow(group: SubjectGroupTreeNode, depth: number)}
	<tr 
		class="group-row" 
		class:selected={selectedGroupId === group.id}
		class:drag-over={dragOverGroupId === group.id}
		draggable="true"
		ondragstart={(e) => handleDragStart(e, 'group', group.id, group.name)}
		ondragend={handleDragEnd}
		ondragover={(e) => handleDragOver(e, group.id)}
		ondragleave={handleDragLeave}
		ondrop={(e) => handleDrop(e, group.id)}
		onclick={(e) => { toggleGroup(group.id); selectGroup(group.id, e); }}
		oncontextmenu={(e) => showContextMenu(e, group.id)}
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
		<td>
			<button class="context-menu-btn" title="Options" onclick={(e) => { e.stopPropagation(); showContextMenu(e, group.id); }}>⋮</button>
		</td>
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
				<td colspan="6" style="padding-left: {(depth + 1) * 1.5 + 1}rem">
					<span class="empty-hint">Empty group</span>
				</td>
			</tr>
		{/if}
	{/if}
{/snippet}

<!-- Snippet: Subject Row -->
{#snippet subjectRow(subject: SubjectResponse, depth: number)}
	<tr 
		class="subject-row" 
		role="button" 
		tabindex="0" 
		draggable="true"
		ondragstart={(e) => handleDragStart(e, 'subject', subject.id, subject.name)}
		ondragend={handleDragEnd}
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
		<td>
			<button class="icon-btn" title="Move" onclick={(e) => { e.stopPropagation(); openMoveModal('subject', subject.id, subject.name); }}>↔</button>
		</td>
	</tr>
{/snippet}

<!-- Snippet: Mobile Group Card (recursive) -->
{#snippet mobileGroupCard(group: SubjectGroupTreeNode, depth: number)}
	<div 
		class="group-mobile-card glass-panel" 
		class:selected={selectedGroupId === group.id}
		style="margin-left: {depth * 0.75}rem"
		role="group"
		aria-label="Group: {group.name}"
		oncontextmenu={(e) => showContextMenu(e, group.id)}
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
		<button class="context-menu-btn mobile" onclick={(e) => { e.stopPropagation(); showContextMenu(e, group.id); }}>⋮</button>
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

<!-- Snippet: Mobile Subject Card -->
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
		<button class="icon-btn small" onclick={() => openMoveModal('subject', subject.id, subject.name)}>Move</button>
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

	.hero {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		gap: 0.9rem;
	}

	.hero-actions {
		display: flex;
		gap: 0.5rem;
		flex-wrap: wrap;
	}

	.eyebrow {
		margin: 0 0 0.35rem;
		font-size: 0.78rem;
		font-weight: 700;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: var(--theme-primary);
	}

	.title {
		margin: 0;
		font-size: 2rem;
		font-weight: 800;
		color: var(--theme-text);
	}

	.toolbar {
		display: flex;
		gap: 0.75rem;
	}

	.search-input {
		flex: 1;
		padding: 0.85rem 1rem;
		border-radius: 0.85rem;
		border: 1px solid rgba(17, 24, 39, 0.14);
		background: rgba(255, 255, 255, 0.78);
		color: var(--theme-text-primary);
		font: inherit;
	}

	.add-btn {
		padding: 0.82rem 1.1rem;
		border-radius: 999px;
		border: 1px solid rgba(var(--theme-primary-rgb), 0.45);
		background: rgba(var(--theme-primary-rgb), 0.18);
		color: var(--theme-text-primary);
		font: inherit;
		font-weight: 800;
		cursor: pointer;
		white-space: nowrap;
	}

	.add-btn.secondary {
		background: rgba(var(--theme-primary-rgb), 0.08);
		border-color: rgba(var(--theme-primary-rgb), 0.25);
	}

	.add-btn:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}

	.error-banner {
		padding: 0.85rem 1rem;
		border-radius: 0.95rem;
		background: rgba(239, 68, 68, 0.12);
		border: 1px solid rgba(239, 68, 68, 0.3);
		color: #b91c1c;
	}

	.stats-row {
		display: grid;
		grid-template-columns: repeat(5, minmax(0, 1fr));
		gap: 0.75rem;
	}

	.stat-card {
		padding: 0.85rem;
		border-radius: 1rem;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.2rem;
	}

	.stat-value {
		font-size: 1.45rem;
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
		border-radius: 1rem;
		overflow-x: auto;
		overflow-y: auto;
		max-height: calc(100vh - 420px);
	}

	.desktop-only {
		display: block !important;
	}

	.mobile-only {
		display: none !important;
	}

	.subjects-mobile-list {
		display: grid;
		gap: 0.75rem;
	}

	.subject-mobile-card {
		border: 1px solid var(--theme-glass-border);
		border-radius: 0.95rem;
		padding: 0.8rem;
		display: flex;
		flex-direction: column;
		gap: 0.55rem;
		text-align: left;
		color: var(--theme-text-primary);
	}

	button.subject-mobile-card {
		cursor: pointer;
		background: transparent;
	}

	.mobile-metrics {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 0.35rem 0.8rem;
		font-size: 0.82rem;
		color: var(--theme-text-muted);
	}

	.mobile-metrics strong {
		color: var(--theme-text-primary);
	}

	.subjects-table {
		width: 100%;
		table-layout: fixed;
		border-collapse: collapse;
	}

	.name-col {
		width: 48%;
	}

	.num-col {
		width: 13%;
	}

	.subjects-table thead th {
		padding: 0.75rem 0.62rem;
		font-size: 0.72rem;
		font-weight: 700;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--theme-text-muted);
		text-align: left;
		border-bottom: 1px solid var(--theme-glass-border);
		border-right: 1px solid color-mix(in srgb, var(--theme-glass-border) 82%, transparent);
		background: rgba(255, 255, 255, 0.35);
	}

	.subjects-table thead th:last-child {
		border-right: none;
	}

	.subjects-table tbody td {
		padding: 0.68rem 0.62rem;
		border-bottom: 1px solid var(--theme-glass-border);
		border-right: 1px solid color-mix(in srgb, var(--theme-glass-border) 72%, transparent);
		color: var(--theme-text-primary);
		vertical-align: top;
		word-break: break-word;
	}

	.subjects-table tbody td:last-child {
		border-right: none;
	}

	.subjects-table th:nth-child(n + 2),
	.subjects-table td:nth-child(n + 2) {
		text-align: center;
	}

	.subject-row {
		cursor: pointer;
	}

	.subjects-table tbody tr:last-child td {
		border-bottom: none;
	}

	.name-stack {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}

	.name-header {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-wrap: wrap;
	}

	.name-header strong {
		font-size: 1rem;
		color: var(--theme-text-primary);
	}

	.code-chip {
		display: inline-flex;
		padding: 0.2rem 0.55rem;
		border-radius: 999px;
		font-size: 0.72rem;
		font-weight: 700;
		letter-spacing: 0.05em;
		text-transform: uppercase;
		background: rgba(var(--theme-primary-rgb), 0.15);
		color: var(--theme-primary);
	}


	.inline-actions {
		display: flex;
		flex-wrap: nowrap;
		gap: 0.4rem;
		justify-content: flex-end;
		overflow-x: auto;
	}

	.table-btn {
		padding: 0.42rem 0.72rem;
		border-radius: 999px;
		border: 1px solid rgba(var(--theme-primary-rgb), 0.35);
		background: rgba(var(--theme-primary-rgb), 0.1);
		color: var(--theme-primary);
		font: inherit;
		font-size: 0.78rem;
		font-weight: 700;
		cursor: pointer;
	}

	.table-btn.primary {
		background: rgba(var(--theme-primary-rgb), 0.2);
		color: var(--theme-text-primary);
	}

	.table-btn:disabled {
		opacity: 0.55;
		cursor: not-allowed;
	}

	.inline-inputs {
		display: grid;
		grid-template-columns: 170px minmax(0, 1fr);
		gap: 0.45rem;
	}

	.cell-input {
		width: 100%;
		padding: 0.5rem 0.6rem;
		border-radius: 0.55rem;
		border: 1px solid var(--theme-glass-border);
		background: var(--theme-input-bg);
		color: var(--theme-text-primary);
		font: inherit;
	}

	.cell-input::placeholder {
		color: color-mix(in srgb, var(--theme-text-primary) 48%, #64748b);
	}

	.code-input {
		text-transform: uppercase;
	}

	.empty-cell {
		padding: 1.1rem 0.8rem;
		text-align: center;
		color: var(--theme-text-muted);
	}

	.center-state {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		min-height: 46vh;
		gap: 0.8rem;
		padding: 1.5rem;
		text-align: center;
		color: var(--theme-text-muted);
	}

	.spinner {
		width: 30px;
		height: 30px;
		border-radius: 50%;
		border: 3px solid rgba(255, 255, 255, 0.14);
		border-top-color: var(--theme-primary);
		animation: spin 0.8s linear infinite;
	}

	.amber-text {
		color: var(--theme-primary);
	}

	.white-text {
		color: var(--theme-text-primary);
	}

	.orange-text {
		color: #d97706;
	}

	.green-text {
		color: #059669;
	}

	.red-text {
		color: #dc2626;
	}

	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}

	:global([data-color-mode='light']) .subjects-table thead th {
		border-bottom-color: rgba(148, 163, 184, 0.42);
		border-right-color: rgba(148, 163, 184, 0.42);
	}

	:global([data-color-mode='light']) .subjects-table tbody td {
		border-bottom-color: rgba(148, 163, 184, 0.38);
		border-right-color: rgba(148, 163, 184, 0.38);
	}

	:global([data-color-mode='light']) .add-row .cell-input,
	:global([data-color-mode='light']) .subject-mobile-card .cell-input {
		background: rgba(255, 255, 255, 0.96);
		border-color: rgba(100, 116, 139, 0.48);
		color: #1f2937;
		box-shadow: 0 1px 0 rgba(255, 255, 255, 0.85), 0 0 0 1px rgba(255, 255, 255, 0.35) inset;
	}

	:global([data-color-mode='light']) .add-row .cell-input:focus,
	:global([data-color-mode='light']) .subject-mobile-card .cell-input:focus {
		outline: none;
		border-color: rgba(var(--theme-primary-rgb), 0.62);
		box-shadow: 0 0 0 3px rgba(var(--theme-primary-rgb), 0.18);
	}

	/* Group styles */
	.action-col {
		width: 6%;
	}

	.group-row {
		cursor: pointer;
		background: rgba(var(--theme-primary-rgb), 0.04);
	}

	.group-row:hover {
		background: rgba(var(--theme-primary-rgb), 0.08);
	}

	.group-row.selected {
		background: rgba(var(--theme-primary-rgb), 0.12);
		outline: 2px solid rgba(var(--theme-primary-rgb), 0.3);
		outline-offset: -2px;
	}

	.group-row.drag-over {
		background: rgba(var(--theme-primary-rgb), 0.2);
		outline: 2px dashed var(--theme-primary);
		outline-offset: -2px;
	}

	.group-header {
		display: flex;
		align-items: center;
		gap: 0.4rem;
	}

	.expand-icon {
		font-size: 0.7rem;
		width: 1rem;
		text-align: center;
		color: var(--theme-text-muted);
	}

	.folder-icon {
		font-size: 1rem;
	}

	.group-count {
		font-size: 0.75rem;
		color: var(--theme-text-muted);
		font-weight: 500;
	}

	.muted-text {
		opacity: 0.7;
	}

	.context-menu-btn {
		padding: 0.3rem 0.5rem;
		border-radius: 0.4rem;
		border: 1px solid rgba(var(--theme-primary-rgb), 0.2);
		background: transparent;
		color: var(--theme-text-muted);
		font-size: 1.1rem;
		cursor: pointer;
		line-height: 1;
	}

	.context-menu-btn:hover {
		background: rgba(var(--theme-primary-rgb), 0.1);
		color: var(--theme-text-primary);
	}

	.context-menu-btn.mobile {
		position: absolute;
		top: 0.8rem;
		right: 0.8rem;
		padding: 0.4rem 0.6rem;
	}

	.context-menu-overlay {
		position: fixed;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		z-index: 1000;
		background: transparent;
	}

	.context-menu {
		position: fixed;
		min-width: 180px;
		border-radius: 0.75rem;
		padding: 0.4rem;
		border: 1px solid var(--theme-glass-border);
		background: var(--theme-bg, #ffffff);
		box-shadow: 0 10px 25px rgba(0, 0, 0, 0.15);
		z-index: 1001;
	}

	.context-menu-item {
		width: 100%;
		padding: 0.65rem 0.85rem;
		border: none;
		border-radius: 0.5rem;
		background: transparent;
		color: var(--theme-text-primary);
		font: inherit;
		font-size: 0.88rem;
		text-align: left;
		cursor: pointer;
		display: flex;
		align-items: center;
		gap: 0.65rem;
		transition: background 0.15s ease;
	}

	.context-menu-item:hover {
		background: rgba(var(--theme-primary-rgb), 0.12);
	}

	.context-menu-item.danger:hover {
		background: rgba(239, 68, 68, 0.12);
		color: #dc2626;
	}

	.context-menu-icon {
		font-size: 0.95rem;
		width: 1.2rem;
		text-align: center;
	}

	.icon-btn {
		padding: 0.3rem 0.5rem;
		border-radius: 0.4rem;
		border: 1px solid rgba(var(--theme-primary-rgb), 0.2);
		background: transparent;
		color: var(--theme-text-muted);
		font-size: 0.85rem;
		cursor: pointer;
	}

	.icon-btn:hover {
		background: rgba(var(--theme-primary-rgb), 0.1);
		color: var(--theme-text-primary);
	}

	.icon-btn.small {
		padding: 0.25rem 0.5rem;
		font-size: 0.72rem;
	}

	.empty-group-row td {
		padding: 0.5rem 0.62rem;
	}

	.empty-hint {
		font-size: 0.8rem;
		color: var(--theme-text-muted);
		font-style: italic;
	}

	.drop-zone-row {
		height: 0;
		transition: height 0.15s ease;
	}

	.drop-zone-row.drag-over {
		height: 2.5rem;
		background: rgba(var(--theme-primary-rgb), 0.1);
	}

	.drop-zone-cell {
		padding: 0 !important;
		border: none !important;
		text-align: center;
	}

	.drop-hint {
		font-size: 0.8rem;
		color: var(--theme-primary);
		font-weight: 600;
	}

	.inline-inputs.single {
		grid-template-columns: auto 1fr;
		align-items: center;
	}

	/* Modal styles */
	.modal-overlay {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.5);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 1000;
		padding: 1rem;
	}

	.modal-content {
		max-width: 400px;
		width: 100%;
		max-height: 80vh;
		overflow-y: auto;
		padding: 1.5rem;
		border-radius: 1rem;
	}

	.modal-content h3 {
		margin: 0 0 0.5rem;
		font-size: 1.1rem;
	}

	.modal-hint {
		margin: 0 0 1rem;
		font-size: 0.85rem;
		color: var(--theme-text-muted);
	}

	.modal-options {
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
		margin-bottom: 1rem;
	}

	.modal-option {
		padding: 0.7rem 1rem;
		border-radius: 0.6rem;
		border: 1px solid var(--theme-glass-border);
		background: transparent;
		color: var(--theme-text-primary);
		font: inherit;
		text-align: left;
		cursor: pointer;
	}

	.modal-option:hover {
		background: rgba(var(--theme-primary-rgb), 0.1);
	}

	.modal-option:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.modal-actions {
		display: flex;
		justify-content: flex-end;
	}

	/* Mobile group styles */
	.group-mobile-card {
		position: relative;
		border: 1px solid var(--theme-glass-border);
		border-radius: 0.95rem;
		padding: 0.8rem;
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
	}

	.group-mobile-card.selected {
		border-color: var(--theme-primary);
		background: rgba(var(--theme-primary-rgb), 0.08);
	}

	.group-header-btn {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		background: transparent;
		border: none;
		color: var(--theme-text-primary);
		font: inherit;
		cursor: pointer;
		padding: 0;
		text-align: left;
	}

	.mobile-metrics.muted {
		opacity: 0.7;
	}

	.card-main {
		flex: 1;
		background: transparent;
		border: none;
		color: inherit;
		font: inherit;
		cursor: pointer;
		padding: 0;
		text-align: left;
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
	}

	@media (max-width: 920px) {
		.desktop-only {
			display: none !important;
		}

		.mobile-only {
			display: grid !important;
		}

		.page {
			padding: 0.9rem 0.95rem 1.25rem;
			gap: 0.8rem;
		}

		.eyebrow {
			display: none;
		}

		.hero {
			flex-direction: column;
			align-items: stretch;
		}

		.hero-actions {
			flex-direction: column;
		}

		.add-btn {
			width: 100%;
		}

		.stats-row {
			grid-template-columns: repeat(3, minmax(0, 1fr));
			gap: 0.45rem;
		}

		.stat-card {
			padding: 0.55rem 0.35rem;
		}

		.stat-value {
			font-size: 1rem;
		}

		.stat-label {
			font-size: 0.6rem;
		}

		.subjects-table thead th,
		.subjects-table tbody td {
			padding: 0.58rem 0.45rem;
			font-size: 0.84rem;
		}

		.inline-inputs {
			grid-template-columns: 1fr;
		}

		.code-chip {
			font-size: 0.66rem;
		}

		.name-header strong {
			font-size: 0.92rem;
		}
	}
</style>