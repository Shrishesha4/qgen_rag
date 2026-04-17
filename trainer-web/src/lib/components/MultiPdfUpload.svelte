<script lang="ts">
	export interface PdfFileProgress {
		percent: number;
		detail: string;
		error?: string;
	}

	interface Props {
		files?: File[];
		onchange: (files: File[]) => void;
		disabled?: boolean;
		progress?: Record<string, PdfFileProgress>;
		label?: string;
	}

	let {
		files = [],
		onchange,
		disabled = false,
		progress = {},
		label = 'Upload PDFs',
	}: Props = $props();

	let dragOver = $state(false);
	let inputEl: HTMLInputElement;

	function addFiles(incoming: File[]) {
		const pdfs = incoming.filter(
			(f) => f.type === 'application/pdf' || f.name.toLowerCase().endsWith('.pdf')
		);
		const existing = new Set(files.map((f) => f.name));
		const fresh = pdfs.filter((f) => !existing.has(f.name));
		if (fresh.length) onchange([...files, ...fresh]);
	}

	function removeFile(index: number) {
		onchange(files.filter((_, i) => i !== index));
	}

	function handleDrop(e: DragEvent) {
		e.preventDefault();
		dragOver = false;
		if (!disabled && e.dataTransfer?.files) {
			addFiles(Array.from(e.dataTransfer.files));
		}
	}

	function handleInput(e: Event) {
		const target = e.target as HTMLInputElement;
		if (!disabled && target.files) {
			addFiles(Array.from(target.files));
			target.value = '';
		}
	}

	function formatSize(bytes: number): string {
		if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
		return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
	}
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="multi-pdf-upload">
	<div
		class="drop-zone"
		class:drag-over={dragOver}
		class:is-disabled={disabled}
		role="button"
		tabindex={disabled ? -1 : 0}
		aria-label={label}
		onclick={() => { if (!disabled) inputEl.click(); }}
		ondragover={(e) => { e.preventDefault(); if (!disabled) dragOver = true; }}
		ondragleave={() => (dragOver = false)}
		ondrop={handleDrop}
		onkeydown={(e) => { if (!disabled && (e.key === 'Enter' || e.key === ' ')) inputEl.click(); }}
	>
		<input
			bind:this={inputEl}
			type="file"
			accept=".pdf,application/pdf"
			multiple
			onchange={handleInput}
			hidden
			{disabled}
		/>
		<span class="drop-icon">📄</span>
		<span class="drop-label">{label}</span>
		<span class="drop-hint">Drag & drop or click to browse · multiple PDFs allowed</span>
	</div>

	{#if files.length > 0}
		<ul class="file-queue">
			{#each files as file, i}
				{@const prog = progress[file.name]}
				<li class="file-row" class:is-uploading={!!prog}>
					<span class="file-thumb">📄</span>
					<div class="file-meta">
						<span class="file-name">{file.name}</span>
						<span class="file-size">{formatSize(file.size)}</span>
						{#if prog}
							<div class="prog-track">
								<div class="prog-fill" style="width: {prog.percent}%"></div>
							</div>
							{#if prog.detail}
								<span class="prog-detail">{prog.detail}</span>
							{/if}
						{/if}
					</div>
					{#if prog}
						<span class="prog-pct">{prog.percent}%</span>
					{:else}
						<button
							class="remove-btn"
							onclick={(e) => { e.stopPropagation(); removeFile(i); }}
							aria-label="Remove {file.name}"
							{disabled}
						>×</button>
					{/if}
				</li>
			{/each}
		</ul>
	{/if}
</div>

<style>
	.multi-pdf-upload {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.drop-zone {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 0.4rem;
		padding: 1.5rem 1rem;
		border: 2px dashed rgba(255, 255, 255, 0.2);
		border-radius: var(--glass-radius, 12px);
		background: rgba(255, 255, 255, 0.04);
		cursor: pointer;
		transition: all 0.2s ease;
		outline: none;
		text-align: center;
	}

	.drop-zone:hover,
	.drop-zone.drag-over {
		border-color: rgba(var(--theme-primary-rgb, 99, 102, 241), 0.55);
		background: rgba(255, 255, 255, 0.07);
	}

	.drop-zone.is-disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.drop-icon {
		font-size: 1.8rem;
		opacity: 0.8;
	}

	.drop-label {
		font-weight: 600;
		font-size: 0.95rem;
		color: var(--theme-text);
	}

	.drop-hint {
		font-size: 0.8rem;
		color: var(--theme-text-muted);
	}

	.file-queue {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
	}

	.file-row {
		display: flex;
		align-items: flex-start;
		gap: 0.6rem;
		padding: 0.55rem 0.75rem;
		border-radius: 8px;
		background: rgba(255, 255, 255, 0.06);
		border: 0.5px solid rgba(255, 255, 255, 0.12);
		transition: background 0.15s;
	}

	.file-row.is-uploading {
		background: rgba(var(--theme-primary-rgb, 99, 102, 241), 0.08);
	}

	.file-thumb {
		font-size: 1.1rem;
		flex-shrink: 0;
		padding-top: 0.05rem;
	}

	.file-meta {
		flex: 1;
		min-width: 0;
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
	}

	.file-name {
		font-size: 0.85rem;
		color: var(--theme-text);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		max-width: 100%;
	}

	.file-size {
		font-size: 0.75rem;
		color: var(--theme-text-muted);
	}

	.prog-track {
		height: 4px;
		border-radius: 2px;
		background: rgba(255, 255, 255, 0.12);
		overflow: hidden;
		margin-top: 0.2rem;
	}

	.prog-fill {
		height: 100%;
		background: var(--theme-primary, #6366f1);
		border-radius: 2px;
		transition: width 0.25s ease;
	}

	.prog-detail {
		font-size: 0.72rem;
		color: var(--theme-text-muted);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.prog-pct {
		font-size: 0.8rem;
		font-weight: 600;
		color: var(--theme-primary, #6366f1);
		white-space: nowrap;
		padding-top: 0.05rem;
	}

	.remove-btn {
		all: unset;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 20px;
		height: 20px;
		border-radius: 50%;
		background: rgba(255, 255, 255, 0.12);
		color: var(--theme-text-muted);
		font-size: 1rem;
		cursor: pointer;
		flex-shrink: 0;
		transition: background 0.15s, color 0.15s;
	}

	.remove-btn:hover:not(:disabled) {
		background: rgba(233, 69, 96, 0.4);
		color: #fff;
	}

	.remove-btn:disabled {
		opacity: 0.4;
		cursor: not-allowed;
	}
</style>
