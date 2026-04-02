<script lang="ts">
	import { BookOpen, Users } from 'lucide-svelte';
	import type { CourseSummary } from '$lib/api/courses';
	import { resolveApiAssetUrl } from '$lib/api/client';

	let { course }: { course: CourseSummary } = $props();
	const coverImageUrl = $derived(resolveApiAssetUrl(course.cover_image_url));

	const priceLabel = $derived(
		course.price_cents === 0
			? 'Free'
			: `${(course.price_cents / 100).toFixed(0)} ${course.currency}`
	);
</script>

<a href="/student/courses/{course.slug}" class="course-card" class:featured={course.is_featured}>
	{#if coverImageUrl}
		<div class="card-cover">
			<img src={coverImageUrl} alt={course.title} />
		</div>
	{:else}
		<div class="card-cover placeholder-cover">
			<BookOpen class="h-8 w-8" />
		</div>
	{/if}

	<div class="card-body">
		<h3 class="card-title">{course.title}</h3>
		{#if course.description}
			<p class="card-desc">{course.description}</p>
		{/if}

		<div class="card-meta">
			<span class="card-price" class:free={course.price_cents === 0}>{priceLabel}</span>
			<span class="card-stat">
				<BookOpen class="h-3.5 w-3.5" />
				{course.module_count} modules
			</span>
			<span class="card-stat">
				<Users class="h-3.5 w-3.5" />
				{course.enrolled_count} enrolled
			</span>
		</div>
	</div>
</a>

<style>
	.course-card {
		display: flex;
		flex-direction: column;
		border-radius: 18px;
		border: 1px solid var(--theme-glass-border);
		background: color-mix(in srgb, var(--theme-nav-glass) 88%, transparent);
		backdrop-filter: blur(14px);
		overflow: hidden;
		text-decoration: none;
		color: inherit;
		transition: transform 0.15s, box-shadow 0.15s;
	}

	.course-card:hover {
		transform: translateY(-2px);
		box-shadow: 0 12px 32px rgba(0, 0, 0, 0.12);
	}

	.course-card.featured {
		border-color: rgba(var(--theme-primary-rgb), 0.35);
	}

	.card-cover {
		aspect-ratio: 16 / 9;
		overflow: hidden;
		background: var(--theme-input-bg);
	}

	.card-cover img {
		width: 100%;
		height: 100%;
		object-fit: cover;
	}

	.placeholder-cover {
		display: grid;
		place-items: center;
		color: var(--theme-text-secondary);
		opacity: 0.4;
	}

	.card-body {
		padding: 1rem 1.15rem;
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		flex: 1;
	}

	.card-title {
		font-size: 1rem;
		font-weight: 700;
		margin: 0;
		color: var(--theme-text-primary);
		display: -webkit-box;
		line-clamp: 2;
		-webkit-line-clamp: 2;
		-webkit-box-orient: vertical;
		overflow: hidden;
	}

	.card-desc {
		font-size: 0.82rem;
		color: var(--theme-text-secondary);
		margin: 0;
		display: -webkit-box;
		line-clamp: 2;
		-webkit-line-clamp: 2;
		-webkit-box-orient: vertical;
		overflow: hidden;
	}

	.card-meta {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.65rem;
		margin-top: auto;
		padding-top: 0.5rem;
		font-size: 0.76rem;
	}

	.card-price {
		font-weight: 800;
		color: var(--theme-text-primary);
	}

	.card-price.free {
		color: rgb(34, 197, 94);
	}

	.card-stat {
		display: inline-flex;
		align-items: center;
		gap: 0.25rem;
		color: var(--theme-text-secondary);
	}
</style>
