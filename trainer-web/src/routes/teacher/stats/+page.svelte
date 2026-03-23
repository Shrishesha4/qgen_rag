<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { session } from '$lib/session';
	import { getQuestionsForVetting, getVetterDashboard, type VetterDashboard } from '$lib/api/vetting';
	import {
		getSubject,
		getSubjectsTree,
		type SubjectResponse,
		type SubjectGroupTreeNode,
		type SubjectTreeResponse
	} from '$lib/api/subjects';

	let loading = $state(true);
	let error = $state('');
	let stats = $state<VetterDashboard | null>(null);
	let treeData = $state<SubjectTreeResponse | null>(null);
	let subjects = $state<SubjectResponse[]>([]);
	let expandedGroups = $state<Set<string>>(new Set());
	let expandedSubjectId = $state('');
	let loadingTopicRowsForSubject = $state('');
	let topicRowsBySubject = $state<Record<string, TopicStatsRow[]>>({});
	let topicRowsError = $state('');

	type TopicStatsRow = {
		id: string;
		name: string;
		generated: number;
		pending: number;
		approved: number;
		rejected: number;
		vettedPct: number;
	};

	onMount(() => {
		const unsub = session.subscribe((s) => {
			if (!s || s.user.role !== 'teacher') {
				goto('/teacher/login');
			}
		});
		void loadData();
		return unsub;
	});

	async function loadData() {
		loading = true;
		error = '';
		try {
			const [dashRes, treeRes] = await Promise.all([getVetterDashboard(), getSubjectsTree()]);
			stats = dashRes;
			treeData = treeRes;
			subjects = flattenSubjects(treeRes.groups, treeRes.ungrouped_subjects);
			expandedGroups = new Set(treeRes.groups.map((group) => group.id));
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to load teacher stats';
		} finally {
			loading = false;
		}
	}

	function flattenSubjects(groups: SubjectGroupTreeNode[], ungrouped: SubjectResponse[]): SubjectResponse[] {
		const result: SubjectResponse[] = [...ungrouped];
		function traverse(group: SubjectGroupTreeNode) {
			result.push(...group.subjects);
			group.children.forEach(traverse);
		}
		groups.forEach(traverse);
		return result;
	}

	function toStatsRow(subject: SubjectResponse) {
		const approved = subject.total_approved ?? 0;
		const rejected = subject.total_rejected ?? 0;
		const pending = subject.total_pending ?? 0;
		const vetted = approved + rejected;
		const total = subject.total_questions ?? vetted + pending;
		const vettedPct = total > 0 ? Math.round((vetted / total) * 100) : 0;
		return {
			...subject,
			approved,
			rejected,
			pending,
			vetted,
			total,
			vettedPct,
		};
	}

	const rows = $derived.by(() => {
		return subjects
			.map((subject) => toStatsRow(subject))
			.sort((a, b) => b.total - a.total);
	});

	const totals = $derived.by(() => {
		if (treeData) {
			return {
				totalQuestions: treeData.totals.total_questions,
				totalPending: treeData.totals.total_pending,
				totalApproved: treeData.totals.total_approved,
				totalRejected: treeData.totals.total_rejected,
			};
		}
		return rows.reduce(
			(acc, row) => {
				acc.totalQuestions += row.total;
				acc.totalPending += row.pending;
				acc.totalApproved += row.approved;
				acc.totalRejected += row.rejected;
				return acc;
			},
			{ totalQuestions: 0, totalPending: 0, totalApproved: 0, totalRejected: 0 }
		);
	});

	const totalVetted = $derived.by(() => totals.totalApproved + totals.totalRejected);

	const overallProgress = $derived.by(() => {
		if (totals.totalQuestions <= 0) return 0;
		return Math.round((totalVetted / totals.totalQuestions) * 100);
	});

	async function countQuestionsByTopic(subjectId: string, status: 'pending' | 'approved' | 'rejected') {
		const counts: Record<string, number> = {};
		const limit = 100;
		let pageNo = 1;

		while (true) {
			const pageRes = await getQuestionsForVetting({
				subject_id: subjectId,
				status,
				page: pageNo,
				limit,
			});
			for (const question of pageRes.questions) {
				if (!question.topic_id) continue;
				counts[question.topic_id] = (counts[question.topic_id] ?? 0) + 1;
			}
			if (pageNo >= pageRes.pages || pageRes.questions.length === 0) break;
			pageNo += 1;
		}

		return counts;
	}

	async function loadTopicRows(subjectId: string) {
		loadingTopicRowsForSubject = subjectId;
		topicRowsError = '';
		try {
			const [detail, pendingCounts, approvedCounts, rejectedCounts] = await Promise.all([
				getSubject(subjectId),
				countQuestionsByTopic(subjectId, 'pending'),
				countQuestionsByTopic(subjectId, 'approved'),
				countQuestionsByTopic(subjectId, 'rejected'),
			]);

			const topicRows: TopicStatsRow[] = detail.topics.map((topic) => {
				const generated = topic.total_questions ?? 0;
				const pending = pendingCounts[topic.id] ?? 0;
				const approved = approvedCounts[topic.id] ?? 0;
				const rejected = rejectedCounts[topic.id] ?? 0;
				const vetted = approved + rejected;
				const vettedPct = generated > 0 ? Math.round((vetted / generated) * 100) : 0;
				return {
					id: topic.id,
					name: topic.name,
					generated,
					pending,
					approved,
					rejected,
					vettedPct,
				};
			});

			topicRowsBySubject = { ...topicRowsBySubject, [subjectId]: topicRows };
		} catch (e: unknown) {
			topicRowsError = e instanceof Error ? e.message : 'Failed to load topic rows';
		} finally {
			loadingTopicRowsForSubject = '';
		}
	}

	async function toggleRow(subjectId: string) {
		expandedSubjectId = expandedSubjectId === subjectId ? '' : subjectId;
		if (expandedSubjectId && !topicRowsBySubject[expandedSubjectId]) {
			await loadTopicRows(expandedSubjectId);
		}
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
</script>

<svelte:head>
	<title>Stats - Teacher Console</title>
</svelte:head>

<div class="page">
	{#if loading}
		<div class="center-state glass-panel">
			<div class="spinner"></div>
			<p>Loading stats...</p>
		</div>
	{:else}
		{#if error}
			<div class="error-banner" role="alert">{error}</div>
		{/if}

		<!-- <section class="progress-panel glass-panel">
			<div class="progress-head">
				<h2>Overall Vetting Progress</h2>
				<strong>{overallProgress}% vetted</strong>
			</div>
			<div class="progress-track" aria-label="Overall progress">
				<div class="progress-approved" style={`width: ${totals.totalQuestions > 0 ? Math.round((totals.totalApproved / totals.totalQuestions) * 100) : 0}%`}></div>
				<div class="progress-pending" style={`width: ${totals.totalQuestions > 0 ? Math.round((totals.totalPending / totals.totalQuestions) * 100) : 0}%`}></div>
			</div>
			<div class="legend">
				<span class="dot green"></span> Approved ({totals.totalApproved})
				<span class="dot red"></span> Rejected ({totals.totalRejected})
				<span class="dot amber"></span> Pending ({totals.totalPending})
			</div>
		</section> -->

		<section class="table-panel glass-panel">
			<div class="table-header">
				<div class="table-header-left">
					<button class="back-btn" onclick={() => goto('/teacher/subjects')} aria-label="Go back">
						←
					</button>
					<h1 class="title font-serif">Stats</h1>
				</div>
				<div class="header-stats" aria-label="Summary totals">
					<div class="stat-chip">
						<span class="chip-value">{totals.totalQuestions}</span>
						<span class="chip-label">Total</span>
					</div>
					<div class="stat-chip amber">
						<span class="chip-value">{totals.totalPending}</span>
						<span class="chip-label">Pending</span>
					</div>
					<div class="stat-chip green">
						<span class="chip-value">{totals.totalApproved}</span>
						<span class="chip-label">Approved</span>
					</div>
					<div class="stat-chip red">
						<span class="chip-value">{totals.totalRejected}</span>
						<span class="chip-label">Rejected</span>
					</div>
				</div>
			</div>
			<div class="table-wrap desktop-only">
				<table>
					<thead>
						<tr>
							<th></th>
							<!-- <th>Code</th> -->
							<th>Name</th>
							<th>Questions</th>
							<th>Pending</th>
							<th>Approved</th>
							<th>Rejected</th>
							<th>Vetted %</th>
						</tr>
					</thead>
					<tbody>
						{#if !treeData || (treeData.groups.length === 0 && treeData.ungrouped_subjects.length === 0)}
							<tr><td colspan="8" class="empty-row">No subjects yet.</td></tr>
						{:else}
							{#each treeData.groups as group}
								{@render statsGroupRow(group, 0)}
							{/each}
							{#each treeData.ungrouped_subjects as subject}
								{@render statsSubjectRow(subject, 0)}
							{/each}
						{/if}
					</tbody>
				</table>
			</div>

			<div class="stats-mobile-list mobile-only">
				{#if rows.length === 0}
					<div class="mobile-card empty-row">No subjects yet.</div>
				{:else}
					{#each rows as row}
						<div class="mobile-card">
							<div class="mobile-card-head">
								<div class="name-header">
									<span class="code-chip">{row.code}</span>
									<span class="name-cell">{row.name}</span>
								</div>
								<button class="table-btn" onclick={() => toggleRow(row.id)}>{expandedSubjectId === row.id ? 'Hide Topics' : 'Show Topics'}</button>
							</div>
							<div class="mobile-metrics">
								<span>Questions <strong>{row.total}</strong></span>
								<span class="amber-text">Pending <strong>{row.pending}</strong></span>
								<span class="green-text">Approved <strong>{row.approved}</strong></span>
								<span class="red-text">Rejected <strong>{row.rejected}</strong></span>
								<span>Vetted <strong>{row.vettedPct}%</strong></span>
							</div>

							{#if expandedSubjectId === row.id}
								{#if loadingTopicRowsForSubject === row.id}
									<div class="topic-substate">Loading topics...</div>
								{:else if topicRowsError}
									<div class="topic-substate error">{topicRowsError}</div>
								{:else if (topicRowsBySubject[row.id] || []).length === 0}
									<div class="topic-substate">No topics found.</div>
								{:else}
									<div class="mobile-topic-list">
										{#each topicRowsBySubject[row.id] || [] as topicRow}
											<div class="mobile-topic-card">
												<strong>{topicRow.name}</strong>
												<div class="mobile-metrics">
													<span>G <strong>{topicRow.generated}</strong></span>
													<span class="amber-text">P <strong>{topicRow.pending}</strong></span>
													<span class="green-text">A <strong>{topicRow.approved}</strong></span>
													<span class="red-text">R <strong>{topicRow.rejected}</strong></span>
													<span>Vetted <strong>{topicRow.vettedPct}%</strong></span>
												</div>
											</div>
										{/each}
									</div>
								{/if}
							{/if}
						</div>
					{/each}
				{/if}
			</div>
		</section>
	{/if}
</div>

{#snippet statsGroupRow(group: SubjectGroupTreeNode, depth: number)}
	<tr class="group-row" onclick={() => toggleGroup(group.id)} role="button" tabindex="0" onkeydown={(event) => {
		if (event.key === 'Enter' || event.key === ' ') {
			event.preventDefault();
			toggleGroup(group.id);
		}
	}}>
		<td>
			<span class="expand-indicator">{expandedGroups.has(group.id) ? '▾' : '▸'}</span>
		</td>
		<!-- <td>—</td> -->
		<td class="name-cell" style="padding-left: {depth * 1.75}rem">
			<span class="group-label">
				{#if depth > 0}
					<span class="tree-branch">↳</span>
				{/if}
				📁 {group.name}
			</span>
		</td>
		<td>{group.total_questions}</td>
		<td class="amber-text">{group.total_pending}</td>
		<td class="green-text">{group.total_approved}</td>
		<td class="red-text">{group.total_rejected}</td>
		<td>—</td>
	</tr>
	{#if expandedGroups.has(group.id)}
		{#each group.children as child}
			{@render statsGroupRow(child, depth + 1)}
		{/each}
		{#each group.subjects as subject}
			{@render statsSubjectRow(subject, depth + 1)}
		{/each}
	{/if}
{/snippet}

{#snippet statsSubjectRow(subject: SubjectResponse, depth: number)}
	{@const row = toStatsRow(subject)}
	<tr class="expandable-row" onclick={() => toggleRow(row.id)} role="button" tabindex="0" onkeydown={(event) => {
		if (event.key === 'Enter' || event.key === ' ') {
			event.preventDefault();
			void toggleRow(row.id);
		}
	}}>
		<td>
			<span class="expand-indicator">{expandedSubjectId === row.id ? '▾' : '▸'}</span>
		</td>
		<!-- <td><span class="code-chip">{row.code}</span></td> -->
		<td class="name-cell" style="padding-left: {depth * 1.75}rem">
			<span class="subject-label" class:nested={depth > 0}>
				{#if depth > 0}
					<span class="tree-branch">↳</span>
				{/if}
				{row.name} 
				<span class="code-chip">{row.code}</span>
			</span>
		</td>
		<td>{row.total}</td>
		<td class="amber-text">{row.pending}</td>
		<td class="green-text">{row.approved}</td>
		<td class="red-text">{row.rejected}</td>
		<td>
			<div class="inline-progress">
				<div class="inline-progress-fill" style={`width: ${row.vettedPct}%`}></div>
			</div>
			<span class="pct">{row.vettedPct}%</span>
		</td>
	</tr>
	{#if expandedSubjectId === row.id}
		<tr class="expanded-row">
			<td></td>
			<td colspan="7">
				<div class="topic-subtable-wrap">
					{#if loadingTopicRowsForSubject === row.id}
						<div class="topic-substate">Loading topics...</div>
					{:else if topicRowsError}
						<div class="topic-substate error">{topicRowsError}</div>
					{:else if (topicRowsBySubject[row.id] || []).length === 0}
						<div class="topic-substate">No topics found.</div>
					{:else}
						<table class="topic-subtable">
							<thead>
								<tr>
									<th>Topic</th>
									<th>Generated</th>
									<th>Pending</th>
									<th>Approved</th>
									<th>Rejected</th>
									<th>Vetted %</th>
								</tr>
							</thead>
							<tbody>
								{#each topicRowsBySubject[row.id] || [] as topicRow}
									<tr>
										<td>{topicRow.name}</td>
										<td>{topicRow.generated}</td>
										<td class="amber-text">{topicRow.pending}</td>
										<td class="green-text">{topicRow.approved}</td>
										<td class="red-text">{topicRow.rejected}</td>
										<td>{topicRow.vettedPct}%</td>
									</tr>
								{/each}
							</tbody>
						</table>
					{/if}
				</div>
			</td>
		</tr>
	{/if}
{/snippet}

<style>
	.page {
		max-width: 1120px;
		margin: 0 auto;
		padding: 1.25rem 1.5rem 2rem;
		display: flex;
		flex-direction: column;
		gap: 1rem;
		height: 100%;
		min-height: 0;
		overflow: hidden;
	}

	.back-btn {
		width: 44px;
		height: 44px;
		border-radius: 999px;
		border: 1px solid rgba(var(--theme-primary-rgb), 0.3);
		background: rgba(var(--theme-primary-rgb), 0.1);
		color: var(--theme-primary);
		font-size: 1.4rem;
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		flex-shrink: 0;
		transition: background 0.15s ease, border-color 0.15s ease;
	}

	.back-btn:hover {
		background: rgba(var(--theme-primary-rgb), 0.16);
		border-color: rgba(var(--theme-primary-rgb), 0.45);
	}

	.table-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.9rem;
	}

	.table-header-left {
		display: inline-flex;
		align-items: center;
		gap: 0.7rem;
		min-width: 0;
	}

	.header-stats {
		display: flex;
		align-items: center;
		justify-content: flex-end;
		gap: 0.5rem;
		flex-wrap: wrap;
	}

	.stat-chip {
		display: inline-flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		min-width: 84px;
		padding: 0.45rem 0.7rem;
		border-radius: 0.85rem;
		border: 1px solid rgba(var(--theme-primary-rgb), 0.24);
		background: rgba(var(--theme-primary-rgb), 0.1);
		line-height: 1;
	}

	.stat-chip.amber {
		border-color: rgba(245, 158, 11, 0.3);
		background: rgba(245, 158, 11, 0.1);
	}

	.stat-chip.green {
		border-color: rgba(16, 185, 129, 0.3);
		background: rgba(16, 185, 129, 0.1);
	}

	.stat-chip.red {
		border-color: rgba(239, 68, 68, 0.3);
		background: rgba(239, 68, 68, 0.1);
	}

	.chip-value {
		font-size: 1.9rem;
		font-weight: 800;
		color: var(--theme-text-primary);
	}

	.stat-chip.amber .chip-value {
		color: #d97706;
	}

	.stat-chip.green .chip-value {
		color: #059669;
	}

	.stat-chip.red .chip-value {
		color: #dc2626;
	}

	.chip-label {
		margin-top: 0.2rem;
		font-size: 0.66rem;
		font-weight: 700;
		letter-spacing: 0.07em;
		text-transform: uppercase;
		color: var(--theme-text-muted);
	}

	.table-panel {
		padding: 1.2rem;
		border-radius: 1rem;
		display: flex;
		flex-direction: column;
		min-height: 0;
	}
	/* .progress-panel,
	.table-panel {
		padding: 1.2rem;
		border-radius: 1rem;
		display: flex;
		flex-direction: column;
		min-height: 0;
	} */

	/* .progress-panel {
		flex: 0 0 auto;
		min-height: auto;
	} */

	.title {
		margin: 0;
		font-size: 2rem;
		color: var(--theme-text-primary);
	}

	.table-panel {
		flex: 1;
	}

	/* .progress-head {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
		gap: 0.75rem;
	} */

	/* .progress-head h2,
	.table-panel h2 {
		margin: 0;
		font-size: 1.2rem;
		color: var(--theme-text-primary);
	} */

	/* .progress-track {
		margin-top: 0.8rem;
		height: 14px;
		border-radius: 999px;
		overflow: hidden;
		background: rgba(148, 163, 184, 0.22);
		display: flex;
	}

	.progress-approved { background: #10b981; }
	.progress-pending { background: #f59e0b; }

	.legend {
		margin-top: 0.7rem;
		display: flex;
		gap: 1rem;
		font-size: 0.85rem;
		color: var(--theme-text-muted);
	}

	.dot {
		display: inline-block;
		width: 0.75rem;
		height: 0.75rem;
		border-radius: 50%;
		margin-right: 0.35rem;
	}

	.dot.green { background: #10b981; }
	.dot.red { background: #ef4444; }
	.dot.amber { background: #f59e0b; } */

	.table-wrap {
		overflow: auto;
		margin-top: 0.75rem;
		flex: 1;
		min-height: 0;
	}

	.desktop-only {
		display: block !important;
	}

	.mobile-only {
		display: none !important;
	}

	.stats-mobile-list {
		display: grid;
		gap: 0.75rem;
		margin-top: 0.75rem;
	}

	.mobile-card {
		border: 1px solid rgba(148, 163, 184, 0.24);
		border-radius: 0.85rem;
		padding: 0.75rem;
		display: flex;
		flex-direction: column;
		gap: 0.55rem;
		background: color-mix(in srgb, var(--theme-glass-bg) 92%, transparent);
	}

	.mobile-card-head {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 0.5rem;
	}

	.mobile-metrics {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 0.28rem 0.7rem;
		font-size: 0.82rem;
		color: var(--theme-text-muted);
	}

	.mobile-metrics strong {
		color: var(--theme-text-primary);
	}

	.mobile-topic-list {
		display: grid;
		gap: 0.45rem;
	}

	.mobile-topic-card {
		border: 1px solid rgba(148, 163, 184, 0.22);
		border-radius: 0.7rem;
		padding: 0.58rem;
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
	}

	.table-btn {
		padding: 0.36rem 0.64rem;
		border-radius: 999px;
		border: 1px solid rgba(var(--theme-primary-rgb), 0.35);
		background: rgba(var(--theme-primary-rgb), 0.1);
		color: var(--theme-primary);
		font: inherit;
		font-size: 0.76rem;
		font-weight: 700;
		cursor: pointer;
	}

	table {
		width: 100%;
		border-collapse: collapse;
	}

	th,
	td {
		padding: 0.8rem 0.7rem;
		border-bottom: 1px solid rgba(148, 163, 184, 0.22);
		border-right: 1px solid rgba(148, 163, 184, 0.22);
		text-align: left;
	}

	th:last-child,
	td:last-child {
		border-right: none;
	}

	th {
		font-size: 0.72rem;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: var(--theme-text-muted);
	}

	th:nth-child(n + 4),
	td:nth-child(n + 4) {
		text-align: center;
	}

	.name-cell {
		font-weight: 700;
		color: var(--theme-text-primary);
	}

	.code-chip {
		display: inline-flex;
		align-items: center;
		padding: 0.2rem 0.6rem;
		border-radius: 999px;
		background: rgba(var(--theme-primary-rgb), 0.16);
		color: var(--theme-primary);
		font-weight: 700;
	}

	.inline-progress {
		width: 80px;
		height: 8px;
		border-radius: 999px;
		overflow: hidden;
		background: rgba(148, 163, 184, 0.3);
		display: inline-block;
		vertical-align: middle;
		margin-right: 0.45rem;
	}

	.inline-progress-fill {
		height: 100%;
		background: #10b981;
	}

	.pct {
		font-size: 0.86rem;
		font-weight: 700;
		color: var(--theme-text-primary);
	}

	.expandable-row {
		cursor: pointer;
		transition: background 0.15s ease;
	}

	.group-row {
		cursor: pointer;
		background: rgba(var(--theme-primary-rgb), 0.06);
	}

	.group-row:hover {
		background: rgba(var(--theme-primary-rgb), 0.11);
	}

	.group-label {
		font-weight: 700;
		margin-left: 0.6rem;
	}

	.subject-label,
	.group-label {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		margin-left: 0.6rem;
	}

	.tree-branch {
		color: var(--theme-text-muted);
		font-weight: 600;
	}

	.expandable-row:hover {
		background: rgba(var(--theme-primary-rgb), 0.08);
	}

	.expand-indicator {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		color: var(--theme-text-muted);
		font-size: 1rem;
		user-select: none;
	}

	.expanded-row td {
		font-size: 0.84rem;
		color: var(--theme-text-muted);
	}

	.topic-subtable-wrap {
		padding: 0.5rem 0;
	}

	.topic-subtable {
		width: 100%;
		border-collapse: collapse;
		background: color-mix(in srgb, var(--theme-glass-bg) 94%, transparent);
		border: 1px solid rgba(148, 163, 184, 0.24);
		border-radius: 0.75rem;
		overflow: hidden;
	}

	.topic-subtable th,
	.topic-subtable td {
		padding: 0.6rem 0.55rem;
		font-size: 0.8rem;
		border-bottom: 1px solid rgba(148, 163, 184, 0.2);
		border-right: 1px solid rgba(148, 163, 184, 0.2);
	}

	.topic-subtable th:last-child,
	.topic-subtable td:last-child {
		border-right: none;
	}

	.topic-subtable tr:last-child td {
		border-bottom: none;
	}

	.topic-subtable th {
		text-align: left;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: var(--theme-text-muted);
	}

	.topic-subtable th:nth-child(n + 2),
	.topic-subtable td:nth-child(n + 2) {
		text-align: center;
	}

	.topic-substate {
		padding: 0.6rem 0.2rem;
		color: var(--theme-text-muted);
	}

	.topic-substate.error {
		color: #b91c1c;
	}

	.empty-row {
		text-align: center;
		color: var(--theme-text-muted);
	}

	.error-banner {
		padding: 0.9rem 1rem;
		border-radius: 1rem;
		background: rgba(239, 68, 68, 0.12);
		border: 1px solid rgba(239, 68, 68, 0.3);
		color: #b91c1c;
	}

	.green-text { color: #059669; }
	.red-text { color: #dc2626; }
	.amber-text { color: #d97706; }

	.center-state {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		min-height: 50vh;
		gap: 0.8rem;
	}

	.spinner {
		width: 30px;
		height: 30px;
		border-radius: 50%;
		border: 3px solid rgba(255,255,255,0.2);
		border-top-color: var(--theme-primary);
		animation: spin 0.8s linear infinite;
	}

	@keyframes spin {
		to { transform: rotate(360deg); }
	}

	:global([data-color-mode='light']) th,
	:global([data-color-mode='light']) td {
		border-bottom-color: rgba(148, 163, 184, 0.38);
		border-right-color: rgba(148, 163, 184, 0.38);
	}

	:global([data-color-mode='light']) .topic-subtable {
		border-color: rgba(148, 163, 184, 0.42);
	}

	:global([data-color-mode='light']) .topic-subtable th,
	:global([data-color-mode='light']) .topic-subtable td {
		border-bottom-color: rgba(148, 163, 184, 0.36);
		border-right-color: rgba(148, 163, 184, 0.36);
	}

	@media (max-width: 920px) {
		.desktop-only {
			display: none !important;
		}

		.mobile-only {
			display: grid !important;
		}

		.page {
			height: auto;
			overflow: visible;
			padding: 0.9rem 1rem 1.25rem;
		}
		.table-header {
			align-items: flex-start;
			flex-direction: column;
		}
		.table-header-left {
			width: 100%;
		}
		.header-stats {
			justify-content: flex-start;
			width: 100%;
		}
		.stat-chip {
			min-width: 78px;
			padding: 0.42rem 0.62rem;
		}
		.chip-value {
			font-size: 1.55rem;
		}
		/* .legend { flex-wrap: wrap; gap: 0.6rem 1rem; } */
		.table-panel { flex: initial; min-height: auto; }
		.table-wrap { flex: initial; min-height: auto; }
	}

	:global(.app-shell.with-desktop-chrome > .desktop-window-wrap > .desktop-window > .desktop-window-content) {
		overflow: hidden;
	}
</style>
