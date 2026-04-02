<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { ChevronLeft, ChevronRight, Check, BookOpen, MessageSquare, Menu, PanelLeftClose, PanelLeftOpen, X } from 'lucide-svelte';
	import ResizableSplitter from '$lib/components/ResizableSplitter.svelte';
	import ModuleViewer from '$lib/components/ModuleViewer.svelte';
	import TutorChat from '$lib/components/TutorChat.svelte';
	import { getCourseBySlug, type CourseResponse, type CourseModuleResponse } from '$lib/api/courses';
	import { listEnrollments, updateProgress, type EnrollmentResponse } from '$lib/api/enrollments';

	const courseSlug = $derived($page.params.courseSlug ?? '');

	let course = $state<CourseResponse | null>(null);
	let enrollment = $state<EnrollmentResponse | null>(null);
	let activeModuleIndex = $state(0);
	let isLoading = $state(true);
	let error = $state<string | null>(null);
	let splitWidth = $state(55);
	let mobileTab = $state<'content' | 'tutor'>('content');
	let showSidebar = $state(false);
	let sidebarCollapsed = $state(false);

	const activeModule = $derived(course?.modules[activeModuleIndex] ?? null);
	const completedIds = $derived(new Set(enrollment?.progress_data?.completed_module_ids ?? []));
	const progressPercent = $derived(
		course?.modules.length
			? Math.round((completedIds.size / course.modules.length) * 100)
			: 0
	);

	onMount(async () => {
		if (!courseSlug) {
			error = 'Course not found.';
			isLoading = false;
			return;
		}

		try {
			course = await getCourseBySlug(courseSlug);
			// Find the enrollment for this course
			const enrollRes = await listEnrollments();
			enrollment = enrollRes.items.find((e) => e.course_id === course!.id) ?? null;

			if (!enrollment) {
				goto(`/courses/${courseSlug}`);
				return;
			}

			// Resume from last incomplete module
			if (enrollment.progress_data?.completed_module_ids?.length && course.modules.length) {
				const done = new Set(enrollment.progress_data.completed_module_ids);
				const firstIncomplete = course.modules.findIndex((m) => !done.has(m.id));
				if (firstIncomplete >= 0) activeModuleIndex = firstIncomplete;
			}
		} catch (e: unknown) {
			error = (e as Error).message ?? 'Failed to load course.';
		} finally {
			isLoading = false;
		}
	});

	async function completeModule() {
		if (!enrollment || !activeModule) return;
		try {
			enrollment = await updateProgress(enrollment.id, {
				completed_module_ids: [activeModule.id],
			});
		} catch {
			// Best-effort: continue even if save fails
		}
		// Auto-advance to next module
		if (course && activeModuleIndex < course.modules.length - 1) {
			activeModuleIndex++;
		}
	}

	function selectModule(index: number) {
		activeModuleIndex = index;
		showSidebar = false;
	}

	function toggleSidebarCollapsed() {
		sidebarCollapsed = !sidebarCollapsed;
	}
</script>

