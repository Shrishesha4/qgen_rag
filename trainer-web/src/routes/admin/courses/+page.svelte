<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { getStoredSession } from '$lib/api/client';
	import { listAdminCourses, type CourseSummary } from '$lib/api/courses';

	let isLoading = $state(true);
	let error = $state<string | null>(null);
	let statusFilter = $state('pending_approval');
	let courses = $state<CourseSummary[]>([]);

	async function loadCourses() {
		isLoading = true;
		error = null;
		try {
			courses = (await listAdminCourses(statusFilter || 'pending_approval')).items;
		} catch (caughtError: unknown) {
			error = caughtError instanceof Error ? caughtError.message : 'Failed to load course review queue.';
		} finally {
			isLoading = false;
		}
	}

	onMount(() => {
		const session = getStoredSession();
		if (!session || session.user.role !== 'admin') {
			goto('/admin/login');
			return;
		}
		void loadCourses();
	});
</script>

<svelte:head>
	<title>Course Review — Admin</title>
</svelte:head>

<div class="admin-courses">
	<header class="page-header">
		<div>
			<p class="eyebrow">Admin Review</p>
			<h1>Courses</h1>
			<p class="subtitle">Review teacher-submitted courses before students can buy them.</p>
		</div>
		<select bind:value={statusFilter} onchange={() => void loadCourses()}>
			<option value="pending_approval">Pending approval</option>
			<option value="published">Published</option>
			<option value="draft">Draft</option>
			<option value="archived">Archived</option>
		</select>
	</header>

	{#if error}
		<div class="error-banner">{error}</div>
	{/if}

	{#if isLoading}
		<div class="loading-state"><div class="spinner"></div></div>
	{:else if courses.length === 0}
		<div class="empty-state glass-panel">No courses found for this status.</div>
	{:else}
		<div class="course-list">
			{#each courses as course (course.id)}
				<a class="course-row glass-panel" href="/admin/courses/{course.id}">
					<div class="row-copy">
						<h2>{course.title}</h2>
						{#if course.description}
							<p>{course.description}</p>
						{/if}
						<div class="row-meta">Teacher: {course.teacher_id}</div>
					</div>
					<div class="row-side">
						<span class="status-chip status-{course.status}">{course.status}</span>
						<span>{course.module_count} modules</span>
						<span>{course.enrolled_count} enrolled</span>
					</div>
				</a>
			{/each}
		</div>
	{/if}
</div>

<style>
	.admin-courses {
		max-width: 1080px;
		margin: 0 auto;
		padding: 1.25rem 1.5rem 2rem;
	}

	.page-header {
		display: flex;
		align-items: end;
		justify-content: space-between;
		gap: 1rem;
		margin-bottom: 1.25rem;
	}

	.eyebrow {
		margin: 0 0 0.35rem;
		font-size: 0.76rem;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: var(--theme-text-secondary);
	}

	h1 {
		margin: 0;
		font-size: 1.7rem;
	}

	.subtitle {
		margin: 0.35rem 0 0;
		color: var(--theme-text-secondary);
	}

	select {
		padding: 0.55rem 0.8rem;
		border-radius: 10px;
		border: 1px solid var(--theme-glass-border);
		background: var(--theme-input-bg);
		color: var(--theme-text-primary);
	}

	.course-list {
		display: grid;
		gap: 0.85rem;
	}

	.course-row {
		display: flex;
		justify-content: space-between;
		gap: 1rem;
		padding: 1rem 1.1rem;
		border-radius: 16px;
		text-decoration: none;
		color: inherit;
	}

	.glass-panel {
		background: color-mix(in srgb, var(--theme-nav-glass) 88%, transparent);
		border: 1px solid var(--theme-glass-border);
		backdrop-filter: blur(18px);
	}

	.row-copy h2 {
		margin: 0 0 0.25rem;
		font-size: 1rem;
	}

	.row-copy p {
		margin: 0;
		color: var(--theme-text-secondary);
	}

	.row-meta {
		margin-top: 0.55rem;
		font-size: 0.78rem;
		color: var(--theme-text-secondary);
	}

	.row-side {
		display: grid;
		justify-items: end;
		gap: 0.35rem;
		font-size: 0.82rem;
		color: var(--theme-text-secondary);
	}

	.status-chip {
		display: inline-flex;
		padding: 0.2rem 0.55rem;
		border-radius: 999px;
		text-transform: uppercase;
		font-size: 0.72rem;
		font-weight: 700;
		letter-spacing: 0.05em;
		border: 1px solid var(--theme-glass-border);
	}

	.status-pending_approval {
		color: rgb(245, 158, 11);
		border-color: rgba(245, 158, 11, 0.3);
	}

	.status-published {
		color: rgb(34, 197, 94);
		border-color: rgba(34, 197, 94, 0.28);
	}

	.status-draft {
		color: rgba(var(--theme-primary-rgb), 0.75);
		border-color: rgba(var(--theme-primary-rgb), 0.24);
	}

	.error-banner,
	.empty-state {
		padding: 0.9rem 1rem;
		border-radius: 14px;
	}

	.error-banner {
		margin-bottom: 1rem;
		background: rgba(239, 68, 68, 0.08);
		border: 1px solid rgba(239, 68, 68, 0.18);
		color: #ef4444;
	}

	@media (max-width: 720px) {
		.page-header,
		.course-row {
			flex-direction: column;
			align-items: stretch;
		}

		.row-side {
			justify-items: start;
		}
	}
</style>