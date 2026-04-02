<script lang="ts">
	import { onMount, tick } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { session } from '$lib/session';
	import {
		getAdminDashboard,
		listAdminSubjects,
		listAdminUsers,
		resetAdminUserPassword,
		type AdminSubjectSummary,
		type AdminUserSummary,
		type UserStats
	} from '$lib/api/admin';

	let loading = $state(true);
	let error = $state('');
	let user = $state<AdminUserSummary | null>(null);
	let userStats = $state<UserStats | null>(null);
	let assignedSubjects = $state<AdminSubjectSummary[]>([]);
	let routeUserId = $state('');
	let resetPassword = $state('');
	let confirmResetPassword = $state('');
	let resetBusy = $state(false);
	let resetError = $state('');
	let resetSuccess = $state('');
	let shouldFocusReset = $state(false);
	let resetSectionElement = $state<HTMLElement | null>(null);

	onMount(() => {
		const unsubSession = session.subscribe((s) => {
			if (!s || s.user.role !== 'admin') {
				goto('/admin/login');
			}
		});

		const unsubPage = page.subscribe(($page) => {
			const nextId = $page.params.id;
			const intent = $page.url.searchParams.get('intent');
			shouldFocusReset = intent === 'reset-password';
			if (intent === 'approve-registration' && nextId) {
				goto(`/admin/users?modal=approvals&user=${nextId}`, { replaceState: true });
				return;
			}
			if (shouldFocusReset && nextId && nextId === routeUserId) {
				void focusResetSection();
			}
			if (!nextId || nextId === routeUserId) return;
			routeUserId = nextId;
			void loadUserDetail(nextId);
		});

		return () => {
			unsubSession();
			unsubPage();
		};
	});

	async function loadUserDetail(userId: string) {
		loading = true;
		error = '';
		user = null;
		userStats = null;
		assignedSubjects = [];
		resetPassword = '';
		confirmResetPassword = '';
		resetError = '';
		resetSuccess = '';

		try {
			const [users, dashboard, subjects] = await Promise.all([
				listAdminUsers(),
				getAdminDashboard(),
				listAdminSubjects()
			]);

			const foundUser = users.find((u) => u.id === userId) || null;
			if (!foundUser) {
				error = 'User not found.';
				return;
			}

			user = foundUser;
			userStats = dashboard.users.find((u) => u.user_id === userId) || null;
			assignedSubjects = subjects.filter((s) => s.teacher_id === userId);
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to load user details';
		} finally {
			loading = false;
			if (shouldFocusReset) {
				await focusResetSection();
			}
		}
	}

	async function focusResetSection() {
		await tick();
		resetSectionElement?.scrollIntoView({ behavior: 'smooth', block: 'start' });
	}

	function openSubject(subjectId: string) {
		goto(`/admin/subjects/${subjectId}`);
	}

	async function handleAdminResetPassword() {
		if (!user || resetBusy) return;
		resetError = '';
		resetSuccess = '';

		if (resetPassword.trim().length < 8) {
			resetError = 'Password must be at least 8 characters.';
			return;
		}

		if (resetPassword !== confirmResetPassword) {
			resetError = 'Passwords do not match.';
			return;
		}

		resetBusy = true;
		try {
			const response = await resetAdminUserPassword(user.id, { new_password: resetPassword });
			resetSuccess = response.message;
			resetPassword = '';
			confirmResetPassword = '';
		} catch (e: unknown) {
			resetError = e instanceof Error ? e.message : 'Failed to reset password.';
		} finally {
			resetBusy = false;
		}
	}

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
	<title>User Details — Admin</title>
</svelte:head>

