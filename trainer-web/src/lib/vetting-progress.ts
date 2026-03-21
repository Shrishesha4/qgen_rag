import { browser } from '$app/environment';
import {
	deleteTeacherVettingProgressRemote,
	listTeacherVettingProgressRemote,
	upsertTeacherVettingProgressRemote,
	type QuestionForVetting,
	type TeacherVettingProgressRecord,
	type TeacherVettingProgressUpsertPayload,
} from '$lib/api/vetting';

const TEACHER_VETTING_PROGRESS_STORAGE_KEY = 'qgen:teacher-vetting-progress:v1';

export interface TeacherVettingProgressContext {
	subjectId: string;
	topicId?: string | null;
	mixedTopicsMode?: boolean;
	selectedMixedTopicIds?: string[];
}

export interface TeacherVettingProgressSnapshot {
	key: string;
	subjectId: string;
	topicId: string | null;
	mixedTopicsMode: boolean;
	selectedMixedTopicIds: string[];
	generationBatchSize: number;
	allowNoPdfGeneration: boolean;
	questions: QuestionForVetting[];
	currentIndex: number;
	approvedQuestionIds: string[];
	rejectedQuestionIds: string[];
	batchComplete: boolean;
	updatedAt: string;
}

export type TeacherVettingProgressStore = Record<string, TeacherVettingProgressSnapshot>;

function normalizeStringArray(value: unknown): string[] {
	if (!Array.isArray(value)) return [];
	return [...new Set(value.filter((item): item is string => typeof item === 'string').map((item) => item.trim()).filter(Boolean))];
}

function toMillis(iso: string): number {
	const ts = Date.parse(iso);
	return Number.isFinite(ts) ? ts : 0;
}

function pickLatest(items: TeacherVettingProgressSnapshot[]): TeacherVettingProgressSnapshot | null {
	if (items.length === 0) return null;
	return items.reduce((latest, candidate) => (toMillis(candidate.updatedAt) > toMillis(latest.updatedAt) ? candidate : latest));
}

export function buildTeacherVettingProgressKey(context: TeacherVettingProgressContext): string {
	const subjectId = context.subjectId.trim();
	const topicId = (context.topicId ?? '').trim() || 'all';
	const mode = context.mixedTopicsMode ? 'mixed' : 'standard';
	const selectedTopics = normalizeStringArray(context.selectedMixedTopicIds).sort().join(',');
	return `${subjectId}|${topicId}|${mode}|${selectedTopics}`;
}

export function readTeacherVettingProgressStore(): TeacherVettingProgressStore {
	if (!browser) return {};
	try {
		const raw = window.localStorage.getItem(TEACHER_VETTING_PROGRESS_STORAGE_KEY);
		if (!raw) return {};
		const parsed = JSON.parse(raw) as Record<string, unknown>;
		if (!parsed || typeof parsed !== 'object') return {};

		const store: TeacherVettingProgressStore = {};
		for (const [key, value] of Object.entries(parsed)) {
			if (!value || typeof value !== 'object') continue;
			const candidate = value as Partial<TeacherVettingProgressSnapshot>;
			const subjectId = typeof candidate.subjectId === 'string' ? candidate.subjectId.trim() : '';
			if (!subjectId) continue;
			const questions = Array.isArray(candidate.questions)
				? (candidate.questions as QuestionForVetting[])
				: [];
			if (questions.length === 0) continue;
			store[key] = {
				key,
				subjectId,
				topicId: typeof candidate.topicId === 'string' && candidate.topicId.trim() ? candidate.topicId.trim() : null,
				mixedTopicsMode: Boolean(candidate.mixedTopicsMode),
				selectedMixedTopicIds: normalizeStringArray(candidate.selectedMixedTopicIds).sort(),
				generationBatchSize: Number.isFinite(candidate.generationBatchSize)
					? Math.max(1, Math.trunc(candidate.generationBatchSize as number))
					: 30,
				allowNoPdfGeneration: Boolean(candidate.allowNoPdfGeneration),
				questions,
				currentIndex: Number.isFinite(candidate.currentIndex)
					? Math.max(0, Math.min(questions.length - 1, Math.trunc(candidate.currentIndex as number)))
					: 0,
				approvedQuestionIds: normalizeStringArray(candidate.approvedQuestionIds),
				rejectedQuestionIds: normalizeStringArray(candidate.rejectedQuestionIds),
				batchComplete: Boolean(candidate.batchComplete),
				updatedAt: typeof candidate.updatedAt === 'string' && candidate.updatedAt
					? candidate.updatedAt
					: new Date().toISOString(),
			};
		}
		return store;
	} catch {
		return {};
	}
}

