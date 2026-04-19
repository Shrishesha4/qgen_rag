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
	let lastUpdate = $state('');
	let historicalData = $state<HistoricalData | null>(null);
	let historicalLoading = $state(false);

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
		loadInitialData();
		connectWebSocket();
	});

	onDestroy(() => {
		stopPingInterval();
		if (ws) {
			ws.close();
			ws = null;
		}
	});

	async function loadInitialData() {
		loading = true;
		error = '';
		try {
			const [active, historical] = await Promise.all([
				apiFetch<{ active_users: ActiveUser[]; vetting_count: number; generating_count: number; timestamp: string }>('/analytics/active'),
				loadHistoricalData()
			]);
			activeUsers = active.active_users;
			vettingCount = active.vetting_count;
			generatingCount = active.generating_count;
			lastUpdate = active.timestamp;
			historicalData = historical;
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to load analytics data';
		} finally {
			loading = false;
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
		}, 30000); // Ping every 30 seconds
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
					activeUsers = (data.data.active_users as ActiveUser[]) || [];
					vettingCount = (data.data.vetting_count as number) || 0;
					generatingCount = (data.data.generating_count as number) || 0;
					lastUpdate = (data.data.timestamp as string) || new Date().toISOString();
				}
				break;
			case 'pong':
				break;
			case 'error':
				console.error('WebSocket error:', data.message);
				break;
		}
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
			{#if lastUpdate}
				<span class="last-update">Updated: {formatTime(lastUpdate)}</span>
			{/if}
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
			<div class="stat-card glass-panel">
				<div class="stat-icon generating-icon">⚡</div>
				<div class="stat-content">
					<span class="stat-value">{generatingCount}</span>
					<span class="stat-label">Generating Now</span>
				</div>
			</div>
			<div class="stat-card glass-panel">
				<div class="stat-icon total-icon">👥</div>
				<div class="stat-content">
					<span class="stat-value">{activeUsers.length}</span>
					<span class="stat-label">Total Active</span>
				</div>
			</div>
		</div>

		<!-- Active Users List -->
		<section class="glass-panel section">
			<h2 class="section-title">Active Users</h2>
			{#if activeUsers.length === 0}
				<div class="empty-state">
					<p>No active users at the moment</p>
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
									<td><span class="duration">{formatDuration(user.duration_seconds)}</span></td>
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

	.total-icon {
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
	}
</style>
