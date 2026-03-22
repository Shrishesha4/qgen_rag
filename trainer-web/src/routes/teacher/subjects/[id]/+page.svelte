<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { session } from '$lib/session';
	import { createTopic, getSubject, updateTopic, type SubjectDetailResponse, type TopicResponse } from '$lib/api/subjects';
	import {
		deleteDocumentById,
		getDocumentStatus,
		getBackgroundGenerationStatuses,
		listReferenceDocuments,
		scheduleBackgroundGeneration,
		uploadDocument,
		type ReferenceDocumentItem,
	} from '$lib/api/documents';
	import { getQuestionsForVetting } from '$lib/api/vetting';

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

	let showEditTopicModal = $state(false);
	let editingTopic = $state(false);
	let editTopicId = $state('');
	let editTopicName = $state('');
	let editTopicDescription = $state('');
	let editTopicSyllabus = $state('');

	let showReferenceModal = $state(false);
	let referenceTab = $state<'pdfs' | 'questions'>('pdfs');
	let referenceLoading = $state(false);
	let referenceUploading = $state(false);
	let deletingRefId = $state('');
	let referenceError = $state('');
	let pdfUploadType = $state<'reference_book' | 'template_paper'>('reference_book');
	let referenceBooks = $state<ReferenceDocumentItem[]>([]);
	let templatePapers = $state<ReferenceDocumentItem[]>([]);
	let referenceQuestions = $state<ReferenceDocumentItem[]>([]);
	let referenceProgressByDoc = $state<Record<string, number>>({});
	let referenceProgressDetailByDoc = $state<Record<string, string>>({});
	let referencePollTimer: ReturnType<typeof setInterval> | null = null;
	let selectedTopicId = $state('');
	let selectedTopicName = $state('');
	let topicDocuments = $state<Record<string, ReferenceDocumentItem[]>>({});
	let loadingTopicDocuments = $state('');
	let topicGeneratingById = $state<Record<string, boolean>>({});
	let topicGenerationProgressById = $state<Record<string, string>>({});
	let completedGenerationHoldByTopicId = $state<Record<string, boolean>>({});
	let generationPollTimer: ReturnType<typeof setInterval> | null = null;
	let generationPollingTopicId = $state<string | null>(null);
	let generationPollingRunId = $state<string | null>(null);
	let generationPollMisses = 0;

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
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to load subject';
		} finally {
			loading = false;
		}
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
			const allQuestions: Array<{ topic_id: string | null; vetting_status: string; version_number: number }> = [];

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
						version_number: Math.max(1, q.version_number || 1),
					}))
				);
				if (pageNo >= pageRes.pages || pageRes.questions.length === 0) break;
				pageNo += 1;
			}

			const perTopic: Record<string, ReviewStats> = {};
			const regeneratedByTopic: Record<string, number> = {};
			for (const topic of subject.topics) {
				perTopic[topic.id] = {
					generated: topic.total_questions,
					approved: 0,
					rejected: 0,
					pending: 0,
					vetted: 0,
					approvalRate: 0,
				};
				regeneratedByTopic[topic.id] = 0;
			}

			for (const q of allQuestions) {
				if (!q.topic_id || !perTopic[q.topic_id]) continue;
				const normalized = normalizeStatus(q.vetting_status);
				if (normalized === 'approved') perTopic[q.topic_id].approved += 1;
				else if (normalized === 'rejected') perTopic[q.topic_id].rejected += 1;
				else perTopic[q.topic_id].pending += 1;
				regeneratedByTopic[q.topic_id] += Math.max(0, q.version_number - 1);
			}

			let approvedTotal = 0;
			let rejectedTotal = 0;
			let pendingTotal = 0;
			let generatedTotal = 0;

			for (const topic of subject.topics) {
				const stats = perTopic[topic.id];
				stats.generated += regeneratedByTopic[topic.id] || 0;
				stats.vetted = stats.approved + stats.rejected;
				if (stats.pending === 0) {
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

	function vetTopic(topicId: string) {
		if (!subjectId) return;
		const params = new URLSearchParams({ subject: subjectId, topic: topicId, resume: '0' });
		goto(`/teacher/train/loop?${params.toString()}`);
	}

	async function generateTopic(topicId: string) {
		if (!subjectId || topicGeneratingById[topicId] || !!generationPollingTopicId) return;
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

	function openAddTopicModal() {
		addTopicName = '';
		addTopicDescription = '';
		addTopicSyllabus = '';
		addTopicBookPdf = null;
		addTopicQuestionPdf = null;
		showAddTopicModal = true;
	}

	function closeAddTopicModal() {
		if (addingTopic) return;
		showAddTopicModal = false;
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
				uploadTasks.push(uploadDocument(addTopicBookPdf, subjectId, 'reference_book', createdTopic.id));
			}
			if (addTopicQuestionPdf) {
				uploadTasks.push(uploadDocument(addTopicQuestionPdf, subjectId, 'reference_questions', createdTopic.id));
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
		}
	}

	function openEditTopicModal(topic: TopicResponse) {
		editTopicId = topic.id;
		editTopicName = topic.name;
		editTopicDescription = topic.description || '';
		editTopicSyllabus = topic.syllabus_content || '';
		showEditTopicModal = true;
	}

	function closeEditTopicModal() {
		if (editingTopic) return;
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

	function getTopicDocumentCount(topicId: string): number {
		const booksAndTemplates = [...referenceBooks, ...templatePapers].filter((doc) => doc.topic_id === topicId).length;
		const questionRefs = referenceQuestions.filter((doc) => doc.topic_id === topicId).length;
		return booksAndTemplates + questionRefs;
	}

	function buildTopicDocumentsMap(): Record<string, ReferenceDocumentItem[]> {
		const topics = subject?.topics || [];
		if (!topics.length) return {};
		const grouped: Record<string, ReferenceDocumentItem[]> = {};
		for (const topic of topics) {
			grouped[topic.id] = [...referenceBooks, ...templatePapers].filter((doc) => doc.topic_id === topic.id);
		}
		return grouped;
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
		if (!showReferenceModal || !hasAnyProcessingDocs()) return;
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
			topicDocuments = buildTopicDocumentsMap();
			await refreshReferenceProgressForProcessingDocs();
			ensureReferenceProgressPolling();
		} catch (e: unknown) {
			referenceError = e instanceof Error ? e.message : 'Failed to load reference materials';
		} finally {
			if (withLoader) referenceLoading = false;
		}
	}

	async function openReferenceModal() {
		referenceError = '';
		referenceTab = 'pdfs';
		selectedTopicId = '';
		selectedTopicName = '';
		topicDocuments = {};
		showReferenceModal = true;
		await loadReferenceMaterials();
	}

	function closeReferenceModal() {
		clearReferencePolling();
		showReferenceModal = false;
		referenceError = '';
		selectedTopicId = '';
		selectedTopicName = '';
		topicDocuments = {};
		referenceBooks = [];
		templatePapers = [];
		referenceQuestions = [];
		referenceProgressByDoc = {};
		referenceProgressDetailByDoc = {};
	}

	function selectTopic(topicId: string, topicName: string) {
		selectedTopicId = topicId;
		selectedTopicName = topicName;
		void loadTopicDocuments(topicId);
	}

	async function loadTopicDocuments(topicId: string) {
		if (topicDocuments[topicId]) return;
		loadingTopicDocuments = topicId;
		try {
			const topicDocs = [...referenceBooks, ...templatePapers].filter((doc) => doc.topic_id === topicId);
			topicDocuments = { ...topicDocuments, [topicId]: topicDocs };
		} finally {
			loadingTopicDocuments = '';
		}
	}

	async function uploadTopicPdf(event: Event, indexType: 'reference_book' | 'template_paper' | 'reference_questions') {
		const input = event.target as HTMLInputElement;
		const file = input.files?.[0];
		if (!file || !subjectId || !selectedTopicId || referenceUploading) return;

		referenceUploading = true;
		referenceError = '';
		try {
			await uploadDocument(file, subjectId, indexType, selectedTopicId);
			await loadReferenceMaterials();
			topicDocuments = {};
			await loadTopicDocuments(selectedTopicId);
			await loadSubject();
		} catch (e: unknown) {
			referenceError = e instanceof Error ? e.message : 'Upload failed';
		} finally {
			referenceUploading = false;
			input.value = '';
		}
	}

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
				<div>
					<p class="eyebrow">{subject.code}</p>
					<h1 class="title font-serif">{subject.name}</h1>
				</div>
			</div>
			{#if subject.description}
				<p class="description">{subject.description}</p>
			{/if}
		</div>

		<div class="stats-grid animate-slide-up">
			<div class="stat-card glass-panel">
				<span class="stat-value amber-text">{subject.total_topics}</span>
				<span class="stat-label">Topics</span>
			</div>
			<div class="stat-card glass-panel">
				<span class="stat-value white-text">{statsLoading ? '…' : subjectReviewStats.generated}</span>
				<span class="stat-label">Generated</span>
			</div>
			<div class="stat-card glass-panel">
				<span class="stat-value blue-text">{statsLoading ? '…' : subjectReviewStats.vetted}</span>
				<span class="stat-label">Vetted</span>
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
					<button class="action-btn action-reference" onclick={openReferenceModal}>References</button>
					<button class="action-btn action-add-topic" onclick={openAddTopicModal}>Add Topic</button>
				</div>
			</div>

			{#if subject.topics.length === 0}
				<div class="center-state compact">
					<p>No topics available for this subject yet.</p>
				</div>
			{:else}
				<div class="topic-list">
					{#each subject.topics as topic, index}
						<div class="topic-card">
							<div class="topic-index">{index + 1}</div>
							<div class="topic-body">
								<div class="topic-header">
									<div>
										<h3 class="topic-name">{topic.name}</h3>
										{#if topic.description}
											<p class="topic-description">{topic.description}</p>
										{/if}
									</div>
									<div class="topic-actions-edge">
										{#if canGenerateTopic(topic.id, topic.total_questions, topic.total_questions)}
											<button class="action-btn action-generate" class:generating={!!topicGeneratingById[topic.id]} onclick={() => generateTopic(topic.id)} disabled={!!topicGeneratingById[topic.id] || !!generationPollingTopicId}>
												{#if topicGeneratingById[topic.id]}
													<span class="btn-spinner" aria-hidden="true"></span>
													<span>Generating {topicGenerationProgressById[topic.id] || ''}</span>
												{:else}
													<span>Generate</span>
												{/if}
											</button>
										{:else}
											<span class="action-slot-spacer" aria-hidden="true"></span>
										{/if}
										<button class="action-btn action-vet" onclick={() => vetTopic(topic.id)}>Vet</button>
										<button class="action-btn action-edit" onclick={() => openEditTopicModal(topic)}>Edit</button>
									</div>
								</div>
								<div class="topic-metrics">
									<div class="metric"><span>Generated</span><strong>{topicReviewStats[topic.id]?.generated ?? topic.total_questions}</strong></div>
									<div class="metric"><span>Vetted</span><strong>{topicReviewStats[topic.id]?.vetted ?? 0}</strong></div>
									<div class="metric"><span>Pending</span><strong>{topicReviewStats[topic.id]?.pending ?? topic.total_questions}</strong></div>
									<div class="metric"><span>Approved</span><strong class="green-text">{topicReviewStats[topic.id]?.approved ?? 0}</strong></div>
									<div class="metric"><span>Rejected</span><strong class="red-text">{topicReviewStats[topic.id]?.rejected ?? 0}</strong></div>
									<div class="metric"><span>Approval Rate</span><strong class="violet-text">{topicReviewStats[topic.id]?.approvalRate ?? 0}%</strong></div>
								</div>
							</div>
						</div>
					{/each}
				</div>
			{/if}
		</div>
	{/if}
</div>

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
						onchange={(e) => {
							const target = e.currentTarget as HTMLInputElement;
							addTopicBookPdf = target.files?.[0] ?? null;
						}}
					/>
				</div>
				<div class="file-input-group">
					<label class="file-label" for="questionPdf">Question PDF (optional)</label>
					<input
						id="questionPdf"
						class="file-input"
						type="file"
						accept=".pdf,application/pdf"
						onchange={(e) => {
							const target = e.currentTarget as HTMLInputElement;
							addTopicQuestionPdf = target.files?.[0] ?? null;
						}}
					/>
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
		<div class="modal-card" role="dialog" aria-modal="true" tabindex="-1" onclick={(e) => e.stopPropagation()}>
			<div class="modal-head">
				<h3>Edit Topic</h3>
				<button class="modal-close" onclick={closeEditTopicModal} aria-label="Close">✕</button>
			</div>
			<div class="modal-body">
				<label class="input-label" for="editTopicName">Topic name</label>
				<input id="editTopicName" class="input" placeholder="Topic name" bind:value={editTopicName} />
				<label class="input-label" for="editTopicDescription">Description</label>
				<input id="editTopicDescription" class="input" placeholder="Description" bind:value={editTopicDescription} />
				<label class="input-label" for="editTopicSyllabus">Syllabus content</label>
				<textarea id="editTopicSyllabus" class="input textarea" rows="4" placeholder="Syllabus content" bind:value={editTopicSyllabus}></textarea>
			</div>
			<div class="modal-actions">
				<button class="action-btn action-muted" onclick={closeEditTopicModal}>Cancel</button>
				<button class="action-btn action-edit" onclick={submitEditTopic} disabled={editingTopic || !editTopicName.trim()}>
					{editingTopic ? 'Saving...' : 'Save Changes'}
				</button>
			</div>
		</div>
	</div>
{/if}

{#if showReferenceModal}
	<div class="modal-backdrop" role="button" tabindex="0" aria-label="Close" onclick={closeReferenceModal} onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && closeReferenceModal()}>
		<div
			class="modal reference-modal"
			role="dialog"
			aria-modal="true"
			tabindex="0"
			onclick={(e) => e.stopPropagation()}
			onkeydown={(e) => e.stopPropagation()}
		>
			<div class="modal-header">
				<h3>Reference Materials • {subject?.name ?? ''}</h3>
				<button class="close-btn" onclick={closeReferenceModal}>✕</button>
			</div>

			{#if referenceError}
				<p class="modal-error">{referenceError}</p>
			{/if}

			{#if referenceLoading}
				<div class="topics-loading"><div class="spinner-sm"></div><span>Loading materials…</span></div>
			{:else}
				<div class="topic-accordion-list">
					{#if subject?.topics?.length}
						{#each subject.topics as topic, index}
							<div class="topic-accordion-panel glass-panel-frosted" class:expanded={selectedTopicId === topic.id}>
								<button
									type="button"
									class="topic-accordion-header"
									aria-expanded={selectedTopicId === topic.id}
									onclick={() =>
										selectedTopicId === topic.id
											? ((selectedTopicId = ''), (selectedTopicName = ''))
											: selectTopic(topic.id, topic.name)}
								>
									<div class="topic-accordion-title-wrap">
										<span class="topic-accordion-index">{index + 1}</span>
										<span class="topic-accordion-title">{topic.name}</span>
									</div>
									<div class="topic-accordion-header-right">
										<span class="topic-status-pill">
											{#if getTopicDocumentCount(topic.id) > 0}
												Ready
											{:else}
												Empty
											{/if}
										</span>
										<span class="topic-accordion-chevron" class:expanded={selectedTopicId === topic.id}>▾</span>
									</div>
								</button>

								<div class="topic-accordion-body-wrap" class:expanded={selectedTopicId === topic.id}>
									<div class="topic-accordion-body">
										<div class="syllabus-block">
											<h4>Syllabus Content</h4>
											<div class="syllabus-preview">{topic.syllabus_content || `Paste or type the syllabus content for this topic...`}</div>
										</div>

										<div class="topic-material-tabs">
											<button type="button" class="topic-material-tab" class:active={referenceTab === 'pdfs'} onclick={() => (referenceTab = 'pdfs')}>
												📚 Reference Books
											</button>
											<button type="button" class="topic-material-tab" class:active={referenceTab === 'questions'} onclick={() => (referenceTab = 'questions')}>
												❖ Reference Questions
												<span class="optional-copy">optional</span>
											</button>
										</div>

										{#if referenceTab === 'pdfs'}
											<p class="topic-upload-copy">Upload textbooks or notes for &quot;{topic.name}&quot;</p>
											<label class="upload-dropzone glass-panel-frosted">
												<input type="file" accept=".pdf,.doc,.docx,.txt" oninput={(e) => uploadTopicPdf(e, pdfUploadType)} disabled={referenceUploading} />
												<div class="upload-dropzone-icon">📁</div>
												<div class="upload-dropzone-title">{referenceUploading ? 'Uploading…' : 'Drop files or click to upload'}</div>
												<div class="upload-dropzone-subtitle">PDF, Word, PowerPoint, or Text</div>
											</label>
											<div class="upload-type-row">
												<select bind:value={pdfUploadType} class="select-input topic-inline-select">
													<option value="reference_book">Reference Book PDF</option>
													<option value="template_paper">Template Paper PDF</option>
												</select>
											</div>
											<div class="doc-list topic-doc-list">
												{#if loadingTopicDocuments === topic.id}
													<div class="topics-loading"><div class="spinner-sm"></div><span>Loading PDFs…</span></div>
												{:else if topicDocuments[topic.id]?.length}
													{#each topicDocuments[topic.id] as doc}
														<div class="doc-row">
															<div class="doc-main">
																<div class="doc-name">{doc.filename}</div>
																<div class="doc-meta">{doc.index_type.replace('_', ' ')} • {doc.processing_status}</div>
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
										{:else}
											<p class="topic-upload-copy">Upload question files for &quot;{topic.name}&quot;</p>
											<label class="upload-dropzone glass-panel-frosted question-dropzone">
												<input type="file" accept=".pdf,.xlsx,.csv" oninput={(e) => uploadTopicPdf(e, 'reference_questions')} disabled={referenceUploading} />
												<div class="upload-dropzone-icon">❖</div>
												<div class="upload-dropzone-title">{referenceUploading ? 'Uploading…' : 'Drop files or click to upload'}</div>
												<div class="upload-dropzone-subtitle">PDF, XLSX, or CSV</div>
											</label>
											<div class="doc-list topic-doc-list">
												{#each referenceQuestions.filter((doc) => doc.topic_id === topic.id) as doc}
													<div class="doc-row">
														<div class="doc-main">
															<div class="doc-name">{doc.filename}</div>
															<div class="doc-meta">
																{doc.processing_status}
																{#if doc.parsed_question_count !== null && doc.parsed_question_count !== undefined}
																	• {doc.parsed_question_count} parsed
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
												{:else}
													<p class="topics-empty">No reference question files uploaded yet.</p>
												{/each}
											</div>
										{/if}
									</div>
								</div>
							</div>
						{/each}
					{:else}
						<div class="empty-state">
							<div class="empty-icon">📚</div>
							<p>No topics found. Please add topics first.</p>
						</div>
					{/if}
				</div>
			{/if}
		</div>
	</div>
{/if}

<style>
	.page {
		max-width: 1120px;
		margin: 0 auto;
		padding: 2rem 1.5rem 2.5rem;
		display: flex;
		flex-direction: column;
		gap: 1rem;
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
		justify-content: space-between;
		align-items: flex-start;
		gap: 1rem;
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
		grid-template-columns: repeat(7, minmax(0, 1fr));
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

	.topic-list {
		display: flex;
		flex-direction: column;
		gap: 0.85rem;
	}

	.topic-card {
		display: flex;
		gap: 1rem;
		padding: 1rem;
		border-radius: 1rem;
		border: 1px solid rgba(17, 24, 39, 0.1);
		background: rgba(255, 255, 255, 0.72);
	}

	.topic-index {
		width: 40px;
		height: 40px;
		border-radius: 50%;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		flex-shrink: 0;
		background: rgba(var(--theme-primary-rgb), 0.15);
		color: var(--theme-primary);
		font-weight: 800;
	}

	.topic-body {
		flex: 1;
		display: flex;
		flex-direction: column;
		gap: 0.9rem;
	}

	.topic-header {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		gap: 1rem;
	}

	.topic-name {
		margin: 0;
		font-size: 1rem;
		color: var(--theme-text-primary);
	}

	.topic-description {
		margin: 0.3rem 0 0;
		color: var(--theme-text-muted);
		line-height: 1.55;
	}

	.topic-metrics {
		display: grid;
		grid-template-columns: repeat(6, minmax(0, 1fr));
		gap: 0.75rem;
	}

	.metric {
		display: flex;
		flex-direction: column;
		gap: 0.1rem;
	}

	.metric span {
		font-size: 0.72rem;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		color: var(--theme-text-muted);
	}

	.metric strong {
		font-size: 0.96rem;
		color: var(--theme-text-primary);
	}

	.topic-actions-edge {
		display: grid;
		grid-template-columns: repeat(3, 128px);
		gap: 0.55rem;
		width: 100%;
		justify-content: end;
		align-self: flex-start;
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

	.action-slot-spacer {
		width: 100%;
		height: 44px;
		visibility: hidden;
		pointer-events: none;
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

	.action-reference {
		background: rgba(var(--theme-primary-rgb), 0.12);
		border-color: rgba(var(--theme-primary-rgb), 0.36);
		color: var(--theme-primary);
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

	.input-label {
		font-size: 0.8rem;
		font-weight: 700;
		color: var(--theme-text-secondary);
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

	.modal-actions {
		display: flex;
		justify-content: space-between;
		gap: 0.55rem;
		padding: 0.78rem 1.1rem 1.1rem;
	}

	.modal-actions .action-btn {
		flex: 1;
	}

	.modal {
		width: min(820px, 96vw);
		max-height: 86vh;
		overflow: auto;
		border-radius: 20px;
		border: 1px solid var(--theme-modal-border);
		background: linear-gradient(
			165deg,
			color-mix(in srgb, var(--theme-modal-surface) 94%, var(--theme-surface)) 0%,
			color-mix(in srgb, var(--theme-modal-surface) 88%, var(--theme-input-bg)) 100%
		);
		box-shadow:
			0 24px 52px rgba(15, 23, 42, 0.24),
			inset 0 1px 0 rgba(255, 255, 255, 0.4);
	}

	.reference-modal {
		width: min(900px, 96vw);
		max-height: 90vh;
		border-radius: 20px;
		border: 1px solid color-mix(in srgb, var(--theme-glass-border) 70%, rgba(255, 255, 255, 0.5));
		background: linear-gradient(
			165deg,
			color-mix(in srgb, var(--theme-modal-surface) 95%, var(--theme-surface)) 0%,
			color-mix(in srgb, var(--theme-modal-surface) 90%, var(--theme-input-bg)) 100%
		);
		backdrop-filter: blur(16px) saturate(140%);
		-webkit-backdrop-filter: blur(16px) saturate(140%);
		box-shadow: 0 24px 54px rgba(15, 23, 42, 0.24), inset 0 1px 0 rgba(255, 255, 255, 0.52);
	}

	.modal-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 1rem 1.1rem;
		border-bottom: 1px solid var(--theme-glass-border);
		background: color-mix(in srgb, var(--theme-surface) 88%, transparent);
	}

	.modal-header h3 {
		margin: 0;
		font-size: 1rem;
		color: var(--theme-text-primary);
	}

	.close-btn {
		background: none;
		border: none;
		color: var(--theme-text-secondary);
		font-size: 1.45rem;
		line-height: 1;
		cursor: pointer;
	}

	.glass-panel-frosted {
		backdrop-filter: blur(10px) saturate(150%);
		-webkit-backdrop-filter: blur(10px) saturate(150%);
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

	.select-input {
		min-height: 40px;
		padding: 0.55rem 0.8rem;
		border-radius: 0.75rem;
		border: 1px solid var(--theme-glass-border);
		background: var(--theme-input-bg);
		color: var(--theme-text-primary);
		font: inherit;
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

	.topic-accordion-list {
		display: flex;
		flex-direction: column;
		gap: 0.8rem;
		padding: 0.75rem 0.85rem 1rem;
	}

	.topic-accordion-panel {
		padding: 0;
		border-radius: 1.5rem;
		overflow: hidden;
		border: 1px solid color-mix(in srgb, var(--theme-glass-border) 75%, rgba(255, 255, 255, 0.4));
		background: linear-gradient(
			145deg,
			color-mix(in srgb, var(--theme-surface) 92%, rgba(var(--theme-primary-rgb), 0.08)) 0%,
			color-mix(in srgb, var(--theme-input-bg) 88%, rgba(var(--theme-primary-rgb), 0.04)) 100%
		);
		box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.36);
	}

	.topic-accordion-panel.expanded {
		border-color: rgba(var(--theme-primary-rgb), 0.55);
		box-shadow: 0 12px 30px rgba(15, 23, 42, 0.12), 0 0 0 1px rgba(var(--theme-primary-rgb), 0.18), inset 0 1px 0 rgba(255, 255, 255, 0.18);
	}

	.topic-accordion-header {
		width: 100%;
		padding: 1.15rem 1.35rem;
		border: 0;
		background: transparent;
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1rem;
		color: inherit;
		font: inherit;
		text-align: left;
		cursor: pointer;
	}

	.topic-accordion-title-wrap {
		display: flex;
		align-items: center;
		gap: 0.95rem;
		min-width: 0;
	}

	.topic-accordion-header-right {
		display: flex;
		align-items: center;
		gap: 0.85rem;
		flex-shrink: 0;
	}

	.topic-status-pill {
		padding: 0.42rem 0.9rem;
		border-radius: 999px;
		background: color-mix(in srgb, var(--theme-input-bg) 90%, rgba(var(--theme-primary-rgb), 0.12));
		border: 1px solid color-mix(in srgb, var(--theme-glass-border) 68%, rgba(255, 255, 255, 0.5));
		color: var(--theme-text-secondary);
		font-size: 0.85rem;
		font-weight: 700;
	}

	.topic-accordion-chevron {
		font-size: 1rem;
		color: var(--theme-text-secondary);
		transition: transform 0.2s ease;
	}

	.topic-accordion-chevron.expanded {
		transform: rotate(180deg);
	}

	.topic-accordion-body {
		min-height: 0;
		overflow: hidden;
		transform-origin: top;
		transform: translateY(-8px);
		opacity: 0;
		transition: transform 0.22s ease, opacity 0.22s ease;
		padding: 0 1.2rem 1.2rem;
		display: flex;
		flex-direction: column;
		gap: 1.2rem;
	}

	.topic-accordion-body-wrap {
		display: grid;
		grid-template-rows: 0fr;
		min-height: 0;
		overflow: hidden;
		transition: grid-template-rows 0.24s ease;
	}

	.topic-accordion-body-wrap.expanded {
		grid-template-rows: 1fr;
	}

	.topic-accordion-body-wrap.expanded .topic-accordion-body {
		transform: translateY(0);
		opacity: 1;
	}

	.syllabus-block h4 {
		margin: 0 0 0.8rem;
		font-size: 1.1rem;
		font-weight: 800;
		color: var(--theme-text);
	}

	.syllabus-preview {
		min-height: 140px;
		padding: 1.2rem 1.3rem;
		border-radius: 1.3rem;
		background: color-mix(in srgb, var(--theme-input-bg) 90%, var(--theme-surface));
		border: 1px solid color-mix(in srgb, var(--theme-glass-border) 70%, rgba(255, 255, 255, 0.4));
		box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.5);
		font-size: 1rem;
		line-height: 1.65;
		color: var(--theme-text-primary);
		white-space: pre-wrap;
	}

	.topic-material-tabs {
		display: grid;
		grid-template-columns: 1fr 1fr;
		align-items: end;
		border-bottom: 1px solid var(--theme-glass-border);
	}

	.topic-material-tab {
		border: 0;
		background: transparent;
		padding: 1rem 1rem 0.9rem;
		color: var(--theme-text-primary);
		font: inherit;
		font-size: 1rem;
		font-weight: 800;
		text-align: left;
		cursor: pointer;
		border-bottom: 3px solid transparent;
		opacity: 0.7;
	}

	.topic-material-tab.active {
		background: color-mix(in srgb, rgba(var(--theme-primary-rgb), 0.26) 58%, transparent);
		border-bottom-color: var(--theme-primary);
		opacity: 1;
		color: var(--theme-primary);
	}

	.optional-copy {
		margin-left: 0.55rem;
		font-size: 0.9rem;
		font-style: italic;
		font-weight: 400;
		color: var(--theme-text-secondary);
	}

	.topic-upload-copy {
		margin: 0;
		font-size: 0.98rem;
		color: var(--theme-text-secondary);
	}

	.upload-dropzone {
		position: relative;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 0.7rem;
		min-height: 230px;
		padding: 1.75rem;
		border-radius: 1.7rem;
		border: 2px dashed color-mix(in srgb, var(--theme-glass-border) 85%, rgba(var(--theme-primary-rgb), 0.22));
		background: linear-gradient(
			180deg,
			color-mix(in srgb, var(--theme-surface) 84%, rgba(var(--theme-primary-rgb), 0.12)) 0%,
			color-mix(in srgb, var(--theme-input-bg) 82%, rgba(var(--theme-primary-rgb), 0.08)) 100%
		);
		text-align: center;
		cursor: pointer;
		overflow: hidden;
	}

	:global([data-color-mode='dark']) .modal-card,
	:global([data-color-mode='dark']) .reference-modal {
		border-color: rgba(255, 255, 255, 0.18);
		box-shadow: 0 24px 54px rgba(0, 0, 0, 0.42), inset 0 1px 0 rgba(255, 255, 255, 0.12);
	}

	:global([data-color-mode='dark']) .input,
	:global([data-color-mode='dark']) .file-input,
	:global([data-color-mode='dark']) .syllabus-preview,
	:global([data-color-mode='dark']) .doc-row,
	:global([data-color-mode='dark']) .topic-status-pill {
		box-shadow: none;
	}

	:global([data-color-mode='dark']) .topic-accordion-panel.expanded {
		box-shadow: 0 14px 34px rgba(0, 0, 0, 0.34), 0 0 0 1px rgba(var(--theme-primary-rgb), 0.24), inset 0 1px 0 rgba(255, 255, 255, 0.08);
	}

	:global([data-color-mode='dark']) .upload-dropzone {
		border-color: rgba(var(--theme-primary-rgb), 0.32);
	}

	:global([data-color-mode='dark']) .topic-status-pill {
		color: var(--theme-text-primary);
	}

	:global([data-color-mode='light']) .modal-backdrop {
		background: rgba(15, 23, 42, 0.28);
	}

	:global([data-color-mode='light']) .modal-card,
	:global([data-color-mode='light']) .reference-modal {
		border-color: rgba(148, 163, 184, 0.38);
		background: linear-gradient(165deg, rgba(255, 255, 255, 0.97) 0%, rgba(248, 250, 252, 0.95) 100%);
		box-shadow: 0 24px 52px rgba(15, 23, 42, 0.16), inset 0 1px 0 rgba(255, 255, 255, 0.96);
	}

	:global([data-color-mode='light']) .modal-head,
	:global([data-color-mode='light']) .modal-header {
		background: rgba(248, 250, 252, 0.72);
	}

	:global([data-color-mode='light']) .input,
	:global([data-color-mode='light']) .file-input,
	:global([data-color-mode='light']) .select-input,
	:global([data-color-mode='light']) .syllabus-preview {
		background: rgba(255, 255, 255, 0.96);
		border-color: rgba(148, 163, 184, 0.46);
		color: var(--theme-text-primary);
	}

	:global([data-color-mode='light']) .topic-accordion-panel {
		background: linear-gradient(145deg, rgba(255, 255, 255, 0.96), rgba(248, 250, 252, 0.92));
		border-color: rgba(148, 163, 184, 0.42);
		box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.95);
	}

	:global([data-color-mode='light']) .doc-row {
		background: rgba(255, 255, 255, 0.9);
	}

	.upload-dropzone input {
		position: absolute;
		inset: 0;
		opacity: 0;
		cursor: pointer;
	}

	.upload-dropzone-icon {
		font-size: 2.8rem;
		line-height: 1;
	}

	.upload-dropzone-title {
		font-size: 1.1rem;
		font-weight: 800;
		color: var(--theme-text-primary);
	}

	.upload-dropzone-subtitle {
		font-size: 0.95rem;
		color: var(--theme-text-secondary);
	}

	.upload-type-row {
		display: flex;
		justify-content: flex-start;
	}

	.topic-inline-select {
		width: min(280px, 100%);
	}

	.topic-doc-list {
		margin-top: 0.25rem;
	}

	.empty-state {
		text-align: center;
		padding: 3rem 2rem;
		color: var(--theme-text-muted);
	}

	.empty-icon {
		font-size: 2.5rem;
		margin-bottom: 1rem;
		opacity: 0.6;
	}

	.empty-state p {
		margin: 0;
		font-size: 0.95rem;
		font-style: italic;
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
	.blue-text { color: var(--theme-primary); }
	.white-text { color: var(--theme-text-primary); }
	.orange-text { color: var(--theme-primary); }
	.green-text { color: #059669; }
	.red-text { color: #dc2626; }
	.violet-text { color: var(--theme-primary); }

	@keyframes spin {
		to { transform: rotate(360deg); }
	}

	@media (max-width: 920px) {
		.stats-grid {
			grid-template-columns: 1fr 1fr;
		}

		.topic-header {
			flex-direction: column;
		}

		.topic-actions-edge {
			grid-template-columns: 1fr;
			width: 100%;
		}

		.topic-metrics {
			grid-template-columns: 1fr 1fr;
		}

		.section-head {
			flex-direction: column;
			align-items: flex-start;
		}
	}
</style>
