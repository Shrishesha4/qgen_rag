<script lang="ts">
	import { onDestroy, tick } from 'svelte';
	import { Send } from 'lucide-svelte';
	import MarkdownContent from './MarkdownContent.svelte';
	import {
		streamConversationalInquiry,
		type InquiryMessage,
	} from '$lib/api/inquiry';

	let {
		subjectId = null,
		topicId = null,
		courseId = null,
		moduleId = null,
		disabled = false,
	}: {
		subjectId?: string | null;
		topicId?: string | null;
		courseId?: string | null;
		moduleId?: string | null;
		disabled?: boolean;
	} = $props();

	let messages = $state<InquiryMessage[]>([]);
	let draft = $state('');
	let isStreaming = $state(false);
	let isWaitingForFirstToken = $state(false);
	let error = $state<string | null>(null);
	let messageViewport = $state<HTMLDivElement | null>(null);
	let streamAbortController: AbortController | null = null;

	async function scrollToBottom() {
		await tick();
		if (messageViewport) {
			messageViewport.scrollTop = messageViewport.scrollHeight;
		}
	}

	$effect(() => {
		if (messages.length) {
			scrollToBottom();
		}
	});

	async function sendMessage() {
		const text = draft.trim();
		if (!text || isStreaming || disabled) return;

		draft = '';
		error = null;
		messages = [...messages, { role: 'user', content: text }];
		isStreaming = true;
		isWaitingForFirstToken = true;

		const abortCtrl = new AbortController();
		streamAbortController = abortCtrl;

		let assistantContent = '';
		try {
			const stream = streamConversationalInquiry({
				subjectId,
				topicId,
				level: 'beginner',
				mode: 'answer_feedback',
				questionCycleIndex: 0,
				messages: messages,
				signal: abortCtrl.signal,
			});

			for await (const event of stream) {
				if (event.type === 'delta' && event.delta) {
					if (isWaitingForFirstToken) {
						isWaitingForFirstToken = false;
						messages = [...messages, { role: 'assistant', content: '' }];
					}
					assistantContent += event.delta;
					messages = [
						...messages.slice(0, -1),
						{ role: 'assistant', content: assistantContent },
					];
				} else if (event.type === 'error') {
					error = event.message ?? 'Something went wrong.';
				}
			}
		} catch (e: unknown) {
			if ((e as Error).name !== 'AbortError') {
				error = (e as Error).message ?? 'Failed to get response.';
			}
		} finally {
			isStreaming = false;
			isWaitingForFirstToken = false;
			streamAbortController = null;
		}
	}

	function handleKeydown(event: KeyboardEvent) {
		if (event.key === 'Enter' && !event.shiftKey) {
			event.preventDefault();
			void sendMessage();
		}
	}

	onDestroy(() => {
		streamAbortController?.abort();
	});

	export function clearChat() {
		messages = [];
		draft = '';
		error = null;
	}

	export function getMessages() {
		return messages;
	}

	export function setMessages(newMessages: InquiryMessage[]) {
		messages = newMessages;
	}
</script>