function fromRemoteRecord(record: TeacherVettingProgressRecord): TeacherVettingProgressSnapshot {
	const questions = Array.isArray(record.questions) ? record.questions : [];
	return {
		key: (record.key || '').trim(),
		subjectId: (record.subject_id || '').trim(),
		topicId: record.topic_id?.trim() || null,
		mixedTopicsMode: Boolean(record.mixed_topics_mode),
		selectedMixedTopicIds: normalizeStringArray(record.selected_mixed_topic_ids).sort(),
		generationBatchSize: Number.isFinite(record.generation_batch_size)
			? Math.max(1, Math.trunc(record.generation_batch_size))
			: 30,
		allowNoPdfGeneration: Boolean(record.allow_no_pdf_generation),
		questions,
		currentIndex: Number.isFinite(record.current_index)
			? Math.max(0, Math.min(questions.length - 1, Math.trunc(record.current_index)))
			: 0,
		approvedQuestionIds: normalizeStringArray(record.approved_question_ids),
		rejectedQuestionIds: normalizeStringArray(record.rejected_question_ids),
		batchComplete: Boolean(record.batch_complete),
		updatedAt: record.updated_at || new Date().toISOString(),
	};
}

function toRemotePayload(snapshot: TeacherVettingProgressSnapshot): TeacherVettingProgressUpsertPayload {
	return {
		key: snapshot.key,
		subject_id: snapshot.subjectId,
		topic_id: snapshot.topicId,
		mixed_topics_mode: snapshot.mixedTopicsMode,
		selected_mixed_topic_ids: snapshot.selectedMixedTopicIds,
		generation_batch_size: snapshot.generationBatchSize,
		allow_no_pdf_generation: snapshot.allowNoPdfGeneration,
		questions: snapshot.questions,
		current_index: snapshot.currentIndex,
		approved_question_ids: snapshot.approvedQuestionIds,
		rejected_question_ids: snapshot.rejectedQuestionIds,
		batch_complete: snapshot.batchComplete,
		updated_at: snapshot.updatedAt,
	};
}

export function mergeTeacherVettingProgressStores(
	baseStore: TeacherVettingProgressStore,
	incomingStore: TeacherVettingProgressStore
): TeacherVettingProgressStore {
	const merged: TeacherVettingProgressStore = { ...baseStore };
	for (const [key, candidate] of Object.entries(incomingStore)) {
		const existing = merged[key];
		if (!existing || toMillis(candidate.updatedAt) >= toMillis(existing.updatedAt)) {
			merged[key] = candidate;
		}
	}
	return merged;
}

export async function hydrateTeacherVettingProgressStoreFromRemote(): Promise<TeacherVettingProgressStore> {
	const localStore = readTeacherVettingProgressStore();
	if (!browser) return localStore;

	try {
		const remoteRecords = await listTeacherVettingProgressRemote();
		const remoteStore: TeacherVettingProgressStore = {};
		for (const record of remoteRecords) {
			const snapshot = fromRemoteRecord(record);
			if (!snapshot.key || !snapshot.subjectId || snapshot.questions.length === 0) continue;
			remoteStore[snapshot.key] = snapshot;
		}

		const merged = mergeTeacherVettingProgressStores(localStore, remoteStore);
		writeTeacherVettingProgressStore(merged);
		return merged;
	} catch {
		return localStore;
	}
}

export async function upsertTeacherVettingProgressRemoteSnapshot(
	snapshot: TeacherVettingProgressSnapshot
): Promise<TeacherVettingProgressSnapshot | null> {
	if (!browser || !snapshot.key) return null;
	try {
		const saved = await upsertTeacherVettingProgressRemote(toRemotePayload(snapshot));
		const normalized = fromRemoteRecord(saved);
		const store = readTeacherVettingProgressStore();
		store[normalized.key] = normalized;
		writeTeacherVettingProgressStore(store);
		return normalized;
	} catch {
		return null;
	}
}

export async function removeTeacherVettingProgressRemoteSnapshot(key: string): Promise<void> {
	if (!browser || !key) return;
	try {
		await deleteTeacherVettingProgressRemote(key);
	} catch {
		// Ignore remote deletion failures and keep local behavior intact.
	}
}

export function writeTeacherVettingProgressStore(store: TeacherVettingProgressStore): void {
	if (!browser) return;
	try {
		window.localStorage.setItem(TEACHER_VETTING_PROGRESS_STORAGE_KEY, JSON.stringify(store));
	} catch {
		// Ignore storage errors
	}
}

