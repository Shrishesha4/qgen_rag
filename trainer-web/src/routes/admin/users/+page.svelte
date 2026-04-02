<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { session } from '$lib/session';
	import { DEFAULT_SECURITY_QUESTION } from '$lib/api/auth';
	import {
		listAdminUsers,
		createAdminUser,
		approveAdminUser,
		bulkApproveAdminUsers,
		updateAdminUser,
		type AdminUserSummary,
		type AdminUserCreateRequest,
		type AdminUserUpdateRequest
	} from '$lib/api/admin';

	type UserRole = 'teacher' | 'vetter' | 'admin';

	type DraftPermissions = {
		role: UserRole;
		is_active: boolean;
		can_manage_groups: boolean;
		can_generate: boolean;
		can_vet: boolean;
	};

	let loading = $state(true);
	let saving = $state(false);
	let error = $state('');
	let success = $state('');
	let query = $state('');
	let currentAdminUserId = $state('');
	let users = $state<AdminUserSummary[]>([]);
	let drafts = $state<Record<string, DraftPermissions>>({});
	let saveBusyByUser = $state<Record<string, boolean>>({});
	let approveBusyByUser = $state<Record<string, boolean>>({});
	let showApprovalModal = $state(false);
	let approvalQuery = $state('');
	let selectedPendingUserIds = $state<string[]>([]);
	let bulkApproveBusy = $state(false);
	let highlightedPendingUserId = $state('');

	let showCreateForm = $state(false);
	let createPayload = $state<AdminUserCreateRequest>({
		email: '',
		username: '',
		password: '',
		full_name: '',
		security_question: DEFAULT_SECURITY_QUESTION,
		security_answer: '',
		role: 'teacher',
		is_active: true,
		can_manage_groups: true,
		can_generate: true,
		can_vet: true
	});

	onMount(() => {
		const unsub = session.subscribe((s) => {
			if (!s || s.user.role !== 'admin') {
				goto('/admin/login');
				return;
			}
			currentAdminUserId = s.user.id;
		});
		if (typeof window !== 'undefined') {
			const params = new URL(window.location.href).searchParams;
			if (params.get('modal') === 'approvals') {
				openApprovalModal(params.get('user') || undefined);
			}
		}
		void loadUsers();
		return unsub;
	});

	function isCurrentAdminUser(userId: string): boolean {
		return userId === currentAdminUserId;
	}

	function userDetailHref(userId: string): string {
		return `/admin/users/${userId}`;
	}

	function defaultPermissionsForRole(role: UserRole) {
		if (role === 'admin') {
			return { can_manage_groups: true, can_generate: true, can_vet: true };
		}
		if (role === 'vetter') {
			return { can_manage_groups: false, can_generate: false, can_vet: true };
		}
		return { can_manage_groups: true, can_generate: true, can_vet: true };
	}

	function hydrateDrafts(nextUsers: AdminUserSummary[]) {
		const nextDrafts: Record<string, DraftPermissions> = {};
		for (const user of nextUsers) {
			nextDrafts[user.id] = {
				role: user.role,
				is_active: user.is_active,
				can_manage_groups: user.can_manage_groups,
				can_generate: user.can_generate,
				can_vet: user.can_vet
			};
		}
		drafts = nextDrafts;
	}

	async function loadUsers() {
		loading = true;
		error = '';
		try {
			const result = await listAdminUsers();
			users = result;
			hydrateDrafts(result);
			selectedPendingUserIds = selectedPendingUserIds.filter((id) => result.some((user) => !user.is_approved && user.id === id));
			if (highlightedPendingUserId && !result.some((user) => !user.is_approved && user.id === highlightedPendingUserId)) {
				highlightedPendingUserId = '';
			}
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to load users';
		} finally {
			loading = false;
		}
	}

	function syncUpdatedUser(updated: AdminUserSummary) {
		users = users.map((user) => (user.id === updated.id ? updated : user));
		drafts = {
			...drafts,
			[updated.id]: {
				role: updated.role,
				is_active: updated.is_active,
				can_manage_groups: updated.can_manage_groups,
				can_generate: updated.can_generate,
				can_vet: updated.can_vet
			}
		};
		if (updated.is_approved) {
			selectedPendingUserIds = selectedPendingUserIds.filter((id) => id !== updated.id);
			if (highlightedPendingUserId === updated.id) {
				highlightedPendingUserId = '';
			}
		}
	}

	function openApprovalModal(targetUserId?: string) {
		showApprovalModal = true;
		approvalQuery = '';
		if (targetUserId) {
			highlightedPendingUserId = targetUserId;
			if (!selectedPendingUserIds.includes(targetUserId)) {
				selectedPendingUserIds = [...selectedPendingUserIds, targetUserId];
			}
		}
	}

	function closeApprovalModal() {
		showApprovalModal = false;
		approvalQuery = '';
		selectedPendingUserIds = [];
		highlightedPendingUserId = '';
	}

	function applyCreateRoleDefaults() {
		const defaults = defaultPermissionsForRole(createPayload.role);
		createPayload = {
			...createPayload,
			...defaults
		};
	}

	async function handleCreateUser() {
		error = '';
		success = '';
		saving = true;
		try {
			if (!createPayload.security_question.trim() || !createPayload.security_answer.trim()) {
				throw new Error('Security question and answer are required');
			}

			const payload: AdminUserCreateRequest = {
				email: createPayload.email.trim(),
				username: createPayload.username.trim().toLowerCase(),
				password: createPayload.password,
				full_name: createPayload.full_name?.trim() || undefined,
				security_question: createPayload.security_question.trim(),
				security_answer: createPayload.security_answer.trim(),
				role: createPayload.role,
				is_active: createPayload.is_active,
				can_manage_groups: createPayload.can_manage_groups,
				can_generate: createPayload.can_generate,
				can_vet: createPayload.can_vet
			};
			await createAdminUser(payload);
			success = 'User created successfully';
			showCreateForm = false;
			createPayload = {
				email: '',
				username: '',
				password: '',
				full_name: '',
				security_question: DEFAULT_SECURITY_QUESTION,
				security_answer: '',
				role: 'teacher',
				is_active: true,
				...defaultPermissionsForRole('teacher')
			};
			await loadUsers();
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to create user';
		} finally {
			saving = false;
		}
	}

	function updateDraftRole(userId: string, role: UserRole) {
		const existing = drafts[userId];
		if (!existing) return;
		const defaults = defaultPermissionsForRole(role);
		drafts = {
			...drafts,
			[userId]: {
				...existing,
				role,
				...defaults
			}
		};
	}

	function hasUserChanges(user: AdminUserSummary): boolean {
		const draft = drafts[user.id];
		if (!draft) return false;
		return (
			draft.role !== user.role ||
			draft.is_active !== user.is_active ||
			draft.can_manage_groups !== user.can_manage_groups ||
			draft.can_generate !== user.can_generate ||
			draft.can_vet !== user.can_vet
		);
	}

	async function saveUser(user: AdminUserSummary) {
		const draft = drafts[user.id];
		if (!draft || !hasUserChanges(user)) return;

		error = '';
		success = '';
		saveBusyByUser = { ...saveBusyByUser, [user.id]: true };
		try {
			const payload: AdminUserUpdateRequest = {
				role: draft.role,
				is_active: draft.is_active,
				can_manage_groups: draft.can_manage_groups,
				can_generate: draft.can_generate,
				can_vet: draft.can_vet
			};
			const updated = await updateAdminUser(user.id, payload);
			syncUpdatedUser(updated);
			success = `Updated ${updated.username}`;
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to update user';
		} finally {
			saveBusyByUser = { ...saveBusyByUser, [user.id]: false };
		}
	}

	async function approveUser(user: AdminUserSummary) {
		if (user.is_approved || approveBusyByUser[user.id]) return;

		error = '';
		success = '';
		approveBusyByUser = { ...approveBusyByUser, [user.id]: true };
		try {
			const updated = await approveAdminUser(user.id);
			syncUpdatedUser(updated);
			success = `Approved ${updated.username}`;
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to approve user';
		} finally {
			approveBusyByUser = { ...approveBusyByUser, [user.id]: false };
		}
	}

	async function bulkApproveSelectedUsers() {
		const pendingIds = selectedPendingUserIds.filter((id) => users.some((user) => !user.is_approved && user.id === id));
		if (pendingIds.length === 0 || bulkApproveBusy) return;

		error = '';
		success = '';
		bulkApproveBusy = true;
		try {
			const response = await bulkApproveAdminUsers(pendingIds);
			for (const updated of response.approved_users) {
				syncUpdatedUser(updated);
			}
			selectedPendingUserIds = selectedPendingUserIds.filter((id) => !pendingIds.includes(id));
			success = response.approved_count === 1 ? 'Approved 1 user' : `Approved ${response.approved_count} users`;
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to bulk approve users';
		} finally {
			bulkApproveBusy = false;
		}
	}

	function togglePendingSelection(userId: string, checked: boolean) {
		if (checked) {
			if (!selectedPendingUserIds.includes(userId)) {
				selectedPendingUserIds = [...selectedPendingUserIds, userId];
			}
			return;
		}
		selectedPendingUserIds = selectedPendingUserIds.filter((id) => id !== userId);
	}

	function toggleAllVisiblePendingUsers(checked: boolean) {
		const visibleIds = filteredPendingUsers.map((user) => user.id);
		if (checked) {
			selectedPendingUserIds = Array.from(new Set([...selectedPendingUserIds, ...visibleIds]));
			return;
		}
		selectedPendingUserIds = selectedPendingUserIds.filter((id) => !visibleIds.includes(id));
	}

	function allVisiblePendingSelected(): boolean {
		return filteredPendingUsers.length > 0 && filteredPendingUsers.every((user) => selectedPendingUserIds.includes(user.id));
	}

	const filteredUsers = $derived.by(() => {
		const needle = query.trim().toLowerCase();
		if (!needle) return users;
		return users.filter((user) =>
			[user.username, user.email, user.full_name || '', user.role].some((value) =>
				value.toLowerCase().includes(needle)
			)
		);
	});

	const pendingUsers = $derived.by(() => users.filter((user) => !user.is_approved));

	const filteredPendingUsers = $derived.by(() => {
		const needle = approvalQuery.trim().toLowerCase();
		if (!needle) return pendingUsers;
		return pendingUsers.filter((user) =>
			[user.username, user.email, user.full_name || '', user.role].some((value) =>
				value.toLowerCase().includes(needle)
			)
		);
	});

	function formatDate(value: string | null): string {
		if (!value) return '—';
		const normalizedValue = /(?:Z|[+-]\d{2}:?\d{2})$/.test(value) ? value : `${value}Z`;
		return new Date(normalizedValue).toLocaleString('en-IN', {
			timeZone: 'Asia/Kolkata',
			year: 'numeric',
			month: '2-digit',
			day: '2-digit',
			hour: '2-digit',
			minute: '2-digit',
			second: '2-digit',
			hour12: true
		});
	}
