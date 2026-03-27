/** Documents API — file upload and management. */
import { apiFetch, apiUrl } from './client';

export interface DocumentResponse {
	id: string;
	filename: string;
	file_size_bytes: number;
	mime_type: string | null;
	processing_status: string;
	total_chunks: number | null;
	index_type: string;
	upload_timestamp: string;
	subject_id: string | null;
}

export interface ReferenceDocumentItem {
	id: string;
	filename: string;
	file_size_bytes: number;
	mime_type: string | null;
	index_type: 'reference_book' | 'template_paper' | 'reference_questions' | string;
	subject_id: string | null;
	topic_id: string | null;
	processing_status: string;
	total_chunks: number | null;
	upload_timestamp: string | null;
	processed_at: string | null;
	parsed_question_count?: number | null;
	uploaded_by_name?: string;
}

export interface ReferenceDocumentsResponse {
	reference_books: ReferenceDocumentItem[];
	template_papers: ReferenceDocumentItem[];
	reference_questions: ReferenceDocumentItem[];
}

export interface DocumentStatusResponse {
	document_id: string;
	filename: string;
	status: string;
	total_chunks: number | null;
	total_tokens: number | null;
	processed_at: string | null;
	processing_step?: string;
	processing_progress?: number;
	processing_detail?: string;
	total_pages?: number;
	extraction_method?: string;
	used_ocr?: boolean;
	error?: string;
}

export async function uploadDocument(
	file: File,
	subjectId?: string,
	indexType: string = 'primary',
	topicId?: string
): Promise<DocumentResponse> {
	const form = new FormData();
	form.append('file', file);

	// When subject_id is provided, use the reference upload endpoint
	// which properly links documents to subjects
	if (subjectId) {
		form.append('subject_id', subjectId);
		form.append('index_type', indexType);
		if (topicId) {
			form.append('topic_id', topicId);
		}
		return apiFetch<DocumentResponse>('/documents/reference/upload', {
			method: 'POST',
			body: form,
		});
	}

	// Generic upload (no subject linkage)
	return apiFetch<DocumentResponse>('/documents/upload', {
		method: 'POST',
		body: form,
	});
}

export async function listDocuments(
	page = 1,
	limit = 50,
	subjectId?: string
): Promise<{ documents: DocumentResponse[]; pagination: Record<string, number> }> {
	const params = new URLSearchParams({ page: String(page), limit: String(limit) });
	if (subjectId) params.set('subject_id', subjectId);
	return apiFetch(`/documents?${params}`);
}

export async function listReferenceDocuments(subjectId?: string, topicId?: string): Promise<ReferenceDocumentsResponse> {
	const params = new URLSearchParams();
	if (subjectId) params.set('subject_id', subjectId);
	if (topicId) params.set('topic_id', topicId);
	const suffix = params.toString() ? `?${params.toString()}` : '';
	return apiFetch<ReferenceDocumentsResponse>(`/documents/reference/list${suffix}`);
}

export async function deleteDocumentById(documentId: string): Promise<void> {
	await apiFetch(`/documents/${documentId}`, {
		method: 'DELETE',
	});
}

export async function getDocumentStatus(documentId: string): Promise<DocumentStatusResponse> {
	return apiFetch<DocumentStatusResponse>(`/documents/${documentId}/status`);
}

// ── Question generation (SSE) ──

export interface GenerationEvent {
	status: 'uploading' | 'processing' | 'generating' | 'complete' | 'error';
	progress: number;
	message?: string;
	document_id?: string;
	session_id?: string;
	questions_generated?: number;
	question?: Record<string, unknown>;
	processing_progress?: number;
	processing_step?: string;
	processing_detail?: string;
	processing_document?: string;
	processing_documents_total?: number;
}

export interface BackgroundGenerationScheduleResponse {
	status: 'scheduled' | 'already_running' | 'skipped_no_reference' | 'queued';
	message: string;
	subject_id: string;
	run_id?: string | null;
	count: number;
	types?: string[];
	difficulty?: string;
	queue_position?: number;
}

export interface BackgroundGenerationStatusItem {
	in_progress: boolean;
	run_id?: string | null;
	status: string;
	progress: number;
	current_question: number;
	total_questions?: number | null;
	started_total_questions?: number | null;
	target_total_questions?: number | null;
	message?: string;
	updated_at?: string | null;
	/** Client-only: timestamp (ms) when the completed indicator was first shown. */
	_completedAt?: number;
}

export interface BackgroundGenerationStatusesResponse {
	statuses: Record<string, BackgroundGenerationStatusItem>;
}

export async function scheduleBackgroundGeneration(opts: {
	subjectId: string;
	count: number;
	types?: string;
	difficulty?: string;
	topicId?: string;
	topicIds?: string[];
	allowWithoutReference?: boolean;
}): Promise<BackgroundGenerationScheduleResponse> {
	const form = new FormData();
	form.append('subject_id', opts.subjectId);
	form.append('count', String(opts.count));
	form.append('types', opts.types ?? 'mcq');
	form.append('difficulty', opts.difficulty ?? 'medium');
	if (opts.topicId) {
		form.append('topic_id', opts.topicId);
	}
	if (opts.topicIds && opts.topicIds.length > 0) {
		form.append('topic_ids', opts.topicIds.join(','));
	}
	if (opts.allowWithoutReference) {
		form.append('allow_without_reference', 'true');
	}

	return apiFetch<BackgroundGenerationScheduleResponse>('/questions/schedule-background-generation', {
		method: 'POST',
		body: form,
	});
}

