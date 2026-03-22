<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { session, currentUser } from '$lib/session';
	import { getVetterDashboard, type VetterDashboard } from '$lib/api/vetting';
	import {
		hydrateVetterProgressStoreFromRemote,
		type VetterProgressSnapshot,
	} from '$lib/vetter-progress';

	let loading = $state(true);
	let stats = $state<VetterDashboard | null>(null);
	let latestResumeProgress = $state<VetterProgressSnapshot | null>(null);

	onMount(() => {
		const unsub = session.subscribe((s) => {
			if (!s || s.user.role !== 'vetter') {
				goto('/vetter/login');
			}
		});
		void loadDashboard();
		return unsub;
	});

	function toMillis(iso: string): number {
		const ts = Date.parse(iso);
		return Number.isFinite(ts) ? ts : 0;
	}

	function isProgressComplete(snapshot: VetterProgressSnapshot | null | undefined): boolean {
		if (!snapshot) return true;
		const total = snapshot.questions.length;
		if (total === 0) return true;
		const reviewed = snapshot.approvedQuestionIds.length + snapshot.rejectedQuestionIds.length;
		return reviewed >= total;
	}

	function resolveLatestProgress(
		store: Record<string, VetterProgressSnapshot>
	): VetterProgressSnapshot | null {
		const snapshots = Object.values(store).filter((snapshot) => !isProgressComplete(snapshot));
		if (snapshots.length === 0) return null;
		return snapshots.reduce((latest, candidate) =>
			toMillis(candidate.updatedAt) > toMillis(latest.updatedAt) ? candidate : latest
		);
	}

	function resumeProgress() {
		if (!latestResumeProgress) {
			startVetting();
			return;
		}
		const params = new URLSearchParams();
		if (latestResumeProgress.subjectId) params.set('subject', latestResumeProgress.subjectId);
		if (latestResumeProgress.topicId) params.set('topic', latestResumeProgress.topicId);
		params.set('resume', '1');
		params.set('resume_key', latestResumeProgress.key);
		goto(`/vetter/loop?${params.toString()}`);
	}

	async function loadDashboard() {
		await Promise.all([loadStats(), loadResumeProgress()]);
	}

	async function loadStats() {
		loading = true;
		try {
			stats = await getVetterDashboard();
		} catch {
			// silently fail — stats show '—'
		} finally {
			loading = false;
		}
	}

	async function loadResumeProgress() {
		try {
			const store = await hydrateVetterProgressStoreFromRemote();
			latestResumeProgress = resolveLatestProgress(store);
		} catch {
			latestResumeProgress = null;
		}
	}

	const resumeProgressLabel = $derived.by(() => {
		const snapshot = latestResumeProgress;
		if (!snapshot) return '';
		const total = snapshot.questions.length;
		if (total <= 0) return 'Saved progress';
		const current = Math.min(total, Math.max(1, snapshot.currentIndex + 1));
		return `${current}/${total} questions`;
	});

	const resumeSubjectLabel = $derived.by(() => {
		const snapshot = latestResumeProgress;
		if (!snapshot) return 'Saved vetting progress';
		return snapshot.questions[0]?.subject_name || 'Saved vetting progress';
	});

	function startVetting() {
		goto('/vetter/subjects');
	}
</script>

<svelte:head>
	<title>Vetter Dashboard — VQuest Trainer</title>
</svelte:head>

