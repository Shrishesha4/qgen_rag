<script lang="ts">
	import { onMount } from 'svelte';
	import { Search, Compass, LibraryBig, Clock3, CheckCircle2 } from 'lucide-svelte';
	import CourseCard from '$lib/components/CourseCard.svelte';
	import { listCourses, type CourseSummary } from '$lib/api/courses';
	import { listEnrollments, type EnrollmentResponse } from '$lib/api/enrollments';
	import { resolveApiAssetUrl } from '$lib/api/client';
	import { getStoredSession } from '$lib/api/client';

	type EnrollmentWithCourse = EnrollmentResponse & {
		course: NonNullable<EnrollmentResponse['course']>;
	};

	let courses = $state<CourseSummary[]>([]);
	let enrollments = $state<EnrollmentResponse[]>([]);
	let total = $state(0);
	let page = $state(1);
	let pageSize = 12;
	let search = $state('');
	let activeTab = $state<'catalog' | 'my-courses'>('my-courses');
	let isLoading = $state(true);
	let isLoadingMyCourses = $state(true);
	let error = $state<string | null>(null);
	let myCoursesError = $state<string | null>(null);

	let searchTimer: ReturnType<typeof setTimeout>;

	const session = $derived(getStoredSession());
	const isLoggedIn = $derived(!!session?.access_token);

	function matchesCourseSearch(
		course: { title: string; description: string | null; slug?: string },
		query: string,
	) {
		const normalizedQuery = query.trim().toLowerCase();
		if (!normalizedQuery) return true;

		return [course.title, course.description ?? '', course.slug ?? '']
			.join(' ')
			.toLowerCase()
			.includes(normalizedQuery);
	}

	function getOwnedCourseEnrollments(items: EnrollmentResponse[], query: string): EnrollmentWithCourse[] {
		return items
			.filter((item): item is EnrollmentWithCourse => !!item.course)
			.filter((item) => matchesCourseSearch(item.course, query))
			.sort((left, right) => Date.parse(right.enrolled_at) - Date.parse(left.enrolled_at));
	}

	function formatDate(value: string) {
		return new Date(value).toLocaleDateString(undefined, {
			month: 'short',
			day: 'numeric',
			year: 'numeric',
		});
	}

	function getCompletionText(enrollment: EnrollmentWithCourse) {
		const completedCount = enrollment.progress_data?.completed_module_ids?.length ?? 0;
		const totalModules = enrollment.course.modules.length;

		if (totalModules === 0) {
			return 'Ready to start';
		}

		return `${Math.round((completedCount / totalModules) * 100)}% complete`;
	}

	function coverImageUrl(path: string | null | undefined) {
		return resolveApiAssetUrl(path);
	}

	async function fetchCourses() {
		isLoading = true;
		error = null;
		try {
			const res = await listCourses({
				search: search || undefined,
				page,
				page_size: pageSize,
			});
			courses = res.items;
			total = res.total;
		} catch (e: unknown) {
			error = (e as Error).message ?? 'Failed to load courses.';
		} finally {
			isLoading = false;
		}
	}

	async function loadMyCourses() {
		isLoadingMyCourses = true;
		myCoursesError = null;

		if (!isLoggedIn) {
			enrollments = [];
			isLoadingMyCourses = false;
			return;
		}

		try {
			const res = await listEnrollments();
			enrollments = res.items;
		} catch (e: unknown) {
			myCoursesError = (e as Error).message ?? 'Failed to load your courses.';
		} finally {
			isLoadingMyCourses = false;
		}
	}

	function onSearchInput() {
		clearTimeout(searchTimer);
		if (activeTab === 'my-courses') {
			return;
		}

		searchTimer = setTimeout(() => {
			page = 1;
			fetchCourses();
		}, 350);
	}

	onMount(() => {
		void Promise.all([fetchCourses(), loadMyCourses()]);
	});

	const totalPages = $derived(Math.ceil(total / pageSize));
	const myCourses = $derived(getOwnedCourseEnrollments(enrollments, search));
	const ownedCourseCount = $derived(getOwnedCourseEnrollments(enrollments, '').length);
</script>

