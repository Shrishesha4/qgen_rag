<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { session } from '$lib/session';
	import {
		getAdminDashboard,
		listAdminSubjects,
		type AdminDashboard,
		type AdminSubjectSummary,
		type UserStats
	} from '$lib/api/admin';

	let loading = $state(true);
	let error = $state('');
	let query = $state('');	
	let stats = $state<AdminDashboard | null>(null);
	let subjects = $state<AdminSubjectSummary[]>([]);
	let expandedTeachers = $state<Record<string, boolean>>({});

	onMount(() => {
		const unsub = session.subscribe((s) => {
			if (!s || s.user.role !== 'admin') {
				goto('/admin/login');
			}
		});
		loadTeachers();
		return unsub;
	});

	async function loadTeachers() {
		loading = true;
		error = '';
		try {
			const [dashboard, subjectList] = await Promise.all([getAdminDashboard(), listAdminSubjects()]);
			stats = dashboard;
			subjects = subjectList;
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to load teacher analytics';
		} finally {
			loading = false;
		}
	}

	type TeacherRow = {
		teacher: UserStats;
		subjects: AdminSubjectSummary[];
		totalTopics: number;
		totalQuestions: number;
		totalApproved: number;
		totalRejected: number;
		totalPending: number;
		totalVetted: number;
		subjectProgress: number;
	};

	const teacherRows = $derived.by<TeacherRow[]>(() => {
		if (!stats) return [];

		const grouped = new Map<string, AdminSubjectSummary[]>();
		for (const subject of subjects) {
			const key = subject.teacher_id || 'unknown';
			const current = grouped.get(key) || [];
			current.push(subject);
			grouped.set(key, current);
		}

		const teachers = stats.users.filter((user) => user.role === 'teacher');
		const rows = teachers.map((teacher) => {
			const teacherSubjects = grouped.get(teacher.user_id) || [];
			const totalTopics = teacherSubjects.reduce((sum, subject) => sum + subject.total_topics, 0);
			const totalQuestions = teacherSubjects.reduce((sum, subject) => sum + subject.total_questions, 0);
			const totalApproved = teacherSubjects.reduce((sum, subject) => sum + subject.total_approved, 0);
			const totalRejected = teacherSubjects.reduce((sum, subject) => sum + subject.total_rejected, 0);
			const totalPending = teacherSubjects.reduce((sum, subject) => sum + subject.total_pending, 0);
			const totalVetted = totalApproved + totalRejected;
			const subjectProgress = totalQuestions > 0 ? Math.round((totalVetted / totalQuestions) * 100) : 0;
			return {
				teacher,
				subjects: teacherSubjects,
				totalTopics,
				totalQuestions,
				totalApproved,
				totalRejected,
				totalPending,
				totalVetted,
				subjectProgress
			};
		});

		const needle = query.trim().toLowerCase();
		const filtered = needle
			? rows.filter((row) => {
					const subjectText = row.subjects.map((subject) => `${subject.name} ${subject.code}`).join(' ');
					return [
						row.teacher.full_name || '',
						row.teacher.username,
						row.teacher.email,
						subjectText
					].some((value) => value.toLowerCase().includes(needle));
				})
			: rows;

		return filtered.sort((a, b) => {
			if (b.totalQuestions !== a.totalQuestions) return b.totalQuestions - a.totalQuestions;
			return a.teacher.username.localeCompare(b.teacher.username);
		});
	});

	const totals = $derived.by(() => {
		return teacherRows.reduce(
			(acc, row) => {
				acc.teachers += 1;
				acc.subjects += row.subjects.length;
				acc.questions += row.totalQuestions;
				acc.vetted += row.totalVetted;
				acc.pending += row.totalPending;
				return acc;
			},
			{ teachers: 0, subjects: 0, questions: 0, vetted: 0, pending: 0 }
		);
	});

	function openSubject(subjectId: string) {
		goto(`/admin/subjects/${subjectId}`);
	}

	function userDetailHref(userId: string): string {
		return `/admin/users/${userId}`;
	}

	function toggleTeacherRow(teacherId: string) {
		expandedTeachers = {
			...expandedTeachers,
			[teacherId]: !expandedTeachers[teacherId]
		};
	}

	function isTeacherExpanded(teacherId: string): boolean {
		return Boolean(expandedTeachers[teacherId]);
	}