<div class="vetter-dash">
	<div class="hero animate-fade-in">
		<div class="hero-icon emerald">
			<img src="/logo.png" alt="VQuest logo" class="hero-logo-img" loading="eager" decoding="async" />
		</div>
		<h1 class="title font-serif">Vetter Dashboard</h1>
		{#if $currentUser}
			<p class="welcome">Welcome, {$currentUser.full_name || $currentUser.username}</p>
		{/if}
	</div>

	<div class="stats-row animate-slide-up">
		<div class="stat glass-panel">
			<span class="stat-value">{loading ? '…' : (stats?.total_pending ?? 0)}</span>
			<span class="stat-label">Pending</span>
		</div>
		<div class="stat glass-panel">
			<span class="stat-value">{loading ? '…' : (stats?.total_approved ?? 0)}</span>
			<span class="stat-label">Approved</span>
		</div>
		<div class="stat glass-panel">
			<span class="stat-value">{loading ? '…' : (stats?.total_rejected ?? 0)}</span>
			<span class="stat-label">Rejected</span>
		</div>
	</div>

	<div class="actions animate-slide-up">
		{#if latestResumeProgress}
			<button class="resume-card" onclick={resumeProgress}>
				<div class="resume-left">
					<span class="resume-kicker">Resumable Progress</span>
					<h2 class="resume-title">Resume Vetting</h2>
					<p class="resume-meta">{resumeSubjectLabel} • {resumeProgressLabel}</p>
				</div>
				<svg class="arrow" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
					<polyline points="9 18 15 12 9 6"></polyline>
				</svg>
			</button>
		{/if}

		<button class="action-card glass-panel" onclick={startVetting}>
			<div class="action-row">
				<div class="action-icon emerald">
					<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
						<path d="M9 11l3 3L22 4"></path>
						<path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"></path>
					</svg>
				</div>
				<div class="action-info">
					<h2 class="action-title">Start Vetting</h2>
					<p class="action-desc">Review the next batch of AI-generated questions</p>
				</div>
				<svg class="arrow" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
					<polyline points="9 18 15 12 9 6"></polyline>
				</svg>
			</div>
		</button>

	</div>
</div>

<style>
	.vetter-dash {
		display: flex;
		flex-direction: column;
		align-items: center;
		padding: 5rem 1.5rem 2rem;
		gap: 2rem;
		min-height: 100vh;
	}

	.hero {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.5rem;
		text-align: center;
	}

	.hero-icon {
		width: 56px;
		height: 56px;
		border-radius: 50%;
		display: flex;
		align-items: center;
		justify-content: center;
		margin-bottom: 0.25rem;
	}
	.hero-icon.emerald {
		background: rgba(16, 185, 129, 0.2);
		color: #10b981;
	}

	.hero-logo-img {
		width: 28px;
		height: 28px;
		object-fit: contain;
	}

	.title {
		font-size: 2rem;
		font-weight: 800;
		margin: 0;
		color: var(--theme-text);
	}

	.welcome {
		font-size: 0.95rem;
		color: var(--theme-text-muted);
		margin: 0;
	}

	.stats-row {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: 0.75rem;
		width: 100%;
		max-width: 400px;
	}

	.stat {
		display: flex;
		flex-direction: column;
		align-items: center;
		padding: 1rem;
		gap: 0.25rem;
		background: rgba(255, 255, 255, 0.86);
		border: 1px solid rgba(255, 255, 255, 0.95);
		box-shadow: 0 10px 28px rgba(15, 23, 42, 0.12);
	}

	.stat-value {
		font-size: 1.5rem;
		font-weight: 800;
		color: var(--theme-text);
	}

	.stat-label {
		font-size: 0.7rem;
		font-weight: 600;
		color: var(--theme-text-muted);
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}

	.actions {
		width: 100%;
		max-width: 400px;
	}

	.action-card {
		width: 100%;
		padding: 1.5rem;
		border-radius: 1rem;
		background: transparent;
		border: none;
		color: inherit;
		cursor: pointer;
		text-align: left;
		transition: transform 0.2s, box-shadow 0.2s;
		/* Enhanced blur effect - force override */
		backdrop-filter: blur(10px) saturate(150%) brightness(1.02) !important;
		-webkit-backdrop-filter: blur(10px) saturate(150%) brightness(1.02) !important;
		background: linear-gradient(
			145deg,
			rgba(255,255,255,0.95) 0%,
			rgba(255,255,255,0.9) 50%,
			rgba(255,255,255,0.94) 100%
		) !important;
		box-shadow:
			0 10px 28px rgba(15, 23, 42, 0.12),
			inset 0 1px 1px rgba(255, 255, 255, 0.65),
			inset 0 -1px 1px rgba(255, 255, 255, 0.35),
			0 0 0 1px rgba(255, 255, 255, 0.98) !important;
	}

	.action-card:hover {
		transform: translateY(-2px);
		background: linear-gradient(
			145deg,
			rgba(255,255,255,0.98) 0%,
			rgba(255,255,255,0.94) 50%,
			rgba(255,255,255,0.96) 100%
		) !important;
		box-shadow: 
			0 14px 30px rgba(15, 23, 42, 0.16),
			inset 0 1px 1px rgba(255, 255, 255, 0.72),
			inset 0 -1px 1px rgba(255, 255, 255, 0.4),
			0 0 0 1px rgba(255, 255, 255, 0.99) !important;
		/* Maintain blur on hover - force override */
		backdrop-filter: blur(10px) saturate(150%) brightness(1.02) !important;
		-webkit-backdrop-filter: blur(10px) saturate(150%) brightness(1.02) !important;
	}

	.resume-card {
		width: 100%;
		padding: 1.1rem 1.2rem;
		border-radius: 1rem;
		border: 1px solid rgba(255, 255, 255, 0.96);
		background: linear-gradient(145deg, rgba(255, 255, 255, 0.98), rgba(255, 255, 255, 0.92));
		box-shadow: 0 10px 28px rgba(15, 23, 42, 0.12);
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1rem;
		cursor: pointer;
		color: var(--theme-text);
		text-align: left;
		margin-bottom: 0.85rem;
	}

	.resume-left {
		display: flex;
		flex-direction: column;
		gap: 0.2rem;
	}

	.resume-kicker {
		font-size: 0.7rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: color-mix(in srgb, var(--theme-primary) 70%, #334155 30%);
	}

	.resume-title {
		margin: 0;
		font-size: 1.02rem;
		font-weight: 800;
		color: var(--theme-text);
	}

	.resume-meta {
		margin: 0;
		font-size: 0.82rem;
		color: var(--theme-text-muted);
	}

	:global([data-color-mode='dark']) .stat {
		background: rgba(20, 24, 31, 0.72);
		border-color: rgba(255, 255, 255, 0.14);
		box-shadow: 0 10px 28px rgba(0, 0, 0, 0.28);
	}

	:global([data-color-mode='dark']) .action-card {
		background: linear-gradient(145deg, rgba(255,255,255,0.03), rgba(255,255,255,0.02), rgba(255,255,255,0.025)) !important;
		box-shadow:
			0 8px 40px rgba(0, 0, 0, 0.25),
			inset 0 1px 1px rgba(255, 255, 255, 0.25),
			inset 0 -1px 1px rgba(255, 255, 255, 0.08),
			0 0 0 1px rgba(255, 255, 255, 0.12) !important;
	}

	:global([data-color-mode='dark']) .action-card:hover {
		background: linear-gradient(145deg, rgba(255,255,255,0.05), rgba(255,255,255,0.04), rgba(255,255,255,0.045)) !important;
		box-shadow:
			0 12px 40px rgba(0, 0, 0, 0.3),
			inset 0 1px 1px rgba(255, 255, 255, 0.3),
			inset 0 -1px 1px rgba(255, 255, 255, 0.12),
			0 0 0 1px rgba(255, 255, 255, 0.18) !important;
	}

	:global([data-color-mode='dark']) .resume-card {
		border-color: rgba(255, 255, 255, 0.14);
		background: linear-gradient(145deg, rgba(20, 24, 31, 0.84), rgba(20, 24, 31, 0.74));
		box-shadow: 0 12px 28px rgba(0, 0, 0, 0.3);
	}

	.action-row {
		display: flex;
		align-items: center;
		gap: 1rem;
		width: 100%;
	}

	.action-icon {
		width: 48px;
		height: 48px;
		border-radius: 50%;
		display: flex;
		align-items: center;
		justify-content: center;
		flex-shrink: 0;
	}
	.action-icon.emerald {
		background: rgba(16, 185, 129, 0.2);
		color: #10b981;
	}

	.action-info {
		flex: 1;
	}

	.action-title {
		font-size: 1.1rem;
		font-weight: 700;
		margin: 0 0 0.2rem;
	}

	.action-desc {
		font-size: 0.85rem;
		color: var(--theme-text-muted);
		margin: 0;
	}

	.arrow {
		opacity: 0.4;
		flex-shrink: 0;
	}

	@media (max-width: 768px) {
		.vetter-dash {
			padding: 4rem 1rem 1.5rem;
			gap: 1.5rem;
		}

		.hero-icon {
			width: 48px;
			height: 48px;
		}

		.hero-logo-img {
			width: 24px;
			height: 24px;
		}

		.title {
			font-size: 1.75rem;
		}

		.welcome {
			font-size: 0.88rem;
		}

		.stats-row {
			gap: 0.5rem;
			max-width: 100%;
		}

		.stat {
			padding: 0.85rem 0.5rem;
		}

		.stat-value {
			font-size: 1.3rem;
		}

		.stat-label {
			font-size: 0.65rem;
		}

		.actions {
			max-width: 100%;
		}

		.action-card {
			padding: 1.25rem;
		}

		.action-icon {
			width: 42px;
			height: 42px;
		}

		.action-title {
			font-size: 1rem;
		}

		.action-desc {
			font-size: 0.8rem;
		}
	}

	@media (max-width: 480px) {
		.vetter-dash {
			padding: 3.5rem 0.75rem 1.25rem;
			gap: 1.25rem;
		}

		.hero {
			gap: 0.35rem;
		}

		.hero-icon {
			width: 44px;
			height: 44px;
		}

		.hero-logo-img {
			width: 22px;
			height: 22px;
		}

		.title {
			font-size: 1.5rem;
		}

		.welcome {
			font-size: 0.82rem;
		}

		.stats-row {
			gap: 0.4rem;
		}

		.stat {
			padding: 0.75rem 0.4rem;
			border-radius: 0.75rem;
		}

		.stat-value {
			font-size: 1.15rem;
		}

		.stat-label {
			font-size: 0.6rem;
		}

		.action-card {
			padding: 1rem;
			border-radius: 0.85rem;
		}

		.action-row {
			gap: 0.75rem;
		}

		.action-icon {
			width: 38px;
			height: 38px;
		}

		.action-icon svg {
			width: 18px;
			height: 18px;
		}

		.action-title {
			font-size: 0.95rem;
		}

		.action-desc {
			font-size: 0.75rem;
			line-height: 1.35;
		}

	}
</style>
