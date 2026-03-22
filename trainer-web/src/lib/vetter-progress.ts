import { browser } from '$app/environment';
import {
	deleteTeacherVettingProgressRemote,
	listTeacherVettingProgressRemote,
	upsertTeacherVettingProgressRemote,
	type QuestionForVetting,
	type TeacherVettingProgressRecord,
} from '$lib/api/vetting';

const VETTER_PROGRESS_STORAGE_KEY = 'qgen:vetter-progress:v1';

export interface VetterProgressContext {
	subjectId?: string | null;
	topicId?: string | null;
}

export interface VetterProgressSnapshot {
	key: string;
	subjectId: string | null;
	topicId: string | null;
	questions: QuestionForVetting[];
	currentIndex: number;
	approvedQuestionIds: string[];
	rejectedQuestionIds: string[];
	updatedAt: string;
}

export type VetterProgressStore = Record<string, VetterProgressSnapshot>;

function toMillis(iso: string): number {
	const ts = Date.parse(iso);
	return Number.isFinite(ts) ? ts : 0;
}

function normalizeStringArray(value: unknown): string[] {
	if (!Array.isArray(value)) return [];
	return [...new Set(value.filter((item): item is string => typeof item === 'string').map((item) => item.trim()).filter(Boolean))];
}

export function buildVetterProgressKey(context: VetterProgressContext): string {
	const subjectId = (context.subjectId ?? '').trim() || 'all';
	const topicId = (context.topicId ?? '').trim() || 'all';
	return `${subjectId}|${topicId}`;
}

export function readVetterProgressStore(): VetterProgressStore {
	if (!browser) return {};
	try {
		const raw = window.localStorage.getItem(VETTER_PROGRESS_STORAGE_KEY);
		if (!raw) return {};
		const parsed = JSON.parse(raw) as Record<string, unknown>;
		if (!parsed || typeof parsed !== 'object') return {};

		const store: VetterProgressStore = {};
		for (const [key, value] of Object.entries(parsed)) {
			if (!value || typeof value !== 'object') continue;
			const candidate = value as Partial<VetterProgressSnapshot>;
			const questions = Array.isArray(candidate.questions)
				? (candidate.questions as QuestionForVetting[])
				: [];
			if (questions.length === 0) continue;

			store[key] = {
				key,
				subjectId:
					typeof candidate.subjectId === 'string' && candidate.subjectId.trim()
						? candidate.subjectId.trim()
						: null,
				topicId:
					typeof candidate.topicId === 'string' && candidate.topicId.trim()
						? candidate.topicId.trim()
						: null,
				questions,
				currentIndex: Number.isFinite(candidate.currentIndex)
					? Math.max(0, Math.min(questions.length - 1, Math.trunc(candidate.currentIndex as number)))
					: 0,
				approvedQuestionIds: normalizeStringArray(candidate.approvedQuestionIds),
				rejectedQuestionIds: normalizeStringArray(candidate.rejectedQuestionIds),
				updatedAt:
					typeof candidate.updatedAt === 'string' && candidate.updatedAt
						? candidate.updatedAt
						: new Date().toISOString(),
			};
		}
		return store;
	} catch {
		return {};
	}
}

export function writeVetterProgressStore(store: VetterProgressStore): void {
	if (!browser) return;
	try {
		window.localStorage.setItem(VETTER_PROGRESS_STORAGE_KEY, JSON.stringify(store));
	} catch {
		// Ignore storage errors.
	}
}

function fromRemoteRecord(record: TeacherVettingProgressRecord): VetterProgressSnapshot {
	const questions = Array.isArray(record.questions) ? record.questions : [];
	return {
		key: (record.key || '').trim(),
		subjectId: (record.subject_id || '').trim() || null,
		topicId: record.topic_id?.trim() || null,
		questions,
		currentIndex: Number.isFinite(record.current_index)
			? Math.max(0, Math.min(questions.length - 1, Math.trunc(record.current_index)))
			: 0,
		approvedQuestionIds: normalizeStringArray(record.approved_question_ids),
		rejectedQuestionIds: normalizeStringArray(record.rejected_question_ids),
		updatedAt: record.updated_at || new Date().toISOString(),
	};
}

