/**
 * WebSocket client for real-time generation status updates.
 * Provides cross-device visibility of background generation progress.
 */

import { apiUrl, getStoredSession } from './client';
import type { TopicGenerationStatusItem } from './documents';

export interface GenerationStatusMessage {
	type: 'generation_status';
	subject_id: string;
	topic_id: string;
	data: TopicGenerationStatusItem;
}

export interface ActiveRunsMessage {
	type: 'active_runs';
	subject_id: string;
	runs: TopicGenerationStatusItem[];
}

export interface StatsData {
	total_questions?: number;
	total_approved?: number;
	total_rejected?: number;
	total_pending?: number;
	total_vetted?: number;
	approval_rate?: number;
	subject_id?: string;
	topic_id?: string;
	generated?: number;
	approved?: number;
	rejected?: number;
	pending?: number;
	vetted?: number;
}

export interface StatsUpdateMessage {
	type: 'stats_update';
	data: StatsData;
}

export interface SubjectStatsUpdateMessage {
	type: 'subject_stats_update';
	subject_id: string;
	data: StatsData;
}

export interface TopicStatsUpdateMessage {
	type: 'topic_stats_update';
	subject_id: string;
	topic_id: string;
	data: StatsData;
}

export interface WebSocketMessage {
	type: string;
	[key: string]: unknown;
}

export type GenerationStatusCallback = (status: TopicGenerationStatusItem) => void;
export type ActiveRunsCallback = (subjectId: string, runs: TopicGenerationStatusItem[]) => void;
export type ConnectionCallback = (connected: boolean) => void;
export type GlobalStatsCallback = (stats: StatsData) => void;
export type SubjectStatsCallback = (subjectId: string, stats: StatsData) => void;
export type TopicStatsCallback = (subjectId: string, topicId: string, stats: StatsData) => void;

export class GenerationWebSocketClient {
	private ws: WebSocket | null = null;
	private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
	private pingTimer: ReturnType<typeof setInterval> | null = null;
	private subscribedSubjects: Set<string> = new Set();
	private subscribedTopics: Set<string> = new Set();
	private subscribedToGlobalStats: boolean = false;
	private statusCallbacks: Set<GenerationStatusCallback> = new Set();
	private activeRunsCallbacks: Set<ActiveRunsCallback> = new Set();
	private connectionCallbacks: Set<ConnectionCallback> = new Set();
	private globalStatsCallbacks: Set<GlobalStatsCallback> = new Set();
	private subjectStatsCallbacks: Set<SubjectStatsCallback> = new Set();
	private topicStatsCallbacks: Set<TopicStatsCallback> = new Set();
	private reconnectAttempts = 0;
	private maxReconnectAttempts = 5;
	private reconnectDelay = 1000;
	private isIntentionallyClosed = false;

	/**
	 * Connect to the WebSocket server.
	 */
	connect(): void {
		if (this.ws?.readyState === WebSocket.OPEN || this.ws?.readyState === WebSocket.CONNECTING) {
			return;
		}

		this.isIntentionallyClosed = false;
		const session = getStoredSession();
		const token = session?.access_token || '';
		
		// Convert HTTP URL to WebSocket URL
		const baseUrl = apiUrl('/ws/generation-status');
		const wsUrl = baseUrl.replace(/^http/, 'ws') + `?token=${encodeURIComponent(token)}`;

		try {
			this.ws = new WebSocket(wsUrl);

			this.ws.onopen = () => {
				console.log('[GenerationWS] Connected');
				this.reconnectAttempts = 0;
				this.notifyConnectionCallbacks(true);
				
				// Re-subscribe to previously subscribed subjects/topics
				this.subscribedSubjects.forEach(subjectId => {
					this.sendMessage({ action: 'subscribe_subject', subject_id: subjectId });
				});
				this.subscribedTopics.forEach(topicId => {
					this.sendMessage({ action: 'subscribe_topic', topic_id: topicId });
				});
				
				// Re-subscribe to global stats if previously subscribed
				if (this.subscribedToGlobalStats) {
					this.sendMessage({ action: 'subscribe_global_stats' });
				}

				// Start ping interval to keep connection alive
				this.startPingInterval();
			};

			this.ws.onmessage = (event) => {
				try {
					const message = JSON.parse(event.data) as WebSocketMessage;
					this.handleMessage(message);
				} catch (e) {
					console.warn('[GenerationWS] Failed to parse message:', e);
				}
			};

			this.ws.onclose = (event) => {
				console.log('[GenerationWS] Disconnected:', event.code, event.reason);
				this.stopPingInterval();
				this.notifyConnectionCallbacks(false);
				
				if (!this.isIntentionallyClosed) {
					this.scheduleReconnect();
				}
			};

			this.ws.onerror = (error) => {
				console.error('[GenerationWS] Error:', error);
			};
		} catch (e) {
			console.error('[GenerationWS] Failed to create WebSocket:', e);
			this.scheduleReconnect();
		}
	}

