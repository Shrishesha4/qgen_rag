<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { get } from 'svelte/store';
	import { goto } from '$app/navigation';
	import { session } from '$lib/session';
	import { apiFetch, apiUrl } from '$lib/api/client';

	interface ActiveUser {
		user_id: string;
		username: string;
		email: string;
		activity: string;
		subject_name: string | null;
		topic_name: string | null;
		started_at: string;
		duration_seconds: number;
	}

	interface GenerationWorkItem {
		run_id: string;
		subject_id: string;
		subject_name: string | null;
		topic_id: string | null;
		topic_name: string | null;
		topic_ids: string[];
		topic_names: string[];
		current_question: number;
		total_questions: number;
		progress: number;
		status: string;
		queue_position: number | null;
		updated_at: string | null;
		message: string | null;
	}

	interface LiveAnalyticsSnapshot {
		active_users: ActiveUser[];
		vetting_count: number;
		generating_count: number;
		queued_count: number;
		pending_generation_threshold: number;
		eligible_topics_count: number;
		generated_questions_total: number;
		target_questions_total: number;
		remaining_questions: number;
		topics_below_target_count: number;
		schedulable_questions_total: number;
		blocked_topics_count: number;
		blocked_questions_total: number;
		topic_backlog_questions_total: number;
		surplus_questions_total: number;
		generating_items: GenerationWorkItem[];
		queued_items: GenerationWorkItem[];
		timestamp: string;
	}

	interface HistoricalItem {
		date: string;
		hour: number | null;
		vetting_count: number;
		generation_count: number;
		questions_vetted: number;
		questions_generated: number;
		unique_vetters: number;
		unique_generators: number;
	}

	interface HistoricalData {
		items: HistoricalItem[];
		total_vetting_sessions: number;
		total_generation_runs: number;
		total_questions_vetted: number;
		total_questions_generated: number;
	}

	// State
	let loading = $state(true);
	let error = $state('');
	let activeUsers = $state<ActiveUser[]>([]);
	let vettingCount = $state(0);
	let generatingCount = $state(0);
	let queuedCount = $state(0);
	let pendingGenerationThreshold = $state(0);
	let eligibleTopicsCount = $state(0);
	let generatedQuestionsTotal = $state(0);
	let targetQuestionsTotal = $state(0);
	let remainingQuestions = $state(0);
	let topicsBelowTargetCount = $state(0);
	let schedulableQuestionsTotal = $state(0);
	let blockedTopicsCount = $state(0);
	let blockedQuestionsTotal = $state(0);
	let topicBacklogQuestionsTotal = $state(0);
	let surplusQuestionsTotal = $state(0);
	let generatingItems = $state<GenerationWorkItem[]>([]);
	let queuedItems = $state<GenerationWorkItem[]>([]);
	let lastUpdate = $state('');
	let historicalData = $state<HistoricalData | null>(null);
	let historicalLoading = $state(false);
	let liveNowMs = $state(Date.now());
	let generationDialogKind = $state<'running' | 'queued' | null>(null);

	// Date range filters
	let fromDate = $state<string>('');
	let toDate = $state<string>('');

	// Sorting
	type SortField = 'date' | 'vetting_count' | 'generation_count' | 'questions_vetted' | 'questions_generated' | 'unique_vetters' | 'unique_generators';
	let sortField = $state<SortField>('date');
	let sortDirection = $state<'asc' | 'desc'>('desc');

	// WebSocket
	let ws: WebSocket | null = null;
	let wsConnected = $state(false);
	let reconnectAttempts = 0;
	const maxReconnectAttempts = 5;
	let pingTimer: ReturnType<typeof setInterval> | null = null;
	let durationTimer: ReturnType<typeof setInterval> | null = null;
	const ANALYTICS_PING_INTERVAL_MS = 10000;

	// Initialize date range (last 7 days by default)
	function initializeDateRange() {
		const today = new Date();
		const weekAgo = new Date(today);
		weekAgo.setDate(today.getDate() - 7);
		
		toDate = today.toISOString().split('T')[0];
		fromDate = weekAgo.toISOString().split('T')[0];
	}

	$effect(() => {
		const unsub = session.subscribe((s) => {
			if (!s || s.user.role !== 'admin') {
				goto('/admin/login');
			}
		});
		return unsub;
	});

	onMount(() => {
		initializeDateRange();
		startDurationTicker();
		void loadInitialData();
		connectWebSocket();
	});

	onDestroy(() => {
		stopDurationTicker();
		stopPingInterval();
		if (ws) {
			ws.close();
			ws = null;
		}
	});

	function applyLiveSnapshot(snapshot: Partial<LiveAnalyticsSnapshot>) {
		if (Array.isArray(snapshot.active_users)) {
			activeUsers = snapshot.active_users;
		}
		if (Array.isArray(snapshot.generating_items)) {
			generatingItems = snapshot.generating_items;
		}
		if (Array.isArray(snapshot.queued_items)) {
			queuedItems = snapshot.queued_items;
		}
		if (typeof snapshot.vetting_count === 'number') {
			vettingCount = snapshot.vetting_count;
		}
		if (typeof snapshot.generating_count === 'number') {
			generatingCount = snapshot.generating_count;
		}
		if (typeof snapshot.queued_count === 'number') {
			queuedCount = snapshot.queued_count;
		}
		if (typeof snapshot.pending_generation_threshold === 'number') {
			pendingGenerationThreshold = snapshot.pending_generation_threshold;
		}
		if (typeof snapshot.eligible_topics_count === 'number') {
			eligibleTopicsCount = snapshot.eligible_topics_count;
		}
		if (typeof snapshot.generated_questions_total === 'number') {
			generatedQuestionsTotal = snapshot.generated_questions_total;
		}
		if (typeof snapshot.target_questions_total === 'number') {
			targetQuestionsTotal = snapshot.target_questions_total;
		}
		if (typeof snapshot.remaining_questions === 'number') {
			remainingQuestions = snapshot.remaining_questions;
		}
		if (typeof snapshot.topics_below_target_count === 'number') {
			topicsBelowTargetCount = snapshot.topics_below_target_count;
		}
		if (typeof snapshot.schedulable_questions_total === 'number') {
			schedulableQuestionsTotal = snapshot.schedulable_questions_total;
		}
		if (typeof snapshot.blocked_topics_count === 'number') {
			blockedTopicsCount = snapshot.blocked_topics_count;
		}
		if (typeof snapshot.blocked_questions_total === 'number') {
			blockedQuestionsTotal = snapshot.blocked_questions_total;
		}
		if (typeof snapshot.topic_backlog_questions_total === 'number') {
			topicBacklogQuestionsTotal = snapshot.topic_backlog_questions_total;
		}
		if (typeof snapshot.surplus_questions_total === 'number') {
			surplusQuestionsTotal = snapshot.surplus_questions_total;
		}
		if (typeof snapshot.timestamp === 'string' && snapshot.timestamp) {
			lastUpdate = snapshot.timestamp;
		}
	}

	async function loadInitialData() {
		loading = true;
		error = '';
		try {
			const active = await apiFetch<LiveAnalyticsSnapshot>('/analytics/active');
			applyLiveSnapshot(active);
			loading = false;
			historicalLoading = true;
			void loadHistoricalInitial();
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to load analytics data';
		} finally {
			if (loading) {
				loading = false;
			}
		}
	}

	async function loadHistoricalInitial() {
		try {
			historicalData = await loadHistoricalData();
		} catch (e: unknown) {
			if (!error) {
				error = e instanceof Error ? e.message : 'Failed to load historical data';
			}
		} finally {
			historicalLoading = false;
		}
	}

	async function loadHistoricalData(): Promise<HistoricalData> {
		if (!fromDate || !toDate) {
			throw new Error('Date range not set');
		}
		const from = new Date(fromDate);
		const to = new Date(toDate);
		const daysDiff = Math.ceil((to.getTime() - from.getTime()) / (1000 * 60 * 60 * 24));
		// Cap at 90 days to match backend validation
		const days = Math.min(Math.max(daysDiff, 1), 90);
		return await apiFetch<HistoricalData>(`/analytics/historical?days=${days}`);
	}

	async function loadHistorical() {
		historicalLoading = true;
		error = ''; // Clear previous errors
		try {
			// Validate date range
			if (fromDate && toDate) {
				const from = new Date(fromDate);
				const to = new Date(toDate);
				const daysDiff = Math.ceil((to.getTime() - from.getTime()) / (1000 * 60 * 60 * 24));
				
				if (daysDiff > 90) {
					error = 'Date range cannot exceed 90 days. Please select a shorter range.';
					historicalLoading = false;
					return;
				}
				
				if (daysDiff < 0) {
					error = 'Start date must be before end date.';
					historicalLoading = false;
					return;
				}
			}
			
			historicalData = await loadHistoricalData();
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to load historical data';
		} finally {
			historicalLoading = false;
		}
	}

	function handleSort(field: SortField) {
		if (sortField === field) {
			sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
		} else {
			sortField = field;
			sortDirection = field === 'date' ? 'desc' : 'asc';
		}
	}

	function getSortedHistoricalItems(): HistoricalItem[] {
		if (!historicalData?.items) return [];
		
		const items = [...historicalData.items];
		
		items.sort((a, b) => {
			let aVal: string | number = a[sortField];
			let bVal: string | number = b[sortField];
			
			// Handle null values
			if (aVal === null) aVal = 0;
			if (bVal === null) bVal = 0;
			
			let comparison = 0;
			if (typeof aVal === 'string' && typeof bVal === 'string') {
				comparison = aVal.localeCompare(bVal);
			} else if (typeof aVal === 'number' && typeof bVal === 'number') {
				comparison = aVal - bVal;
			}
			
			return sortDirection === 'asc' ? comparison : -comparison;
		});
		
		return items;
	}

	function setDateRange(days: number) {
		const today = new Date();
		const startDate = new Date(today);
		startDate.setDate(today.getDate() - days);
		
		toDate = today.toISOString().split('T')[0];
		fromDate = startDate.toISOString().split('T')[0];
		
		loadHistorical();
	}

	function startPingInterval() {
		stopPingInterval();
		pingTimer = setInterval(() => {
			if (ws && ws.readyState === WebSocket.OPEN) {
				ws.send(JSON.stringify({ action: 'ping' }));
			}
		}, ANALYTICS_PING_INTERVAL_MS);
	}

	function startDurationTicker() {
		stopDurationTicker();
		durationTimer = setInterval(() => {
			liveNowMs = Date.now();
		}, 1000);
	}

	function stopDurationTicker() {
		if (durationTimer) {
			clearInterval(durationTimer);
			durationTimer = null;
		}
	}

	function stopPingInterval() {
		if (pingTimer) {
			clearInterval(pingTimer);
			pingTimer = null;
		}
	}

	function connectWebSocket() {
		const sess = get(session);
		if (!sess) return;

		// Convert HTTP API URL to WebSocket URL
		const baseUrl = apiUrl('/analytics/ws');
		const wsUrl = baseUrl.replace(/^http/, 'ws') + `?token=${encodeURIComponent(sess.access_token)}`;

		try {
			ws = new WebSocket(wsUrl);

			ws.onopen = () => {
				wsConnected = true;
				reconnectAttempts = 0;
				console.log('Analytics WebSocket connected');
				startPingInterval();
			};

			ws.onmessage = (event) => {
				try {
					const data = JSON.parse(event.data);
					handleWebSocketMessage(data);
				} catch (e) {
					console.error('Failed to parse WebSocket message:', e);
				}
			};

			ws.onerror = (event) => {
				console.error('Analytics WebSocket error:', event);
			};

			ws.onclose = () => {
				wsConnected = false;
				stopPingInterval();
				console.log('Analytics WebSocket disconnected');

				// Attempt reconnection
				if (reconnectAttempts < maxReconnectAttempts) {
					reconnectAttempts++;
					setTimeout(connectWebSocket, Math.min(1000 * Math.pow(2, reconnectAttempts), 30000));
				}
			};
		} catch (e) {
			console.error('Failed to create WebSocket:', e);
		}
	}

	function handleWebSocketMessage(data: { type: string; data?: Record<string, unknown>; [key: string]: unknown }) {
		switch (data.type) {
			case 'connected':
				console.log('WebSocket connection confirmed:', data.connection_id);
				break;
			case 'activity_update':
				if (data.data) {
					applyLiveSnapshot(data.data as Partial<LiveAnalyticsSnapshot>);
				}
				break;
			case 'pong':
				break;
			case 'error':
				console.error('WebSocket error:', data.message);
				break;
		}
	}

	function getLiveDurationSeconds(user: ActiveUser): number {
		const startedAtMs = Date.parse(user.started_at);
		if (!Number.isFinite(startedAtMs)) {
			return user.duration_seconds;
		}
		return Math.max(user.duration_seconds, Math.floor((liveNowMs - startedAtMs) / 1000));
	}

	function formatDuration(seconds: number): string {
		if (seconds < 60) return `${seconds}s`;
		const mins = Math.floor(seconds / 60);
		const secs = seconds % 60;
		if (mins < 60) return `${mins}m ${secs}s`;
		const hours = Math.floor(mins / 60);
		const remainingMins = mins % 60;
		return `${hours}h ${remainingMins}m`;
	}

	function formatTime(isoString: string): string {
		const normalized = /[Zz]$|[+-]\d{2}:\d{2}$/.test(isoString) ? isoString : isoString + 'Z';
		return new Date(normalized).toLocaleTimeString();
	}

	function activityClass(activity: string): string {
		switch (activity) {
			case 'vetting':
				return 'activity-vetting';
			case 'generating':
				return 'activity-generating';
			default:
				return 'activity-idle';
		}
	}

	function openGenerationDialog(kind: 'running' | 'queued') {
		generationDialogKind = kind;
	}

	function closeGenerationDialog() {
		generationDialogKind = null;
	}

	function handleGenerationDialogKeydown(event: KeyboardEvent) {
		if (event.key === 'Escape') {
			closeGenerationDialog();
		}
	}

	function generationDialogItems(): GenerationWorkItem[] {
		if (generationDialogKind === 'running') return generatingItems;
		if (generationDialogKind === 'queued') return queuedItems;
		return [];
	}

	function generationDialogTitle(): string {
		if (generationDialogKind === 'running') return 'Currently Generating';
		if (generationDialogKind === 'queued') return 'Generation Backlog';
		return '';
	}

	function generationDialogDescription(): string {
		if (generationDialogKind === 'running') {
			return 'Live background generation runs and their current progress.';
		}
		if (generationDialogKind === 'queued') {
			const baseline = `${formatNumber(remainingQuestions)} questions remain to reach the 30-question baseline across eligible topics.`;
			const schedulable = `${formatNumber(schedulableQuestionsTotal)} can be scheduled right now.`;
			if (blockedQuestionsTotal > 0) {
				return `${baseline} ${schedulable} ${formatNumber(blockedQuestionsTotal)} are paused because ${blockedTopicsCount} topics exceed the pending threshold of ${pendingGenerationThreshold}.`;
			}
			return `${baseline} ${schedulable}`;
		}
		return '';
	}

	function formatNumber(value: number): string {
		return new Intl.NumberFormat().format(value);
	}

	function formatGenerationStatus(status: string): string {
		return status
			.split('_')
			.filter(Boolean)
			.map((part) => part.charAt(0).toUpperCase() + part.slice(1))
			.join(' ');
	}

	function generationTopicSummary(item: GenerationWorkItem): string {
		if (item.topic_name) return item.topic_name;
		if (item.topic_names.length === 1) return item.topic_names[0];
		if (item.topic_names.length > 1 && item.topic_names.length <= 3) return item.topic_names.join(', ');
		if (item.topic_names.length > 3) return `${item.topic_names.length} topics`;
		if (item.topic_ids.length > 1) return `${item.topic_ids.length} topics`;
		return 'All topics';
	}

	function generationProgressSummary(item: GenerationWorkItem): string {
		return `${item.current_question} out of ${item.total_questions}`;
	}

	function generationProgressWidth(item: GenerationWorkItem): string {
		const progress = Number.isFinite(item.progress) ? item.progress : 0;
		return `${Math.max(0, Math.min(100, progress))}%`;
	}

	function remainingTopicsLabel(): string {
		const topicCount = topicsBelowTargetCount || queuedItems.length;
		if (targetQuestionsTotal > 0) {
			const blockedSegment = blockedTopicsCount > 0 ? ` | ${blockedTopicsCount} blocked` : '';
			return `${topicCount} ${topicCount === 1 ? 'topic' : 'topics'} below target | ${formatNumber(remainingQuestions)} baseline gap | ${formatNumber(schedulableQuestionsTotal)} schedulable now${blockedSegment}`;
		}
		return `${topicCount} ${topicCount === 1 ? 'topic' : 'topics'} below target`;
	}