</script>

<svelte:head>
	<title>User Access Control — Admin</title>
</svelte:head>

<div class="page">
	<!-- <div class="hero animate-fade-in">
		<div>
			<p class="eyebrow">Admin Console</p>
			<h1 class="title font-serif">User Access Control</h1>
			<p class="subtitle">Create users, assign roles, and control permissions for generation, vetting, and group management actions.</p>
		</div>
	</div> -->

	<div class="toolbar glass-panel animate-slide-up">
		<input class="search-input" bind:value={query} placeholder="Search by username, email, name, or role" />
		<div class="toolbar-actions">
			<button class="secondary-btn" onclick={() => openApprovalModal()}>
				Pending Approvals
				{#if pendingUsers.length > 0}
					<span class="toolbar-badge">{pendingUsers.length}</span>
				{/if}
			</button>
			<button class="primary-btn" onclick={() => (showCreateForm = !showCreateForm)}>
				{showCreateForm ? 'Close' : 'Add User'}
			</button>
		</div>
	</div>

	{#if error}
		<div class="error-banner" role="alert">{error}</div>
	{/if}

	{#if success}
		<div class="success-banner" role="status">{success}</div>
	{/if}

	{#if showCreateForm}
		<section class="create-panel glass-panel animate-fade-in" aria-label="Create user form">
			<h2>Create User</h2>
			<div class="create-grid">
				<label class="field">
					<span>Email</span>
					<input bind:value={createPayload.email} type="email" placeholder="user@example.com" />
				</label>
				<label class="field">
					<span>Username</span>
					<input bind:value={createPayload.username} type="text" placeholder="username" />
				</label>
				<label class="field">
					<span>Full Name</span>
					<input bind:value={createPayload.full_name} type="text" placeholder="Optional" />
				</label>
				<label class="field">
					<span>Password</span>
					<input bind:value={createPayload.password} type="password" placeholder="At least 8 characters" />
				</label>
				<label class="field field-span-2">
					<span>Security Question</span>
					<input bind:value={createPayload.security_question} type="text" placeholder="Set a password reset question" />
				</label>
				<label class="field">
					<span>Security Answer</span>
					<input bind:value={createPayload.security_answer} type="text" placeholder="Answer used for password reset" />
				</label>
				<label class="field">
					<span>Role</span>
					<select bind:value={createPayload.role} onchange={applyCreateRoleDefaults}>
						<option value="teacher">Teacher</option>
						<option value="vetter">Vetter</option>
						<option value="admin">Admin</option>
					</select>
				</label>
				<label class="field checkbox-inline">
					<input bind:checked={createPayload.is_active} type="checkbox" />
					<span>Active account</span>
				</label>
			</div>
			<div class="permission-grid">
				<label><input bind:checked={createPayload.can_manage_groups} type="checkbox" /> Can manage groups</label>
				<label><input bind:checked={createPayload.can_generate} type="checkbox" /> Can generate</label>
				<label><input bind:checked={createPayload.can_vet} type="checkbox" /> Can vet</label>
			</div>
			<div class="actions-row">
				<button class="primary-btn" onclick={handleCreateUser} disabled={saving}>{saving ? 'Creating...' : 'Create User'}</button>
			</div>
		</section>
	{/if}

	{#if showApprovalModal}
		<div class="modal-backdrop" role="presentation" onclick={(event) => {
			if (event.currentTarget === event.target) {
				closeApprovalModal();
			}
		}}>
			<div class="approval-modal glass-panel" role="dialog" aria-modal="true" aria-labelledby="approval-modal-title">
				<div class="approval-modal-header">
					<div>
						<p class="modal-eyebrow">Registration Queue</p>
					</div>
					<button class="secondary-btn" type="button" onclick={closeApprovalModal}>Close</button>
				</div>

				<div class="approval-modal-toolbar">
					<input class="approval-search" bind:value={approvalQuery} placeholder="Search pending users by username, email, name, or role" />
					<div class="approval-modal-actions">
						<label class="bulk-select-label">
							<input type="checkbox" checked={allVisiblePendingSelected()} onchange={(event) => toggleAllVisiblePendingUsers((event.currentTarget as HTMLInputElement).checked)} disabled={filteredPendingUsers.length === 0} />
							<span>Select visible</span>
						</label>
						<button class="secondary-btn" type="button" onclick={() => {
							selectedPendingUserIds = [];
							highlightedPendingUserId = '';
						}} disabled={selectedPendingUserIds.length === 0}>Clear</button>
						<button class="approve-btn" type="button" onclick={bulkApproveSelectedUsers} disabled={bulkApproveBusy || selectedPendingUserIds.length === 0}>
							{bulkApproveBusy ? 'Approving...' : `Approve (${selectedPendingUserIds.length})`}
						</button>
					</div>
				</div>

				{#if pendingUsers.length === 0}
					<div class="approval-empty glass-panel">
						<p>No pending registrations right now.</p>
					</div>
				{:else if filteredPendingUsers.length === 0}
					<div class="approval-empty glass-panel">
						<p>No pending users match this search.</p>
					</div>
				{:else}
					<div class="approval-list">
						{#each filteredPendingUsers as user}
							<div class="approval-card glass-panel" class:approval-card--highlight={highlightedPendingUserId === user.id}>
								<label class="approval-check">
									<input type="checkbox" checked={selectedPendingUserIds.includes(user.id)} onchange={(event) => togglePendingSelection(user.id, (event.currentTarget as HTMLInputElement).checked)} />
								</label>
								<div class="approval-card-main">
									<div class="approval-card-heading">
										<a class="user-name user-link" href={userDetailHref(user.id)}>{user.full_name || user.username}</a>
										<span class="status-pill status-pill--pending">Pending Approval</span>
									</div>
									<div class="approval-card-meta">
										<span>{user.email}</span>
										<span class="locked-role">{user.role}</span>
										<span>Registered {formatDate(user.created_at)}</span>
									</div>
								</div>
								<div class="approval-card-actions">
									<a class="secondary-link" href={userDetailHref(user.id)}>Open</a>
									<button class="approve-btn" type="button" onclick={() => approveUser(user)} disabled={approveBusyByUser[user.id]}>
										{approveBusyByUser[user.id] ? 'Approving...' : 'Approve'}
									</button>
								</div>
							</div>
						{/each}
					</div>
				{/if}
			</div>
		</div>
	{/if}

	{#if loading}
		<div class="center-state loading-state">
			<div class="spinner"></div>
			<p>Loading users...</p>
		</div>
	{:else if filteredUsers.length === 0}
		<div class="center-state glass-panel">
			<p>No users found.</p>
		</div>
	{:else}
		<div class="table-wrap glass-panel animate-fade-in desktop-only">
			<table class="data-table">
				<colgroup>
					<col class="col-user" />
					<col class="col-role" />
					<col class="col-status" />
					<col class="col-perm" />
					<col class="col-perm" />
					<col class="col-perm" />
					<col class="col-login" />
					<col class="col-action" />
				</colgroup>
				<thead>
					<tr>
						<th>User</th>
						<th>Role</th>
						<th>Active</th>
						<th>Manage Groups</th>
						<th>Generate</th>
						<th>Vet</th>
						<th>Last Login</th>
						<th></th>
					</tr>
				</thead>
				<tbody>
					{#each filteredUsers as user}
						{@const draft = drafts[user.id]}
						<tr>
							<td>
								<div class="user-cell">
									<a class="user-name user-link" href={userDetailHref(user.id)}>{user.full_name || user.username}</a>
									<span class="user-email">{user.email}</span>
								</div>
							</td>
							<td>
								{#if isCurrentAdminUser(user.id)}
									<span class="locked-role">{draft?.role || user.role}</span>
								{:else}
									<select value={draft?.role || user.role} onchange={(e) => updateDraftRole(user.id, (e.currentTarget as HTMLSelectElement).value as UserRole)}>
										<option value="teacher">Teacher</option>
										<option value="vetter">Vetter</option>
										<option value="admin">Admin</option>
									</select>
								{/if}
							</td>
							<td>
								<label class="cell-check">
									<input
										type="checkbox"
										aria-label={`Set ${user.username} as active`}
										checked={draft?.is_active ?? user.is_active}
										onchange={(e) => {
											const checked = (e.currentTarget as HTMLInputElement).checked;
											drafts = { ...drafts, [user.id]: { ...(draft || { role: user.role, is_active: user.is_active, can_manage_groups: user.can_manage_groups, can_generate: user.can_generate, can_vet: user.can_vet }), is_active: checked } };
										}}
									/>
								</label>
							</td>
							<td>
                            <label class="cell-check">
								<input
									type="checkbox"
									checked={draft?.can_manage_groups ?? user.can_manage_groups}
									onchange={(e) => {
										const checked = (e.currentTarget as HTMLInputElement).checked;
										drafts = { ...drafts, [user.id]: { ...(draft || { role: user.role, is_active: user.is_active, can_manage_groups: user.can_manage_groups, can_generate: user.can_generate, can_vet: user.can_vet }), can_manage_groups: checked } };
									}}
								/>
                            </label>
							</td>
							<td>
                                <label class="cell-check">
                                    <input
                                        type="checkbox"
                                        checked={draft?.can_generate ?? user.can_generate}
                                        onchange={(e) => {
                                            const checked = (e.currentTarget as HTMLInputElement).checked;
                                            drafts = { ...drafts, [user.id]: { ...(draft || { role: user.role, is_active: user.is_active, can_manage_groups: user.can_manage_groups, can_generate: user.can_generate, can_vet: user.can_vet }), can_generate: checked } };
                                        }}
                                    />
                                </label>
							</td>
							<td>
                                <label class="cell-check">
                                    <input
                                        type="checkbox"
                                        checked={draft?.can_vet ?? user.can_vet}
                                        onchange={(e) => {
                                            const checked = (e.currentTarget as HTMLInputElement).checked;
                                            drafts = { ...drafts, [user.id]: { ...(draft || { role: user.role, is_active: user.is_active, can_manage_groups: user.can_manage_groups, can_generate: user.can_generate, can_vet: user.can_vet }), can_vet: checked } };
                                        }}
                                    />
                                </label>
							</td>
							<td>{formatDate(user.last_login_at)}</td>
							<td>
								<button
									class="save-btn"
									class:save-btn--dirty={hasUserChanges(user)}
									onclick={() => saveUser(user)}
									disabled={saveBusyByUser[user.id] || !hasUserChanges(user)}
								>
									{saveBusyByUser[user.id] ? 'Saving...' : 'Save'}
								</button>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>

		<div class="mobile-list mobile-only animate-fade-in">
			{#each filteredUsers as user}
				{@const draft = drafts[user.id]}
				<div class="mobile-card glass-panel">
					<div class="user-cell">
						<a class="user-name user-link" href={userDetailHref(user.id)}>{user.full_name || user.username}</a>
						<span class="user-email">{user.email}</span>
					</div>
					<div class="mobile-grid">
						{#if isCurrentAdminUser(user.id)}
							<div class="locked-role-mobile">Role: <strong>{draft?.role || user.role}</strong></div>
						{:else}
							<label>Role
								<select value={draft?.role || user.role} onchange={(e) => updateDraftRole(user.id, (e.currentTarget as HTMLSelectElement).value as UserRole)}>
									<option value="teacher">Teacher</option>
									<option value="vetter">Vetter</option>
									<option value="admin">Admin</option>
								</select>
							</label>
						{/if}
						<label><input type="checkbox" checked={draft?.is_active ?? user.is_active} onchange={(e) => drafts = { ...drafts, [user.id]: { ...(draft || { role: user.role, is_active: user.is_active, can_manage_groups: user.can_manage_groups, can_generate: user.can_generate, can_vet: user.can_vet }), is_active: (e.currentTarget as HTMLInputElement).checked } }} /> Active</label>
						<label><input type="checkbox" checked={draft?.can_manage_groups ?? user.can_manage_groups} onchange={(e) => drafts = { ...drafts, [user.id]: { ...(draft || { role: user.role, is_active: user.is_active, can_manage_groups: user.can_manage_groups, can_generate: user.can_generate, can_vet: user.can_vet }), can_manage_groups: (e.currentTarget as HTMLInputElement).checked } }} /> Manage groups</label>
						<label><input type="checkbox" checked={draft?.can_generate ?? user.can_generate} onchange={(e) => drafts = { ...drafts, [user.id]: { ...(draft || { role: user.role, is_active: user.is_active, can_manage_groups: user.can_manage_groups, can_generate: user.can_generate, can_vet: user.can_vet }), can_generate: (e.currentTarget as HTMLInputElement).checked } }} /> Generate</label>
						<label><input type="checkbox" checked={draft?.can_vet ?? user.can_vet} onchange={(e) => drafts = { ...drafts, [user.id]: { ...(draft || { role: user.role, is_active: user.is_active, can_manage_groups: user.can_manage_groups, can_generate: user.can_generate, can_vet: user.can_vet }), can_vet: (e.currentTarget as HTMLInputElement).checked } }} /> Vet</label>
					</div>
					<div class="card-meta">Last login: {formatDate(user.last_login_at)}</div>
					<button
						class="save-btn"
						class:save-btn--dirty={hasUserChanges(user)}
						onclick={() => saveUser(user)}
						disabled={saveBusyByUser[user.id] || !hasUserChanges(user)}
					>
						{saveBusyByUser[user.id] ? 'Saving...' : 'Save Changes'}
					</button>
				</div>
			{/each}
		</div>
	{/if}
</div>

<style>
	.page {
		max-width: 1220px;
		margin: 0 auto;
		padding: 2rem 1.5rem 2.5rem;
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}

	.toolbar {
		display: flex;
		gap: 0.75rem;
		padding: 1rem;
		border-radius: 1rem;
	}

	.search-input,
	input:not([type='checkbox']),
	select {
		width: 100%;
		padding: 0.72rem 0.9rem;
		border-radius: 0.75rem;
		border: 1px solid var(--theme-glass-border);
		background: var(--theme-input-bg);
		color: var(--theme-text);
		font: inherit;
	}

	.search-input {
		flex: 1;
	}

	.toolbar-actions {
		display: flex;
		align-items: center;
		justify-content: flex-end;
		gap: 0.75rem;
	}

	.primary-btn {
		padding: 0.72rem 1rem;
		border-radius: 0.8rem;
		border: 1px solid color-mix(in srgb, var(--theme-primary) 45%, var(--theme-glass-border));
		background: linear-gradient(180deg, color-mix(in srgb, var(--theme-primary) 85%, #ffffff 15%) 0%, var(--theme-primary) 100%);
		color: #061219;
		font-weight: 700;
		cursor: pointer;
	}

	.secondary-btn {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		gap: 0.5rem;
		padding: 0.72rem 1rem;
		border-radius: 0.8rem;
		border: 1px solid color-mix(in srgb, var(--theme-glass-border) 88%, transparent);
		background: color-mix(in srgb, var(--theme-input-bg) 84%, transparent);
		color: var(--theme-text);
		font-weight: 700;
		cursor: pointer;
	}

	.toolbar-badge {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		min-width: 1.35rem;
		height: 1.35rem;
		padding: 0 0.35rem;
		border-radius: 999px;
		background: color-mix(in srgb, var(--theme-primary) 22%, transparent);
		border: 1px solid color-mix(in srgb, var(--theme-primary) 50%, var(--theme-glass-border));
		color: var(--theme-text);
		font-size: 0.72rem;
		font-weight: 700;
	}

	.save-btn {
		padding: 0.72rem 1rem;
		border-radius: 0.8rem;
		border: 1px solid color-mix(in srgb, var(--theme-glass-border) 88%, transparent);
		background: color-mix(in srgb, var(--theme-input-bg) 84%, transparent);
		color: var(--theme-text-muted);
		font-weight: 700;
		cursor: pointer;
	}

	.approve-btn {
		padding: 0.52rem 0.75rem;
		border-radius: 0.72rem;
		border: 1px solid color-mix(in srgb, #10b981 45%, var(--theme-glass-border));
		background: color-mix(in srgb, #10b981 18%, var(--theme-input-bg));
		color: var(--theme-text);
		font-weight: 700;
		cursor: pointer;
	}

	.secondary-link {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		padding: 0.62rem 0.82rem;
		border-radius: 0.75rem;
		border: 1px solid color-mix(in srgb, var(--theme-glass-border) 88%, transparent);
		background: color-mix(in srgb, var(--theme-input-bg) 84%, transparent);
		color: var(--theme-text);
		text-decoration: none;
		font-weight: 700;
	}

	.save-btn.save-btn--dirty {
		border: 1px solid color-mix(in srgb, var(--theme-primary) 45%, var(--theme-glass-border));
		background: linear-gradient(180deg, color-mix(in srgb, var(--theme-primary) 85%, #ffffff 15%) 0%, var(--theme-primary) 100%);
		color: #f8fafc;
	}

	.primary-btn:hover:not(:disabled),
	.secondary-btn:hover:not(:disabled),
	.save-btn.save-btn--dirty:hover:not(:disabled),
	.approve-btn:hover:not(:disabled),
	.secondary-link:hover {
		filter: brightness(1.05);
	}

	input[type='checkbox'] {
		-webkit-appearance: none !important;
		appearance: none !important;
		width: 1.1rem;
		height: 1.1rem;
		margin: 0;
		padding: 0;
		cursor: pointer;
		border-radius: 0.28rem;
		border: 1.5px solid color-mix(in srgb, var(--theme-text-muted) 60%, transparent) !important;
		background: transparent !important;
		display: inline-grid;
		place-content: center;
		transition: border-color 0.15s ease, box-shadow 0.15s ease;
	}

	input[type='checkbox']::after {
		content: '✓';
		font-size: 0.86rem;
		line-height: 1;
		font-weight: 800;
		color: var(--theme-primary);
		transform: scale(0);
		opacity: 0;
		transition: transform 0.15s ease, opacity 0.15s ease;
	}

	input[type='checkbox']:checked {
		border-color: var(--theme-primary) !important;
		/* box-shadow: 0 0 0 2px color-mix(in srgb, var(--theme-primary) 30%, transparent); */
	}

	input[type='checkbox']:checked::after {
		transform: scale(1);
		opacity: 1;
	}

	input[type='checkbox']:focus-visible {
		outline: 2px solid rgba(245, 158, 11, 0.7);
		outline-offset: 1px;
	}

	/* td > input[type='checkbox'] {
		display: block;
		margin: 0 auto;
	} */

	.primary-btn:disabled,
	.secondary-btn:disabled,
	.save-btn:disabled,
	.approve-btn:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}

	.error-banner,
	.success-banner {
		padding: 0.9rem 1rem;
		border-radius: 0.9rem;
	}

	.error-banner {
		background: rgba(239, 68, 68, 0.12);
		border: 1px solid rgba(239, 68, 68, 0.3);
		color: #fca5a5;
	}

	.success-banner {
		background: rgba(16, 185, 129, 0.14);
		border: 1px solid rgba(16, 185, 129, 0.35);
		color: #6ee7b7;
	}

	.create-panel {
		padding: 1rem;
		border-radius: 1rem;
		display: flex;
		flex-direction: column;
		gap: 0.9rem;
	}

	.create-panel h2 {
		margin: 0;
		font-size: 1.05rem;
	}

	.create-grid {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 0.8rem;
	}

	.field {
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
	}

	.field-span-2 {
		grid-column: span 2;
	}

	.field span {
		font-size: 0.78rem;
		color: var(--theme-text-muted);
	}

	.checkbox-inline {
		justify-content: center;
	}

	.permission-grid {
		display: flex;
		flex-wrap: wrap;
		gap: 1rem;
		font-size: 0.9rem;
	}

	.actions-row {
		display: flex;
		justify-content: flex-end;
	}

	.modal-backdrop {
		position: fixed;
		inset: 0;
		z-index: 80;
		padding: 1.4rem;
		background: rgba(2, 6, 23, 0.58);
		backdrop-filter: blur(10px);
		-webkit-backdrop-filter: blur(10px);
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.approval-modal {
		width: min(980px, 100%);
		max-height: min(88vh, 940px);
		padding: 1.1rem;
		border-radius: 1.2rem;
		display: flex;
		flex-direction: column;
		gap: 1rem;
		overflow: hidden;
	}

	.approval-modal-header {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 1rem;
	}

	.modal-eyebrow {
		margin: 0 0 0.3rem;
		font-size: 0.75rem;
		font-weight: 700;
		letter-spacing: 0.12em;
		text-transform: uppercase;
		color: var(--theme-text-muted);
	}

	.approval-modal-header h2 {
		margin: 0;
		font-size: 1.35rem;
	}

	.modal-copy {
		margin: 0.35rem 0 0;
		max-width: 60ch;
		color: var(--theme-text-muted);
	}

	.approval-modal-toolbar {
		display: flex;
		align-items: center;
		gap: 0.75rem;
	}

	.approval-search {
		flex: 1;
	}

	.approval-modal-actions {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: flex-end;
		gap: 0.75rem;
	}

	.bulk-select-label {
		display: inline-flex;
		align-items: center;
		gap: 0.55rem;
		padding: 0.68rem 0.85rem;
		border-radius: 0.8rem;
		border: 1px solid color-mix(in srgb, var(--theme-glass-border) 88%, transparent);
		background: color-mix(in srgb, var(--theme-input-bg) 84%, transparent);
		color: var(--theme-text);
		font-size: 0.9rem;
	}

	.approval-empty {
		padding: 1.2rem;
		border-radius: 1rem;
		text-align: center;
	}

	.approval-empty p {
		margin: 0;
		color: var(--theme-text-muted);
	}

	.approval-list {
		display: flex;
		flex-direction: column;
		gap: 0.8rem;
		overflow: auto;
		padding-right: 0.15rem;
	}

	.approval-card {
		display: grid;
		grid-template-columns: auto minmax(0, 1fr) auto;
		align-items: center;
		gap: 0.9rem;
		padding: 0.95rem 1rem;
		border-radius: 1rem;
		border: 1px solid rgba(255, 255, 255, 0.06);
	}

	.approval-card--highlight {
		border-color: color-mix(in srgb, var(--theme-primary) 55%, var(--theme-glass-border));
		box-shadow: 0 0 0 1px color-mix(in srgb, var(--theme-primary) 30%, transparent);
	}

	.approval-check {
		display: flex;
		align-items: center;
		justify-content: center;
		padding-top: 0.1rem;
	}

	.approval-card-main {
		min-width: 0;
		display: flex;
		flex-direction: column;
		gap: 0.45rem;
	}

	.approval-card-heading {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.65rem;
	}

	.approval-card-meta {
		display: flex;
		flex-wrap: wrap;
		gap: 0.6rem 0.85rem;
		font-size: 0.84rem;
		color: var(--theme-text-muted);
	}

	.approval-card-meta span {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		min-width: 0;
	}

	.approval-card-actions {
		display: flex;
		align-items: center;
		gap: 0.65rem;
	}

	.table-wrap {
		padding: 0.85rem;
		border-radius: 1rem;
		overflow-x: auto;
	}

	.data-table {
		width: 100%;
		border-collapse: collapse;
		table-layout: fixed;
	}

	.col-user {
		width: 26%;
	}

	.col-role {
		width: 12%;
	}

	.col-status,
	.col-perm {
		width: 9%;
	}

	.col-login {
		width: 18%;
	}

	.col-action {
		width: 8%;
	}

	th,
	td {
		padding: 0.7rem;
		border-bottom: 1px solid rgba(255, 255, 255, 0.08);
		text-align: left;
		font-size: 0.9rem;
	}

	.user-cell {
		display: flex;
		flex-direction: column;
		gap: 0.12rem;
	}

	.user-name {
		font-weight: 700;
	}

	.user-link {
		text-decoration: none;
		color: inherit;
	}

	.user-link:hover {
		text-decoration: underline;
		text-decoration-color: color-mix(in srgb, var(--theme-primary) 65%, transparent);
	}

	.user-email {
		font-size: 0.78rem;
		color: var(--theme-text-muted);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.status-pill {
		display: inline-flex;
		align-items: center;
		width: fit-content;
		padding: 0.2rem 0.52rem;
		border-radius: 999px;
		font-size: 0.72rem;
		font-weight: 700;
	}

	.status-pill--pending {
		background: rgba(250, 204, 21, 0.12);
		border: 1px solid rgba(250, 204, 21, 0.3);
		color: #fde68a;
	}

	.locked-role {
		display: inline-flex;
		align-items: center;
		padding: 0.4rem 0.6rem;
		border-radius: 0.6rem;
		font-size: 0.82rem;
		font-weight: 700;
		text-transform: capitalize;
		background: color-mix(in srgb, var(--theme-input-bg) 78%, transparent);
		border: 1px solid var(--theme-glass-border);
		color: var(--theme-text);
	}

	.locked-role-mobile {
		font-size: 0.86rem;
		color: var(--theme-text);
	}

	.cell-check {
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.permission-grid label,
	.mobile-grid label {
		display: inline-flex;
		align-items: center;
		gap: 0.45rem;
		color: var(--theme-text);
	}

	:global([data-color-mode='light']) .primary-btn,
	:global([data-color-mode='light']) .save-btn.save-btn--dirty {
		color: #052232;
	}

	:global([data-color-mode='dark']) .primary-btn,
	:global([data-color-mode='dark']) .save-btn.save-btn--dirty {
		color: #f8fafc;
	}

	:global([data-color-mode='light']) .search-input,
	:global([data-color-mode='light']) input:not([type='checkbox']),
	:global([data-color-mode='light']) select {
		background: #ffffff;
		border-color: rgba(148, 163, 184, 0.42);
		color: #0f172a;
	}

	:global([data-color-mode='light']) .table-wrap,
	:global([data-color-mode='light']) .create-panel,
	:global([data-color-mode='light']) .toolbar,
	:global([data-color-mode='light']) .approval-modal,
	:global([data-color-mode='light']) .approval-empty,
	:global([data-color-mode='light']) .approval-card,
	:global([data-color-mode='light']) .mobile-card,
	:global([data-color-mode='light']) .center-state.glass-panel {
		background: #ffffff;
		border: 1px solid rgba(148, 163, 184, 0.3);
		box-shadow: 0 14px 34px rgba(15, 23, 42, 0.08);
	}

	:global([data-color-mode='light']) .secondary-btn,
	:global([data-color-mode='light']) .secondary-link,
	:global([data-color-mode='light']) .bulk-select-label {
		background: #ffffff;
		border-color: rgba(148, 163, 184, 0.42);
		color: #0f172a;
	}

	:global([data-color-mode='light']) .modal-backdrop {
		background: rgba(226, 232, 240, 0.55);
	}

	:global([data-color-mode='light']) th,
	:global([data-color-mode='light']) td {
		border-bottom-color: rgba(148, 163, 184, 0.32);
	}

	:global([data-color-mode='light']) input[type='checkbox'] {
		border-color: rgba(71, 85, 105, 0.55) !important;
	}

	.mobile-list {
		display: none;
	}

	.mobile-card {
		padding: 0.9rem;
		border-radius: 0.9rem;
		display: flex;
		flex-direction: column;
		gap: 0.7rem;
	}

	.mobile-grid {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 0.6rem;
		font-size: 0.86rem;
	}

	.card-meta {
		font-size: 0.78rem;
		color: var(--theme-text-muted);
	}

	.center-state {
		padding: 1.5rem;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.75rem;
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
		width: 1.6rem;
		height: 1.6rem;
		border-radius: 999px;
		border: 2px solid rgba(255, 255, 255, 0.2);
		border-top-color: var(--theme-primary);
		animation: spin 1s linear infinite;
	}

	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}

	@media (max-width: 960px) {
		.create-grid {
			grid-template-columns: repeat(2, minmax(0, 1fr));
		}

		.toolbar-actions {
			width: 100%;
			justify-content: flex-start;
		}
	}

	@media (max-width: 860px) {
		.approval-modal {
			max-height: 90vh;
		}

		.approval-modal-header,
		.approval-modal-toolbar {
			flex-direction: column;
			align-items: stretch;
		}

		.approval-modal-actions {
			justify-content: flex-start;
		}

		.approval-card {
			grid-template-columns: auto minmax(0, 1fr);
		}

		.approval-card-actions {
			grid-column: 1 / -1;
			justify-content: flex-end;
			padding-top: 0.2rem;
		}
	}

	@media (max-width: 768px) {
		.page {
			padding: 1.2rem 0.9rem 1.6rem;
		}

		.toolbar {
			flex-direction: column;
		}

		.toolbar-actions {
			flex-direction: column;
			align-items: stretch;
		}

		.toolbar-actions > button {
			width: 100%;
		}

		.modal-backdrop {
			padding: 0.75rem;
			align-items: flex-end;
		}

		.approval-modal {
			width: 100%;
			max-height: 92vh;
			padding: 0.95rem;
		}

		.approval-modal-actions {
			width: 100%;
		}

		.bulk-select-label,
		.approval-card-actions,
		.approval-modal-actions > button,
		.secondary-link,
		.approve-btn {
			width: 100%;
		}

		.approval-card {
			grid-template-columns: 1fr;
		}

		.approval-check {
			justify-content: flex-start;
		}

		.approval-card-actions {
			justify-content: stretch;
			flex-direction: column;
		}

		.table-wrap {
			display: none;
		}

		.mobile-list {
			display: grid;
			gap: 0.7rem;
		}

		.mobile-grid {
			grid-template-columns: 1fr;
		}

		.create-grid {
			grid-template-columns: 1fr;
		}

		.field-span-2 {
			grid-column: span 1;
		}
	}
</style>
