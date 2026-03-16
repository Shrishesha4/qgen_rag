<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { session, currentUser } from '$lib/session';
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
	let activeHelpCard = $state<string | null>(null);

	type HelpField = {
		name: string;
		meaning: string;
		impact: string;
	};

	type HelpCard = {
		title: string;
		description: string;
		fields: HelpField[];
	};

	const cardHelp: Record<string, HelpCard> = {
		triggerTraining: {
			title: 'Trigger Training',
			description: 'Starts a new fine-tuning run from vetted data.',
			fields: [
				{
					name: 'Method',
					meaning: 'Selects which training strategy to run: SFT, DPO, or both.',
					impact:
						'SFT improves baseline instruction quality; DPO improves preference alignment from reject/edit signals; sft+dpo does both for stronger generation behavior.'
				},
				{
					name: 'Run Training Trigger',
					meaning: 'Queues a training job and creates a new model version entry.',
					impact:
						'Begins the model-improvement cycle; later generations can become better after evaluation and promotion.'
				}
			]
		},
		buildDataset: {
			title: 'Build Dataset',
			description: 'Builds a snapshot of training examples from recent vetting data.',
			fields: [
				{
					name: 'Days',
					meaning: 'How far back to look for vetted examples.',
					impact:
						'Lower values focus on recent behavior drift; higher values increase volume but may include older style patterns.'
				},
				{
					name: 'Confidence Min',
					meaning: 'Minimum confidence threshold for including examples.',
					impact:
						'Higher thresholds improve dataset quality but reduce size; lower thresholds increase diversity but may add noisy supervision.'
				},
				{
					name: 'Build Dataset Snapshot',
					meaning: 'Creates and stores an immutable dataset tag for downstream evaluation/training.',
					impact:
						'Provides reproducible inputs so training/evaluation results can be compared reliably across versions.'
				}
			]
		},
		evaluatePromote: {
			title: 'Evaluate / Canary / Promote',
			description: 'Runs quality gates before making a model active.',
			fields: [
				{
					name: 'Version',
					meaning: 'Target model version for evaluation or rollout actions.',
					impact:
						'All quality and rollout operations apply to this version; selecting the wrong version can gate or deploy the wrong candidate.'
				},
				{
					name: 'Dataset Tag',
					meaning: 'Dataset snapshot used for evaluation.',
					impact:
						'Determines what performance is measured; stable tags make comparisons across versions fair and repeatable.'
				},
				{
					name: 'Eval Type',
					meaning: 'Evaluation mode (for example, offline).',
					impact:
						'Changes which metrics and gate checks run before canary/promotion.'
				},
				{
					name: 'Evaluate',
					meaning: 'Runs evaluation and records metrics for the selected version.',
					impact:
						'Updates offline quality signals that promotion gates use to protect generation quality.'
				},
				{
					name: 'Canary',
					meaning: 'Starts limited rollout/validation against the active baseline.',
					impact:
						'Checks real-world behavior safely before full promotion.'
				},
				{
					name: 'Promote',
					meaning: 'Marks the candidate as active if gates pass.',
					impact:
						'Future question generation uses this model by default.'
				},
				{
					name: 'Rollback',
					meaning: 'Reverts active model to a previous stable version.',
					impact:
						'Reduces production risk quickly when generation quality regresses.'
				}
			]
		},
		pipelineStatus: {
			title: 'Pipeline Status',
			description: 'Live snapshot of the training pipeline state.',
			fields: [
				{
					name: 'Status JSON',
					meaning: 'Current backend state for training phases, latest jobs, and state flags.',
					impact:
						'Helps diagnose stuck phases or sequencing issues that can delay model improvements and generation updates.'
				}
			]
		},
		queueStatus: {
			title: 'Queue Status',
			description: 'Background worker queue health and depth.',
			fields: [
				{
					name: 'Queue JSON',
					meaning: 'Per-queue pending/running/failed counters.',
					impact:
						'Backlog or failures here slow evaluation/training completion, delaying generation quality updates.'
				}
			]
		},
		liveMetrics: {
			title: 'Live Metrics',
			description: 'Operational model quality and reliability metrics.',
			fields: [
				{
					name: 'Metrics JSON',
					meaning: 'Approve/reject rates, timeout/latency, and related live KPIs.',
					impact:
						'Directly reflects current generation quality; these metrics drive promotion confidence and rollback decisions.'
				}
			]
		},
		modelVersions: {
			title: 'Recent Model Versions',
			description: 'Most recent model lineage and metadata entries.',
			fields: [
				{
					name: 'Versions JSON',
					meaning: 'Version tags, statuses, and adapter metadata.',
					impact:
						'Makes it easy to select correct candidates and trace which model version changed generation behavior.'
				}
			]
		},
		recentJobs: {
			title: 'Recent Jobs',
			description: 'Latest training/evaluation job history.',
			fields: [
				{
					name: 'Jobs JSON',
					meaning: 'Recent job statuses, errors, and completion data.',
					impact:
						'Identifies failures that block training progress and prevent better generation models from going live.'
				}
			]
		},
		recentDatasets: {
			title: 'Recent Datasets',
			description: 'Recently built dataset snapshots used by the pipeline.',
			fields: [
				{
					name: 'Datasets JSON',
					meaning: 'Dataset tags, size, and source properties.',
					impact:
						'Dataset quality and coverage strongly influence what the model learns and how it generates questions.'
				}
			]
		}
	};

	function getActiveHelp(): HelpCard | null {
		if (!activeHelpCard) return null;
		return cardHelp[activeHelpCard] ?? null;
	}

	function toggleHelp(cardId: string) {
		activeHelpCard = activeHelpCard === cardId ? null : cardId;
	}

	function closeHelp() {
		activeHelpCard = null;
	}

	onMount(() => {
		const unsub = session.subscribe((s) => {
			if (!s || s.user.role !== 'teacher') {
				goto('/teacher/login');
			}
		});
		void refreshAll();
		const onKeyDown = (event: KeyboardEvent) => {
			if (event.key === 'Escape') closeHelp();
		};
		window.addEventListener('keydown', onKeyDown);
		return () => {
			unsub();
			window.removeEventListener('keydown', onKeyDown);
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
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to load ops data';
		} finally {
			loading = false;
		}
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
	<title>Training Ops — VQuest Trainer</title>
</svelte:head>

<div class="ops-page">
	<div class="hero glass-panel">
		<h1 class="font-serif">Training Ops</h1>
		<p class="muted">Signed in as: {$currentUser?.username} ({$currentUser?.role})</p>
	</div>

	{#if loading}
		<div class="glass-panel">Loading training operations data...</div>
	{:else}
		<div class="grid">
			<section class="glass-panel card">
				<div class="card-head">
					<h2>Trigger Training</h2>
					<button
						type="button"
						class="info-btn"
						onclick={() => toggleHelp('triggerTraining')}
						aria-label="Explain Trigger Training card"
						aria-expanded={activeHelpCard === 'triggerTraining'}
					>
						i
					</button>
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
					<button
						type="button"
						class="info-btn"
						onclick={() => toggleHelp('buildDataset')}
						aria-label="Explain Build Dataset card"
						aria-expanded={activeHelpCard === 'buildDataset'}
					>
						i
					</button>
				</div>
				<div class="row">
					<label for="dataset-days">Days</label>
					<input id="dataset-days" type="number" min="1" bind:value={days} />
				</div>
				<div class="row">
					<label for="confidence-min">Confidence Min</label>
					<input id="confidence-min" type="number" min="0" max="1" step="0.05" bind:value={confidenceMin} />
				</div>
				<button
					disabled={busy}
					onclick={() => runOp(() => buildTrainingDataset({ days, confidence_min: confidenceMin }))}
				>
					Build Dataset Snapshot
				</button>
			</section>

			<section class="glass-panel card">
				<div class="card-head">
					<h2>Evaluate / Canary / Promote</h2>
					<button
						type="button"
						class="info-btn"
						onclick={() => toggleHelp('evaluatePromote')}
						aria-label="Explain Evaluate, Canary and Promote card"
						aria-expanded={activeHelpCard === 'evaluatePromote'}
					>
						i
					</button>
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

			<section class="glass-panel card">
				<div class="card-head">
					<h2>Pipeline Status</h2>
					<button
						type="button"
						class="info-btn"
						onclick={() => toggleHelp('pipelineStatus')}
						aria-label="Explain Pipeline Status card"
						aria-expanded={activeHelpCard === 'pipelineStatus'}
					>
						i
					</button>
				</div>
				<pre>{getPretty(status)}</pre>
			</section>

			<section class="glass-panel card">
				<div class="card-head">
					<h2>Queue Status</h2>
					<button
						type="button"
						class="info-btn"
						onclick={() => toggleHelp('queueStatus')}
						aria-label="Explain Queue Status card"
						aria-expanded={activeHelpCard === 'queueStatus'}
					>
						i
					</button>
				</div>
				<pre>{getPretty(queueStatus)}</pre>
			</section>

			<section class="glass-panel card">
				<div class="card-head">
					<h2>Live Metrics</h2>
					<button
						type="button"
						class="info-btn"
						onclick={() => toggleHelp('liveMetrics')}
						aria-label="Explain Live Metrics card"
						aria-expanded={activeHelpCard === 'liveMetrics'}
					>
						i
					</button>
				</div>
				<pre>{getPretty(liveMetrics)}</pre>
			</section>

			<section class="glass-panel card">
				<div class="card-head">
					<h2>Recent Model Versions</h2>
					<button
						type="button"
						class="info-btn"
						onclick={() => toggleHelp('modelVersions')}
						aria-label="Explain Recent Model Versions card"
						aria-expanded={activeHelpCard === 'modelVersions'}
					>
						i
					</button>
				</div>
				<pre>{getPretty(versions.slice(0, 10))}</pre>
			</section>

			<section class="glass-panel card">
				<div class="card-head">
					<h2>Recent Jobs</h2>
					<button
						type="button"
						class="info-btn"
						onclick={() => toggleHelp('recentJobs')}
						aria-label="Explain Recent Jobs card"
						aria-expanded={activeHelpCard === 'recentJobs'}
					>
						i
					</button>
				</div>
				<pre>{getPretty(jobs.slice(0, 10))}</pre>
			</section>

			<section class="glass-panel card">
				<div class="card-head">
					<h2>Recent Datasets</h2>
					<button
						type="button"
						class="info-btn"
						onclick={() => toggleHelp('recentDatasets')}
						aria-label="Explain Recent Datasets card"
						aria-expanded={activeHelpCard === 'recentDatasets'}
					>
						i
					</button>
				</div>
				<pre>{getPretty(datasets.slice(0, 10))}</pre>
			</section>
		</div>
	{/if}

	{#if error}
		<div class="glass-panel error">{error}</div>
	{/if}
	{#if operationResult}
		<div class="glass-panel result">
			<h2>Last Operation Result</h2>
			<pre>{getPretty(operationResult)}</pre>
		</div>
	{/if}

	{#if activeHelpCard && getActiveHelp()}
		<button
			type="button"
			class="help-backdrop"
			onclick={closeHelp}
			aria-label="Close help window"
		></button>
		<div class="help-modal" role="dialog" aria-modal="true" aria-label="Card help details">
			<div class="help-modal-head">
				<h3>{getActiveHelp()?.title}</h3>
				<button type="button" class="help-close" onclick={closeHelp} aria-label="Close help">×</button>
			</div>
			<p>{getActiveHelp()?.description}</p>
			{#each getActiveHelp()?.fields ?? [] as field}
				<div class="help-field">
					<strong>{field.name}</strong>
					<p><span>Meaning:</span> {field.meaning}</p>
					<p><span>Impact:</span> {field.impact}</p>
				</div>
			{/each}
		</div>
	{/if}
</div>

<style>
	.ops-page {
		padding: 1.25rem;
		display: flex;
		flex-direction: column;
		gap: 1.1rem;
		color: rgba(255, 255, 255, 0.95);
	}

	.hero {
		padding: 1rem 1.1rem;
	}

	.hero h1 {
		margin: 0;
		font-size: 1.7rem;
		font-weight: 700;
		letter-spacing: 0.01em;
		text-shadow: 0 1px 10px rgba(0, 0, 0, 0.35);
	}

	.hero p {
		margin: 0.25rem 0;
		font-size: 1.03rem;
		line-height: 1.4;
	}

	.muted {
		opacity: 0.82;
		font-size: 0.96rem;
	}

	.grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
		gap: 1.1rem;
	}

	.card {
		display: flex;
		flex-direction: column;
		gap: 0.95rem;
		min-height: 220px;
		padding: 1.05rem 1.1rem;
	}

	.card h2 {
		margin: 0 0 0.2rem;
		font-size: 1.22rem;
		font-weight: 650;
		letter-spacing: 0.01em;
		color: rgba(255, 255, 255, 0.96);
	}

	.card-head {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 0.7rem;
	}

	button.info-btn {
		margin-top: 0 !important;
		width: 2.1rem !important;
		height: 2.1rem !important;
		min-width: 2.1rem !important;
		max-width: 2.1rem !important;
		min-height: 2.1rem !important;
		max-height: 2.1rem !important;
		aspect-ratio: 1 / 1 !important;
		padding: 0 !important;
		border-radius: 50% !important;
		font-size: 0.9rem;
		font-weight: 700;
		line-height: 1;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		text-transform: lowercase;
		flex-shrink: 0;
	}

	.help-modal {
		position: fixed;
		top: 50%;
		left: 50%;
		transform: translate(-50%, -50%);
		z-index: 45;
		width: min(720px, calc(100vw - 2rem));
		max-height: min(80vh, 760px);
		overflow: auto;
		border: 1px solid var(--theme-modal-border);
		background: var(--theme-modal-surface);
		backdrop-filter: var(--theme-modal-backdrop-blur);
		-webkit-backdrop-filter: var(--theme-modal-backdrop-blur);
		border-radius: 0.85rem;
		padding: 0.95rem 1rem;
		display: flex;
		flex-direction: column;
		gap: 0.62rem;
		box-shadow: var(--theme-modal-shadow);
	}

	.help-modal-head {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
	}

	.help-modal h3 {
		margin: 0;
		font-size: 1.04rem;
		font-weight: 650;
	}

	.help-close {
		margin-top: 0 !important;
		width: 2.1rem !important;
		height: 2.1rem !important;
		min-width: 2.1rem !important;
		max-width: 2.1rem !important;
		min-height: 2.1rem !important;
		max-height: 2.1rem !important;
		aspect-ratio: 1 / 1 !important;
		padding: 0 !important;
		border-radius: 50% !important;
		font-size: 1.15rem;
		line-height: 1;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		flex-shrink: 0;
	}

	.help-modal > p {
		margin: 0;
		font-size: 0.86rem;
		line-height: 1.35;
		opacity: 0.95;
	}

	.help-field {
		padding-top: 0.45rem;
		border-top: 1px solid rgba(255, 255, 255, 0.1);
	}

	.help-field strong {
		display: block;
		font-size: 0.9rem;
		margin-bottom: 0.22rem;
	}

	.help-field p {
		margin: 0.1rem 0;
		font-size: 0.82rem;
		line-height: 1.34;
		color: rgba(238, 245, 255, 0.95);
	}

	.help-field span {
		font-weight: 650;
	}

	.help-backdrop {
		position: fixed;
		inset: 0;
		z-index: 40;
		border: 0;
		margin: 0;
		padding: 0;
		background: var(--theme-modal-backdrop);
		backdrop-filter: var(--theme-modal-backdrop-blur);
		-webkit-backdrop-filter: var(--theme-modal-backdrop-blur);
		cursor: default;
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
		opacity: 0.93;
		font-size: 1rem;
		font-weight: 560;
	}

	.row input,
	.row select {
		width: 100%;
		padding: 0.72rem 0.78rem;
		border-radius: 0.6rem;
		border: 1px solid rgba(255, 255, 255, 0.26);
		background: rgba(255, 255, 255, 0.11);
		color: rgba(255, 255, 255, 0.97);
		font-size: 1.04rem;
		font-weight: 520;
		outline: none;
	}

	.row input::placeholder {
		color: rgba(220, 230, 245, 0.65);
	}

	.row input:focus,
	.row select:focus {
		border-color: rgba(var(--theme-primary-rgb), 0.8);
		box-shadow: 0 0 0 3px rgba(var(--theme-primary-rgb), 0.2);
	}

	.row select option {
		background: #1a2433;
		color: #f2f6ff;
	}

	button {
		margin-top: 0.2rem;
		padding: 0.76rem 1rem;
		border-radius: 0.6rem;
		border: 1px solid rgba(var(--theme-primary-rgb), 0.68);
		background: linear-gradient(
			180deg,
			rgba(var(--theme-primary-rgb), 0.52) 0%,
			rgba(var(--theme-primary-rgb), 0.36) 100%
		);
		color: #ffffff;
		font-size: 1.05rem;
		font-weight: 640;
		letter-spacing: 0.01em;
		text-shadow: 0 1px 6px rgba(0, 0, 0, 0.45);
		cursor: pointer;
		transition: transform 100ms ease, filter 120ms ease, box-shadow 120ms ease;
	}

	button:hover:not(:disabled) {
		filter: brightness(1.08);
		transform: translateY(-1px);
		box-shadow: 0 6px 18px rgba(0, 0, 0, 0.25);
	}

	button:active:not(:disabled) {
		transform: translateY(0);
	}

	button:focus-visible {
		outline: 2px solid rgba(255, 255, 255, 0.95);
		outline-offset: 2px;
	}

	button:disabled {
		opacity: 0.48;
		cursor: not-allowed;
		transform: none;
		box-shadow: none;
	}

	button.danger {
		border-color: rgba(255, 130, 130, 0.75);
		background: linear-gradient(180deg, rgba(210, 70, 70, 0.74) 0%, rgba(140, 35, 35, 0.82) 100%);
	}

	.button-row {
		display: flex;
		gap: 0.65rem;
		flex-wrap: wrap;
		margin-top: 0.2rem;
	}

	.button-row button {
		min-width: 100px;
	}

	pre {
		margin: 0.1rem 0 0;
		max-height: 240px;
		overflow: auto;
		font-size: 0.8rem;
		line-height: 1.4;
		padding: 0.72rem;
		border-radius: 0.6rem;
		background: rgba(0, 0, 0, 0.28);
		color: rgba(232, 242, 255, 0.96);
		border: 1px solid rgba(255, 255, 255, 0.12);
	}

	.error {
		border: 1px solid rgba(255, 99, 99, 0.35);
	}

	@media (max-width: 640px) {
		.ops-page {
			padding: 0.9rem;
			gap: 0.9rem;
		}

		.hero,
		.card {
			padding: 0.85rem 0.9rem;
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

		.help-modal {
			width: calc(100vw - 1.1rem);
			padding: 0.82rem 0.85rem;
		}

		button.info-btn {
			width: 2.1rem !important;
			height: 2.1rem !important;
			min-width: 2.1rem !important;
			max-width: 2.1rem !important;
			min-height: 2.1rem !important;
			max-height: 2.1rem !important;
			padding: 0 !important;
		}

		.help-close {
			width: 2.1rem !important;
			height: 2.1rem !important;
			min-width: 2.1rem !important;
			max-width: 2.1rem !important;
			min-height: 2.1rem !important;
			max-height: 2.1rem !important;
			padding: 0 !important;
		}
	}
</style>
