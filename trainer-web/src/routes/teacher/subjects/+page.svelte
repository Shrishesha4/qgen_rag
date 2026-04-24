<script lang="ts">
	import { onMount, onDestroy, tick } from 'svelte';
	import { goto, preloadData } from '$app/navigation';
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
	import {
		listCurrentUserFavorites,
		addCurrentUserFavorite,
		removeCurrentUserFavorite,
		type FavoriteSummary,
	} from '$lib/api/activity';
	import { getGenerationWebSocketClient, type StatsData } from '$lib/api/generation-websocket';
	import { buildSubjectGroupMetaById, getSubjectGroupPath, matchesSubjectSearch } from '$lib/subject-group-search';

	// Tab state
	type ViewTab = 'subjects' | 'groups';
	let activeTab = $state<ViewTab>('groups');

	let loading = $state(true);
	let error = $state('');
	let treeData = $state<SubjectTreeResponse | null>(null);
	let favorites = $state<FavoriteSummary[]>([]);
	let favoriteBusyKeys = $state<Record<string, boolean>>({});
	let query = $state('');
	
	// WebSocket for live stats updates
	let wsUnsubscribers: (() => void)[] = [];
	
	// Add subject state (for subjects view)
	let addingSubject = $state(false);
	let draftCode = $state('');
	let draftName = $state('');
	let savingSubject = $state(false);
	let addSubjectError = $state('');
	let addSubjectCodeInput = $state<HTMLInputElement | null>(null);
	
	// Add group state (for groups view)
	let addingGroup = $state(false);
	let draftGroupName = $state('');
	let savingGroup = $state(false);
	let addGroupError = $state('');
	let addGroupNameInput = $state<HTMLInputElement | null>(null);
	
	// Selection and expansion state (for groups view)
	let selectedGroupId = $state<string | null>(null);
	let expandedGroups = $state<Set<string>>(new Set());
	
	// Move modal state
	let showMoveModal = $state(false);
	let moveTargetType = $state<'subject' | 'group'>('subject');
	let moveTargetId = $state<string>('');
	let moveTargetName = $state<string>('');
	let movingItem = $state(false);
	let moveExpandedGroups = $state<Set<string>>(new Set());
	
	// Manage subjects in group modal
	let showManageSubjectsModal = $state(false);
	let manageGroupId = $state<string>('');
	let manageGroupName = $state<string>('');
	let manageSubjectsQuery = $state('');
	let managingSubjects = $state(false);
	
	// Drag state
	let draggedItem = $state<{ type: 'subject' | 'group'; id: string; name: string } | null>(null);
	let dragOverGroupId = $state<string | null>(null);
	let dragOverRoot = $state(false);
	
	// Context menu state
	let contextMenuGroupId = $state<string | null>(null);
	let contextMenuPosition = $state<{ x: number; y: number } | null>(null);
	let contextMenuElement = $state<HTMLDivElement | null>(null);
	let contextMenuOverlayElement = $state<HTMLDivElement | null>(null);
	const preloadedSubjectRoutes = new Set<string>();

	function favoriteKey(entityType: string, entityId: string): string {
		return `${entityType}:${entityId}`;
	}

	function collectFavoritedGroups(groups: SubjectGroupTreeNode[], favoriteIds: Set<string>): SubjectGroupTreeNode[] {
		const results: SubjectGroupTreeNode[] = [];
		function walk(group: SubjectGroupTreeNode) {
			if (favoriteIds.has(group.id)) {
				results.push(group);
				return;
			}
			group.children.forEach(walk);
		}
		groups.forEach(walk);
		return results;
	}

	function stripFavoritedGroups(groups: SubjectGroupTreeNode[], favoriteIds: Set<string>): SubjectGroupTreeNode[] {
		return groups.flatMap((group) => {
			if (favoriteIds.has(group.id)) {
				return [];
			}
			return [{
				...group,
				children: stripFavoritedGroups(group.children, favoriteIds),
			}];
		});
	}

	// Custom confirmation modal state
	let showConfirmModal = $state(false);
	let confirmTitle = $state('Confirm action');
	let confirmMessage = $state('');
	let confirmConfirmLabel = $state('Confirm');
	let confirmCancelLabel = $state('Cancel');
	let confirmDanger = $state(false);
	let confirmResolver: ((accepted: boolean) => void) | null = null;

	onMount(() => {
		const unsub = session.subscribe((s) => {
			if (!s || s.user.role !== 'teacher') {
				goto('/teacher/login');
			}
		});
		void loadData();
		setupWebSocket();
		return unsub;
	});
	
	onDestroy(() => {
		wsUnsubscribers.forEach(unsub => unsub());
		wsUnsubscribers = [];
	});
	
	function setupWebSocket() {
		const wsClient = getGenerationWebSocketClient();
		wsClient.connect();
		wsClient.subscribeGlobalStats();
		
		// Handle global stats updates - update totals
		const globalUnsub = wsClient.onGlobalStats((statsData: StatsData) => {
			if (treeData) {
				treeData = {
					...treeData,
					totals: {
						...treeData.totals,
						total_questions: statsData.total_questions ?? treeData.totals.total_questions,
						total_approved: statsData.total_approved ?? treeData.totals.total_approved,
						total_rejected: statsData.total_rejected ?? treeData.totals.total_rejected,
						total_pending: statsData.total_pending ?? treeData.totals.total_pending,
					}
				};
			}
		});
		wsUnsubscribers.push(globalUnsub);
		
		// Handle subject-specific stats updates
		const subjectUnsub = wsClient.onSubjectStats((subjectId: string, statsData: StatsData) => {
			if (!treeData) return;
			
			// Update subject in ungrouped_subjects
			const updatedUngrouped = treeData.ungrouped_subjects.map(s => {
				if (s.id === subjectId) {
					return {
						...s,
						total_questions: statsData.total_questions ?? s.total_questions,
						total_approved: statsData.total_approved ?? s.total_approved,
						total_rejected: statsData.total_rejected ?? s.total_rejected,
						total_pending: statsData.total_pending ?? s.total_pending,
					};
				}
				return s;
			});
			
			// Update subject in groups recursively
			function updateGroupSubjects(groups: SubjectGroupTreeNode[]): SubjectGroupTreeNode[] {
				return groups.map(group => ({
					...group,
					subjects: group.subjects.map(s => {
						if (s.id === subjectId) {
							return {
								...s,
								total_questions: statsData.total_questions ?? s.total_questions,
								total_approved: statsData.total_approved ?? s.total_approved,
								total_rejected: statsData.total_rejected ?? s.total_rejected,
								total_pending: statsData.total_pending ?? s.total_pending,
							};
						}
						return s;
					}),
					children: updateGroupSubjects(group.children),
				}));
			}
			
			treeData = {
				...treeData,
				ungrouped_subjects: updatedUngrouped,
				groups: updateGroupSubjects(treeData.groups),
			};
		});
		wsUnsubscribers.push(subjectUnsub);
	}

	async function loadData() {
		loading = true;
		error = '';
		try {
			const [treeRes, favoriteRes] = await Promise.all([
				getSubjectsTree(),
				listCurrentUserFavorites(),
			]);
			treeData = treeRes;
			favorites = favoriteRes;
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to load subjects';
		} finally {
			loading = false;
		}
	}

	async function preloadSubjectRoute(subjectId: string) {
		if (!subjectId || preloadedSubjectRoutes.has(subjectId)) return;
		preloadedSubjectRoutes.add(subjectId);
		try {
			await preloadData(`/teacher/subjects/${subjectId}`);
		} catch {
			// Keep UI responsive even if prefetch fails.
		}
	}

	async function loadTree() {
		try {
			treeData = await getSubjectsTree();
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to load subjects';
		}
	}

	const favoriteEntityKeys = $derived.by(() => new Set(favorites.map((favorite) => favoriteKey(favorite.entity_type, favorite.entity_id))));

	const subjects = $derived.by<SubjectResponse[]>(() => {
		if (!treeData) return [];

		const groupedSubjects: SubjectResponse[] = [];
		function walk(groups: SubjectGroupTreeNode[]) {
			for (const group of groups) {
				groupedSubjects.push(...group.subjects);
				walk(group.children);
			}
		}

		walk(treeData.groups);
		return [...groupedSubjects, ...treeData.ungrouped_subjects].sort((left, right) => {
			const byName = left.name.localeCompare(right.name);
			if (byName !== 0) return byName;
			return left.code.localeCompare(right.code);
		});
	});

	function isFavorite(entityType: 'subject' | 'group', entityId: string): boolean {
		return favoriteEntityKeys.has(favoriteKey(entityType, entityId));
	}

	async function toggleFavorite(entityType: 'subject' | 'group', entityId: string, entityName: string): Promise<void> {
		const key = favoriteKey(entityType, entityId);
		if (favoriteBusyKeys[key]) return;
		favoriteBusyKeys = { ...favoriteBusyKeys, [key]: true };
		try {
			if (favoriteEntityKeys.has(key)) {
				await removeCurrentUserFavorite({
					entity_type: entityType,
					entity_id: entityId,
					entity_name: entityName,
					source_area: 'teacher_subjects',
				});
				favorites = favorites.filter((favorite) => favoriteKey(favorite.entity_type, favorite.entity_id) !== key);
			} else {
				const favorite = await addCurrentUserFavorite({
					entity_type: entityType,
					entity_id: entityId,
					entity_name: entityName,
					source_area: 'teacher_subjects',
				});
				favorites = [...favorites, favorite];
			}
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to update favorite';
		} finally {
			favoriteBusyKeys = { ...favoriteBusyKeys, [key]: false };
		}
	}

	const subjectGroupMetaById = $derived.by(() => buildSubjectGroupMetaById(treeData?.groups ?? []));

	const groupedSubjects = $derived.by(() => {
		return subjects.filter((subject) => subjectGroupMetaById.has(subject.id));
	});

	const hasActiveSearch = $derived.by(() => query.trim().length > 0);

	// Filtered subjects for subjects view
	const filteredSubjectsView = $derived.by(() => {
		const search = query.trim().toLowerCase();
		if (!search) return subjects;
		return subjects.filter((subject) => matchesSubjectSearch(subject, search, subjectGroupMetaById));
	});

	const pinnedSubjectsView = $derived.by(() => {
		return filteredSubjectsView.filter((subject) => favoriteEntityKeys.has(favoriteKey('subject', subject.id)));
	});

	const regularSubjectsView = $derived.by(() => {
		return filteredSubjectsView.filter((subject) => !favoriteEntityKeys.has(favoriteKey('subject', subject.id)));
	});

	// Filtered subjects for groups view (returns null when no search to show tree)
	const filteredGroupsView = $derived.by(() => {
		const search = query.trim().toLowerCase();
		if (!search) return null;
		return groupedSubjects.filter((subject) => matchesSubjectSearch(subject, search, subjectGroupMetaById));
	});

	const pinnedGroupedSubjectResults = $derived.by(() => {
		if (filteredGroupsView === null) return [];
		return filteredGroupsView.filter((subject) => favoriteEntityKeys.has(favoriteKey('subject', subject.id)));
	});

	const regularGroupedSubjectResults = $derived.by(() => {
		if (filteredGroupsView === null) return [];
		return filteredGroupsView.filter((subject) => !favoriteEntityKeys.has(favoriteKey('subject', subject.id)));
	});

	const favoriteGroupIds = $derived.by(() => new Set(favorites.filter((favorite) => favorite.entity_type === 'group').map((favorite) => favorite.entity_id)));

	const pinnedGroupsTree = $derived.by(() => {
		if (!treeData) return [];
		return collectFavoritedGroups(treeData.groups, favoriteGroupIds);
	});

	const visibleGroupsTree = $derived.by(() => {
		if (!treeData) return [];
		return stripFavoritedGroups(treeData.groups, favoriteGroupIds);
	});

	const totals = $derived.by(() => {
		if (activeTab === 'subjects') {
			return filteredSubjectsView.reduce(
				(acc, subject) => {
					acc.totalTopics += subject.total_topics;
					acc.totalQuestions += subject.total_questions;
					acc.totalPending += subject.total_pending ?? 0;
					acc.totalApproved += subject.total_approved ?? 0;
					acc.totalRejected += subject.total_rejected ?? 0;
					return acc;
				},
				{ totalTopics: 0, totalQuestions: 0, totalPending: 0, totalApproved: 0, totalRejected: 0, totalSubjects: filteredSubjectsView.length }
			);
		}
		if (!treeData) return { totalSubjects: 0, totalQuestions: 0, totalPending: 0, totalApproved: 0, totalRejected: 0, totalTopics: 0 };
		return {
			totalSubjects: treeData.totals.total_subjects,
			totalQuestions: treeData.totals.total_questions,
			totalPending: treeData.totals.total_pending,
			totalApproved: treeData.totals.total_approved,
			totalRejected: treeData.totals.total_rejected,
			totalTopics: 0,
		};
	});

	function openSubject(subjectId: string) {
		void preloadSubjectRoute(subjectId);
		goto(`/teacher/subjects/${subjectId}`);
	}

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

	// Context menu handlers
	function getContextMenuAnchorPoint(event: MouseEvent): { x: number; y: number } {
		if (event.clientX !== 0 || event.clientY !== 0) {
			return { x: event.clientX, y: event.clientY };
		}

		const target = event.currentTarget;
		if (target instanceof HTMLElement) {
			const rect = target.getBoundingClientRect();
			return { x: rect.right, y: rect.bottom };
		}

		return {
			x: Math.max(window.innerWidth / 2, 16),
			y: Math.max(window.innerHeight / 2, 16)
		};
	}

	function clampContextMenuPosition(anchorX: number, anchorY: number) {
		const offset = 4;
		const padding = 8;
		const fallbackWidth = 180;
		const fallbackHeight = 100;

		const overlayRect = contextMenuOverlayElement?.getBoundingClientRect();
		const overlayLeft = overlayRect?.left ?? 0;
		const overlayTop = overlayRect?.top ?? 0;
		const overlayWidth = overlayRect?.width ?? window.innerWidth;
		const overlayHeight = overlayRect?.height ?? window.innerHeight;

		const menuRect = contextMenuElement?.getBoundingClientRect();
		const menuWidth = menuRect?.width ?? fallbackWidth;
		const menuHeight = menuRect?.height ?? fallbackHeight;

		const localAnchorX = anchorX - overlayLeft;
		const localAnchorY = anchorY - overlayTop;

		let x = localAnchorX + offset;
		let y = localAnchorY + offset;

		const maxX = overlayWidth - menuWidth - padding;
		const maxY = overlayHeight - menuHeight - padding;
		const minX = padding;
		const minY = padding;

		x = Math.min(Math.max(x, minX), maxX);
		y = Math.min(Math.max(y, minY), maxY);

		contextMenuPosition = { x, y };
	}

	async function showContextMenu(event: MouseEvent, groupId: string) {
		event.preventDefault();
		event.stopPropagation();

		const anchor = getContextMenuAnchorPoint(event);
		contextMenuGroupId = groupId;
		contextMenuPosition = anchor;

		await tick();
		clampContextMenuPosition(anchor.x, anchor.y);
	}

	function hideContextMenu() {
		contextMenuGroupId = null;
		contextMenuPosition = null;
	}

	function handleContextMenuMove(groupId: string, groupName: string) {
		hideContextMenu();
		openMoveModal('group', groupId, groupName);
	}

	function handleContextMenuManageSubjects(groupId: string) {
		hideContextMenu();
		openManageSubjectsModal(groupId);
	}

	function handleContextMenuAddSubgroup(groupId: string) {
		hideContextMenu();
		selectedGroupId = groupId;
		startAddGroup();
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
		tick().then(() => {
			addSubjectCodeInput?.focus();
		});
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
			await createSubject({ code, name, group_id: selectedGroupId });
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
		tick().then(() => {
			addGroupNameInput?.focus();
		});
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
				expandedGroups = new Set([selectedGroupId]);
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
		moveExpandedGroups = new Set(treeData?.groups.map((group) => group.id) ?? []);
		showMoveModal = true;
	}

	function closeMoveModal() {
		showMoveModal = false;
		moveTargetId = '';
		moveTargetName = '';
		moveExpandedGroups = new Set();
	}

	function toggleMoveGroup(groupId: string) {
		const next = new Set(moveExpandedGroups);
		if (next.has(groupId)) {
			next.delete(groupId);
		} else {
			next.add(groupId);
		}
		moveExpandedGroups = next;
	}

	function containsGroup(groups: SubjectGroupTreeNode[], groupId: string): boolean {
		for (const group of groups) {
			if (group.id === groupId) return true;
			if (containsGroup(group.children, groupId)) return true;
		}
		return false;
	}

	function isMoveDestinationDisabled(groupId: string): boolean {
		if (moveTargetType !== 'group' || !treeData) return false;
		if (groupId === moveTargetId) return true;
		const movingGroup = findGroupById(treeData.groups, moveTargetId);
		if (!movingGroup) return false;
		return containsGroup(movingGroup.children, groupId);
	}

	function getGroupLabel(groupId: string | null): string {
		if (groupId === null) return 'Root (No Group)';
		if (!treeData) return 'Selected Group';
		const group = findGroupById(treeData.groups, groupId);
		return group?.name ?? 'Selected Group';
	}

	function requestConfirmation(options: {
		title: string;
		message: string;
		confirmLabel?: string;
		cancelLabel?: string;
		danger?: boolean;
	}): Promise<boolean> {
		confirmTitle = options.title;
		confirmMessage = options.message;
		confirmConfirmLabel = options.confirmLabel ?? 'Confirm';
		confirmCancelLabel = options.cancelLabel ?? 'Cancel';
		confirmDanger = options.danger ?? false;
		showConfirmModal = true;

		return new Promise((resolve) => {
			confirmResolver = resolve;
		});
	}

	function resolveConfirmation(accepted: boolean) {
		const resolver = confirmResolver;
		confirmResolver = null;
		showConfirmModal = false;
		if (resolver) resolver(accepted);
	}

	function cancelConfirmation() {
		resolveConfirmation(false);
	}

	async function handleMoveToGroup(groupId: string | null) {
		if (movingItem) return;
		if (groupId && isMoveDestinationDisabled(groupId)) return;
		if (moveTargetType === 'subject') {
			if (!canAssignSubjectToGroup(groupId)) {
				error = 'Subjects can only be moved into top-level departments.';
				return;
			}
			const destination = getGroupLabel(groupId);
			const ok = await requestConfirmation({
				title: 'Move Subject',
				message: `Move subject "${moveTargetName}" to "${destination}"?`,
				confirmLabel: 'Move'
			});
			if (!ok) return;
		}
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
		const droppedItem = draggedItem;
		
		// Prevent dropping group into itself
		if (droppedItem.type === 'group' && droppedItem.id === targetGroupId) {
			handleDragEnd();
			return;
		}

		if (droppedItem.type === 'subject') {
			if (!canAssignSubjectToGroup(targetGroupId)) {
				error = 'Subjects can only be moved into top-level departments.';
				handleDragEnd();
				return;
			}
			const destination = getGroupLabel(targetGroupId);
			const ok = await requestConfirmation({
				title: 'Move Subject',
				message: `Move subject "${droppedItem.name}" to "${destination}"?`,
				confirmLabel: 'Move'
			});
			if (!ok) {
				handleDragEnd();
				return;
			}
		}

		try {
			if (droppedItem.type === 'subject') {
				await moveSubject(droppedItem.id, targetGroupId);
			} else {
				await moveGroup(droppedItem.id, targetGroupId);
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
		const ok = await requestConfirmation({
			title: 'Delete Group',
			message: `Delete group "${groupName}"? Its direct children and subjects will move one level up.`,
			confirmLabel: 'Delete',
			danger: true
		});
		if (!ok) return;
		try {
			await deleteGroup(groupId, true);
			if (selectedGroupId === groupId) selectedGroupId = null;
			await loadTree();
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to delete group';
		}
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

	function canAssignSubjectToGroup(groupId: string | null): boolean {
		if (groupId === null) return true;
		if (!treeData) return false;
		return findGroupById(treeData.groups, groupId) !== null;
	}

	// Manage subjects in group modal
	function openManageSubjectsModal(groupId: string | null) {
		if (!groupId || !treeData) return;
		const group = findGroupById(treeData.groups, groupId);
		if (!group) return;
		manageGroupId = groupId;
		manageGroupName = group.name;
		manageSubjectsQuery = '';
		showManageSubjectsModal = true;
	}

	function closeManageSubjectsModal() {
		showManageSubjectsModal = false;
		manageGroupId = '';
		manageGroupName = '';
		manageSubjectsQuery = '';
	}

	// Get subjects that can be added to a group (ungrouped subjects)
	const availableSubjectsForGroup = $derived.by(() => {
		if (!treeData) return [];
		return treeData.ungrouped_subjects;
	});

	// Get subjects currently in the managed group
	const subjectsInManagedGroup = $derived.by(() => {
		if (!treeData || !manageGroupId) return [];
		const group = findGroupById(treeData.groups, manageGroupId);
		return group?.subjects ?? [];
	});

	const filteredSubjectsInManagedGroup = $derived.by(() => {
		const search = manageSubjectsQuery.trim().toLowerCase();
		if (!search) return subjectsInManagedGroup;
		return subjectsInManagedGroup.filter((subject) => {
			return [subject.name, subject.code, subject.description ?? ''].some((value) =>
				value.toLowerCase().includes(search)
			);
		});
	});

	const filteredAvailableSubjectsForGroup = $derived.by(() => {
		const search = manageSubjectsQuery.trim().toLowerCase();
		if (!search) return availableSubjectsForGroup;
		return availableSubjectsForGroup.filter((subject) => {
			return [subject.name, subject.code, subject.description ?? ''].some((value) =>
				value.toLowerCase().includes(search)
			);
		});
	});

	function flattenGroups(groups: SubjectGroupTreeNode[]): SubjectGroupTreeNode[] {
		const result: SubjectGroupTreeNode[] = [];
		function walk(group: SubjectGroupTreeNode) {
			result.push(group);
			group.children.forEach(walk);
		}
		groups.forEach(walk);
		return result;
	}

	function collectGroupIds(groups: SubjectGroupTreeNode[]): Set<string> {
		const ids = new Set<string>();
		function walk(group: SubjectGroupTreeNode) {
			ids.add(group.id);
			group.children.forEach(walk);
		}
		groups.forEach(walk);
		return ids;
	}

	const groupsInManagedGroup = $derived.by(() => {
		if (!treeData || !manageGroupId) return [];
		const group = findGroupById(treeData.groups, manageGroupId);
		return group?.children ?? [];
	});

	const descendantGroupIdsInManagedGroup = $derived.by(() => {
		return collectGroupIds(groupsInManagedGroup);
	});

	const availableGroupsForManagedGroup = $derived.by(() => {
		if (!treeData || !manageGroupId) return [];
		const allGroups = flattenGroups(treeData.groups);
		return allGroups.filter((group) => {
			if (group.id === manageGroupId) return false;
			if (group.parent_id === manageGroupId) return false;
			if (descendantGroupIdsInManagedGroup.has(group.id)) return false;
			return true;
		});
	});

	const filteredGroupsInManagedGroup = $derived.by(() => {
		const search = manageSubjectsQuery.trim().toLowerCase();
		if (!search) return groupsInManagedGroup;
		return groupsInManagedGroup.filter((group) => group.name.toLowerCase().includes(search));
	});

	const filteredAvailableGroupsForManagedGroup = $derived.by(() => {
		const search = manageSubjectsQuery.trim().toLowerCase();
		if (!search) return availableGroupsForManagedGroup;
		return availableGroupsForManagedGroup.filter((group) => group.name.toLowerCase().includes(search));
	});

	async function addSubjectToManagedGroup(subjectId: string) {
		if (managingSubjects || !manageGroupId) return;
		if (!canAssignSubjectToGroup(manageGroupId)) {
			error = 'Subjects can only be added to top-level departments.';
			return;
		}
		managingSubjects = true;
		try {
			await moveSubject(subjectId, manageGroupId);
			await loadTree();
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to add subject to group';
		} finally {
			managingSubjects = false;
		}
	}

	async function removeSubjectFromManagedGroup(subjectId: string) {
		if (managingSubjects) return;
		managingSubjects = true;
		try {
			await moveSubject(subjectId, null);
			await loadTree();
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to remove subject from group';
		} finally {
			managingSubjects = false;
		}
	}

	async function addGroupToManagedGroup(groupId: string) {
		if (managingSubjects || !manageGroupId) return;
		managingSubjects = true;
		try {
			await moveGroup(groupId, manageGroupId);
			await loadTree();
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to add group to group';
		} finally {
			managingSubjects = false;
		}
	}

	async function removeGroupFromManagedGroup(groupId: string) {
		if (managingSubjects) return;
		managingSubjects = true;
		try {
			await moveGroup(groupId, null);
			await loadTree();
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to remove group from group';
		} finally {
			managingSubjects = false;
		}
	}
</script>

<svelte:head>
	<title>Subjects - Teacher Console</title>
</svelte:head>

<div class="page">
	<div class="hero animate-fade-in">
		<div class="hero-intro">
			<h1 class="title font-serif">Subjects</h1>
		</div>

		<!-- Tab Bar -->
		<div class="tab-bar animate-slide-up">
			<button 
				class="tab-btn" 
				class:active={activeTab === 'groups'} 
				onclick={() => { activeTab = 'groups'; query = ''; }}
			>
				Groups
			</button>
			<button 
				class="tab-btn" 
				class:active={activeTab === 'subjects'} 
				onclick={() => { activeTab = 'subjects'; query = ''; }}
			>
				Subjects
			</button>
		</div>

		<div class="hero-actions">
			{#if activeTab === 'subjects'}
				<button class="add-btn" onclick={startAddSubject} disabled={savingSubject || addingSubject}>+ Add Subject</button>
			{:else if activeTab === 'groups'}
				{#if selectedGroupId}
					<!-- <button class="add-btn secondary" onclick={startAddGroup} disabled={savingGroup || addingGroup}>+ Add Subgroup</button> -->
				{:else}
					<button class="add-btn secondary" onclick={startAddGroup} disabled={savingGroup || addingGroup}>+ Add Group</button>
				{/if}
			{/if}
		</div>
	</div>

	<div class="toolbar animate-slide-up">
		<input class="search-input" bind:value={query} placeholder="Search by subject, code, description, or group" />
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
	{:else if activeTab === 'subjects'}
		<!-- SUBJECTS VIEW (flat list) -->
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
						<th>Name</th>
						<th>Questions</th>
						<th>Pending</th>
						<th>Approved</th>
						<th>Rejected</th>
					</tr>
				</thead>
				<tbody>
					{#if addingSubject}
						<tr class="add-row">
							<td>
								<div class="name-stack">
									<div class="inline-inputs">
										<input class="cell-input code-input" bind:value={draftCode} bind:this={addSubjectCodeInput} placeholder="SUB101" maxlength="24" onkeydown={(e) => { if (e.key === 'Enter') saveAddSubject(); }} />
										<input class="cell-input" bind:value={draftName} placeholder="Subject Name" maxlength="120" onkeydown={(e) => { if (e.key === 'Enter') saveAddSubject(); }} />
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
						</tr>
					{/if}

					{#if filteredSubjectsView.length === 0}
						<tr>
							<td colspan="5" class="empty-cell">No subjects matched your search.</td>
						</tr>
					{:else}
						{#each pinnedSubjectsView as subject}
							{@const groupPath = getSubjectGroupPath(subject.id, subjectGroupMetaById)}
							<tr class="subject-row" role="button" tabindex="0" onclick={() => openSubject(subject.id)} onkeydown={(event) => {
								if (event.key === 'Enter' || event.key === ' ') {
									event.preventDefault();
									openSubject(subject.id);
								}
							}}>
								<td>
									<div class="name-stack">
										<div class="name-header">
											<button
												class="favorite-btn"
												type="button"
												title="Unpin subject"
												onclick={(e) => {
													e.stopPropagation();
													void toggleFavorite('subject', subject.id, subject.name);
												}}
												disabled={favoriteBusyKeys[favoriteKey('subject', subject.id)]}
											>
												★
											</button>
											<strong>{subject.name}</strong>
											<span class="code-chip">{subject.code}</span>
										</div>
										{#if hasActiveSearch && groupPath}
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
						{#if pinnedSubjectsView.length > 0 && regularSubjectsView.length > 0}
							<tr class="pin-divider-row">
								<td colspan="5"><span>More Subjects</span></td>
							</tr>
						{/if}
						{#each regularSubjectsView as subject}
							{@const groupPath = getSubjectGroupPath(subject.id, subjectGroupMetaById)}
							<tr class="subject-row" role="button" tabindex="0" onclick={() => openSubject(subject.id)} onkeydown={(event) => {
								if (event.key === 'Enter' || event.key === ' ') {
									event.preventDefault();
									openSubject(subject.id);
								}
							}}>
								<td>
									<div class="name-stack">
										<div class="name-header">
											<button
												class="favorite-btn"
												type="button"
												title="Pin subject"
												onclick={(e) => {
													e.stopPropagation();
													void toggleFavorite('subject', subject.id, subject.name);
												}}
												disabled={favoriteBusyKeys[favoriteKey('subject', subject.id)]}
											>
												☆
											</button>
											<strong>{subject.name}</strong>
											<span class="code-chip">{subject.code}</span>
										</div>
										{#if hasActiveSearch && groupPath}
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
				</tbody>
			</table>
		</div>

		<!-- Mobile Subjects View -->
		<div class="subjects-mobile-list mobile-only animate-fade-in">
			{#if addingSubject}
				<div class="subject-mobile-card glass-panel">
					<div class="inline-inputs">
						<input class="cell-input code-input" bind:value={draftCode} bind:this={addSubjectCodeInput} placeholder="SUB101" maxlength="24" onkeydown={(e) => { if (e.key === 'Enter') saveAddSubject(); }} />
						<input class="cell-input" bind:value={draftName} placeholder="Subject Name" maxlength="120" onkeydown={(e) => { if (e.key === 'Enter') saveAddSubject(); }} />
					</div>
					<div class="inline-actions">
						<button class="table-btn primary" onclick={saveAddSubject} disabled={savingSubject}>{savingSubject ? 'Saving...' : 'Save'}</button>
						<button class="table-btn" onclick={cancelAddSubject} disabled={savingSubject}>Cancel</button>
					</div>
				</div>
			{/if}

			{#if filteredSubjectsView.length === 0}
				<div class="subject-mobile-card glass-panel empty-cell">No subjects matched your search.</div>
			{:else}
				{#each pinnedSubjectsView as subject}
					{@const groupPath = getSubjectGroupPath(subject.id, subjectGroupMetaById)}
					<div class="subject-mobile-card glass-panel">
						<div class="mobile-card-actions">
							<button class="favorite-btn" type="button" title="Unpin subject" onclick={() => void toggleFavorite('subject', subject.id, subject.name)} disabled={favoriteBusyKeys[favoriteKey('subject', subject.id)]}>★</button>
						</div>
						<button class="card-main" onclick={() => openSubject(subject.id)}>
							<div class="name-header">
								<span class="code-chip">{subject.code}</span>
								<strong>{subject.name}</strong>
							</div>
							{#if hasActiveSearch && groupPath}
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
				{#if pinnedSubjectsView.length > 0 && regularSubjectsView.length > 0}
					<div class="favorites-divider">More Subjects</div>
				{/if}
				{#each regularSubjectsView as subject}
					{@const groupPath = getSubjectGroupPath(subject.id, subjectGroupMetaById)}
					<div class="subject-mobile-card glass-panel">
						<div class="mobile-card-actions">
							<button class="favorite-btn" type="button" title="Pin subject" onclick={() => void toggleFavorite('subject', subject.id, subject.name)} disabled={favoriteBusyKeys[favoriteKey('subject', subject.id)]}>☆</button>
						</div>
						<button class="card-main" onclick={() => openSubject(subject.id)}>
							<div class="name-header">
								<span class="code-chip">{subject.code}</span>
								<strong>{subject.name}</strong>
							</div>
							{#if hasActiveSearch && groupPath}
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
		</div>
	{:else if activeTab === 'groups' && treeData}
		<!-- GROUPS VIEW (hierarchical tree) -->
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
					<!-- Add Group Row -->
					{#if addingGroup}
						<tr class="add-row">
							<td>
								<div class="name-stack" style="padding-left: {selectedGroupId ? '2rem' : '0'}">
									<div class="inline-inputs single">
										<span class="folder-icon">📁</span>
										<input class="cell-input" bind:value={draftGroupName} bind:this={addGroupNameInput} placeholder="Group Name" maxlength="120" onkeydown={(e) => { if (e.key === 'Enter') saveAddGroup(); }} />
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

					<!-- Search Results (flat list) in Groups view -->
					{#if filteredGroupsView !== null}
						{#if filteredGroupsView.length === 0}
							<tr>
								<td colspan="6" class="empty-cell">No subjects matched your search.</td>
							</tr>
						{:else}
							{#each pinnedGroupedSubjectResults as subject}
								{@const groupPath = getSubjectGroupPath(subject.id, subjectGroupMetaById)}
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
												<button class="favorite-btn" type="button" title="Unpin subject" onclick={(e) => { e.stopPropagation(); void toggleFavorite('subject', subject.id, subject.name); }} disabled={favoriteBusyKeys[favoriteKey('subject', subject.id)]}>★</button>
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
									<td>
										<button class="icon-btn" title="Move" onclick={(e) => { e.stopPropagation(); openMoveModal('subject', subject.id, subject.name); }}>↔</button>
									</td>
								</tr>
							{/each}
							{#if pinnedGroupedSubjectResults.length > 0 && regularGroupedSubjectResults.length > 0}
								<tr class="pin-divider-row">
									<td colspan="6"><span>More Results</span></td>
								</tr>
							{/if}
							{#each regularGroupedSubjectResults as subject}
								{@const groupPath = getSubjectGroupPath(subject.id, subjectGroupMetaById)}
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
												<button class="favorite-btn" type="button" title="Pin subject" onclick={(e) => { e.stopPropagation(); void toggleFavorite('subject', subject.id, subject.name); }} disabled={favoriteBusyKeys[favoriteKey('subject', subject.id)]}>☆</button>
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
						{#each pinnedGroupsTree as group}
							{@render groupRow(group, 0, true)}
						{/each}

						{#if pinnedGroupsTree.length > 0 && visibleGroupsTree.length > 0}
							<tr class="pin-divider-row">
								<td colspan="6"><span>Other Groups</span></td>
							</tr>
						{/if}

						{#each visibleGroupsTree as group}
							{@render groupRow(group, 0, false)}
						{/each}

						{#if treeData.groups.length === 0}
							<tr>
								<td colspan="6" class="empty-cell">No groups yet. Create a group, then add subjects to it.</td>
							</tr>
						{/if}
					{/if}
				</tbody>
			</table>
		</div>

		<!-- Mobile Groups View -->
		<div class="subjects-mobile-list mobile-only animate-fade-in">
			{#if addingGroup}
				<div class="subject-mobile-card glass-panel">
					<div class="inline-inputs single">
						<span class="folder-icon">📁</span>
						<input class="cell-input" bind:value={draftGroupName} bind:this={addGroupNameInput} placeholder="Group Name" maxlength="120" onkeydown={(e) => { if (e.key === 'Enter') saveAddGroup(); }} />
					</div>
					<div class="inline-actions">
						<button class="table-btn primary" onclick={saveAddGroup} disabled={savingGroup}>{savingGroup ? 'Saving...' : 'Save'}</button>
						<button class="table-btn" onclick={cancelAddGroup} disabled={savingGroup}>Cancel</button>
					</div>
				</div>
			{/if}

				{#if filteredGroupsView !== null}
				{#if filteredGroupsView.length === 0}
						<div class="subject-mobile-card glass-panel empty-cell">No grouped subjects matched your search.</div>
				{:else}
					{#each pinnedGroupedSubjectResults as subject}
						{@const groupPath = getSubjectGroupPath(subject.id, subjectGroupMetaById)}
						<div class="subject-mobile-card glass-panel">
							<div class="mobile-card-actions">
								<button class="favorite-btn" type="button" title="Unpin subject" onclick={() => void toggleFavorite('subject', subject.id, subject.name)} disabled={favoriteBusyKeys[favoriteKey('subject', subject.id)]}>★</button>
							</div>
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
					{#if pinnedGroupedSubjectResults.length > 0 && regularGroupedSubjectResults.length > 0}
						<div class="favorites-divider">More Results</div>
					{/if}
					{#each regularGroupedSubjectResults as subject}
						{@const groupPath = getSubjectGroupPath(subject.id, subjectGroupMetaById)}
						<div class="subject-mobile-card glass-panel">
							<div class="mobile-card-actions">
								<button class="favorite-btn" type="button" title="Pin subject" onclick={() => void toggleFavorite('subject', subject.id, subject.name)} disabled={favoriteBusyKeys[favoriteKey('subject', subject.id)]}>☆</button>
							</div>
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
				<!-- Mobile Tree View -->
				{#each pinnedGroupsTree as group}
					{@render mobileGroupCard(group, 0, true)}
				{/each}
				{#if pinnedGroupsTree.length > 0 && visibleGroupsTree.length > 0}
					<div class="favorites-divider">Other Groups</div>
				{/if}
				{#each visibleGroupsTree as group}
					{@render mobileGroupCard(group, 0, false)}
				{/each}
					{#if treeData.groups.length === 0}
						<div class="subject-mobile-card glass-panel empty-cell">No groups yet.</div>
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
					class="modal-option root-option" 
					onclick={() => handleMoveToGroup(null)}
					disabled={movingItem || moveTargetType === 'subject'}
				>
					📂 Root (No Group)
				</button>
				{#each treeData.groups as group}
					{@render moveGroupOption(group, 0)}
				{/each}
			</div>
			<div class="modal-actions">
				<button class="table-btn" onclick={closeMoveModal} disabled={movingItem}>Cancel</button>
			</div>
		</section>
	</div>
{/if}

{#snippet moveGroupOption(group: SubjectGroupTreeNode, depth: number)}
	{@const hasChildren = group.children.length > 0}
	{@const expanded = moveExpandedGroups.has(group.id)}
	{@const disabledDestination = isMoveDestinationDisabled(group.id)}
	{@const disabledForSubjectPlacement = moveTargetType === 'subject' && !canAssignSubjectToGroup(group.id)}
	{@const destinationDisabled = disabledDestination || disabledForSubjectPlacement}
	<div class="move-tree-node" style="margin-left: {depth * 0.9}rem">
		<div class="move-tree-row" class:disabled={destinationDisabled}>
			<button
				class="move-tree-toggle"
				type="button"
				onclick={(event) => {
					event.stopPropagation();
					if (hasChildren) toggleMoveGroup(group.id);
				}}
				disabled={!hasChildren}
				aria-label={hasChildren ? (expanded ? 'Collapse group' : 'Expand group') : 'No subgroups'}
			>
				{#if hasChildren}
					<span class="move-tree-chevron" class:open={expanded}>▸</span>
				{:else}
					<span class="move-tree-dot">•</span>
				{/if}
			</button>
			<button
				class="modal-option move-tree-option"
				onclick={() => handleMoveToGroup(group.id)}
				disabled={movingItem || destinationDisabled}
			>
				📁 {group.name}
			</button>
		</div>
	</div>
	{#if hasChildren && expanded}
		{#each group.children as child}
			{@render moveGroupOption(child, depth + 1)}
		{/each}
	{/if}
{/snippet}

<!-- Confirm Modal -->
{#if showConfirmModal}
	<div class="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="confirm-modal-title" tabindex="-1" onclick={cancelConfirmation} onkeydown={(e) => { if (e.key === 'Escape') cancelConfirmation(); }}>
		<!-- svelte-ignore a11y_click_events_have_key_events -->
		<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
		<section class="modal-content confirm-modal-content glass-panel" aria-label="Confirmation" onclick={(e) => e.stopPropagation()}>
			<h3 id="confirm-modal-title">{confirmTitle}</h3>
			<p class="modal-hint confirm-message">{confirmMessage}</p>
			<div class="modal-actions confirm-actions">
				<button class="table-btn" onclick={() => resolveConfirmation(false)}>{confirmCancelLabel}</button>
				<button class={`table-btn ${confirmDanger ? 'danger' : 'primary'}`} onclick={() => resolveConfirmation(true)}>{confirmConfirmLabel}</button>
			</div>
		</section>
	</div>
{/if}

<!-- Manage Subjects Modal -->
{#if showManageSubjectsModal}
	<div class="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="manage-subjects-title" tabindex="-1" onclick={closeManageSubjectsModal} onkeydown={(e) => { if (e.key === 'Escape') closeManageSubjectsModal(); }}>
		<!-- svelte-ignore a11y_click_events_have_key_events -->
		<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
		<section class="modal-content manage-subjects-modal glass-panel" aria-label="Manage subjects" onclick={(e) => e.stopPropagation()}>
			<h3 id="manage-subjects-title">Manage Subjects in "{manageGroupName}"</h3>
			<div class="manage-search-bar">
				<input
					class="manage-search-input"
					bind:value={manageSubjectsQuery}
					placeholder="Search subjects by name, code, or description"
				/>
			</div>
			
			<!-- Subjects in this group -->
			<div class="manage-section">
				<h4 class="manage-section-title">Subjects in Group</h4>
				{#if filteredSubjectsInManagedGroup.length === 0}
					{#if subjectsInManagedGroup.length === 0}
					<p class="manage-empty">No subjects in this group yet.</p>
					{:else}
					<p class="manage-empty">No subjects in this group matched your search.</p>
					{/if}
				{:else}
					<div class="manage-list">
						{#each filteredSubjectsInManagedGroup as subject}
							<div class="manage-item">
								<div class="manage-item-info">
									<span class="code-chip">{subject.code}</span>
									<strong>{subject.name}</strong>
								</div>
								<button 
									class="table-btn danger small" 
									onclick={() => removeSubjectFromManagedGroup(subject.id)}
									disabled={managingSubjects}
								>
									Remove
								</button>
							</div>
						{/each}
					</div>
				{/if}
			</div>
			
			<!-- Available subjects to add -->
			<div class="manage-section">
				<h4 class="manage-section-title">Available Subjects (Ungrouped)</h4>
				{#if filteredAvailableSubjectsForGroup.length === 0}
					{#if availableSubjectsForGroup.length === 0}
					<p class="manage-empty">No ungrouped subjects available.</p>
					{:else}
					<p class="manage-empty">No available subjects matched your search.</p>
					{/if}
				{:else}
					<div class="manage-list">
						{#each filteredAvailableSubjectsForGroup as subject}
							<div class="manage-item">
								<div class="manage-item-info">
									<span class="code-chip">{subject.code}</span>
									<strong>{subject.name}</strong>
								</div>
								<button 
									class="table-btn primary small" 
									onclick={() => addSubjectToManagedGroup(subject.id)}
									disabled={managingSubjects}
								>
									Add
								</button>
							</div>
						{/each}
					</div>
				{/if}
			</div>

			<!-- Groups currently under this group -->
			<div class="manage-section">
				<h4 class="manage-section-title">Groups in Group</h4>
				{#if filteredGroupsInManagedGroup.length === 0}
					{#if groupsInManagedGroup.length === 0}
					<p class="manage-empty">No groups in this group yet.</p>
					{:else}
					<p class="manage-empty">No groups in this group matched your search.</p>
					{/if}
				{:else}
					<div class="manage-list">
						{#each filteredGroupsInManagedGroup as group}
							<div class="manage-item">
								<div class="manage-item-info">
									<span class="group-chip">Group</span>
									<strong>{group.name}</strong>
								</div>
								<button
									class="table-btn danger small"
									onclick={() => removeGroupFromManagedGroup(group.id)}
									disabled={managingSubjects}
								>
									Remove
								</button>
							</div>
						{/each}
					</div>
				{/if}
			</div>

			<!-- Existing groups available to add under this group -->
			<div class="manage-section">
				<h4 class="manage-section-title">Available Existing Groups</h4>
				{#if filteredAvailableGroupsForManagedGroup.length === 0}
					{#if availableGroupsForManagedGroup.length === 0}
					<p class="manage-empty">No eligible groups available.</p>
					{:else}
					<p class="manage-empty">No available groups matched your search.</p>
					{/if}
				{:else}
					<div class="manage-list">
						{#each filteredAvailableGroupsForManagedGroup as group}
							<div class="manage-item">
								<div class="manage-item-info">
									<span class="group-chip">Group</span>
									<strong>{group.name}</strong>
								</div>
								<button
									class="table-btn primary small"
									onclick={() => addGroupToManagedGroup(group.id)}
									disabled={managingSubjects}
								>
									Add
								</button>
							</div>
						{/each}
					</div>
				{/if}
			</div>
			
			<div class="modal-actions">
				<button class="table-btn" onclick={closeManageSubjectsModal} disabled={managingSubjects}>Close</button>
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
		<div class="context-menu-overlay" onclick={hideContextMenu} bind:this={contextMenuOverlayElement}>
			<div 
				class="context-menu glass-panel" 
				style="left: {contextMenuPosition.x}px; top: {contextMenuPosition.y}px"
				bind:this={contextMenuElement}
				onclick={(e) => e.stopPropagation()}
			>
				<button class="context-menu-item" onclick={() => handleContextMenuManageSubjects(group.id)}>
					<span class="context-menu-icon">📚</span>
					Manage
				</button>
				<button class="context-menu-item" onclick={() => handleContextMenuAddSubgroup(group.id)}>
					<span class="context-menu-icon">➕</span>
					Add Subgroup
				</button>
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
{#snippet groupRow(group: SubjectGroupTreeNode, depth: number, pinned: boolean)}
	<tr 
		class="group-row" 
		class:pinned-row={pinned}
		class:selected={selectedGroupId === group.id}
		class:drag-over={dragOverGroupId === group.id}
		draggable="true"
		ondragstart={(e) => handleDragStart(e, 'group', group.id, group.name)}
		ondragend={handleDragEnd}
		ondragover={(e) => handleDragOver(e, group.id)}
		ondragleave={handleDragLeave}
		ondrop={(e) => handleDrop(e, group.id)}
		onclick={(e) => { toggleGroup(group.id); selectGroup(group.id, e); }}
		// oncontextmenu={(e) => showContextMenu(e, group.id)}
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
			<button class="context-menu-btn" aria-label="Group options" title="Options" onclick={(e) => { e.stopPropagation(); showContextMenu(e, group.id); }}>
				<svg class="options-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
					<path d="M4 6.5H16" />
					<path d="M8 12H20" />
					<path d="M4 17.5H16" />
					<circle cx="18" cy="6.5" r="2" />
					<circle cx="6" cy="12" r="2" />
					<circle cx="14" cy="17.5" r="2" />
				</svg>
			</button>
			<button class="favorite-btn inline-favorite-btn" type="button" title={isFavorite('group', group.id) ? 'Unpin group' : 'Pin group'} onclick={(e) => { e.stopPropagation(); void toggleFavorite('group', group.id, group.name); }} disabled={favoriteBusyKeys[favoriteKey('group', group.id)]}>
				{isFavorite('group', group.id) ? '★' : '☆'}
			</button>
		</td>
	</tr>
	{#if expandedGroups.has(group.id)}
		{#each group.children as child}
			{@render groupRow(child, depth + 1, false)}
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
{#snippet mobileGroupCard(group: SubjectGroupTreeNode, depth: number, pinned: boolean)}
	<div 
		class="group-mobile-card glass-panel" 
		class:pinned-row={pinned}
		class:selected={selectedGroupId === group.id}
		style="margin-left: {depth * 0.75}rem"
		role="group"
		aria-label="Group: {group.name}"
		// oncontextmenu={(e) => showContextMenu(e, group.id)}
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
		<button class="context-menu-btn mobile" aria-label="Group options" title="Options" onclick={(e) => { e.stopPropagation(); showContextMenu(e, group.id); }}>
			<svg class="options-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
				<path d="M4 6.5H16" />
				<path d="M8 12H20" />
				<path d="M4 17.5H16" />
				<circle cx="18" cy="6.5" r="2" />
				<circle cx="6" cy="12" r="2" />
				<circle cx="14" cy="17.5" r="2" />
			</svg>
		</button>
		<button class="favorite-btn mobile-favorite-btn" type="button" title={isFavorite('group', group.id) ? 'Unpin group' : 'Pin group'} onclick={(e) => { e.stopPropagation(); void toggleFavorite('group', group.id, group.name); }} disabled={favoriteBusyKeys[favoriteKey('group', group.id)]}>
			{isFavorite('group', group.id) ? '★' : '☆'}
		</button>
	</div>
	{#if expandedGroups.has(group.id)}
		{#each group.children as child}
			{@render mobileGroupCard(child, depth + 1, false)}
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
		display: grid;
		grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
		align-items: start;
		gap: 0.9rem;
	}

	.hero-intro {
		justify-self: start;
	}

	.hero-actions {
		display: flex;
		gap: 0.5rem;
		flex-wrap: wrap;
		justify-self: end;
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

	/* Tab Bar */
	.tab-bar {
		display: flex;
		gap: 0.25rem;
		padding: 0.25rem;
		background: rgba(var(--theme-primary-rgb), 0.08);
		border-radius: 0.75rem;
		width: fit-content;
		align-self: start;
		justify-self: center;
	}

	.tab-btn {
		padding: 0.6rem 1.2rem;
		border-radius: 0.55rem;
		border: none;
		background: transparent;
		color: var(--theme-text-muted);
		font: inherit;
		font-size: 0.88rem;
		font-weight: 600;
		cursor: pointer;
		transition: all 0.15s ease;
	}

	.tab-btn:hover {
		color: var(--theme-text-primary);
		background: rgba(var(--theme-primary-rgb), 0.08);
	}

	.tab-btn.active {
		background: rgba(var(--theme-primary-rgb), 0.18);
		color: var(--theme-text-primary);
		font-weight: 700;
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
		max-height: calc(100vh - 400px);
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
		position: relative;
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

	.mobile-card-actions {
		display: flex;
		justify-content: flex-end;
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

	.pin-divider-row td {
		padding: 0.6rem 0.62rem;
		background: transparent;
		border-bottom: none;
		text-align: center;
	}

	.pin-divider-row span,
	.favorites-divider {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		padding: 0.35rem 0.8rem;
		border-radius: 999px;
		border: 1px dashed color-mix(in srgb, var(--theme-primary) 35%, var(--theme-glass-border));
		color: var(--theme-text-muted);
		font-size: 0.78rem;
		font-weight: 700;
		letter-spacing: 0.04em;
		text-transform: uppercase;
	}

	.favorites-divider {
		width: fit-content;
		justify-self: center;
		margin: 0.1rem auto;
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

	.group-context {
		font-size: 0.78rem;
		line-height: 1.35;
		color: var(--theme-text-muted);
	}

	.favorite-btn {
		width: 2rem;
		height: 2rem;
		border-radius: 999px;
		border: 1px solid rgba(var(--theme-primary-rgb), 0.26);
		background: rgba(var(--theme-primary-rgb), 0.08);
		color: var(--theme-primary);
		font: inherit;
		font-size: 0.92rem;
		font-weight: 800;
		line-height: 1;
		cursor: pointer;
		flex: 0 0 auto;
	}

	.favorite-btn:hover {
		background: rgba(var(--theme-primary-rgb), 0.16);
	}

	.favorite-btn:disabled {
		opacity: 0.55;
		cursor: not-allowed;
	}

	.inline-favorite-btn {
		margin-left: 0.4rem;
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

	.pinned-row {
		box-shadow: inset 3px 0 0 rgba(var(--theme-primary-rgb), 0.45);
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
		padding: 0.35rem;
		border-radius: 0.4rem;
		border: 1px solid rgba(var(--theme-primary-rgb), 0.2);
		background: transparent;
		color: var(--theme-text-muted);
		cursor: pointer;
		line-height: 0;
		display: inline-flex;
		align-items: center;
		justify-content: center;
	}

	.context-menu-btn:hover {
		background: rgba(var(--theme-primary-rgb), 0.1);
		color: var(--theme-text-primary);
	}

	.context-menu-btn.mobile {
		position: absolute;
		top: 0.8rem;
		right: 0.8rem;
		padding: 0.42rem;
	}

	.mobile-favorite-btn {
		position: absolute;
		top: 0.8rem;
		right: 3.25rem;
	}

	.options-icon {
		width: 1.1rem;
		height: 1.1rem;
		stroke: currentColor;
		fill: none;
		stroke-width: 1.9;
		stroke-linecap: round;
		stroke-linejoin: round;
	}

	.options-icon circle {
		fill: currentColor;
		stroke: none;
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

	.context-menu-item:disabled {
		opacity: 0.5;
		cursor: not-allowed;
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

	.root-option {
		font-weight: 700;
	}

	.move-tree-node {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}

	.move-tree-row {
		display: grid;
		grid-template-columns: auto minmax(0, 1fr);
		gap: 0.35rem;
		align-items: center;
	}

	.move-tree-row.disabled {
		opacity: 0.6;
	}

	.move-tree-toggle {
		width: 1.7rem;
		height: 1.7rem;
		border-radius: 0.45rem;
		border: 1px solid var(--theme-glass-border);
		background: rgba(var(--theme-primary-rgb), 0.08);
		color: var(--theme-text-muted);
		display: inline-flex;
		align-items: center;
		justify-content: center;
		cursor: pointer;
	}

	.move-tree-toggle:disabled {
		cursor: default;
		opacity: 0.45;
	}

	.move-tree-chevron {
		display: inline-block;
		transition: transform 0.15s ease;
	}

	.move-tree-chevron.open {
		transform: rotate(90deg);
	}

	.move-tree-dot {
		font-size: 0.95rem;
		line-height: 1;
	}

	.move-tree-option {
		margin: 0;
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

	.confirm-modal-content {
		max-width: 460px;
	}

	.confirm-message {
		margin-bottom: 1.2rem;
		line-height: 1.45;
	}

	.confirm-actions {
		gap: 0.55rem;
	}

	/* Manage Subjects Modal */
	.manage-subjects-modal {
		max-width: 520px;
	}

	.manage-search-bar {
		margin: 0.8rem 0 1rem;
	}

	.manage-search-input {
		width: 100%;
		border-radius: 0.7rem;
		border: 1px solid var(--theme-glass-border);
		background: rgba(var(--theme-primary-rgb), 0.05);
		color: var(--theme-text-primary);
		padding: 0.62rem 0.82rem;
		font: inherit;
	}

	.manage-search-input::placeholder {
		color: var(--theme-text-muted);
	}

	.manage-search-input:focus-visible {
		outline: 2px solid rgba(var(--theme-primary-rgb), 0.35);
		outline-offset: 1px;
	}

	.manage-section {
		margin-bottom: 1.25rem;
	}

	.manage-section-title {
		margin: 0 0 0.6rem;
		font-size: 0.85rem;
		font-weight: 700;
		color: var(--theme-text-muted);
		text-transform: uppercase;
		letter-spacing: 0.04em;
	}

	.manage-empty {
		margin: 0;
		padding: 0.8rem;
		font-size: 0.88rem;
		color: var(--theme-text-muted);
		font-style: italic;
		text-align: center;
		background: rgba(var(--theme-primary-rgb), 0.04);
		border-radius: 0.6rem;
	}

	.manage-list {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		max-height: 200px;
		overflow-y: auto;
	}

	.manage-item {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.75rem;
		padding: 0.6rem 0.8rem;
		background: rgba(var(--theme-primary-rgb), 0.04);
		border-radius: 0.6rem;
		border: 1px solid var(--theme-glass-border);
	}

	.manage-item-info {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex: 1;
		min-width: 0;
	}

	.manage-item-info strong {
		font-size: 0.9rem;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.group-chip {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		padding: 0.12rem 0.45rem;
		border-radius: 999px;
		font-size: 0.66rem;
		font-weight: 700;
		letter-spacing: 0.03em;
		text-transform: uppercase;
		background: rgba(var(--theme-primary-rgb), 0.14);
		color: var(--theme-primary);
		border: 1px solid rgba(var(--theme-primary-rgb), 0.34);
	}

	.table-btn.small {
		padding: 0.3rem 0.6rem;
		font-size: 0.72rem;
	}

	.table-btn.danger {
		background: rgba(220, 38, 38, 0.18);
		border-color: rgba(220, 38, 38, 0.45);
		color: #991b1b;
	}

	.table-btn.danger:hover {
		background: rgba(220, 38, 38, 0.24);
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
			display: flex;
			flex-direction: column;
			align-items: stretch;
		}

		.tab-bar {
			align-self: center;
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