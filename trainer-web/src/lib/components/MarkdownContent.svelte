<script lang="ts">
	import { browser } from '$app/environment';
	import { tick } from 'svelte';
	import DOMPurify from 'isomorphic-dompurify';
	import { marked } from 'marked';

	let { content } = $props<{ content: string }>();

	let container = $state<HTMLDivElement | null>(null);
	let mermaidApi: typeof import('mermaid').default | null = null;
	let mermaidInitialized = false;
	let mermaidCounter = 0;

	function renderMarkdown(value: string): string {
		const rendered = marked.parse(value ?? '', {
			gfm: true,
			breaks: true,
		}) as string;

		return DOMPurify.sanitize(rendered, {
			USE_PROFILES: { html: true },
		});
	}

	const sanitizedHtml = $derived(renderMarkdown(content));

	async function loadMermaid() {
		if (!browser) return null;
		if (!mermaidApi) {
			mermaidApi = (await import('mermaid')).default;
		}
		if (!mermaidInitialized && mermaidApi) {
			mermaidApi.initialize({
				startOnLoad: false,
				securityLevel: 'strict',
				theme: 'neutral',
				fontFamily: 'inherit',
				suppressErrorRendering: false,
			});
			mermaidInitialized = true;
		}
		return mermaidApi;
	}

	function enhanceLinks() {
		if (!container) return;
		for (const link of container.querySelectorAll('a[href]')) {
			link.setAttribute('target', '_blank');
			link.setAttribute('rel', 'noreferrer noopener');
		}
	}

	async function renderMermaidDiagrams() {
		if (!browser || !container) return;
		const mermaid = await loadMermaid();
		if (!mermaid) return;

		const blocks = Array.from(container.querySelectorAll('pre > code.language-mermaid'));
		for (const block of blocks) {
			const pre = block.parentElement;
			if (!pre) continue;

			const source = block.textContent?.trim();
			if (!source) continue;

			const host = document.createElement('div');
			host.className = 'mermaid-render';

			try {
				const { svg, bindFunctions } = await mermaid.render(
					`train-mermaid-${mermaidCounter++}`,
					source,
				);
				host.innerHTML = svg;
				bindFunctions?.(host);
				pre.replaceWith(host);
			} catch {
				pre.classList.add('mermaid-fallback');
			}
		}
	}

	async function enhanceRenderedContent() {
		if (!browser) return;
		await tick();
		enhanceLinks();
		await renderMermaidDiagrams();
	}

	$effect(() => {
		sanitizedHtml;
		void enhanceRenderedContent();
	});
</script>

<div class="markdown-content" bind:this={container}>
	{@html sanitizedHtml}
</div>

<style>
	.markdown-content {
		color: inherit;
		white-space: normal;
		line-height: 1.65;
	}

	.markdown-content :global(*:first-child) {
		margin-top: 0;
	}

	.markdown-content :global(*:last-child) {
		margin-bottom: 0;
	}

	.markdown-content :global(p),
	.markdown-content :global(ul),
	.markdown-content :global(ol),
	.markdown-content :global(blockquote),
	.markdown-content :global(pre),
	.markdown-content :global(table) {
		margin: 0 0 0.9rem;
	}

	.markdown-content :global(h1),
	.markdown-content :global(h2),
	.markdown-content :global(h3),
	.markdown-content :global(h4) {
		margin: 0 0 0.7rem;
		line-height: 1.25;
		color: var(--theme-text-primary);
	}

	.markdown-content :global(h1) {
		font-size: 1.32rem;
	}

	.markdown-content :global(h2) {
		font-size: 1.16rem;
	}

	.markdown-content :global(h3),
	.markdown-content :global(h4) {
		font-size: 1.02rem;
	}

	.markdown-content :global(ul),
	.markdown-content :global(ol) {
		padding-left: 1.15rem;
	}

	.markdown-content :global(li + li) {
		margin-top: 0.35rem;
	}

	.markdown-content :global(a) {
		color: rgba(var(--theme-primary-rgb), 0.96);
		text-decoration: underline;
		text-underline-offset: 0.18rem;
	}

	.markdown-content :global(blockquote) {
		padding: 0.15rem 0 0.15rem 0.9rem;
		border-left: 3px solid rgba(var(--theme-primary-rgb), 0.34);
		color: var(--theme-text-secondary);
	}

	.markdown-content :global(code) {
		font-family: 'SFMono-Regular', 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
	}

	.markdown-content :global(:not(pre) > code) {
		padding: 0.15rem 0.35rem;
		border-radius: 8px;
		background: color-mix(in srgb, var(--theme-input-bg) 80%, var(--theme-surface) 20%);
		border: 1px solid var(--theme-glass-border);
		font-size: 0.92em;
	}

	.markdown-content :global(pre),
	.markdown-content :global(.mermaid-render) {
		overflow-x: auto;
		padding: 0.9rem 1rem;
		border-radius: 14px;
		background: color-mix(in srgb, var(--theme-input-bg) 80%, var(--theme-surface) 20%);
		border: 1px solid var(--theme-glass-border);
	}

	.markdown-content :global(pre code) {
		background: transparent;
		border: 0;
		padding: 0;
		font-size: 0.92rem;
	}

	.markdown-content :global(hr) {
		margin: 1rem 0;
		border: 0;
		border-top: 1px solid var(--theme-glass-border);
	}

	.markdown-content :global(table) {
		display: block;
		width: 100%;
		overflow-x: auto;
		border-collapse: collapse;
		border-spacing: 0;
		border: 1px solid var(--theme-glass-border);
		border-radius: 14px;
		background: color-mix(in srgb, var(--theme-input-bg) 72%, var(--theme-surface) 28%);
	}

	.markdown-content :global(th),
	.markdown-content :global(td) {
		padding: 0.7rem 0.85rem;
		border-bottom: 1px solid var(--theme-glass-border);
		text-align: left;
		vertical-align: top;
	}

	.markdown-content :global(th) {
		font-weight: 700;
		color: var(--theme-text-primary);
		background: color-mix(in srgb, var(--theme-input-bg) 84%, var(--theme-surface) 16%);
	}

	.markdown-content :global(tr:last-child td) {
		border-bottom: 0;
	}

	.markdown-content :global(img),
	.markdown-content :global(video) {
		max-width: 100%;
		height: auto;
		border-radius: 12px;
	}

	.markdown-content :global(input[type='checkbox']) {
		accent-color: rgb(var(--theme-primary-rgb));
		margin-right: 0.45rem;
	}

	.markdown-content :global(.mermaid-render svg) {
		display: block;
		max-width: 100%;
		height: auto;
		margin: 0 auto;
	}

	.markdown-content :global(pre.mermaid-fallback) {
		border-color: rgba(245, 158, 11, 0.35);
	}
</style>