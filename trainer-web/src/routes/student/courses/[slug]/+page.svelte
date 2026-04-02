<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { BookOpen, Clock, Star, PlayCircle, Lock, CheckCircle2 } from 'lucide-svelte';
	import PaymentAnimation from '$lib/components/PaymentAnimation.svelte';
	import { getCourseBySlug, type CourseResponse } from '$lib/api/courses';
	import { enrollInCourse, listEnrollments, type EnrollmentResponse } from '$lib/api/enrollments';
	import { getStoredSession } from '$lib/api/client';

	let course = $state<CourseResponse | null>(null);
	let isLoading = $state(true);
	let error = $state<string | null>(null);
	let enrollError = $state<string | null>(null);
	let showPayment = $state(false);
	let isEnrolling = $state(false);
	let existingEnrollment = $state<EnrollmentResponse | null>(null);

	const slug = $derived($page.params.slug ?? '');
	const session = $derived(getStoredSession());
	const isLoggedIn = $derived(!!session?.access_token);
	const isEnrolled = $derived(!!existingEnrollment);
	const priceLabel = $derived(
		course?.price_cents === 0
			? 'Free'
			: `₹${((course?.price_cents ?? 0) / 100).toFixed(0)}`
	);

	function formatDate(value: string) {
		return new Date(value).toLocaleDateString(undefined, {
			month: 'short',
			day: 'numeric',
			year: 'numeric',
		});
	}

	onMount(async () => {
		if (!slug) {
			error = 'Course not found.';
			isLoading = false;
			return;
		}

		try {
			course = await getCourseBySlug(slug);

			if (isLoggedIn) {
				try {
					const enrollmentList = await listEnrollments();
					existingEnrollment = enrollmentList.items.find((item) => item.course_id === course?.id) ?? null;
				} catch {
					existingEnrollment = null;
				}
			}
		} catch (e: unknown) {
			error = (e as Error).message ?? 'Course not found.';
		} finally {
			isLoading = false;
		}
	});

	async function handleEnroll() {
		if (!course || isEnrolling) return;

		if (existingEnrollment) {
			goto(`/student/learn/${course.slug}`);
			return;
		}

		if (!isLoggedIn) {
			goto('/login');
			return;
		}

		isEnrolling = true;
		enrollError = null;

		if (course.price_cents > 0) {
			// Mock payment animation
			showPayment = true;
		} else {
			// Free enrollment — go directly
			try {
				existingEnrollment = await enrollInCourse(course.id, { payment_provider: 'mock', mock: true });
				goto(`/student/learn/${course.slug}`);
			} catch (e: unknown) {
				enrollError = (e as Error).message ?? 'Enrollment failed.';
				isEnrolling = false;
			}
		}
	}

	async function onPaymentComplete() {
		if (!course) return;
		try {
			existingEnrollment = await enrollInCourse(course.id, { payment_provider: 'mock', mock: true });
			goto(`/student/learn/${course.slug}`);
		} catch (e: unknown) {
			enrollError = (e as Error).message ?? 'Enrollment failed.';
			showPayment = false;
			isEnrolling = false;
		}
	}
</script>

