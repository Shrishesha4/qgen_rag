<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { session, currentUser } from '$lib/session';
	import { logout } from '$lib/api/auth';
	import { getAdminDashboard, listAdminSubjects, type AdminDashboard, type UserStats, type VetterBreakdown, type AdminSubjectSummary } from '$lib/api/admin';

	let loading = $state(true);
	let stats = $state<AdminDashboard | null>(null);
	let adminSubjects = $state<AdminSubjectSummary[]>([]);
	let error = $state('');
	let activeTab: 'overview' | 'users' | 'vetters' | 'teachers' = $state('overview');

	onMount(() => {
		const unsub = session.subscribe((s) => {
			if (!s || s.user.role !== 'admin') {
				goto('/admin/login');
			}
		});
		loadStats();
		return unsub;
	});

	async function loadStats() {
		loading = true;
		error = '';
		try {
			const [dashboard, subjects] = await Promise.all([getAdminDashboard(), listAdminSubjects()]);
			stats = dashboard;
			adminSubjects = subjects;
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to load dashboard';
		} finally {
			loading = false;
		}
	}

	async function handleLogout() {
		await logout();
		session.clear();
		goto('/');
	}

	function vetRate(u: UserStats): string {
		const total = u.total_generated;
		if (!total) return '—';
		const vetted = u.total_approved + u.total_rejected;
		return Math.round((vetted / total) * 100) + '%';
	}

	let teacherViewRows = $derived.by(() => {
		if (!stats) return [];
		const teacherUsers = stats.users.filter((u) => u.role === 'teacher');
		const grouped = new Map<string, AdminSubjectSummary[]>();
		for (const subject of adminSubjects) {
			const key = subject.teacher_id || 'unknown';
			const current = grouped.get(key) || [];
			current.push(subject);
			grouped.set(key, current);
		}

		return teacherUsers.map((teacher) => {
			const subjects = grouped.get(teacher.user_id) || [];
			const totalTopics = subjects.reduce((sum, s) => sum + s.total_topics, 0);
			const totalQuestions = subjects.reduce((sum, s) => sum + s.total_questions, 0);
			const approved = subjects.reduce((sum, s) => sum + s.total_approved, 0);
			const rejected = subjects.reduce((sum, s) => sum + s.total_rejected, 0);
			const pending = subjects.reduce((sum, s) => sum + s.total_pending, 0);
			const vetted = approved + rejected;
			const progress = totalQuestions > 0 ? Math.round((vetted / totalQuestions) * 100) : 0;
			return { teacher, subjects, totalTopics, totalQuestions, approved, rejected, pending, progress };
		});
	});
</script>

<svelte:head>
	<title>Admin Dashboard — VQuest Trainer</title>
</svelte:head>

