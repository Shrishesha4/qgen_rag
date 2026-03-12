<script lang="ts">
	/**
	 * VoiceRecorder — Recording popup with animated mic, pulsing rings,
	 * waveform visualization, and editable transcript.
	 * Matches the next-ui reference design.
	 */

	interface Props {
		/** Title shown at top of popup, e.g. "Grade: Easy" or "Reject" */
		title: string;
		/** Accent color class: 'emerald' | 'amber' | 'rose' | 'blue' */
		accent?: string;
		/** Called when user submits with transcript */
		onSubmit: (transcript: string) => void;
		/** Called when user cancels */
		onCancel: () => void;
	}

	let { title, accent = 'blue', onSubmit, onCancel }: Props = $props();

	let phase: 'recording' | 'transcript' = $state('recording');
	let transcript = $state('');
	let recordingTime = $state(0);
	let timer: ReturnType<typeof setInterval> | null = $state(null);

	// Start timer on mount
	$effect(() => {
		if (phase === 'recording') {
			recordingTime = 0;
			timer = setInterval(() => { recordingTime++; }, 1000);
		}
		return () => {
			if (timer) clearInterval(timer);
		};
	});

	const SAMPLE_TRANSCRIPTS = [
		'This question is well-structured and tests fundamental knowledge effectively.',
		'The question covers an important topic area and is clearly worded.',
		'Good question with appropriate complexity for the target audience.',
		'This seems like a solid question that aligns with our content standards.',
	];

	function formatTime(s: number): string {
		const m = Math.floor(s / 60);
		const sec = s % 60;
		return `${m}:${sec.toString().padStart(2, '0')}`;
	}

	function stopRecording() {
		if (timer) clearInterval(timer);
		timer = null;
		transcript = SAMPLE_TRANSCRIPTS[Math.floor(Math.random() * SAMPLE_TRANSCRIPTS.length)];
		phase = 'transcript';
	}

	function handleSubmit() {
		onSubmit(transcript);
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') onCancel();
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
</script>

<svelte:window on:keydown={handleKeydown} />

<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
<div class="recorder-overlay" onclick={onCancel}>
	<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
	<div class="recorder-modal glass-panel animate-scale-in" onclick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
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
					<div class="pulse-ring ring-1" style:border-color={accentColors.solid}></div>
					<div class="pulse-ring ring-2" style:border-color={accentColors.solid}></div>
					<button
						class="mic-btn"
						style:background={accentColors.bg}
						style:border-color={accentColors.border}
						onclick={stopRecording}
						aria-label="Stop recording"
					>
						<svg width="24" height="24" viewBox="0 0 24 24" fill={accentColors.text} stroke="none">
							<rect x="6" y="6" width="12" height="12" rx="2"></rect>
						</svg>
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
							style:background={accentColors.solid}
							style:animation-delay="{i * 0.08}s"
						></div>
					{/each}
				</div>

				<p class="recording-hint">Tap the square to stop recording</p>
			</div>
		{:else}
			<!-- Transcript phase -->
			<div class="transcript-area">
				<label class="transcript-label">Transcript</label>
				<textarea
					class="transcript-input"
					bind:value={transcript}
					rows="4"
					placeholder="Edit or type your feedback..."
				></textarea>
				<p class="transcript-hint">Edit the transcript above or type your own feedback</p>
			</div>

			<div class="recorder-actions">
				<button class="recorder-cancel-btn" onclick={onCancel}>Cancel</button>
				<button
					class="recorder-submit-btn"
					style:background={accentColors.solid}
					onclick={handleSubmit}
					disabled={!transcript.trim()}
				>
					<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
						<line x1="22" y1="2" x2="11" y2="13"></line>
						<polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
					</svg>
					Submit
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

	.recording-hint {
		font-size: 0.8rem;
		color: rgba(255, 255, 255, 0.5);
		margin: 0;
	}

	/* Transcript phase */
	.transcript-area {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
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
</style>