export function upsertTeacherVettingProgress(
	input: Omit<TeacherVettingProgressSnapshot, 'key' | 'updatedAt'> & {
		key?: string;
		updatedAt?: string;
	}
): TeacherVettingProgressSnapshot {
	const key =
		input.key ??
		buildTeacherVettingProgressKey({
			subjectId: input.subjectId,
			topicId: input.topicId,
			mixedTopicsMode: input.mixedTopicsMode,
			selectedMixedTopicIds: input.selectedMixedTopicIds,
		});

	const snapshot: TeacherVettingProgressSnapshot = {
		key,
		subjectId: input.subjectId.trim(),
		topicId: input.topicId?.trim() || null,
		mixedTopicsMode: Boolean(input.mixedTopicsMode),
		selectedMixedTopicIds: normalizeStringArray(input.selectedMixedTopicIds).sort(),
		generationBatchSize: Math.max(1, Math.trunc(input.generationBatchSize)),
		allowNoPdfGeneration: Boolean(input.allowNoPdfGeneration),
		questions: input.questions,
		currentIndex: Math.max(0, Math.min(input.questions.length - 1, Math.trunc(input.currentIndex))),
		approvedQuestionIds: normalizeStringArray(input.approvedQuestionIds),
		rejectedQuestionIds: normalizeStringArray(input.rejectedQuestionIds),
		batchComplete: Boolean(input.batchComplete),
		updatedAt: input.updatedAt ?? new Date().toISOString(),
	};

	const store = readTeacherVettingProgressStore();
	store[key] = snapshot;
	writeTeacherVettingProgressStore(store);
	return snapshot;
}

export function removeTeacherVettingProgress(key: string): void {
	if (!browser || !key) return;
	const store = readTeacherVettingProgressStore();
	if (!store[key]) return;
	delete store[key];
	writeTeacherVettingProgressStore(store);
}

export function findTeacherVettingProgressMatch(
	store: TeacherVettingProgressStore,
	context: TeacherVettingProgressContext
): TeacherVettingProgressSnapshot | null {
	const exact = store[buildTeacherVettingProgressKey(context)];
	if (exact) return exact;
	const subjectId = context.subjectId.trim();
	if (!subjectId) return null;
	const preferredTopicId = (context.topicId ?? '').trim() || null;
	const candidates = Object.values(store).filter((entry) => entry.subjectId === subjectId);
	if (preferredTopicId) {
		return pickLatest(candidates.filter((entry) => entry.topicId === preferredTopicId));
	}
	return pickLatest(candidates.filter((entry) => entry.topicId === null));
}

export function findTeacherVettingProgressForSubject(
	store: TeacherVettingProgressStore,
	subjectId: string,
	preferredTopicId: string | null = null
): TeacherVettingProgressSnapshot | null {
	const cleanSubjectId = subjectId.trim();
	if (!cleanSubjectId) return null;
	const candidates = Object.values(store).filter((entry) => entry.subjectId === cleanSubjectId);
	if (preferredTopicId) {
		const exactTopic = pickLatest(candidates.filter((entry) => entry.topicId === preferredTopicId));
		if (exactTopic) return exactTopic;
	}
	return pickLatest(candidates);
}

export function latestTeacherVettingProgressBySubject(
	store: TeacherVettingProgressStore
): Record<string, TeacherVettingProgressSnapshot> {
	const grouped: Record<string, TeacherVettingProgressSnapshot[]> = {};
	for (const snapshot of Object.values(store)) {
		if (!grouped[snapshot.subjectId]) {
			grouped[snapshot.subjectId] = [];
		}
		grouped[snapshot.subjectId].push(snapshot);
	}
	const latest: Record<string, TeacherVettingProgressSnapshot> = {};
	for (const [subjectId, snapshots] of Object.entries(grouped)) {
		const winner = pickLatest(snapshots);
		if (winner) latest[subjectId] = winner;
	}
	return latest;
}

export function createTeacherVettingLoopUrl(
	snapshot: TeacherVettingProgressSnapshot,
	options: {
		resume?: boolean;
		resumeKey?: string;
	} = {}
): string {
	const params = new URLSearchParams();
	params.set('subject', snapshot.subjectId);
	if (snapshot.topicId) params.set('topic', snapshot.topicId);
	if (snapshot.mixedTopicsMode) {
		params.set('mode', 'mixed-topics');
		if (snapshot.selectedMixedTopicIds.length > 0) {
			params.set('topics', snapshot.selectedMixedTopicIds.join(','));
		}
	}
	if (snapshot.allowNoPdfGeneration) params.set('noPdf', '1');
	if (snapshot.generationBatchSize > 0) params.set('count', String(snapshot.generationBatchSize));

	const shouldResume = options.resume ?? true;
	params.set('resume', shouldResume ? '1' : '0');
	if (shouldResume) {
		params.set('resume_key', options.resumeKey ?? snapshot.key);
	}

	return `/teacher/train/loop?${params.toString()}`;
}