	/**
	 * Disconnect from the WebSocket server.
	 */
	disconnect(): void {
		this.isIntentionallyClosed = true;
		this.stopPingInterval();
		
		if (this.reconnectTimer) {
			clearTimeout(this.reconnectTimer);
			this.reconnectTimer = null;
		}

		if (this.ws) {
			this.ws.close();
			this.ws = null;
		}
	}

	/**
	 * Subscribe to generation status updates for a subject.
	 */
	subscribeSubject(subjectId: string): void {
		const wasSubscribed = this.subscribedSubjects.has(subjectId);
		this.subscribedSubjects.add(subjectId);
		if (!wasSubscribed && this.ws?.readyState === WebSocket.OPEN) {
			this.sendMessage({ action: 'subscribe_subject', subject_id: subjectId });
		}
	}

	/**
	 * Unsubscribe from a subject.
	 */
	unsubscribeSubject(subjectId: string): void {
		const wasSubscribed = this.subscribedSubjects.delete(subjectId);
		if (wasSubscribed && this.ws?.readyState === WebSocket.OPEN) {
			this.sendMessage({ action: 'unsubscribe_subject', subject_id: subjectId });
		}
	}

	/**
	 * Subscribe to generation status updates for a topic.
	 */
	subscribeTopic(topicId: string): void {
		this.subscribedTopics.add(topicId);
		if (this.ws?.readyState === WebSocket.OPEN) {
			this.sendMessage({ action: 'subscribe_topic', topic_id: topicId });
		}
	}

	/**
	 * Unsubscribe from a topic.
	 */
	unsubscribeTopic(topicId: string): void {
		this.subscribedTopics.delete(topicId);
		if (this.ws?.readyState === WebSocket.OPEN) {
			this.sendMessage({ action: 'unsubscribe_topic', topic_id: topicId });
		}
	}

	/**
	 * Request active runs for a subject.
	 */
	getActiveRuns(subjectId: string): void {
		if (this.ws?.readyState === WebSocket.OPEN) {
			this.sendMessage({ action: 'get_active_runs', subject_id: subjectId });
		}
	}

	/**
	 * Subscribe to global stats updates.
	 */
	subscribeGlobalStats(): void {
		this.subscribedToGlobalStats = true;
		if (this.ws?.readyState === WebSocket.OPEN) {
			this.sendMessage({ action: 'subscribe_global_stats' });
		}
	}

	/**
	 * Unsubscribe from global stats updates.
	 */
	unsubscribeGlobalStats(): void {
		this.subscribedToGlobalStats = false;
		if (this.ws?.readyState === WebSocket.OPEN) {
			this.sendMessage({ action: 'unsubscribe_global_stats' });
		}
	}

	/**
	 * Register a callback for generation status updates.
	 */
	onStatusUpdate(callback: GenerationStatusCallback): () => void {
		this.statusCallbacks.add(callback);
		return () => this.statusCallbacks.delete(callback);
	}

	/**
	 * Register a callback for active runs responses.
	 */
	onActiveRuns(callback: ActiveRunsCallback): () => void {
		this.activeRunsCallbacks.add(callback);
		return () => this.activeRunsCallbacks.delete(callback);
	}

	/**
	 * Register a callback for connection state changes.
	 */
	onConnectionChange(callback: ConnectionCallback): () => void {
		this.connectionCallbacks.add(callback);
		return () => this.connectionCallbacks.delete(callback);
	}