<div class="admin-dash">
	{#if error}
		<div class="error-banner" role="alert">{error}</div>
	{/if}

	<!-- Top-level stat cards -->
	<div class="stats-grid animate-slide-up">
		<div class="stat-card glass-panel">
			<span class="stat-value amber-text">{loading ? '…' : (stats?.total_subjects ?? 0)}</span>
			<span class="stat-label">Subjects</span>
		</div>
		<div class="stat-card glass-panel">
			<span class="stat-value blue-text">{loading ? '…' : (stats?.total_topics ?? 0)}</span>
			<span class="stat-label">Topics</span>
		</div>
		<div class="stat-card glass-panel">
			<span class="stat-value white-text">{loading ? '…' : (stats?.total_questions ?? 0)}</span>
			<span class="stat-label">Questions</span>
		</div>
		<div class="stat-card glass-panel">
			<span class="stat-value green-text">{loading ? '…' : (stats?.total_vetted ?? 0)}</span>
			<span class="stat-label">Vetted</span>
		</div>
		<div class="stat-card glass-panel">
			<span class="stat-value emerald-text">{loading ? '…' : (stats?.total_approved ?? 0)}</span>
			<span class="stat-label">Approved</span>
		</div>
		<div class="stat-card glass-panel">
			<span class="stat-value red-text">{loading ? '…' : (stats?.total_rejected ?? 0)}</span>
			<span class="stat-label">Rejected</span>
		</div>
		<div class="stat-card glass-panel">
			<span class="stat-value orange-text">{loading ? '…' : (stats?.total_pending ?? 0)}</span>
			<span class="stat-label">Pending</span>
		</div>
		<div class="stat-card glass-panel">
			<span class="stat-value purple-text">{loading ? '…' : (stats?.total_users ?? 0)}</span>
			<span class="stat-label">Users</span>
		</div>
	</div>

	<!-- User role breakdown -->
	{#if !loading && stats}
		<div class="role-bar animate-slide-up">
			<span class="role-chip teacher-chip">{stats.total_teachers} Teachers</span>
			<span class="role-chip vetter-chip">{stats.total_vetters} Vetters</span>
			<span class="role-chip admin-chip">{stats.total_admins} Admins</span>
		</div>
	{/if}

	<div class="quick-links animate-slide-up">
		<a href="/admin/subjects" class="quick-link glass-panel">
			<div>
				<h2 class="quick-link-title">Browse Subjects</h2>
				<p class="quick-link-desc">Open a full subject inventory with teacher ownership, question counts, and topic-level vetting breakdowns.</p>
			</div>
			<span class="quick-link-arrow">→</span>
		</a>
	</div>

	<!-- Tabs -->
	<div class="tabs animate-slide-up">
		<button class="tab-btn" class:active={activeTab === 'overview'} onclick={() => activeTab = 'overview'}>Overview</button>
		<button class="tab-btn" class:active={activeTab === 'users'} onclick={() => activeTab = 'users'}>All Users</button>
		<button class="tab-btn" class:active={activeTab === 'vetters'} onclick={() => activeTab = 'vetters'}>Vetters</button>
		<button class="tab-btn" class:active={activeTab === 'teachers'} onclick={() => activeTab = 'teachers'}>Teachers</button>
	</div>

	<!-- Tab content -->
	{#if !loading && stats}
		<div class="tab-content animate-fade-in">
			{#if activeTab === 'overview'}
				<div class="section glass-panel">
					<h2 class="section-title">Platform Summary</h2>
					<div class="summary-grid">
						<div class="summary-item">
							<span class="summary-label">Vetting Rate</span>
							<span class="summary-value">{stats.total_questions > 0 ? Math.round((stats.total_vetted / stats.total_questions) * 100) : 0}%</span>
						</div>
						<div class="summary-item">
							<span class="summary-label">Approval Rate</span>
							<span class="summary-value">{stats.total_vetted > 0 ? Math.round((stats.total_approved / stats.total_vetted) * 100) : 0}%</span>
						</div>
						<div class="summary-item">
							<span class="summary-label">Rejection Rate</span>
							<span class="summary-value">{stats.total_vetted > 0 ? Math.round((stats.total_rejected / stats.total_vetted) * 100) : 0}%</span>
						</div>
						<div class="summary-item">
							<span class="summary-label">Avg Questions/Subject</span>
							<span class="summary-value">{stats.total_subjects > 0 ? Math.round(stats.total_questions / stats.total_subjects) : 0}</span>
						</div>
					</div>
				</div>

				<!-- Top generators -->
				{#if stats.users.length > 0}
					<div class="section glass-panel">
						<h2 class="section-title">Top Generators</h2>
						<div class="leaderboard">
							{#each stats.users.filter(u => u.total_generated > 0).slice(0, 5) as u, i}
								<div class="lb-row">
									<span class="lb-rank">#{i + 1}</span>
									<div class="lb-info">
										<span class="lb-name">{u.full_name || u.username}</span>
										<span class="lb-meta">{u.role} · {u.email}</span>
									</div>
									<span class="lb-count">{u.total_generated}</span>
								</div>
							{/each}
						</div>
					</div>
				{/if}

				<!-- Top vetters -->
				{#if stats.vetters.length > 0}
					<div class="section glass-panel">
						<h2 class="section-title">Top Vetters</h2>
						<div class="leaderboard">
							{#each stats.vetters.slice(0, 5) as v, i}
								<div class="lb-row">
									<span class="lb-rank">#{i + 1}</span>
									<div class="lb-info">
										<span class="lb-name">{v.full_name || v.username}</span>
										<span class="lb-meta">{v.email}</span>
									</div>
									<div class="lb-badges">
										<span class="badge green">{v.total_approved} approved</span>
										<span class="badge red">{v.total_rejected} rejected</span>
									</div>
								</div>
							{/each}
						</div>
					</div>
				{/if}

			{:else if activeTab === 'users'}
				<div class="section glass-panel">
					<h2 class="section-title">All Users ({stats.users.length})</h2>
					<div class="table-wrapper">
						<table class="data-table">
							<thead>
								<tr>
									<th>User</th>
									<th>Role</th>
									<th>Generated</th>
									<th>Approved</th>
									<th>Rejected</th>
									<th>Pending</th>
									<th>Vet Rate</th>
									<th>Subjects</th>
									<th>Topics</th>
								</tr>
							</thead>
							<tbody>
								{#each stats.users as u}
									<tr>
										<td>
											<div class="user-cell">
												<span class="user-name">{u.full_name || u.username}</span>
												<span class="user-email">{u.email}</span>
											</div>
										</td>
										<td><span class="role-tag {u.role}">{u.role}</span></td>
										<td class="num">{u.total_generated}</td>
										<td class="num green-text">{u.total_approved}</td>
										<td class="num red-text">{u.total_rejected}</td>
										<td class="num orange-text">{u.total_pending}</td>
										<td class="num">{vetRate(u)}</td>
										<td class="num">{u.subjects_count}</td>
										<td class="num">{u.topics_count}</td>
									</tr>
								{/each}
							</tbody>
						</table>
					</div>
				</div>

			{:else if activeTab === 'vetters'}
				<div class="section glass-panel">
					<h2 class="section-title">Vetter Breakdown ({stats.vetters.length})</h2>
					{#if stats.vetters.length === 0}
						<p class="empty-msg">No vetting activity yet.</p>
					{:else}
						<div class="table-wrapper">
							<table class="data-table">
								<thead>
									<tr>
										<th>Vetter</th>
										<th>Total Vetted</th>
										<th>Approved</th>
										<th>Rejected</th>
										<th>Approval %</th>
									</tr>
								</thead>
								<tbody>
									{#each stats.vetters as v}
										<tr>
											<td>
												<div class="user-cell">
													<span class="user-name">{v.full_name || v.username}</span>
													<span class="user-email">{v.email}</span>
												</div>
											</td>
											<td class="num">{v.total_vetted}</td>
											<td class="num green-text">{v.total_approved}</td>
											<td class="num red-text">{v.total_rejected}</td>
											<td class="num">{v.total_vetted > 0 ? Math.round((v.total_approved / v.total_vetted) * 100) : 0}%</td>
										</tr>
									{/each}
								</tbody>
							</table>
						</div>
					{/if}
				</div>
			{:else if activeTab === 'teachers'}
				<div class="section glass-panel">
					<h2 class="section-title">Teacher Subject Progress ({teacherViewRows.length})</h2>
					{#if teacherViewRows.length === 0}
						<p class="empty-msg">No teachers found.</p>
					{:else}
						<div class="teacher-grid">
							{#each teacherViewRows as row}
								<div class="teacher-card">
									<div class="teacher-head">
										<div>
											<p class="teacher-name">{row.teacher.full_name || row.teacher.username}</p>
											<p class="teacher-email">{row.teacher.email}</p>
										</div>
										<span class="teacher-progress">{row.progress}% progress</span>
									</div>
									<div class="teacher-metrics">
										<span>Subjects: <strong>{row.subjects.length}</strong></span>
										<span>Topics: <strong>{row.totalTopics}</strong></span>
										<span>Questions: <strong>{row.totalQuestions}</strong></span>
										<span class="green-text">Approved: <strong>{row.approved}</strong></span>
										<span class="red-text">Rejected: <strong>{row.rejected}</strong></span>
										<span class="orange-text">Pending: <strong>{row.pending}</strong></span>
									</div>
									{#if row.subjects.length > 0}
										<div class="teacher-subjects">
											{#each row.subjects as subject}
												<span class="teacher-subject-chip">{subject.name} ({subject.total_topics})</span>
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
			{/if}
		</div>
	{/if}

	{#if loading}
		<div class="loading-msg">
			<span class="spinner"></span>
			Loading dashboard…
		</div>
	{/if}

	<button class="logout-link" onclick={handleLogout}>Sign Out</button>
</div>

<style>
	.admin-dash {
		display: flex;
		flex-direction: column;
		align-items: center;
		padding: 5rem 0 2rem;
		gap: 1.5rem;
		min-height: 100vh;
		width: 100%;
		max-width: 960px;
		margin: 0 auto;
	}

	.hero {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.5rem;
		text-align: center;
	}

	.hero-icon {
		width: 56px;
		height: 56px;
		border-radius: 50%;
		display: flex;
		align-items: center;
		justify-content: center;
		margin-bottom: 0.25rem;
	}
	.hero-icon.amber {
		background: rgba(245, 158, 11, 0.2);
		color: #f59e0b;
	}

	.title {
		font-size: 2rem;
		font-weight: 800;
		margin: 0;
		color: var(--theme-text);
	}

	.welcome {
		font-size: 0.95rem;
		color: var(--theme-text-muted);
		margin: 0;
	}

	.error-banner {
		background: rgba(220, 38, 38, 0.15);
		border: 0.5px solid rgba(220, 38, 38, 0.3);
		color: #f87171;
		border-radius: 0.75rem;
		padding: 0.65rem 0.85rem;
		font-size: 0.85rem;
		width: 100%;
		max-width: 600px;
		text-align: center;
	}

	/* Stats grid */
	.stats-grid {
		display: grid;
		grid-template-columns: repeat(4, 1fr);
		gap: 0.65rem;
		width: 100%;
	}

	.stat-card {
		display: flex;
		flex-direction: column;
		align-items: center;
		padding: 1rem 0.5rem;
		gap: 0.2rem;
		border-radius: 1rem;
		/* Force blur effect - override mobile styles */
		backdrop-filter: blur(10px) saturate(150%) brightness(1.02) !important;
		-webkit-backdrop-filter: blur(10px) saturate(150%) brightness(1.02) !important;
		background: linear-gradient(
			145deg,
			rgba(255,255,255,0.1) 0%,
			rgba(255,255,255,0.05) 50%,
			rgba(255,255,255,0.08) 100%
		) !important;
		box-shadow:
			0 8px 40px rgba(0, 0, 0, 0.25),
			inset 0 1px 1px rgba(255, 255, 255, 0.25),
			inset 0 -1px 1px rgba(255, 255, 255, 0.08),
			0 0 0 1px rgba(255, 255, 255, 0.12) !important;
	}

	.stat-value {
		font-size: 1.6rem;
		font-weight: 800;
	}

	.stat-label {
		font-size: 0.68rem;
		font-weight: 600;
		color: var(--theme-text-muted);
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}

	.amber-text { color: #f59e0b; }
	.blue-text { color: #60a5fa; }
	.white-text { color: var(--theme-text); }
	.green-text { color: #34d399; }
	.emerald-text { color: #10b981; }
	.red-text { color: #f87171; }
	.orange-text { color: #fb923c; }
	.purple-text { color: #a78bfa; }

	/* Role breakdown bar */
	.role-bar {
		display: flex;
		gap: 0.5rem;
		flex-wrap: wrap;
		justify-content: center;
	}

	.role-chip {
		padding: 0.3rem 0.75rem;
		border-radius: 999px;
		font-size: 0.78rem;
		font-weight: 600;
	}

	.quick-links {
		width: 100%;
	}

	.quick-link {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 1rem;
		padding: 1.1rem 1.2rem;
		border-radius: 1rem;
		text-decoration: none;
		color: inherit;
	}

	.quick-link-title {
		margin: 0;
		font-size: 1rem;
		font-weight: 700;
		color: var(--theme-text);
	}

	.quick-link-desc {
		margin: 0.25rem 0 0;
		font-size: 0.85rem;
		line-height: 1.55;
		color: var(--theme-text-muted);
	}

	.quick-link-arrow {
		font-size: 1.35rem;
		font-weight: 800;
		color: #fbbf24;
	}

	.teacher-chip {
		background: rgba(59, 130, 246, 0.15);
		color: #93c5fd;
		border: 1px solid rgba(59, 130, 246, 0.25);
	}

	.vetter-chip {
		background: rgba(16, 185, 129, 0.15);
		color: #6ee7b7;
		border: 1px solid rgba(16, 185, 129, 0.25);
	}

	.admin-chip {
		background: rgba(245, 158, 11, 0.15);
		color: #fbbf24;
		border: 1px solid rgba(245, 158, 11, 0.25);
	}

	/* Tabs */
	.tabs {
		display: flex;
		gap: 0.25rem;
		background: var(--theme-nav-glass);
		border-radius: 0.75rem;
		padding: 0.25rem;
		border: 1px solid var(--theme-glass-border);
		/* Force blur effect - override mobile styles */
		backdrop-filter: blur(10px) saturate(150%) brightness(1.02) !important;
		-webkit-backdrop-filter: blur(10px) saturate(150%) brightness(1.02) !important;
		box-shadow:
			0 8px 40px rgba(0, 0, 0, 0.25),
			inset 0 1px 1px rgba(255, 255, 255, 0.25),
			inset 0 -1px 1px rgba(255, 255, 255, 0.08),
			0 0 0 1px rgba(255, 255, 255, 0.12) !important;
	}

	.tab-btn {
		padding: 0.5rem 1.25rem;
		border: 1px solid transparent;
		border-radius: 0.6rem;
		background: transparent;
		color: var(--theme-text-muted);
		font-size: 0.85rem;
		font-weight: 600;
		cursor: pointer;
		transition: all 0.2s;
		font-family: inherit;
	}

	.tab-btn:hover {
		color: var(--theme-text);
	}

	.tab-btn.active {
		background: color-mix(in srgb, var(--theme-input-bg) 72%, rgba(var(--theme-primary-rgb), 0.26));
		border-color: color-mix(in srgb, var(--theme-glass-border) 68%, rgba(var(--theme-primary-rgb), 0.48));
		color: var(--theme-primary);
		box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.32);
	}

	/* Tab content / Sections */
	.tab-content {
		width: 100%;
	}

	.teacher-grid {
		display: grid;
		grid-template-columns: 1fr;
		gap: 0.85rem;
	}

	.teacher-card {
		padding: 0.95rem;
		border-radius: 0.95rem;
		border: 1px solid var(--theme-glass-border);
		background: color-mix(in srgb, var(--theme-surface) 88%, transparent);
	}

	.teacher-head {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		gap: 0.75rem;
	}

	.teacher-name {
		margin: 0;
		font-weight: 700;
		font-size: 1rem;
		color: var(--theme-text-primary);
	}

	.teacher-email {
		margin: 0.2rem 0 0;
		font-size: 0.82rem;
		color: var(--theme-text-secondary);
	}

	.teacher-progress {
		padding: 0.25rem 0.6rem;
		border-radius: 999px;
		background: color-mix(in srgb, var(--theme-input-bg) 68%, rgba(var(--theme-primary-rgb), 0.2));
		color: var(--theme-primary);
		font-size: 0.78rem;
		font-weight: 700;
		white-space: nowrap;
	}

	.teacher-metrics {
		margin-top: 0.65rem;
		display: flex;
		flex-wrap: wrap;
		gap: 0.45rem 0.9rem;
		font-size: 0.82rem;
		color: var(--theme-text-secondary);
	}

	.teacher-subjects {
		margin-top: 0.7rem;
		display: flex;
		flex-wrap: wrap;
		gap: 0.45rem;
	}

	.teacher-subject-chip {
		padding: 0.25rem 0.55rem;
		border-radius: 999px;
		background: color-mix(in srgb, var(--theme-input-bg) 64%, rgba(var(--theme-primary-rgb), 0.16));
		color: var(--theme-text-primary);
		font-size: 0.76rem;
		font-weight: 700;
	}

	:global([data-color-mode='dark']) .tab-btn.active {
		box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.12), 0 6px 14px rgba(0, 0, 0, 0.28);
	}

	:global([data-color-mode='dark']) .teacher-card {
		box-shadow: 0 10px 24px rgba(0, 0, 0, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.08);
	}

	.section {
		padding: 1.5rem;
		border-radius: 1rem;
		margin-bottom: 1rem;
		/* Force blur effect - override mobile styles */
		backdrop-filter: blur(10px) saturate(150%) brightness(1.02) !important;
		-webkit-backdrop-filter: blur(10px) saturate(150%) brightness(1.02) !important;
		background: linear-gradient(
			145deg,
			rgba(255,255,255,0.1) 0%,
			rgba(255,255,255,0.05) 50%,
			rgba(255,255,255,0.08) 100%
		) !important;
		box-shadow:
			0 8px 40px rgba(0, 0, 0, 0.25),
			inset 0 1px 1px rgba(255, 255, 255, 0.25),
			inset 0 -1px 1px rgba(255, 255, 255, 0.08),
			0 0 0 1px rgba(255, 255, 255, 0.12) !important;
	}

	.section-title {
		font-size: 1.1rem;
		font-weight: 700;
		margin: 0 0 1rem;
		color: var(--theme-text);
	}

	/* Summary grid */
	.summary-grid {
		display: grid;
		grid-template-columns: repeat(2, 1fr);
		gap: 1rem;
	}

	.summary-item {
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
	}

	.summary-label {
		font-size: 0.75rem;
		font-weight: 600;
		color: var(--theme-text-muted);
		text-transform: uppercase;
		letter-spacing: 0.04em;
	}

	.summary-value {
		font-size: 1.5rem;
		font-weight: 800;
		color: var(--theme-text);
	}

	/* Leaderboard */
	.leaderboard {
		display: flex;
		flex-direction: column;
		gap: 0.65rem;
	}

	.lb-row {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		padding: 0.65rem 0;
		border-bottom: 1px solid rgba(255, 255, 255, 0.06);
	}

	.lb-row:last-child {
		border-bottom: none;
	}

	.lb-rank {
		font-size: 0.85rem;
		font-weight: 700;
		color: var(--theme-text-muted);
		min-width: 2rem;
	}

	.lb-info {
		flex: 1;
		display: flex;
		flex-direction: column;
		gap: 0.1rem;
	}

	.lb-name {
		font-size: 0.9rem;
		font-weight: 600;
		color: var(--theme-text);
	}

	.lb-meta {
		font-size: 0.75rem;
		color: var(--theme-text-muted);
	}

	.lb-count {
		font-size: 1.3rem;
		font-weight: 800;
		color: var(--theme-primary);
	}

	.lb-badges {
		display: flex;
		gap: 0.35rem;
	}

	.badge {
		padding: 0.2rem 0.5rem;
		border-radius: 999px;
		font-size: 0.7rem;
		font-weight: 600;
	}

	.badge.green {
		background: rgba(16, 185, 129, 0.15);
		color: #6ee7b7;
	}

	.badge.red {
		background: rgba(239, 68, 68, 0.15);
		color: #fca5a5;
	}

	/* Data table */
	.table-wrapper {
		overflow-x: auto;
		-webkit-overflow-scrolling: touch;
		margin: 0 -0.5rem;
		padding: 0 0.5rem;
	}

	.data-table {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.82rem;
		min-width: 700px;
	}

	.data-table th {
		text-align: left;
		padding: 0.6rem 0.5rem;
		font-weight: 700;
		font-size: 0.7rem;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: var(--theme-text-muted);
		border-bottom: 1px solid rgba(255, 255, 255, 0.1);
		white-space: nowrap;
	}

	.data-table td {
		padding: 0.6rem 0.5rem;
		border-bottom: 1px solid rgba(255, 255, 255, 0.04);
		vertical-align: middle;
	}

	.data-table tbody tr:hover {
		background: rgba(255, 255, 255, 0.03);
	}

	.num {
		text-align: right;
		font-variant-numeric: tabular-nums;
		font-weight: 600;
	}

	.user-cell {
		display: flex;
		flex-direction: column;
		gap: 0.1rem;
	}

	.user-name {
		font-weight: 600;
		color: var(--theme-text);
		font-size: 0.85rem;
	}

	.user-email {
		font-size: 0.72rem;
		color: var(--theme-text-muted);
	}

	.role-tag {
		display: inline-block;
		padding: 0.15rem 0.5rem;
		border-radius: 999px;
		font-size: 0.7rem;
		font-weight: 600;
		text-transform: capitalize;
	}

	.role-tag.teacher {
		background: rgba(59, 130, 246, 0.15);
		color: #93c5fd;
	}

	.role-tag.vetter {
		background: rgba(16, 185, 129, 0.15);
		color: #6ee7b7;
	}

	.role-tag.admin {
		background: rgba(245, 158, 11, 0.15);
		color: #fbbf24;
	}

	.empty-msg {
		text-align: center;
		color: var(--theme-text-muted);
		font-size: 0.9rem;
		padding: 2rem 0;
	}

	/* Loading */
	.loading-msg {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		color: var(--theme-text-muted);
		font-size: 0.9rem;
	}

	.spinner {
		width: 1.2rem;
		height: 1.2rem;
		border: 2px solid rgba(255, 255, 255, 0.15);
		border-top-color: #f59e0b;
		border-radius: 50%;
		animation: spin 0.6s linear infinite;
	}

	@keyframes spin {
		to { transform: rotate(360deg); }
	}

	/* Logout */
	.logout-link {
		background: none;
		border: none;
		color: var(--theme-text-muted);
		cursor: pointer;
		font-size: 0.85rem;
		padding: 0.5rem;
		transition: color 0.15s;
		font-family: inherit;
		margin-top: 0.5rem;
	}

	.logout-link:hover {
		color: #e94560;
	}

	/* Responsive */
	@media (max-width: 768px) {
		.admin-dash {
			padding: 4rem 1rem 1.5rem;
			gap: 1.25rem;
		}

		.hero-icon {
			width: 48px;
			height: 48px;
		}

		.title {
			font-size: 1.75rem;
		}

		.stats-grid {
			grid-template-columns: repeat(4, 1fr);
			gap: 0.5rem;
		}

		.stat-card {
			padding: 0.75rem 0.3rem;
		}

		.stat-value {
			font-size: 1.25rem;
		}

		.stat-label {
			font-size: 0.6rem;
		}

		.summary-grid {
			grid-template-columns: 1fr 1fr;
		}

		.section {
			padding: 1.25rem;
		}

		.tab-btn {
			padding: 0.45rem 0.85rem;
			font-size: 0.8rem;
		}
	}

	@media (max-width: 480px) {
		.admin-dash {
			padding: 1rem 0.75rem 1.25rem;
			gap: 1rem;
		}

		.title {
			font-size: 1.5rem;
		}

		.stats-grid {
			grid-template-columns: repeat(2, 1fr);
			gap: 0.4rem;
		}

		.stat-card {
			padding: 0.65rem 0.25rem;
			border-radius: 0.75rem;
		}

		.stat-value {
			font-size: 1.15rem;
		}

		.section {
			padding: 1rem;
			border-radius: 0.85rem;
		}

		.section-title {
			font-size: 1rem;
		}

		.summary-grid {
			grid-template-columns: 1fr;
			gap: 0.75rem;
		}

		.tab-btn {
			padding: 0.4rem 0.65rem;
			font-size: 0.75rem;
		}

		.lb-row {
			flex-wrap: wrap;
		}

		.lb-badges {
			width: 100%;
			margin-top: 0.25rem;
			padding-left: 2.75rem;
		}
	}
</style>