<div class="page">
	<div class="header glass-panel">
		<div>
			<p class="eyebrow">Admin User View</p>
			<h1 class="title">{user ? user.full_name || user.username : 'User Details'}</h1>
		</div>
		<div class="meta-card">
			<span class="meta-label">Role</span>
			<strong class="caps">{user?.role}</strong>
		</div>
		<a class="back-link" href="/admin/users">Back to User Management</a>
	</div>

	{#if error}
		<div class="error-banner" role="alert">{error}</div>
	{/if}

	{#if loading}
		<div class="center-state glass-panel">
			<div class="spinner"></div>
			<p>Loading user details...</p>
		</div>
	{:else if user}
		<div class="meta-grid">
			<div class="meta-card glass-panel">
				<span class="meta-label">Email</span>
				<strong>{user.email}</strong>
			</div>
			<div class="meta-card glass-panel">
				<span class="meta-label">Status</span>
				<strong>{user.is_active ? 'Active' : 'Disabled'}</strong>
			</div>
			<div class="meta-card glass-panel">
				<span class="meta-label">Approval</span>
				<strong>{user.is_approved ? 'Approved' : 'Pending Approval'}</strong>
			</div>
			<div class="meta-card glass-panel">
				<span class="meta-label">Last Login</span>
				<strong>{formatDate(user.last_login_at)}</strong>
			</div>
		</div>

		<div class="stats-grid">
			<div class="stat-card glass-panel">
				<span class="stat-label">Generated</span>
				<span class="stat-value">{userStats?.total_generated ?? 0}</span>
			</div>
			<div class="stat-card glass-panel">
				<span class="stat-label">Approved</span>
				<span class="stat-value green-text">{userStats?.total_approved ?? 0}</span>
			</div>
			<div class="stat-card glass-panel">
				<span class="stat-label">Rejected</span>
				<span class="stat-value red-text">{userStats?.total_rejected ?? 0}</span>
			</div>
			<div class="stat-card glass-panel">
				<span class="stat-label">Pending</span>
				<span class="stat-value orange-text">{userStats?.total_pending ?? 0}</span>
			</div>
			<div class="stat-card glass-panel">
				<span class="stat-label">Subjects</span>
				<span class="stat-value">{userStats?.subjects_count ?? assignedSubjects.length}</span>
			</div>
			<div class="stat-card glass-panel">
				<span class="stat-label">Topics</span>
				<span class="stat-value">{userStats?.topics_count ?? 0}</span>
			</div>
		</div>

		<section class="section glass-panel">
			<h2>Access Controls</h2>
			<div class="access-grid">
				<div class="access-item">
					<span>Manage Groups</span>
					<strong>{user.can_manage_groups ? 'Allowed' : 'Blocked'}</strong>
				</div>
				<div class="access-item">
					<span>Generate</span>
					<strong>{user.can_generate ? 'Allowed' : 'Blocked'}</strong>
				</div>
				<div class="access-item">
					<span>Vet</span>
					<strong>{user.can_vet ? 'Allowed' : 'Blocked'}</strong>
				</div>
			</div>
		</section>

		<section class="section glass-panel reset-section" bind:this={resetSectionElement}>
			<h2>Admin Password Reset</h2>
			<div class="reset-grid">
				<label class="field">
					<span>New Password</span>
					<input bind:value={resetPassword} type="password" placeholder="At least 8 characters" minlength="8" />
				</label>
				<label class="field">
					<span>Confirm Password</span>
					<input bind:value={confirmResetPassword} type="password" placeholder="Repeat the new password" minlength="8" />
				</label>
			</div>
			{#if resetError}
				<p class="feedback error">{resetError}</p>
			{/if}
			{#if resetSuccess}
				<p class="feedback success">{resetSuccess}</p>
			{/if}
			<div class="actions-row">
				<button class="open-btn" onclick={handleAdminResetPassword} disabled={resetBusy}>
					{resetBusy ? 'Resetting...' : 'Reset Password'}
				</button>
			</div>
		</section>

		<section class="section glass-panel">
			<h2>Assigned Subjects</h2>
			{#if assignedSubjects.length === 0}
				<p class="empty-msg">No subjects assigned to this user.</p>
			{:else}
				<div class="table-wrap desktop-only">
					<table class="data-table">
						<thead>
							<tr>
								<th>Subject</th>
								<th>Topics</th>
								<th>Questions</th>
								<th>Approved</th>
								<th>Rejected</th>
								<th>Pending</th>
								<th></th>
							</tr>
						</thead>
						<tbody>
							{#each assignedSubjects as subject}
								<tr>
									<td>
										<div class="subject-cell">
											<span class="subject-name">{subject.name}</span>
											<span class="subject-code">{subject.code}</span>
										</div>
									</td>
									<td class="num">{subject.total_topics}</td>
									<td class="num">{subject.total_questions}</td>
									<td class="num green-text">{subject.total_approved}</td>
									<td class="num red-text">{subject.total_rejected}</td>
									<td class="num orange-text">{subject.total_pending}</td>
									<td><button class="open-btn" onclick={() => openSubject(subject.id)}>Open</button></td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>

				<div class="mobile-list mobile-only">
					{#each assignedSubjects as subject}
						<div class="mobile-card">
							<div class="subject-cell">
								<span class="subject-name">{subject.name}</span>
								<span class="subject-code">{subject.code}</span>
							</div>
							<div class="mobile-metrics">
								<span>Topics <strong>{subject.total_topics}</strong></span>
								<span>Questions <strong>{subject.total_questions}</strong></span>
								<span class="green-text">Approved <strong>{subject.total_approved}</strong></span>
								<span class="red-text">Rejected <strong>{subject.total_rejected}</strong></span>
								<span class="orange-text">Pending <strong>{subject.total_pending}</strong></span>
							</div>
							<button class="open-btn" onclick={() => openSubject(subject.id)}>Open Subject</button>
						</div>
					{/each}
				</div>
			{/if}
		</section>
	{/if}
</div>

<style>
	.page {
		max-width: 1160px;
		margin: 0 auto;
		padding: 2rem 1.25rem 2.25rem;
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}

	.header {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		gap: 1rem;
		padding: 1rem;
		border-radius: 1rem;
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
		font-size: 1.5rem;
		color: var(--theme-text);
	}

	.back-link {
		display: inline-flex;
		align-items: center;
		padding: 0.55rem 0.8rem;
		border-radius: 0.7rem;
		font-weight: 700;
		color: var(--theme-text);
		background: color-mix(in srgb, var(--theme-input-bg) 84%, transparent);
		border: 1px solid var(--theme-glass-border);
	}

	.error-banner {
		padding: 0.85rem 0.95rem;
		border-radius: 0.8rem;
		background: rgba(239, 68, 68, 0.12);
		border: 1px solid rgba(239, 68, 68, 0.3);
		color: #fca5a5;
	}

	.meta-grid,
	.stats-grid {
		display: grid;
		grid-template-columns: repeat(4, minmax(0, 1fr));
		gap: 0.75rem;
	}

	.stats-grid {
		grid-template-columns: repeat(6, minmax(0, 1fr));
	}

	.meta-card,
	.stat-card {
		padding: 0.9rem;
		border-radius: 0.9rem;
		display: flex;
		flex-direction: column;
		gap: 0.2rem;
	}

	.meta-label,
	.stat-label {
		font-size: 0.74rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: var(--theme-text-muted);
	}

	.stat-value {
		font-size: 1.25rem;
		font-weight: 800;
		color: var(--theme-text);
	}

	.section {
		padding: 1rem;
		border-radius: 1rem;
	}

	.section h2 {
		margin: 0 0 0.85rem;
		font-size: 1.05rem;
		color: var(--theme-text);
	}

	.reset-grid {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 0.75rem;
	}

	.field {
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
	}

	.field span {
		font-size: 0.76rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: var(--theme-text-muted);
	}

	.field input {
		padding: 0.7rem 0.8rem;
		border-radius: 0.75rem;
		border: 1px solid var(--theme-glass-border);
		background: color-mix(in srgb, var(--theme-input-bg) 86%, transparent);
		color: var(--theme-text);
		font: inherit;
	}

	.actions-row {
		display: flex;
		justify-content: flex-end;
		margin-top: 0.85rem;
	}

	.feedback {
		margin: 0.85rem 0 0;
		padding: 0.75rem 0.85rem;
		border-radius: 0.8rem;
		font-size: 0.9rem;
	}

	.feedback.error {
		background: rgba(239, 68, 68, 0.12);
		border: 1px solid rgba(239, 68, 68, 0.3);
		color: #fca5a5;
	}

	.feedback.success {
		background: rgba(34, 197, 94, 0.12);
		border: 1px solid rgba(34, 197, 94, 0.28);
		color: #86efac;
	}

	.access-grid {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 0.65rem;
	}

	.access-item {
		padding: 0.7rem;
		border-radius: 0.75rem;
		border: 1px solid var(--theme-glass-border);
		background: color-mix(in srgb, var(--theme-input-bg) 86%, transparent);
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 0.7rem;
		color: var(--theme-text);
	}

	.table-wrap {
		overflow-x: auto;
		border-radius: 0.95rem;
		border: 1px solid var(--theme-glass-border);
		background: color-mix(in srgb, var(--theme-surface) 88%, transparent);
	}

	.desktop-only {
		display: block;
	}

	.mobile-only {
		display: none;
	}

	.data-table {
		width: 100%;
		min-width: 760px;
		border-collapse: collapse;
	}

	.data-table th,
	.data-table td {
		padding: 0.72rem;
		text-align: left;
		font-size: 0.86rem;
		border-bottom: 1px solid rgba(148, 163, 184, 0.24);
		color: var(--theme-text);
	}

	.data-table th {
		font-size: 0.72rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: var(--theme-text-muted);
	}

	.subject-cell {
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
	}

	.subject-name {
		font-weight: 700;
		color: var(--theme-text);
	}

	.subject-code {
		font-size: 0.72rem;
		font-weight: 700;
		display: inline-flex;
		align-items: center;
		width: fit-content;
		padding: 0.2rem 0.45rem;
		border-radius: 999px;
		background: color-mix(in srgb, rgba(59, 130, 246, 0.2) 70%, var(--theme-input-bg));
		color: color-mix(in srgb, #60a5fa 78%, var(--theme-text));
	}

	.num {
		text-align: right;
		font-variant-numeric: tabular-nums;
	}

	.open-btn {
		padding: 0.46rem 0.75rem;
		border-radius: 0.65rem;
		font-weight: 700;
		border: 1px solid color-mix(in srgb, var(--theme-primary) 45%, var(--theme-glass-border));
		background: color-mix(in srgb, var(--theme-primary) 16%, var(--theme-input-bg));
		color: var(--theme-text);
		cursor: pointer;
	}

	.open-btn:disabled {
		opacity: 0.65;
		cursor: not-allowed;
	}

	.mobile-list {
		display: none;
		gap: 0.65rem;
	}

	.mobile-card {
		border: 1px solid var(--theme-glass-border);
		border-radius: 0.85rem;
		padding: 0.75rem;
		display: flex;
		flex-direction: column;
		gap: 0.55rem;
	}

	.mobile-metrics {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 0.28rem 0.62rem;
		font-size: 0.8rem;
		color: var(--theme-text-muted);
	}

	.mobile-metrics strong {
		color: var(--theme-text);
	}

	.center-state {
		padding: 1.4rem;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.55rem;
		border-radius: 0.9rem;
		color: var(--theme-text-muted);
	}

	.spinner {
		width: 1.5rem;
		height: 1.5rem;
		border: 2px solid rgba(255, 255, 255, 0.18);
		border-top-color: var(--theme-primary);
		border-radius: 999px;
		animation: spin 1s linear infinite;
	}

	.empty-msg {
		margin: 0;
		color: var(--theme-text-muted);
	}

	.caps {
		text-transform: capitalize;
	}

	.green-text { color: #34d399; }
	.red-text { color: #f87171; }
	.orange-text { color: #fb923c; }

	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}

	@media (max-width: 980px) {
		.stats-grid {
			grid-template-columns: repeat(3, minmax(0, 1fr));
		}

		.reset-grid {
			grid-template-columns: 1fr;
		}

		.access-grid {
			grid-template-columns: 1fr;
		}
	}

	@media (max-width: 768px) {
		.header {
			flex-direction: column;
		}

		.meta-grid,
		.stats-grid {
			grid-template-columns: repeat(2, minmax(0, 1fr));
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

	:global([data-color-mode='light']) .header,
	:global([data-color-mode='light']) .meta-card,
	:global([data-color-mode='light']) .stat-card,
	:global([data-color-mode='light']) .section,
	:global([data-color-mode='light']) .center-state,
	:global([data-color-mode='light']) .mobile-card {
		background: #ffffff;
		border: 1px solid rgba(148, 163, 184, 0.3);
		box-shadow: 0 14px 34px rgba(15, 23, 42, 0.08);
	}

	:global([data-color-mode='light']) .access-item,
	:global([data-color-mode='light']) .back-link,
	:global([data-color-mode='light']) .open-btn {
		background: #f8fafc;
		border-color: rgba(148, 163, 184, 0.35);
		color: #0f172a;
	}

	:global([data-color-mode='light']) .data-table th,
	:global([data-color-mode='light']) .data-table td {
		border-bottom-color: rgba(148, 163, 184, 0.35);
	}

	:global([data-color-mode='light']) .table-wrap {
		background: rgba(255, 255, 255, 0.8);
		border-color: rgba(148, 163, 184, 0.38);
	}

	:global([data-color-mode='light']) .subject-code {
		background: rgba(59, 130, 246, 0.14);
		color: #1d4ed8;
	}

	:global([data-color-mode='dark']) .table-wrap {
		background: rgba(248, 250, 252, 0.1);
		border-color: rgba(203, 213, 225, 0.28);
	}

	:global([data-color-mode='dark']) .data-table td {
		color: #e5e7eb;
	}

	:global([data-color-mode='dark']) .subject-code {
		background: rgba(96, 165, 250, 0.24);
		color: #bfdbfe;
	}
</style>