{#if showPayment}
	<PaymentAnimation onComplete={onPaymentComplete} />
{/if}

<div class="course-detail">
	{#if isLoading}
		<div class="loading-state"><div class="spinner"></div></div>
	{:else if error}
		<div class="error-state">{error}</div>
	{:else if course}
		<header class="course-hero">
			{#if course.cover_image_url}
				<img src={course.cover_image_url} alt={course.title} class="hero-cover" />
			{/if}
			<div class="hero-content">
				<h1 class="hero-title">{course.title}</h1>
				{#if course.description}
					<p class="hero-desc">{course.description}</p>
				{/if}

				<div class="hero-meta">
					{#if isEnrolled}
						<span class="owned-pill"><CheckCircle2 class="h-4 w-4" /> Purchased</span>
						<span class="meta-item"><Clock class="h-4 w-4" /> Enrolled {formatDate(existingEnrollment?.enrolled_at ?? '')}</span>
					{:else}
						<span class="hero-price" class:free={course.price_cents === 0}>{priceLabel}</span>
					{/if}
					<span class="meta-item"><BookOpen class="h-4 w-4" /> {course.modules.length} modules</span>
				</div>

				<button class="enroll-btn" onclick={handleEnroll} disabled={isEnrolling}>
					{#if isEnrolling}
						Enrolling…
					{:else if existingEnrollment}
						Continue Learning
					{:else if course.price_cents === 0}
						Enroll for Free
					{:else}
						Buy — {priceLabel}
					{/if}
				</button>

				{#if enrollError}
					<p class="enroll-error">{enrollError}</p>
				{/if}
			</div>
		</header>

		{#if course.learning_outcomes}
			<section class="section glass-panel">
				<h2 class="section-title">What You'll Learn</h2>
				{#if Array.isArray(course.learning_outcomes)}
					<ul class="outcomes-list">
						{#each course.learning_outcomes as outcome}
							<li><Star class="h-4 w-4" /> <span>{outcome}</span></li>
						{/each}
					</ul>
				{/if}
			</section>
		{/if}

		<section class="section glass-panel">
			<h2 class="section-title">Curriculum</h2>
			<div class="module-list">
				{#each course.modules as mod, i}
					<div class="module-item">
						<span class="module-index">{i + 1}</span>
						<div class="module-info">
							<span class="module-name">{mod.title}</span>
							{#if mod.description}
								<span class="module-desc-text">{mod.description}</span>
							{/if}
						</div>
						<div class="module-badges">
							{#if isEnrolled}
								<span class="preview-badge available-badge"><CheckCircle2 class="h-3.5 w-3.5" /> Available</span>
							{:else if mod.is_preview}
								<span class="preview-badge"><PlayCircle class="h-3.5 w-3.5" /> Preview</span>
							{:else}
								<Lock class="h-3.5 w-3.5 lock-icon" />
							{/if}
							{#if mod.duration_minutes}
								<span class="duration-badge"><Clock class="h-3.5 w-3.5" /> {mod.duration_minutes} min</span>
							{/if}
						</div>
					</div>
				{/each}
			</div>
		</section>
	{/if}
</div>

<style>
	.course-detail {
		max-width: 900px;
		margin: 0 auto;
		padding: clamp(1rem, 2vw, 1.5rem) clamp(1.25rem, 3vw, 2.25rem) clamp(2rem, 3vw, 2.75rem);
		color: var(--theme-text-primary);
	}

	.course-hero {
		margin-bottom: 2rem;
	}

	.hero-cover {
		width: 100%;
		aspect-ratio: 21 / 9;
		object-fit: cover;
		border-radius: 18px;
		margin-bottom: 1.5rem;
		border: 1px solid var(--theme-glass-border);
	}

	.hero-content {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}

	.hero-title {
		font-size: 1.75rem;
		font-weight: 800;
		margin: 0;
	}

	.hero-desc {
		font-size: 0.95rem;
		color: var(--theme-text-secondary);
		margin: 0;
		line-height: 1.6;
	}

	.hero-meta {
		display: flex;
		align-items: center;
		gap: 1rem;
		flex-wrap: wrap;
	}

	.hero-price {
		font-size: 1.25rem;
		font-weight: 800;
	}

	.hero-price.free {
		color: rgb(34, 197, 94);
	}

	.owned-pill {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		padding: 0.4rem 0.7rem;
		border-radius: 999px;
		background: rgba(34, 197, 94, 0.14);
		border: 1px solid rgba(34, 197, 94, 0.3);
		color: rgb(134, 239, 172);
		font-size: 0.82rem;
		font-weight: 700;
	}

	.meta-item {
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
		font-size: 0.85rem;
		color: var(--theme-text-secondary);
	}

	.enroll-btn {
		align-self: flex-start;
		padding: 0.85rem 2rem;
		border-radius: 14px;
		border: none;
		background: rgba(var(--theme-primary-rgb), 0.9);
		color: white;
		font-weight: 800;
		font-size: 1rem;
		cursor: pointer;
		transition: background 0.15s;
	}

	.enroll-btn:hover {
		background: rgba(var(--theme-primary-rgb), 1);
	}

	.enroll-btn:disabled {
		opacity: 0.55;
		cursor: not-allowed;
	}

	.enroll-error {
		font-size: 0.84rem;
		color: #ef4444;
		margin: 0;
	}

	.section {
		margin-bottom: 1.5rem;
		padding: 1.25rem;
	}

	.glass-panel {
		background: color-mix(in srgb, var(--theme-nav-glass) 88%, transparent);
		border: 1px solid var(--theme-glass-border);
		border-radius: 18px;
		box-shadow: 0 18px 48px rgba(0, 0, 0, 0.18);
		backdrop-filter: blur(18px);
	}

	.section-title {
		font-size: 1.15rem;
		font-weight: 700;
		margin: 0 0 1rem;
	}

	.outcomes-list {
		list-style: none;
		padding: 0;
		margin: 0;
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.outcomes-list li {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		font-size: 0.9rem;
	}

	.module-list {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.module-item {
		display: flex;
		align-items: center;
		gap: 0.85rem;
		padding: 0.75rem 0.85rem;
		border-radius: 12px;
		border: 1px solid var(--theme-glass-border);
		background: var(--theme-input-bg);
	}

	.module-index {
		width: 28px;
		height: 28px;
		border-radius: 50%;
		background: rgba(var(--theme-primary-rgb), 0.1);
		color: rgba(var(--theme-primary-rgb), 0.9);
		display: grid;
		place-items: center;
		font-size: 0.78rem;
		font-weight: 800;
		flex-shrink: 0;
	}

	.module-info {
		flex: 1;
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
	}

	.module-name {
		font-weight: 600;
		font-size: 0.9rem;
	}

	.module-desc-text {
		font-size: 0.78rem;
		color: var(--theme-text-secondary);
	}

	.module-badges {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-shrink: 0;
	}

	.preview-badge, .duration-badge {
		display: inline-flex;
		align-items: center;
		gap: 0.25rem;
		font-size: 0.72rem;
		color: var(--theme-text-secondary);
	}

	.preview-badge {
		color: rgba(var(--theme-primary-rgb), 0.85);
	}

	.available-badge {
		color: rgb(134, 239, 172);
	}

	:global(.lock-icon) {
		color: var(--theme-text-secondary);
		opacity: 0.5;
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

	.error-state {
		display: grid;
		place-items: center;
		padding: 4rem;
		color: #ef4444;
	}
</style>
