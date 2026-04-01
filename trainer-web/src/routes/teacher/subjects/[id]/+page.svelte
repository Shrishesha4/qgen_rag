<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { session } from '$lib/session';
	import { apiFetch, apiUrl, getStoredSession } from '$lib/api/client';
	import {
		createTopic,
		deleteSubject,
		getSubject,
		updateTopic,
		type SubjectDetailResponse,
		type TopicResponse,
	} from '$lib/api/subjects';
	import {
		deleteDocumentById,
		getDocumentStatus,
		getBackgroundGenerationStatuses,
		getTopicGenerationStatuses,
		listReferenceDocuments,
		scheduleBackgroundGeneration,
		uploadDocument,
		type ReferenceDocumentItem,
		type TopicGenerationStatusItem,
	} from '$lib/api/documents';
	import { getQuestionsForVetting } from '$lib/api/vetting';
	import { getGenerationWebSocketClient, type GenerationWebSocketClient } from '$lib/api/generation-websocket';

	let loading = $state(true);
	let error = $state('');
	let subjectId = $state('');
	let subject = $state<SubjectDetailResponse | null>(null);
	let statsLoading = $state(false);

	type ReviewStats = {
		generated: number;
		approved: number;
		rejected: number;
		pending: number;
		vetted: number;
		approvalRate: number;
	};

	let subjectReviewStats = $state<ReviewStats>({
		generated: 0,
		approved: 0,
		rejected: 0,
		pending: 0,
		vetted: 0,
		approvalRate: 0,
	});
	let topicReviewStats = $state<Record<string, ReviewStats>>({});

	let showAddTopicModal = $state(false);
	let addingTopic = $state(false);
	let addTopicName = $state('');
	let addTopicDescription = $state('');
	let addTopicSyllabus = $state('');
	let addTopicBookPdf = $state<File | null>(null);
	let addTopicQuestionPdf = $state<File | null>(null);
	let addTopicUploadProgress = $state<Record<string, number>>({});
	let addTopicUploadProgressDetail = $state<Record<string, string>>({});
	let addTopicUploadingFiles = $state<Record<string, boolean>>({});

	let showEditTopicModal = $state(false);
	let editingTopic = $state(false);
	let deletingSubject = $state(false);
	let editTopicId = $state('');
	let editTopicName = $state('');
	let editTopicDescription = $state('');
	let editTopicSyllabus = $state('');
	let showSyllabusExpand = $state(false);

	// History tab state
	type EditModalTab = 'edit' | 'history';
	let editModalTab = $state<EditModalTab>('edit');
	type AuditEntry = {
		id: string;
		topic_id: string;
		user_name: string;
		action: string;
		field_name: string | null;
		old_value: string | null;
		new_value: string | null;
		created_at: string | null;
	};
	let auditEntries = $state<AuditEntry[]>([]);
	let auditLoading = $state(false);
	let auditError = $state('');

	async function loadAuditLog(topicId: string) {
		auditLoading = true;
		auditError = '';
		try {
			const data = await apiFetch<{ entries: AuditEntry[] }>(`/subjects/topics/${topicId}/audit-log?limit=100`);
			auditEntries = data.entries ?? [];
		} catch (e: unknown) {
			auditError = e instanceof Error ? e.message : 'Failed to load history';
		} finally {
			auditLoading = false;
		}
	}

	function formatAuditDate(iso: string | null): string {
		if (!iso) return 'Unknown';
		const d = new Date(iso);
		if (isNaN(d.getTime())) return 'Unknown';
		return d.toLocaleString();
	}

	function formatFieldName(field: string | null): string {
		const map: Record<string, string> = {
			topic_name: 'Topic Name',
			description: 'Description',
			syllabus_content: 'Syllabus Content',
			reference_pdf: 'Reference PDF',
		};
		return map[field ?? ''] ?? field ?? 'Unknown';
	}

	function truncateValue(val: string | null, max: number = 120): string {
		if (!val) return '(empty)';
		return val.length > max ? val.slice(0, max) + '...' : val;
	}

	let referenceTab = $state<'pdfs' | 'questions'>('pdfs');
	let referenceLoading = $state(false);
	let referenceUploading = $state(false);
	let referenceError = $state<string>('');
	let deletingRefId = $state<string | null>(null);

	// PDF Preview Modal
	let showPreviewModal = $state(false);
	let previewLoading = $state(false);
	let previewError = $state('');
	let previewUrl = $state<string | null>(null);
	let previewFilename = $state('');

	async function openPdfPreview(docId: string, filename: string) {
		previewFilename = filename;
		previewLoading = true;
		previewError = '';
		showPreviewModal = true;
		
		try {
			const s = getStoredSession();
			const res = await fetch(apiUrl(`/documents/${docId}/download`), {
				headers: s?.access_token ? { Authorization: `Bearer ${s.access_token}` } : {},
			});
			if (!res.ok) throw new Error('Failed to load PDF preview');
			const blob = await res.blob();
			previewUrl = URL.createObjectURL(blob);
		} catch (e: any) {
			previewError = e.message || 'Error loading PDF';
		} finally {
			previewLoading = false;
		}
	}

	function closePdfPreview() {
		showPreviewModal = false;
		if (previewUrl) {
			URL.revokeObjectURL(previewUrl);
			previewUrl = null;
		}
		previewFilename = '';
	}
	let pdfUploadType = $state<'reference_book' | 'template_paper'>('reference_book');
	let referenceBooks = $state<ReferenceDocumentItem[]>([]);
	let templatePapers = $state<ReferenceDocumentItem[]>([]);
	let referenceQuestions = $state<ReferenceDocumentItem[]>([]);
	let referenceProgressByDoc = $state<Record<string, number>>({});
	let referenceProgressDetailByDoc = $state<Record<string, string>>({});
	let referencePollTimer: ReturnType<typeof setInterval> | null = null;
	let topicGeneratingById = $state<Record<string, boolean>>({});
	let topicGenerationProgressById = $state<Record<string, string>>({});
	let completedGenerationHoldByTopicId = $state<Record<string, boolean>>({});
	let showGenerationNoticeModal = $state(false);
	let generationNoticeMessage = $state('');
	let showMissingSyllabusModal = $state(false);
	let missingSyllabusTopicName = $state('');
	let missingSyllabusTopicId = $state('');
	let showGenerateBeforeVettingModal = $state(false);
	let generateBeforeVettingTopicId = $state('');
	let generateBeforeVettingTopicName = $state('');
	let generationPollTimer: ReturnType<typeof setInterval> | null = null;
	let generationPollingTopicId = $state<string | null>(null);
	let generationPollingRunId = $state<string | null>(null);
	let generationPollMisses = 0;
	
	// WebSocket client for real-time generation updates
	let wsClient = $state<GenerationWebSocketClient | null>(null);
	let wsUnsubscribe = $state<(() => void) | null>(null);

	const PROCESSING_DOC_STATUSES = new Set(['pending', 'processing']);

	onMount(() => {
		const unsub = session.subscribe((s) => {
			if (!s || s.user.role !== 'teacher') {
				goto('/teacher/login');
			}
		});

		const unsubPage = page.subscribe((p) => {
			subjectId = p.params.id ?? '';
			void loadSubject();
		});

		return () => {
			unsub();
			unsubPage();
		};
	});

	onDestroy(() => {
		clearReferencePolling();
		clearGenerationPolling();
		// Clean up WebSocket
		if (wsClient && subjectId) {
			wsClient.unsubscribeSubject(subjectId);
		}
		if (wsUnsubscribe) {
			wsUnsubscribe();
			wsUnsubscribe = null;
		}
	});

	function clearGenerationPolling() {
		if (generationPollTimer) {
			clearInterval(generationPollTimer);
			generationPollTimer = null;
		}
		generationPollingTopicId = null;
		generationPollingRunId = null;
		generationPollMisses = 0;
	}

	async function syncBackgroundGenerationState() {
		if (!subjectId || !generationPollingTopicId) return;

		try {
			const statusRes = await getBackgroundGenerationStatuses([subjectId]);
			const status = statusRes.statuses[subjectId];

			if (!status) {
				generationPollMisses += 1;
				if (generationPollMisses >= 2 && generationPollingTopicId) {
					const next = { ...topicGeneratingById };
					delete next[generationPollingTopicId];
					topicGeneratingById = next;

					const nextProgress = { ...topicGenerationProgressById };
					delete nextProgress[generationPollingTopicId];
					topicGenerationProgressById = nextProgress;

					// Clear stored topic ID since generation appears to be done
					if (subjectId) {
						sessionStorage.removeItem(`gen_topic_${subjectId}`);
					}

					clearGenerationPolling();
					await loadSubject();
				}
				return;
			}

			generationPollMisses = 0;

			if (generationPollingRunId && status.run_id && status.run_id !== generationPollingRunId) {
				return;
			}

			if (generationPollingTopicId) {
				const total = Math.max(1, status.total_questions || 0);
				const current = Math.max(0, Math.min(total, status.current_question || 0));
				topicGenerationProgressById = {
					...topicGenerationProgressById,
					[generationPollingTopicId]: `${current}/${total}`,
				};
			}

			if (status.in_progress) {
				if (generationPollingTopicId) {
					topicGeneratingById = {
						...topicGeneratingById,
						[generationPollingTopicId]: true,
					};
				}
				return;
			}

			if (generationPollingTopicId) {
				const next = { ...topicGeneratingById };
				delete next[generationPollingTopicId];
				topicGeneratingById = next;

				const nextProgress = { ...topicGenerationProgressById };
				delete nextProgress[generationPollingTopicId];
				topicGenerationProgressById = nextProgress;

				if ((status.status || '').toLowerCase() === 'completed' && (status.current_question || 0) > 0) {
					completedGenerationHoldByTopicId = {
						...completedGenerationHoldByTopicId,
						[generationPollingTopicId]: true,
					};
				}
				
				// Clear stored topic ID since generation is complete
				if (subjectId) {
					sessionStorage.removeItem(`gen_topic_${subjectId}`);
				}
			}

			clearGenerationPolling();
			await loadSubject();
		} catch {
			// Keep polling; transient status failures should not interrupt active generation UI.
		}
	}

	function startGenerationPolling(topicId: string, runId?: string | null) {
		if (generationPollTimer) {
			clearInterval(generationPollTimer);
			generationPollTimer = null;
		}

		generationPollingTopicId = topicId;
		generationPollingRunId = runId ?? null;
		generationPollMisses = 0;

		generationPollTimer = setInterval(() => {
			void syncBackgroundGenerationState();
		}, 2500);

		void syncBackgroundGenerationState();
	}

	function clearReferencePolling() {
		if (referencePollTimer) {
			clearInterval(referencePollTimer);
			referencePollTimer = null;
		}
	}

	async function loadSubject() {
		if (!subjectId) return;
		loading = true;
		error = '';
		try {
			subject = await getSubject(subjectId);
			await loadReviewStats();
			// Check for any in-progress generation after loading subject
			await checkForInProgressGeneration();
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to load subject';
		} finally {
			loading = false;
		}
	}

	async function checkForInProgressGeneration() {
		if (!subjectId || !subject) return;
		
		try {
			// Get all topic IDs for this subject
			const topicIds = subject.topics.map(t => t.id);
			if (!topicIds.length) return;
			
			// Query the database for any active generation runs (cross-device visibility)
			const statusRes = await getTopicGenerationStatuses(topicIds);
			
			// Process any active runs
			for (const [topicId, status] of Object.entries(statusRes.statuses)) {
				if (status.in_progress) {
					// There's an active generation for this topic
					topicGeneratingById = { ...topicGeneratingById, [topicId]: true };
					const total = status.total_questions || 30;
					const current = status.current_question || 0;
					topicGenerationProgressById = { ...topicGenerationProgressById, [topicId]: `${current}/${total}` };
					
					// Store topic ID for this session
					sessionStorage.setItem(`gen_topic_${subjectId}`, topicId);
					
					// Start polling for this topic
					startGenerationPolling(topicId, status.run_id);
				}
			}
			
			// Set up WebSocket for real-time updates
			setupWebSocket();
		} catch {
			// Silently fail - this is just a status check
			// Fall back to the old subject-based check
			try {
				const statusRes = await getBackgroundGenerationStatuses([subjectId]);
				const status = statusRes.statuses[subjectId];
				
				if (status && status.in_progress) {
					const storedTopicId = sessionStorage.getItem(`gen_topic_${subjectId}`);
					
					if (storedTopicId && subject?.topics.some(t => t.id === storedTopicId)) {
						topicGeneratingById = { ...topicGeneratingById, [storedTopicId]: true };
						const total = status.total_questions || 30;
						const current = status.current_question || 0;
						topicGenerationProgressById = { ...topicGenerationProgressById, [storedTopicId]: `${current}/${total}` };
						startGenerationPolling(storedTopicId, status.run_id);
					}
				}
			} catch {
				// Silently fail
			}
		}
	}
	
	function setupWebSocket() {
		if (!subjectId) return;
		
		// Get or create WebSocket client
		wsClient = getGenerationWebSocketClient();
		wsClient.connect();
		
		// Subscribe to this subject's updates
		wsClient.subscribeSubject(subjectId);
		
		// Handle real-time status updates
		wsUnsubscribe = wsClient.onStatusUpdate((status: TopicGenerationStatusItem) => {
			// Only process updates for topics in this subject
			if (status.subject_id !== subjectId) return;
			
			const topicId = status.topic_id;
			
			if (status.in_progress) {
				// Update generating state
				topicGeneratingById = { ...topicGeneratingById, [topicId]: true };
				const total = status.total_questions || 30;
				const current = status.current_question || 0;
				topicGenerationProgressById = { ...topicGenerationProgressById, [topicId]: `${current}/${total}` };
			} else {
				// Generation completed or failed
				const next = { ...topicGeneratingById };
				delete next[topicId];
				topicGeneratingById = next;
				
				const nextProgress = { ...topicGenerationProgressById };
				delete nextProgress[topicId];
				topicGenerationProgressById = nextProgress;
				
				// Clear stored topic ID
				sessionStorage.removeItem(`gen_topic_${subjectId}`);
				
				// Show completion hold if successful
				if (status.status === 'completed' && status.current_question > 0) {
					completedGenerationHoldByTopicId = {
						...completedGenerationHoldByTopicId,
						[topicId]: true,
					};
				}
				
				// Reload subject to get updated question counts
				void loadSubject();
			}
		});
		
		// Handle subject stats updates
		const subjectStatsUnsub = wsClient.onSubjectStats((sid: string, statsData) => {
			if (sid !== subjectId || !subject) return;
			
			// Update subject stats
			subject = {
				...subject,
				total_questions: statsData.total_questions ?? subject.total_questions,
				total_approved: statsData.total_approved ?? subject.total_approved,
				total_rejected: statsData.total_rejected ?? subject.total_rejected,
				total_pending: statsData.total_pending ?? subject.total_pending,
			};
			
			// Update review stats
			subjectReviewStats = {
				...subjectReviewStats,
				generated: statsData.total_questions ?? subjectReviewStats.generated,
				approved: statsData.total_approved ?? subjectReviewStats.approved,
				rejected: statsData.total_rejected ?? subjectReviewStats.rejected,
				pending: statsData.total_pending ?? subjectReviewStats.pending,
				vetted: (statsData.total_approved ?? 0) + (statsData.total_rejected ?? 0),
				approvalRate: statsData.approval_rate ?? subjectReviewStats.approvalRate,
			};
		});
		
		// Handle topic stats updates
		const topicStatsUnsub = wsClient.onTopicStats((sid: string, tid: string, statsData) => {
			if (sid !== subjectId) return;
			
			// Update topic review stats
			topicReviewStats = {
				...topicReviewStats,
				[tid]: {
					generated: statsData.generated ?? topicReviewStats[tid]?.generated ?? 0,
					approved: statsData.approved ?? topicReviewStats[tid]?.approved ?? 0,
					rejected: statsData.rejected ?? topicReviewStats[tid]?.rejected ?? 0,
					pending: statsData.pending ?? topicReviewStats[tid]?.pending ?? 0,
					vetted: (statsData.approved ?? 0) + (statsData.rejected ?? 0),
					approvalRate: statsData.approval_rate ?? topicReviewStats[tid]?.approvalRate ?? 0,
				}
			};
			
			// Update topic in subject.topics array
			if (subject) {
				subject = {
					...subject,
					topics: subject.topics.map(t => {
						if (t.id === tid) {
							return {
								...t,
								total_questions: statsData.generated ?? t.total_questions,
							};
						}
						return t;
					})
				};
			}
		});
		
		// Store additional unsubscribers - we'll clean them up in onDestroy
		const originalUnsub = wsUnsubscribe;
		wsUnsubscribe = () => {
			originalUnsub?.();
			subjectStatsUnsub();
			topicStatsUnsub();
		};
	}

	function calcApprovalRate(approved: number, generated: number): number {
		if (generated <= 0) return 0;
		return Math.round((approved / generated) * 100);
	}

	function normalizeStatus(status: string | null | undefined): 'approved' | 'rejected' | 'pending' {
		const value = (status || '').toLowerCase();
		if (value.includes('approve')) return 'approved';
		if (value.includes('reject')) return 'rejected';
		return 'pending';
	}

	async function loadReviewStats() {
		if (!subject) return;
		statsLoading = true;
		try {
			const limit = 100;
			let pageNo = 1;
			const allQuestions: Array<{ topic_id: string | null; vetting_status: string }> = [];

			while (true) {
				const pageRes = await getQuestionsForVetting({
					subject_id: subject.id,
					status: 'all',
					page: pageNo,
					limit,
				});
				allQuestions.push(
					...pageRes.questions.map((q) => ({
						topic_id: q.topic_id,
						vetting_status: q.vetting_status,
					}))
				);
				if (pageNo >= pageRes.pages || pageRes.questions.length === 0) break;
				pageNo += 1;
			}

			const perTopic: Record<string, ReviewStats> = {};
			for (const topic of subject.topics) {
				perTopic[topic.id] = {
					generated: 0,
					approved: 0,
					rejected: 0,
					pending: 0,
					vetted: 0,
					approvalRate: 0,
				};
			}

			let orphanApproved = 0;
			let orphanRejected = 0;
			let orphanPending = 0;

			for (const q of allQuestions) {
				const normalized = normalizeStatus(q.vetting_status);
				if (q.topic_id && perTopic[q.topic_id]) {
					if (normalized === 'approved') perTopic[q.topic_id].approved += 1;
					else if (normalized === 'rejected') perTopic[q.topic_id].rejected += 1;
					else perTopic[q.topic_id].pending += 1;
					continue;
				}

				if (normalized === 'approved') orphanApproved += 1;
				else if (normalized === 'rejected') orphanRejected += 1;
				else orphanPending += 1;
			}

			if (subject.topics.length === 1) {
				const onlyTopicId = subject.topics[0].id;
				perTopic[onlyTopicId].approved += orphanApproved;
				perTopic[onlyTopicId].rejected += orphanRejected;
				perTopic[onlyTopicId].pending += orphanPending;
			}

			let approvedTotal = 0;
			let rejectedTotal = 0;
			let pendingTotal = 0;
			let generatedTotal = 0;

			for (const topic of subject.topics) {
				const stats = perTopic[topic.id];
				stats.generated = stats.approved + stats.rejected + stats.pending;
				stats.vetted = stats.approved + stats.rejected;
				if (stats.generated === 0) {
					stats.generated = topic.total_questions;
					stats.pending = Math.max(0, topic.total_questions - stats.vetted);
				}
				stats.approvalRate = calcApprovalRate(stats.approved, stats.generated);

				generatedTotal += stats.generated;
				approvedTotal += stats.approved;
				rejectedTotal += stats.rejected;
				pendingTotal += stats.pending;
			}

			const vettedTotal = approvedTotal + rejectedTotal;
			topicReviewStats = perTopic;
				subjectReviewStats = {
				generated: generatedTotal,
				approved: approvedTotal,
				rejected: rejectedTotal,
				pending: pendingTotal,
				vetted: vettedTotal,
					approvalRate: calcApprovalRate(approvedTotal, generatedTotal),
			};

			if (Object.keys(completedGenerationHoldByTopicId).length > 0) {
				const nextHold = { ...completedGenerationHoldByTopicId };
				for (const topicId of Object.keys(nextHold)) {
					if ((perTopic[topicId]?.generated || 0) > 0) {
						delete nextHold[topicId];
					}
				}
				completedGenerationHoldByTopicId = nextHold;
			}
		} catch {
			if (subject) {
				subjectReviewStats = {
					generated: subject.total_questions,
					approved: 0,
					rejected: 0,
					pending: subject.total_questions,
					vetted: 0,
					approvalRate: 0,
				};
			}
		} finally {
			statsLoading = false;
		}
	}

	function openGenerateBeforeVettingModal(topicId: string, topicName: string) {
		generateBeforeVettingTopicId = topicId;
		generateBeforeVettingTopicName = topicName;
		showGenerateBeforeVettingModal = true;
	}

	function closeGenerateBeforeVettingModal() {
		showGenerateBeforeVettingModal = false;
		generateBeforeVettingTopicId = '';
		generateBeforeVettingTopicName = '';
	}

	function generateFromVettingModal() {
		const topicId = generateBeforeVettingTopicId;
		closeGenerateBeforeVettingModal();
		if (!topicId) return;
		void generateTopic(topicId);
	}

	function vetTopic(topicId: string) {
		if (!subjectId) return;
		const topic = subject?.topics.find((item) => item.id === topicId);
		const generatedCount = topicReviewStats[topicId]?.generated ?? topic?.total_questions ?? 0;
		if (generatedCount <= 0) {
			openGenerateBeforeVettingModal(topicId, topic?.name ?? 'This topic');
			return;
		}
		const params = new URLSearchParams({ subject: subjectId, topic: topicId, resume: '0' });
		goto(`/teacher/train/loop?${params.toString()}`);
	}

	function closeGenerationNoticeModal() {
		showGenerationNoticeModal = false;
	}

	function openMissingSyllabusModal(topicId: string, topicName: string) {
		missingSyllabusTopicId = topicId;
		missingSyllabusTopicName = topicName;
		showMissingSyllabusModal = true;
	}

	function closeMissingSyllabusModal() {
		showMissingSyllabusModal = false;
		missingSyllabusTopicId = '';
		missingSyllabusTopicName = '';
	}

	function openTopicEditorFromSyllabusModal() {
		if (!missingSyllabusTopicId || !subject) {
			closeMissingSyllabusModal();
			return;
		}

		const topic = subject.topics.find((item) => item.id === missingSyllabusTopicId);
		closeMissingSyllabusModal();
		if (topic) openEditTopicModal(topic);
	}

	async function generateTopic(topicId: string) {
		if (!subjectId || topicGeneratingById[topicId] || !!generationPollingTopicId) return;

		const topic = subject?.topics.find((item) => item.id === topicId);
		const topicName = topic?.name ?? 'this topic';
		const syllabusContent = topic?.syllabus_content?.trim() ?? '';
		if (!syllabusContent) {
			openMissingSyllabusModal(topicId, topicName);
			return;
		}

		generationNoticeMessage = `Question generation for "${topicName}" has started in the background. This may take a few minutes. You can navigate away and come back later to vet the generated questions.`;
		showGenerationNoticeModal = true;
		
		// Store topic ID for resuming on page reload
		sessionStorage.setItem(`gen_topic_${subjectId}`, topicId);
		
		const nextHold = { ...completedGenerationHoldByTopicId };
		delete nextHold[topicId];
		completedGenerationHoldByTopicId = nextHold;
		topicGeneratingById = {
			...topicGeneratingById,
			[topicId]: true,
		};
		topicGenerationProgressById = {
			...topicGenerationProgressById,
			[topicId]: '0/30',
		};
		error = '';
		try {
			const references = await listReferenceDocuments(subjectId, topicId);
			const topicPdfCount = [
				...(references.reference_books ?? []),
				...(references.template_papers ?? []),
			].filter((doc) => doc.topic_id === topicId).length;
			const allowWithoutReference = topicPdfCount === 0;

			const scheduled = await scheduleBackgroundGeneration({
				subjectId,
				count: 30,
				types: 'mcq',
				difficulty: 'medium',
				topicId,
				allowWithoutReference,
			});

			const total = Math.max(1, scheduled.count || 30);
			topicGenerationProgressById = {
				...topicGenerationProgressById,
				[topicId]: `0/${total}`,
			};

			startGenerationPolling(topicId, scheduled.run_id ?? null);
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to start background generation';

			const next = { ...topicGeneratingById };
			delete next[topicId];
			topicGeneratingById = next;

			const nextProgress = { ...topicGenerationProgressById };
			delete nextProgress[topicId];
			topicGenerationProgressById = nextProgress;
		}
	}

	function canGenerateTopic(topicId: string, fallbackPending: number, fallbackGenerated: number) {
		if (completedGenerationHoldByTopicId[topicId]) return false;
		const totalPending = subjectReviewStats.pending;
		const topicGenerated = topicReviewStats[topicId]?.generated ?? fallbackGenerated;
		const topicPending = topicReviewStats[topicId]?.pending ?? fallbackPending;
		if (topicGenerated === 0) return true;
		return totalPending <= 25 && topicPending < 5;
	}

	// Check if topic is currently generating (show status even when questions > 0)
	function isTopicGenerating(topicId: string): boolean {
		return !!topicGeneratingById[topicId] || generationPollingTopicId === topicId;
	}

	function openAddTopicModal() {
		addTopicName = '';
		addTopicDescription = '';
		addTopicSyllabus = '';
		addTopicBookPdf = null;
		addTopicQuestionPdf = null;
		addTopicUploadProgress = {};
		addTopicUploadProgressDetail = {};
		addTopicUploadingFiles = {};
		showAddTopicModal = true;
	}

	function closeAddTopicModal() {
		if (addingTopic || Object.keys(addTopicUploadingFiles).length > 0) return;
		showAddTopicModal = false;
	}

	async function uploadWithProgress(file: File, subjectId: string, indexType: string, topicId: string, progressKey: string): Promise<void> {
		return new Promise((resolve, reject) => {
			const xhr = new XMLHttpRequest();
			const form = new FormData();
			form.append('file', file);
			form.append('subject_id', subjectId);
			form.append('index_type', indexType);
			form.append('topic_id', topicId);

			// Track if upload portion is complete
			let uploadComplete = false;

			xhr.upload.addEventListener('progress', (e) => {
				if (e.lengthComputable) {
					// Upload progress is 0-50% of total progress
					const uploadPercent = Math.round((e.loaded / e.total) * 50);
					addTopicUploadProgress = { ...addTopicUploadProgress, [progressKey]: uploadPercent };
					addTopicUploadProgressDetail = { ...addTopicUploadProgressDetail, [progressKey]: 'Uploading file...' };
				}
			});

			xhr.addEventListener('load', async () => {
				if (xhr.status >= 200 && xhr.status < 300) {
					uploadComplete = true;
					const response = JSON.parse(xhr.responseText);
					const documentId = response.document_id;

					if (documentId) {
						// Start polling backend for processing status
						let processingDone = false;
						const pollInterval = setInterval(async () => {
							if (processingDone) {
								clearInterval(pollInterval);
								return;
							}

							try {
								const status = await getDocumentStatus(documentId);
								// Overall progress: upload 50% + processing 50%
								const processingProgress = (status.processing_progress ?? 0);
								const overallProgress = 50 + Math.round(processingProgress * 0.5);
								addTopicUploadProgress = { ...addTopicUploadProgress, [progressKey]: overallProgress };
								addTopicUploadProgressDetail = { ...addTopicUploadProgressDetail, [progressKey]: status.processing_detail || status.processing_step || 'Processing...' };

								// Check if processing is complete
								if (status.status === 'completed') {
									processingDone = true;
									addTopicUploadProgress = { ...addTopicUploadProgress, [progressKey]: 100 };
									addTopicUploadProgressDetail = { ...addTopicUploadProgressDetail, [progressKey]: 'Completed' };
									clearInterval(pollInterval);
									const next = { ...addTopicUploadingFiles };
									delete next[progressKey];
									addTopicUploadingFiles = next;
									resolve();
								}
							} catch (e) {
								// Polling failed, but upload succeeded - still resolve
								if (!processingDone) {
									processingDone = true;
									clearInterval(pollInterval);
									const next = { ...addTopicUploadingFiles };
									delete next[progressKey];
									addTopicUploadingFiles = next;
									resolve();
								}
							}
						}, 1000); // Poll every 1 second
					} else {
						const next = { ...addTopicUploadingFiles };
						delete next[progressKey];
						addTopicUploadingFiles = next;
						resolve();
					}
				} else {
					const next = { ...addTopicUploadingFiles };
					delete next[progressKey];
					addTopicUploadingFiles = next;
					reject(new Error(`Upload failed with status ${xhr.status}`));
				}
			});

			xhr.addEventListener('error', () => {
				const next = { ...addTopicUploadingFiles };
				delete next[progressKey];
				addTopicUploadingFiles = next;
				reject(new Error('Upload error'));
			});

			xhr.open('POST', apiUrl('/documents/reference/upload'));
			// Add authorization header
			const storedSession = getStoredSession();
			if (storedSession?.access_token) {
				xhr.setRequestHeader('Authorization', `Bearer ${storedSession.access_token}`);
			}
			
			xhr.send(form);
		});
	}

	async function submitAddTopic() {
		if (!subjectId || !addTopicName.trim() || addingTopic) return;
		addingTopic = true;
		error = '';
		let createdTopic: TopicResponse | null = null;
		try {
			createdTopic = await createTopic(subjectId, {
				subject_id: subjectId,
				name: addTopicName.trim(),
				description: addTopicDescription.trim() || undefined,
				syllabus_content: addTopicSyllabus.trim() || undefined,
			});

			const uploadTasks: Promise<unknown>[] = [];
			if (addTopicBookPdf) {
				const bookKey = 'book_pdf';
				addTopicUploadingFiles = { ...addTopicUploadingFiles, [bookKey]: true };
				uploadTasks.push(
					uploadWithProgress(addTopicBookPdf, subjectId, 'reference_book', createdTopic.id, bookKey)
				);
			}
			if (addTopicQuestionPdf) {
				const questionKey = 'question_pdf';
				addTopicUploadingFiles = { ...addTopicUploadingFiles, [questionKey]: true };
				uploadTasks.push(
					uploadWithProgress(addTopicQuestionPdf, subjectId, 'reference_questions', createdTopic.id, questionKey)
				);
			}
			if (uploadTasks.length > 0) {
				await Promise.all(uploadTasks);
			}

			showAddTopicModal = false;
			await loadSubject();
		} catch (e: unknown) {
			const message = e instanceof Error ? e.message : 'Failed to add topic';
			if (createdTopic) {
				showAddTopicModal = false;
				await loadSubject();
				error = `Topic was added, but one or more PDF uploads failed: ${message}`;
			} else {
				error = message;
			}
		} finally {
			addingTopic = false;
			addTopicUploadingFiles = {};
		}
	}

	function openEditTopicModal(topic: TopicResponse) {
		editTopicId = topic.id;
		editTopicName = topic.name;
		editTopicDescription = topic.description || '';
		editTopicSyllabus = topic.syllabus_content || '';
		referenceTab = 'pdfs';
		referenceError = '';
		editModalTab = 'edit';
		auditEntries = [];
		auditError = '';
		showEditTopicModal = true;
		void loadReferenceMaterials();
	}

	function closeEditTopicModal() {
		if (editingTopic) return;
		clearReferencePolling();
		referenceError = '';
		referenceBooks = [];
		templatePapers = [];
		referenceQuestions = [];
		referenceProgressByDoc = {};
		referenceProgressDetailByDoc = {};
		showEditTopicModal = false;
	}

	async function submitEditTopic() {
		if (!subjectId || !editTopicId || !editTopicName.trim() || editingTopic) return;
		editingTopic = true;
		error = '';
		try {
			await updateTopic(subjectId, editTopicId, {
				name: editTopicName.trim(),
				description: editTopicDescription.trim() || undefined,
				syllabus_content: editTopicSyllabus.trim() || undefined,
				has_syllabus: editTopicSyllabus.trim().length > 0,
			});
			showEditTopicModal = false;
			await loadSubject();
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to update topic';
		} finally {
			editingTopic = false;
		}
	}

	function allReferenceDocs() {
		return [...referenceBooks, ...templatePapers, ...referenceQuestions];
	}

	function isDocProcessing(status: string) {
		return PROCESSING_DOC_STATUSES.has((status || '').toLowerCase());
	}

	function hasAnyProcessingDocs() {
		return allReferenceDocs().some((doc) => isDocProcessing(doc.processing_status));
	}

	async function refreshReferenceProgressForProcessingDocs() {
		const processingDocs = allReferenceDocs().filter((doc) => isDocProcessing(doc.processing_status));
		if (processingDocs.length === 0) return;

		const updates = await Promise.all(
			processingDocs.map(async (doc) => {
				try {
					const status = await getDocumentStatus(doc.id);
					return {
						id: doc.id,
						progress: status.processing_progress ?? 0,
						detail: status.processing_detail ?? status.processing_step ?? '',
					};
				} catch {
					return {
						id: doc.id,
						progress: 0,
						detail: '',
					};
				}
			})
		);

		const nextProgress = { ...referenceProgressByDoc };
		const nextDetail = { ...referenceProgressDetailByDoc };
		for (const update of updates) {
			nextProgress[update.id] = update.progress;
			nextDetail[update.id] = update.detail;
		}
		referenceProgressByDoc = nextProgress;
		referenceProgressDetailByDoc = nextDetail;
	}

	function ensureReferenceProgressPolling() {
		clearReferencePolling();
		if (!showEditTopicModal || !hasAnyProcessingDocs()) return;
		referencePollTimer = setInterval(() => {
			void loadReferenceMaterials(false);
		}, 5000);
	}

	async function loadReferenceMaterials(withLoader = true) {
		if (!subjectId) return;
		if (withLoader) referenceLoading = true;
		referenceError = '';
		try {
			const res = await listReferenceDocuments(subjectId);
			referenceBooks = res.reference_books || [];
			templatePapers = res.template_papers || [];
			referenceQuestions = res.reference_questions || [];
			await refreshReferenceProgressForProcessingDocs();
			ensureReferenceProgressPolling();
		} catch (e: unknown) {
			referenceError = e instanceof Error ? e.message : 'Failed to load reference materials';
		} finally {
			if (withLoader) referenceLoading = false;
		}
	}

	async function uploadTopicPdf(event: Event, indexType: 'reference_book' | 'template_paper' | 'reference_questions') {
		const input = event.target as HTMLInputElement;
		const file = input.files?.[0];
		if (!file || !subjectId || !editTopicId || referenceUploading) return;

		const progressKey = `edit_${indexType}`;
		referenceUploading = true;
		referenceError = '';

		try {
			await new Promise<void>((resolve, reject) => {
				const xhr = new XMLHttpRequest();
				const form = new FormData();
				form.append('file', file);
				form.append('subject_id', subjectId);
				form.append('index_type', indexType);
				form.append('topic_id', editTopicId);

				xhr.upload.addEventListener('progress', (e) => {
					if (e.lengthComputable) {
						// Upload progress is 0-50% of total
						const uploadPercent = Math.round((e.loaded / e.total) * 50);
						referenceProgressByDoc = { ...referenceProgressByDoc, [progressKey]: uploadPercent };
						referenceProgressDetailByDoc = { ...referenceProgressDetailByDoc, [progressKey]: 'Uploading file...' };
					}
				});

				xhr.addEventListener('load', async () => {
					if (xhr.status >= 200 && xhr.status < 300) {
						const response = JSON.parse(xhr.responseText);
						const documentId = response.document_id;

						if (documentId) {
							// Start polling for processing status
							let processingDone = false;
							const pollInterval = setInterval(async () => {
								if (processingDone) {
									clearInterval(pollInterval);
									return;
								}

								try {
									const status = await getDocumentStatus(documentId);
									// Overall progress: upload 50% + processing 50%
								const processingProgress = (status.processing_progress ?? 0);

									// Show detailed status from backend
									const detailText = status.processing_detail || status.processing_step || 'Processing...';
									referenceProgressDetailByDoc = { ...referenceProgressDetailByDoc, [progressKey]: detailText };

									if (status.status === 'completed') {
										processingDone = true;
										referenceProgressByDoc = { ...referenceProgressByDoc, [progressKey]: 100 };
										referenceProgressDetailByDoc = { ...referenceProgressDetailByDoc, [progressKey]: 'Completed' };
										clearInterval(pollInterval);
										const nextProgress = { ...referenceProgressByDoc };
										delete nextProgress[progressKey];
										referenceProgressByDoc = nextProgress;
										const nextDetail = { ...referenceProgressDetailByDoc };
										delete nextDetail[progressKey];
										referenceProgressDetailByDoc = nextDetail;
										resolve();
									} else if (status.status === 'failed') {
										processingDone = true;
										clearInterval(pollInterval);
										const error = status.error || 'Processing failed';
										const nextProgress = { ...referenceProgressByDoc };
										delete nextProgress[progressKey];
										referenceProgressByDoc = nextProgress;
										const nextDetail = { ...referenceProgressDetailByDoc };
										delete nextDetail[progressKey];
										referenceProgressDetailByDoc = nextDetail;
										reject(new Error(error));
									}
								} catch (e) {
									// Polling failed but upload succeeded - still resolve
									if (!processingDone) {
										processingDone = true;
										clearInterval(pollInterval);
										const nextProgress = { ...referenceProgressByDoc };
										delete nextProgress[progressKey];
										referenceProgressByDoc = nextProgress;
										const nextDetail = { ...referenceProgressDetailByDoc };
										delete nextDetail[progressKey];
										referenceProgressDetailByDoc = nextDetail;
										resolve();
									}
								}
							}, 1000); // Poll every 1 second
						} else {
							setTimeout(() => {
								const nextProgress = { ...referenceProgressByDoc };
								delete nextProgress[progressKey];
								referenceProgressByDoc = nextProgress;
								const nextDetail = { ...referenceProgressDetailByDoc };
								delete nextDetail[progressKey];
								referenceProgressDetailByDoc = nextDetail;
							}, 800);
							resolve();
						}
					} else {
						const nextProgress = { ...referenceProgressByDoc };
						delete nextProgress[progressKey];
						referenceProgressByDoc = nextProgress;
						const nextDetail = { ...referenceProgressDetailByDoc };
						delete nextDetail[progressKey];
						referenceProgressDetailByDoc = nextDetail;
						reject(new Error(`Upload failed with status ${xhr.status}`));
					}
				});

				xhr.addEventListener('error', () => {
					const nextProgress = { ...referenceProgressByDoc };
					delete nextProgress[progressKey];
					referenceProgressByDoc = nextProgress;
					const nextDetail = { ...referenceProgressDetailByDoc };
					delete nextDetail[progressKey];
					referenceProgressDetailByDoc = nextDetail;
					reject(new Error('Upload error'));
				});

				xhr.open('POST', apiUrl('/documents/reference/upload'));
				
				// Add authorization header
				const storedSession = getStoredSession();
				if (storedSession?.access_token) {
					xhr.setRequestHeader('Authorization', `Bearer ${storedSession.access_token}`);
				}
				
				xhr.send(form);
			});

			await loadReferenceMaterials();
			await loadSubject();
		} catch (e: unknown) {
			referenceError = e instanceof Error ? e.message : 'Upload failed';
		} finally {
			referenceUploading = false;
			input.value = '';
		}
	}

	const editTopicReferenceDocs = $derived.by(() => {
		if (!editTopicId) return [] as ReferenceDocumentItem[];
		return [...referenceBooks, ...templatePapers].filter((doc) => doc.topic_id === editTopicId);
	});

	const editTopicQuestionDocs = $derived.by(() => {
		if (!editTopicId) return [] as ReferenceDocumentItem[];
		return referenceQuestions.filter((doc) => doc.topic_id === editTopicId);
	});

	async function deleteReference(docId: string) {
		if (!subjectId || deletingRefId) return;
		deletingRefId = docId;
		referenceError = '';
		try {
			await deleteDocumentById(docId);
			await loadReferenceMaterials();
			await loadSubject();
		} catch (e: unknown) {
			referenceError = e instanceof Error ? e.message : 'Delete failed';
		} finally {
			deletingRefId = '';
		}
	}

	async function onDeleteSubject() {
		if (!subject || deletingSubject) return;
		const confirmed = window.confirm(
			`Delete subject "${subject.name}"? This will remove the subject and related topics.`
		);
		if (!confirmed) return;

		deletingSubject = true;
		error = '';
		try {
			await deleteSubject(subject.id);
			goto('/teacher/subjects');
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to delete subject';
		} finally {
			deletingSubject = false;
		}
	}
