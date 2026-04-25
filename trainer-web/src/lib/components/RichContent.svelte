<script lang="ts">
	import { browser } from '$app/environment';
	import { onMount, tick } from 'svelte';
	import MarkdownIt from 'markdown-it';
	import markdownItKatex from 'markdown-it-katex';
	import hljs from 'highlight.js/lib/common';
	import sanitizeHtml from 'sanitize-html';
	import mermaid from 'mermaid';
	import 'katex/dist/katex.min.css';
	import 'highlight.js/styles/github-dark.min.css';

	export let content = '';
	export let inline = false;
	export let className = '';

	let container: HTMLElement | null = null;
	let renderedHtml = '';
	let mermaidInitialized = false;

	function escapeHtml(value: string): string {
		return value
			.replaceAll('&', '&amp;')
			.replaceAll('<', '&lt;')
			.replaceAll('>', '&gt;')
			.replaceAll('"', '&quot;')
			.replaceAll("'", '&#39;');
	}

	function normalizeFencedCodeBlocks(value: string): string {
		if (!value || !value.includes('```')) return value;
		const fence = '```';
		const unescaped = value.replace(/\\`\\`\\`/g, '```');

		return unescaped.replace(/```([\s\S]*?)```/g, (_match: string, rawInner: string) => {
			const inner = String(rawInner || '').replace(/^\n+/, '');
			let lang = '';
			let code = inner;

			const langMatch = inner.match(/^([A-Za-z0-9_+-]+)(?:\n|[ \t]+)([\s\S]*)$/);
			if (langMatch) {
				lang = langMatch[1];
				code = langMatch[2];
			}

			return `\n\n${fence}${lang}\n${code.trim()}\n${fence}\n\n`;
		});
	}

	function mapNonCodeSegments(value: string, transform: (segment: string) => string): string {
		if (!value) return value;
		const fencePattern = /```[\s\S]*?```/g;
		let out = '';
		let lastIndex = 0;
		for (const match of value.matchAll(fencePattern)) {
			const index = match.index ?? 0;
			out += transform(value.slice(lastIndex, index));
			out += match[0];
			lastIndex = index + match[0].length;
		}
		out += transform(value.slice(lastIndex));
		return out;
	}

	function normalizeMathNotation(value: string): string {
		return mapNonCodeSegments(value, (segment: string) => {
			let next = segment;
			// Normalize escaped LaTeX delimiters to forms markdown-it-katex parses reliably.
			next = next.replace(/\\\(([^\n]+?)\\\)/g, (_m: string, expr: string) => `$${expr.trim()}$`);
			next = next.replace(/\\\[([\s\S]+?)\\\]/g, (_m: string, expr: string) => `\n\n$$\n${expr.trim()}\n$$\n\n`);
			// Normalize common plain transpose notation so it renders as math.
			next = next.replace(/\b([A-Za-z][A-Za-z0-9]*)\s*\^\s*T\b/g, (_m: string, symbol: string) => `$${symbol}^{T}$`);
			return next;
		});
	}

	const markdown: MarkdownIt = new MarkdownIt({
		html: false,
		linkify: true,
		breaks: true,
		highlight(code: string, language: string): string {
			const lang = (language || '').trim();
			const escaped = escapeHtml(code);
			if (lang && hljs.getLanguage(lang)) {
				const highlighted = hljs.highlight(code, { language: lang, ignoreIllegals: true }).value;
				return `<pre class="rich-pre"><code class="hljs language-${lang}">${highlighted}</code></pre>`;
			}
			return `<pre class="rich-pre"><code class="hljs">${escaped}</code></pre>`;
		}
	});
	markdown.use(markdownItKatex as never);

	const allowedTags = [
		...sanitizeHtml.defaults.allowedTags,
		'img',
		'table',
		'thead',
		'tbody',
		'tr',
		'th',
		'td',
		'span',
		'div',
		'pre',
		'code',
		'svg',
		'g',
		'path',
		'line',
		'polyline',
		'polygon',
		'rect',
		'circle',
		'ellipse',
		'text'
	];

	function sanitizeMarkup(markup: string): string {
		return sanitizeHtml(markup, {
			allowedTags,
			allowedAttributes: {
				...sanitizeHtml.defaults.allowedAttributes,
				a: ['href', 'name', 'target', 'rel'],
				img: ['src', 'alt', 'title', 'width', 'height'],
				code: ['class'],
				span: ['class'],
				div: ['class'],
				pre: ['class'],
				table: ['class'],
				svg: [
					'viewBox',
					'width',
					'height',
					'xmlns',
					'fill',
					'stroke',
					'stroke-width',
					'stroke-linecap',
					'stroke-linejoin',
					'role',
					'aria-label'
				],
				g: ['fill', 'stroke', 'stroke-width', 'transform'],
				path: ['d', 'fill', 'stroke', 'stroke-width', 'transform'],
				line: ['x1', 'y1', 'x2', 'y2', 'stroke', 'stroke-width'],
				polyline: ['points', 'stroke', 'stroke-width', 'fill'],
				polygon: ['points', 'stroke', 'stroke-width', 'fill'],
				rect: ['x', 'y', 'width', 'height', 'rx', 'ry', 'stroke', 'stroke-width', 'fill'],
				circle: ['cx', 'cy', 'r', 'stroke', 'stroke-width', 'fill'],
				ellipse: ['cx', 'cy', 'rx', 'ry', 'stroke', 'stroke-width', 'fill'],
				text: ['x', 'y', 'dx', 'dy', 'text-anchor', 'font-size', 'fill']
			},
			allowedSchemes: ['http', 'https', 'mailto', 'data'],
			allowedSchemesByTag: {
				img: ['http', 'https', 'data']
			}
		});
	}

	function toInline(markup: string): string {
		return markup.replace(/^<p>/, '').replace(/<\/p>\s*$/, '');
	}

	async function renderMermaidBlocks(): Promise<void> {
		if (!browser || !container) return;
		if (!mermaidInitialized) {
			mermaid.initialize({
				startOnLoad: false,
				theme: 'neutral',
				securityLevel: 'strict'
			});
			mermaidInitialized = true;
		}

		const codeBlocks = Array.from(
			container.querySelectorAll<HTMLElement>('pre code.language-mermaid, pre code.lang-mermaid')
		);
		for (const codeNode of codeBlocks) {
			const source = codeNode.textContent?.trim();
			const hostPre = codeNode.closest('pre');
			if (!source || !hostPre) continue;
			const id = `mermaid-${Math.random().toString(36).slice(2, 10)}`;
			try {
				const result = await mermaid.render(id, source);
				const wrapper = document.createElement('div');
				wrapper.className = 'mermaid-render';
				wrapper.innerHTML = result.svg;
				hostPre.replaceWith(wrapper);
			} catch {
				hostPre.classList.add('mermaid-error');
			}
		}
	}

	async function renderContent(): Promise<void> {
		const normalizedCode = normalizeFencedCodeBlocks(content || '');
		const normalized = normalizeMathNotation(normalizedCode);
		const raw = normalized.trim() ? markdown.render(normalized) : '';
		const sanitized = sanitizeMarkup(raw || '');
		renderedHtml = inline ? toInline(sanitized) : sanitized;
		if (!browser) return;
		await tick();
		await renderMermaidBlocks();
	}

	$: void renderContent();

	onMount(async () => {
		await renderMermaidBlocks();
	});
</script>

{#if inline}
	<span class={`rich-content rich-inline ${className}`}>{@html renderedHtml}</span>
{:else}
	<div bind:this={container} class={`rich-content ${className}`}>{@html renderedHtml}</div>
{/if}

<style>
	.rich-content {
		line-height: 1.5;
		word-break: break-word;
	}

	.rich-content :global(p) {
		margin: 0.35rem 0;
	}

	.rich-content :global(.rich-pre) {
		margin: 0.4rem 0;
		padding: 0.55rem 0.65rem;
		border-radius: 0.55rem;
		overflow-x: auto;
		background: rgba(15, 23, 42, 0.72);
	}

	.rich-content :global(code) {
		font-family: 'JetBrains Mono', 'Fira Code', ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas,
			'Liberation Mono', monospace;
		font-size: 0.9em;
	}

	.rich-content :global(.katex-display) {
		overflow-x: auto;
		overflow-y: hidden;
		padding: 0.2rem 0;
	}

	.rich-content :global(.mermaid-render) {
		margin: 0.5rem 0;
		padding: 0.5rem;
		border-radius: 0.55rem;
		background: rgba(148, 163, 184, 0.09);
		overflow-x: auto;
	}

	.rich-content :global(pre.mermaid-error) {
		border: 1px dashed rgba(239, 68, 68, 0.6);
	}

	.rich-inline :global(p) {
		display: inline;
		margin: 0;
	}
</style>
