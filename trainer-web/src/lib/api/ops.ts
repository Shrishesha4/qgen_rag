import {
	buildTrainingDataset,
	evaluateModelVersion,
	promoteModelVersion,
	canaryModelVersion,
	rollbackModelVersion,
	getLiveModelMetrics,
	getTrainingQueueStatus,
} from './training';
import { session } from '../session';

declare global {
	interface Window {
		aiOps?: {
			buildDataset: (snapshotFilter?: Record<string, unknown>) => Promise<Record<string, unknown>>;
			runEval: (versionId: string, opts?: { dataset_tag?: string; eval_type?: string }) => Promise<Record<string, unknown>>;
			canaryModel: (versionId: string) => Promise<Record<string, unknown>>;
			promoteModel: (versionId: string) => Promise<Record<string, unknown>>;
			rollbackModel: (versionId: string) => Promise<Record<string, unknown>>;
			queueStatus: () => Promise<Record<string, unknown>>;
			liveMetrics: () => Promise<Record<string, unknown>>;
		};
	}
}

let metricsTimer: number | null = null;

function startLiveMetricsPolling(): void {
	if (typeof window === 'undefined' || metricsTimer !== null) return;

	// Check if user is authenticated before starting polling
	let unsubscribe: (() => void) | null = null;
	const stop = session.subscribe(($session) => {
		if (!$session) {
			// User not authenticated, don't start polling
			return;
		}

		const poll = async () => {
			try {
				const [metrics, queue] = await Promise.all([
					getLiveModelMetrics(),
					getTrainingQueueStatus(),
				]);
				// console.debug('[aiOps] live-metrics', metrics);
				// console.debug('[aiOps] queue-status', queue);
			} catch (error) {
				console.warn('[aiOps] metrics polling failed', error);
			}
		};

		poll();
		metricsTimer = window.setInterval(poll, 30_000);
		unsubscribe?.(); // Unsubscribe after starting polling
	});
	unsubscribe = stop;
}

export function initAiOps(): void {
	if (typeof window === 'undefined') return;

	window.aiOps = {
		buildDataset: (snapshotFilter?: Record<string, unknown>) => buildTrainingDataset(snapshotFilter),
		runEval: (versionId: string, opts?: { dataset_tag?: string; eval_type?: string }) =>
			evaluateModelVersion(versionId, opts),
		canaryModel: (versionId: string) => canaryModelVersion(versionId),
		promoteModel: (versionId: string) => promoteModelVersion(versionId),
		rollbackModel: (versionId: string) => rollbackModelVersion(versionId),
		queueStatus: () => getTrainingQueueStatus(),
		liveMetrics: () => getLiveModelMetrics(),
	};

	if (import.meta.env.DEV) {
		startLiveMetricsPolling();
	}
}
