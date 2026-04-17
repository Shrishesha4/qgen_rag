<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { session } from '$lib/session';
	import ThemeSelector from '$lib/components/ThemeSelector.svelte';
	import {
		listModelVersions,
		listEvaluations,
		getTrainingStatus,
		getTrainingDataSummary,
		listTrainingPairs,
		type ModelVersionResponse,
		type EvaluationResponse,
		type TrainingStatus,
		type TrainingDataSummary,
		type TrainingPairsListResponse,
	} from '$lib/api/training';

	// ── State ──
	let loading = $state(true);
	let error = $state('');
	let versions = $state<ModelVersionResponse[]>([]);
	let evaluations = $state<EvaluationResponse[]>([]);
	let trainingStatus = $state<TrainingStatus | null>(null);
	let dataSummary = $state<TrainingDataSummary | null>(null);
	let pairsData = $state<TrainingPairsListResponse | null>(null);

	// Comparison state
	let selectedVersionA = $state<string>('');
	let selectedVersionB = $state<string>('');
	let activeTab = $state<'overview' | 'compare' | 'pairs'>('overview');

	// ── Derived ──
	let activeVersion = $derived(versions.find(v => v.is_active));
	let nonActiveVersions = $derived(versions.filter(v => !v.is_active));
	let versionA = $derived(versions.find(v => v.id === selectedVersionA));
	let versionB = $derived(versions.find(v => v.id === selectedVersionB));
	let evalsForA = $derived(evaluations.filter(e => e.model_version_id === selectedVersionA));
	let evalsForB = $derived(evaluations.filter(e => e.model_version_id === selectedVersionB));
	let latestEvalA = $derived(evalsForA.length > 0 ? evalsForA[0] : null);
	let latestEvalB = $derived(evalsForB.length > 0 ? evalsForB[0] : null);

	onMount(() => {
		const unsub = session.subscribe((s) => {
			if (!s || s.user.role !== 'teacher') goto('/teacher/login');
		});
		loadData();
		return unsub;
	});

	async function loadData() {
		loading = true;
		error = '';
		try {
			const [v, e, s] = await Promise.all([
				listModelVersions(),
				listEvaluations().catch(() => []),
				getTrainingStatus().catch(() => null),
			]);
			versions = v;
			evaluations = e;
			trainingStatus = s;

			// Auto-select: finetuned model (A) vs current generation model (B)
			if (versions.length > 0) {
				const active = versions.find(x => x.is_active);
				const trained = versions
					.filter(x => x.status === 'trained')
					.sort((a, b) => (b.training_completed_at ?? '').localeCompare(a.training_completed_at ?? ''));
				const latestFinetuned = trained.find(x => !x.is_active) ?? trained[0];

				if (latestFinetuned && active && latestFinetuned.id !== active.id) {
					selectedVersionA = latestFinetuned.id;
					selectedVersionB = active.id;
				} else if (trained.length >= 2) {
					selectedVersionA = trained[0].id;
					selectedVersionB = trained[1].id;
				} else if (active) {
					selectedVersionB = active.id;
					const other = versions.find(x => x.id !== active.id);
					if (other) selectedVersionA = other.id;
				} else if (versions.length >= 2) {
					selectedVersionA = versions[0].id;
					selectedVersionB = versions[1].id;
				}
			}

			// Load additional data in background
			Promise.all([
				getTrainingDataSummary().catch(() => null),
				listTrainingPairs({ limit: 10 }).catch(() => null),
			]).then(([ds, pd]) => {
				dataSummary = ds;
				pairsData = pd;
			});
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to load data';
		} finally {
			loading = false;
		}
	}

	function formatDate(iso: string | null): string {
		if (!iso) return '—';
		const normalized = /[Zz]$|[+-]\d{2}:\d{2}$/.test(iso) ? iso : iso + 'Z';
		return new Date(normalized).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
	}

	function formatMetric(val: unknown): string {
		if (val == null) return '—';
		if (typeof val === 'number') return val >= 1 ? String(val) : `${(val * 100).toFixed(1)}%`;
		return String(val);
	}

	function statusBadgeClass(status: string): string {
		switch (status) {
			case 'trained': case 'completed': case 'active': case 'passed': return 'badge-success';
			case 'training': case 'pending': case 'running': case 'evaluating': return 'badge-info';
			case 'failed': case 'error': case 'rejected': return 'badge-error';
			default: return 'badge-default';
		}
	}

	function getMetricKeys(evalA: EvaluationResponse | null, evalB: EvaluationResponse | null): string[] {
		const keys = new Set<string>();
		if (evalA?.metrics) Object.keys(evalA.metrics).forEach(k => keys.add(k));
		if (evalB?.metrics) Object.keys(evalB.metrics).forEach(k => keys.add(k));
		return [...keys].sort();
	}

	function metricLabel(key: string): string {
		return key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
	}

	function isBetterMetric(key: string, valA: unknown, valB: unknown): 'a' | 'b' | 'tie' {
		const a = typeof valA === 'number' ? valA : NaN;
		const b = typeof valB === 'number' ? valB : NaN;
		if (isNaN(a) && isNaN(b)) return 'tie';
		if (isNaN(a)) return 'b';
		if (isNaN(b)) return 'a';
		// Higher is better for most metrics, lower for loss/reject/similarity
		const lowerIsBetter = /loss|reject|similarity|error/.test(key);
		if (Math.abs(a - b) < 0.001) return 'tie';
		if (lowerIsBetter) return a < b ? 'a' : 'b';
		return a > b ? 'a' : 'b';
	}
