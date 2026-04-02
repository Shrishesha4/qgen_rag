<script lang="ts">
	import { Users, Upload, AlertCircle, CheckCircle2 } from 'lucide-svelte';

	const steps = [
		{
			title: 'Import roster',
			description: 'Upload a CSV of students with name, email, cohort, and grade.',
			icon: Upload,
		},
		{
			title: 'Assign evaluation items',
			description: 'Attach curated evaluation items to a GEL assignment for the cohort.',
			icon: CheckCircle2,
		},
		{
			title: 'Track progress',
			description: 'Use Analytics to monitor completion, scores, and issue patterns.',
			icon: Users,
		},
	];
</script>

<svelte:head>
	<title>GEL Students | Teacher Dashboard</title>
</svelte:head>

<div class="gel-page">
	<section class="gel-panel gel-page__hero">
		<div>
			<p class="gel-page__eyebrow">GEL</p>
			<h1 class="gel-page__title">Students</h1>
			<p class="gel-page__copy">
				Roster tooling is the next piece of the teacher workflow. This area now communicates the
				intended process clearly while the supporting APIs are being completed.
			</p>
		</div>
		<div class="gel-page__actions">
			<button on:click={() => alert('Upload support coming soon. For now, share your roster with the team.')} class="gel-button gel-button--primary">
				<Upload class="h-5 w-5" />
				<span>Upload Roster</span>
			</button>
		</div>
	</section>

	<section class="gel-panel gel-empty">
		<Users class="h-12 w-12" />
		<h2>Roster management is coming soon</h2>
		<p>
			Teacher-facing cohort, invitation, and access-control workflows are still being wired up.
			Until then, coordinate student lists with the team or use existing assignments to onboard participants manually.
		</p>
	</section>

	<div class="gel-note gel-panel">
		<AlertCircle class="h-5 w-5" />
		<div>
			<p><strong>Temporary limitation</strong></p>
			<p>Access controls, invitations, and CSV upload processing will become active with the roster API rollout.</p>
		</div>
	</div>

	<section class="gel-grid-3">
		{#each steps as step}
			<div class="gel-panel gel-card">
				<div class="gel-card__header">
					<svelte:component this={step.icon} class="h-5 w-5" />
					<h3 class="gel-card__title">{step.title}</h3>
				</div>
				<p class="gel-card__copy">{step.description}</p>
			</div>
		{/each}
	</section>
</div>