export async function getBackgroundGenerationStatuses(subjectIds: string[]): Promise<BackgroundGenerationStatusesResponse> {
	if (!subjectIds.length) return { statuses: {} };
	const params = new URLSearchParams({ subject_ids: subjectIds.join(',') });
	return apiFetch<BackgroundGenerationStatusesResponse>(`/questions/background-generation-statuses?${params.toString()}`);
}

export interface TopicGenerationStatusItem {
	run_id: string;
	subject_id: string;
	topic_id: string;
	in_progress: boolean;
	status: string;
	progress: number;
	current_question: number;
	total_questions: number;
	target_total_questions?: number;
	message?: string;
	updated_at?: string | null;
	started_at?: string | null;
	completed_at?: string | null;
}

export interface TopicGenerationStatusesResponse {
	statuses: Record<string, TopicGenerationStatusItem>;
}

export async function getTopicGenerationStatuses(topicIds: string[]): Promise<TopicGenerationStatusesResponse> {
	if (!topicIds.length) return { statuses: {} };
	const params = new URLSearchParams({ topic_ids: topicIds.join(',') });
	return apiFetch<TopicGenerationStatusesResponse>(`/questions/topic-generation-statuses?${params.toString()}`);
}

/**
 * Generate questions from a subject's indexed documents via SSE.
 * Calls POST /questions/quick-generate-from-subject.
 * Yields parsed GenerationEvent objects as they arrive.
 */
export async function cancelGeneration(subjectId: string): Promise<void> {
	const form = new FormData();
	form.append('subject_id', subjectId);
	try {
		await apiFetch('/questions/cancel-generation', { method: 'POST', body: form });
	} catch {
		// best-effort — ignore errors
	}
}

export async function* generateChapter(opts: {
	topicId: string;
	count?: number;
	types?: string;
	difficulty?: string;
	signal?: AbortSignal;
}): AsyncGenerator<GenerationEvent> {
	const { getStoredSession } = await import('./client');
	const session = getStoredSession();

	const count = opts.count ?? 10;
	const qType = opts.types ?? 'mcq';
	const marksMap: Record<string, number> = { mcq: 1, short_answer: 2, long_answer: 5 };
	// Build question_types dict: e.g. { "mcq": { "count": 10, "marks_each": 1 } }
	const questionTypes: Record<string, { count: number; marks_each: number }> = {};
	for (const t of qType.split(',')) {
		const tt = t.trim();
		if (tt) questionTypes[tt] = { count, marks_each: marksMap[tt] ?? 2 };
	}

	const body = JSON.stringify({
		topic_id: opts.topicId,
		question_types: questionTypes,
		difficulty: opts.difficulty ?? 'medium',
	});

	const res = await fetch(apiUrl('/questions/generate-chapter'), {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json',
			...(session?.access_token ? { Authorization: `Bearer ${session.access_token}` } : {}),
		},
		body,
		signal: opts.signal,
	});

	if (!res.ok) {
		const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
		throw new Error(err.detail || `Generation failed (${res.status})`);
	}

	const reader = res.body?.getReader();
	if (!reader) throw new Error('No response body');

	const decoder = new TextDecoder();
	let buffer = '';

	while (true) {
		const { done, value } = await reader.read();
		if (done) break;
		buffer += decoder.decode(value, { stream: true });

		const lines = buffer.split('\n');
		buffer = lines.pop() ?? '';

		for (const line of lines) {
			const trimmed = line.trim();
			if (trimmed.startsWith('data: ')) {
				const json = trimmed.slice(6);
				if (json === '[DONE]') return;
				try {
					yield JSON.parse(json) as GenerationEvent;
				} catch {
					// skip non-JSON heartbeat lines
				}
			}
		}
	}
}

export async function* generateFromSubject(opts: {
	subjectId: string;
	context: string;
	count?: number;
	types?: string;
	difficulty?: string;
	topicId?: string;
	allowWithoutReference?: boolean;
	signal?: AbortSignal;
}): AsyncGenerator<GenerationEvent> {
	const { getStoredSession } = await import('./client');
	const session = getStoredSession();

	const form = new FormData();
	form.append('subject_id', opts.subjectId);
	form.append('context', opts.context);
	form.append('count', String(opts.count ?? 3));
	form.append('types', opts.types ?? 'mcq');
	form.append('difficulty', opts.difficulty ?? 'medium');
	if (opts.topicId) form.append('topic_id', opts.topicId);
	if (opts.allowWithoutReference) form.append('allow_without_reference', 'true');

	const res = await fetch(apiUrl('/questions/quick-generate-from-subject'), {
		method: 'POST',
		headers: session?.access_token ? { Authorization: `Bearer ${session.access_token}` } : {},
		body: form,
		signal: opts.signal,
	});

	if (!res.ok) {
		const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
		throw new Error(err.detail || `Generation failed (${res.status})`);
	}

	const reader = res.body?.getReader();
	if (!reader) throw new Error('No response body');

	const decoder = new TextDecoder();
	let buffer = '';

	while (true) {
		const { done, value } = await reader.read();
		if (done) break;
		buffer += decoder.decode(value, { stream: true });

		const lines = buffer.split('\n');
		buffer = lines.pop() ?? '';

		for (const line of lines) {
			const trimmed = line.trim();
			if (trimmed.startsWith('data: ')) {
				const json = trimmed.slice(6);
				if (json === '[DONE]') return;
				try {
					yield JSON.parse(json) as GenerationEvent;
				} catch {
					// skip non-JSON heartbeat lines
				}
			}
		}
	}
}