export function mergeVetterProgressStores(
	baseStore: VetterProgressStore,
	incomingStore: VetterProgressStore
): VetterProgressStore {
	const merged: VetterProgressStore = { ...baseStore };
	for (const [key, candidate] of Object.entries(incomingStore)) {
		const existing = merged[key];
		if (!existing || toMillis(candidate.updatedAt) >= toMillis(existing.updatedAt)) {
			merged[key] = candidate;
		}
	}
	return merged;
}

export async function hydrateVetterProgressStoreFromRemote(opts: {
	subjectId?: string | null;
	topicId?: string | null;
} = {}): Promise<VetterProgressStore> {
	const localStore = readVetterProgressStore();
	if (!browser) return localStore;

	const subjectId = (opts.subjectId ?? '').trim();

	try {
		const remoteRecords = await listTeacherVettingProgressRemote(
			subjectId
				? {
					subject_id: subjectId,
					topic_id: (opts.topicId ?? '').trim() || undefined,
				}
				: {}
		);

		const remoteStore: VetterProgressStore = {};
		for (const record of remoteRecords) {
			const snapshot = fromRemoteRecord(record);
			if (!snapshot.key || !snapshot.subjectId || snapshot.questions.length === 0) continue;
			remoteStore[snapshot.key] = snapshot;
		}

		const merged = mergeVetterProgressStores(localStore, remoteStore);
		writeVetterProgressStore(merged);
		return merged;
	} catch {
		return localStore;
	}
}

export function upsertVetterProgress(
	input: Omit<VetterProgressSnapshot, 'key' | 'updatedAt'> & { key?: string; updatedAt?: string }
): VetterProgressSnapshot {
	const key =
		input.key ??
		buildVetterProgressKey({
			subjectId: input.subjectId,
			topicId: input.topicId,
		});

	const snapshot: VetterProgressSnapshot = {
		key,
		subjectId: input.subjectId?.trim() || null,
		topicId: input.topicId?.trim() || null,
		questions: input.questions,
		currentIndex: Math.max(0, Math.min(input.questions.length - 1, Math.trunc(input.currentIndex))),
		approvedQuestionIds: normalizeStringArray(input.approvedQuestionIds),
		rejectedQuestionIds: normalizeStringArray(input.rejectedQuestionIds),
		updatedAt: input.updatedAt ?? new Date().toISOString(),
	};

	const store = readVetterProgressStore();
	store[key] = snapshot;
	writeVetterProgressStore(store);
	return snapshot;
}

export async function upsertVetterProgressRemoteSnapshot(
	snapshot: VetterProgressSnapshot
): Promise<VetterProgressSnapshot | null> {
	if (!browser || !snapshot.key) return null;
	const remoteSubjectId =
		snapshot.subjectId ||
		snapshot.questions.find((question) => question.subject_id)?.subject_id ||
		null;
	if (!remoteSubjectId) return null;
	try {
		const saved = await upsertTeacherVettingProgressRemote({
			key: snapshot.key,
			subject_id: remoteSubjectId,
			topic_id: snapshot.topicId,
			mixed_topics_mode: false,
			selected_mixed_topic_ids: [],
			generation_batch_size: 30,
			allow_no_pdf_generation: false,
			questions: snapshot.questions,
			current_index: snapshot.currentIndex,
			approved_question_ids: snapshot.approvedQuestionIds,
			rejected_question_ids: snapshot.rejectedQuestionIds,
			batch_complete: false,
			updated_at: snapshot.updatedAt,
		});

		const normalized = fromRemoteRecord(saved);
		const store = readVetterProgressStore();
		store[normalized.key] = normalized;
		writeVetterProgressStore(store);
		return normalized;
	} catch {
		return null;
	}
}

export async function removeVetterProgressRemoteSnapshot(key: string): Promise<void> {
	if (!browser || !key) return;
	try {
		await deleteTeacherVettingProgressRemote(key);
	} catch {
		// Ignore remote deletion failures and keep local behavior intact.
	}
}

export function removeVetterProgress(key: string): void {
	if (!browser || !key) return;
	const store = readVetterProgressStore();
	if (!store[key]) return;
	delete store[key];
	writeVetterProgressStore(store);
}

export function findVetterProgressMatch(
	store: VetterProgressStore,
	context: VetterProgressContext
): VetterProgressSnapshot | null {
	const key = buildVetterProgressKey(context);
	return store[key] ?? null;
}