<div class="catalog-page">
	<div class="catalog-toolbar glass-panel">
		<div class="tab-row">
			<button class="tab-chip" class:active={activeTab === 'my-courses'} onclick={() => (activeTab = 'my-courses')}>
				<LibraryBig class="h-4 w-4" />
				My Courses
				<span class="tab-count">{ownedCourseCount}</span>
			</button>
			<button class="tab-chip" class:active={activeTab === 'catalog'} onclick={() => (activeTab = 'catalog')}>
				<Compass class="h-4 w-4" />
				Catalog
			</button>
		</div>

		<div class="search-bar">
			<Search class="h-4 w-4 search-icon" />
			<input
				type="text"
				bind:value={search}
				oninput={onSearchInput}
				placeholder={activeTab === 'catalog' ? 'Search courses…' : 'Search your purchased courses…'}
			/>
		</div>
	</div>

	{#if activeTab === 'catalog' && error}
		<div class="error-banner">{error}</div>
	{/if}

	{#if activeTab === 'my-courses' && myCoursesError}
		<div class="error-banner">{myCoursesError}</div>
	{/if}

	{#if activeTab === 'catalog'}
		{#if isLoading}
			<div class="loading-state">
				<div class="spinner"></div>
			</div>
		{:else if courses.length === 0}
			<div class="empty-state glass-panel">
				<p>No courses found. Check back later.</p>
			</div>
		{:else}
			<div class="course-grid">
				{#each courses as course (course.id)}
					<CourseCard {course} />
				{/each}
			</div>

			{#if totalPages > 1}
				<div class="pagination">
					<button disabled={page <= 1} onclick={() => { page--; fetchCourses(); }}>Previous</button>
					<span class="page-info">Page {page} of {totalPages}</span>
					<button disabled={page >= totalPages} onclick={() => { page++; fetchCourses(); }}>Next</button>
				</div>
			{/if}
		{/if}
	{:else}
		{#if !isLoggedIn}
			<div class="empty-state glass-panel">
				<p>Sign in to see courses you already own.</p>
				<a href="/login" class="action-link">Go to login</a>
			</div>
		{:else if isLoadingMyCourses}
			<div class="loading-state">
				<div class="spinner"></div>
			</div>
		{:else if myCourses.length === 0}
			<div class="empty-state glass-panel">
				<p>
					{search.trim()
						? 'No purchased courses match this search.'
						: 'You have not purchased any courses yet.'}
				</p>
			</div>
		{:else}
			<div class="owned-course-grid">
				{#each myCourses as enrollment (enrollment.id)}
					<a href="/student/learn/{enrollment.course.slug}" class="owned-course-card glass-panel">
						{#if coverImageUrl(enrollment.course.cover_image_url)}
							<img src={coverImageUrl(enrollment.course.cover_image_url) ?? ''} alt={enrollment.course.title} class="owned-course-cover" />
						{:else}
							<div class="owned-course-cover placeholder-cover">
								<LibraryBig class="h-8 w-8" />
							</div>
						{/if}

						<div class="owned-course-body">
							<div class="owned-course-topline">
								<span class="owned-badge"><CheckCircle2 class="h-3.5 w-3.5" /> Purchased</span>
								<span class="owned-date"><Clock3 class="h-3.5 w-3.5" /> {formatDate(enrollment.enrolled_at)}</span>
							</div>

							<h2 class="owned-course-title">{enrollment.course.title}</h2>
							{#if enrollment.course.description}
								<p class="owned-course-description">{enrollment.course.description}</p>
							{/if}

							<div class="owned-course-footer">
								<span class="owned-progress">{getCompletionText(enrollment)}</span>
								<span class="owned-link">Continue learning</span>
							</div>
						</div>
					</a>
				{/each}
			</div>
		{/if}
	{/if}
</div>

<style>
	.catalog-page {
		max-width: 1240px;
		margin: 0 auto;
		padding: clamp(1rem, 2vw, 1.5rem) clamp(1.25rem, 3vw, 2.25rem) clamp(2rem, 3vw, 2.75rem);
		color: var(--theme-text-primary);
	}
	
	.catalog-toolbar {
		display: flex;
		align-items: center;
		justify-content: space-between;
		flex-wrap: wrap;
		gap: 1rem;
		margin-bottom: 1.5rem;
		padding: 0.75rem 1rem;
	}

	.tab-row {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		flex-wrap: wrap;
	}

	.tab-chip {
		display: inline-flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.55rem 0.85rem;
		border-radius: 999px;
		border: 1px solid var(--theme-glass-border);
		background: var(--theme-input-bg);
		color: var(--theme-text-secondary);
		cursor: pointer;
		font-weight: 700;
	}

	.tab-chip.active {
		background: rgba(var(--theme-primary-rgb), 0.14);
		border-color: rgba(var(--theme-primary-rgb), 0.34);
		color: var(--theme-text-primary);
	}

	.tab-count {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		min-width: 1.5rem;
		height: 1.5rem;
		padding: 0 0.35rem;
		border-radius: 999px;
		background: rgba(var(--theme-primary-rgb), 0.16);
		color: rgba(var(--theme-primary-rgb), 0.95);
		font-size: 0.74rem;
	}

	.glass-panel {
		background: color-mix(in srgb, var(--theme-nav-glass) 88%, transparent);
		border: 1px solid var(--theme-glass-border);
		border-radius: 18px;
		box-shadow: 0 18px 48px rgba(0, 0, 0, 0.18);
		backdrop-filter: blur(18px);
	}

	.search-bar {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex: 1;
		min-width: min(100%, 280px);
	}

	.search-bar :global(.search-icon) {
		color: var(--theme-text-secondary);
		flex-shrink: 0;
	}

	.search-bar input {
		flex: 1;
		border: none;
		background: transparent;
		color: var(--theme-text-primary);
		font-size: 0.9rem;
		outline: none;
	}

	.search-bar input::placeholder {
		color: var(--theme-text-secondary);
	}

	.course-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
		gap: 1.25rem;
	}

	.owned-course-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
		gap: 1.25rem;
	}

	.owned-course-card {
		display: flex;
		flex-direction: column;
		padding: 0;
		overflow: hidden;
		text-decoration: none;
		color: inherit;
		transition: transform 0.15s ease, box-shadow 0.15s ease;
	}

	.owned-course-card:hover {
		transform: translateY(-2px);
		box-shadow: 0 18px 40px rgba(0, 0, 0, 0.16);
	}

	.owned-course-cover {
		width: 100%;
		height: 180px;
		object-fit: cover;
		background: var(--theme-input-bg);
	}

	.owned-course-body {
		display: flex;
		flex-direction: column;
		gap: 0.8rem;
		padding: 1rem 1.1rem 1.15rem;
		flex: 1;
	}

	.owned-course-topline,
	.owned-course-footer,
	.owned-date,
	.owned-badge,
	.owned-progress {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
	}

	.owned-course-topline,
	.owned-course-footer {
		justify-content: space-between;
		flex-wrap: wrap;
	}

	.owned-badge {
		padding: 0.3rem 0.55rem;
		border-radius: 999px;
		background: rgba(34, 197, 94, 0.14);
		border: 1px solid rgba(34, 197, 94, 0.28);
		color: rgb(134, 239, 172);
		font-size: 0.75rem;
		font-weight: 700;
	}

	.owned-date,
	.owned-progress {
		font-size: 0.78rem;
		color: var(--theme-text-secondary);
	}

	.owned-course-title {
		margin: 0;
		font-size: 1rem;
		font-weight: 800;
		color: var(--theme-text-primary);
	}

	.owned-course-description {
		margin: 0;
		font-size: 0.84rem;
		line-height: 1.55;
		color: var(--theme-text-secondary);
		display: -webkit-box;
		line-clamp: 3;
		-webkit-line-clamp: 3;
		-webkit-box-orient: vertical;
		overflow: hidden;
	}

	.owned-link {
		font-size: 0.8rem;
		font-weight: 800;
		color: rgba(var(--theme-primary-rgb), 0.94);
	}

	.pagination {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 1rem;
		margin-top: 2rem;
	}

	.pagination button {
		padding: 0.5rem 1rem;
		border-radius: 10px;
		border: 1px solid var(--theme-glass-border);
		background: var(--theme-input-bg);
		color: var(--theme-text-primary);
		cursor: pointer;
		font-weight: 600;
	}

	.pagination button:disabled {
		opacity: 0.4;
		cursor: not-allowed;
	}

	.page-info {
		font-size: 0.85rem;
		color: var(--theme-text-secondary);
	}

	.loading-state {
		display: grid;
		place-items: center;
		padding: 4rem;
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

	.empty-state {
		display: grid;
		place-items: center;
		gap: 0.75rem;
		padding: 4rem;
		color: var(--theme-text-secondary);
		text-align: center;
	}

	.action-link {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		padding: 0.7rem 1rem;
		border-radius: 999px;
		text-decoration: none;
		font-weight: 700;
		color: white;
		background: rgba(var(--theme-primary-rgb), 0.92);
	}

	.error-banner {
		padding: 0.75rem 1rem;
		border-radius: 12px;
		background: rgba(239, 68, 68, 0.08);
		border: 1px solid rgba(239, 68, 68, 0.2);
		color: #ef4444;
		margin-bottom: 1rem;
		font-size: 0.88rem;
	}

	@media (max-width: 720px) {
		.catalog-toolbar {
			align-items: stretch;
		}

		.search-bar {
			width: 100%;
		}

		.owned-course-topline,
		.owned-course-footer {
			align-items: flex-start;
			flex-direction: column;
		}
	}
</style>
