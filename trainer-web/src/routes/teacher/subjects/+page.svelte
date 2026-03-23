<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { session } from '$lib/session';
	import { createSubject, listSubjects, type SubjectResponse } from '$lib/api/subjects';

	let loading = $state(true);
	let error = $state('');
	let subjects = $state<SubjectResponse[]>([]);
	let query = $state('');
	let addingRow = $state(false);
	let draftCode = $state('');
	let draftName = $state('');
	let saving = $state(false);
	let addError = $state('');

	onMount(() => {
		const unsub = session.subscribe((s) => {
			if (!s || s.user.role !== 'teacher') {
				goto('/teacher/login');
			}
		});
		void loadSubjects();
		return unsub;
	});

	async function loadSubjects() {
		loading = true;
		error = '';
		try {
			const response = await listSubjects(1, 100);
			subjects = response.subjects;
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
			return [subject.name, subject.code, subject.description ?? ''].some((value) =>
				value.toLowerCase().includes(search)
			);
		});
	});

	const totals = $derived.by(() => {
		return filteredSubjects.reduce(
			(acc, subject) => {
				acc.totalTopics += subject.total_topics;
				acc.totalQuestions += subject.total_questions;
				acc.totalPending += subject.total_pending ?? 0;
				acc.totalApproved += subject.total_approved ?? 0;
				acc.totalRejected += subject.total_rejected ?? 0;
				return acc;
			},
			{ totalTopics: 0, totalQuestions: 0, totalPending: 0, totalApproved: 0, totalRejected: 0 }
		);
	});

	function openSubject(subjectId: string) {
		goto(`/teacher/subjects/${subjectId}`);
	}

	function startAddRow() {
		if (saving) return;
		addingRow = true;
		addError = '';
	}

	function cancelAddRow() {
		if (saving) return;
		addingRow = false;
		draftCode = '';
		draftName = '';
		addError = '';
	}

	async function saveAddRow() {
		if (saving) return;
		const code = draftCode.trim().toUpperCase();
		const name = draftName.trim();
		if (!code || !name) {
			addError = 'Enter both subject code and name.';
			return;
		}

		saving = true;
		addError = '';
		try {
			await createSubject({ code, name });
			addingRow = false;
			draftCode = '';
			draftName = '';
			await loadSubjects();
		} catch (e: unknown) {
			addError = e instanceof Error ? e.message : 'Failed to create subject';
		} finally {
			saving = false;
		}
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
		<button class="add-subject-btn" onclick={startAddRow} disabled={saving || addingRow}>+ Add Subject</button>
	</div>

	<div class="toolbar animate-slide-up">
		<input class="search-input" bind:value={query} placeholder="Search by subject, code, or description" />
	</div>

	{#if error}
		<div class="error-banner" role="alert">{error}</div>
	{/if}

	{#if addError}
		<div class="error-banner" role="alert">{addError}</div>
	{/if}

	<div class="stats-row animate-slide-up">
		<div class="stat-card glass-panel">
			<span class="stat-value amber-text">{loading ? '...' : filteredSubjects.length}</span>
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
						<th>Name</th>
						<th>Questions</th>
						<th>Pending</th>
						<th>Approved</th>
						<th>Rejected</th>
					</tr>
				</thead>
				<tbody>
					{#if addingRow}
						<tr class="add-row">
							<td>
								<div class="name-stack">
									<div class="inline-inputs">
										<input class="cell-input code-input" bind:value={draftCode} placeholder="SUB101" maxlength="24" />
										<input class="cell-input" bind:value={draftName} placeholder="Subject Name" maxlength="120" />
									</div>
									<div class="inline-actions">
										<button class="table-btn primary" onclick={saveAddRow} disabled={saving}>{saving ? 'Saving...' : 'Save'}</button>
										<button class="table-btn" onclick={cancelAddRow} disabled={saving}>Cancel</button>
									</div>
								</div>
							</td>
							<td>-</td>
							<td>-</td>
							<td>-</td>
							<td>-</td>
						</tr>
					{/if}

					{#if filteredSubjects.length === 0}
						<tr>
							<td colspan="5" class="empty-cell">No subjects matched your search.</td>
						</tr>
					{:else}
						{#each filteredSubjects as subject}
							<tr class="subject-row" role="button" tabindex="0" onclick={() => openSubject(subject.id)} onkeydown={(event) => {
								if (event.key === 'Enter' || event.key === ' ') {
									event.preventDefault();
									openSubject(subject.id);
								}
							}}>
								<td>
									<div class="name-stack">
										<div class="name-header">
											<strong>{subject.name}</strong>
											<span class="code-chip">{subject.code}</span>
										</div>
										<!-- {#if subject.description}
											<span class="description">{subject.description}</span>
										{/if} -->
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

		<div class="subjects-mobile-list mobile-only animate-fade-in">
			{#if addingRow}
				<div class="subject-mobile-card glass-panel">
					<div class="inline-inputs">
						<input class="cell-input code-input" bind:value={draftCode} placeholder="SUB101" maxlength="24" />
						<input class="cell-input" bind:value={draftName} placeholder="Subject Name" maxlength="120" />
					</div>
					<div class="inline-actions">
						<button class="table-btn primary" onclick={saveAddRow} disabled={saving}>{saving ? 'Saving...' : 'Save'}</button>
						<button class="table-btn" onclick={cancelAddRow} disabled={saving}>Cancel</button>
					</div>
				</div>
			{/if}

			{#if filteredSubjects.length === 0}
				<div class="subject-mobile-card glass-panel empty-cell">No subjects matched your search.</div>
			{:else}
				{#each filteredSubjects as subject}
					<button class="subject-mobile-card glass-panel" onclick={() => openSubject(subject.id)}>
						<div class="name-header">
							<span class="code-chip">{subject.code}</span>
							<strong>{subject.name}</strong>
						</div>
						{#if subject.description}
							<span class="description">{subject.description}</span>
						{/if}
						<div class="mobile-metrics">
							<span>Questions <strong>{subject.total_questions}</strong></span>
							<span>Pending <strong>{subject.total_pending ?? 0}</strong></span>
							<span class="green-text">Approved <strong>{subject.total_approved ?? 0}</strong></span>
							<span class="red-text">Rejected <strong>{subject.total_rejected ?? 0}</strong></span>
						</div>
					</button>
				{/each}
			{/if}
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
		gap: 1rem;
	}

	.hero {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		gap: 0.9rem;
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

	/* .subtitle {
		margin: 0.5rem 0 0;
		max-width: 48rem;
		color: var(--theme-text-muted);
		line-height: 1.55;
	} */

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

	.add-subject-btn {
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

	.add-subject-btn:disabled {
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

	.description {
		color: var(--theme-text-muted);
		font-size: 0.8rem;
		line-height: 1.35;
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

		.add-subject-btn {
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