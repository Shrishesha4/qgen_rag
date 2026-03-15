<script lang="ts">
	/**
	 * VoiceRecorder — Recording popup with animated mic, pulsing rings,
	 * waveform visualization, and editable transcript.
	 * Matches the next-ui reference design.
	 */

	import { onMount } from 'svelte';

	type SpeechRecognitionResultLike = {
		isFinal: boolean;
		0: { transcript: string };
	};

	type SpeechRecognitionEventLike = Event & {
		resultIndex: number;
		results: ArrayLike<SpeechRecognitionResultLike>;
	};

	type SpeechRecognitionLike = {
		continuous: boolean;
		interimResults: boolean;
		lang: string;
		onresult: ((event: SpeechRecognitionEventLike) => void) | null;
		onerror: ((event: Event & { error?: string }) => void) | null;
		onend: (() => void) | null;
		start: () => void;
		stop: () => void;
	};

	interface Props {
		/** Title shown at top of popup, e.g. "Grade: Easy" or "Reject" */
		title: string;
		/** Accent color class: 'emerald' | 'amber' | 'rose' | 'blue' */
		accent?: string;
		/** Label shown on the final action button */
		submitLabel?: string;
		/** Called when user submits with transcript */
		onSubmit: (transcript: string) => void;
		/** Called when user cancels */
		onCancel: () => void;
	}

	let { title, accent = 'blue', submitLabel = 'Submit', onSubmit, onCancel }: Props = $props();

	let phase: 'recording' | 'transcript' = $state('recording');
	let transcript = $state('');
	let recordingTime = $state(0);
	let timer: ReturnType<typeof setInterval> | null = $state(null);
	let recorderError = $state('');
	let isRequestingPermission = $state(false);
	let isRecording = $state(false);
	let isStopping = $state(false);
	let isTranscribing = $state(false);
	let transcriptionReady = $state(false);
	let transcriptionStatus = $state('Checking browser speech recognition support...');
	let audioPreviewUrl = $state('');
	let audioPreviewSize = $state('');
	let finalTranscript = $state('');
	let interimTranscript = $state('');

	let mediaStream: MediaStream | null = null;
	let speechRecognition: SpeechRecognitionLike | null = null;
	let speechRecognitionActive = $state(false);
	let audioContext: AudioContext | null = null;
	let mediaSourceNode: MediaStreamAudioSourceNode | null = null;
	let scriptProcessorNode: ScriptProcessorNode | null = null;
	let silenceGainNode: GainNode | null = null;
	let recordedPcmChunks: Float32Array[] = [];
	let recordingSampleRate = 16000;
	let isCaptureActive = false;

	$effect(() => {
		if (phase === 'recording' && isRecording) {
			recordingTime = 0;
			timer = setInterval(() => {
				recordingTime++;
			}, 1000);
		}
		return () => {
			if (timer) clearInterval(timer);
			timer = null;
		};
	});

	onMount(() => {
		if (typeof window === 'undefined') return;
		setupSpeechRecognition();
		void startCapture();

		return () => {
			cleanupResources();
			stopSpeechRecognition();
		};
	});

	function formatTime(s: number): string {
		const m = Math.floor(s / 60);
		const sec = s % 60;
		return `${m}:${sec.toString().padStart(2, '0')}`;
	}

	function formatBytes(bytes: number): string {
		if (bytes < 1024) return `${bytes} B`;
		if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
		return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
	}

	async function startCapture() {
		if (typeof navigator === 'undefined' || mediaStream || isRecording || isRequestingPermission || isStopping) return;

		isRequestingPermission = true;
		recorderError = '';
		transcript = '';
		finalTranscript = '';
		interimTranscript = '';
		recordingTime = 0;
		revokeAudioPreview();
		recordedPcmChunks = [];

		try {
			mediaStream = await navigator.mediaDevices.getUserMedia({
				audio: {
					echoCancellation: true,
					noiseSuppression: true,
					autoGainControl: true
				}
			});

			await setupAudioCapture(mediaStream);
			startSpeechRecognition();
			isCaptureActive = true;
			isRecording = true;
			if (timer) clearInterval(timer);
			recordingTime = 0;
			isRequestingPermission = false;
		} catch (error) {
			const message = error instanceof Error ? error.message : 'Unable to access the microphone.';
			recorderError = `Microphone access failed. ${message}`;
			isRequestingPermission = false;
			cleanupResources();
			phase = 'transcript';
		}
	}

	async function setupAudioCapture(stream: MediaStream) {
		const AudioContextCtor =
			window.AudioContext ||
			(window as Window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;

		if (!AudioContextCtor) {
			throw new Error('This browser does not expose AudioContext.');
		}

		audioContext = new AudioContextCtor();
		recordingSampleRate = audioContext.sampleRate;
		mediaSourceNode = audioContext.createMediaStreamSource(stream);
		scriptProcessorNode = audioContext.createScriptProcessor(4096, 1, 1);
		silenceGainNode = audioContext.createGain();
		silenceGainNode.gain.value = 0;
		recordedPcmChunks = [];

		scriptProcessorNode.onaudioprocess = (event: AudioProcessingEvent) => {
			if (!isCaptureActive) {
				return;
			}

			const input = event.inputBuffer.getChannelData(0);
			const copy = new Float32Array(input.length);
			copy.set(input);
			recordedPcmChunks = [...recordedPcmChunks, copy];
		};

		mediaSourceNode.connect(scriptProcessorNode);
		scriptProcessorNode.connect(silenceGainNode);
		silenceGainNode.connect(audioContext.destination);

		if (audioContext.state === 'suspended') {
			await audioContext.resume();
		}
	}

	function setupSpeechRecognition() {
		if (typeof window === 'undefined') return;
		const Ctor =
			(window as Window & {
				SpeechRecognition?: new () => SpeechRecognitionLike;
				webkitSpeechRecognition?: new () => SpeechRecognitionLike;
			}).SpeechRecognition ??
			(window as Window & {
				SpeechRecognition?: new () => SpeechRecognitionLike;
				webkitSpeechRecognition?: new () => SpeechRecognitionLike;
			}).webkitSpeechRecognition;

		if (!Ctor) {
			transcriptionReady = false;
			transcriptionStatus = 'Built-in speech recognition is unavailable in this browser. You can still type feedback manually.';
			return;
		}

		speechRecognition = new Ctor();
		speechRecognition.continuous = true;
		speechRecognition.interimResults = true;
		speechRecognition.lang = 'en-US';

		speechRecognition.onresult = (event) => {
			let nextFinal = finalTranscript;
			let nextInterim = '';
			for (let i = event.resultIndex; i < event.results.length; i += 1) {
				const result = event.results[i];
				const text = normalizeTranscript(result[0]?.transcript ?? '');
				if (!text) continue;
				if (result.isFinal) {
					nextFinal = appendTranscriptChunk(nextFinal, text);
				} else {
					nextInterim = appendTranscriptChunk(nextInterim, text);
				}
			}

			finalTranscript = nextFinal;
			interimTranscript = nextInterim;
			transcript = normalizeTranscript(`${finalTranscript} ${interimTranscript}`);
		};

		speechRecognition.onerror = (event) => {
			speechRecognitionActive = false;
			if (event.error && event.error !== 'no-speech' && event.error !== 'aborted') {
				recorderError = `Speech recognition issue: ${event.error}. You can still type feedback manually.`;
			}
		};

		speechRecognition.onend = () => {
			speechRecognitionActive = false;
		};

		transcriptionReady = true;
		transcriptionStatus = 'Using built-in browser speech recognition.';
	}

	function startSpeechRecognition() {
		if (!speechRecognition || speechRecognitionActive) return;
		try {
			speechRecognition.start();
			speechRecognitionActive = true;
			transcriptionStatus = 'Listening… speak clearly in English.';
		} catch {
			// Some browsers throw if start is called too quickly.
		}
	}

	function stopSpeechRecognition() {
		if (!speechRecognition || !speechRecognitionActive) return;
		try {
			speechRecognition.stop();
		} finally {
			speechRecognitionActive = false;
		}
	}

	async function handleRecordingButton() {
		if (isRecording) {
			await stopRecording();
			return;
		}

		await startCapture();
	}

	async function stopRecording() {
		if (!isRecording || isStopping) return;
		isStopping = true;

		if (timer) {
			clearInterval(timer);
			timer = null;
		}

		await new Promise((resolve) => setTimeout(resolve, 120));

		const recordedAudio = await stopAudioCapture();
		isCaptureActive = false;
		isRecording = false;
		stopSpeechRecognition();
		await stopAudioContext();
		stopMediaStream();
		phase = 'transcript';
		if (recordedAudio) {
			finalizeAudioPreview(recordedAudio.wavBlob);
			if (!transcript.trim()) {
				transcriptionStatus = 'No speech was detected. You can type feedback manually.';
			}
		} else {
			recorderError = 'No audio was captured. Please record again.';
			transcriptionStatus = 'No audio available for transcription.';
		}
		isStopping = false;
	}

	async function stopAudioCapture(): Promise<{ samples: Float32Array; sampleRate: number; wavBlob: Blob } | null> {
		if (!recordedPcmChunks.length) {
			return null;
		}

		const samples = mergePcmChunks(recordedPcmChunks);
		recordedPcmChunks = [];
		return {
			samples,
			sampleRate: recordingSampleRate,
			wavBlob: encodeWavBlob(samples, recordingSampleRate)
		};
	}

	function mergePcmChunks(chunks: Float32Array[]): Float32Array {
		const totalLength = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
		const merged = new Float32Array(totalLength);
		let offset = 0;
		for (const chunk of chunks) {
			merged.set(chunk, offset);
			offset += chunk.length;
		}
		return merged;
	}

	function encodeWavBlob(samples: Float32Array, sampleRate: number): Blob {
		const buffer = new ArrayBuffer(44 + samples.length * 2);
		const view = new DataView(buffer);
		writeWavHeader(view, samples.length, sampleRate);
		floatTo16BitPcm(view, 44, samples);
		return new Blob([buffer], { type: 'audio/wav' });
	}

	function writeWavHeader(view: DataView, sampleCount: number, sampleRate: number) {
		const byteRate = sampleRate * 2;
		const dataSize = sampleCount * 2;

		writeAscii(view, 0, 'RIFF');
		view.setUint32(4, 36 + dataSize, true);
		writeAscii(view, 8, 'WAVE');
		writeAscii(view, 12, 'fmt ');
		view.setUint32(16, 16, true);
		view.setUint16(20, 1, true);
		view.setUint16(22, 1, true);
		view.setUint32(24, sampleRate, true);
		view.setUint32(28, byteRate, true);
		view.setUint16(32, 2, true);
		view.setUint16(34, 16, true);
		writeAscii(view, 36, 'data');
		view.setUint32(40, dataSize, true);
	}

	function writeAscii(view: DataView, offset: number, value: string) {
		for (let index = 0; index < value.length; index += 1) {
			view.setUint8(offset + index, value.charCodeAt(index));
		}
	}

	function floatTo16BitPcm(view: DataView, offset: number, samples: Float32Array) {
		for (let index = 0; index < samples.length; index += 1) {
			const sample = Math.max(-1, Math.min(1, samples[index]));
			view.setInt16(offset + index * 2, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true);
		}
	}

	function finalizeAudioPreview(audioBlob: Blob) {
		revokeAudioPreview();
		audioPreviewUrl = URL.createObjectURL(audioBlob);
		audioPreviewSize = formatBytes(audioBlob.size);
	}



	function revokeAudioPreview() {
		if (!audioPreviewUrl) return;
		URL.revokeObjectURL(audioPreviewUrl);
		audioPreviewUrl = '';
		audioPreviewSize = '';
	}

	function stopMediaStream() {
		if (!mediaStream) return;
		for (const track of mediaStream.getTracks()) {
			track.stop();
		}
		mediaStream = null;
	}

	async function stopAudioContext() {
		scriptProcessorNode?.disconnect();
		mediaSourceNode?.disconnect();
		silenceGainNode?.disconnect();
		scriptProcessorNode = null;
		mediaSourceNode = null;
		silenceGainNode = null;

		if (!audioContext) return;
		await audioContext.close();
		audioContext = null;
	}

	function cleanupResources() {
		if (timer) {
			clearInterval(timer);
			timer = null;
		}
		isCaptureActive = false;
		scriptProcessorNode?.disconnect();
		mediaSourceNode?.disconnect();
		silenceGainNode?.disconnect();
		scriptProcessorNode = null;
		mediaSourceNode = null;
		silenceGainNode = null;
		if (audioContext) {
			void audioContext.close();
			audioContext = null;
		}
		stopMediaStream();
		revokeAudioPreview();
	}

	async function retryRecording() {
		cleanupResources();
		phase = 'recording';
		isStopping = false;
		isRecording = false;
		isRequestingPermission = false;
		isTranscribing = false;
		finalTranscript = '';
		interimTranscript = '';
		transcript = '';
		recorderError = '';
		transcriptionStatus = transcriptionReady
			? 'Using built-in browser speech recognition.'
			: 'Built-in speech recognition is unavailable. Type feedback manually.';
	}

	async function rerecordFromTranscript() {
		if (isRequestingPermission || isStopping) return;
		await retryRecording();
		await startCapture();
	}

	function normalizeTranscript(value: string): string {
		return value.replace(/\s+/g, ' ').trim();
	}

	function appendTranscriptChunk(existing: string, incoming: string): string {
		const base = normalizeTranscript(existing);
		const chunk = normalizeTranscript(incoming);
		if (!chunk) return base;

		// If recognition sends the same phrase repeatedly, keep one copy.
		if (base && base.toLowerCase().endsWith(chunk.toLowerCase())) {
			return base;
		}

		if (!base) return chunk;

		const baseTokens = base.split(' ');
		const chunkTokens = chunk.split(' ');
		const maxOverlap = Math.min(baseTokens.length, chunkTokens.length, 12);

		for (let size = maxOverlap; size > 0; size -= 1) {
			const baseTail = baseTokens.slice(baseTokens.length - size).join(' ').toLowerCase();
			const chunkHead = chunkTokens.slice(0, size).join(' ').toLowerCase();
			if (baseTail === chunkHead) {
				const mergedTokens = [...baseTokens, ...chunkTokens.slice(size)];
				return mergedTokens.join(' ');
			}
		}

		return `${base} ${chunk}`;
	}

	function handleSubmit() {
		onSubmit(transcript);
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') onCancel();
	}

	function handleOverlayKeydown(e: KeyboardEvent) {
		if (e.target !== e.currentTarget) {
			return;
		}

		if (e.key === 'Enter' || e.key === ' ') {
			e.preventDefault();
			onCancel();
		}
	}

	// Accent color mapping
	let accentColors = $derived.by(() => {
		switch (accent) {
			case 'emerald': return { bg: 'rgba(16,185,129,0.2)', border: 'rgba(16,185,129,0.4)', text: '#6ee7b7', solid: '#10b981' };
			case 'amber': return { bg: 'rgba(245,158,11,0.2)', border: 'rgba(245,158,11,0.4)', text: '#fcd34d', solid: '#f59e0b' };
			case 'rose': return { bg: 'rgba(244,63,94,0.2)', border: 'rgba(244,63,94,0.4)', text: '#fda4af', solid: '#f43f5e' };
			default: return { bg: 'rgba(59,130,246,0.2)', border: 'rgba(59,130,246,0.4)', text: '#93c5fd', solid: '#3b82f6' };
		}
	});

	let recorderStatus = $derived.by(() => {
		if (isRequestingPermission) return 'Requesting microphone access...';
		if (isStopping) return 'Finalizing recording...';
		if (!isRecording) return 'Tap the mic to start recording. Your speech stays on this device.';
		if (!transcriptionReady) return transcriptionStatus;
		if (recorderError) return recorderError;
		return 'Recording audio in English using built-in browser speech recognition.';
	});
</script>

<svelte:window on:keydown={handleKeydown} />

<div
	class="recorder-overlay"
	onclick={onCancel}
	onkeydown={handleOverlayKeydown}
	role="button"
	tabindex="0"
	aria-label="Close recorder"
>
	<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
	<div class="recorder-modal glass-panel animate-scale-in" onclick={(e) => e.stopPropagation()} role="dialog" aria-modal="true" tabindex="-1">
		<!-- Header -->
		<div class="recorder-header">
			<h3 class="recorder-title" style:color={accentColors.text}>{title}</h3>
			<button class="recorder-close" onclick={onCancel} aria-label="Close">
				<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
					<line x1="18" y1="6" x2="6" y2="18"></line>
					<line x1="6" y1="6" x2="18" y2="18"></line>
				</svg>
			</button>
		</div>

		{#if phase === 'recording'}
			<!-- Recording phase -->
			<div class="recording-area">
				<!-- Mic button with pulsing rings -->
				<div class="mic-container">
					{#if isRecording}
						<div class="pulse-ring ring-1" style:border-color={accentColors.solid}></div>
						<div class="pulse-ring ring-2" style:border-color={accentColors.solid}></div>
					{/if}
					<button
						class="mic-btn"
						style:background={accentColors.bg}
						style:border-color={accentColors.border}
						onclick={handleRecordingButton}
						disabled={isRequestingPermission || isStopping}
						aria-label={isRecording ? 'Stop recording' : 'Start recording'}
					>
						{#if isRecording}
							<svg width="24" height="24" viewBox="0 0 24 24" fill={accentColors.text} stroke="none">
								<rect x="6" y="6" width="12" height="12" rx="2"></rect>
							</svg>
						{:else}
							<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke={accentColors.text} stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
								<path d="M12 3a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V6a3 3 0 0 0-3-3Z"></path>
								<path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
								<line x1="12" y1="19" x2="12" y2="22"></line>
								<line x1="8" y1="22" x2="16" y2="22"></line>
							</svg>
						{/if}
					</button>
				</div>

				<!-- Timer -->
				<div class="recording-timer" style:color={accentColors.text}>
					{formatTime(recordingTime)}
				</div>

				<!-- Waveform visualization -->
				<div class="waveform">
					{#each Array(24) as _, i}
						<div
							class="wave-bar"
							class:wave-bar-idle={!isRecording}
							style:background={accentColors.solid}
							style:animation-delay="{i * 0.08}s"
						></div>
					{/each}
				</div>

				<p class="recording-hint">{recorderStatus}</p>

				{#if recorderError && !isRecording}
					<button class="retry-btn" style:border-color={accentColors.border} onclick={retryRecording}>
						Try again
					</button>
				{/if}
			</div>
		{:else}
			<!-- Transcript phase -->
			<div class="transcript-area">
				{#if recorderError}
					<p class="transcript-warning">{recorderError}</p>
				{/if}

				{#if isTranscribing || transcriptionStatus}
					<div class="transcription-status-panel">
						<span class="live-transcript-label">Transcription</span>
						<p class="live-transcript-copy">{transcriptionStatus}</p>
					</div>
				{/if}

				{#if audioPreviewUrl}
					<div class="audio-preview">
						<div class="audio-preview-meta">
							<span class="audio-preview-label">Recorded audio</span>
							<span class="audio-preview-size">{audioPreviewSize}</span>
						</div>
						<audio class="audio-preview-player" controls src={audioPreviewUrl}></audio>
					</div>
				{/if}

				<label class="transcript-label" for="voice-recorder-transcript">Transcript</label>
				<textarea
					id="voice-recorder-transcript"
					class="transcript-input"
					bind:value={transcript}
					rows="4"
					placeholder="Edit or type your feedback..."
				></textarea>
				<p class="transcript-hint">
					Review the transcription above before submitting. You can edit it if needed.
				</p>
				<button class="retry-btn transcript-retry-btn" style:border-color={accentColors.border} onclick={rerecordFromTranscript} disabled={isRequestingPermission || isStopping}>
					{isRequestingPermission ? 'Starting...' : 'Re-record audio'}
				</button>
			</div>

			<div class="recorder-actions">
				<button class="recorder-cancel-btn" onclick={onCancel}>Cancel</button>
				<button
					class="recorder-submit-btn"
					style:background={accentColors.solid}
					onclick={handleSubmit}
					disabled={!transcript.trim() || isTranscribing}
				>
					<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
						<line x1="22" y1="2" x2="11" y2="13"></line>
						<polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
					</svg>
					{submitLabel}
				</button>
			</div>
		{/if}
	</div>
</div>

<style>
	.recorder-overlay {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.7);
		backdrop-filter: blur(8px);
		-webkit-backdrop-filter: blur(8px);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 1000;
		padding: 1rem;
	}

	.recorder-modal {
		width: 100%;
		max-width: 400px;
		border-radius: 1.5rem;
		padding: 1.5rem;
		display: flex;
		flex-direction: column;
		gap: 1.25rem;
	}

	.recorder-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
	}

	.recorder-title {
		font-size: 1.1rem;
		font-weight: 700;
		margin: 0;
	}

	.recorder-close {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 32px;
		height: 32px;
		border-radius: 8px;
		border: none;
		background: rgba(255, 255, 255, 0.1);
		color: rgba(255, 255, 255, 0.6);
		cursor: pointer;
		transition: all 0.2s;
	}

	.recorder-close:hover {
		background: rgba(255, 255, 255, 0.2);
		color: white;
	}

	.retry-btn {
		padding: 0.7rem 1rem;
		border-radius: 999px;
		border: 1px solid;
		background: rgba(255, 255, 255, 0.06);
		color: rgba(255, 255, 255, 0.8);
		font-size: 0.85rem;
		font-weight: 600;
		cursor: pointer;
		transition: all 0.2s;
	}

	.retry-btn:hover {
		background: rgba(255, 255, 255, 0.12);
	}


	/* Recording phase */
	.recording-area {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 1.25rem;
		padding: 1rem 0;
	}

	.mic-container {
		position: relative;
		width: 80px;
		height: 80px;
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.pulse-ring {
		position: absolute;
		inset: -8px;
		border-radius: 50%;
		border: 2px solid;
		opacity: 0;
		animation: pulseRing 2s ease-out infinite;
	}

	.ring-2 {
		animation-delay: 0.8s;
	}

	.mic-btn {
		width: 64px;
		height: 64px;
		border-radius: 50%;
		border: 2px solid;
		display: flex;
		align-items: center;
		justify-content: center;
		cursor: pointer;
		transition: all 0.2s;
		position: relative;
		z-index: 1;
	}

	.mic-btn:hover {
		transform: scale(1.05);
	}

	.mic-btn:disabled {
		cursor: wait;
		opacity: 0.65;
		transform: none;
	}

	.recording-timer {
		font-size: 2rem;
		font-weight: 300;
		font-variant-numeric: tabular-nums;
		letter-spacing: 0.05em;
	}

	/* Waveform */
	.waveform {
		display: flex;
		align-items: center;
		gap: 2px;
		height: 40px;
		padding: 0 1rem;
	}

	.wave-bar {
		width: 3px;
		height: 100%;
		border-radius: 999px;
		opacity: 0.7;
		transform-origin: center;
		animation: waveBar 1.2s ease-in-out infinite;
	}

	.wave-bar-idle {
		animation-play-state: paused;
		opacity: 0.25;
	}

	.recording-hint {
		font-size: 0.8rem;
		color: rgba(255, 255, 255, 0.5);
		margin: 0;
		text-align: center;
		max-width: 24rem;
	}

	.transcription-status-panel {
		width: 100%;
		padding: 0.9rem 1rem;
		border-radius: 1rem;
		background: rgba(255, 255, 255, 0.06);
		border: 1px solid rgba(255, 255, 255, 0.08);
		display: flex;
		flex-direction: column;
		gap: 0.45rem;
	}

	.live-transcript-label,
	.audio-preview-label {
		font-size: 0.72rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		color: rgba(255, 255, 255, 0.55);
	}

	.live-transcript-copy {
		margin: 0;
		font-size: 0.88rem;
		line-height: 1.55;
		color: rgba(255, 255, 255, 0.85);
	}

	/* Transcript phase */
	.transcript-area {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.transcript-warning {
		margin: 0;
		padding: 0.75rem 0.85rem;
		border-radius: 0.85rem;
		background: rgba(244, 63, 94, 0.12);
		border: 1px solid rgba(244, 63, 94, 0.22);
		color: rgba(254, 205, 211, 0.92);
		font-size: 0.82rem;
		line-height: 1.45;
	}

	.audio-preview {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		padding: 0.9rem 1rem;
		border-radius: 1rem;
		background: rgba(255, 255, 255, 0.06);
		border: 1px solid rgba(255, 255, 255, 0.08);
	}

	.audio-preview-meta {
		display: flex;
		justify-content: space-between;
		gap: 1rem;
		align-items: center;
	}

	.audio-preview-size {
		font-size: 0.78rem;
		color: rgba(255, 255, 255, 0.5);
	}

	.audio-preview-player {
		width: 100%;
		height: 40px;
		accent-color: var(--theme-primary);
	}

	.transcript-label {
		font-size: 0.75rem;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: rgba(255, 255, 255, 0.6);
	}

	.transcript-input {
		width: 100%;
		padding: 0.75rem;
		background: rgba(255, 255, 255, 0.08);
		border: 1px solid rgba(255, 255, 255, 0.15);
		border-radius: 12px;
		color: var(--theme-text);
		font-family: inherit;
		font-size: 0.92rem;
		line-height: 1.5;
		resize: vertical;
	}

	.transcript-input:focus {
		outline: none;
		border-color: rgba(255, 255, 255, 0.3);
		box-shadow: 0 0 0 2px rgba(255, 255, 255, 0.1);
	}

	.transcript-hint {
		font-size: 0.75rem;
		color: rgba(255, 255, 255, 0.4);
		margin: 0;
	}

	/* Actions */
	.recorder-actions {
		display: flex;
		gap: 0.75rem;
	}

	.recorder-cancel-btn {
		flex: 1;
		padding: 0.75rem;
		border-radius: 12px;
		border: 1px solid rgba(255, 255, 255, 0.15);
		background: rgba(255, 255, 255, 0.05);
		color: rgba(255, 255, 255, 0.7);
		font-size: 0.95rem;
		font-weight: 600;
		cursor: pointer;
		transition: all 0.2s;
		font-family: inherit;
	}

	.recorder-cancel-btn:hover {
		background: rgba(255, 255, 255, 0.1);
	}

	.recorder-submit-btn {
		flex: 1;
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 0.5rem;
		padding: 0.75rem;
		border-radius: 12px;
		border: none;
		color: white;
		font-size: 0.95rem;
		font-weight: 600;
		cursor: pointer;
		transition: all 0.2s;
		font-family: inherit;
	}

	.recorder-submit-btn:hover {
		filter: brightness(1.1);
		transform: translateY(-1px);
	}

	.recorder-submit-btn:disabled {
		opacity: 0.5;
		cursor: not-allowed;
		transform: none;
	}

	@media (max-width: 480px) {
		.recorder-overlay {
			padding: 0.75rem;
			align-items: flex-end;
		}

		.recorder-modal {
			max-width: 100%;
			padding: 1.25rem;
			gap: 1rem;
			border-radius: 1.25rem 1.25rem 0 0;
			max-height: 85vh;
			overflow-y: auto;
		}

		.recorder-title {
			font-size: 1rem;
		}

		.recorder-close {
			width: 28px;
			height: 28px;
			border-radius: 6px;
		}

		.mic-container {
			width: 72px;
			height: 72px;
		}

		.mic-btn {
			width: 56px;
			height: 56px;
		}

		.mic-btn svg {
			width: 20px;
			height: 20px;
		}

		.recording-timer {
			font-size: 1.6rem;
		}

		.waveform {
			height: 32px;
			gap: 1.5px;
		}

		.wave-bar {
			width: 2.5px;
		}

		.recording-hint {
			font-size: 0.75rem;
			max-width: 100%;
		}

		.retry-btn {
			padding: 0.6rem 0.85rem;
			font-size: 0.8rem;
		}

		.transcription-status-panel {
			padding: 0.75rem 0.85rem;
			border-radius: 0.85rem;
		}

		.live-transcript-label,
		.audio-preview-label {
			font-size: 0.68rem;
		}

		.live-transcript-copy {
			font-size: 0.82rem;
		}

		.audio-preview {
			padding: 0.75rem 0.85rem;
			border-radius: 0.85rem;
		}

		.audio-preview-player {
			height: 36px;
		}

		.transcript-warning {
			padding: 0.65rem 0.75rem;
			font-size: 0.78rem;
		}

		.transcript-label {
			font-size: 0.7rem;
		}

		.transcript-input {
			padding: 0.65rem;
			font-size: 0.88rem;
			border-radius: 10px;
		}

		.transcript-hint {
			font-size: 0.7rem;
		}

		.recorder-actions {
			gap: 0.6rem;
		}

		.recorder-cancel-btn,
		.recorder-submit-btn {
			padding: 0.65rem;
			font-size: 0.88rem;
			border-radius: 10px;
		}

		.recorder-submit-btn svg {
			width: 14px;
			height: 14px;
		}
	}
</style>
