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

<div class="glass-panel p-6 space-y-6 border border-white/10 shadow-2xl text-slate-100">
	<div class="flex items-center justify-between">
		<div>
			<p class="text-xs uppercase tracking-[0.2em] text-slate-300">GEL</p>
			<h1 class="text-3xl font-semibold text-white">Students</h1>
			<p class="text-slate-200/80">Manage cohorts and track who is participating in GEL assignments.</p>
		</div>
	</div>

	<div class="glass-panel border border-white/10 rounded-xl p-10 text-center space-y-3 bg-slate-900/70">
		<Users class="h-12 w-12 text-rose-200 mx-auto" />
		<h2 class="text-xl font-semibold text-white">Roster management is coming soon</h2>
		<p class="text-slate-300/85 max-w-2xl mx-auto">
			We are finishing the teacher-facing roster APIs. In the meantime, share your student list with the team or use existing assignments to invite participants manually.
		</p>
		<button
			on:click={() => alert('Upload support coming soon. For now, share your roster with the team.')}
			class="inline-flex items-center space-x-2 px-4 py-2 rounded-xl bg-rose-500 hover:bg-rose-400 text-white shadow-lg shadow-rose-500/20"
		>
			<Upload class="h-5 w-5" />
			<span>Upload roster (coming soon)</span>
		</button>
		<div class="flex items-center justify-center space-x-2 text-sm text-amber-200 mt-2">
			<AlertCircle class="h-4 w-4" />
			<span>Access controls and invitations will be enabled with the upcoming roster API.</span>
		</div>
	</div>

	<div class="grid md:grid-cols-3 gap-4">
		{#each steps as step}
			<div class="glass-panel border border-white/10 p-4 rounded-xl">
				<div class="flex items-center space-x-3">
					<svelte:component this={step.icon} class="h-5 w-5 text-rose-200" />
					<div>
						<p class="text-sm font-semibold text-white">{step.title}</p>
						<p class="text-sm text-slate-300/85">{step.description}</p>
					</div>
				</div>
			</div>
		{/each}
	</div>
</div>
