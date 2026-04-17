<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { session } from '$lib/session';
	import { listAdminSubjects, type AdminSubjectSummary } from '$lib/api/admin';
	import { updateSubject } from '$lib/api/subjects';

	let loading = $state(true);
	let error = $state('');
	let subjects = $state<AdminSubjectSummary[]>([]);
	let query = $state('');
	let editingSubjectId = $state('');
	let editingName = $state('');
	let editingCode = $state('');
	let saveBusySubjectId = $state('');

	onMount(() => {
		const unsub = session.subscribe((s) => {
			if (!s || s.user.role !== 'admin') {
				goto('/admin/login');
			}
		});
		loadSubjects();
		return unsub;
	});

	async function loadSubjects() {
		loading = true;
		error = '';
		try {
			subjects = await listAdminSubjects();
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to load subjects';
		} finally {
			loading = false;
		}
	}

	const filteredSubjects = $derived.by(() => {
		const search = query.trim().toLowerCase();
		if (!search) return subjects;
		return subjects.filter((subject) => {
			return [
				subject.name,
				subject.code,
				subject.teacher_name ?? '',
				subject.teacher_email ?? ''
			].some((value) => value.toLowerCase().includes(search));
		});
	});

	const totals = $derived.by(() => {
		return filteredSubjects.reduce(
			(acc, subject) => {
				acc.totalTopics += subject.total_topics;
				acc.totalQuestions += subject.total_questions;
				acc.totalPending += subject.total_pending;
				return acc;
			},
			{ totalTopics: 0, totalQuestions: 0, totalPending: 0 }
		);
	});

	function openSubject(subjectId: string) {
		goto(`/admin/subjects/${subjectId}`);
	}

	function startInlineEdit(subject: AdminSubjectSummary): void {
		editingSubjectId = subject.id;
		editingName = subject.name;
		editingCode = subject.code;
	}

	function cancelInlineEdit(): void {
		editingSubjectId = '';
		editingName = '';
		editingCode = '';
	}

	function hasInlineChanges(subject: AdminSubjectSummary): boolean {
		if (editingSubjectId !== subject.id) return false;
		return editingName.trim() !== subject.name || editingCode.trim() !== subject.code;
	}

	async function saveInlineEdit(subject: AdminSubjectSummary): Promise<void> {
		if (!hasInlineChanges(subject)) {
			cancelInlineEdit();
			return;
		}

		const nextName = editingName.trim();
		const nextCode = editingCode.trim();
		if (!nextName || !nextCode) {
			error = 'Subject name and code are required';
			return;
		}

		error = '';
		saveBusySubjectId = subject.id;
		try {
			await updateSubject(subject.id, {
				name: nextName,
				code: nextCode
			});
			subjects = subjects.map((item) =>
				item.id === subject.id
					? {
						...item,
						name: nextName,
						code: nextCode
					}
					: item
			);
			cancelInlineEdit();
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to update subject';
		} finally {
			saveBusySubjectId = '';
		}
	}

	function userDetailHref(userId: string): string {
		return `/admin/users/${userId}`;
	}

	function formatDate(value: string) {
		return new Date(value).toLocaleDateString();
	}

	function updateEditableName(event: Event) {
		editingName = ((event.currentTarget as HTMLElement).textContent || '').replace(/\u00a0/g, ' ');
	}

	function updateEditableCode(event: Event) {
		editingCode = ((event.currentTarget as HTMLElement).textContent || '').replace(/\u00a0/g, ' ');
	}

	function seedEditableContent(node: HTMLElement, value: string) {
		node.textContent = value;
		let lastValue = value;
		return {
			update(nextValue: string) {
				if (nextValue !== lastValue) {
					lastValue = nextValue;
					node.textContent = nextValue;
				}
			}
		};
	}
</script>

<svelte:head>
	<title>Admin Subjects — VQuest Trainer</title>
</svelte:head>