</script>

<svelte:head>
	<title>A/B Testing — VQuest Trainer</title>
</svelte:head>

<ThemeSelector />

<div class="ab-page">
	<header class="ab-header animate-fade-in">
		<button class="back-btn glass-btn" onclick={() => goto('/teacher/dashboard')}>← Back</button>
		<div class="ab-header-text">
			<h1 class="ab-title font-serif">A/B Model Testing</h1>
			<p class="ab-subtitle">Compare model versions and review finetuned output quality</p>
		</div>
	</header>

	<!-- Tab bar -->
	<nav class="ab-tabs animate-fade-in">
		<button class="ab-tab" class:active={activeTab === 'overview'} onclick={() => activeTab = 'overview'}>
			Overview
		</button>
		<button class="ab-tab" class:active={activeTab === 'compare'} onclick={() => activeTab = 'compare'}>
			Compare Models
		</button>
		<button class="ab-tab" class:active={activeTab === 'pairs'} onclick={() => activeTab = 'pairs'}>
			DPO Pairs
		</button>
	</nav>

	{#if loading}
		<div class="center-state animate-fade-in">
			<div class="loading-spinner"></div>
			<p class="loading-text">Loading model data...</p>
		</div>
	{:else if error}
		<div class="center-state animate-fade-in">
			<span class="err-icon">⚠️</span>
			<p class="err-msg">{error}</p>
			<button class="glass-btn" onclick={loadData}>Retry</button>
		</div>
	{:else if activeTab === 'overview'}
		<!-- Overview Tab -->
		<div class="ab-content animate-slide-up">
			<!-- Active Model Card -->
			{#if activeVersion}
				<div class="model-hero glass-panel">
					<div class="model-hero-badge">ACTIVE MODEL</div>
					<h2 class="model-hero-name">{activeVersion.version_tag}</h2>
					<div class="model-hero-meta">
						<span class="meta-chip">{activeVersion.base_model}</span>
						<span class="meta-chip">{activeVersion.training_method.toUpperCase()}</span>
						<span class="meta-chip">{activeVersion.sft_samples_count} SFT samples</span>
						{#if activeVersion.training_pairs_count > 0}
							<span class="meta-chip">{activeVersion.training_pairs_count} DPO pairs</span>
						{/if}
					</div>
					{#if activeVersion.eval_metrics}
						<div class="hero-metrics">
							{#each Object.entries(activeVersion.eval_metrics).slice(0, 6) as [key, val]}
								<div class="hero-metric">
									<span class="hero-metric-label">{metricLabel(key)}</span>
									<span class="hero-metric-value">{formatMetric(val)}</span>
								</div>
							{/each}
						</div>
					{/if}
				</div>
			{:else}
				<div class="center-state glass-panel">
					<p>No active model version found. Train your first model to get started.</p>
				</div>
			{/if}

			<!-- Stats Grid -->
			<div class="stats-grid">
				<div class="stat-card glass-panel">
					<span class="stat-value">{versions.length}</span>
					<span class="stat-label">Model Versions</span>
				</div>
				<div class="stat-card glass-panel">
					<span class="stat-value">{evaluations.length}</span>
					<span class="stat-label">Evaluations</span>
				</div>
				<div class="stat-card glass-panel">
					<span class="stat-value">{dataSummary?.approved_questions ?? '—'}</span>
					<span class="stat-label">Approved Questions</span>
				</div>
				<div class="stat-card glass-panel">
					<span class="stat-value">{dataSummary?.dpo_pairs ?? '—'}</span>
					<span class="stat-label">DPO Pairs</span>
				</div>
			</div>

			<!-- Version List -->
			{#if versions.length > 0}
				<h3 class="section-title">All Model Versions</h3>
				<div class="version-list">
					{#each versions as v}
						<div class="version-row glass-panel" class:active-row={v.is_active}>
							<div class="version-info">
								<div class="version-name-row">
									<span class="version-name">{v.version_tag}</span>
									{#if v.is_active}<span class="badge badge-success">Active</span>{/if}
									<span class="badge {statusBadgeClass(v.status)}">{v.status}</span>
								</div>
								<div class="version-meta">
									<span>{v.base_model}</span>
									<span>•</span>
									<span>{v.training_method}</span>
									<span>•</span>
									<span>{v.sft_samples_count} SFT</span>
									<span>•</span>
									<span>Created {formatDate(v.created_at)}</span>
								</div>
							</div>
							<button
								class="glass-btn compare-btn"
								onclick={() => {
									if (activeVersion) selectedVersionA = activeVersion.id;
									selectedVersionB = v.id;
									activeTab = 'compare';
								}}
							>
								Compare
							</button>
						</div>
					{/each}
				</div>
			{/if}

			<!-- Training Readiness -->
			{#if dataSummary}
				<h3 class="section-title">Training Data Readiness</h3>
				<div class="readiness-card glass-panel">
					<div class="readiness-grid">
						<div class="readiness-item">
							<span class="readiness-label">SFT Ready</span>
							<span class="readiness-value" class:ready={dataSummary.sft_ready}>{dataSummary.sft_ready ? '✓ Yes' : '✗ No'}</span>
						</div>
						<div class="readiness-item">
							<span class="readiness-label">DPO Ready</span>
							<span class="readiness-value" class:ready={dataSummary.dpo_ready}>{dataSummary.dpo_ready ? '✓ Yes' : '✗ No'}</span>
						</div>
						<div class="readiness-item">
							<span class="readiness-label">Total Questions</span>
							<span class="readiness-value">{dataSummary.total_questions}</span>
						</div>
						<div class="readiness-item">
							<span class="readiness-label">Subjects</span>
							<span class="readiness-value">{dataSummary.subjects}</span>
						</div>
					</div>
					{#if Object.keys(dataSummary.bloom_distribution).length > 0}
						<div class="dist-section">
							<span class="dist-title">Bloom's Taxonomy Distribution</span>
							<div class="dist-bars">
								{#each Object.entries(dataSummary.bloom_distribution) as [level, count]}
									<div class="dist-bar-row">
										<span class="dist-bar-label">{level}</span>
										<div class="dist-bar-track">
											<div class="dist-bar-fill" style="width: {Math.min(100, (count / Math.max(1, dataSummary.total_questions)) * 100)}%"></div>
										</div>
										<span class="dist-bar-count">{count}</span>
									</div>
								{/each}
							</div>
						</div>
					{/if}
				</div>
			{/if}
		</div>

	{:else if activeTab === 'compare'}
		<!-- Compare Tab -->
		<div class="ab-content animate-slide-up">
			<div class="compare-selectors">
				<div class="compare-selector">
					<label class="compare-label" for="compare-select-a">Model A</label>
					<select id="compare-select-a" class="glass-input compare-select" bind:value={selectedVersionA}>
						<option value="">Select a version…</option>
						{#each versions as v}
							<option value={v.id}>{v.version_tag}{v.is_active ? ' (active)' : ''}</option>
						{/each}
					</select>
				</div>
				<span class="compare-vs">VS</span>
				<div class="compare-selector">
					<label class="compare-label" for="compare-select-b">Model B</label>
					<select id="compare-select-b" class="glass-input compare-select" bind:value={selectedVersionB}>
						<option value="">Select a version…</option>
						{#each versions as v}
							<option value={v.id}>{v.version_tag}{v.is_active ? ' (active)' : ''}</option>
						{/each}
					</select>
				</div>
			</div>

			{#if versionA && versionB}
				<!-- Side-by-side comparison -->
				<div class="compare-grid">
					<!-- Version info -->
					<div class="compare-card glass-panel">
						<div class="compare-card-header">
							<span class="compare-tag tag-a">A</span>
							<h3 class="compare-card-title">{versionA.version_tag}</h3>
						</div>
						<div class="compare-details">
							<div class="detail-row"><span class="detail-label">Base Model</span><span class="detail-value">{versionA.base_model}</span></div>
							<div class="detail-row"><span class="detail-label">Method</span><span class="detail-value">{versionA.training_method}</span></div>
							<div class="detail-row"><span class="detail-label">SFT Samples</span><span class="detail-value">{versionA.sft_samples_count}</span></div>
							<div class="detail-row"><span class="detail-label">DPO Pairs</span><span class="detail-value">{versionA.training_pairs_count}</span></div>
							<div class="detail-row"><span class="detail-label">Status</span><span class="badge {statusBadgeClass(versionA.status)}">{versionA.status}</span></div>
							<div class="detail-row"><span class="detail-label">Trained</span><span class="detail-value">{formatDate(versionA.training_completed_at)}</span></div>
						</div>
					</div>
					<div class="compare-card glass-panel">
						<div class="compare-card-header">
							<span class="compare-tag tag-b">B</span>
							<h3 class="compare-card-title">{versionB.version_tag}</h3>
						</div>
						<div class="compare-details">
							<div class="detail-row"><span class="detail-label">Base Model</span><span class="detail-value">{versionB.base_model}</span></div>
							<div class="detail-row"><span class="detail-label">Method</span><span class="detail-value">{versionB.training_method}</span></div>
							<div class="detail-row"><span class="detail-label">SFT Samples</span><span class="detail-value">{versionB.sft_samples_count}</span></div>
							<div class="detail-row"><span class="detail-label">DPO Pairs</span><span class="detail-value">{versionB.training_pairs_count}</span></div>
							<div class="detail-row"><span class="detail-label">Status</span><span class="badge {statusBadgeClass(versionB.status)}">{versionB.status}</span></div>
							<div class="detail-row"><span class="detail-label">Trained</span><span class="detail-value">{formatDate(versionB.training_completed_at)}</span></div>
						</div>
					</div>
				</div>

				<!-- Metrics comparison -->
				{#if latestEvalA || latestEvalB}
					<h3 class="section-title">Evaluation Metrics</h3>
					<div class="metrics-table glass-panel">
						<div class="metrics-header">
							<span class="metrics-col-label">Metric</span>
							<span class="metrics-col-a">Model A</span>
							<span class="metrics-col-b">Model B</span>
						</div>
						{#each getMetricKeys(latestEvalA, latestEvalB) as key}
							{@const valA = latestEvalA?.metrics?.[key]}
							{@const valB = latestEvalB?.metrics?.[key]}
							{@const winner = isBetterMetric(key, valA, valB)}
							<div class="metrics-row">
								<span class="metrics-col-label">{metricLabel(key)}</span>
								<span class="metrics-col-a" class:winner={winner === 'a'}>{formatMetric(valA)}</span>
								<span class="metrics-col-b" class:winner={winner === 'b'}>{formatMetric(valB)}</span>
							</div>
						{/each}
					</div>
				{:else}
					<div class="center-state glass-panel" style="margin-top: 1rem;">
						<p>No evaluations found for the selected models. Run an evaluation first.</p>
					</div>
				{/if}

				<!-- Gate checks comparison -->
				{#if latestEvalA?.gate_checks || latestEvalB?.gate_checks}
					<h3 class="section-title">Quality Gates</h3>
					<div class="compare-grid">
						<div class="gates-card glass-panel">
							<span class="compare-tag tag-a">A</span>
							{#if latestEvalA?.gate_checks}
								{#each Object.entries(latestEvalA.gate_checks) as [gate, result]}
									<div class="gate-row">
										<span class="gate-icon">{typeof result === 'object' && result && 'passed' in result && (result as Record<string, unknown>).passed ? '✓' : '✗'}</span>
										<span class="gate-name">{metricLabel(gate)}</span>
									</div>
								{/each}
							{:else}
								<p class="no-data">No gate checks</p>
							{/if}
						</div>
						<div class="gates-card glass-panel">
							<span class="compare-tag tag-b">B</span>
							{#if latestEvalB?.gate_checks}
								{#each Object.entries(latestEvalB.gate_checks) as [gate, result]}
									<div class="gate-row">
										<span class="gate-icon">{typeof result === 'object' && result && 'passed' in result && (result as Record<string, unknown>).passed ? '✓' : '✗'}</span>
										<span class="gate-name">{metricLabel(gate)}</span>
									</div>
								{/each}
							{:else}
								<p class="no-data">No gate checks</p>
							{/if}
						</div>
					</div>
				{/if}
			{:else if selectedVersionA || selectedVersionB}
				<div class="center-state glass-panel" style="margin-top: 1rem;">
					<p>Select two model versions to compare.</p>
				</div>
			{:else}
				<div class="center-state glass-panel" style="margin-top: 1rem;">
					<p>Select two model versions above to start comparing.</p>
				</div>
			{/if}
		</div>

	{:else if activeTab === 'pairs'}
		<!-- DPO Pairs Tab -->
		<div class="ab-content animate-slide-up">
			{#if pairsData && pairsData.pairs.length > 0}
				<div class="pairs-header">
					<h3 class="section-title">Recent DPO Training Pairs</h3>
					<span class="pairs-total">{pairsData.total} total</span>
				</div>
				<div class="pairs-list">
					{#each pairsData.pairs as pair}
						<div class="pair-card glass-panel">
							<div class="pair-header">
								<span class="badge {statusBadgeClass(pair.status)}">{pair.status}</span>
								<span class="pair-type">{pair.pair_type}</span>
								{#if pair.confidence != null}
									<span class="pair-confidence">{(pair.confidence * 100).toFixed(0)}% conf</span>
								{/if}
								<span class="pair-date">{formatDate(pair.created_at)}</span>
							</div>
							<div class="pair-content">
								<div class="pair-prompt">
									<span class="pair-label">Prompt</span>
									<p class="pair-text">{pair.prompt}</p>
								</div>
								<div class="pair-responses">
									<div class="pair-chosen">
										<span class="pair-label chosen-label">✓ Chosen</span>
										<p class="pair-text">{pair.chosen_response}</p>
									</div>
									<div class="pair-rejected">
										<span class="pair-label rejected-label">✗ Rejected</span>
										<p class="pair-text">{pair.rejected_response}</p>
									</div>
								</div>
							</div>
						</div>
					{/each}
				</div>
			{:else}
				<div class="center-state glass-panel">
					<span style="font-size: 2rem;">📊</span>
					<p>No DPO training pairs yet.</p>
					<p class="sub-text">DPO pairs are created when you reject questions with feedback during vetting.</p>
				</div>
			{/if}
		</div>
	{/if}
</div>

<style>
	.ab-page {
		max-width: 960px;
		margin: 0 auto;
		padding: 2rem 1.5rem 4rem;
		display: flex;
		flex-direction: column;
		gap: 1.25rem;
	}

	.ab-header {
		display: flex;
		align-items: center;
		gap: 1rem;
	}

	.back-btn {
		padding: 0.5rem 0.85rem;
		font-size: 0.85rem;
		flex-shrink: 0;
	}

	.ab-header-text {
		flex: 1;
	}

	.ab-title {
		font-size: 1.65rem;
		font-weight: 800;
		margin: 0;
		letter-spacing: -0.02em;
	}

	.ab-subtitle {
		font-size: 0.9rem;
		color: var(--theme-text-muted);
		margin: 0.2rem 0 0;
	}

	/* Tabs */
	.ab-tabs {
		display: flex;
		gap: 0;
		border-bottom: 1px solid var(--theme-glass-border);
	}

	.ab-tab {
		flex: 1;
		padding: 0.7rem 1rem;
		background: none;
		border: none;
		border-bottom: 2px solid transparent;
		color: var(--theme-text-muted);
		font-size: 0.9rem;
		font-weight: 600;
		cursor: pointer;
		transition: color 0.15s, border-color 0.15s, background 0.15s;
		font-family: inherit;
	}

	.ab-tab:hover { color: var(--theme-text); }
	.ab-tab.active {
		background: color-mix(in srgb, var(--theme-input-bg) 72%, rgba(var(--theme-primary-rgb), 0.22));
		color: var(--theme-primary);
		border-bottom-color: var(--theme-primary);
	}

	:global([data-color-mode='dark']) .ab-tab.active {
		box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.1);
	}

	/* Content */
	.ab-content {
		display: flex;
		flex-direction: column;
		gap: 1.25rem;
	}

	/* Center state */
	.center-state {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 0.75rem;
		padding: 3rem 1.5rem;
		text-align: center;
		color: var(--theme-text-muted);
	}

	.loading-spinner {
		width: 32px;
		height: 32px;
		border: 3px solid rgba(255, 255, 255, 0.1);
		border-top-color: var(--theme-primary);
		border-radius: 50%;
		animation: spin 0.8s linear infinite;
	}

	@keyframes spin { to { transform: rotate(360deg); } }

	.err-icon { font-size: 2rem; }
	.err-msg { color: #f07888; font-size: 0.95rem; }

	/* Hero model card */
	.model-hero {
		padding: 1.5rem;
		text-align: center;
		backdrop-filter: blur(18px) saturate(160%) brightness(1.08) !important;
		-webkit-backdrop-filter: blur(18px) saturate(160%) brightness(1.08) !important;
		background: linear-gradient(145deg, rgba(255,255,255,0.14) 0%, rgba(255,255,255,0.10) 50%, rgba(255,255,255,0.12) 100%) !important;
		box-shadow: 0 8px 40px rgba(0,0,0,0.18), inset 0 1px 2px rgba(255,255,255,0.45), inset 0 -1px 1px rgba(255,255,255,0.12), 0 0 0 1px rgba(255,255,255,0.22) !important;
	}

	.model-hero-badge {
		display: inline-block;
		font-size: 0.65rem;
		font-weight: 700;
		letter-spacing: 0.16em;
		text-transform: uppercase;
		padding: 0.2rem 0.65rem;
		border-radius: 12px;
		background: rgba(var(--theme-primary-rgb), 0.2);
		color: var(--theme-primary);
		margin-bottom: 0.5rem;
	}

	.model-hero-name {
		font-size: 1.4rem;
		font-weight: 800;
		margin: 0 0 0.5rem;
	}

	.model-hero-meta {
		display: flex;
		flex-wrap: wrap;
		gap: 0.35rem;
		justify-content: center;
		margin-bottom: 1rem;
	}

	.meta-chip {
		font-size: 0.75rem;
		padding: 0.2rem 0.55rem;
		border-radius: 8px;
		background: rgba(255, 255, 255, 0.08);
		color: var(--theme-text-muted);
	}

	.hero-metrics {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
		gap: 0.65rem;
		margin-top: 0.5rem;
	}

	.hero-metric {
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
		padding: 0.5rem;
		background: rgba(255, 255, 255, 0.05);
		border-radius: 8px;
	}

	.hero-metric-label {
		font-size: 0.7rem;
		color: var(--theme-text-muted);
		text-transform: uppercase;
		letter-spacing: 0.04em;
	}

	.hero-metric-value {
		font-size: 1rem;
		font-weight: 700;
		color: var(--theme-text);
	}

	/* Stats grid */
	.stats-grid {
		display: grid;
		grid-template-columns: repeat(4, 1fr);
		gap: 0.75rem;
	}

	.stat-card {
		padding: 1rem;
		text-align: center;
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}

	.stat-value {
		font-size: 1.5rem;
		font-weight: 800;
		color: var(--theme-text);
	}

	.stat-label {
		font-size: 0.75rem;
		color: var(--theme-text-muted);
		text-transform: uppercase;
		letter-spacing: 0.04em;
	}

	/* Section title */
	.section-title {
		font-size: 1rem;
		font-weight: 700;
		margin: 0.5rem 0 0;
		color: var(--theme-text);
	}

	/* Version list */
	.version-list {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.version-row {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 0.85rem 1rem;
		gap: 0.75rem;
	}

	.version-row.active-row {
		border: 1px solid rgba(var(--theme-primary-rgb), 0.3);
	}

	.version-info {
		flex: 1;
		min-width: 0;
	}

	.version-name-row {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		flex-wrap: wrap;
	}

	.version-name {
		font-weight: 700;
		font-size: 0.95rem;
	}

	.version-meta {
		display: flex;
		gap: 0.35rem;
		font-size: 0.75rem;
		color: var(--theme-text-muted);
		margin-top: 0.2rem;
		flex-wrap: wrap;
	}

	.compare-btn {
		padding: 0.4rem 0.85rem;
		font-size: 0.8rem;
		flex-shrink: 0;
	}

	/* Badges */
	.badge {
		display: inline-block;
		font-size: 0.65rem;
		font-weight: 700;
		padding: 0.15rem 0.45rem;
		border-radius: 6px;
		text-transform: uppercase;
		letter-spacing: 0.04em;
	}

	.badge-success { background: rgba(34, 197, 94, 0.15); color: #22c55e; }
	.badge-info { background: rgba(96, 165, 250, 0.15); color: #60a5fa; }
	.badge-error { background: rgba(239, 68, 68, 0.15); color: #ef4444; }
	.badge-default { background: rgba(255, 255, 255, 0.1); color: var(--theme-text-muted); }

	/* Readiness card */
	.readiness-card { padding: 1.25rem; }

	.readiness-grid {
		display: grid;
		grid-template-columns: repeat(4, 1fr);
		gap: 0.75rem;
		margin-bottom: 1rem;
	}

	.readiness-item {
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
	}

	.readiness-label {
		font-size: 0.75rem;
		color: var(--theme-text-muted);
		text-transform: uppercase;
		letter-spacing: 0.04em;
	}

	.readiness-value {
		font-size: 1rem;
		font-weight: 700;
		color: var(--theme-text);
	}

	.readiness-value.ready { color: #22c55e; }

	.dist-section { margin-top: 0.5rem; }

	.dist-title {
		font-size: 0.8rem;
		font-weight: 600;
		color: var(--theme-text-muted);
		display: block;
		margin-bottom: 0.5rem;
	}

	.dist-bars {
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
	}

	.dist-bar-row {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	.dist-bar-label {
		width: 100px;
		font-size: 0.75rem;
		color: var(--theme-text);
		text-transform: capitalize;
		flex-shrink: 0;
	}

	.dist-bar-track {
		flex: 1;
		height: 6px;
		border-radius: 3px;
		background: rgba(255, 255, 255, 0.08);
		overflow: hidden;
	}

	.dist-bar-fill {
		height: 100%;
		background: linear-gradient(90deg, var(--theme-primary), var(--theme-primary-hover));
		border-radius: 3px;
		transition: width 0.3s ease;
	}

	.dist-bar-count {
		width: 40px;
		text-align: right;
		font-size: 0.75rem;
		font-weight: 600;
		color: var(--theme-text-muted);
	}

	/* Compare tab */
	.compare-selectors {
		display: flex;
		align-items: flex-end;
		gap: 0.75rem;
	}

	.compare-selector {
		flex: 1;
		display: flex;
		flex-direction: column;
		gap: 0.3rem;
	}

	.compare-label {
		font-size: 0.75rem;
		font-weight: 600;
		color: var(--theme-text-muted);
		text-transform: uppercase;
		letter-spacing: 0.04em;
	}

	.compare-select {
		width: 100%;
		padding: 0.6rem 0.75rem;
		font-size: 0.85rem;
	}

	.compare-vs {
		font-size: 0.9rem;
		font-weight: 800;
		color: var(--theme-text-muted);
		padding-bottom: 0.6rem;
		flex-shrink: 0;
	}

	.compare-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 0.75rem;
	}

	.compare-card { padding: 1rem; }

	.compare-card-header {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-bottom: 0.85rem;
	}

	.compare-tag {
		width: 26px;
		height: 26px;
		border-radius: 50%;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		font-size: 0.75rem;
		font-weight: 800;
		flex-shrink: 0;
	}

	.tag-a { background: rgba(96, 165, 250, 0.2); color: #60a5fa; }
	.tag-b { background: rgba(251, 191, 36, 0.2); color: #fbbf24; }

	.compare-card-title {
		font-size: 1rem;
		font-weight: 700;
		margin: 0;
	}

	.compare-details {
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
	}

	.detail-row {
		display: flex;
		justify-content: space-between;
		align-items: center;
		font-size: 0.85rem;
	}

	.detail-label { color: var(--theme-text-muted); }
	.detail-value { font-weight: 600; color: var(--theme-text); }

	/* Metrics table */
	.metrics-table { padding: 0; overflow: hidden; }

	.metrics-header, .metrics-row {
		display: grid;
		grid-template-columns: 1fr 1fr 1fr;
		gap: 0;
	}

	.metrics-header {
		background: rgba(255, 255, 255, 0.06);
		border-bottom: 1px solid rgba(255, 255, 255, 0.08);
	}

	.metrics-header > span {
		padding: 0.65rem 0.85rem;
		font-size: 0.75rem;
		font-weight: 700;
		color: var(--theme-text-muted);
		text-transform: uppercase;
		letter-spacing: 0.04em;
	}

	.metrics-row {
		border-bottom: 1px solid rgba(255, 255, 255, 0.04);
	}

	.metrics-row:last-child { border-bottom: none; }

	.metrics-row > span {
		padding: 0.55rem 0.85rem;
		font-size: 0.85rem;
	}

	.metrics-col-label { color: var(--theme-text); font-weight: 500; }
	.metrics-col-a, .metrics-col-b { font-weight: 600; text-align: center; }
	.metrics-col-a.winner { color: #22c55e; }
	.metrics-col-b.winner { color: #22c55e; }

	/* Gates */
	.gates-card {
		padding: 1rem;
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
	}

	.gate-row {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		font-size: 0.85rem;
	}

	.gate-icon { font-size: 0.9rem; }
	.gate-name { color: var(--theme-text); }
	.no-data { color: var(--theme-text-muted); font-size: 0.85rem; margin: 0; }

	/* Pairs tab */
	.pairs-header {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
	}

	.pairs-total {
		font-size: 0.8rem;
		color: var(--theme-text-muted);
		font-weight: 600;
	}

	.pairs-list {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}

	.pair-card { padding: 1rem; }

	.pair-header {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-bottom: 0.75rem;
		flex-wrap: wrap;
	}

	.pair-type {
		font-size: 0.75rem;
		font-weight: 600;
		color: var(--theme-text-muted);
		text-transform: capitalize;
	}

	.pair-confidence {
		font-size: 0.75rem;
		color: var(--theme-text-muted);
	}

	.pair-date {
		font-size: 0.72rem;
		color: var(--theme-text-muted);
		margin-left: auto;
	}

	.pair-content {
		display: flex;
		flex-direction: column;
		gap: 0.65rem;
	}

	.pair-label {
		font-size: 0.7rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		color: var(--theme-text-muted);
		display: block;
		margin-bottom: 0.2rem;
	}

	.chosen-label { color: #22c55e; }
	.rejected-label { color: #ef4444; }

	.pair-text {
		font-size: 0.85rem;
		line-height: 1.45;
		color: var(--theme-text);
		margin: 0;
		white-space: pre-wrap;
		word-break: break-word;
	}

	.pair-prompt {
		padding: 0.65rem;
		background: rgba(255, 255, 255, 0.04);
		border-radius: 8px;
	}

	.pair-responses {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 0.5rem;
	}

	.pair-chosen, .pair-rejected {
		padding: 0.65rem;
		border-radius: 8px;
	}

	.pair-chosen {
		background: rgba(34, 197, 94, 0.06);
		border: 1px solid rgba(34, 197, 94, 0.15);
	}

	.pair-rejected {
		background: rgba(239, 68, 68, 0.06);
		border: 1px solid rgba(239, 68, 68, 0.15);
	}

	.sub-text {
		font-size: 0.85rem;
		color: var(--theme-text-muted);
	}

	/* Responsive */
	@media (max-width: 768px) {
		.stats-grid { grid-template-columns: repeat(2, 1fr); }
		.readiness-grid { grid-template-columns: repeat(2, 1fr); }
		.compare-grid { grid-template-columns: 1fr; }
		.compare-selectors { flex-direction: column; align-items: stretch; }
		.compare-vs { text-align: center; padding: 0; }
		.pair-responses { grid-template-columns: 1fr; }
	}

	@media (max-width: 480px) {
		.ab-page { padding: 1rem 0.85rem 3rem; }
		.ab-title { font-size: 1.3rem; }
		.stats-grid { grid-template-columns: repeat(2, 1fr); }
		.model-hero { padding: 1rem; }
		.hero-metrics { grid-template-columns: repeat(2, 1fr); }
	}
</style>
