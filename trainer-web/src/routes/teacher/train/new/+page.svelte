<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { session } from '$lib/session';
	import FileUploadZone from '$lib/components/FileUploadZone.svelte';
	import { createSubject, createTopic, extractChapters, updateTopic, type TopicResponse } from '$lib/api/subjects';
	import { uploadDocument } from '$lib/api/documents';

	onMount(() => {
		const unsub = session.subscribe((s) => {
			if (!s) goto('/teacher/login');
		});
		return unsub;
	});

	// ── Wizard state ──
	let step = $state(1);
	const totalSteps = 7;

	// Step 1: Discipline
	const presetDisciplines = [
		{ name: 'Engineering', icon: '⚙️' },
		{ name: 'Medicine', icon: '🩺' },
		{ name: 'Dental', icon: '🦷' },
		{ name: 'Business', icon: '📊' },
		{ name: 'Law', icon: '⚖️' },
		{ name: 'Arts & Humanities', icon: '🎨' }
	] as const;
	let selectedDiscipline = $state('');
	let useCustomDiscipline = $state(false);
	let disciplineName = $state('');
	let disciplineCode = $state('');

	// Step 2: Topics
	interface TopicItem { name: string; syllabusContent: string; }
	let topics = $state<TopicItem[]>([]);
	let topicInput = $state('');
	let importingPdf = $state(false);
	let importError = $state('');
	// We need a temp subject to use extractChapters — we'll create it lazily
	let tempSubjectId = $state('');

	// Step 3: Syllabus per topic
	let expandedTopic = $state(0);

	// Step 4: Reference materials
	let materials = $state<File[]>([]);

	// Step 5: Reference questions
	let refQuestions = $state<File[]>([]);

	// Step 6/7: Setup & generation
	let isSettingUp = $state(false);
	let setupProgress = $state(0);
	let setupStatus = $state('');
	let setupError = $state('');

	// ── Derived ──
	let canProceed = $derived.by(() => {
		switch (step) {
			case 1: return disciplineName.trim().length > 0;
			case 2: return topics.length > 0;
			case 3: return true; // syllabus is optional per topic
			case 4: return true; // reference materials optional
			case 5: return true; // reference questions optional
			case 6: return true; // review
			case 7: return true;
			default: return false;
		}
	});

	let stepTitle = $derived.by(() => {
		switch (step) {
			case 1: return 'Discipline';
			case 2: return 'Topics';
			case 3: return 'Syllabus Content';
			case 4: return 'Reference Materials';
			case 5: return 'Reference Questions';
			case 6: return 'Review';
			case 7: return 'Setting Up';
			default: return '';
		}
	});

	let topicsWithSyllabus = $derived(topics.filter(t => t.syllabusContent.trim().length > 0).length);

	// ── Functions ──
	function syncDisciplineName(value: string) {
		disciplineName = value;
	}

	function handleDisciplineSelection(value: string) {
		useCustomDiscipline = false;
		selectedDiscipline = value;
		syncDisciplineName(value);
	}

	function activateCustomDiscipline() {
		selectedDiscipline = '';
		useCustomDiscipline = true;
		syncDisciplineName('');
	}

	function addTopic() {
		const trimmed = topicInput.trim();
		if (trimmed && !topics.some(t => t.name === trimmed)) {
			topics = [...topics, { name: trimmed, syllabusContent: '' }];
			topicInput = '';
		}
	}

	function removeTopic(index: number) {
		topics = topics.filter((_, i) => i !== index);
		if (expandedTopic >= topics.length) expandedTopic = Math.max(0, topics.length - 1);
	}

	function handleTopicKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter') { e.preventDefault(); addTopic(); }
	}

	async function importFromPdf() {
		const input = document.createElement('input');
		input.type = 'file';
		input.accept = '.pdf,.doc,.docx';
		input.onchange = async () => {
			const file = input.files?.[0];
			if (!file) return;
			importingPdf = true;
			importError = '';
			try {
				// Need a subject to extract chapters — create temp one if needed
				if (!tempSubjectId) {
					const code = disciplineName.trim().slice(0, 6).toUpperCase().replace(/\s+/g, '') + String(Date.now()).slice(-4);
					const subj = await createSubject({
						name: disciplineName.trim(),
						code: disciplineCode.trim() || code,
					});
					tempSubjectId = subj.id;
				}
				const result = await extractChapters(tempSubjectId, file);
				if (result.topics && result.topics.length > 0) {
					const newTopics = result.topics
						.filter(t => !topics.some(existing => existing.name === t.name))
						.map(t => ({
							name: t.name,
							syllabusContent: t.syllabus_content || '',
						}));
					topics = [...topics, ...newTopics];
				}
			} catch (e: unknown) {
				importError = e instanceof Error ? e.message : 'Failed to import chapters';
			} finally {
				importingPdf = false;
			}
		};
		input.click();
	}

	function nextStep() {
		if (step < totalSteps && canProceed) step++;
	}

	function prevStep() {
		if (step > 1) step--;
		else goto('/teacher/train');
	}

	async function startSetup() {
		isSettingUp = true;
		setupProgress = 0;
		setupError = '';
		setupStatus = 'Creating discipline...';

		try {
			// 1. Create subject (or reuse tempSubjectId)
			let subjectId = tempSubjectId;
			if (!subjectId) {
				const code = disciplineCode.trim() || (disciplineName.trim().slice(0, 6).toUpperCase().replace(/\s+/g, '') + String(Date.now()).slice(-4));
				const subj = await createSubject({
					name: disciplineName.trim(),
					code,
				});
				subjectId = subj.id;
			}
			setupProgress = 10;

			// 2. Create topics (or update existing from PDF import)
			setupStatus = 'Adding topics...';
			// Get existing topics from pdf import (already created by extractChapters)
			const existingTopicNames = new Set<string>();
			if (tempSubjectId) {
				// Topics from extractChapters are already created — just need to update syllabus content
				const { getSubject } = await import('$lib/api/subjects');
				try {
					const detail = await getSubject(subjectId);
					for (const t of detail.topics) {
						existingTopicNames.add(t.name);
						// Update syllabus if user edited it
						const local = topics.find(lt => lt.name === t.name);
						if (local && local.syllabusContent.trim() && local.syllabusContent !== (t.syllabus_content || '')) {
							await updateTopic(subjectId, t.id, {
								syllabus_content: local.syllabusContent,
								has_syllabus: true,
							});
						}
					}
				} catch { /* ignore */ }
			}
			// Create any manually-added topics not yet on server
			for (let i = 0; i < topics.length; i++) {
				if (!existingTopicNames.has(topics[i].name)) {
					await createTopic(subjectId, {
						name: topics[i].name,
						order_index: i,
						subject_id: subjectId,
						syllabus_content: topics[i].syllabusContent || undefined,
					});
				}
			}
			setupProgress = 30;

			// 3. Upload reference materials
			if (materials.length > 0) {
				setupStatus = 'Uploading reference materials...';
				for (let i = 0; i < materials.length; i++) {
					await uploadDocument(materials[i], subjectId, 'reference_book');
					setupProgress = 30 + Math.round(((i + 1) / materials.length) * 25);
				}
			} else {
				setupProgress = 55;
			}

			// 4. Upload reference questions
			if (refQuestions.length > 0) {
				setupStatus = 'Uploading reference questions...';
				for (let i = 0; i < refQuestions.length; i++) {
					await uploadDocument(refQuestions[i], subjectId, 'reference_questions');
					setupProgress = 55 + Math.round(((i + 1) / refQuestions.length) * 25);
				}
			} else {
				setupProgress = 80;
			}

			setupProgress = 100;
			setupStatus = 'Setup complete! Redirecting...';
			await new Promise(r => setTimeout(r, 600));
			goto(`/teacher/train/loop?subject=${subjectId}`);
		} catch (e: unknown) {
			setupError = e instanceof Error ? e.message : 'Setup failed';
			setupStatus = '';
			isSettingUp = false;
		}
	}
