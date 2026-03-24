<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { session } from '$lib/session';
	import {
		listAdminUsers,
		createAdminUser,
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

	let showCreateForm = $state(false);
	let createPayload = $state<AdminUserCreateRequest>({
		email: '',
		username: '',
		password: '',
		full_name: '',
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
		void loadUsers();
		return unsub;
	});

	function isCurrentAdminUser(userId: string): boolean {
		return userId === currentAdminUserId;
	}

	function userDetailHref(userId: string): string {
		return `/users/${userId}`;
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
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to load users';
		} finally {
			loading = false;
		}
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
			const payload: AdminUserCreateRequest = {
				email: createPayload.email.trim(),
				username: createPayload.username.trim().toLowerCase(),
				password: createPayload.password,
				full_name: createPayload.full_name?.trim() || undefined,
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
			users = users.map((u) => (u.id === updated.id ? updated : u));
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
			success = `Updated ${updated.username}`;
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to update user';
		} finally {
			saveBusyByUser = { ...saveBusyByUser, [user.id]: false };
		}
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

	function formatDate(value: string | null): string {
		if (!value) return '—';
		return new Date(value).toLocaleString();
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
		<button class="primary-btn" onclick={() => (showCreateForm = !showCreateForm)}>
			{showCreateForm ? 'Close' : 'Add User'}
		</button>
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

	{#if loading}
		<div class="center-state">
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
						<th>Status</th>
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

	.primary-btn {
		padding: 0.72rem 1rem;
		border-radius: 0.8rem;
		border: 1px solid color-mix(in srgb, var(--theme-primary) 45%, var(--theme-glass-border));
		background: linear-gradient(180deg, color-mix(in srgb, var(--theme-primary) 85%, #ffffff 15%) 0%, var(--theme-primary) 100%);
		color: #061219;
		font-weight: 700;
		cursor: pointer;
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

	.save-btn.save-btn--dirty {
		border: 1px solid color-mix(in srgb, var(--theme-primary) 45%, var(--theme-glass-border));
		background: linear-gradient(180deg, color-mix(in srgb, var(--theme-primary) 85%, #ffffff 15%) 0%, var(--theme-primary) 100%);
		color: #f8fafc;
	}

	.primary-btn:hover:not(:disabled),
	.save-btn.save-btn--dirty:hover:not(:disabled) {
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
	.save-btn:disabled {
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
	:global([data-color-mode='light']) .mobile-card,
	:global([data-color-mode='light']) .center-state.glass-panel {
		background: #ffffff;
		border: 1px solid rgba(148, 163, 184, 0.3);
		box-shadow: 0 14px 34px rgba(15, 23, 42, 0.08);
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
	}

	@media (max-width: 768px) {
		.page {
			padding: 1.2rem 0.9rem 1.6rem;
		}

		.toolbar {
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
	}
</style>
