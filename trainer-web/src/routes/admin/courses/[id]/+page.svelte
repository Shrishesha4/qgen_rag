<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { ArrowLeft, CheckCircle2, Eye, RotateCcw } from 'lucide-svelte';
	import ModuleViewer from '$lib/components/ModuleViewer.svelte';
	import { getStoredSession } from '$lib/api/client';
	import { approveCourse, getCourseById, rejectCourse, type CourseResponse } from '$lib/api/courses';

	const courseId = $derived($page.params.id ?? '');
	let course = $state<CourseResponse | null>(null);
	let isLoading = $state(true);
	let isActing = $state(false);
	let error = $state<string | null>(null);
	let notice = $state<string | null>(null);
	let activeModuleIndex = $state(0);

	const activeModule = $derived(course?.modules[activeModuleIndex] ?? null);

	async function loadCourse() {
		if (!courseId) {
			error = 'Course not found.';
			isLoading = false;
			return;
		}

		isLoading = true;
		error = null;
		try {
			course = await getCourseById(courseId);
			activeModuleIndex = 0;
		} catch (caughtError: unknown) {
			error = caughtError instanceof Error ? caughtError.message : 'Failed to load course.';
		} finally {
			isLoading = false;
		}
	}

	async function handleApprove() {
		if (!course || isActing) return;
		isActing = true;
		try {
			course = await approveCourse(course.id);
			notice = 'Course approved and now available to students.';
		} catch (caughtError: unknown) {
			error = caughtError instanceof Error ? caughtError.message : 'Failed to approve course.';
		} finally {
			isActing = false;
		}
	}

	async function handleReject() {
		if (!course || isActing) return;
		isActing = true;
		try {
			course = await rejectCourse(course.id);
			notice = 'Course sent back to draft for teacher revisions.';
		} catch (caughtError: unknown) {
			error = caughtError instanceof Error ? caughtError.message : 'Failed to send course back to draft.';
		} finally {
			isActing = false;
		}
	}

	onMount(() => {
		const session = getStoredSession();
		if (!session || session.user.role !== 'admin') {
			goto('/admin/login');
			return;
		}
		void loadCourse();
	});
</script>

<svelte:head>
	<title>Course Review Detail — Admin</title>
</svelte:head>

