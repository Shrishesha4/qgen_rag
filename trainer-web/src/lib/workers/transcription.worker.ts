import { pipeline } from '@huggingface/transformers';

type WorkerInboundMessage =
	| { type: 'init' }
	| { type: 'transcribe'; audio: ArrayBuffer };

type WorkerOutboundMessage =
	| { type: 'model-loading'; message: string }
	| { type: 'model-ready' }
	| { type: 'transcription-started'; message: string }
	| { type: 'transcription-complete'; text: string }
	| { type: 'error'; message: string };

type ProgressStatus = {
	status?: string;
	file?: string;
	progress?: number;
	loaded?: number;
	total?: number;
};

type WorkerScopeLike = {
	postMessage: (message: WorkerOutboundMessage) => void;
	onmessage: ((event: MessageEvent<WorkerInboundMessage>) => Promise<void> | void) | null;
};

const workerScope = self as unknown as WorkerScopeLike;
let transcriberPromise: Promise<any> | null = null;

function isBenignTransformersWarning(message: string): boolean {
	return (
		message.includes('Unable to determine content-length from response headers') ||
		message.includes('dtype not specified for "encoder_model"') ||
		message.includes('dtype not specified for "decoder_model_merged"')
	);
}

async function withSuppressedModelWarnings<T>(work: () => Promise<T>): Promise<T> {
	const originalWarn = console.warn;
	console.warn = (...args: unknown[]) => {
		const firstArg = typeof args[0] === 'string' ? args[0] : '';
		if (isBenignTransformersWarning(firstArg)) {
			return;
		}
		originalWarn(...args);
	};

	try {
		return await work();
	} finally {
		console.warn = originalWarn;
	}
}

function post(message: WorkerOutboundMessage) {
	workerScope.postMessage(message);
}

function formatProgress(progress: ProgressStatus): string {
	if (typeof progress.progress === 'number') {
		return `Downloading local speech model to this browser once… ${Math.round(progress.progress)}%`;
	}

	if (typeof progress.loaded === 'number' && typeof progress.total === 'number' && progress.total > 0) {
		return `Downloading local speech model to this browser once… ${Math.round((progress.loaded / progress.total) * 100)}%`;
	}

	if (progress.file) {
		return `Preparing ${progress.file} for on-device transcription in this browser…`;
	}

	return 'Loading on-device transcription model in this browser…';
}

async function getTranscriber() {
	if (!transcriberPromise) {
		post({ type: 'model-loading', message: 'Loading on-device transcription model in this browser…' });
		transcriberPromise = withSuppressedModelWarnings(() =>
			pipeline('automatic-speech-recognition', 'Xenova/whisper-tiny', {
				dtype: {
					encoder_model: 'q8',
					decoder_model_merged: 'q8'
				},
				progress_callback: (progress: ProgressStatus) => {
					post({ type: 'model-loading', message: formatProgress(progress) });
				}
			})
		);
	}

	return transcriberPromise;
}

workerScope.onmessage = async (event: MessageEvent<WorkerInboundMessage>) => {
	try {
		if (event.data.type === 'init') {
			await getTranscriber();
			post({ type: 'model-ready' });
			return;
		}

		post({ type: 'transcription-started', message: 'Transcribing…' });
		const transcriber = await getTranscriber();
		const audio = new Float32Array(event.data.audio);
		const result = (await transcriber(audio, {
			chunk_length_s: 20,
			stride_length_s: 5,
			return_timestamps: false,
			language: 'en',
			task: 'transcribe'
		})) as { text?: string };

		post({ type: 'transcription-complete', text: result.text?.trim() ?? '' });
	} catch (error) {
		const message = error instanceof Error ? error.message : 'On-device transcription failed.';
		post({ type: 'error', message });
	}
};

export {};