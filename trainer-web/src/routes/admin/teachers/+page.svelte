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
</script>

<svelte:head>
	<title>Teacher Progress — Admin</title>
</svelte:head>

<div class="page">
	<div class="hero animate-fade-in">
		<div>
			<p class="eyebrow">Admin Console</p>
			<h1 class="title font-serif">Teacher Progress</h1>
			<p class="subtitle">Track teacher-level generation and vetting progress with subject ownership and question status breakdowns.</p>
		</div>
	</div>

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
		<div class="center-state">
			<div class="spinner"></div>
			<p>Loading teacher analytics…</p>
		</div>
	{:else if teacherRows.length === 0}
		<div class="center-state glass-panel">
			<p>No teachers matched your search.</p>
		</div>
	{:else}
		<div class="teacher-grid animate-fade-in">
			{#each teacherRows as row}
				<div class="teacher-card glass-panel">
					<div class="teacher-head">
						<div>
							<p class="teacher-name">{row.teacher.full_name || row.teacher.username}</p>
							<p class="teacher-email">{row.teacher.email}</p>
						</div>
						<span class="progress-pill">{row.subjectProgress}% vetted</span>
					</div>

					<div class="metrics-grid">
						<div class="metric"><span>Assigned Subjects</span><strong>{row.subjects.length}</strong></div>
						<div class="metric"><span>Total Topics</span><strong>{row.totalTopics}</strong></div>
						<div class="metric"><span>Generated</span><strong>{row.teacher.total_generated}</strong></div>
						<div class="metric"><span>Teacher Vetted</span><strong>{row.teacher.total_vetted}</strong></div>
						<div class="metric"><span>Approved</span><strong class="green-text">{row.totalApproved}</strong></div>
						<div class="metric"><span>Rejected</span><strong class="red-text">{row.totalRejected}</strong></div>
						<div class="metric"><span>Pending</span><strong class="orange-text">{row.totalPending}</strong></div>
						<div class="metric"><span>Coverage</span><strong>{row.totalQuestions > 0 ? Math.round((row.totalVetted / row.totalQuestions) * 100) : 0}%</strong></div>
					</div>

					{#if row.subjects.length > 0}
						<div class="subject-grid">
							{#each row.subjects as subject}
								<button class="subject-chip" onclick={() => openSubject(subject.id)}>
									<span>{subject.name}</span>
									<small>{subject.total_questions}q · {subject.total_pending} pending</small>
								</button>
							{/each}
						</div>
					{:else}
						<p class="empty-msg">No subjects assigned.</p>
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

	.hero {
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
	}

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
		border: 1px solid rgba(255,255,255,0.14);
		background: rgba(255,255,255,0.06);
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

	.teacher-grid {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 1rem;
	}

	.teacher-card {
		padding: 1rem;
		border-radius: 1rem;
		display: flex;
		flex-direction: column;
		gap: 0.9rem;
	}

	.teacher-head {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 0.75rem;
	}

	.teacher-name {
		margin: 0;
		font-size: 1.05rem;
		font-weight: 700;
		color: var(--theme-text);
	}

	.teacher-email {
		margin: 0.2rem 0 0;
		font-size: 0.82rem;
		color: var(--theme-text-muted);
	}

	.progress-pill {
		padding: 0.35rem 0.6rem;
		border-radius: 999px;
		font-size: 0.75rem;
		font-weight: 700;
		background: rgba(34, 197, 94, 0.18);
		color: #4ade80;
	}

	.metrics-grid {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 0.55rem;
	}

	.metric {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
		gap: 0.5rem;
		padding: 0.55rem 0.7rem;
		border-radius: 0.75rem;
		background: rgba(255,255,255,0.06);
		font-size: 0.8rem;
		color: var(--theme-text-muted);
	}

	.metric strong {
		font-size: 0.92rem;
		color: var(--theme-text);
	}

	.subject-grid {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 0.5rem;
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

		.teacher-grid {
			grid-template-columns: 1fr;
		}
	}

	@media (max-width: 640px) {
		.page {
			padding: 1.25rem 0.95rem 1.8rem;
		}

		.metrics-grid,
		.subject-grid {
			grid-template-columns: 1fr;
		}
	}

	:global([data-theme='light']) .search-input {
		background: #ffffff;
		border-color: rgba(148, 163, 184, 0.42);
		color: #0f172a;
	}

	:global([data-theme='light']) .teacher-card,
	:global([data-theme='light']) .stat-card,
	:global([data-theme='light']) .toolbar {
		background: #ffffff;
		border: 1px solid rgba(148, 163, 184, 0.3);
		box-shadow: 0 14px 34px rgba(15, 23, 42, 0.08);
	}

	:global([data-theme='light']) .metric,
	:global([data-theme='light']) .subject-chip {
		background: #f8fafc;
		border-color: rgba(148, 163, 184, 0.35);
	}

	:global([data-theme='light']) .teacher-name,
	:global([data-theme='light']) .title,
	:global([data-theme='light']) .metric strong,
	:global([data-theme='light']) .subject-chip {
		color: #0f172a;
	}

	:global([data-theme='light']) .teacher-email,
	:global([data-theme='light']) .subtitle,
	:global([data-theme='light']) .metric,
	:global([data-theme='light']) .subject-chip small,
	:global([data-theme='light']) .stat-label {
		color: #475569;
	}
</style>