<div class="course-review-page">
	{#if isLoading}
		<div class="loading-state"><div class="spinner"></div></div>
	{:else if error && !course}
		<div class="error-banner">{error}</div>
	{:else if course}
		<header class="page-header">
			<div>
				<button class="back-link" onclick={() => goto('/admin/courses')}>
					<ArrowLeft class="h-4 w-4" /> Back to course queue
				</button>
				<p class="eyebrow">Admin Review</p>
				<h1>{course.title}</h1>
				<p class="subtitle">Teacher ID: {course.teacher_id} • Status: {course.status}</p>
			</div>

			<div class="header-actions">
				{#if course.status === 'pending_approval'}
					<button class="secondary-btn" onclick={() => void handleReject()} disabled={isActing}>
						<RotateCcw class="h-4 w-4" /> Return to Draft
					</button>
					<button class="primary-btn" onclick={() => void handleApprove()} disabled={isActing}>
						<CheckCircle2 class="h-4 w-4" /> Approve
					</button>
				{/if}
			</div>
		</header>

		{#if notice}
			<div class="notice-banner">{notice}</div>
		{/if}
		{#if error}
			<div class="error-banner">{error}</div>
		{/if}

		<div class="review-grid">
			<aside class="course-meta glass-panel">
				<h2>Course details</h2>
				{#if course.description}
					<p class="description">{course.description}</p>
				{/if}
				<div class="meta-list">
					<div><span>Price</span><strong>{course.currency} {(course.price_cents / 100).toFixed(2)}</strong></div>
					<div><span>Modules</span><strong>{course.modules.length}</strong></div>
					<div><span>Subject ID</span><strong>{course.subject_id ?? 'Not linked'}</strong></div>
				</div>

				<h3>Modules</h3>
				<nav class="module-nav">
					{#each course.modules as module, index}
						<button class:active={index === activeModuleIndex} onclick={() => (activeModuleIndex = index)}>
							<span>{index + 1}</span>
							<div>
								<strong>{module.title}</strong>
								<small>{module.module_type}</small>
							</div>
						</button>
					{/each}
				</nav>
			</aside>

			<section class="module-preview glass-panel">
				{#if activeModule}
					<ModuleViewer module={activeModule} />
				{:else}
					<p class="empty-module">This course has no modules yet.</p>
				{/if}
			</section>
		</div>
	{/if}
</div>

<style>
	.course-review-page {
		max-width: 1320px;
		margin: 0 auto;
		padding: 1.25rem 1.5rem 2rem;
	}

	.page-header {
		display: flex;
		justify-content: space-between;
		gap: 1rem;
		align-items: start;
		margin-bottom: 1rem;
	}

	.back-link {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		margin-bottom: 0.85rem;
		border: none;
		background: transparent;
		color: var(--theme-text-secondary);
		padding: 0;
		cursor: pointer;
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

	.header-actions {
		display: flex;
		gap: 0.75rem;
		flex-wrap: wrap;
	}

	.primary-btn,
	.secondary-btn {
		display: inline-flex;
		align-items: center;
		gap: 0.45rem;
		padding: 0.7rem 1rem;
		border-radius: 12px;
		font-weight: 700;
		text-decoration: none;
		cursor: pointer;
	}

	.primary-btn {
		border: none;
		background: rgba(34, 197, 94, 0.92);
		color: white;
	}

	.secondary-btn {
		border: 1px solid var(--theme-glass-border);
		background: color-mix(in srgb, var(--theme-nav-glass) 88%, transparent);
		color: var(--theme-text-primary);
	}

	.notice-banner,
	.error-banner {
		padding: 0.85rem 1rem;
		border-radius: 14px;
		margin-bottom: 1rem;
	}

	.notice-banner {
		background: rgba(34, 197, 94, 0.08);
		border: 1px solid rgba(34, 197, 94, 0.18);
		color: rgb(21, 128, 61);
	}

	.error-banner {
		background: rgba(239, 68, 68, 0.08);
		border: 1px solid rgba(239, 68, 68, 0.18);
		color: #ef4444;
	}

	.review-grid {
		display: grid;
		grid-template-columns: 320px minmax(0, 1fr);
		gap: 1rem;
		align-items: start;
	}

	.glass-panel {
		background: color-mix(in srgb, var(--theme-nav-glass) 88%, transparent);
		border: 1px solid var(--theme-glass-border);
		backdrop-filter: blur(18px);
		border-radius: 18px;
	}

	.course-meta {
		padding: 1rem;
	}

	.course-meta h2,
	.course-meta h3 {
		margin: 0 0 0.85rem;
	}

	.description {
		margin: 0 0 1rem;
		color: var(--theme-text-secondary);
	}

	.meta-list {
		display: grid;
		gap: 0.7rem;
		margin-bottom: 1.1rem;
	}

	.meta-list div {
		display: flex;
		justify-content: space-between;
		gap: 1rem;
		font-size: 0.85rem;
	}

	.meta-list span {
		color: var(--theme-text-secondary);
	}

	.meta-list strong {
		text-align: right;
	}

	.module-nav {
		display: grid;
		gap: 0.55rem;
	}

	.module-nav button {
		display: grid;
		grid-template-columns: auto 1fr;
		gap: 0.75rem;
		align-items: start;
		padding: 0.8rem;
		border-radius: 14px;
		border: 1px solid var(--theme-glass-border);
		background: transparent;
		color: inherit;
		text-align: left;
		cursor: pointer;
	}

	.module-nav button.active {
		border-color: rgba(var(--theme-primary-rgb), 0.35);
		background: rgba(var(--theme-primary-rgb), 0.08);
	}

	.module-nav span {
		display: inline-grid;
		place-items: center;
		width: 1.8rem;
		height: 1.8rem;
		border-radius: 999px;
		background: rgba(var(--theme-primary-rgb), 0.12);
		font-size: 0.78rem;
		font-weight: 700;
	}

	.module-nav small {
		display: block;
		margin-top: 0.2rem;
		color: var(--theme-text-secondary);
		text-transform: uppercase;
		font-size: 0.72rem;
		letter-spacing: 0.05em;
	}

	.module-preview {
		padding: 0.25rem;
		min-height: 65vh;
	}

	.empty-module {
		padding: 2rem;
		color: var(--theme-text-secondary);
	}

	@media (max-width: 980px) {
		.page-header,
		.review-grid {
			grid-template-columns: 1fr;
			flex-direction: column;
		}
	}
</style>