	/**
	 * Register a callback for global stats updates.
	 */
	onGlobalStats(callback: GlobalStatsCallback): () => void {
		this.globalStatsCallbacks.add(callback);
		return () => this.globalStatsCallbacks.delete(callback);
	}

	/**
	 * Register a callback for subject stats updates.
	 */
	onSubjectStats(callback: SubjectStatsCallback): () => void {
		this.subjectStatsCallbacks.add(callback);
		return () => this.subjectStatsCallbacks.delete(callback);
	}

	/**
	 * Register a callback for topic stats updates.
	 */
	onTopicStats(callback: TopicStatsCallback): () => void {
		this.topicStatsCallbacks.add(callback);
		return () => this.topicStatsCallbacks.delete(callback);
	}

	/**
	 * Check if connected.
	 */
	isConnected(): boolean {
		return this.ws?.readyState === WebSocket.OPEN;
	}

	private sendMessage(message: Record<string, unknown>): void {
		if (this.ws?.readyState === WebSocket.OPEN) {
			this.ws.send(JSON.stringify(message));
		}
	}

	private handleMessage(message: WebSocketMessage): void {
		switch (message.type) {
			case 'generation_status': {
				const statusMsg = message as unknown as GenerationStatusMessage;
				this.statusCallbacks.forEach(cb => cb(statusMsg.data));
				break;
			}
			case 'active_runs': {
				const runsMsg = message as unknown as ActiveRunsMessage;
				this.activeRunsCallbacks.forEach(cb => cb(runsMsg.subject_id, runsMsg.runs));
				break;
			}
			case 'stats_update': {
				const statsMsg = message as unknown as StatsUpdateMessage;
				this.globalStatsCallbacks.forEach(cb => cb(statsMsg.data));
				break;
			}
			case 'subject_stats_update': {
				const subjectStatsMsg = message as unknown as SubjectStatsUpdateMessage;
				this.subjectStatsCallbacks.forEach(cb => cb(subjectStatsMsg.subject_id, subjectStatsMsg.data));
				break;
			}
			case 'topic_stats_update': {
				const topicStatsMsg = message as unknown as TopicStatsUpdateMessage;
				this.topicStatsCallbacks.forEach(cb => cb(topicStatsMsg.subject_id, topicStatsMsg.topic_id, topicStatsMsg.data));
				break;
			}
			case 'connected':
				console.log('[GenerationWS] Connection confirmed');
				break;
			case 'subscribed':
				console.log('[GenerationWS] Subscribed:', message);
				break;
			case 'unsubscribed':
				console.log('[GenerationWS] Unsubscribed:', message);
				break;
			case 'pong':
				// Heartbeat response
				break;
			case 'error':
				console.warn('[GenerationWS] Server error:', message);
				break;
			default:
				console.log('[GenerationWS] Unknown message type:', message.type);
		}
	}

	private notifyConnectionCallbacks(connected: boolean): void {
		this.connectionCallbacks.forEach(cb => cb(connected));
	}

	private startPingInterval(): void {
		this.stopPingInterval();
		this.pingTimer = setInterval(() => {
			this.sendMessage({ action: 'ping' });
		}, 30000); // Ping every 30 seconds
	}

	private stopPingInterval(): void {
		if (this.pingTimer) {
			clearInterval(this.pingTimer);
			this.pingTimer = null;
		}
	}

	private scheduleReconnect(): void {
		if (this.reconnectAttempts >= this.maxReconnectAttempts) {
			console.log('[GenerationWS] Max reconnect attempts reached');
			return;
		}

		const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts);
		console.log(`[GenerationWS] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts + 1})`);

		this.reconnectTimer = setTimeout(() => {
			this.reconnectAttempts++;
			this.connect();
		}, delay);
	}
}

// Global singleton instance
let globalClient: GenerationWebSocketClient | null = null;

export function getGenerationWebSocketClient(): GenerationWebSocketClient {
	if (!globalClient) {
		globalClient = new GenerationWebSocketClient();
	}
	return globalClient;
}