</script>

<svelte:head>
	<title>Teacher Progress — Admin</title>
</svelte:head>

<div class="page">
	<!-- <div class="hero animate-fade-in">
		<div>
			<p class="eyebrow">Admin Console</p>
			<h1 class="title font-serif">Teacher Progress</h1>
			<p class="subtitle">Track teacher-level generation and vetting progress with subject ownership and question status breakdowns.</p>
		</div>
	</div> -->

	<div class="toolbar glass-panel animate-slide-up">
		<input class="search-input" bind:value={query} placeholder="Search teacher, email, or subject" />
	</div>

	{#if error}
		<div class="error-banner" role="alert">{error}</div>
	{/if}

	<div class="stats-row animate-slide-up">
		<div class="stat-card glass-panel">
			<span class="stat-value amber-text">{loading ? '…' : totals.teachers}</span>
			<span class="stat-label">Teachers</span>
		</div>
		<div class="stat-card glass-panel">
			<span class="stat-value blue-text">{loading ? '…' : totals.subjects}</span>
			<span class="stat-label">Subjects</span>
		</div>
		<div class="stat-card glass-panel">
			<span class="stat-value white-text">{loading ? '…' : totals.questions}</span>
			<span class="stat-label">Questions</span>
		</div>
		<div class="stat-card glass-panel">
			<span class="stat-value green-text">{loading ? '…' : totals.vetted}</span>
			<span class="stat-label">Vetted</span>
		</div>
		<div class="stat-card glass-panel">
			<span class="stat-value orange-text">{loading ? '…' : totals.pending}</span>
			<span class="stat-label">Pending</span>
		</div>
	</div>

	{#if loading}
		<div class="center-state loading-state">
			<div class="spinner"></div>
			<p>Loading teacher analytics…</p>
		</div>
	{:else if teacherRows.length === 0}
		<div class="center-state glass-panel">
			<p>No teachers matched your search.</p>
		</div>
	{:else}
		<div class="table-wrap glass-panel animate-fade-in desktop-only">
			<table class="data-table">
				<thead>
					<tr>
						<th>Teacher</th>
						<th>Subjects</th>
						<th>Topics</th>
						<th>Questions</th>
						<th>Approved</th>
						<th>Rejected</th>
						<th>Pending</th>
						<th>Coverage</th>
						<th></th>
					</tr>
				</thead>
				<tbody>
					{#each teacherRows as row}
						<tr>
							<td>
								<div class="teacher-cell">
									<a class="teacher-name user-link" href={userDetailHref(row.teacher.user_id)}>{row.teacher.full_name || row.teacher.username}</a>
									<span class="teacher-email">{row.teacher.email}</span>
								</div>
							</td>
							<td class="num">{row.subjects.length}</td>
							<td class="num">{row.totalTopics}</td>
							<td class="num">{row.totalQuestions}</td>
							<td class="num green-text">{row.totalApproved}</td>
							<td class="num red-text">{row.totalRejected}</td>
							<td class="num orange-text">{row.totalPending}</td>
							<td class="num">{row.subjectProgress}%</td>
							<td>
								<button class="toggle-btn" onclick={() => toggleTeacherRow(row.teacher.user_id)}>
									{isTeacherExpanded(row.teacher.user_id) ? 'Hide' : 'Show'}
								</button>
							</td>
						</tr>
						{#if isTeacherExpanded(row.teacher.user_id)}
							<tr class="detail-row">
								<td colspan="9">
									{#if row.subjects.length > 0}
										<div class="detail-subjects">
											{#each row.subjects as subject}
												<button class="subject-chip" onclick={() => openSubject(subject.id)}>
													<span>{subject.name}</span>
													<small>{subject.total_questions}q · {subject.total_pending} pending</small>
												</button>
											{/each}
										</div>
									{:else}
										<p class="empty-msg">No subjects created.</p>
									{/if}
								</td>
							</tr>
						{/if}
					{/each}
				</tbody>
			</table>
		</div>

		<div class="mobile-list mobile-only animate-fade-in">
			{#each teacherRows as row}
				<div class="mobile-card glass-panel">
					<div class="teacher-cell">
						<a class="teacher-name user-link" href={userDetailHref(row.teacher.user_id)}>{row.teacher.full_name || row.teacher.username}</a>
						<span class="teacher-email">{row.teacher.email}</span>
					</div>
					<div class="mobile-metrics">
						<span>Subjects <strong>{row.subjects.length}</strong></span>
						<span>Topics <strong>{row.totalTopics}</strong></span>
						<span>Questions <strong>{row.totalQuestions}</strong></span>
						<span class="green-text">Approved <strong>{row.totalApproved}</strong></span>
						<span class="red-text">Rejected <strong>{row.totalRejected}</strong></span>
						<span class="orange-text">Pending <strong>{row.totalPending}</strong></span>
						<span>Coverage <strong>{row.subjectProgress}%</strong></span>
					</div>
					<button class="toggle-btn" onclick={() => toggleTeacherRow(row.teacher.user_id)}>
						{isTeacherExpanded(row.teacher.user_id) ? 'Hide Subjects' : 'Show Subjects'}
					</button>
					{#if isTeacherExpanded(row.teacher.user_id)}
						{#if row.subjects.length > 0}
							<div class="detail-subjects">
								{#each row.subjects as subject}
									<button class="subject-chip" onclick={() => openSubject(subject.id)}>
										<span>{subject.name}</span>
										<small>{subject.total_questions}q · {subject.total_pending} pending</small>
									</button>
								{/each}
							</div>
						{:else}
							<p class="empty-msg">No subjects created.</p>
						{/if}
					{/if}
				</div>
			{/each}
		</div>
	{/if}
</div>

<style>
	.page {
		max-width: 1160px;
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
		max-width: 52rem;
		color: var(--theme-text-muted);
		line-height: 1.6;
	} */

	.toolbar {
		display: flex;
		gap: 0.75rem;
		padding: 1rem;
		border-radius: 1rem;
	}

	.search-input {
		width: 100%;
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
		min-width: 980px;
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

	.teacher-cell {
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
	}

	.teacher-name {
		font-size: 0.95rem;
		font-weight: 700;
		color: var(--theme-text);
	}

	.user-link {
		text-decoration: none;
	}

	.user-link:hover {
		text-decoration: underline;
		text-decoration-color: color-mix(in srgb, var(--theme-primary) 65%, transparent);
	}

	.teacher-email {
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

	.toggle-btn {
		padding: 0.45rem 0.75rem;
		border-radius: 0.7rem;
		border: 1px solid color-mix(in srgb, var(--theme-primary) 45%, var(--theme-glass-border));
		background: color-mix(in srgb, var(--theme-primary) 16%, var(--theme-input-bg));
		color: var(--theme-text);
		font-weight: 700;
		cursor: pointer;
	}

	.detail-row td {
		background: color-mix(in srgb, var(--theme-input-bg) 80%, transparent);
	}

	.detail-subjects {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 0.55rem;
	}

	.subject-chip {
		display: flex;
		flex-direction: column;
		gap: 0.2rem;
		padding: 0.55rem 0.7rem;
		border-radius: 0.75rem;
		border: 1px solid rgba(255,255,255,0.18);
		background: rgba(255,255,255,0.04);
		color: var(--theme-text);
		text-align: left;
		cursor: pointer;
	}

	.subject-chip small {
		color: var(--theme-text-muted);
		font-size: 0.74rem;
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

	.empty-msg {
		margin: 0;
		font-size: 0.82rem;
		color: var(--theme-text-muted);
	}

	.center-state {
		display: grid;
		place-items: center;
		gap: 0.55rem;
		padding: 2.2rem 1rem;
		text-align: center;
		color: var(--theme-text-muted);
	}

	.center-state.loading-state {
		min-height: 6rem;
		width: 100%;
		background: transparent !important;
		border: none !important;
		box-shadow: none !important;
		backdrop-filter: none !important;
		-webkit-backdrop-filter: none !important;
	}

	.spinner {
		width: 22px;
		height: 22px;
		border-radius: 50%;
		border: 2px solid rgba(255,255,255,0.24);
		border-top-color: #fbbf24;
		animation: spin 1s linear infinite;
	}

	@keyframes spin {
		to { transform: rotate(360deg); }
	}

	@media (max-width: 900px) {
		.stats-row {
			grid-template-columns: repeat(2, minmax(0, 1fr));
		}

		.detail-subjects {
			grid-template-columns: repeat(2, minmax(0, 1fr));
		}
	}

	@media (max-width: 768px) {
		.desktop-only {
			display: none;
		}

		.mobile-only {
			display: grid;
		}

		.mobile-list {
			display: grid;
		}

		.mobile-metrics,
		.detail-subjects {
			grid-template-columns: 1fr;
		}
	}

	@media (max-width: 640px) {
		.page {
			padding: 1.25rem 0.95rem 1.8rem;
		}
	}

	:global([data-color-mode='light']) .search-input {
		background: #ffffff;
		border-color: rgba(148, 163, 184, 0.42);
		color: #0f172a;
	}

	:global([data-color-mode='light']) .table-wrap,
	:global([data-color-mode='light']) .stat-card,
	:global([data-color-mode='light']) .toolbar,
	:global([data-color-mode='light']) .mobile-card {
		background: #ffffff;
		border: 1px solid rgba(148, 163, 184, 0.3);
		box-shadow: 0 14px 34px rgba(15, 23, 42, 0.08);
	}

	:global([data-color-mode='light']) .detail-row td,
	:global([data-color-mode='light']) .toggle-btn,
	:global([data-color-mode='light']) .subject-chip {
		background: #f8fafc;
		border-color: rgba(148, 163, 184, 0.35);
	}

	:global([data-color-mode='light']) .teacher-name,
	:global([data-color-mode='light']) .mobile-metrics strong,
	:global([data-color-mode='light']) .toggle-btn,
	:global([data-color-mode='light']) .subject-chip {
		color: #0f172a;
	}

	:global([data-color-mode='light']) .teacher-email,
	:global([data-color-mode='light']) .mobile-metrics,
	:global([data-color-mode='light']) .subject-chip small,
	:global([data-color-mode='light']) .stat-label,
	:global([data-color-mode='light']) .data-table th {
		color: #475569;
	}
	
	/* :global([data-color-mode='light']) .teacher-name,
	:global([data-color-mode='light']) .title,
	:global([data-color-mode='light']) .mobile-metrics strong,
	:global([data-color-mode='light']) .toggle-btn,
	:global([data-color-mode='light']) .subject-chip {
		color: #0f172a;
	}

	:global([data-color-mode='light']) .teacher-email,
	:global([data-color-mode='light']) .subtitle,
	:global([data-color-mode='light']) .mobile-metrics,
	:global([data-color-mode='light']) .subject-chip small,
	:global([data-color-mode='light']) .stat-label,
	:global([data-color-mode='light']) .data-table th {
		color: #475569;
	} */

	:global([data-color-mode='light']) .data-table th,
	:global([data-color-mode='light']) .data-table td {
		border-bottom-color: rgba(148, 163, 184, 0.35);
	}
</style>