</script>

<svelte:head>
	<title>{subject?.name ?? 'Subject'} - Teacher Subjects</title>
</svelte:head>

<div class="page">
	{#if loading}
		<div class="center-state glass-panel">
			<div class="spinner"></div>
			<p>Loading subject...</p>
		</div>
	{:else if error}
		<div class="error-banner" role="alert">{error}</div>
	{:else if subject}
		<div class="hero glass-panel animate-fade-in">
			<div class="hero-top">
				<button class="back-btn" onclick={() => goto('/teacher/subjects')} aria-label="Go back">
					←
				</button>
				<div>
					<p class="eyebrow">{subject.code}  {#if subject.creator_username} · {subject.creator_username}{/if}</p>
					<h1 class="title font-serif">{subject.name}</h1>
				</div>
				<!-- <button class="action-btn action-danger" onclick={onDeleteSubject} disabled={deletingSubject}>
					{deletingSubject ? 'Deleting…' : 'Delete Subject'}
				</button> -->
			</div>
			{#if subject.description}
				<p class="description">{subject.description}</p>
			{/if}
		</div>

		<div class="stats-grid animate-slide-up">
			<div class="stat-card glass-panel">
				<span class="stat-value amber-text">{subject.total_topics}</span >
				<span class="stat-label">Topics</span>
			</div>
			<div class="stat-card glass-panel">
				<span class="stat-value white-text">{statsLoading ? '…' : subjectReviewStats.generated}</span>
				<span class="stat-label">Generated</span>
			</div>
			<div class="stat-card glass-panel">
				<span class="stat-value orange-text">{statsLoading ? '…' : subjectReviewStats.pending}</span>
				<span class="stat-label">Pending</span>
			</div>
			<div class="stat-card glass-panel">
				<span class="stat-value green-text">{statsLoading ? '…' : subjectReviewStats.approved}</span>
				<span class="stat-label">Approved</span>
			</div>
			<div class="stat-card glass-panel">
				<span class="stat-value red-text">{statsLoading ? '…' : subjectReviewStats.rejected}</span>
				<span class="stat-label">Rejected</span>
			</div>
			<div class="stat-card glass-panel">
				<span class="stat-value violet-text">{statsLoading ? '…' : subjectReviewStats.approvalRate}%</span>
				<span class="stat-label">Approval Rate</span>
			</div>
		</div>

		<div class="topic-section glass-panel animate-fade-in">
			<div class="section-head">
				<div>
					<h2 class="section-title">Topics</h2>
					<p class="section-subtitle">Generate or vet directly from each topic.</p>
				</div>
				<div class="section-head-actions">
					<span class="topic-count">{subject.topics.length}</span>
					<button class="action-btn action-add-topic" onclick={openAddTopicModal}>Add Topic</button>
				</div>
			</div>

			{#if subject.topics.length === 0}
				<div class="center-state compact">
					<p>No topics available for this subject yet.</p>
				</div>
			{:else}
				<div class="topics-table-shell desktop-only">
					<table class="topics-table">
						<colgroup>
							<col class="topic-col" />
							<col class="metric-col" />
							<col class="metric-col" />
							<col class="metric-col" />
							<col class="metric-col" />
							<col class="metric-col" />
							<col class="metric-col" />
							<col class="actions-col" />
						</colgroup>
						<thead>
							<tr>
								<th>Topic</th>
								<th>G</th>
								<th>V</th>
								<th>P</th>
								<th>A</th>
								<th>R</th>
								<th>AR</th>
								<th>Actions</th>
							</tr>
						</thead>
						<tbody>
							{#each subject.topics as topic, index}
								<tr>
									<td>
										<div class="topic-main-cell">
											<div class="topic-title-row">
												<span class="topic-index">{index + 1}</span>
												<div class="topic-copy">
													<button class="topic-name-btn" onclick={() => openEditTopicModal(topic)} title="Click to edit topic">
														<h3 class="topic-name">{topic.name}</h3>
													</button>
												</div>
											</div>
										</div>
									</td>
									<td>{topicReviewStats[topic.id]?.generated ?? topic.total_questions}</td>
									<td>{topicReviewStats[topic.id]?.vetted ?? 0}</td>
									<td>{topicReviewStats[topic.id]?.pending ?? topic.total_questions}</td>
									<td class="green-text">{topicReviewStats[topic.id]?.approved ?? 0}</td>
									<td class="red-text">{topicReviewStats[topic.id]?.rejected ?? 0}</td>
									<td class="violet-text">{topicReviewStats[topic.id]?.approvalRate ?? 0}%</td>
									<td class="action-cell">
										<div class="topic-inline-actions">
											{#if isTopicGenerating(topic.id)}
												<button class="action-btn action-generate generating" disabled>
													<span class="btn-spinner" aria-hidden="true"></span>
													<span>Generating {topicGenerationProgressById[topic.id] || ''}</span>
												</button>
											{:else if canGenerateTopic(
												topic.id,
												topicReviewStats[topic.id]?.pending ?? topic.total_questions,
												topicReviewStats[topic.id]?.generated ?? topic.total_questions
											)}
												<button class="action-btn action-generate" onclick={() => generateTopic(topic.id)} disabled={!!generationPollingTopicId}>
													<span>Generate</span>
												</button>
											{/if}
											<button class="action-btn action-vet" onclick={() => vetTopic(topic.id)}>Vet</button>
										</div>
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>

				<div class="mobile-topic-list mobile-only">
					{#each subject.topics as topic, index}
						<div class="mobile-topic-card">
							<div class="topic-title-row">
								<span class="topic-index">{index + 1}</span>
								<div class="topic-copy">
									<button class="topic-name-btn" onclick={() => openEditTopicModal(topic)} title="Click to edit topic">
										<h3 class="topic-name">{topic.name}</h3>
									</button>
									{#if topic.description}
										<p class="topic-description">{topic.description}</p>
									{/if}
								</div>
							</div>
							<div class="mobile-metrics">
								<span>G <strong>{topicReviewStats[topic.id]?.generated ?? topic.total_questions}</strong></span>
								<span>V <strong>{topicReviewStats[topic.id]?.vetted ?? 0}</strong></span>
								<span>P <strong>{topicReviewStats[topic.id]?.pending ?? topic.total_questions}</strong></span>
								<span class="green-text">A <strong>{topicReviewStats[topic.id]?.approved ?? 0}</strong></span>
								<span class="red-text">R <strong>{topicReviewStats[topic.id]?.rejected ?? 0}</strong></span>
								<span class="violet-text">AR <strong>{topicReviewStats[topic.id]?.approvalRate ?? 0}%</strong></span>
							</div>
							<div class="topic-inline-actions">
								{#if isTopicGenerating(topic.id)}
									<button class="action-btn action-generate generating" disabled>
										<span class="btn-spinner" aria-hidden="true"></span>
										<span>Generating {topicGenerationProgressById[topic.id] || ''}</span>
									</button>
								{:else if canGenerateTopic(
									topic.id,
									topicReviewStats[topic.id]?.pending ?? topic.total_questions,
									topicReviewStats[topic.id]?.generated ?? topic.total_questions
								)}
									<button class="action-btn action-generate" onclick={() => generateTopic(topic.id)} disabled={!!generationPollingTopicId}>
										<span>Generate</span>
									</button>
								{/if}
								<button class="action-btn action-vet" onclick={() => vetTopic(topic.id)}>Vet</button>
							</div>
						</div>
					{/each}
				</div>
			{/if}
		</div>
	{/if}
</div>

{#if showGenerationNoticeModal}
	<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
	<div class="modal-backdrop" role="button" tabindex="0" aria-label="Close" onclick={closeGenerationNoticeModal}>
		<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
		<div class="modal-card generation-notice-card" role="dialog" aria-modal="true" tabindex="-1" onclick={(e) => e.stopPropagation()}>
			<div class="modal-head">
				<h3>Generation Started</h3>
				<button class="modal-close" onclick={closeGenerationNoticeModal} aria-label="Close">✕</button>
			</div>
			<div class="modal-body">
				<p class="generation-notice-message">{generationNoticeMessage}</p>
			</div>
			<div class="modal-actions">
				<button class="action-btn action-add-topic" onclick={closeGenerationNoticeModal}>Okay</button>
			</div>
		</div>
	</div>
{/if}

{#if showGenerateBeforeVettingModal}
	<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
	<div class="modal-backdrop" role="button" tabindex="0" aria-label="Close" onclick={closeGenerateBeforeVettingModal}>
		<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
		<div class="modal-card" role="dialog" aria-modal="true" tabindex="-1" onclick={(e) => e.stopPropagation()}>
			<div class="modal-head">
				<h3>No Questions To Vet</h3>
				<button class="modal-close" onclick={closeGenerateBeforeVettingModal} aria-label="Close">✕</button>
			</div>
			<div class="modal-body">
				<p class="generation-notice-message">
					{generateBeforeVettingTopicName} has no generated questions yet. Generate first, then start vetting.
				</p>
			</div>
			<div class="modal-actions">
				<button class="action-btn action-muted" onclick={closeGenerateBeforeVettingModal}>Cancel</button>
				<button class="action-btn action-add-topic" onclick={generateFromVettingModal}>Generate First</button>
			</div>
		</div>
	</div>
{/if}

{#if showMissingSyllabusModal}
	<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
	<div class="modal-backdrop" role="button" tabindex="0" aria-label="Close" onclick={closeMissingSyllabusModal}>
		<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
		<div class="modal-card" role="dialog" aria-modal="true" tabindex="-1" onclick={(e) => e.stopPropagation()}>
			<div class="modal-head">
				<h3>Add Syllabus Content First</h3>
				<button class="modal-close" onclick={closeMissingSyllabusModal} aria-label="Close">✕</button>
			</div>
			<div class="modal-body">
				<p class="generation-notice-message">
					{missingSyllabusTopicName} has no syllabus content yet. Add some syllabus content to this topic before generating a question batch.
				</p>
			</div>
			<div class="modal-actions">
				<button class="action-btn action-muted" onclick={closeMissingSyllabusModal}>Cancel</button>
				<button class="action-btn action-edit" onclick={openTopicEditorFromSyllabusModal}>Add Syllabus</button>
			</div>
		</div>
	</div>
{/if}

{#if showAddTopicModal}
	<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
	<div class="modal-backdrop" role="button" tabindex="0" aria-label="Close" onclick={closeAddTopicModal}>
		<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
		<div class="modal-card" role="dialog" aria-modal="true" tabindex="-1" onclick={(e) => e.stopPropagation()}>
			<div class="modal-head">
				<h3>Add Topic</h3>
				<button class="modal-close" onclick={closeAddTopicModal} aria-label="Close">✕</button>
			</div>
			<div class="modal-body">
				<input class="input" placeholder="Topic name" bind:value={addTopicName} />
				<input class="input" placeholder="Description (optional)" bind:value={addTopicDescription} />
				<textarea class="input textarea" rows="4" placeholder="Syllabus content" bind:value={addTopicSyllabus}></textarea>
				<div class="file-input-group">
					<label class="file-label" for="bookPdf">Book PDF</label>
					<input
						id="bookPdf"
						class="file-input"
						type="file"
						accept=".pdf,application/pdf"
						disabled={addTopicUploadingFiles['book_pdf']}
						onchange={(e) => {
							const target = e.currentTarget as HTMLInputElement;
							addTopicBookPdf = target.files?.[0] ?? null;
						}}
					/>
					{#if addTopicUploadingFiles['book_pdf']}
						<div class="upload-progress">
							<div class="progress-bar-track">
								<div class="progress-bar-fill" style={`width: ${addTopicUploadProgress['book_pdf'] ?? 0}%`}></div>
							</div>
							<span class="progress-text">{addTopicUploadProgress['book_pdf'] ?? 0}%</span>
							{#if addTopicUploadProgressDetail['book_pdf']}
								<div class="progress-detail">{addTopicUploadProgressDetail['book_pdf']}</div>
							{/if}
						</div>
					{/if}
				</div>
				<div class="file-input-group">
					<label class="file-label" for="questionPdf">Question PDF (optional)</label>
					<input
						id="questionPdf"
						class="file-input"
						type="file"
						accept=".pdf,application/pdf"
						disabled={addTopicUploadingFiles['question_pdf']}
						onchange={(e) => {
							const target = e.currentTarget as HTMLInputElement;
							addTopicQuestionPdf = target.files?.[0] ?? null;
						}}
					/>
					{#if addTopicUploadingFiles['question_pdf']}
						<div class="upload-progress">
							<div class="progress-bar-track">
								<div class="progress-bar-fill" style={`width: ${addTopicUploadProgress['question_pdf'] ?? 0}%`}></div>
							</div>
							<span class="progress-text">{addTopicUploadProgress['question_pdf'] ?? 0}%</span>
							{#if addTopicUploadProgressDetail['question_pdf']}
								<div class="progress-detail">{addTopicUploadProgressDetail['question_pdf']}</div>
							{/if}
						</div>
					{/if}
				</div>
			</div>
			<div class="modal-actions">
				<button class="action-btn action-muted" onclick={closeAddTopicModal}>Cancel</button>
				<button class="action-btn action-add-topic" onclick={submitAddTopic} disabled={addingTopic || !addTopicName.trim()}>
					{addingTopic ? 'Adding...' : 'Add Topic'}
				</button>
			</div>
		</div>
	</div>
{/if}

{#if showEditTopicModal}
	<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
	<div class="modal-backdrop" role="button" tabindex="0" aria-label="Close" onclick={closeEditTopicModal}>
		<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
		<div class="modal-card edit-topic-card" role="dialog" aria-modal="true" tabindex="-1" onclick={(e) => e.stopPropagation()}>
			<div class="modal-head">
				<div class="modal-head-tabs">
					<h3>Edit Topic</h3>
					<div class="modal-tab-bar">
						<button class="modal-tab" class:active={editModalTab === 'edit'} onclick={() => editModalTab = 'edit'}>Edit</button>
						<button class="modal-tab" class:active={editModalTab === 'history'} onclick={() => { editModalTab = 'history'; if (!auditEntries.length && editTopicId) loadAuditLog(editTopicId); }}>History</button>
					</div>
				</div>
				<button class="modal-close" onclick={closeEditTopicModal} aria-label="Close">✕</button>
			</div>
			{#if editModalTab === 'edit'}
			<div class="modal-body">
				<input id="editTopicName" class="input" placeholder="Topic name" bind:value={editTopicName} />
				<input id="editTopicDescription" class="input" placeholder="Description (optional)" bind:value={editTopicDescription} />
				<div class="syllabus-field-wrapper">
					<textarea id="editTopicSyllabus" class="input textarea" rows="4" placeholder="Syllabus content" bind:value={editTopicSyllabus}></textarea>
					<button class="syllabus-expand-btn" type="button" onclick={() => showSyllabusExpand = true} title="Expand syllabus editor">⤢</button>
				</div>

				{#if referenceError}
					<p class="modal-error inline-error">{referenceError}</p>
				{/if}

				{#if referenceLoading}
					<div class="topics-loading"><div class="spinner-sm"></div><span>Loading materials…</span></div>
				{:else}
					<div class="file-input-group">
						<label class="file-label" for="editBookPdf">Book/Template PDF</label>
						<input
							id="editBookPdf"
							class="file-input"
							type="file"
							accept=".pdf,.doc,.docx,.txt"
							oninput={(e) => uploadTopicPdf(e, pdfUploadType)}
							disabled={referenceUploading}
						/>
						{#if referenceProgressByDoc[`edit_${pdfUploadType}`] !== undefined}
							<div class="upload-progress">
								<div class="progress-bar-track">
									<div class="progress-bar-fill" style={`width: ${referenceProgressByDoc[`edit_${pdfUploadType}`] ?? 0}%`}></div>
								</div>
								<span class="progress-text">{referenceProgressByDoc[`edit_${pdfUploadType}`] ?? 0}%</span>
								{#if referenceProgressDetailByDoc[`edit_${pdfUploadType}`]}
									<div class="progress-detail">{referenceProgressDetailByDoc[`edit_${pdfUploadType}`]}</div>
								{/if}
							</div>
						{/if}
					</div>
					<div class="doc-list topic-doc-list">
						{#if editTopicReferenceDocs.length}
							{#each editTopicReferenceDocs as doc}
								<div class="doc-row">
									<div class="doc-main">
										<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
										<!-- svelte-ignore a11y_no_static_element_interactions -->
										<div class="doc-name clickable" onclick={() => openPdfPreview(doc.id, doc.filename)}>{doc.filename}</div>
										<div class="doc-meta">{doc.index_type.replace('_', ' ')} • {doc.processing_status}{#if doc.uploaded_by_name} • <span class="doc-uploader">by {doc.uploaded_by_name}</span>{/if}</div>
										{#if isDocProcessing(doc.processing_status)}
											<div class="doc-progress-track">
												<div class="doc-progress-fill" style:width="{referenceProgressByDoc[doc.id] ?? 0}%"></div>
											</div>
											{#if referenceProgressDetailByDoc[doc.id]}
												<div class="doc-progress-detail">{referenceProgressDetailByDoc[doc.id]}</div>
											{/if}
										{/if}
									</div>
									<button class="danger-btn" disabled={deletingRefId === doc.id} onclick={() => deleteReference(doc.id)}>
										{deletingRefId === doc.id ? 'Deleting...' : 'Delete'}
									</button>
								</div>
							{/each}
						{:else}
							<p class="topics-empty">No reference books uploaded yet.</p>
						{/if}
					</div>

					<div class="file-input-group">
						<label class="file-label" for="editQuestionPdf">Question PDF (optional)</label>
						<input
							id="editQuestionPdf"
							class="file-input"
							type="file"
							accept=".pdf,.xlsx,.csv"
							oninput={(e) => uploadTopicPdf(e, 'reference_questions')}
							disabled={referenceUploading}
						/>
						{#if referenceProgressByDoc['edit_reference_questions'] !== undefined}
							<div class="upload-progress">
								<div class="progress-bar-track">
									<div class="progress-bar-fill" style={`width: ${referenceProgressByDoc['edit_reference_questions'] ?? 0}%`}></div>
								</div>
								<span class="progress-text">{referenceProgressByDoc['edit_reference_questions'] ?? 0}%</span>
								{#if referenceProgressDetailByDoc['edit_reference_questions']}
									<div class="progress-detail">{referenceProgressDetailByDoc['edit_reference_questions']}</div>
								{/if}
							</div>
						{/if}
					</div>
					<div class="doc-list topic-doc-list">
						{#if editTopicQuestionDocs.length}
							{#each editTopicQuestionDocs as doc}
								<div class="doc-row">
									<div class="doc-main">
										<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
										<!-- svelte-ignore a11y_no_static_element_interactions -->
										<div class="doc-name clickable" onclick={() => openPdfPreview(doc.id, doc.filename)}>{doc.filename}</div>
										<div class="doc-meta">
											{doc.processing_status}
											{#if doc.parsed_question_count !== null && doc.parsed_question_count !== undefined}
												• {doc.parsed_question_count} parsed
											{/if}
											{#if doc.uploaded_by_name}
												• <span class="doc-uploader">by {doc.uploaded_by_name}</span>
											{/if}
										</div>
										{#if isDocProcessing(doc.processing_status)}
											<div class="doc-progress-track">
												<div class="doc-progress-fill" style:width="{referenceProgressByDoc[doc.id] ?? 0}%"></div>
											</div>
											{#if referenceProgressDetailByDoc[doc.id]}
												<div class="doc-progress-detail">{referenceProgressDetailByDoc[doc.id]}</div>
											{/if}
										{/if}
									</div>
									<button class="danger-btn" disabled={deletingRefId === doc.id} onclick={() => deleteReference(doc.id)}>
										{deletingRefId === doc.id ? 'Deleting...' : 'Delete'}
									</button>
								</div>
							{/each}
						{:else}
							<p class="topics-empty">No reference question files uploaded yet.</p>
						{/if}
					</div>
				{/if}
			</div>
			<div class="modal-actions">
				<button class="action-btn action-muted" onclick={closeEditTopicModal}>Cancel</button>
				<button class="action-btn action-edit" onclick={submitEditTopic} disabled={editingTopic || !editTopicName.trim()}>
					{editingTopic ? 'Saving...' : 'Save Changes'}
				</button>
			</div>
			{:else}
			<!-- History Tab -->
			<div class="modal-body history-body">
				{#if auditLoading}
					<div class="center-state" style="min-height: 200px;"><div class="spinner"></div><p>Loading history...</p></div>
				{:else if auditError}
					<p class="modal-error">{auditError}</p>
				{:else if auditEntries.length === 0}
					<p class="topics-empty" style="text-align: center; padding: 2rem;">No edit history yet. Changes will appear here after edits are made.</p>
				{:else}
					<div class="audit-timeline">
						{#each auditEntries as entry}
							<div class="timeline-item">
								<div class="timeline-dot"></div>
								<div class="timeline-content">
									<div class="timeline-header">
										<span class="timeline-user">{entry.user_name}</span>
										<span class="timeline-action">{entry.action}</span>
										<span class="timeline-field">{formatFieldName(entry.field_name)}</span>
									</div>
									<div class="timeline-date">{formatAuditDate(entry.created_at)}</div>
									{#if entry.old_value || entry.new_value}
										<div class="timeline-diff">
											{#if entry.old_value}
												<div class="diff-line diff-old"><span class="diff-prefix">−</span>{truncateValue(entry.old_value)}</div>
											{/if}
											{#if entry.new_value}
												<div class="diff-line diff-new"><span class="diff-prefix">+</span>{truncateValue(entry.new_value)}</div>
											{/if}
										</div>
									{/if}
								</div>
							</div>
						{/each}
					</div>
				{/if}
			</div>
			{/if}
		</div>
	</div>
{/if}

{#if showSyllabusExpand}
	<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
	<div class="modal-backdrop syllabus-expand-backdrop" role="button" tabindex="0" aria-label="Close" onclick={() => showSyllabusExpand = false}>
		<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
		<div class="syllabus-expand-card" role="dialog" aria-modal="true" tabindex="-1" onclick={(e) => e.stopPropagation()}>
			<div class="modal-head">
				<h3>Syllabus Content</h3>
				<button class="modal-close" onclick={() => showSyllabusExpand = false} aria-label="Close">✕</button>
			</div>
			<div class="syllabus-expand-body">
				<textarea class="input textarea syllabus-expand-textarea" placeholder="Syllabus content" bind:value={editTopicSyllabus}></textarea>
			</div>
		</div>
	</div>
{/if}

<!-- PDF Preview Modal -->
{#if showPreviewModal}
	<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
	<div class="modal-backdrop preview-backdrop" role="button" tabindex="0" aria-label="Close" onclick={closePdfPreview}>
		<div class="modal-card preview-card" role="dialog" aria-modal="true" tabindex="-1" onclick={(e) => e.stopPropagation()}>
			<div class="modal-head">
				<h3>{previewFilename}</h3>
				<button class="modal-close" onclick={closePdfPreview} aria-label="Close">✕</button>
			</div>
			<div class="modal-body preview-body">
				{#if previewLoading}
					<div class="center-state"><div class="spinner"></div><p>Loading PDF...</p></div>
				{:else if previewError}
					<div class="center-state modal-error"><p>{previewError}</p></div>
				{:else if previewUrl}
					<iframe src={previewUrl} title={previewFilename} class="pdf-frame" frameborder="0"></iframe>
				{/if}
			</div>
		</div>
	</div>
{/if}

<style>
	.page {
		max-width: 1320px;
		margin: 0 auto;
		padding: 2rem 1.5rem 2.5rem;
		display: flex;
		flex-direction: column;
		gap: 1rem;
		height: 100%;
		min-height: 0;
		overflow: hidden;
	}

	.hero,
	.topic-section,
	.center-state,
	.stat-card {
		padding: 1.25rem;
		border-radius: 1.25rem;
	}

	.hero-top {
		display: flex;
		justify-content: flex-start;
		align-items: center;
		gap: 2rem;
	}

	.back-btn {
		width: 44px;
		height: 44px;
		border-radius: 999px;
		border: 1px solid rgba(var(--theme-primary-rgb), 0.3);
		background: rgba(var(--theme-primary-rgb), 0.1);
		color: var(--theme-primary);
		font-size: 1.4rem;
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		flex-shrink: 0;
		transition: background 0.15s ease, border-color 0.15s ease;
	}

	.back-btn:hover {
		background: rgba(var(--theme-primary-rgb), 0.16);
		border-color: rgba(var(--theme-primary-rgb), 0.45);
	}

	.eyebrow {
		margin: 0 0 0.35rem;
		font-size: 0.78rem;
		font-weight: 700;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: var(--theme-primary);
	}

	.title {
		margin: 0;
		font-size: 2rem;
		font-weight: 800;
		color: var(--theme-text-primary);
	}

	.description {
		margin: 0.85rem 0 0;
		line-height: 1.65;
		color: var(--theme-text-muted);
	}

	.stats-grid {
		display: grid;
		grid-template-columns: repeat(6, minmax(0, 1fr));
		gap: 0.75rem;
	}

	.stat-card {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.2rem;
	}

	.stat-value {
		font-size: 1.55rem;
		font-weight: 800;
	}

	.stat-label {
		font-size: 0.7rem;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: var(--theme-text-muted);
		font-weight: 700;
	}

	.section-head {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		gap: 1rem;
		margin-bottom: 1rem;
	}

	.section-head-actions {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	.section-title {
		margin: 0;
		font-size: 1.2rem;
		color: var(--theme-text-primary);
	}

	.section-subtitle {
		margin: 0.35rem 0 0;
		color: var(--theme-text-muted);
	}

	.topic-count {
		padding: 0.35rem 0.7rem;
		border-radius: 999px;
		background: rgba(var(--theme-primary-rgb), 0.16);
		color: var(--theme-primary);
		font-weight: 700;
		font-size: 0.8rem;
	}

	.topics-table-shell {
		border-radius: 1rem;
		overflow: auto;
		border: 1px solid color-mix(in srgb, var(--theme-glass-border) 88%, rgba(148, 163, 184, 0.22));
		background: color-mix(in srgb, var(--theme-glass-bg) 92%, transparent);
		max-height: clamp(260px, 52dvh, 650px);
	}

	.topics-table {
		width: 100%;
		table-layout: fixed;
		border-collapse: collapse;
	}

	.topic-col {
		width: 45%;
	}

	.metric-col {
		width: 7.5%;
	}

	.actions-col {
		width: 16%;
	}

	.topics-table th {
		padding: 0.72rem 0.62rem;
		font-size: 0.72rem;
		font-weight: 800;
		letter-spacing: 0.07em;
		text-transform: uppercase;
		color: var(--theme-text-muted);
		text-align: left;
		border-bottom: 1px solid color-mix(in srgb, var(--theme-glass-border) 90%, transparent);
		border-right: 1px solid color-mix(in srgb, var(--theme-glass-border) 82%, transparent);
		background: color-mix(in srgb, var(--theme-glass-bg) 94%, rgba(255, 255, 255, 0.24));
		position: sticky;
		top: 0;
		z-index: 2;
	}

	.topics-table th:last-child {
		border-right: none;
	}

	.topics-table td {
		padding: 0.7rem 0.62rem;
		border-bottom: 1px solid color-mix(in srgb, var(--theme-glass-border) 78%, transparent);
		border-right: 1px solid color-mix(in srgb, var(--theme-glass-border) 72%, transparent);
		color: var(--theme-text-primary);
		vertical-align: top;
		word-break: break-word;
	}

	.topics-table td:last-child {
		border-right: none;
	}

	.topics-table th:nth-child(n + 2),
	.topics-table td:nth-child(n + 2) {
		text-align: center;
	}

	.action-cell {
		text-align: center;
		vertical-align: middle;
	}

	.topics-table tbody tr:last-child td {
		border-bottom: none;
	}

	.topic-main-cell {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}

	.topic-title-row {
		display: flex;
		gap: 0.7rem;
		align-items: flex-start;
	}

	.topic-index {
		width: 32px;
		height: 32px;
		border-radius: 50%;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		flex-shrink: 0;
		background: rgba(var(--theme-primary-rgb), 0.15);
		color: var(--theme-primary);
		font-weight: 800;
		font-size: 0.82rem;
	}

	.topic-copy {
		min-width: 0;
	}

	.topic-name {
		margin: 0;
		font-size: 0.98rem;
		color: var(--theme-text-primary);
	}

	.topic-name-btn {
		background: none;
		border: none;
		padding: 0;
		margin: 0;
		cursor: pointer;
		text-align: left;
		font: inherit;
		color: inherit;
		transition: color 0.15s ease;
	}

	.topic-name-btn:hover .topic-name {
		color: var(--theme-primary);
		text-decoration: underline;
	}

	.topic-name-btn:focus {
		outline: none;
	}

	.topic-name-btn:focus-visible .topic-name {
		color: var(--theme-primary);
		text-decoration: underline;
	}

	.topic-description {
		margin: 0.28rem 0 0;
		color: var(--theme-text-muted);
		line-height: 1.4;
		font-size: 0.86rem;
	}

	.topic-inline-actions {
		display: flex;
		flex-wrap: wrap;
		gap: 0.45rem;
		justify-content: center;
		align-items: center;
		overflow: visible;
	}

	.topics-table .topic-inline-actions {
		flex-direction: column;
		flex-wrap: nowrap;
	}

	.topic-inline-actions .action-btn {
		width: auto;
		min-width: 84px;
		height: 36px;
		padding: 0.4rem 0.68rem;
		font-size: 0.78rem;
	}

	.topics-table .topic-inline-actions .action-btn {
		width: min(132px, 100%);
	}

	.mobile-topic-list .topic-inline-actions {
		justify-content: flex-start;
		align-items: center;
	}

	.action-btn {
		width: 100%;
		min-width: 0;
		height: 44px;
		padding: 0.62rem 0.95rem;
		border-radius: 999px;
		font: inherit;
		font-size: 0.86rem;
		font-weight: 800;
		border: 1px solid transparent;
		cursor: pointer;
		transition: background 0.15s ease, border-color 0.15s ease, transform 0.15s ease;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		white-space: nowrap;
	}

	.action-btn:hover {
		transform: translateY(-1px);
	}

	.action-btn:disabled {
		opacity: 0.65;
		cursor: not-allowed;
		transform: none;
	}

	.action-generate {
		background: rgba(var(--theme-primary-rgb), 0.22);
		border-color: rgba(var(--theme-primary-rgb), 0.5);
		color: var(--theme-text-primary);
	}

	.action-generate.generating {
		gap: 0.45rem;
	}

	.btn-spinner {
		width: 0.88rem;
		height: 0.88rem;
		border-radius: 999px;
		border: 2px solid rgba(255, 255, 255, 0.35);
		border-top-color: currentColor;
		animation: btn-spin 0.8s linear infinite;
		flex-shrink: 0;
	}

	@keyframes btn-spin {
		to {
			transform: rotate(360deg);
		}
	}

	.action-vet {
		background: rgba(var(--theme-primary-rgb), 0.14);
		border-color: rgba(var(--theme-primary-rgb), 0.38);
		color: var(--theme-primary);
	}

	.action-add-topic {
		background: rgba(var(--theme-primary-rgb), 0.2);
		border-color: rgba(var(--theme-primary-rgb), 0.46);
		color: var(--theme-text-primary);
	}

	.action-edit {
		background: rgba(var(--theme-primary-rgb), 0.1);
		border-color: rgba(var(--theme-primary-rgb), 0.34);
		color: var(--theme-primary-hover);
	}

	.action-muted {
		background: var(--theme-input-bg);
		border-color: var(--theme-glass-border);
		color: var(--theme-text-primary);
	}

	/* .action-danger {
		width: auto;
		min-width: 148px;
		background: rgba(239, 68, 68, 0.14);
		border-color: rgba(220, 38, 38, 0.42);
		color: #dc2626;
	}

	.action-danger:hover {
		background: rgba(239, 68, 68, 0.2);
	} */

	.modal-backdrop {
		position: fixed;
		inset: 0;
		z-index: 120;
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 1rem;
		background: var(--theme-modal-backdrop, rgba(15, 23, 42, 0.45));
		backdrop-filter: blur(12px) saturate(125%);
		-webkit-backdrop-filter: blur(12px) saturate(125%);
	}

	.modal-card {
		width: min(620px, 96vw);
		max-height: min(82dvh, 760px);
		border-radius: 1.2rem;
		border: 1px solid color-mix(in srgb, var(--theme-glass-border) 70%, rgba(255, 255, 255, 0.45));
		background: linear-gradient(
			165deg,
			color-mix(in srgb, var(--theme-modal-surface) 94%, var(--theme-surface)) 0%,
			color-mix(in srgb, var(--theme-modal-surface) 88%, var(--theme-input-bg)) 100%
		);
		box-shadow:
			0 24px 58px rgba(15, 23, 42, 0.24),
			inset 0 1px 0 rgba(255, 255, 255, 0.42);
		overflow: hidden;
		display: flex;
		flex-direction: column;
	}

	.modal-head {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 1rem 1.1rem;
		border-bottom: 1px solid var(--theme-glass-border);
		background: color-mix(in srgb, var(--theme-surface) 88%, transparent);
	}

	.modal-head h3 {
		margin: 0;
		font-size: 1.1rem;
		color: var(--theme-text-primary);
	}

	.modal-close {
		border: none;
		background: none;
		font-size: 1.45rem;
		line-height: 1;
		cursor: pointer;
		color: var(--theme-text-secondary);
	}

	.modal-body {
		display: flex;
		flex-direction: column;
		gap: 0.82rem;
		padding: 1rem 1.1rem;
		overflow: auto;
		flex: 1;
		min-height: 0;
	}

	.input {
		width: 100%;
		padding: 0.75rem 0.9rem;
		border-radius: 0.9rem;
		border: 1px solid color-mix(in srgb, var(--theme-glass-border) 72%, rgba(255, 255, 255, 0.5));
		background: color-mix(in srgb, var(--theme-input-bg) 88%, var(--theme-surface));
		color: var(--theme-text-primary);
		font: inherit;
		box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.28);
	}

	.input:focus,
	.file-input:focus {
		outline: none;
		border-color: rgba(var(--theme-primary-rgb), 0.55);
		box-shadow: 0 0 0 2px rgba(var(--theme-primary-rgb), 0.18);
	}

	.textarea {
		resize: vertical;
		min-height: 120px;
	}

	.file-input-group {
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
	}

	.file-label {
		font-size: 0.8rem;
		font-weight: 700;
		color: var(--theme-text-secondary);
	}

	.file-input {
		width: 100%;
		padding: 0.68rem 0.8rem;
		border-radius: 0.9rem;
		border: 1px solid color-mix(in srgb, var(--theme-glass-border) 72%, rgba(255, 255, 255, 0.5));
		background: color-mix(in srgb, var(--theme-input-bg) 88%, var(--theme-surface));
		color: var(--theme-text-primary);
		font: inherit;
		box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.28);
	}

	.upload-progress {
		display: flex;
		align-items: center;
		gap: 0.55rem;
		margin-top: 0.3rem;
	}

	.progress-bar-track {
		flex: 1;
		height: 6px;
		border-radius: 999px;
		overflow: hidden;
		background: rgba(var(--theme-primary-rgb), 0.2);
	}

	.progress-bar-fill {
		height: 100%;
		background: linear-gradient(90deg, var(--theme-primary), var(--theme-primary-hover));
		transition: width 0.2s ease;
	}

	.progress-text {
		font-size: 0.75rem;
		font-weight: 700;
		color: var(--theme-text-secondary);
		min-width: 30px;
		text-align: right;
	}

	.progress-detail {
		width: 100%;
		font-size: 0.7rem;
		color: var(--theme-text-secondary);
		margin-top: 0.3rem;
		font-style: italic;
	}

	.modal-actions {
		display: flex;
		justify-content: space-between;
		gap: 0.55rem;
		padding: 0.78rem 1.1rem 1.1rem;
	}

	.modal-actions .action-btn {
		flex: 1;
	}

	.generation-notice-card {
		width: min(520px, 94vw);
	}

	.generation-notice-message {
		margin: 0;
		line-height: 1.55;
		color: var(--theme-text-primary);
	}

	.topics-loading {
		display: flex;
		align-items: center;
		gap: 0.7rem;
		padding: 1rem;
		color: var(--theme-text-secondary);
	}

	.topics-empty {
		margin: 0;
		padding: 0.8rem 0.2rem;
		color: var(--theme-text-muted);
	}

	.doc-list {
		padding: 0.35rem 0 0.8rem;
	}

	.doc-row {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.75rem;
		padding: 0.65rem 1rem;
		border-radius: 0.8rem;
		border-top: 1px solid var(--theme-glass-border);
		background: color-mix(in srgb, var(--theme-surface) 90%, var(--theme-input-bg));
	}

	.doc-main {
		flex: 1;
		min-width: 0;
	}

	.doc-name {
		font-weight: 600;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.doc-meta {
		color: var(--theme-text-secondary);
		font-size: 0.82rem;
	}

	.doc-progress-track {
		margin-top: 0.45rem;
		height: 6px;
		border-radius: 999px;
		overflow: hidden;
		background: rgba(255, 255, 255, 0.12);
	}

	.doc-progress-fill {
		height: 100%;
		background: linear-gradient(90deg, var(--theme-primary), var(--theme-primary-hover));
		transition: width 0.3s ease;
	}

	.doc-progress-detail {
		margin-top: 0.35rem;
		font-size: 0.76rem;
		color: var(--theme-text-muted);
	}

	.danger-btn {
		padding: 0.4rem 0.72rem;
		border-radius: 10px;
		border: 1px solid rgba(233, 69, 96, 0.45);
		background: rgba(233, 69, 96, 0.14);
		color: #b91c1c;
		cursor: pointer;
		font: inherit;
		font-size: 0.82rem;
	}

	.modal-error {
		margin: 0 1rem 0.8rem;
		padding: 0.55rem 0.65rem;
		border-radius: 10px;
		background: rgba(233, 69, 96, 0.12);
		border: 1px solid rgba(233, 69, 96, 0.3);
		color: #b91c1c;
		font-size: 0.85rem;
	}



	:global([data-color-mode='dark']) .modal-card {
		border-color: rgba(255, 255, 255, 0.18);
		box-shadow: 0 24px 54px rgba(0, 0, 0, 0.42), inset 0 1px 0 rgba(255, 255, 255, 0.12);
	}

	:global([data-color-mode='dark']) .input,
	:global([data-color-mode='dark']) .file-input,
	:global([data-color-mode='dark']) .doc-row {
		box-shadow: none;
	}

	:global([data-color-mode='light']) .modal-backdrop {
		background: rgba(15, 23, 42, 0.28);
	}

	:global([data-color-mode='light']) .modal-card {
		border-color: rgba(148, 163, 184, 0.38);
		background: linear-gradient(165deg, rgba(255, 255, 255, 0.97) 0%, rgba(248, 250, 252, 0.95) 100%);
		box-shadow: 0 24px 52px rgba(15, 23, 42, 0.16), inset 0 1px 0 rgba(255, 255, 255, 0.96);
	}

	:global([data-color-mode='light']) .modal-head {
		background: rgba(248, 250, 252, 0.72);
	}

	:global([data-color-mode='light']) .topics-table-shell {
		border-color: rgba(148, 163, 184, 0.5);
	}

	:global([data-color-mode='light']) .topics-table th {
		border-right-color: rgba(148, 163, 184, 0.42);
		border-bottom-color: rgba(148, 163, 184, 0.42);
	}

	:global([data-color-mode='light']) .topics-table td {
		border-right-color: rgba(148, 163, 184, 0.38);
		border-bottom-color: rgba(148, 163, 184, 0.38);
	}

	:global([data-color-mode='light']) .input,
	:global([data-color-mode='light']) .file-input {
		background: rgba(255, 255, 255, 0.96);
		border-color: rgba(148, 163, 184, 0.46);
		color: var(--theme-text-primary);
	}

	:global([data-color-mode='light']) .doc-row {
		background: rgba(255, 255, 255, 0.9);
	}

	.topic-doc-list {
		margin-top: 0.25rem;
	}

	.spinner-sm {
		width: 18px;
		height: 18px;
		border: 2px solid rgba(17, 24, 39, 0.18);
		border-top-color: var(--theme-primary);
		border-radius: 50%;
		animation: spin 0.8s linear infinite;
	}

	.center-state {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		min-height: 56vh;
		gap: 0.8rem;
		text-align: center;
		color: var(--theme-text-muted);
	}

	.topic-section {
		display: flex;
		flex-direction: column;
		flex: 1;
		min-height: 0;
	}

	.desktop-only {
		display: block !important;
	}

	.mobile-only {
		display: none !important;
	}

	.mobile-topic-list {
		display: grid;
		gap: 0.7rem;
	}

	.mobile-topic-card {
		border: 1px solid color-mix(in srgb, var(--theme-glass-border) 86%, transparent);
		border-radius: 0.9rem;
		padding: 0.72rem;
		display: flex;
		flex-direction: column;
		gap: 0.6rem;
		background: color-mix(in srgb, var(--theme-glass-bg) 90%, transparent);
	}

	.mobile-metrics {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 0.3rem 0.65rem;
		font-size: 0.8rem;
		color: var(--theme-text-muted);
	}

	.mobile-metrics strong {
		color: var(--theme-text-primary);
	}

	:global([data-color-mode='dark']) .topics-table-shell {
		background: color-mix(in srgb, var(--theme-glass-bg) 78%, rgba(15, 23, 42, 0.4));
		border-color: color-mix(in srgb, var(--theme-glass-border) 82%, rgba(255, 255, 255, 0.06));
	}

	:global([data-color-mode='dark']) .topics-table th {
		background: color-mix(in srgb, var(--theme-glass-bg) 70%, rgba(15, 23, 42, 0.55));
	}

	:global([data-color-mode='dark']) .topic-name {
		color: var(--theme-text-primary);
	}

	:global([data-color-mode='dark']) .topic-description {
		color: var(--theme-text-secondary);
	}

	.spinner {
		width: 30px;
		height: 30px;
		border-radius: 50%;
		border: 3px solid rgba(255,255,255,0.14);
		border-top-color: var(--theme-primary);
		animation: spin 0.8s linear infinite;
	}

	.error-banner {
		padding: 0.9rem 1rem;
		border-radius: 1rem;
		background: rgba(239, 68, 68, 0.12);
		border: 1px solid rgba(239, 68, 68, 0.3);
		color: #b91c1c;
	}

	.amber-text { color: var(--theme-primary); }
	/* .blue-text { color: var(--theme-primary); } */
	.white-text { color: var(--theme-text-primary); }
	.orange-text { color: var(--theme-primary); }
	.green-text { color: #059669; }
	.red-text { color: #dc2626; }
	.violet-text { color: var(--theme-primary); }

	@keyframes spin {
		to { transform: rotate(360deg); }
	}

	@media (max-width: 920px) {
		.desktop-only {
			display: none !important;
		}

		.mobile-only {
			display: grid !important;
		}

		.page {
			height: auto;
			overflow: visible;
		}

		.stats-grid {
			grid-template-columns: 1fr 1fr;
		}

		.topics-table th,
		.topics-table td {
			padding: 0.56rem 0.44rem;
			font-size: 0.8rem;
		}

		.topic-col {
			width: 44%;
		}

		.metric-col {
			width: 9.33%;
		}

		.topic-inline-actions .action-btn {
			min-width: 82px;
			height: 34px;
			font-size: 0.72rem;
			padding: 0.34rem 0.58rem;
		}

		.topic-index {
			width: 28px;
			height: 28px;
			font-size: 0.76rem;
		}

		.section-head {
			flex-direction: column;
			align-items: flex-start;
		}

		.hero-top {
			flex-direction: column;
			align-items: flex-start;
		}

		.topics-table-shell {
			max-height: none;
		}
	}

	.syllabus-field-wrapper {
		position: relative;
	}

	.syllabus-expand-btn {
		position: absolute;
		top: 6px;
		right: 6px;
		width: 28px;
		height: 28px;
		border-radius: 0.5rem;
		border: 1px solid var(--theme-glass-border);
		background: var(--theme-glass-bg, rgba(255, 255, 255, 0.12));
		color: var(--theme-text-muted);
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 1rem;
		transition: background 0.15s, color 0.15s;
		z-index: 1;
	}

	.syllabus-expand-btn:hover {
		background: var(--theme-primary);
		color: #fff;
	}

	.syllabus-expand-backdrop {
		z-index: 1100;
	}

	.syllabus-expand-card {
		width: min(900px, 96vw);
		height: min(80dvh, 700px);
		border-radius: 1.2rem;
		border: 1px solid color-mix(in srgb, var(--theme-glass-border) 70%, rgba(255, 255, 255, 0.45));
		background: linear-gradient(
			165deg,
			color-mix(in srgb, var(--theme-modal-surface) 94%, var(--theme-surface)) 0%,
			color-mix(in srgb, var(--theme-modal-surface) 88%, var(--theme-input-bg)) 100%
		);
		box-shadow:
			0 24px 58px rgba(15, 23, 42, 0.24),
			inset 0 1px 0 rgba(255, 255, 255, 0.42);
		overflow: hidden;
		display: flex;
		flex-direction: column;
	}

	.syllabus-expand-body {
		flex: 1;
		padding: 1rem;
		display: flex;
		flex-direction: column;
		min-height: 0;
	}

	.syllabus-expand-textarea {
		flex: 1;
		resize: none;
		font-size: 0.92rem;
		line-height: 1.6;
	}

	/* Modal Edit/History tab bar */
	.modal-head-tabs {
		display: flex;
		align-items: center;
		gap: 1rem;
	}

	.modal-tab-bar {
		display: flex;
		gap: 0.25rem;
		background: var(--theme-glass-bg, rgba(255, 255, 255, 0.08));
		border-radius: 0.5rem;
		padding: 2px;
	}

	.modal-tab {
		padding: 0.3rem 0.7rem;
		border-radius: 0.4rem;
		border: none;
		background: transparent;
		color: var(--theme-text-muted);
		font-size: 0.78rem;
		font-weight: 600;
		cursor: pointer;
		transition: all 0.15s;
	}

	.modal-tab.active {
		background: var(--theme-primary);
		color: #fff;
	}

	.modal-tab:hover:not(.active) {
		color: var(--theme-text-primary);
	}

	.edit-topic-card {
		height: min(86dvh, 800px);
	}

	/* History tab body */
	.history-body {
		flex: 1;
	}

	/* Vertical timeline */
	.audit-timeline {
		position: relative;
		padding-left: 1.5rem;
	}

	.audit-timeline::before {
		content: '';
		position: absolute;
		left: 7px;
		top: 0;
		bottom: 0;
		width: 2px;
		background: var(--theme-glass-border, rgba(255, 255, 255, 0.12));
		border-radius: 1px;
	}

	.timeline-item {
		position: relative;
		padding-bottom: 1.25rem;
		display: flex;
		gap: 0.75rem;
	}

	.timeline-item:last-child {
		padding-bottom: 0;
	}

	.timeline-dot {
		position: absolute;
		left: -1.5rem;
		top: 4px;
		width: 12px;
		height: 12px;
		border-radius: 50%;
		background: var(--theme-primary);
		border: 2px solid var(--theme-surface, #1e293b);
		z-index: 1;
		flex-shrink: 0;
	}

	.timeline-content {
		flex: 1;
		min-width: 0;
	}

	.timeline-header {
		display: flex;
		align-items: center;
		gap: 0.35rem;
		flex-wrap: wrap;
		font-size: 0.82rem;
	}

	.timeline-user {
		font-weight: 700;
		color: var(--theme-text-primary);
	}

	.timeline-action {
		color: var(--theme-text-muted);
		font-style: italic;
	}

	.timeline-field {
		padding: 0.1rem 0.4rem;
		border-radius: 0.3rem;
		background: color-mix(in srgb, var(--theme-primary) 18%, transparent);
		color: var(--theme-primary);
		font-size: 0.72rem;
		font-weight: 600;
	}

	.timeline-date {
		font-size: 0.72rem;
		color: var(--theme-text-muted);
		margin-top: 0.2rem;
	}

	.timeline-diff {
		margin-top: 0.4rem;
		border-radius: 0.5rem;
		overflow: hidden;
		border: 1px solid var(--theme-glass-border);
		font-family: 'Menlo', 'Consolas', monospace;
		font-size: 0.75rem;
	}

	.diff-line {
		padding: 0.3rem 0.5rem;
		white-space: pre-wrap;
		word-break: break-word;
	}

	.diff-old {
		background: rgba(239, 68, 68, 0.1);
		color: #fca5a5;
	}

	.diff-new {
		background: rgba(34, 197, 94, 0.1);
		color: #86efac;
	}

	.diff-prefix {
		font-weight: 700;
		margin-right: 0.35rem;
		opacity: 0.7;
	}

	.doc-uploader {
		font-style: italic;
		color: var(--theme-primary);
	}

	.doc-name.clickable {
		cursor: pointer;
		color: var(--theme-primary);
		text-decoration: underline;
		text-decoration-color: transparent;
		transition: text-decoration-color 0.2s;
	}

	.doc-name.clickable:hover {
		text-decoration-color: var(--theme-primary);
	}

	/* Preview Modal */
	.preview-backdrop {
		z-index: 1200;
	}

	.preview-card {
		width: min(1000px, 98vw);
		height: min(90dvh, 900px);
	}

	.preview-body {
		padding: 0;
		display: flex;
		flex: 1;
		flex-direction: column;
	}

	.pdf-frame {
		width: 100%;
		height: 100%;
		flex: 1;
		border: none;
		border-radius: 0 0 1.2rem 1.2rem;
		background: #fff; /* PDF viewer is typically white */
	}

</style>
