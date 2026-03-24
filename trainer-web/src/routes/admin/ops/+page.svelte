<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { session, currentUser } from '$lib/session';
	import WorkflowWizard from '$lib/components/WorkflowWizard.svelte';
	import StatusDisplay from '$lib/components/StatusDisplay.svelte';
	import ModeToggle from '$lib/components/ModeToggle.svelte';
	import {
		getTrainingStatus,
		listModelVersions,
		listTrainingJobs,
		buildTrainingDataset,
		listTrainingDatasets,
		evaluateModelVersion,
		canaryModelVersion,
		promoteModelVersion,
		rollbackModelVersion,
		getTrainingQueueStatus,
		getLiveModelMetrics,
		triggerTraining,
		type ModelVersionResponse,
		type TrainingJobResponse,
		type TrainingDatasetResponse,
		type TrainingStatus,
	} from '$lib/api/training';

	let loading = $state(true);
	let busy = $state(false);
	let error = $state('');
	let status = $state<TrainingStatus | null>(null);
	let versions = $state<ModelVersionResponse[]>([]);
	let jobs = $state<TrainingJobResponse[]>([]);
	let datasets = $state<TrainingDatasetResponse[]>([]);
	let queueStatus = $state<Record<string, unknown> | null>(null);
	let liveMetrics = $state<Record<string, unknown> | null>(null);
	let operationResult = $state<Record<string, unknown> | null>(null);

	let selectedVersionId = $state('');
	let selectedDatasetTag = $state('');
	let evalType = $state('offline');
	let trainingMethod = $state('sft+dpo');
	let days = $state(30);
	let confidenceMin = $state(0.0);
	let isAdvanced = $state(true);
	let currentWorkflowStep = $state(0);
	let stepStatuses = $state<('waiting' | 'in-progress' | 'completed' | 'error')[]>([
		'waiting',
		'waiting',
		'waiting',
		'waiting',
		'waiting',
	]);
	let stepSummaries = $state<string[]>([
		'Prepare a set of training materials to begin.',
		'Start training when your materials are ready.',
		'Run a quality check after training finishes.',
		'Try the AI with a small group if you want extra reassurance.',
		'Deploying to all students is optional and can be done later.',
	]);

	onMount(() => {
		const unsub = session.subscribe((s) => {
			if (!s || !['teacher', 'admin'].includes(s.user.role)) {
				goto('/teacher/login');
			}
		});
		void refreshAll();
		return () => {
			unsub();
		};
	});

	async function refreshAll() {
		loading = true;
		error = '';
		try {
			const [nextStatus, nextVersions, nextJobs, nextDatasets, nextQueue, nextLive] = await Promise.all([
				getTrainingStatus(),
				listModelVersions(),
				listTrainingJobs(20),
				listTrainingDatasets(50),
				getTrainingQueueStatus(),
				getLiveModelMetrics(),
			]);
			status = nextStatus;
			versions = nextVersions;
			jobs = nextJobs;
			datasets = nextDatasets;
			queueStatus = nextQueue;
			liveMetrics = nextLive;
			if (!selectedVersionId && nextVersions.length > 0) selectedVersionId = nextVersions[0].id;
			if (!selectedDatasetTag && nextDatasets.length > 0) selectedDatasetTag = nextDatasets[0].dataset_tag;
			syncWorkflowState(nextStatus, nextVersions, nextJobs, nextDatasets);
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to load ops data';
		} finally {
			loading = false;
		}
	}

	function metricCount(metrics: Record<string, unknown> | null | undefined): number {
		return metrics ? Object.keys(metrics).length : 0;
	}

	function formatTrainingProgress(job: TrainingJobResponse | null, versionTag?: string): string {
		if (!job) {
			return versionTag ? `${versionTag} is getting ready for training.` : 'Training has been queued.';
		}

		if (job.total_epochs > 0 && job.current_epoch > 0) {
			return `${versionTag ?? 'Your AI'} is training now — epoch ${job.current_epoch} of ${job.total_epochs}.`;
		}

		if (job.total_steps > 0 && job.current_step > 0) {
			return `${versionTag ?? 'Your AI'} is training now — step ${job.current_step} of ${job.total_steps}.`;
		}

		if (job.status === 'pending') {
			return `${versionTag ?? 'Your AI'} is queued and will begin training shortly.`;
		}

		return `${versionTag ?? 'Your AI'} is training now.`;
	}

	function syncWorkflowState(
		nextStatus: TrainingStatus,
		nextVersions: ModelVersionResponse[],
		nextJobs: TrainingJobResponse[],
		nextDatasets: TrainingDatasetResponse[]
	) {
		const previousStatuses = [...stepStatuses];
		const previousSummaries = [...stepSummaries];
		const nextStepStatuses: ('waiting' | 'in-progress' | 'completed' | 'error')[] = [
			'waiting',
			'waiting',
			'waiting',
			'waiting',
			'waiting',
		];
		const nextStepSummaries = [
			'Prepare a set of training materials to begin.',
			'Start training when your materials are ready.',
			'Run a quality check after training finishes.',
			'Try the AI with a small group if you want extra reassurance.',
			'Deploying to all students is optional and can be done later.',
		];

		const selectedVersion = nextVersions.find((version) => version.id === selectedVersionId) ?? nextVersions[0] ?? null;
		const selectedVersionTag = selectedVersion?.version_tag;
		const latestTrainingJob = nextJobs.find((job) => /sft|dpo|train/i.test(job.job_type)) ?? null;
		const latestEvalJob = nextJobs.find((job) => /eval/i.test(job.job_type)) ?? null;
		const normalizedStatus = selectedVersion?.status?.toLowerCase() ?? '';
		const activeVersionTag = nextStatus.active_version?.version_tag ?? '';

		if (nextDatasets.length > 0) {
			nextStepStatuses[0] = 'completed';
			nextStepSummaries[0] = `Training materials are ready. Latest set: ${nextDatasets[0].dataset_tag}.`;
		}

		if (latestTrainingJob?.status === 'failed' || normalizedStatus === 'failed') {
			nextStepStatuses[1] = 'error';
			nextStepSummaries[1] = selectedVersion?.error_message || latestTrainingJob?.error_message || 'Training needs attention before you continue.';
		} else if (latestTrainingJob && ['pending', 'running'].includes(latestTrainingJob.status)) {
			nextStepStatuses[1] = 'in-progress';
			nextStepSummaries[1] = formatTrainingProgress(latestTrainingJob, selectedVersionTag);
		} else if (
			selectedVersion &&
			(selectedVersion.training_completed_at !== null || ['completed', 'ready', 'evaluated', 'canary', 'promoted', 'active'].includes(normalizedStatus))
		) {
			nextStepStatuses[1] = 'completed';
			nextStepSummaries[1] = `${selectedVersion.version_tag} finished training and is ready for checking.`;
		} else if (selectedVersion && ['pending', 'queued'].includes(normalizedStatus)) {
			nextStepStatuses[1] = 'in-progress';
			nextStepSummaries[1] = `${selectedVersion.version_tag} is queued and will begin training shortly.`;
		} else if (previousStatuses[1] !== 'waiting') {
			nextStepStatuses[1] = previousStatuses[1];
			nextStepSummaries[1] = previousSummaries[1];
		}

		if (latestEvalJob?.status === 'failed') {
			nextStepStatuses[2] = 'error';
			nextStepSummaries[2] = latestEvalJob.error_message || 'The quality check did not finish successfully.';
		} else if (latestEvalJob && ['pending', 'running'].includes(latestEvalJob.status)) {
			nextStepStatuses[2] = 'in-progress';
			nextStepSummaries[2] = `Quality check is running for ${selectedVersionTag ?? 'your AI version'}.`;
		} else if (selectedVersion?.eval_metrics) {
			nextStepStatuses[2] = 'completed';
			nextStepSummaries[2] = `Quality check completed. ${metricCount(selectedVersion.eval_metrics)} evaluation signals were recorded.`;
			console.log('Evaluation step marked as completed based on eval_metrics');
		} else if (nextStepStatuses[1] === 'completed') {
			nextStepSummaries[2] = `Training is done. You can now run a quality check for ${selectedVersionTag ?? 'this version'}.`;
		} else if (previousStatuses[2] !== 'waiting') {
			nextStepStatuses[2] = previousStatuses[2];
			nextStepSummaries[2] = previousSummaries[2];
		}

		if (normalizedStatus.includes('canary')) {
			nextStepStatuses[3] = 'completed';
			nextStepSummaries[3] = `${selectedVersionTag ?? 'This AI version'} has been sent to a classroom trial.`;
		} else if (previousStatuses[3] !== 'waiting') {
			nextStepStatuses[3] = previousStatuses[3];
			nextStepSummaries[3] = previousSummaries[3];
		} else if (nextStepStatuses[2] === 'completed') {
			nextStepSummaries[3] = 'Optional: try this AI with a smaller group before deciding on full rollout.';
			console.log('Canary step ready - evaluation completed');
		}

		if ((selectedVersion?.is_active ?? false) || (selectedVersionTag && activeVersionTag === selectedVersionTag)) {
			nextStepStatuses[4] = 'completed';
			nextStepSummaries[4] = `${selectedVersionTag ?? 'This AI version'} is now live for all students.`;
		} else if (previousStatuses[4] !== 'waiting') {
			nextStepStatuses[4] = previousStatuses[4];
			nextStepSummaries[4] = previousSummaries[4];
		} else if (nextStepStatuses[3] === 'completed' || nextStepStatuses[2] === 'completed') {
			nextStepSummaries[4] = 'Optional: deploy this version now, or come back later when you are comfortable.';
		}

		stepStatuses = nextStepStatuses;
		stepSummaries = nextStepSummaries;

		if (nextStepStatuses[0] !== 'completed') {
			currentWorkflowStep = 0;
		} else if (['waiting', 'in-progress', 'error'].includes(nextStepStatuses[1])) {
			currentWorkflowStep = 1;
		} else if (['waiting', 'in-progress', 'error'].includes(nextStepStatuses[2])) {
			currentWorkflowStep = 2;
		} else if (nextStepStatuses[4] === 'completed') {
			currentWorkflowStep = 4;
		} else {
			currentWorkflowStep = 3;
		}
		
		console.log('Workflow state updated', { 
			currentWorkflowStep, 
			stepStatuses: nextStepStatuses, 
			selectedVersionId, 
			hasVersions: versions.length > 0 
		});
	}

	async function runOpWithStepUpdate(fn: () => Promise<Record<string, unknown>>, stepIndex: number) {
		busy = true;
		error = '';
		operationResult = null;
		stepStatuses[stepIndex] = 'in-progress';
		stepSummaries[stepIndex] = [
			'Preparing your training materials now.',
			'Training has started. This can take some time, and you can come back later.',
			'Running the quality check now.',
			'Starting the classroom trial now.',
			'Deploying this AI version to students now.'
		][stepIndex];
		try {
			operationResult = await fn();
			if (stepIndex === 0) {
				stepStatuses[stepIndex] = 'completed';
				stepSummaries[stepIndex] = 'Training materials were prepared successfully.';
			} else if (stepIndex === 4) {
				stepStatuses[stepIndex] = 'completed';
				stepSummaries[stepIndex] = 'This AI version has been deployed for all students.';
			}
			if (currentWorkflowStep === stepIndex && stepIndex < 3) {
				currentWorkflowStep++;
			}
			await refreshAll();
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Operation failed';
			stepStatuses[stepIndex] = 'error';
		} finally {
			busy = false;
		}
	}

	async function handleBuildDataset() {
		await runOpWithStepUpdate(() => buildTrainingDataset({ days, confidence_min: confidenceMin }), 0);
	}

	async function handleTriggerTraining() {
		await runOpWithStepUpdate(() => triggerTraining({ training_method: trainingMethod }), 1);
	}

	async function handleEvaluate() {
		if (!selectedVersionId) {
			error = 'Please select a model version to evaluate';
			return;
		}
		await runOpWithStepUpdate(() => evaluateModelVersion(selectedVersionId, { dataset_tag: selectedDatasetTag || undefined, eval_type: evalType || 'offline' }), 2);
	}

	async function handleCanary() {
		console.log('handleCanary called', { selectedVersionId, stepStatuses, currentWorkflowStep });
		if (!selectedVersionId) {
			error = 'Please select a model version for classroom trial';
			return;
		}
		console.log('Starting canary deployment for version:', selectedVersionId);
		await runOpWithStepUpdate(() => canaryModelVersion(selectedVersionId), 3);
	}

	async function handlePromote() {
		if (!selectedVersionId) {
			error = 'Please select a model version to deploy';
			return;
		}
		await runOpWithStepUpdate(() => promoteModelVersion(selectedVersionId), 4);
	}

	async function handleRollback() {
		if (!selectedVersionId) {
			error = 'Please select a model version to rollback';
			return;
		}
		await runOp(() => rollbackModelVersion(selectedVersionId));
	}

	async function runOp(fn: () => Promise<Record<string, unknown>>) {
		busy = true;
		error = '';
		operationResult = null;
		try {
			operationResult = await fn();
			await refreshAll();
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Operation failed';
		} finally {
			busy = false;
		}
	}

	function getPretty(obj: unknown): string {
		return JSON.stringify(obj, null, 2);
	}
