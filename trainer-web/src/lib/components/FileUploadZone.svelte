<script lang="ts">
	interface Props {
		onfilesSelected: (files: File[]) => void;
		accept?: string;
		label?: string;
		hint?: string;
		files?: File[];
	}

	let { onfilesSelected, accept = '*', label = 'Upload files', hint = 'Drag & drop or click to browse', files = [] }: Props = $props();

	let dragOver = $state(false);
	let inputEl: HTMLInputElement;

	function handleDrop(e: DragEvent) {
		e.preventDefault();
		dragOver = false;
		if (e.dataTransfer?.files) {
			onfilesSelected(Array.from(e.dataTransfer.files));
		}
	}

	function handleInput(e: Event) {
		const target = e.target as HTMLInputElement;
		if (target.files) {
			onfilesSelected(Array.from(target.files));
		}
	}

	function removeFile(index: number) {
		const updated = files.filter((_, i) => i !== index);
		onfilesSelected(updated);
	}
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
	class="upload-zone"
	class:drag-over={dragOver}
	ondragover={(e) => { e.preventDefault(); dragOver = true; }}
	ondragleave={() => dragOver = false}
	ondrop={handleDrop}
	onclick={() => inputEl.click()}
	role="button"
	tabindex="0"
	onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') inputEl.click(); }}
>
	<input bind:this={inputEl} type="file" {accept} multiple onchange={handleInput} hidden />
	<div class="upload-icon">📁</div>
	<p class="upload-label">{label}</p>
	<p class="upload-hint">{hint}</p>
</div>

{#if files.length > 0}
	<div class="file-list">
		{#each files as file, i}
			<div class="file-chip">
				<span class="file-name">{file.name}</span>
				<button
					class="remove-btn"
					onclick={(e) => { e.stopPropagation(); removeFile(i); }}
					aria-label="Remove {file.name}"
				>×</button>
			</div>
		{/each}
	</div>
{/if}

<style>
	.upload-zone {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		padding: 2rem 1.5rem;
		border: 2px dashed rgba(255, 255, 255, 0.2);
		border-radius: var(--glass-radius);
		background: rgba(255, 255, 255, 0.04);
		cursor: pointer;
		transition: all 0.2s ease;
		outline: none;
		gap: 0.5rem;
	}

	.upload-zone:hover, .drag-over {
		background: rgba(255, 255, 255, 0.08);
		border-color: rgba(var(--theme-primary-rgb), 0.5);
	}

	.upload-icon {
		font-size: 2rem;
		opacity: 0.8;
	}

	.upload-label {
		font-weight: 600;
		color: var(--theme-text);
		margin: 0;
	}

	.upload-hint {
		font-size: 0.85rem;
		color: var(--theme-text-muted);
		margin: 0;
	}

	.file-list {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
		margin-top: 0.75rem;
	}

	.file-chip {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		padding: 0.35rem 0.75rem;
		background: rgba(255, 255, 255, 0.1);
		border: 0.5px solid rgba(255, 255, 255, 0.15);
		border-radius: 8px;
		font-size: 0.85rem;
		color: var(--theme-text);
	}

	.file-name {
		max-width: 150px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.remove-btn {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 18px;
		height: 18px;
		border: none;
		border-radius: 50%;
		background: rgba(255, 255, 255, 0.15);
		color: var(--theme-text-muted);
		font-size: 0.9rem;
		cursor: pointer;
		line-height: 1;
		padding: 0;
	}

	.remove-btn:hover {
		background: rgba(233, 69, 96, 0.4);
		color: #fff;
	}
</style>
