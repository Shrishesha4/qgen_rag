<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { session } from '$lib/session';
	import {
		listSubjects,
		getSubject,
		createTopic,
		type SubjectResponse,
		type TopicResponse,
	} from '$lib/api/subjects';
	import {
		listReferenceDocuments,
		uploadDocument,
		deleteDocumentById,
		type ReferenceDocumentItem,
	} from '$lib/api/documents';

	onMount(() => {
		const unsub = session.subscribe((s) => {
			if (!s) goto('/teacher/login');
		});
		loadSubjects();
		return unsub;
	});

	let subjects = $state<SubjectResponse[]>([]);
	let loading = $state(true);
	let error = $state('');

	let expandedId = $state('');
	let topicsMap = $state<Record<string, TopicResponse[]>>({});
	let loadingTopics = $state('');
	let addingTopicFor = $state('');
	let showAddTopicModal = $state(false);
	let addTopicSubjectId = $state('');
	let addTopicSubjectName = $state('');
	let addTopicName = $state('');
	let addTopicSyllabus = $state('');

	let showReferenceModal = $state(false);
	let referenceSubjectId = $state('');
	let referenceSubjectName = $state('');
	let referenceTab = $state<'pdfs' | 'questions'>('pdfs');
	let referenceLoading = $state(false);
	let referenceUploading = $state(false);
	let deletingRefId = $state('');
	let referenceError = $state('');
	let pdfUploadType = $state<'reference_book' | 'template_paper'>('reference_book');
	let referenceBooks = $state<ReferenceDocumentItem[]>([]);
	let templatePapers = $state<ReferenceDocumentItem[]>([]);
	let referenceQuestions = $state<ReferenceDocumentItem[]>([]);

	async function loadSubjects() {
		loading = true;
		error = '';
		try {
			const res = await listSubjects(1, 100);
			subjects = res.subjects;
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to load subjects';
		} finally {
			loading = false;
		}
	}

	async function refreshSubject(subjectId: string) {
		try {
			const detail = await getSubject(subjectId);
			topicsMap = { ...topicsMap, [subjectId]: detail.topics };
			subjects = subjects.map((s) =>
				s.id === subjectId
					? {
						...s,
						total_topics: detail.total_topics,
						total_questions: detail.total_questions,
					}
					: s
			);
		} catch {
			// keep stale view on refresh failure
		}
	}

	async function toggleSubject(id: string) {
		if (expandedId === id) {
			expandedId = '';
			return;
		}
		expandedId = id;
		if (!topicsMap[id]) {
			loadingTopics = id;
			try {
				const detail = await getSubject(id);
				topicsMap = { ...topicsMap, [id]: detail.topics };
			} catch {
				topicsMap = { ...topicsMap, [id]: [] };
			} finally {
				loadingTopics = '';
			}
		}
	}

	function trainTopic(subjectId: string, topicId: string) {
		goto(`/teacher/train/loop?subject=${subjectId}&topic=${topicId}`);
	}

	function openAddTopicModal(subject: SubjectResponse) {
		addTopicSubjectId = subject.id;
		addTopicSubjectName = subject.name;
		addTopicName = '';
		addTopicSyllabus = '';
		error = '';
		showAddTopicModal = true;
	}

	function closeAddTopicModal() {
		showAddTopicModal = false;
		addTopicSubjectId = '';
		addTopicSubjectName = '';
		addTopicName = '';
		addTopicSyllabus = '';
	}

	async function addTopicRow(subjectId: string) {
		const name = addTopicName.trim();
		const syllabus = addTopicSyllabus.trim();
		if (!name || addingTopicFor) return;

		addingTopicFor = subjectId;
		error = '';
		try {
			const currentTopics = topicsMap[subjectId] || [];
			await createTopic(subjectId, {
				name,
				subject_id: subjectId,
				order_index: currentTopics.length,
				syllabus_content: syllabus || undefined,
			});

			closeAddTopicModal();
			await refreshSubject(subjectId);
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Failed to add topic';
		} finally {
			addingTopicFor = '';
		}
	}

	function formatDate(iso: string): string {
		return new Date(iso).toLocaleDateString('en-US', {
			month: 'short',
			day: 'numeric',
			year: 'numeric',
		});
	}

	async function openReferenceModal(subject: SubjectResponse) {
		referenceSubjectId = subject.id;
		referenceSubjectName = subject.name;
		referenceTab = 'pdfs';
		referenceError = '';
		showReferenceModal = true;
		await loadReferenceMaterials(subject.id);
	}

	function closeReferenceModal() {
		showReferenceModal = false;
		referenceSubjectId = '';
		referenceSubjectName = '';
		referenceError = '';
		referenceBooks = [];
		templatePapers = [];
		referenceQuestions = [];
	}

	async function loadReferenceMaterials(subjectId: string) {
		referenceLoading = true;
		referenceError = '';
		try {
			const res = await listReferenceDocuments(subjectId);
			referenceBooks = res.reference_books || [];
			templatePapers = res.template_papers || [];
			referenceQuestions = res.reference_questions || [];
		} catch (e: unknown) {
			referenceError = e instanceof Error ? e.message : 'Failed to load reference materials';
		} finally {
			referenceLoading = false;
		}
	}

	async function uploadReferenceFile(event: Event, indexType: 'reference_book' | 'template_paper' | 'reference_questions') {
		const input = event.target as HTMLInputElement;
		const file = input.files?.[0];
		if (!file || !referenceSubjectId || referenceUploading) return;

		referenceUploading = true;
		referenceError = '';
		try {
			await uploadDocument(file, referenceSubjectId, indexType);
			await loadReferenceMaterials(referenceSubjectId);
			await refreshSubject(referenceSubjectId);
		} catch (e: unknown) {
			referenceError = e instanceof Error ? e.message : 'Upload failed';
		} finally {
			referenceUploading = false;
			input.value = '';
		}
	}

	async function deleteReference(docId: string) {
		if (!referenceSubjectId || deletingRefId) return;
		deletingRefId = docId;
		referenceError = '';
		try {
			await deleteDocumentById(docId);
			await loadReferenceMaterials(referenceSubjectId);
		} catch (e: unknown) {
			referenceError = e instanceof Error ? e.message : 'Delete failed';
		} finally {
			deletingRefId = '';
		}
	}