</script>

<svelte:head>
	<title>AI Training Studio — VQuest Trainer</title>
</svelte:head>

<div class="ops-page">
	<div class="hero glass-panel">
		<div class="hero-head">
			<div>
				<p class="hero-eyebrow">Admin Operations</p>
				<h1 class="font-serif">AI Training Studio</h1>
				<p class="muted">Welcome back, {$currentUser?.full_name || $currentUser?.username}</p>
			</div>
			<div class="hero-controls">
				<ModeToggle bind:isAdvanced />
			</div>
		</div>
		<div class="hero-stats" aria-label="Ops summary">
			<div class="hero-stat-pill">
				<span>Versions</span>
				<strong>{versions.length}</strong>
			</div>
			<div class="hero-stat-pill">
				<span>Datasets</span>
				<strong>{datasets.length}</strong>
			</div>
			<div class="hero-stat-pill">
				<span>Jobs</span>
				<strong>{jobs.length}</strong>
			</div>
		</div>
	</div>

	{#if loading}
		<div class="glass-panel loading-message">
			<div class="loading-spinner">⟳</div>
			Setting up your training studio...
		</div>
	{:else if isAdvanced}
		
		<!-- Status Display in Advanced Mode -->
		<StatusDisplay 
			status={status as Record<string, unknown> | null}
			{queueStatus} 
			{liveMetrics} 
			{isAdvanced} 
			{loading}
		/>

		<div class="grid">
			<!-- Original technical cards here -->
			<section class="glass-panel card">
				<div class="card-head">
					<h2>Trigger Training</h2>
				</div>
				<div class="row">
					<label for="training-method">Method</label>
					<select id="training-method" bind:value={trainingMethod}>
						<option value="sft">sft</option>
						<option value="dpo">dpo</option>
						<option value="sft+dpo">sft+dpo</option>
					</select>
				</div>
				<button disabled={busy} onclick={() => runOp(() => triggerTraining({ training_method: trainingMethod }))}>Run Training Trigger</button>
			</section>

			<section class="glass-panel card">
				<div class="card-head">
					<h2>Build Dataset</h2>
				</div>
				<div class="row">
					<label for="dataset-days">Days</label>
					<input id="dataset-days" type="number" min="1" bind:value={days} />
				</div>
				<div class="row">
					<label for="confidence-min">Confidence Min</label>
					<input id="confidence-min" type="number" min="0" max="1" step="0.05" bind:value={confidenceMin} />
				</div>
				<button disabled={busy} onclick={() => runOp(() => buildTrainingDataset({ days, confidence_min: confidenceMin }))}>
					Build Dataset Snapshot
				</button>
			</section>

			<section class="glass-panel card">
				<div class="card-head">
					<h2>Evaluate / Canary / Promote</h2>
				</div>
				<div class="row">
					<label for="selected-version">Version</label>
					<select id="selected-version" bind:value={selectedVersionId}>
						{#each versions as v}
							<option value={v.id}>{v.version_tag} ({v.status})</option>
						{/each}
					</select>
				</div>
				<div class="row">
					<label for="dataset-tag">Dataset Tag</label>
					<input id="dataset-tag" bind:value={selectedDatasetTag} placeholder="latest" />
				</div>
				<div class="row">
					<label for="eval-type">Eval Type</label>
					<input id="eval-type" bind:value={evalType} />
				</div>
				<div class="button-row">
					<button disabled={busy || !selectedVersionId} onclick={() => runOp(() => evaluateModelVersion(selectedVersionId, { dataset_tag: selectedDatasetTag || undefined, eval_type: evalType || 'offline' }))}>Evaluate</button>
					<button disabled={busy || !selectedVersionId} onclick={() => runOp(() => canaryModelVersion(selectedVersionId))}>Canary</button>
					<button disabled={busy || !selectedVersionId} onclick={() => runOp(() => promoteModelVersion(selectedVersionId))}>Promote</button>
					<button class="danger" disabled={busy || !selectedVersionId} onclick={() => runOp(() => rollbackModelVersion(selectedVersionId))}>Rollback</button>
				</div>
			</section>

			<!-- Add more advanced cards as needed -->
		</div>
	{:else}

		<!-- Status Display in Simple Mode -->
		<StatusDisplay 
			status={status as Record<string, unknown> | null}
			{queueStatus} 
			{liveMetrics} 
			{isAdvanced} 
			{loading}
		/>

		<WorkflowWizard
			bind:currentStep={currentWorkflowStep}
			bind:stepStatuses={stepStatuses}
			{stepSummaries}
			{busy}
			{error}
			{days}
			{confidenceMin}
			{trainingMethod}
			bind:selectedVersionId
			bind:selectedDatasetTag
			{versions}
			onBuildDataset={handleBuildDataset}
			onTriggerTraining={handleTriggerTraining}
			onEvaluate={handleEvaluate}
			onCanary={handleCanary}
			onPromote={handlePromote}
		/>
	{/if}

	{#if operationResult && isAdvanced}
		<div class="glass-panel result">
			<h2>Last Operation Result</h2>
			<pre>{getPretty(operationResult)}</pre>
		</div>
	{/if}
</div>

<style>
	.ops-page {
		width: min(1120px, 100%);
		margin: 0 auto;
		padding: clamp(1rem, 1.5vw, 1.5rem);
		display: flex;
		flex-direction: column;
		gap: clamp(0.95rem, 1.5vw, 1.2rem);
		color: var(--theme-text, rgba(255, 255, 255, 0.95));
	}

	.hero {
		padding: clamp(1rem, 2vw, 1.25rem);
		background:
			linear-gradient(140deg, rgba(var(--theme-primary-rgb), 0.2) 0%, rgba(17, 24, 39, 0.2) 42%, rgba(7, 11, 20, 0.28) 100%),
			rgba(255, 255, 255, 0.06);
		border: 1px solid rgba(255, 255, 255, 0.14);
	}

	.hero-head {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 1rem;
	}

	.hero-controls {
		display: flex;
		align-items: flex-start;
	}

	.hero-controls :global(.mode-toggle) {
		margin: 0;
	}

	.hero-eyebrow {
		margin: 0;
		font-size: 0.72rem;
		font-weight: 700;
		letter-spacing: 0.11em;
		text-transform: uppercase;
		color: var(--theme-text-secondary, rgba(0, 0, 0, 0.6));
	}

	.hero h1 {
		margin: 0.2rem 0 0;
		font-size: clamp(1.5rem, 2.6vw, 1.95rem);
		font-weight: 700;
		letter-spacing: 0.012em;
		text-shadow: 0 1px 10px rgba(0, 0, 0, 0.35);
	}

	.hero p {
		margin: 0.38rem 0 0;
		font-size: clamp(0.92rem, 1.4vw, 1.02rem);
		line-height: 1.4;
	}

	.hero-stats {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 0.55rem;
		margin-top: 0.85rem;
	}

	.hero-stat-pill {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 0.5rem;
		padding: 0.52rem 0.68rem;
		border-radius: 0.72rem;
		background: rgba(6, 10, 18, 0.28);
		border: 1px solid rgba(255, 255, 255, 0.14);
	}

	.hero-stat-pill span {
		font-size: 0.72rem;
		letter-spacing: 0.05em;
		text-transform: uppercase;
		color: rgba(226, 236, 252, 0.72);
	}

	.hero-stat-pill strong {
		font-size: 1rem;
		font-weight: 700;
		color: rgba(247, 251, 255, 0.96);
	}

	.muted {
		opacity: 0.88;
		color: var(--theme-text-muted, rgba(225, 232, 247, 0.88));
	}

	.loading-message {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		padding: 1.6rem;
		text-align: center;
		font-size: 1rem;
		justify-content: center;
		border: 1px solid rgba(255, 255, 255, 0.14);
	}

	.loading-spinner {
		animation: spin 1s linear infinite;
		font-size: 1.5rem;
	}

	@keyframes spin {
		from { transform: rotate(0deg); }
		to { transform: rotate(360deg); }
	}

	.grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(310px, 1fr));
		gap: 0.95rem;
		align-items: start;
	}

	.card {
		display: flex;
		flex-direction: column;
		gap: 0.9rem;
		min-height: 230px;
		padding: 1rem 1.05rem;
		border: 1px solid rgba(255, 255, 255, 0.34);
		background: linear-gradient(150deg, rgba(255, 255, 255, 0.82), rgba(255, 255, 255, 0.68));
		box-shadow: 0 10px 26px rgba(7, 12, 22, 0.12);
	}

	.card h2 {
		margin: 0 0 0.2rem;
		font-size: 1.22rem;
		font-weight: 650;
		letter-spacing: 0.01em;
		color: var(--theme-text-primary, #1a1a2e);
	}

	.card-head {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 0.7rem;
	}

	.row {
		display: grid;
		grid-template-columns: 120px minmax(0, 1fr);
		column-gap: 0.8rem;
		align-items: center;
		margin: 0.2rem 0;
	}

	.row label {
		min-width: 0;
		opacity: 0.95;
		font-size: 1rem;
		font-weight: 560;
		color: var(--theme-text-primary, #1a1a2e);
	}

	.row input,
	.row select {
		width: 100%;
		padding: 0.72rem 0.8rem;
		border-radius: 0.7rem;
		border: 1px solid rgba(13, 22, 36, 0.14);
		background: rgba(255, 255, 255, 0.84);
		color: var(--theme-text-primary, #1a1a2e);
		font-size: 0.95rem;
		font-weight: 520;
		outline: none;
		box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.2);
	}

	.row input::placeholder {
		color: rgba(31, 41, 55, 0.56);
	}

	.row input:focus,
	.row select:focus {
		border-color: rgba(var(--theme-primary-rgb), 0.8);
		box-shadow:
			0 0 0 3px rgba(var(--theme-primary-rgb), 0.2),
			inset 0 1px 0 rgba(255, 255, 255, 0.08);
	}

	.row select option {
		background: #ffffff;
		color: #1a1a2e;
	}

	button {
		margin-top: 0.35rem;
		padding: 0.75rem 0.92rem;
		border-radius: 0.7rem;
		border: 1px solid rgba(var(--theme-primary-rgb), 0.72);
		background: linear-gradient(
			180deg,
			rgba(var(--theme-primary-rgb), 0.92) 0%,
			rgba(var(--theme-primary-rgb), 0.62) 100%
		);
		color: #ffffff;
		font-size: 0.9rem;
		font-weight: 680;
		letter-spacing: 0.01em;
		text-shadow: 0 1px 6px rgba(0, 0, 0, 0.4);
		cursor: pointer;
		transition: transform 120ms ease, filter 120ms ease, box-shadow 120ms ease;
		box-shadow: 0 8px 20px rgba(0, 0, 0, 0.24);
	}

	button:hover:not(:disabled) {
		filter: brightness(1.08);
		transform: translateY(-1px);
		box-shadow: 0 10px 24px rgba(0, 0, 0, 0.28);
	}

	button:active:not(:disabled) {
		transform: translateY(0);
	}

	button:focus-visible {
		outline: 2px solid rgba(255, 255, 255, 0.96);
		outline-offset: 2px;
	}

	button:disabled {
		opacity: 0.5;
		cursor: not-allowed;
		transform: none;
		box-shadow: none;
	}

	button.danger {
		border-color: rgba(255, 130, 130, 0.78);
		background: linear-gradient(180deg, rgba(214, 78, 78, 0.9) 0%, rgba(147, 44, 44, 0.95) 100%);
	}

	.button-row {
		display: flex;
		gap: 0.65rem;
		flex-wrap: wrap;
		margin-top: 0.35rem;
	}

	.button-row button {
		min-width: 106px;
	}

	pre {
		margin: 0.1rem 0 0;
		max-height: 240px;
		overflow: auto;
		font-size: 0.8rem;
		line-height: 1.4;
		padding: 0.72rem;
		border-radius: 0.6rem;
		background: rgba(8, 12, 21, 0.7);
		color: rgba(232, 242, 255, 0.96);
		border: 1px solid rgba(255, 255, 255, 0.18);
	}

	.result {
		border: 1px solid rgba(255, 255, 255, 0.2);
	}

	@media (max-width: 640px) {
		.ops-page {
			padding: 0.8rem;
			gap: 0.9rem;
		}

		.hero,
		.card {
			padding: 0.85rem 0.9rem;
		}

		.hero-head {
			flex-direction: column;
			align-items: flex-start;
			gap: 0.65rem;
		}

		.hero-controls {
			width: 100%;
		}

		.hero-controls :global(.toggle-btn) {
			width: 100%;
			justify-content: center;
		}

		.hero-stats {
			grid-template-columns: 1fr;
		}

		.grid {
			grid-template-columns: 1fr;
			gap: 0.9rem;
		}

		.row {
			grid-template-columns: 1fr;
			row-gap: 0.45rem;
			margin: 0.1rem 0;
		}

		.button-row button {
			flex: 1 1 calc(50% - 0.35rem);
			min-width: 0;
		}
	}
</style>
