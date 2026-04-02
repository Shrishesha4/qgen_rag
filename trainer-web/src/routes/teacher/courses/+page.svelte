<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { Plus, BookOpen, Archive, Globe, Pencil } from 'lucide-svelte';
	import { listMyCourses, type CourseSummary } from '$lib/api/courses';
	import { createCourse } from '$lib/api/courses';

	let courses = $state<CourseSummary[]>([]);
	let isLoading = $state(true);
	let error = $state<string | null>(null);
	let statusFilter = $state<string>('');
	let isCreating = $state(false);

	async function fetchCourses() {
		isLoading = true;
		error = null;
		try {
			const res = await listMyCourses(statusFilter || undefined);
			courses = res.items;
		} catch (e: unknown) {
			error = (e as Error).message ?? 'Failed to load courses.';
		} finally {
			isLoading = false;
		}
	}

	async function handleCreate() {
		isCreating = true;
		try {
			const course = await createCourse({ title: 'Untitled Course', description: '' });
			goto(`/teacher/courses/${course.id}/edit`);
		} catch (e: unknown) {
			error = (e as Error).message ?? 'Failed to create course.';
		} finally {
			isCreating = false;
		}
	}

	onMount(() => {
		fetchCourses();
	});

	function statusIcon(status: string) {
		if (status === 'published') return Globe;
		if (status === 'archived') return Archive;
		return Pencil;
	}
</script>

<div class="teacher-courses">
	<header class="page-header">
		<div>
			<h1 class="title">My Courses</h1>
			<p class="subtitle">Create and manage your courses.</p>
		</div>
		<button class="create-btn" onclick={handleCreate} disabled={isCreating}>
			<Plus class="h-4 w-4" />
			{isCreating ? 'Creating…' : 'New Course'}
		</button>
	</header>

	<div class="filter-bar">
		<select bind:value={statusFilter} onchange={() => fetchCourses()}>
			<option value="">All statuses</option>
			<option value="draft">Draft</option>
			<option value="published">Published</option>
			<option value="archived">Archived</option>
		</select>
	</div>

	{#if error}
		<div class="error-banner">{error}</div>
	{/if}

	{#if isLoading}
		<div class="loading-state"><div class="spinner"></div></div>
	{:else if courses.length === 0}
		<div class="empty-state">
			<BookOpen class="h-10 w-10" style="opacity: 0.4" />
			<p>No courses yet. Create your first course!</p>
		</div>
	{:else}
		<div class="course-list">
			{#each courses as course (course.id)}
				<a href="/teacher/courses/{course.id}/edit" class="course-row glass-panel">
					<div class="row-info">
						<h3 class="row-title">{course.title}</h3>
						{#if course.description}
							<p class="row-desc">{course.description}</p>
						{/if}
					</div>
					<div class="row-meta">
						<span class="row-status" class:published={course.status === 'published'} class:draft={course.status === 'draft'}>
							{#if course.status === 'published'}
								<Globe class="h-3.5 w-3.5" />
							{:else if course.status === 'archived'}
								<Archive class="h-3.5 w-3.5" />
							{:else}
								<Pencil class="h-3.5 w-3.5" />
							{/if}
							{course.status}
						</span>
						<span class="row-stat">{course.module_count} modules</span>
						<span class="row-stat">{course.enrolled_count} enrolled</span>
					</div>
				</a>
			{/each}
		</div>
	{/if}
</div>

<style>
	.teacher-courses {
		max-width: 900px;
		margin: 0 auto;
		padding: clamp(1rem, 2vw, 1.5rem) clamp(1.25rem, 3vw, 2.25rem);
		color: var(--theme-text-primary);
	}

	.page-header {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 1rem;
		margin-bottom: 1.5rem;
	}

	.title {
		font-size: 1.5rem;
		font-weight: 800;
		margin: 0 0 0.2rem;
	}

	.subtitle {
		font-size: 0.88rem;
		color: var(--theme-text-secondary);
		margin: 0;
	}

	.create-btn {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		padding: 0.65rem 1.15rem;
		border-radius: 12px;
		border: none;
		background: rgba(var(--theme-primary-rgb), 0.9);
		color: white;
		font-weight: 700;
		cursor: pointer;
		flex-shrink: 0;
	}

	.create-btn:disabled {
		opacity: 0.55;
	}

	.filter-bar {
		margin-bottom: 1rem;
	}

	.filter-bar select {
		padding: 0.45rem 0.8rem;
		border-radius: 10px;
		border: 1px solid var(--theme-glass-border);
		background: var(--theme-input-bg);
		color: var(--theme-text-primary);
		font-size: 0.85rem;
	}

	.course-list {
		display: flex;
		flex-direction: column;
		gap: 0.65rem;
	}

	.course-row {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1rem;
		padding: 1rem 1.15rem;
		border-radius: 14px;
		text-decoration: none;
		color: inherit;
		transition: transform 0.1s;
	}

	.course-row:hover {
		transform: translateX(2px);
	}

	.glass-panel {
		background: color-mix(in srgb, var(--theme-nav-glass) 88%, transparent);
		border: 1px solid var(--theme-glass-border);
		backdrop-filter: blur(18px);
	}

	.row-info {
		flex: 1;
		min-width: 0;
	}

	.row-title {
		font-size: 1rem;
		font-weight: 700;
		margin: 0 0 0.15rem;
	}

	.row-desc {
		font-size: 0.82rem;
		color: var(--theme-text-secondary);
		margin: 0;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.row-meta {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		flex-shrink: 0;
	}

	.row-status {
		display: inline-flex;
		align-items: center;
		gap: 0.25rem;
		font-size: 0.72rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		padding: 0.2rem 0.55rem;
		border-radius: 999px;
		border: 1px solid var(--theme-glass-border);
		color: var(--theme-text-secondary);
	}

	.row-status.published {
		color: rgb(34, 197, 94);
		border-color: rgba(34, 197, 94, 0.3);
	}

	.row-status.draft {
		color: rgba(var(--theme-primary-rgb), 0.7);
		border-color: rgba(var(--theme-primary-rgb), 0.2);
	}

	.row-stat {
		font-size: 0.78rem;
		color: var(--theme-text-secondary);
	}

	.error-banner {
		padding: 0.75rem 1rem;
		border-radius: 12px;
		background: rgba(239, 68, 68, 0.08);
		border: 1px solid rgba(239, 68, 68, 0.2);
		color: #ef4444;
		margin-bottom: 1rem;
	}

	.loading-state, .empty-state {
		display: grid;
		place-items: center;
		padding: 4rem;
		gap: 0.75rem;
		color: var(--theme-text-secondary);
	}

	.spinner {
		width: 42px;
		height: 42px;
		border-radius: 50%;
		border: 3px solid rgba(var(--theme-primary-rgb), 0.14);
		border-top-color: rgba(var(--theme-primary-rgb), 0.84);
		animation: spin 0.8s linear infinite;
	}

	@keyframes spin {
		0% { transform: rotate(0deg); }
		100% { transform: rotate(360deg); }
	}

	@media (max-width: 640px) {
		.page-header {
			flex-direction: column;
		}

		.course-row {
			flex-direction: column;
			align-items: stretch;
		}

		.row-meta {
			flex-wrap: wrap;
		}
	}
</style>