</script>

<svelte:head>
	<title>Existing Topics — QGen Trainer</title>
</svelte:head>

<div class="page">
	{#if loading}
		<div class="center-state">
			<div class="spinner"></div>
			<p>Loading subjects…</p>
		</div>
	{:else if error}
		<div class="center-state">
			<span class="err-icon">⚠️</span>
			<p class="err-msg">{error}</p>
			<button class="glass-btn" onclick={loadSubjects}>Retry</button>
		</div>
	{:else if subjects.length === 0}
		<div class="center-state">
			<span class="empty-icon">📭</span>
			<p>No subjects created yet</p>
			<button class="glass-btn" onclick={() => goto('/teacher/train/new')}>
				Create New Topic
			</button>
		</div>
	{:else}
		<div class="subject-list">
			{#each subjects as s}
				<div class="subject-card glass-card" class:expanded={expandedId === s.id}>
					<button class="sc-header" onclick={() => toggleSubject(s.id)}>
						<div class="sc-top">
							<span class="sc-code">{s.code}</span>
							<span class="sc-arrow">{expandedId === s.id ? '▼' : '▶'}</span>
						</div>
						<h2 class="sc-name">{s.name}</h2>
						<div class="sc-stats">
							<span class="sc-stat">📝 {s.total_questions} questions</span>
							<span class="sc-stat">📚 {s.total_topics} topics</span>
							<span class="sc-stat">📅 {formatDate(s.created_at)}</span>
						</div>
					</button>

					{#if expandedId === s.id}
						<div class="topics-panel">
							<div class="subject-actions">
								<button class="glass-btn small-btn" onclick={() => openAddTopicModal(s)}>Add Topic</button>
								<button class="glass-btn small-btn" onclick={() => openReferenceModal(s)}>Reference</button>
							</div>

							{#if loadingTopics === s.id}
								<div class="topics-loading">
									<div class="spinner-sm"></div>
									<span>Loading topics…</span>
								</div>
							{:else if topicsMap[s.id]?.length}
								{#each topicsMap[s.id] as topic}
									<button class="topic-row" onclick={() => trainTopic(s.id, topic.id)}>
										<div class="tr-left">
											<span class="tr-name">{topic.name}</span>
										</div>
										<div class="tr-right">
											<span class="tr-qs">{topic.total_questions} Qs</span>
											<span class="tr-arrow">→</span>
										</div>
									</button>
								{/each}
							{:else}
								<p class="topics-empty">No topics found for this subject</p>
							{/if}
						</div>
					{/if}
				</div>
			{/each}
		</div>
	{/if}

	{#if showReferenceModal}
		<div class="modal-backdrop" role="button" tabindex="0" aria-label="Close" onclick={closeReferenceModal} onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && closeReferenceModal()}>
			<div
				class="modal"
				role="dialog"
				aria-modal="true"
				tabindex="0"
				onclick={(e) => e.stopPropagation()}
				onkeydown={(e) => e.stopPropagation()}
			>
				<div class="modal-header">
					<h3>Reference Materials • {referenceSubjectName}</h3>
					<button class="close-btn" onclick={closeReferenceModal}>✕</button>
				</div>

				<div class="tab-row">
					<button class="tab-btn" class:active={referenceTab === 'pdfs'} onclick={() => (referenceTab = 'pdfs')}>Reference PDFs</button>
					<button class="tab-btn" class:active={referenceTab === 'questions'} onclick={() => (referenceTab = 'questions')}>Reference Questions</button>
				</div>

				{#if referenceError}
					<p class="modal-error">{referenceError}</p>
				{/if}

				{#if referenceLoading}
					<div class="topics-loading"><div class="spinner-sm"></div><span>Loading materials…</span></div>
				{:else if referenceTab === 'pdfs'}
					<div class="upload-row">
						<select bind:value={pdfUploadType} class="select-input">
							<option value="reference_book">Reference Book PDF</option>
							<option value="template_paper">Template Paper PDF</option>
						</select>
						<label class="glass-btn small-btn upload-btn">
							{referenceUploading ? 'Uploading...' : 'Add PDF'}
							<input type="file" accept=".pdf,.doc,.docx,.txt" oninput={(e) => uploadReferenceFile(e, pdfUploadType)} disabled={referenceUploading} />
						</label>
					</div>

					<div class="doc-list">
						{#each [...referenceBooks, ...templatePapers] as doc}
							<div class="doc-row">
								<div class="doc-main">
									<div class="doc-name">{doc.filename}</div>
									<div class="doc-meta">{doc.index_type.replace('_', ' ')} • {doc.processing_status}</div>
								</div>
								<button class="danger-btn" disabled={deletingRefId === doc.id} onclick={() => deleteReference(doc.id)}>
									{deletingRefId === doc.id ? 'Deleting...' : 'Delete'}
								</button>
							</div>
						{:else}
							<p class="topics-empty">No reference PDFs uploaded yet.</p>
						{/each}
					</div>
				{:else}
					<div class="upload-row">
						<label class="glass-btn small-btn upload-btn">
							{referenceUploading ? 'Uploading...' : 'Add Question File'}
							<input type="file" accept=".pdf,.xlsx,.csv" oninput={(e) => uploadReferenceFile(e, 'reference_questions')} disabled={referenceUploading} />
						</label>
					</div>

					<div class="doc-list">
						{#each referenceQuestions as doc}
							<div class="doc-row">
								<div class="doc-main">
									<div class="doc-name">{doc.filename}</div>
									<div class="doc-meta">
										{doc.processing_status}
										{#if doc.parsed_question_count !== null && doc.parsed_question_count !== undefined}
											• {doc.parsed_question_count} parsed
										{/if}
									</div>
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
	{/if}

	{#if showAddTopicModal}
		<div class="modal-backdrop" role="button" tabindex="0" aria-label="Close" onclick={closeAddTopicModal} onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && closeAddTopicModal()}>
			<div
				class="modal add-topic-modal"
				role="dialog"
				aria-modal="true"
				tabindex="0"
				onclick={(e) => e.stopPropagation()}
				onkeydown={(e) => e.stopPropagation()}
			>
				<div class="modal-header">
					<h3>Add Topic • {addTopicSubjectName}</h3>
					<button class="close-btn" onclick={closeAddTopicModal}>✕</button>
				</div>

				<div class="topic-create-fields topic-create-modal-fields">
					<input
						class="topic-input"
						type="text"
						placeholder="Add new topic"
						value={addTopicName}
						oninput={(e) => {
							addTopicName = (e.currentTarget as HTMLInputElement).value;
						}}
					/>
					<textarea
						class="syllabus-input"
						rows="3"
						placeholder="Syllabus content for this topic"
						value={addTopicSyllabus}
						oninput={(e) => {
							addTopicSyllabus = (e.currentTarget as HTMLTextAreaElement).value;
						}}
					></textarea>
				</div>

				<div class="modal-actions">
					<button class="glass-btn small-btn" onclick={closeAddTopicModal}>Cancel</button>
					<button
						class="glass-btn small-btn"
						disabled={addingTopicFor === addTopicSubjectId || !addTopicName.trim()}
						onclick={() => addTopicRow(addTopicSubjectId)}
					>
						{addingTopicFor === addTopicSubjectId ? 'Adding...' : 'Add Topic'}
					</button>
				</div>
			</div>
		</div>
	{/if}
</div>

<style>
	.page {
		max-width: 980px;
		margin: 0 auto;
		padding: 2rem 1.5rem;
		min-height: 100vh;
	}

	.center-state {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 1rem;
		padding: 4rem 1rem;
		text-align: center;
	}

	.center-state p {
		color: var(--theme-text-muted);
		margin: 0;
	}

	.spinner {
		width: 32px;
		height: 32px;
		border: 3px solid rgba(255, 255, 255, 0.15);
		border-top-color: var(--theme-primary);
		border-radius: 50%;
		animation: spin 0.8s linear infinite;
	}

	.spinner-sm {
		width: 18px;
		height: 18px;
		border: 2px solid rgba(255, 255, 255, 0.15);
		border-top-color: var(--theme-primary);
		border-radius: 50%;
		animation: spin 0.8s linear infinite;
	}

	@keyframes spin {
		to { transform: rotate(360deg); }
	}

	.err-icon { font-size: 2rem; }
	.err-msg { color: #e94560 !important; }
	.empty-icon { font-size: 3rem; }

	.subject-list {
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}

	.subject-card {
		padding: 0;
		width: 100%;
		overflow: hidden;
		transition: all 0.2s;
	}

	.subject-card.expanded {
		border-color: rgba(var(--theme-primary-rgb), 0.3);
	}

	.sc-header {
		display: block;
		text-align: left;
		cursor: pointer;
		padding: 1.25rem 1.5rem;
		width: 100%;
		font-family: inherit;
		background: none;
		border: none;
		color: inherit;
	}

	.sc-header:hover {
		background: rgba(255, 255, 255, 0.03);
	}

	.sc-top {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 0.5rem;
	}

	.sc-code {
		font-size: 0.7rem;
		font-weight: 700;
		padding: 0.15rem 0.5rem;
		background: rgba(var(--theme-primary-rgb), 0.15);
		color: var(--theme-primary);
		border-radius: 4px;
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}

	.sc-arrow {
		font-size: 0.75rem;
		color: var(--theme-text-muted);
	}

	.sc-name {
		font-size: 1.1rem;
		font-weight: 700;
		margin: 0 0 0.5rem;
		color: var(--theme-text);
	}

	.sc-stats {
		display: flex;
		gap: 1rem;
		flex-wrap: wrap;
	}

	.sc-stat {
		font-size: 0.82rem;
		color: var(--theme-text-muted);
	}

	.topics-panel {
		border-top: 0.5px solid rgba(255, 255, 255, 0.08);
		padding: 0.5rem 0;
	}

	.subject-actions {
		display: flex;
		justify-content: space-evenly;
		gap: 0.75rem;
		padding: 0.5rem 1.5rem 0.25rem;
	}

	.subject-actions .small-btn {
		flex: 1;
		max-width: 220px;
		text-align: center;
		align-self: stretch;
	}

	.topic-create-fields {
		flex: 1;
		display: flex;
		flex-direction: column;
		gap: 0.45rem;
	}

	.topic-create-modal-fields {
		padding: 0.9rem 1rem 0.25rem;
	}

	.topic-input,
	.syllabus-input,
	.select-input {
		width: 100%;
		padding: 0.55rem 0.7rem;
		border-radius: 10px;
		border: 1px solid rgba(255, 255, 255, 0.14);
		background: rgba(255, 255, 255, 0.04);
		color: var(--theme-text);
		font: inherit;
	}

	.syllabus-input {
		resize: vertical;
		min-height: 56px;
	}

	.small-btn {
		padding: 0.5rem 0.85rem;
		font-size: 0.82rem;
		align-self: flex-start;
	}

	.topics-loading {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 1rem 1.5rem;
		color: var(--theme-text-muted);
		font-size: 0.85rem;
	}

	.topics-empty {
		padding: 1rem 1.5rem;
		color: var(--theme-text-muted);
		font-size: 0.85rem;
		margin: 0;
	}

	.topic-row {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		text-align: left;
		width: 100%;
		padding: 0.8rem 1.5rem;
		background: none;
		border: none;
		border-bottom: 0.5px solid rgba(255, 255, 255, 0.04);
		color: var(--theme-text);
		cursor: pointer;
		font-family: inherit;
		font-size: 0.95rem;
		transition: background 0.15s;
		gap: 0.75rem;
	}

	.topic-row:last-child {
		border-bottom: none;
	}

	.topic-row:hover {
		background: rgba(var(--theme-primary-rgb), 0.08);
	}

	.tr-left {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		flex: 1;
		min-width: 0;
	}

	.tr-name {
		font-weight: 600;
		white-space: normal;
		word-break: break-word;
		line-height: 1.35;
	}

	/* .tr-badge {
		font-size: 0.75rem;
		padding: 0.16rem 0.48rem;
		background: rgba(var(--theme-primary-rgb), 0.12);
		border-radius: 999px;
		color: var(--theme-primary);
		flex-shrink: 0;
	} */

	.tr-right {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding-top: 0.1rem;
		flex-shrink: 0;
	}

	.tr-qs {
		font-size: 0.9rem;
		color: var(--theme-text-muted);
	}

	.tr-arrow {
		color: var(--theme-primary);
		font-weight: 700;
		font-size: 1.05rem;
	}

	.modal-backdrop {
		position: fixed;
		inset: 0;
		background: rgba(2, 8, 20, 0.62);
		backdrop-filter: blur(4px);
		display: grid;
		place-items: center;
		z-index: 80;
		padding: 1rem;
	}

	.modal {
		width: min(820px, 96vw);
		max-height: 86vh;
		overflow: auto;
		border-radius: 16px;
		border: 1px solid rgba(255, 255, 255, 0.16);
		background: rgba(8, 16, 30, 0.82);
		box-shadow: 0 20px 50px rgba(0, 0, 0, 0.34);
	}

	.add-topic-modal {
		width: min(560px, 94vw);
	}

	.modal-actions {
		display: flex;
		justify-content: flex-end;
		gap: 0.55rem;
		padding: 0.65rem 1rem 1rem;
	}

	.modal-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 0.9rem 1rem;
		border-bottom: 1px solid rgba(255, 255, 255, 0.08);
	}

	.modal-header h3 {
		margin: 0;
		font-size: 1rem;
	}

	.close-btn {
		background: none;
		border: none;
		color: var(--theme-text-muted);
		font-size: 1rem;
		cursor: pointer;
	}

	.tab-row {
		display: flex;
		gap: 0.5rem;
		padding: 0.75rem 1rem;
	}

	.tab-btn {
		padding: 0.48rem 0.85rem;
		border-radius: 999px;
		border: 1px solid rgba(255, 255, 255, 0.14);
		background: rgba(255, 255, 255, 0.04);
		color: var(--theme-text-muted);
		cursor: pointer;
		font: inherit;
	}

	.tab-btn.active {
		background: rgba(var(--theme-primary-rgb), 0.2);
		color: var(--theme-text);
		border-color: rgba(var(--theme-primary-rgb), 0.5);
	}

	.upload-row {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		padding: 0 1rem 0.75rem;
	}

	.upload-btn {
		position: relative;
		overflow: hidden;
	}

	.upload-btn input[type='file'] {
		position: absolute;
		inset: 0;
		opacity: 0;
		cursor: pointer;
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
		border-top: 1px solid rgba(255, 255, 255, 0.06);
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
		color: var(--theme-text-muted);
		font-size: 0.82rem;
	}

	.danger-btn {
		padding: 0.4rem 0.72rem;
		border-radius: 10px;
		border: 1px solid rgba(233, 69, 96, 0.45);
		background: rgba(233, 69, 96, 0.14);
		color: #ffb4c1;
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
		color: #ff9dad;
		font-size: 0.85rem;
	}

	@media (max-width: 768px) {
		.page {
			padding-top: 1rem;
		}

		.small-btn {
			align-self: stretch;
			text-align: center;
		}

		.tr-right {
			min-width: 72px;
			justify-content: flex-end;
		}

		.upload-row {
			flex-direction: column;
			align-items: stretch;
		}
	}
</style>
