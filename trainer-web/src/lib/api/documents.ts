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

export async function uploadDocument(
	file: File,
	subjectId?: string,
	indexType: string = 'primary'
): Promise<DocumentResponse> {
	const form = new FormData();
	form.append('file', file);

	// When subject_id is provided, use the reference upload endpoint
	// which properly links documents to subjects
	if (subjectId) {
		form.append('subject_id', subjectId);
		form.append('index_type', indexType);
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

// ── Question generation (SSE) ──

export interface GenerationEvent {
	status: 'uploading' | 'processing' | 'generating' | 'complete' | 'error';
	progress: number;
	message?: string;
	document_id?: string;
	session_id?: string;
	questions_generated?: number;
	question?: Record<string, unknown>;
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

export async function* generateFromSubject(opts: {
	subjectId: string;
	context: string;
	count?: number;
	types?: string;
	difficulty?: string;
	topicId?: string;
	signal?: AbortSignal;
}): AsyncGenerator<GenerationEvent> {
	const { getStoredSession } = await import('./client');
	const session = getStoredSession();

	const form = new FormData();
	form.append('subject_id', opts.subjectId);
	form.append('context', opts.context);
	form.append('count', String(opts.count ?? 10));
	form.append('types', opts.types ?? 'mcq');
	form.append('difficulty', opts.difficulty ?? 'medium');
	if (opts.topicId) form.append('topic_id', opts.topicId);

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
