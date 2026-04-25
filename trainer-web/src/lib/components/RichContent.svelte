<script lang="ts">
	import { browser } from '$app/environment';
	import { onMount, tick } from 'svelte';
	import MarkdownIt from 'markdown-it';
	import katex from 'katex';
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
			// Unescape literal \n / \t sequences produced by LLM double-escaping
			const inner = String(rawInner || '')
				.replace(/^\n+/, '')
				.replace(/\\n/g, '\n')
				.replace(/\\t/g, '\t');
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

	function restoreCorruptedLatex(value: string): string {
		// Existing DB records may have LaTeX commands corrupted by JSON \t/\b/\f/\r escape parsing.
		// e.g. \times → TAB + "imes", \beta → BACKSPACE + "eta", \frac → FORMFEED + "rac"
		// Restore by replacing control chars followed by letters back to \command form.
		return value
			.replace(/\x09([a-zA-Z]+)/g, '\\t$1')  // TAB + letters → \t... (\times, \theta, etc.)
			.replace(/\x08([a-zA-Z]+)/g, '\\b$1')  // Backspace + letters → \b... (\beta, etc.)
			.replace(/\x0c([a-zA-Z]+)/g, '\\f$1')  // Form feed + letters → \f... (\frac, \forall, etc.)
			.replace(/\x0d([a-zA-Z]+)/g, '\\r$1'); // CR + letters → \r... (\rho, \right, etc.)
	}

	function normalizeMathNotation(value: string): string {
		return mapNonCodeSegments(value, (segment: string) => {
			let next = segment;
			// \(...\) → $...$  and  \[...\] → $$...$$
			next = next.replace(/\\\(([^\n]+?)\\\)/g, (_m: string, expr: string) => `$${expr.trim()}$`);
			next = next.replace(/\\\[([\s\S]+?)\\\]/g, (_m: string, expr: string) => `\n\n$$\n${expr.trim()}\n$$\n\n`);
			// Normalize plain transpose notation: A^T → $A^{T}$
			next = next.replace(/\b([A-Za-z][A-Za-z0-9]*)\s*\^\s*T\b(?!\$)/g, (_m: string, symbol: string) => `$${symbol}^{T}$`);
			return next;
		});
	}

	interface MathPlaceholder {
		key: string;
		html: string;
	}

	function extractAndRenderMath(text: string): { processed: string; placeholders: MathPlaceholder[] } {
		const placeholders: MathPlaceholder[] = [];
		let counter = 0;
		const makeKey = () => `MATHPH${counter++}MATHPH`;
		const opts = { throwOnError: false, trust: false, strict: false } as const;

		// Display math $$...$$ first (before inline to avoid partial matches)
		let processed = text.replace(/\$\$([\s\S]*?)\$\$/g, (_: string, expr: string) => {
			const key = makeKey();
			try {
				const html = katex.renderToString(expr.trim(), { ...opts, displayMode: true });
				placeholders.push({ key, html: `<span class="math-display">${html}</span>` });
			} catch {
				placeholders.push({ key, html: `<span class="math-error">$$${expr}$$</span>` });
			}
			return key;
		});

		// Inline math $...$  — require non-whitespace start/end to avoid false positives
		processed = processed.replace(/\$([^\s$][^$\n]*?[^\s$]|\S)\$/g, (_: string, expr: string) => {
			const key = makeKey();
			try {
				const html = katex.renderToString(expr.trim(), { ...opts, displayMode: false });
				placeholders.push({ key, html: `<span class="math-inline">${html}</span>` });
			} catch {
				placeholders.push({ key, html: `<span class="math-error">$${expr}$</span>` });
			}
			return key;
		});

		return { processed, placeholders };
	}

	function restoreMathPlaceholders(html: string, placeholders: MathPlaceholder[]): string {
		let result = html;
		for (const { key, html: mathHtml } of placeholders) {
			result = result.split(key).join(mathHtml);
		}
		return result;
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
	// Math is handled manually via extractAndRenderMath (KaTeX pre-render + placeholder restore)
	// so no markdown-it-katex plugin needed.

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
				span: ['class', 'style'],
				div: ['class', 'style'],
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
		const restorePass = restoreCorruptedLatex(content || '');
		const normalizedCode = normalizeFencedCodeBlocks(restorePass);
		const normalized = normalizeMathNotation(normalizedCode);
		// Pre-render all math expressions with KaTeX (bypasses broken markdown-it-katex@2.x)
		const { processed, placeholders } = extractAndRenderMath(normalized);
		const raw = processed.trim() ? markdown.render(processed) : '';
		// Restore KaTeX HTML in place of placeholders
		const withMath = restoreMathPlaceholders(raw, placeholders);
		const sanitized = sanitizeMarkup(withMath);
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