</script>

<svelte:head>
	<title>Analytics - VQuest Admin</title>
</svelte:head>

<div class="page">
	<header class="header">
		<div class="header-main">
			<h1>Analytics</h1>
			<p>Activity tracking and historical data</p>
		</div>
		<div class="header-status">
			<!-- <span class="ws-status" class:connected={wsConnected}>
				<span class="ws-dot"></span>
				{wsConnected ? 'Live' : 'Disconnected'}
			</span> -->
			<!-- {#if lastUpdate}
				<span class="last-update">Updated: {formatTime(lastUpdate)}</span>
			{/if} -->
		</div>
	</header>

	{#if error}
		<div class="error-banner" role="alert">{error}</div>
	{/if}

	{#if loading}
		<div class="center-state glass-panel">
			<div class="spinner"></div>
			<p>Loading analytics...</p>
		</div>
	{:else}
		<!-- Live Activity Summary -->
		<div class="stats-row">
			<div class="stat-card glass-panel">
				<div class="stat-icon vetting-icon">✓</div>
				<div class="stat-content">
					<span class="stat-value">{vettingCount}</span>
					<span class="stat-label">Vetting Now</span>
				</div>
			</div>
			<button class="stat-card stat-card-button glass-panel" type="button" onclick={() => openGenerationDialog('running')}>
				<div class="stat-icon generating-icon">⚡</div>
				<div class="stat-content">
					<span class="stat-value">{generatingCount}</span>
					<span class="stat-label">Currently Generating</span>
					<span class="stat-action">View runs</span>
				</div>
			</button>
			<button class="stat-card stat-card-button glass-panel" type="button" onclick={() => openGenerationDialog('queued')}>
				<div class="stat-icon queue-icon">⏳</div>
				<div class="stat-content">
					<span class="stat-value">{formatNumber(schedulableQuestionsTotal)}</span>
					<span class="stat-label">Schedulable To Target</span>
					<span class="stat-action">View backlog</span>
					<span class="stat-meta">{remainingTopicsLabel()}</span>
				</div>
			</button>
		</div>

		{#if generationDialogKind}
			<div class="modal-backdrop" role="presentation" onclick={() => closeGenerationDialog()}>
				<div
					class="generation-dialog glass-panel"
					role="dialog"
					aria-modal="true"
					aria-labelledby="generation-dialog-title"
					tabindex="-1"
					onclick={(event) => event.stopPropagation()}
					onkeydown={handleGenerationDialogKeydown}
				>
					<div class="generation-dialog-header">
						<div>
							<h2 id="generation-dialog-title">{generationDialogTitle()}</h2>
							<p>{generationDialogDescription()}</p>
						</div>
						<button class="dialog-close" type="button" onclick={() => closeGenerationDialog()}>Close</button>
					</div>

					{#if generationDialogItems().length === 0}
						<div class="empty-state compact-empty-state">
							<p>{generationDialogKind === 'running' ? 'No generation is active right now.' : 'No topics are below the current generation target right now.'}</p>
						</div>
					{:else}
						<div class="generation-list">
							{#each generationDialogItems() as item}
								<article class="generation-item">
									<div class="generation-item-header">
										<div class="generation-title-block">
											<h3>{item.subject_name || 'Unknown subject'}</h3>
											<p>{generationTopicSummary(item)}</p>
										</div>
										<span class={`generation-status status-${item.status}`}>{formatGenerationStatus(item.status)}</span>
									</div>

									<div class="generation-metrics-row">
										<span class="generation-metric strong-metric">{generationProgressSummary(item)}</span>
										<span class="generation-metric">{item.progress}%</span>
									</div>
									<div class="generation-progress-bar" aria-hidden="true">
										<span style={`width: ${generationProgressWidth(item)}`}></span>
									</div>

									<div class="generation-meta-row">
										{#if item.queue_position}
											<span>Queue position #{item.queue_position}</span>
										{/if}
										<!-- {#if item.updated_at}
											<span>Updated {formatTime(item.updated_at)}</span>
										{/if} -->
									</div>

									{#if item.message}
										<p class="generation-message">{item.message}</p>
									{/if}
								</article>
							{/each}
						</div>
					{/if}
				</div>
			</div>
		{/if}

		<!-- Active Users List -->
		<section class="glass-panel section">
			<h2 class="section-title">Active Vetters</h2>
			{#if activeUsers.length === 0}
				<div class="empty-state">
					<p>No one is vetting right now</p>
				</div>
			{:else}
				<div class="table-wrap">
					<table>
						<thead>
							<tr>
								<th>User</th>
								<th>Activity</th>
								<th>Subject / Topic</th>
								<th>Started</th>
								<th>Duration</th>
							</tr>
						</thead>
						<tbody>
							{#each activeUsers as user}
								<tr>
									<td>
										<div class="user-cell">
											<strong>{user.username}</strong>
											<span class="email">{user.email}</span>
										</div>
									</td>
									<td>
										<span class={`activity-badge ${activityClass(user.activity)}`}>
											{user.activity}
										</span>
									</td>
									<td>
										{#if user.subject_name || user.topic_name}
											<span class="context-info">
												{user.subject_name || ''}{user.topic_name ? ` / ${user.topic_name}` : ''}
											</span>
										{:else}
											<span class="text-muted">—</span>
										{/if}
									</td>
									<td>{formatTime(user.started_at)}</td>
									<td><span class="duration">{formatDuration(getLiveDurationSeconds(user))}</span></td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{/if}
		</section>

		<!-- Historical Data -->
		<section class="glass-panel section">
			<div class="section-header">
				<h2 class="section-title">Historical Activity</h2>
				<div class="filter-controls">
					<div class="quick-filters">
						<button class="quick-btn" onclick={() => setDateRange(7)}>7d</button>
						<button class="quick-btn" onclick={() => setDateRange(14)}>14d</button>
						<button class="quick-btn" onclick={() => setDateRange(30)}>30d</button>
						<button class="quick-btn" onclick={() => setDateRange(90)}>90d</button>
					</div>
					<div class="date-inputs">
						<label>
							<span class="date-label">From</span>
							<input type="date" class="date-input" bind:value={fromDate} />
						</label>
						<label>
							<span class="date-label">To</span>
							<input type="date" class="date-input" bind:value={toDate} />
						</label>
						<button class="apply-btn" onclick={() => loadHistorical()}>Apply</button>
					</div>
				</div>
			</div>

			{#if historicalLoading}
				<div class="loading-overlay">
					<div class="spinner"></div>
				</div>
			{/if}

			{#if historicalData}
				<div class="summary-stats">
					<div class="summary-item">
						<span class="summary-label">Total Vetting Sessions</span>
						<strong>{historicalData.total_vetting_sessions}</strong>
					</div>
					<div class="summary-item">
						<span class="summary-label">Total Generation Runs</span>
						<strong>{historicalData.total_generation_runs}</strong>
					</div>
					<div class="summary-item">
						<span class="summary-label">Questions Vetted</span>
						<strong>{historicalData.total_questions_vetted}</strong>
					</div>
					<div class="summary-item">
						<span class="summary-label">Questions Generated</span>
						<strong>{historicalData.total_questions_generated}</strong>
					</div>
				</div>

				{#if historicalData.items.length > 0}
					<div class="table-wrap">
						<table>
							<thead>
								<tr>
									<th class="sortable" class:sorted={sortField === 'date'} onclick={() => handleSort('date')}>
										Date
										{#if sortField === 'date'}
											<span class="sort-icon">{sortDirection === 'asc' ? '▲' : '▼'}</span>
										{/if}
									</th>
									<th class="sortable" class:sorted={sortField === 'vetting_count'} onclick={() => handleSort('vetting_count')}>
										Vetting Sessions
										{#if sortField === 'vetting_count'}
											<span class="sort-icon">{sortDirection === 'asc' ? '▲' : '▼'}</span>
										{/if}
									</th>
									<th class="sortable" class:sorted={sortField === 'generation_count'} onclick={() => handleSort('generation_count')}>
										Generation Runs
										{#if sortField === 'generation_count'}
											<span class="sort-icon">{sortDirection === 'asc' ? '▲' : '▼'}</span>
										{/if}
									</th>
									<th class="sortable" class:sorted={sortField === 'questions_vetted'} onclick={() => handleSort('questions_vetted')}>
										Questions Vetted
										{#if sortField === 'questions_vetted'}
											<span class="sort-icon">{sortDirection === 'asc' ? '▲' : '▼'}</span>
										{/if}
									</th>
									<th class="sortable" class:sorted={sortField === 'questions_generated'} onclick={() => handleSort('questions_generated')}>
										Questions Generated
										{#if sortField === 'questions_generated'}
											<span class="sort-icon">{sortDirection === 'asc' ? '▲' : '▼'}</span>
										{/if}
									</th>
									<th class="sortable" class:sorted={sortField === 'unique_vetters'} onclick={() => handleSort('unique_vetters')}>
										Unique Vetters
										{#if sortField === 'unique_vetters'}
											<span class="sort-icon">{sortDirection === 'asc' ? '▲' : '▼'}</span>
										{/if}
									</th>
									<th class="sortable" class:sorted={sortField === 'unique_generators'} onclick={() => handleSort('unique_generators')}>
										Unique Generators
										{#if sortField === 'unique_generators'}
											<span class="sort-icon">{sortDirection === 'asc' ? '▲' : '▼'}</span>
										{/if}
									</th>
								</tr>
							</thead>
							<tbody>
								{#each getSortedHistoricalItems() as item}
									<tr>
										<td>{item.date}</td>
										<td>{item.vetting_count}</td>
										<td>{item.generation_count}</td>
										<td>{item.questions_vetted}</td>
										<td>{item.questions_generated}</td>
										<td>{item.unique_vetters}</td>
										<td>{item.unique_generators}</td>
									</tr>
								{/each}
							</tbody>
						</table>
					</div>
				{:else}
					<div class="empty-state">
						<p>No activity data for this period</p>
					</div>
				{/if}
			{/if}
		</section>
	{/if}
</div>

<style>
	.page {
		max-width: 1280px;
		margin: 0 auto;
		padding: 1.5rem 1.25rem 2.5rem;
		display: grid;
		gap: 1.25rem;
	}

	.header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 1rem;
		flex-wrap: wrap;
		padding: 1.25rem;
		background: var(--theme-glass-bg);
		border: 1px solid var(--theme-glass-border);
		border-radius: 0.9rem;
		backdrop-filter: blur(10px);
	}

	.header-main {
		flex: 1;
		min-width: 200px;
	}

	.header h1 {
		margin: 0;
		font-size: 1.75rem;
		font-weight: 800;
		color: var(--theme-text);
	}

	.header p {
		margin: 0.25rem 0 0;
		color: var(--theme-text-muted);
		font-size: 0.9rem;
	}

	.header-status {
		display: flex;
		align-items: center;
		gap: 1rem;
	}

	.ws-status {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		padding: 0.35rem 0.7rem;
		border-radius: 999px;
		font-size: 0.78rem;
		font-weight: 700;
		background: rgba(239, 68, 68, 0.15);
		border: 1px solid rgba(239, 68, 68, 0.3);
		color: #f87171;
	}

	.ws-status.connected {
		background: rgba(16, 185, 129, 0.15);
		border-color: rgba(16, 185, 129, 0.3);
		color: #34d399;
	}

	.ws-dot {
		width: 0.5rem;
		height: 0.5rem;
		border-radius: 50%;
		background: currentColor;
	}

	.last-update {
		font-size: 0.78rem;
		color: var(--theme-text-muted);
	}

	.error-banner {
		background: rgba(220, 38, 38, 0.14);
		border: 1px solid rgba(220, 38, 38, 0.28);
		color: #f87171;
		border-radius: 0.7rem;
		padding: 0.75rem 1rem;
	}

	.stats-row {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
		gap: 1rem;
	}

	.stat-card {
		display: flex;
		align-items: center;
		gap: 1rem;
		padding: 1.25rem;
		border-radius: 0.9rem;
	}

	.stat-card-button {
		width: 100%;
		border: 1px solid var(--theme-glass-border);
		background: var(--theme-glass-bg);
		color: inherit;
		text-align: left;
		cursor: pointer;
		transition: transform 0.18s ease, border-color 0.18s ease, background 0.18s ease;
	}

	.stat-card-button:hover {
		transform: translateY(-1px);
		border-color: color-mix(in srgb, var(--theme-primary) 35%, var(--theme-glass-border));
		background: color-mix(in srgb, var(--theme-primary) 8%, var(--theme-glass-bg));
	}

	.stat-card-button:focus-visible {
		outline: 2px solid var(--theme-primary);
		outline-offset: 2px;
	}

	.stat-icon {
		width: 3rem;
		height: 3rem;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: 0.7rem;
		font-size: 1.25rem;
	}

	.vetting-icon {
		background: rgba(16, 185, 129, 0.2);
		color: #34d399;
	}

	.generating-icon {
		background: rgba(99, 102, 241, 0.2);
		color: #818cf8;
	}

	.queue-icon {
		background: rgba(245, 158, 11, 0.2);
		color: #fbbf24;
	}

	.stat-content {
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
	}

	.stat-value {
		font-size: 1.75rem;
		font-weight: 800;
		line-height: 1;
	}

	.stat-label {
		font-size: 0.82rem;
		color: var(--theme-text-muted);
	}

	.stat-action {
		font-size: 0.75rem;
		font-weight: 700;
		color: var(--theme-primary);
	}

	.stat-meta {
		font-size: 0.72rem;
		color: var(--theme-text-muted);
	}

	.section {
		padding: 1.25rem;
		border-radius: 0.9rem;
	}

	.section-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 1rem;
		flex-wrap: wrap;
		gap: 0.75rem;
	}

	.section-title {
		margin: 0 0 1rem;
		font-size: 1.1rem;
		font-weight: 700;
	}

	.section-header .section-title {
		margin-bottom: 0;
	}

	.filter-controls {
		display: flex;
		gap: 1rem;
		align-items: center;
		flex-wrap: wrap;
	}

	.quick-filters {
		display: flex;
		gap: 0.4rem;
	}

	.quick-btn {
		padding: 0.4rem 0.75rem;
		border-radius: 0.5rem;
		border: 1px solid var(--theme-glass-border);
		background: var(--theme-glass-bg);
		color: var(--theme-text);
		font-size: 0.8rem;
		font-weight: 600;
		cursor: pointer;
		transition: all 0.2s;
	}

	.quick-btn:hover {
		background: color-mix(in srgb, var(--theme-primary) 20%, var(--theme-glass-bg));
		border-color: var(--theme-primary);
	}

	.date-inputs {
		display: flex;
		gap: 0.65rem;
		align-items: center;
	}

	.date-inputs label {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}

	.date-label {
		font-size: 0.75rem;
		color: var(--theme-text-muted);
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.02em;
	}

	.date-input {
		padding: 0.5rem 0.65rem;
		border-radius: 0.55rem;
		border: 1px solid var(--theme-glass-border);
		background: var(--theme-input-bg);
		color: var(--theme-text);
		font-size: 0.84rem;
		min-width: 140px;
	}

	.apply-btn {
		padding: 0.5rem 1rem;
		border-radius: 0.55rem;
		border: 1px solid var(--theme-primary);
		background: var(--theme-primary);
		color: white;
		font-size: 0.84rem;
		font-weight: 600;
		cursor: pointer;
		align-self: flex-end;
		transition: all 0.2s;
	}

	.apply-btn:hover {
		background: color-mix(in srgb, var(--theme-primary) 85%, black);
		transform: translateY(-1px);
	}

	.apply-btn:active {
		transform: translateY(0);
	}

	/* .filter-select {
		padding: 0.45rem 0.65rem;
		border-radius: 0.55rem;
		border: 1px solid var(--theme-glass-border);
		background: var(--theme-input-bg);
		color: var(--theme-text);
		font-size: 0.84rem;
	} */

	.table-wrap {
		overflow-x: auto;
		border: 1px solid var(--theme-glass-border);
		border-radius: 0.75rem;
	}

	table {
		width: 100%;
		border-collapse: collapse;
		min-width: 600px;
	}

	th,
	td {
		text-align: left;
		padding: 0.65rem 0.75rem;
		border-bottom: 1px solid var(--theme-glass-border);
		color: var(--theme-text);
	}

	th {
		font-size: 0.78rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.02em;
		color: var(--theme-text-muted);
		background: color-mix(in srgb, var(--theme-surface) 50%, transparent);
	}

	th.sortable {
		cursor: pointer;
		user-select: none;
		transition: all 0.2s;
		position: relative;
	}

	th.sortable:hover {
		background: color-mix(in srgb, var(--theme-surface) 70%, transparent);
		color: var(--theme-text);
	}

	th.sorted {
		color: var(--theme-primary);
	}

	.sort-icon {
		font-size: 0.7rem;
		margin-left: 0.3rem;
		opacity: 0.8;
	}

	tr:last-child td {
		border-bottom: none;
	}

	.user-cell {
		display: flex;
		flex-direction: column;
		gap: 0.1rem;
	}

	.user-cell .email {
		font-size: 0.78rem;
		color: var(--theme-text-muted);
	}

	.activity-badge {
		display: inline-flex;
		align-items: center;
		padding: 0.25rem 0.55rem;
		border-radius: 999px;
		font-size: 0.75rem;
		font-weight: 700;
		text-transform: capitalize;
	}

	.activity-vetting {
		background: rgba(16, 185, 129, 0.18);
		color: #34d399;
	}

	.activity-generating {
		background: rgba(99, 102, 241, 0.18);
		color: #818cf8;
	}

	.activity-idle {
		background: rgba(148, 163, 184, 0.18);
		color: var(--theme-text-muted);
	}

	.context-info {
		font-size: 0.85rem;
	}

	.text-muted {
		color: var(--theme-text-muted);
	}

	.duration {
		font-family: monospace;
		font-size: 0.85rem;
	}

	.summary-stats {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
		gap: 0.75rem;
		margin-bottom: 1rem;
	}

	.summary-item {
		padding: 0.85rem;
		border: 1px solid var(--theme-glass-border);
		border-radius: 0.7rem;
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		background: color-mix(in srgb, var(--theme-surface) 50%, transparent);
	}

	.summary-label {
		font-size: 0.78rem;
		color: var(--theme-text-muted);
	}

	.summary-item strong {
		font-size: 1.35rem;
		font-weight: 700;
	}

	.empty-state {
		padding: 2rem;
		text-align: center;
		color: var(--theme-text-muted);
	}

	.center-state {
		padding: 3rem;
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 0.75rem;
		border-radius: 0.9rem;
		color: var(--theme-text-muted);
	}

	.spinner {
		width: 1.5rem;
		height: 1.5rem;
		border: 2px solid rgba(255, 255, 255, 0.2);
		border-top-color: var(--theme-primary);
		border-radius: 999px;
		animation: spin 1s linear infinite;
	}

	.loading-overlay {
		display: flex;
		justify-content: center;
		padding: 1.5rem;
	}

	.modal-backdrop {
		position: fixed;
		inset: 0;
		z-index: 50;
		padding: 1.25rem;
		display: flex;
		align-items: center;
		justify-content: center;
		background: rgba(15, 23, 42, 0.5);
		backdrop-filter: blur(10px);
	}

	.generation-dialog {
		width: min(720px, 100%);
		max-height: min(80vh, 760px);
		overflow: auto;
		padding: 1.25rem;
		border-radius: 1rem;
	}

	.generation-dialog-header {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 1rem;
		margin-bottom: 1rem;
	}

	.generation-dialog-header h2 {
		margin: 0;
		font-size: 1.2rem;
		font-weight: 800;
	}

	.generation-dialog-header p {
		margin: 0.25rem 0 0;
		font-size: 0.84rem;
		color: var(--theme-text-muted);
	}

	.dialog-close {
		border: 1px solid var(--theme-glass-border);
		background: var(--theme-input-bg);
		color: var(--theme-text);
		padding: 0.55rem 0.85rem;
		border-radius: 0.6rem;
		font-size: 0.82rem;
		font-weight: 700;
		cursor: pointer;
	}

	.generation-list {
		display: grid;
		gap: 0.85rem;
	}

	.generation-item {
		padding: 1rem;
		border: 1px solid var(--theme-glass-border);
		border-radius: 0.85rem;
		background: color-mix(in srgb, var(--theme-surface) 55%, transparent);
		display: grid;
		gap: 0.7rem;
	}

	.generation-item-header {
		display: flex;
		justify-content: space-between;
		gap: 1rem;
		align-items: flex-start;
	}

	.generation-title-block h3 {
		margin: 0;
		font-size: 1rem;
		font-weight: 800;
	}

	.generation-title-block p {
		margin: 0.22rem 0 0;
		font-size: 0.82rem;
		color: var(--theme-text-muted);
	}

	.generation-status {
		display: inline-flex;
		align-items: center;
		padding: 0.28rem 0.65rem;
		border-radius: 999px;
		font-size: 0.74rem;
		font-weight: 800;
		white-space: nowrap;
		background: rgba(148, 163, 184, 0.16);
		color: var(--theme-text-muted);
	}

	.generation-status.status-generating,
	.generation-status.status-refilling {
		background: rgba(99, 102, 241, 0.18);
		color: #818cf8;
	}

	.generation-status.status-waiting_for_documents,
	.generation-status.status-scheduled {
		background: rgba(14, 165, 233, 0.18);
		color: #38bdf8;
	}

	.generation-status.status-queued {
		background: rgba(245, 158, 11, 0.18);
		color: #fbbf24;
	}

	.generation-status.status-blocked {
		background: rgba(239, 68, 68, 0.18);
		color: #fca5a5;
	}

	.generation-metrics-row,
	.generation-meta-row {
		display: flex;
		justify-content: space-between;
		gap: 0.75rem;
		flex-wrap: wrap;
	}

	.generation-metric,
	.generation-meta-row span {
		font-size: 0.8rem;
		color: var(--theme-text-muted);
	}

	.strong-metric {
		color: var(--theme-text);
		font-weight: 700;
	}

	.generation-progress-bar {
		height: 0.5rem;
		border-radius: 999px;
		overflow: hidden;
		background: rgba(148, 163, 184, 0.18);
	}

	.generation-progress-bar span {
		display: block;
		height: 100%;
		border-radius: inherit;
		background: linear-gradient(90deg, #38bdf8 0%, #818cf8 100%);
	}

	.generation-message {
		margin: 0;
		font-size: 0.82rem;
		color: var(--theme-text-muted);
	}

	.compact-empty-state {
		padding: 1.5rem 1rem;
	}

	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}

	@media (max-width: 768px) {
		.header {
			flex-direction: column;
		}

		/* .stats-row {
			grid-template-columns: 1fr;
		} */

		.section-header {
			flex-direction: column;
			align-items: flex-start;
		}

		.filter-controls {
			width: 100%;
			flex-direction: column;
			align-items: stretch;
		}

		.date-inputs {
			flex-direction: column;
			align-items: stretch;
		}

		.date-input {
			width: 100%;
		}

		.apply-btn {
			align-self: stretch;
		}

		.generation-dialog-header,
		.generation-item-header,
		.generation-metrics-row,
		.generation-meta-row {
			flex-direction: column;
			align-items: flex-start;
		}
	}
</style>