<div class="page">
	<!-- <div class="hero animate-fade-in">
		<div>
			<p class="eyebrow">Admin Console</p>
			<h1 class="title font-serif">Subjects</h1>
			<p class="subtitle">Browse every subject, see ownership, question inventory, and drill into topic-level vetting status.</p>
		</div>
	</div> -->

	<div class="toolbar glass-panel animate-slide-up">
		<input class="search-input" bind:value={query} placeholder="Search by subject, code, teacher, or email" />
		<div class="toolbar-actions">
			<a class="nav-btn" href="/admin/groups">Groups</a>
		</div>
		<!-- <button class="refresh-btn" onclick={loadSubjects}>Refresh</button> -->
	</div>

	{#if error}
		<div class="error-banner" role="alert">{error}</div>
	{/if}

	<div class="stats-row animate-slide-up">
		<div class="stat-card glass-panel">
			<span class="stat-value amber-text">{loading ? '…' : filteredSubjects.length}</span>
			<span class="stat-label">Subjects</span>
		</div>
		<div class="stat-card glass-panel">
			<span class="stat-value blue-text">{loading ? '…' : totals.totalTopics}</span>
			<span class="stat-label">Topics</span>
		</div>
		<div class="stat-card glass-panel">
			<span class="stat-value white-text">{loading ? '…' : totals.totalQuestions}</span>
			<span class="stat-label">Questions</span>
		</div>
		<div class="stat-card glass-panel">
			<span class="stat-value orange-text">{loading ? '…' : totals.totalPending}</span>
			<span class="stat-label">Pending</span>
		</div>
	</div>

	{#if loading}
		<div class="center-state loading-state">
			<div class="spinner"></div>
			<p>Loading subjects…</p>
		</div>
	{:else if filteredSubjects.length === 0}
		<div class="center-state glass-panel">
			<p>No subjects matched your search.</p>
		</div>
	{:else}
		<div class="table-wrap glass-panel animate-fade-in desktop-only">
			<table class="data-table">
				<thead>
					<tr>
						<th>S.No</th>
						<th>Subject</th>
						<th>Teacher</th>
						<th>T</th>
						<th>Q</th>
						<th>Q</th>
						<th>R</th>
						<th>P</th>
						<th>Created</th>
					</tr>
				</thead>
				<tbody>
					{#each filteredSubjects as subject, index}
						<tr>
							<td class="num">{index + 1}</td>
							<td>
								{#if editingSubjectId === subject.id}
									<div class="subject-cell editing-row">
										<span
											class="subject-name subject-editable"
											contenteditable="plaintext-only"
											role="textbox"
											tabindex="0"
											use:seedEditableContent={subject.name}
											oninput={updateEditableName}
										></span>
										<span
											class="subject-code subject-code-editable"
											contenteditable="plaintext-only"
											role="textbox"
											tabindex="0"
											use:seedEditableContent={subject.code}
											oninput={updateEditableCode}
										></span>
										<div class="inline-actions">
											<button
												type="button"
												class="icon-btn icon-btn-save"
												title="Save"
												onclick={() => saveInlineEdit(subject)}
												disabled={saveBusySubjectId === subject.id || !hasInlineChanges(subject)}
											>
												&#10003;
											</button>
											<button
												type="button"
												class="icon-btn icon-btn-cancel"
												title="Cancel"
												onclick={cancelInlineEdit}
												disabled={saveBusySubjectId === subject.id}
											>
												&#10005;
											</button>
										</div>
									</div>
								{:else}
									<div class="subject-cell">
										<button class="subject-inline-trigger" type="button" onclick={() => startInlineEdit(subject)}>
											<span class="subject-name">{subject.name}</span>
											<span class="subject-code">{subject.code}</span>
										</button>
									</div>
								{/if}
							</td>
							<td>
								<div class="owner-cell">
									{#if subject.teacher_id}
										<a class="owner-name user-link" href={userDetailHref(subject.teacher_id)}>{subject.teacher_name || 'Unknown teacher'}</a>
									{:else}
										<span class="owner-name">{subject.teacher_name || 'Unknown teacher'}</span>
									{/if}
									<span class="owner-email">{subject.teacher_email || 'No email'}</span>
								</div>
							</td>
							<td class="num">{subject.total_topics}</td>
							<td class="num">{subject.total_questions}</td>
							<td class="num green-text">{subject.total_approved}</td>
							<td class="num red-text">{subject.total_rejected}</td>
							<td class="num orange-text">{subject.total_pending}</td>
							<td>{formatDate(subject.created_at)}</td>
							<td>
								<button class="open-btn" onclick={() => openSubject(subject.id)}>Open</button>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>

		<div class="mobile-list mobile-only animate-fade-in">
			{#each filteredSubjects as subject}
				<div class="mobile-card glass-panel">
					{#if editingSubjectId === subject.id}
						<div class="subject-cell editing-row">
							<span
								class="subject-name subject-editable"
								contenteditable="plaintext-only"
								role="textbox"
								tabindex="0"
								use:seedEditableContent={subject.name}
								oninput={updateEditableName}
							></span>
							<span
								class="subject-code subject-code-editable"
								contenteditable="plaintext-only"
								role="textbox"
								tabindex="0"
								use:seedEditableContent={subject.code}
								oninput={updateEditableCode}
							></span>
							<div class="inline-actions">
								<button
									type="button"
									class="icon-btn icon-btn-save"
									title="Save"
									onclick={() => saveInlineEdit(subject)}
									disabled={saveBusySubjectId === subject.id || !hasInlineChanges(subject)}
								>
									&#10003;
								</button>
								<button
									type="button"
									class="icon-btn icon-btn-cancel"
									title="Cancel"
									onclick={cancelInlineEdit}
									disabled={saveBusySubjectId === subject.id}
								>
									&#10005;
								</button>
							</div>
						</div>
					{:else}
						<div class="subject-cell">
							<button class="subject-inline-trigger" type="button" onclick={() => startInlineEdit(subject)}>
								<span class="subject-name">{subject.name}</span>
								<span class="subject-code">{subject.code}</span>
							</button>
						</div>
					{/if}
					<div class="owner-cell">
						{#if subject.teacher_id}
							<a class="owner-name user-link" href={userDetailHref(subject.teacher_id)}>{subject.teacher_name || 'Unknown teacher'}</a>
						{:else}
							<span class="owner-name">{subject.teacher_name || 'Unknown teacher'}</span>
						{/if}
						<span class="owner-email">{subject.teacher_email || 'No email'}</span>
					</div>
					<div class="mobile-metrics">
						<span>Topics <strong>{subject.total_topics}</strong></span>
						<span>Questions <strong>{subject.total_questions}</strong></span>
						<span class="green-text">Approved <strong>{subject.total_approved}</strong></span>
						<span class="red-text">Rejected <strong>{subject.total_rejected}</strong></span>
						<span class="orange-text">Pending <strong>{subject.total_pending}</strong></span>
						<span>Created <strong>{formatDate(subject.created_at)}</strong></span>
					</div>
					<button class="open-btn" onclick={() => openSubject(subject.id)}>Open Subject</button>
				</div>
			{/each}
		</div>
	{/if}
</div>

<style>
	.page {
		max-width: 1120px;
		margin: 0 auto;
		padding: 2rem 1.5rem 2.5rem;
		display: flex;
		flex-direction: column;
		gap: 1.25rem;
	}

	/* .hero {
		padding-top: 0.5rem;
	}

	.eyebrow {
		margin: 0 0 0.35rem;
		font-size: 0.78rem;
		font-weight: 700;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: #fbbf24;
	}

	.title {
		margin: 0;
		font-size: 2rem;
		font-weight: 800;
		color: var(--theme-text);
	}

	.subtitle {
		margin: 0.5rem 0 0;
		max-width: 48rem;
		color: var(--theme-text-muted);
		line-height: 1.6;
	} */

	.toolbar {
		display: flex;
		gap: 0.75rem;
		padding: 1rem;
		border-radius: 1rem;
	}

	.toolbar-actions {
		display: flex;
		gap: 0.75rem;
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

	.nav-btn {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		padding: 0.85rem 1rem;
		border-radius: 0.85rem;
		border: 1px solid color-mix(in srgb, var(--theme-primary) 45%, var(--theme-glass-border));
		background: color-mix(in srgb, var(--theme-primary) 16%, var(--theme-input-bg));
		color: var(--theme-text);
		font: inherit;
		font-weight: 700;
		text-decoration: none;
	}

	/* .refresh-btn {
		padding: 0.85rem 1rem;
		border-radius: 0.85rem;
		border: 1px solid rgba(245, 158, 11, 0.3);
		background: rgba(245, 158, 11, 0.15);
		color: #fbbf24;
		font: inherit;
		font-weight: 700;
		cursor: pointer;
	} */

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

	.table-wrap {
		overflow-x: auto;
		border-radius: 1rem;
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
		min-width: 900px;
	}

	.data-table th,
	.data-table td {
		padding: 0.75rem 0.8rem;
		border-bottom: 1px solid rgba(148, 163, 184, 0.24);
		text-align: left;
		font-size: 0.86rem;
	}

	.data-table th {
		font-size: 0.72rem;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		font-weight: 700;
		color: var(--theme-text-muted);
	}

	.subject-code {
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

	.subject-name {
		font-size: 0.95rem;
		font-weight: 700;
		line-height: 1.35;
		color: var(--theme-text);
	}

	.subject-cell,
	.owner-cell {
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
	}

	.subject-inline-trigger {
		padding: 0;
		border: 0;
		background: transparent;
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: 0.15rem;
		cursor: text;
		text-align: left;
		font: inherit;
		color: inherit;
	}

	.subject-inline-trigger:hover .subject-name,
	.subject-inline-trigger:hover .subject-code {
		text-decoration: underline;
		text-decoration-color: color-mix(in srgb, var(--theme-primary) 60%, transparent);
	}

	.editing-row {
		gap: 0.35rem;
	}

	.subject-editable {
		border-radius: 0.45rem;
		padding: 0.2rem 0.35rem;
		outline: 1px solid color-mix(in srgb, var(--theme-primary) 35%, var(--theme-glass-border));
		background: color-mix(in srgb, var(--theme-input-bg) 86%, transparent);
		min-width: 6rem;
	}

	.subject-editable:focus-visible {
		outline: 2px solid color-mix(in srgb, var(--theme-primary) 72%, transparent);
	}

	.subject-code-editable {
		display: inline-flex;
		align-items: center;
		justify-content: center;
	}

	.inline-actions {
		display: inline-flex;
		gap: 0.28rem;
		align-items: center;
	}

	.icon-btn {
		width: 1.55rem;
		height: 1.55rem;
		border-radius: 999px;
		border: 1px solid color-mix(in srgb, var(--theme-glass-border) 80%, transparent);
		background: color-mix(in srgb, var(--theme-input-bg) 84%, transparent);
		color: var(--theme-text);
		font-size: 0.78rem;
		font-weight: 800;
		line-height: 1;
		padding: 0;
		cursor: pointer;
	}

	.icon-btn-save {
		color: color-mix(in srgb, #34d399 80%, var(--theme-text));
	}

	.icon-btn-cancel {
		color: color-mix(in srgb, #f87171 78%, var(--theme-text));
	}

	.icon-btn:disabled {
		opacity: 0.45;
		cursor: not-allowed;
	}

	.owner-name {
		font-weight: 700;
		color: var(--theme-text);
		font-size: 0.88rem;
	}

	.user-link {
		text-decoration: none;
	}

	.user-link:hover {
		text-decoration: underline;
		text-decoration-color: color-mix(in srgb, var(--theme-primary) 65%, transparent);
	}

	.owner-email {
		font-size: 0.78rem;
		color: var(--theme-text-muted);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.num {
		text-align: right;
		font-variant-numeric: tabular-nums;
	}

	.open-btn {
		padding: 0.5rem 0.8rem;
		border-radius: 0.7rem;
		border: 1px solid color-mix(in srgb, var(--theme-primary) 45%, var(--theme-glass-border));
		background: color-mix(in srgb, var(--theme-primary) 16%, var(--theme-input-bg));
		color: var(--theme-text);
		font-weight: 700;
		cursor: pointer;
	}

	.mobile-list {
		display: none;
		gap: 0.75rem;
	}

	.mobile-card {
		padding: 0.9rem;
		border-radius: 0.95rem;
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

		.toolbar {
			flex-direction: column;
		}

		.toolbar-actions {
			width: 100%;
		}

		.nav-btn {
			width: 100%;
		}

		.desktop-only {
			display: none;
		}

		.mobile-only {
			display: grid;
		}

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

	:global([data-color-mode='light']) .nav-btn {
		color: #0f172a;
	}

	:global([data-color-mode='light']) .stat-card,
	:global([data-color-mode='light']) .toolbar,
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

	:global([data-color-mode='light']) .open-btn {
		color: #0f172a;
	}

	:global([data-color-mode='light']) .subject-code {
		background: rgba(59, 130, 246, 0.14);
		color: #1d4ed8;
	}

	:global([data-color-mode='light']) .icon-btn {
		background: #ffffff;
		border-color: rgba(148, 163, 184, 0.45);
	}

	:global([data-color-mode='dark']) .subject-code {
		background: rgba(96, 165, 250, 0.24);
		color: #bfdbfe;
	}

	:global([data-color-mode='dark']) .icon-btn {
		background: color-mix(in srgb, var(--theme-input-bg) 84%, transparent);
		border-color: rgba(148, 163, 184, 0.22);
	}

	:global([data-color-mode='dark']) .icon-btn-save {
		color: #6ee7b7;
	}

	:global([data-color-mode='dark']) .icon-btn-cancel {
		color: #fca5a5;
	}
</style>
