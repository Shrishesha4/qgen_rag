import { apiUrl, getStoredSession } from './client';

export type InquiryLevel = 'beginner' | 'advanced' | 'pro';

export interface InquiryMessage {
	role: 'user' | 'assistant';
	content: string;
}

export interface InquiryStreamEvent {
	type: 'meta' | 'delta' | 'complete' | 'error';
	delta?: string | null;
	message?: string | null;
	provider_key?: string | null;
	provider_name?: string | null;
	provider_model?: string | null;
}

async function parseStreamError(res: Response): Promise<Error> {
	const fallback = `Request failed (${res.status})`;
	try {
		const body = await res.json();
		const detail =
			typeof body?.detail === 'string'
				? body.detail
				: typeof body?.message === 'string'
					? body.message
					: fallback;
		return new Error(detail || fallback);
	} catch {
		return new Error(fallback);
	}
}

export async function* streamConversationalInquiry(opts: {
	subjectId?: string | null;
	topicId?: string | null;
	level: InquiryLevel;
	mode: 'question' | 'answer_feedback' | 'reasoning_feedback';
	questionCycleIndex: number;
	explanationAttempt?: number;
	messages: InquiryMessage[];
	signal?: AbortSignal;
}): AsyncGenerator<InquiryStreamEvent> {
	const session = getStoredSession();
	const res = await fetch(apiUrl('/questions/conversational-inquiry'), {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json',
			...(session?.access_token ? { Authorization: `Bearer ${session.access_token}` } : {}),
		},
		body: JSON.stringify({
			subject_id: opts.subjectId ?? null,
			topic_id: opts.topicId ?? null,
			level: opts.level,
			mode: opts.mode,
			question_cycle_index: opts.questionCycleIndex,
			explanation_attempt: opts.explanationAttempt ?? 0,
			messages: opts.messages,
		}),
		signal: opts.signal,
	});

	if (!res.ok) {
		throw await parseStreamError(res);
	}

	const reader = res.body?.getReader();
	if (!reader) {
		throw new Error('No response body');
	}

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
			if (!trimmed || trimmed.startsWith(':')) continue;
			if (!trimmed.startsWith('data: ')) continue;

			const payload = trimmed.slice(6);
			if (payload === '[DONE]') return;

			try {
				yield JSON.parse(payload) as InquiryStreamEvent;
			} catch {
				// Ignore keepalive and partial lines.
			}
		}
	}

	const remaining = buffer.trim();
	if (remaining.startsWith('data: ')) {
		try {
			yield JSON.parse(remaining.slice(6)) as InquiryStreamEvent;
		} catch {
			// Ignore trailing partial data.
		}
	}
}