<script lang="ts">
	export let status: Record<string, unknown> | null = null;
	export let queueStatus: Record<string, unknown> | null = null;
	export let liveMetrics: Record<string, unknown> | null = null;
	export let isAdvanced = false;
	export let loading = false;

	// Simple mode status messages
	$: simpleStatus = getSimpleStatus();
	$: simpleMetrics = getSimpleMetrics();

	function getSimpleStatus() {
		if (!status) return "No status available";
		
		const statusObj = status as any;
		const latestJob = statusObj.latest_job;
		if (!latestJob) return "Ready to start training";
		
		switch (latestJob.status) {
			case 'pending':
				return "Training is waiting to start";
			case 'running':
				const progress = latestJob.current_step && latestJob.total_steps 
					? Math.round((latestJob.current_step / latestJob.total_steps) * 100)
					: 0;
				return `Training in progress - ${progress}% complete`;
			case 'completed':
				return "Training completed successfully";
			case 'failed':
				return "Training failed - please check advanced mode";
			default:
				return "Checking training status...";
		}
	}

	function getSimpleMetrics() {
		if (!liveMetrics) return { quality: "No data", questionsReviewed: 0, responseTime: "Unknown" };
		
		const metrics = liveMetrics as any;
		const approveRate = metrics.approve_rate || 0;
		const totalReviewed = metrics.total_reviewed || 0;
		const avgLatency = metrics.p95_latency_ns ? Math.round(metrics.p95_latency_ns / 1000000) : 0;
		
		return {
			quality: approveRate > 0.8 ? "Excellent" : approveRate > 0.6 ? "Good" : "Needs Improvement",
			questionsReviewed: totalReviewed,
			responseTime: avgLatency > 0 ? `${avgLatency}ms` : "Very Fast"
		};
	}

	function getPretty(obj: unknown): string {
		return JSON.stringify(obj, null, 2);
	}

	function getStatusColor(status: string) {
		switch (status) {
			case 'completed': return '#10b981';
			case 'running': return '#3b82f6';
			case 'failed': return '#ef4444';
			case 'pending': return '#f59e0b';
			default: return '#6b7280';
		}
	}
</script>

<div class="status-display">
	{#if loading}
		<div class="status-loading">
			<div class="loading-spinner">⟳</div>
			<span>Loading status...</span>
		</div>
	{:else if isAdvanced}
		<!-- Advanced Mode - Show technical details -->
		<div class="advanced-status">
			{#if status}
				<div class="status-section">
					<h3>🔧 Pipeline Status</h3>
					<pre class="json-display">{getPretty(status)}</pre>
				</div>
			{/if}
			
			{#if queueStatus}
				<div class="status-section">
					<h3>📋 Queue Status</h3>
					<pre class="json-display">{getPretty(queueStatus)}</pre>
				</div>
			{/if}
			
			{#if liveMetrics}
				<div class="status-section">
					<h3>📊 Live Metrics</h3>
					<pre class="json-display">{getPretty(liveMetrics)}</pre>
				</div>
			{/if}
		</div>
	{:else}
		<!-- Simple Mode - Show friendly status -->
		<div class="simple-status">
			<div class="status-card">
				<div class="status-header">
					<h3>📊 Training Status</h3>
					<div class="status-indicator" style="color: {getStatusColor((status as any)?.latest_job?.status || 'pending')}">
						{#if (status as any)?.latest_job?.status === 'running'}
							<div class="pulse-dot"></div>
						{/if}
						{simpleStatus}
					</div>
				</div>
			</div>

			{#if simpleMetrics}
				<div class="metrics-card">
					<h3>📈 Performance</h3>
					<div class="metrics-grid">
						<div class="metric-item">
							<div class="metric-label">Quality Score</div>
							<div class="metric-value">{simpleMetrics.quality}</div>
						</div>
						<div class="metric-item">
							<div class="metric-label">Questions Reviewed</div>
							<div class="metric-value">{simpleMetrics.questionsReviewed}</div>
						</div>
						<div class="metric-item">
							<div class="metric-label">Response Time</div>
							<div class="metric-value">{simpleMetrics.responseTime}</div>
						</div>
					</div>
				</div>
			{/if}
		</div>
	{/if}
</div>

<style>
	.status-display {
		margin-bottom: 1.5rem;
	}

	.status-loading {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 1rem;
		color: rgba(255, 255, 255, 0.7);
		font-style: italic;
	}

	.loading-spinner {
		animation: spin 1s linear infinite;
	}

	@keyframes spin {
		from { transform: rotate(0deg); }
		to { transform: rotate(360deg); }
	}

	.advanced-status {
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}

	.status-section {
		background: rgba(0, 0, 0, 0.2);
		border-radius: 0.75rem;
		padding: 1rem;
		border: 1px solid rgba(255, 255, 255, 0.1);
	}

	.status-section h3 {
		margin: 0 0 0.75rem 0;
		font-size: 0.9rem;
		font-weight: 600;
		color: rgba(255, 255, 255, 0.9);
	}

	.json-display {
		margin: 0;
		max-height: 200px;
		overflow: auto;
		font-size: 0.75rem;
		line-height: 1.3;
		padding: 0.75rem;
		border-radius: 0.5rem;
		background: rgba(0, 0, 0, 0.3);
		color: rgba(232, 242, 255, 0.9);
		border: 1px solid rgba(255, 255, 255, 0.1);
	}

	.simple-status {
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}

	.status-card, .metrics-card {
		background: rgba(255, 255, 255, 0.05);
		border-radius: 1rem;
		padding: 1.25rem;
		border: 1px solid rgba(255, 255, 255, 0.1);
		backdrop-filter: blur(10px);
	}

	.status-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 1rem;
	}

	.status-header h3 {
		margin: 0;
		font-size: 1rem;
		font-weight: 600;
		color: rgba(255, 255, 255, 0.95);
	}

	.status-indicator {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		font-size: 0.85rem;
		font-weight: 500;
		padding: 0.25rem 0.75rem;
		border-radius: 1rem;
		background: rgba(255, 255, 255, 0.1);
	}

	.pulse-dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		background: currentColor;
		animation: pulse 2s infinite;
	}

	@keyframes pulse {
		0%, 100% { opacity: 1; }
		50% { opacity: 0.5; }
	}

	.metrics-card h3 {
		margin: 0 0 1rem 0;
		font-size: 1rem;
		font-weight: 600;
		color: rgba(255, 255, 255, 0.95);
	}

	.metrics-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
		gap: 1rem;
	}

	.metric-item {
		text-align: center;
		padding: 0.75rem;
		background: rgba(255, 255, 255, 0.05);
		border-radius: 0.75rem;
		border: 1px solid rgba(255, 255, 255, 0.1);
	}

	.metric-label {
		font-size: 0.75rem;
		color: rgba(255, 255, 255, 0.7);
		margin-bottom: 0.25rem;
		font-weight: 500;
	}

	.metric-value {
		font-size: 0.9rem;
		font-weight: 600;
		color: rgba(255, 255, 255, 0.95);
	}

	@media (max-width: 640px) {
		.status-header {
			flex-direction: column;
			align-items: flex-start;
			gap: 0.5rem;
		}

		.metrics-grid {
			grid-template-columns: 1fr;
		}
	}
</style>