<div class="learn-page">
	{#if isLoading}
		<div class="loading-state"><div class="spinner"></div></div>
	{:else if error}
		<div class="error-state">{error}</div>
	{:else if course && enrollment}
		<!-- Top bar -->
		<header class="learn-header glass-panel">
			<button class="back-btn" onclick={() => goto('/student/courses')}>
				<ChevronLeft class="h-4 w-4" />
			</button>
			<h1 class="course-name">{course.title}</h1>
			<div class="progress-bar-wrapper">
				<div class="progress-track">
					<div class="progress-fill" style="width: {progressPercent}%"></div>
				</div>
				<span class="progress-label">{progressPercent}%</span>
			</div>
			<button class="sidebar-toggle mobile-only" onclick={() => showSidebar = !showSidebar}>
				{#if showSidebar}
					<X class="h-5 w-5" />
				{:else}
					<Menu class="h-5 w-5" />
				{/if}
			</button>
		</header>

		<!-- Mobile tab switcher -->
		<div class="mobile-tabs mobile-only">
			<button class:active={mobileTab === 'content'} onclick={() => mobileTab = 'content'}>
				<BookOpen class="h-4 w-4" /> Content
			</button>
			<button class:active={mobileTab === 'tutor'} onclick={() => mobileTab = 'tutor'}>
				<MessageSquare class="h-4 w-4" /> Tutor
			</button>
		</div>

		<div class="learn-body">
			<!-- Module sidebar (desktop always visible, mobile toggle) -->
			<aside class="module-sidebar glass-panel" class:open={showSidebar} class:collapsed={sidebarCollapsed}>
				<div class="sidebar-header desktop-only">
					<h2 class="sidebar-title">{sidebarCollapsed ? 'Mod' : 'Modules'}</h2>
					<button class="sidebar-collapse-btn" onclick={toggleSidebarCollapsed} aria-label={sidebarCollapsed ? 'Expand module sidebar' : 'Collapse module sidebar'}>
						{#if sidebarCollapsed}
							<PanelLeftOpen class="h-4 w-4" />
						{:else}
							<PanelLeftClose class="h-4 w-4" />
						{/if}
					</button>
				</div>
				<h2 class="sidebar-title mobile-only">Modules</h2>
				<nav class="sidebar-nav">
					{#each course.modules as mod, i}
						<button
							class="sidebar-item"
							class:active={i === activeModuleIndex}
							class:completed={completedIds.has(mod.id)}
							class:icon-only={sidebarCollapsed}
							onclick={() => selectModule(i)}
							title={mod.title}
						>
							<span class="sidebar-index">
								{#if completedIds.has(mod.id)}
									<Check class="h-3.5 w-3.5" />
								{:else}
									{i + 1}
								{/if}
							</span>
							{#if !sidebarCollapsed}
								<span class="sidebar-label">{mod.title}</span>
							{/if}
						</button>
					{/each}
				</nav>
			</aside>

			<!-- Main content area (split pane on desktop, tabs on mobile) -->
			<div class="split-area desktop-only">
				<ResizableSplitter bind:leftWidth={splitWidth} minLeft={350} minRight={300}>
					{#snippet left()}
						{#if activeModule}
							<ModuleViewer module={activeModule} onComplete={completeModule} />
						{/if}
					{/snippet}
					{#snippet right()}
						<TutorChat
							subjectId={course?.subject_id}
							courseId={course?.id}
							moduleId={activeModule?.id}
						/>
					{/snippet}
				</ResizableSplitter>
			</div>

			<div class="mobile-content mobile-only">
				{#if mobileTab === 'content'}
					{#if activeModule}
						<ModuleViewer module={activeModule} onComplete={completeModule} />
					{/if}
				{:else}
					<TutorChat
						subjectId={course?.subject_id}
						courseId={course?.id}
						moduleId={activeModule?.id}
					/>
				{/if}
			</div>
		</div>
	{/if}
</div>

<style>
	.learn-page {
		display: flex;
		flex-direction: column;
		height: 100%;
		min-height: 0;
		overflow: hidden;
		color: var(--theme-text-primary);
	}

	.learn-header {
		display: flex;
		align-items: center;
		gap: 0.85rem;
		padding: 0.65rem 1rem;
		border-radius: 0;
		border-top: none;
		border-left: none;
		border-right: none;
		flex-shrink: 0;
	}

	.glass-panel {
		background: color-mix(in srgb, var(--theme-nav-glass) 88%, transparent);
		border: 1px solid var(--theme-glass-border);
		backdrop-filter: blur(18px);
	}

	.back-btn {
		display: inline-flex;
		align-items: center;
		padding: 0.35rem;
		border-radius: 8px;
		border: 1px solid var(--theme-glass-border);
		background: transparent;
		color: var(--theme-text-primary);
		cursor: pointer;
	}

	.course-name {
		font-size: 0.92rem;
		font-weight: 700;
		margin: 0;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		flex: 1;
	}

	.progress-bar-wrapper {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-shrink: 0;
	}

	.progress-track {
		width: 100px;
		height: 6px;
		border-radius: 3px;
		background: var(--theme-input-bg);
		overflow: hidden;
	}

	.progress-fill {
		height: 100%;
		border-radius: 3px;
		background: rgba(var(--theme-primary-rgb), 0.8);
		transition: width 0.3s;
	}

	.progress-label {
		font-size: 0.72rem;
		font-weight: 700;
		color: var(--theme-text-secondary);
	}

	.learn-body {
		display: flex;
		flex: 1;
		min-height: 0;
		overflow: hidden;
	}

	.module-sidebar {
		width: 240px;
		flex-shrink: 0;
		display: flex;
		flex-direction: column;
		overflow-y: auto;
		padding: 1rem 0.5rem;
		border-radius: 0;
		border-top: none;
		border-bottom: none;
		border-left: none;
		transition: width 0.18s ease, padding 0.18s ease;
	}

	.module-sidebar.collapsed {
		width: 76px;
		padding-inline: 0.35rem;
	}

	.sidebar-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
		padding: 0 0.25rem 0.5rem;
	}

	.sidebar-collapse-btn {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 28px;
		height: 28px;
		padding: 0;
		border-radius: 999px;
		border: 1px solid var(--theme-glass-border);
		background: var(--theme-input-bg);
		color: var(--theme-text-secondary);
		cursor: pointer;
	}

	.sidebar-title {
		font-size: 0.78rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		color: var(--theme-text-secondary);
		margin: 0 0.5rem 0.75rem;
	}

	.sidebar-nav {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		min-height: 0;
	}

	.sidebar-item {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.55rem 0.65rem;
		border-radius: 10px;
		border: none;
		background: transparent;
		color: var(--theme-text-primary);
		cursor: pointer;
		text-align: left;
		font-size: 0.84rem;
		transition: background 0.1s;
	}

	.sidebar-item:hover {
		background: rgba(var(--theme-primary-rgb), 0.06);
	}

	.sidebar-item.active {
		background: rgba(var(--theme-primary-rgb), 0.12);
		font-weight: 600;
	}

	.sidebar-item.completed {
		color: var(--theme-text-secondary);
	}

	.sidebar-item.icon-only {
		justify-content: center;
		padding-inline: 0.35rem;
	}

	.sidebar-index {
		width: 24px;
		height: 24px;
		border-radius: 50%;
		background: var(--theme-input-bg);
		display: grid;
		place-items: center;
		font-size: 0.72rem;
		font-weight: 700;
		flex-shrink: 0;
	}

	.sidebar-item.completed .sidebar-index {
		background: rgba(34, 197, 94, 0.15);
		color: rgb(34, 197, 94);
	}

	.sidebar-label {
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.split-area {
		flex: 1;
		min-height: 0;
		overflow: hidden;
	}

	.mobile-content {
		flex: 1;
		overflow-y: auto;
	}

	.mobile-tabs {
		display: flex;
		gap: 0;
		border-bottom: 1px solid var(--theme-glass-border);
		flex-shrink: 0;
	}

	.mobile-tabs button {
		flex: 1;
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 0.35rem;
		padding: 0.65rem;
		border: none;
		background: transparent;
		color: var(--theme-text-secondary);
		font-weight: 600;
		font-size: 0.85rem;
		cursor: pointer;
		border-bottom: 2px solid transparent;
	}

	.mobile-tabs button.active {
		color: rgba(var(--theme-primary-rgb), 0.9);
		border-bottom-color: rgba(var(--theme-primary-rgb), 0.9);
	}

	.sidebar-toggle {
		display: inline-flex;
		align-items: center;
		padding: 0.35rem;
		border-radius: 8px;
		border: 1px solid var(--theme-glass-border);
		background: transparent;
		color: var(--theme-text-primary);
		cursor: pointer;
	}

	/* Desktop / mobile visibility */
	.desktop-only { display: flex; }
	.mobile-only { display: none; }

	@media (max-width: 768px) {
		.desktop-only { display: none !important; }
		.mobile-only { display: flex; }

		.module-sidebar {
			position: fixed;
			top: 0;
			left: 0;
			bottom: 0;
			z-index: 50;
			width: 260px;
			transform: translateX(-100%);
			transition: transform 0.2s;
		}

		.module-sidebar.open {
			transform: translateX(0);
		}
	}

	.loading-state {
		flex: 1;
		display: grid;
		place-items: center;
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

	.error-state {
		flex: 1;
		display: grid;
		place-items: center;
		color: #ef4444;
	}
</style>