</script>

<svelte:head>
	<title>{stepTitle} — New Topic — QGen Trainer</title>
</svelte:head>

<div class="wizard">
	<div class="wizard-meta animate-fade-in">
		<p class="wizard-kicker">New Topic Setup</p>
		<div class="wizard-progress-pill">{step}/{totalSteps}</div>
	</div>
	<!-- Step indicator -->
	<div class="step-bar">
		{#each Array(totalSteps) as _, i}
			<div class="step-dot" class:active={i + 1 === step} class:done={i + 1 < step}></div>
			{#if i < totalSteps - 1}
				<div class="step-line" class:done={i + 1 < step}></div>
			{/if}
		{/each}
	</div>

	<h1 class="step-title">{stepTitle}</h1>

	<div class="step-content">
		<!-- Step 1: Discipline -->
		{#if step === 1}
			<p class="step-desc">Pick a discipline card or add your own custom field of study</p>
			<div class="field-group">
				<span class="field-label">Discipline Name *</span>
				<div class="discipline-grid" role="list" aria-label="Choose a discipline">
					{#each presetDisciplines as discipline}
						<button
							type="button"
							class="discipline-card"
							class:selected={!useCustomDiscipline && selectedDiscipline === discipline.name}
							onclick={() => handleDisciplineSelection(discipline.name)}
						>
							<span class="discipline-icon">{discipline.icon}</span>
							<span class="discipline-card-name">{discipline.name}</span>
						</button>
					{/each}
					<button
						type="button"
						class="discipline-card discipline-card-custom"
						class:selected={useCustomDiscipline}
						onclick={activateCustomDiscipline}
					>
						<span class="discipline-icon">＋</span>
						<span class="discipline-card-name">Add Custom Discipline</span>
					</button>
				</div>
				{#if useCustomDiscipline}
					<input
						id="disc-name"
						class="glass-input discipline-custom-input"
						type="text"
						placeholder="e.g., Computer Science"
						bind:value={disciplineName}
					/>
				{/if}
			</div>
			<div class="field-group">
				<label class="field-label" for="disc-code">Subject Code <span class="hint">(optional, auto-generated if empty)</span></label>
				<input id="disc-code" class="glass-input" type="text" placeholder="e.g., CS101" bind:value={disciplineCode} />
			</div>

		<!-- Step 2: Topics -->
		{:else if step === 2}
			<p class="step-desc">Add topics manually or import from a syllabus PDF</p>
			<div class="topic-input-row">
				<input
					class="glass-input topic-input"
					type="text"
					placeholder="e.g., Organic Chemistry"
					bind:value={topicInput}
					onkeydown={handleTopicKeydown}
				/>
				<button class="glass-btn add-btn" onclick={addTopic} disabled={!topicInput.trim()}>Add</button>
			</div>

			<div class="import-row">
				<button class="glass-btn import-btn" onclick={importFromPdf} disabled={importingPdf || !disciplineName.trim()}>
					{#if importingPdf}
						<span class="btn-spinner"></span> Extracting…
					{:else}
						📄 Import from PDF
					{/if}
				</button>
				<span class="import-hint">AI will extract chapters automatically</span>
			</div>
			{#if importError}
				<p class="inline-error">⚠️ {importError}</p>
			{/if}

			{#if topics.length > 0}
				<div class="topic-list">
					{#each topics as topic, i}
						<div class="topic-chip" class:has-syllabus={topic.syllabusContent.trim().length > 0}>
							<span class="topic-number">{i + 1}</span>
							<span>{topic.name}</span>
							{#if topic.syllabusContent.trim()}
								<span class="syllabus-badge">📄</span>
							{/if}
							<button class="chip-remove" onclick={() => removeTopic(i)}>×</button>
						</div>
					{/each}
				</div>
			{/if}

		<!-- Step 3: Syllabus per topic -->
		{:else if step === 3}
			<p class="step-desc">Review and edit syllabus content for each topic</p>
			{#if topics.length === 0}
				<div class="center-msg">
					<span>📭</span>
					<p>No topics added yet. Go back to add topics.</p>
				</div>
			{:else}
				<div class="syllabus-accordion">
					{#each topics as topic, i}
						<div class="syllabus-item" class:expanded={expandedTopic === i}>
							<button class="syllabus-header" onclick={() => expandedTopic = expandedTopic === i ? -1 : i}>
								<div class="sh-left">
									<span class="sh-number">{i + 1}</span>
									<span class="sh-name">{topic.name}</span>
								</div>
								<div class="sh-right">
									{#if topic.syllabusContent.trim()}
										<span class="sh-badge filled">✓ Content</span>
									{:else}
										<span class="sh-badge empty">Empty</span>
									{/if}
									<span class="sh-arrow">{expandedTopic === i ? '▼' : '▶'}</span>
								</div>
							</button>
							{#if expandedTopic === i}
								<div class="syllabus-body">
									<textarea
										class="glass-input syl-textarea"
										placeholder="Paste or type the syllabus content for this topic..."
										bind:value={topics[i].syllabusContent}
										rows="8"
									></textarea>
								</div>
							{/if}
						</div>
					{/each}
				</div>
				<p class="step-hint">{topicsWithSyllabus} of {topics.length} topics have syllabus content</p>
			{/if}

		<!-- Step 4: Reference Materials -->
		{:else if step === 4}
			<p class="step-desc">Upload reference books and study materials for this discipline</p>
			<FileUploadZone
				accept=".pdf,.doc,.docx,.txt,.pptx"
				label="Upload Reference Materials"
				hint="PDF, Word, PowerPoint, or Text — multiple files allowed"
				files={materials}
				onfilesSelected={(f) => materials = [...materials, ...f]}
			/>
			{#if materials.length > 0}
				<div class="file-list">
					{#each materials as file, i}
						<div class="file-item">
							<span class="file-icon">📁</span>
							<span class="file-name">{file.name}</span>
							<span class="file-size">{(file.size / 1024 / 1024).toFixed(1)} MB</span>
							<button class="file-remove" onclick={() => materials = materials.filter((_, j) => j !== i)}>×</button>
						</div>
					{/each}
				</div>
			{/if}

		<!-- Step 5: Reference Questions -->
		{:else if step === 5}
			<p class="step-desc">Upload previous question papers or question banks (optional)</p>
			<FileUploadZone
				accept=".pdf,.doc,.docx,.txt,.csv,.xlsx,.xls"
				label="Upload Reference Questions"
				hint="PDF, Word, Excel, CSV — multiple files allowed"
				files={refQuestions}
				onfilesSelected={(f) => refQuestions = [...refQuestions, ...f]}
			/>
			{#if refQuestions.length > 0}
				<div class="file-list">
					{#each refQuestions as file, i}
						<div class="file-item">
							<span class="file-icon">📋</span>
							<span class="file-name">{file.name}</span>
							<span class="file-size">{(file.size / 1024 / 1024).toFixed(1)} MB</span>
							<button class="file-remove" onclick={() => refQuestions = refQuestions.filter((_, j) => j !== i)}>×</button>
						</div>
					{/each}
				</div>
			{/if}

		<!-- Step 6: Review -->
		{:else if step === 6}
			<div class="review-card glass">
				<h2 class="review-title">Review Setup</h2>
				<div class="review-sections">
					<div class="review-section">
						<span class="rs-label">Discipline</span>
						<span class="rs-value">{disciplineName}{disciplineCode ? ` (${disciplineCode})` : ''}</span>
					</div>
					<div class="review-section">
						<span class="rs-label">Topics</span>
						<div class="rs-topics">
							{#each topics as t, i}
								<span class="rs-topic-chip">
									{i + 1}. {t.name}
									{#if t.syllabusContent.trim()}<span class="rs-syl">📄</span>{/if}
								</span>
							{/each}
						</div>
					</div>
					<div class="review-section">
						<span class="rs-label">Syllabus</span>
						<span class="rs-value">{topicsWithSyllabus} of {topics.length} topics have content</span>
					</div>
					<div class="review-section">
						<span class="rs-label">Reference Materials</span>
						<span class="rs-value">{materials.length} file{materials.length !== 1 ? 's' : ''}</span>
					</div>
					<div class="review-section">
						<span class="rs-label">Reference Questions</span>
						<span class="rs-value">{refQuestions.length} file{refQuestions.length !== 1 ? 's' : ''}</span>
					</div>
				</div>
				{#if setupError}
					<p class="gen-error">⚠️ {setupError}</p>
				{/if}
			</div>

		<!-- Step 7: Setting up -->
		{:else if step === 7}
			<div class="progress-section">
				<div class="progress-icon">⚡</div>
				<h2 class="progress-title">Setting Up</h2>
				<p class="progress-status">{setupStatus || 'Initializing...'}</p>
				<div class="progress-bar-wrap">
					<div class="progress-bar" style:width="{setupProgress}%"></div>
				</div>
				<span class="progress-pct">{setupProgress}%</span>
				{#if setupError}
					<p class="gen-error">⚠️ {setupError}</p>
					<button class="glass-btn" onclick={() => { step = 6; }}>← Back to Review</button>
				{/if}
			</div>
		{/if}
	</div>

	<!-- Navigation -->
	<div class="nav-bar">
		{#if step > 1 && step < 7}
			<button class="glass-btn-secondary nav-btn" onclick={prevStep}>← Back</button>
		{:else}
			<div></div>
		{/if}

		{#if step < 6}
			<button class="glass-btn nav-btn" onclick={nextStep} disabled={!canProceed}>
				{step === 5 ? 'Review →' : 'Next Step →'}
			</button>
		{:else if step === 6 && !isSettingUp}
			<button class="glass-btn nav-btn start-btn" onclick={() => { step = 7; startSetup(); }}>
				⚡ Start Training
			</button>
		{/if}
	</div>
</div>

<style>
	.wizard {
		display: flex;
		flex-direction: column;
		align-items: center;
		min-height: 100vh;
		padding: 2rem 1.5rem 6rem;
		max-width: 600px;
		margin: 0 auto;
	}

	.wizard-meta {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1rem;
		width: 100%;
		margin-bottom: 0.5rem;
	}

	.wizard-kicker {
		margin: 0;
		font-size: 0.78rem;
		font-weight: 700;
		letter-spacing: 0.14em;
		text-transform: uppercase;
		color: var(--theme-primary);
	}

	.wizard-progress-pill {
		min-width: 4.75rem;
		padding: 0.8rem 1rem;
		border-radius: 999px;
		background: rgba(255, 255, 255, 0.12);
		border: 1px solid rgba(255, 255, 255, 0.12);
		color: var(--theme-text);
		font-size: 0.95rem;
		font-weight: 700;
		text-align: center;
	}

	/* Step bar */
	.step-bar {
		display: flex;
		align-items: center;
		gap: 0;
		margin-bottom: 2rem;
		width: 100%;
		max-width: 400px;
	}

	.step-dot {
		width: 10px;
		height: 10px;
		border-radius: 50%;
		background: rgba(255, 255, 255, 0.2);
		flex-shrink: 0;
		transition: all 0.3s;
	}

	.step-dot.active {
		background: var(--theme-primary);
		box-shadow: 0 0 8px var(--theme-glow);
		width: 12px;
		height: 12px;
	}

	.step-dot.done {
		background: var(--theme-primary);
		opacity: 0.6;
	}

	.step-line {
		flex: 1;
		height: 2px;
		background: rgba(255, 255, 255, 0.15);
		transition: background 0.3s;
	}

	.step-line.done {
		background: var(--theme-primary);
		opacity: 0.5;
	}

	.step-title {
		font-size: 1.75rem;
		font-weight: 800;
		margin: 0 0 0.5rem;
		color: var(--theme-text);
		text-align: center;
	}

	.step-content {
		width: 100%;
		margin-top: 1rem;
	}

	.step-desc {
		text-align: center;
		color: var(--theme-text-muted);
		font-size: 0.95rem;
		margin: 0 0 1.5rem;
	}

	.step-hint {
		text-align: center;
		color: var(--theme-text-muted);
		font-size: 0.85rem;
		margin-top: 1rem;
	}

	/* Step 1: Discipline fields */
	.field-group {
		margin-bottom: 1rem;
	}

	.field-label {
		display: block;
		font-size: 0.85rem;
		font-weight: 600;
		color: var(--theme-text);
		margin-bottom: 0.4rem;
	}

	.field-label .hint {
		font-weight: 400;
		color: var(--theme-text-muted);
		font-size: 0.8rem;
	}

	.discipline-grid {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 0.75rem;
	}

	.discipline-card {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		padding: 1rem;
		border-radius: 16px;
		border: 1px solid rgba(255, 255, 255, 0.12);
		background: rgba(255, 255, 255, 0.05);
		color: var(--theme-text);
		cursor: pointer;
		font-family: inherit;
		text-align: left;
		transition: all 0.2s ease;
	}

	.discipline-card:hover {
		background: rgba(255, 255, 255, 0.08);
		border-color: rgba(var(--theme-primary-rgb), 0.28);
	}

	.discipline-card.selected {
		background: rgba(var(--theme-primary-rgb), 0.16);
		border-color: rgba(var(--theme-primary-rgb), 0.45);
		box-shadow: 0 0 0 1px rgba(var(--theme-primary-rgb), 0.2);
	}

	.discipline-icon {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 2.5rem;
		height: 2.5rem;
		border-radius: 12px;
		background: rgba(255, 255, 255, 0.08);
		font-size: 1.25rem;
		flex-shrink: 0;
	}

	.discipline-card-name {
		font-size: 0.95rem;
		font-weight: 600;
	}

	.discipline-card-custom {
		border-style: dashed;
	}

	.discipline-custom-input {
		margin-top: 0.85rem;
	}

	/* Step 2: Topics */
	.topic-input-row {
		display: flex;
		gap: 0.5rem;
	}

	.topic-input {
		flex: 1;
		padding: 0.75rem 1rem;
		font-size: 0.95rem;
	}

	.add-btn {
		padding: 0.75rem 1.25rem;
		font-size: 0.9rem;
	}

	.add-btn:disabled {
		opacity: 0.4;
		cursor: not-allowed;
	}

	.import-row {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		margin-top: 1rem;
	}

	.import-btn {
		white-space: nowrap;
	}

	.import-hint {
		font-size: 0.8rem;
		color: var(--theme-text-muted);
	}

	.inline-error {
		margin: 0.5rem 0 0;
		padding: 0.5rem 0.75rem;
		background: rgba(233, 69, 96, 0.12);
		border-radius: 8px;
		color: #f07888;
		font-size: 0.85rem;
	}

	.btn-spinner {
		display: inline-block;
		width: 14px;
		height: 14px;
		border: 2px solid rgba(255,255,255,0.3);
		border-top-color: var(--theme-primary);
		border-radius: 50%;
		animation: spin 0.7s linear infinite;
	}

	@keyframes spin { to { transform: rotate(360deg); } }

	@media (max-width: 640px) {
		.discipline-grid {
			grid-template-columns: 1fr;
		}
	}

	.topic-list {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
		margin-top: 1rem;
	}

	.topic-chip {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		padding: 0.4rem 0.8rem;
		background: rgba(var(--theme-primary-rgb), 0.15);
		border: 0.5px solid rgba(var(--theme-primary-rgb), 0.3);
		border-radius: 20px;
		font-size: 0.85rem;
		color: var(--theme-text);
	}

	.topic-chip.has-syllabus {
		border-color: rgba(var(--theme-primary-rgb), 0.5);
	}

	.topic-number {
		font-weight: 700;
		font-size: 0.75rem;
		color: var(--theme-primary);
		min-width: 16px;
		text-align: center;
	}

	.syllabus-badge {
		font-size: 0.75rem;
	}

	.chip-remove {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 18px;
		height: 18px;
		border: none;
		border-radius: 50%;
		background: rgba(255, 255, 255, 0.15);
		color: var(--theme-text-muted);
		font-size: 0.8rem;
		cursor: pointer;
		padding: 0;
		line-height: 1;
	}

	.chip-remove:hover {
		background: rgba(233, 69, 96, 0.4);
		color: #fff;
	}

	/* Step 3: Syllabus accordion */
	.center-msg {
		text-align: center;
		padding: 2rem 0;
		color: var(--theme-text-muted);
	}

	.center-msg span {
		font-size: 2rem;
	}

	.syllabus-accordion {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.syllabus-item {
		background: rgba(255, 255, 255, 0.04);
		border: 0.5px solid rgba(255, 255, 255, 0.1);
		border-radius: var(--glass-radius-sm, 12px);
		overflow: hidden;
		transition: border-color 0.2s;
	}

	.syllabus-item.expanded {
		border-color: rgba(var(--theme-primary-rgb), 0.3);
	}

	.syllabus-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		width: 100%;
		padding: 0.75rem 1rem;
		background: none;
		border: none;
		color: var(--theme-text);
		cursor: pointer;
		font-family: inherit;
		font-size: 0.9rem;
	}

	.syllabus-header:hover {
		background: rgba(255, 255, 255, 0.04);
	}

	.sh-left {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	.sh-number {
		font-weight: 700;
		font-size: 0.8rem;
		color: var(--theme-primary);
		min-width: 20px;
	}

	.sh-name {
		font-weight: 600;
	}

	.sh-right {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	.sh-badge {
		font-size: 0.7rem;
		padding: 0.15rem 0.5rem;
		border-radius: 10px;
		font-weight: 600;
	}

	.sh-badge.filled {
		background: rgba(var(--theme-primary-rgb), 0.2);
		color: var(--theme-primary);
	}

	.sh-badge.empty {
		background: rgba(255, 255, 255, 0.08);
		color: var(--theme-text-muted);
	}

	.sh-arrow {
		font-size: 0.7rem;
		color: var(--theme-text-muted);
	}

	.syllabus-body {
		padding: 0 1rem 1rem;
	}

	.syl-textarea {
		width: 100%;
		padding: 0.75rem;
		font-size: 0.9rem;
		resize: vertical;
		min-height: 120px;
		font-family: inherit;
		line-height: 1.5;
	}

	/* Step 4/5: File list */
	.file-list {
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
		margin-top: 1rem;
	}

	.file-item {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.5rem 0.75rem;
		background: rgba(255, 255, 255, 0.04);
		border: 0.5px solid rgba(255, 255, 255, 0.08);
		border-radius: 8px;
		font-size: 0.85rem;
	}

	.file-icon {
		font-size: 1rem;
	}

	.file-name {
		flex: 1;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		color: var(--theme-text);
	}

	.file-size {
		color: var(--theme-text-muted);
		font-size: 0.75rem;
		flex-shrink: 0;
	}

	.file-remove {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 20px;
		height: 20px;
		border: none;
		border-radius: 50%;
		background: rgba(255, 255, 255, 0.1);
		color: var(--theme-text-muted);
		font-size: 0.85rem;
		cursor: pointer;
		padding: 0;
		flex-shrink: 0;
	}

	.file-remove:hover {
		background: rgba(233, 69, 96, 0.35);
		color: #fff;
	}

	/* Step 6: Review */
	.review-card {
		padding: 1.5rem;
	}

	.review-title {
		font-size: 1.25rem;
		font-weight: 700;
		margin: 0 0 1rem;
		text-align: center;
	}

	.review-sections {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}

	.review-section {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		padding: 0.75rem;
		background: rgba(255, 255, 255, 0.04);
		border-radius: 10px;
	}

	.rs-label {
		font-size: 0.75rem;
		color: var(--theme-text-muted);
		text-transform: uppercase;
		letter-spacing: 0.05em;
		font-weight: 600;
	}

	.rs-value {
		font-size: 0.95rem;
		font-weight: 600;
		color: var(--theme-text);
	}

	.rs-topics {
		display: flex;
		flex-wrap: wrap;
		gap: 0.35rem;
	}

	.rs-topic-chip {
		padding: 0.25rem 0.6rem;
		background: rgba(var(--theme-primary-rgb), 0.12);
		border-radius: 12px;
		font-size: 0.8rem;
		color: var(--theme-text);
	}

	.rs-syl {
		font-size: 0.7rem;
	}

	/* Step 7: Progress */
	.progress-section {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.75rem;
		padding: 2rem 0;
	}

	.progress-icon {
		font-size: 2.5rem;
	}

	.progress-title {
		font-size: 1.25rem;
		font-weight: 700;
		margin: 0;
	}

	.progress-status {
		font-size: 0.9rem;
		color: var(--theme-text-muted);
		margin: 0;
		text-align: center;
	}

	.progress-bar-wrap {
		width: 100%;
		max-width: 320px;
		height: 6px;
		background: rgba(255, 255, 255, 0.1);
		border-radius: 3px;
		overflow: hidden;
	}

	.progress-bar {
		height: 100%;
		background: linear-gradient(90deg, var(--theme-primary), var(--theme-primary-hover));
		border-radius: 3px;
		transition: width 0.5s ease;
	}

	.progress-pct {
		font-size: 0.85rem;
		font-weight: 700;
		color: var(--theme-primary);
	}

	.gen-error {
		margin: 1rem 0 0;
		padding: 0.75rem 1rem;
		background: rgba(233, 69, 96, 0.15);
		border: 0.5px solid rgba(233, 69, 96, 0.3);
		border-radius: 10px;
		color: #f07888;
		font-size: 0.88rem;
		text-align: center;
	}

	/* Navigation */
	.nav-bar {
		position: fixed;
		bottom: 0;
		left: 0;
		right: 0;
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 1rem 1.5rem;
		background: rgba(0, 0, 0, 0.2);
		backdrop-filter: blur(20px) saturate(180%);
		-webkit-backdrop-filter: blur(20px) saturate(180%);
		border-top: 0.5px solid rgba(255, 255, 255, 0.08);
		z-index: 20;
	}

	@media (min-width: 769px) {
		.nav-bar {
			left: 260px;
		}
	}

	.nav-btn {
		padding: 0.75rem 1.5rem;
		font-size: 0.95rem;
	}

	.nav-btn:disabled {
		opacity: 0.35;
		cursor: not-allowed;
		transform: none;
		box-shadow: none;
	}

	.start-btn {
		padding: 0.75rem 2rem;
	}

	@media (max-width: 768px) {
		.wizard {
			padding-top: 1rem;
		}

		.step-bar {
			display: none;
		}

		.step-title {
			font-size: 1.35rem;
		}
	}
</style>