<div class="tutor-chat">
	<div class="chat-viewport" bind:this={messageViewport}>
		{#if messages.length === 0 && !isWaitingForFirstToken}
			<div class="chat-empty">
				<p>Ask the tutor anything about this content.</p>
			</div>
		{:else}
			{#each messages as message}
				<article class="message-row" class:user={message.role === 'user'}>
					<div class="message-meta">{message.role === 'assistant' ? 'Tutor' : 'You'}</div>
					<div class="message-bubble">
						<MarkdownContent content={message.content} />
					</div>
				</article>
			{/each}

			{#if isWaitingForFirstToken}
				<article class="message-row">
					<div class="message-meta">Tutor</div>
					<div class="message-bubble typing-bubble">
						<span class="typing-dot"></span>
						<span class="typing-dot"></span>
						<span class="typing-dot"></span>
					</div>
				</article>
			{/if}
		{/if}
	</div>

	{#if error}
		<div class="chat-error">{error}</div>
	{/if}

	<form class="composer" onsubmit={(e) => { e.preventDefault(); void sendMessage(); }}>
		<textarea
			bind:value={draft}
			onkeydown={handleKeydown}
			placeholder="Ask the tutor…"
			disabled={isStreaming || disabled}
		></textarea>
		<button class="composer-send" type="submit" disabled={isStreaming || !draft.trim() || disabled}>
			<Send class="h-4 w-4" />
			<span>{isStreaming ? 'Thinking…' : 'Send'}</span>
		</button>
	</form>
</div>

<style>
	.tutor-chat {
		display: flex;
		flex-direction: column;
		height: 100%;
		overflow: hidden;
	}

	.chat-viewport {
		flex: 1;
		overflow-y: auto;
		padding: 1rem;
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}

	.chat-empty {
		display: grid;
		place-items: center;
		flex: 1;
		color: var(--theme-text-secondary);
		font-size: 0.9rem;
		padding: 2rem;
		text-align: center;
	}

	.message-row {
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
		max-width: min(84%, 760px);
	}

	.message-row.user {
		align-self: flex-end;
	}

	.message-meta {
		font-size: 0.72rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: var(--theme-text-secondary);
		padding: 0 0.25rem;
	}

	.message-bubble {
		padding: 0.95rem 1rem;
		border-radius: 18px;
		border: 1px solid rgba(0, 0, 0, 0.1);
		background: rgba(0, 0, 0, 0.07);
		color: var(--theme-text-primary);
		line-height: 1.6;
	}

	.message-row.user .message-bubble {
		background: rgba(var(--theme-primary-rgb), 0.12);
		border-color: rgba(var(--theme-primary-rgb), 0.22);
	}

	:global([data-color-mode='dark']) .message-bubble {
		background: color-mix(in srgb, var(--theme-input-bg) 60%, var(--theme-surface) 40%);
		border-color: var(--theme-glass-border);
	}

	:global([data-color-mode='dark']) .message-row.user .message-bubble {
		background: color-mix(in srgb, rgba(var(--theme-primary-rgb), 0.18) 60%, var(--theme-input-bg) 40%);
		border-color: rgba(var(--theme-primary-rgb), 0.28);
	}

	.typing-bubble {
		display: flex;
		align-items: center;
		gap: 5px;
		min-width: 58px;
	}

	.typing-dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		background: var(--theme-text-secondary);
		opacity: 0.55;
		animation: typing-bounce 1.3s ease-in-out infinite;
		flex-shrink: 0;
	}

	.typing-dot:nth-child(2) { animation-delay: 0.18s; }
	.typing-dot:nth-child(3) { animation-delay: 0.36s; }

	@keyframes typing-bounce {
		0%, 55%, 100% { transform: translateY(0); opacity: 0.55; }
		28% { transform: translateY(-7px); opacity: 1; }
	}

	.chat-error {
		padding: 0.5rem 1rem;
		font-size: 0.82rem;
		color: #ef4444;
		background: rgba(239, 68, 68, 0.06);
		border-top: 1px solid rgba(239, 68, 68, 0.15);
	}

	.composer {
		display: grid;
		grid-template-columns: minmax(0, 1fr) auto;
		gap: 0.85rem;
		align-items: flex-end;
		padding: 0.9rem 1rem;
		background: linear-gradient(
			to top,
			color-mix(in srgb, var(--theme-nav-glass) 98%, transparent),
			color-mix(in srgb, var(--theme-nav-glass) 90%, transparent)
		);
		border-top: 1px solid color-mix(in srgb, var(--theme-glass-border) 72%, transparent);
	}

	.composer textarea {
		height: 72px;
		min-height: 72px;
		resize: none;
		width: 100%;
		padding: 0.65rem 0.8rem;
		border-radius: 12px;
		border: 1px solid var(--theme-glass-border);
		background: var(--theme-input-bg);
		color: var(--theme-text-primary);
		font-size: 0.88rem;
		font-family: inherit;
		line-height: 1.55;
	}

	.composer textarea:disabled {
		opacity: 0.55;
	}

	.composer textarea::placeholder {
		color: var(--theme-text-secondary);
	}

	.composer textarea:focus {
		outline: none;
		border-color: rgba(var(--theme-primary-rgb), 0.55);
	}

	.composer-send {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		gap: 0.45rem;
		padding: 0.65rem 0.85rem;
		border-radius: 12px;
		border: 1px solid rgba(var(--theme-primary-rgb), 0.24);
		background: color-mix(in srgb, var(--theme-surface) 82%, rgba(var(--theme-primary-rgb), 0.12));
		color: var(--theme-text-primary);
		font-weight: 700;
		cursor: pointer;
		font-size: 0.82rem;
	}

	.composer-send:disabled {
		opacity: 0.45;
		cursor: not-allowed;
	}

	@media (max-width: 768px) {
		.composer {
			grid-template-columns: 1fr;
		}

		.composer-send {
			width: 100%;
		}

		.message-row {
			max-width: 100%;
		}
	}
</style>
