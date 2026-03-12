<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { session } from '$lib/session';
	import GlassCard from '$lib/components/GlassCard.svelte';
	import IconBadge from '$lib/components/IconBadge.svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import FileUploadZone from '$lib/components/FileUploadZone.svelte';
	import { createSubject, createTopic } from '$lib/api/subjects';
	import { uploadDocument, generateFromSubject } from '$lib/api/documents';

	onMount(() => {
		const unsub = session.subscribe((s) => {
			if (!s) goto('/teacher/login');
		});
		return unsub;
	});

	// Wizard state
	let step = $state(1);
	const totalSteps = 6;

	// Step 1: Discipline
	let discipline = $state('');
	let customDiscipline = $state('');
	const disciplines = [
		{ name: 'Chemistry', icon: '🧪' },
		{ name: 'Engineering', icon: '⚙️' },
		{ name: 'Medicine', icon: '🩺' },
		{ name: 'Business', icon: '📊' },
		{ name: 'Law', icon: '⚖️' },
		{ name: 'Arts & Humanities', icon: '🎨' },
		{ name: 'Computer Science', icon: '💻' },
		{ name: 'Mathematics', icon: '📐' },
		{ name: 'Physics', icon: '⚛️' },
		{ name: 'Biology', icon: '🧬' }
	];
	let showCustomInput = $state(false);

	// Step 2: Topics
	let topics = $state<string[]>([]);
	let topicInput = $state('');

	// Step 3: Syllabus
	let syllabus = $state('');

	// Step 4: Reference materials
	let materials = $state<File[]>([]);

	// Step 5: Sample questions
	let sampleQuestions = $state<File[]>([]);

	// Step 6: Training
	let isGenerating = $state(false);
	let progress = $state(0);
	let generationStatus = $state('');
	let generationError = $state('');

	// Computed
	let selectedDiscipline = $derived(showCustomInput ? customDiscipline : discipline);
	let canProceed = $derived.by(() => {
		switch (step) {
			case 1: return selectedDiscipline.trim().length > 0;
			case 2: return topics.length > 0;
			case 3: return syllabus.trim().length > 0;
			case 4: return true; // materials optional
			case 5: return true; // sample questions optional
			case 6: return true;
			default: return false;
		}
	});

	let stepTitle = $derived.by(() => {
		switch (step) {
			case 1: return 'Discipline';
			case 2: return 'Add Topics';
			case 3: return 'Syllabus';
			case 4: return 'Reference Materials';
			case 5: return 'Sample Questions';
			case 6: return 'Train Mode';
			default: return '';
		}
	});

	function selectDiscipline(name: string) {
		discipline = name;
		showCustomInput = false;
	}

	function addTopic() {
		const trimmed = topicInput.trim();
		if (trimmed && !topics.includes(trimmed)) {
			topics = [...topics, trimmed];
			topicInput = '';
		}
	}

	function removeTopic(index: number) {
		topics = topics.filter((_, i) => i !== index);
	}

	function nextStep() {
		if (step < totalSteps && canProceed) {
			step++;
		}
	}

	function prevStep() {
		if (step > 1) {
			step--;
		} else {
			goto('/teacher/train');
		}
	}

	async function startTraining() {
		isGenerating = true;
		progress = 0;
		generationError = '';
		generationStatus = 'Creating subject...';

		try {
			// 1. Create subject
			const prefix = selectedDiscipline.slice(0, 6).toUpperCase().replace(/\s+/g, '');
			const code = prefix + String(Date.now()).slice(-4);
			const subject = await createSubject({
				name: selectedDiscipline,
				code,
			});
			progress = 15;
			generationStatus = 'Adding topics...';

			// 2. Create topics with syllabus content distributed
			for (let i = 0; i < topics.length; i++) {
				await createTopic(subject.id, {
					name: topics[i],
					order_index: i,
					subject_id: subject.id,
					syllabus_content: syllabus || undefined,
				});
			}
			progress = 30;

			// 3. Upload reference materials as primary documents (used for question generation)
			if (materials.length > 0) {
				generationStatus = 'Uploading reference materials...';
				for (let i = 0; i < materials.length; i++) {
					await uploadDocument(materials[i], subject.id, 'primary');
					progress = 30 + Math.round(((i + 1) / materials.length) * 20);
				}
			} else {
				progress = 50;
			}

			// 4. Upload sample questions as template papers
			if (sampleQuestions.length > 0) {
				generationStatus = 'Uploading sample questions...';
				for (let i = 0; i < sampleQuestions.length; i++) {
					await uploadDocument(sampleQuestions[i], subject.id, 'template_paper');
					progress = 50 + Math.round(((i + 1) / sampleQuestions.length) * 10);
				}
			} else {
				progress = 60;
			}

			// 5. Generate questions from uploaded documents via SSE
			generationStatus = 'Generating questions from documents...';
			progress = 65;
			let questionsGenerated = 0;

			try {
				for await (const evt of generateFromSubject({
					subjectId: subject.id,
					context: `${selectedDiscipline}: ${topics.join(', ')}`,
					count: 10,
					types: 'mcq,short_answer',
					difficulty: 'medium',
				})) {
					if (evt.status === 'error') {
						throw new Error(evt.message || 'Generation failed');
					}
					if (evt.progress != null) {
						progress = 65 + Math.round(evt.progress * 0.3);
					}
					if (evt.question) {
						questionsGenerated++;
						generationStatus = `Generated ${questionsGenerated} question${questionsGenerated > 1 ? 's' : ''}...`;
					}
					if (evt.status === 'complete') {
						questionsGenerated = evt.questions_generated ?? questionsGenerated;
					}
				}
			} catch (genErr: unknown) {
				// Generation failed but subject/docs were created — still navigate to loop
				console.warn('Generation error (continuing):', genErr);
			}

			progress = 100;
			generationStatus = questionsGenerated > 0
				? `Done! ${questionsGenerated} questions generated.`
				: 'Setup complete!';

			await new Promise((r) => setTimeout(r, 600));
			goto(`/teacher/train/loop?subject=${subject.id}`);
		} catch (e: unknown) {
			generationError = e instanceof Error ? e.message : 'Setup failed';
			generationStatus = '';
			isGenerating = false;
		}
	}

	function handleTopicKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter') {
			e.preventDefault();
			addTopic();
		}
	}
</script>

<svelte:head>
	<title>{stepTitle} — New Topic — QGen Trainer</title>
</svelte:head>

<PageHeader
	title={stepTitle}
	backHref={step > 1 ? undefined : '/teacher/train'}
	{step}
	{totalSteps}
/>

<div class="wizard">
	<!-- Desktop step indicator -->
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
			<p class="step-desc">Choose a discipline for your training topic</p>
			<div class="discipline-grid">
				{#each disciplines as d}
					<button
						class="discipline-btn"
						class:selected={discipline === d.name && !showCustomInput}
						onclick={() => selectDiscipline(d.name)}
					>
						<span class="d-icon">{d.icon}</span>
						<span class="d-name">{d.name}</span>
					</button>
				{/each}
				<button
					class="discipline-btn"
					class:selected={showCustomInput}
					onclick={() => { showCustomInput = true; discipline = ''; }}
				>
					<span class="d-icon">➕</span>
					<span class="d-name">Custom</span>
				</button>
			</div>
			{#if showCustomInput}
				<input
					class="glass-input custom-input"
					type="text"
					placeholder="Enter your discipline..."
					bind:value={customDiscipline}
				/>
			{/if}

		<!-- Step 2: Topics -->
		{:else if step === 2}
			<p class="step-desc">Add the topics you want to train on</p>
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
			{#if topics.length > 0}
				<div class="topic-list">
					{#each topics as topic, i}
						<div class="topic-chip">
							<span>{topic}</span>
							<button class="chip-remove" onclick={() => removeTopic(i)}>×</button>
						</div>
					{/each}
				</div>
			{/if}

		<!-- Step 3: Syllabus -->
		{:else if step === 3}
			<p class="step-desc">Paste or enter your course syllabus</p>
			<textarea
				class="glass-input syllabus-input"
				placeholder="Paste your syllabus content here...&#10;&#10;You can include course objectives, learning outcomes, weekly topics, etc."
				bind:value={syllabus}
				rows="12"
			></textarea>

		<!-- Step 4: Reference Materials -->
		{:else if step === 4}
			<p class="step-desc">Upload reference materials (textbooks, notes, slides)</p>
			<FileUploadZone
				accept=".pdf,.doc,.docx,.txt,.pptx"
				label="Upload Materials"
				hint="PDF, Word, PowerPoint, or Text files"
				files={materials}
				onfilesSelected={(f) => materials = f}
			/>

		<!-- Step 5: Sample Questions -->
		{:else if step === 5}
			<p class="step-desc">Upload example questions to guide the AI style (optional)</p>
			<FileUploadZone
				accept=".pdf,.doc,.docx,.txt,.csv,.json"
				label="Upload Sample Questions"
				hint="PDF, Word, Text, CSV, or JSON files"
				files={sampleQuestions}
				onfilesSelected={(f) => sampleQuestions = f}
			/>

		<!-- Step 6: Train Mode -->
		{:else if step === 6}
			{#if !isGenerating}
				<div class="train-summary glass">
					<h2 class="summary-title">Ready to Train</h2>
					<div class="summary-grid">
						<div class="summary-item">
							<span class="summary-label">Discipline</span>
							<span class="summary-value">{selectedDiscipline}</span>
						</div>
						<div class="summary-item">
							<span class="summary-label">Topics</span>
							<span class="summary-value">{topics.length} topic{topics.length !== 1 ? 's' : ''}</span>
						</div>
						<div class="summary-item">
							<span class="summary-label">Materials</span>
							<span class="summary-value">{materials.length} file{materials.length !== 1 ? 's' : ''}</span>
						</div>
						<div class="summary-item">
							<span class="summary-label">Sample Qs</span>
							<span class="summary-value">{sampleQuestions.length} file{sampleQuestions.length !== 1 ? 's' : ''}</span>
						</div>
					</div>
					{#if generationError}
						<p class="gen-error">⚠️ {generationError}</p>
					{/if}
				</div>
			{:else}
				<div class="progress-section">
					<div class="progress-icon">⚡</div>
					<h2 class="progress-title">Setting Up</h2>
					<p class="progress-status">{generationStatus}</p>
					<div class="progress-bar-wrap">
						<div class="progress-bar" style:width="{progress}%"></div>
					</div>
					<span class="progress-pct">{progress}%</span>
				</div>
			{/if}
		{/if}
	</div>

	<!-- Navigation -->
	<div class="nav-bar">
		{#if step > 1}
			<button class="glass-btn-secondary nav-btn" onclick={prevStep}>
				← Back
			</button>
		{:else}
			<div></div>
		{/if}

		{#if step < totalSteps}
			<button class="glass-btn nav-btn" onclick={nextStep} disabled={!canProceed}>
				Next Step →
			</button>
		{:else if !isGenerating}
			<button class="glass-btn nav-btn start-btn" onclick={startTraining}>
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

	/* Step bar */
	.step-bar {
		display: flex;
		align-items: center;
		gap: 0;
		margin-bottom: 2rem;
		width: 100%;
		max-width: 320px;
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

	/* Step 1: Disciplines */
	.discipline-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
		gap: 0.75rem;
	}

	.discipline-btn {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.5rem;
		padding: 1rem 0.75rem;
		background: rgba(255, 255, 255, 0.06);
		backdrop-filter: blur(12px);
		-webkit-backdrop-filter: blur(12px);
		border: 0.5px solid rgba(255, 255, 255, 0.12);
		border-radius: var(--glass-radius-sm);
		color: var(--theme-text);
		cursor: pointer;
		transition: all 0.2s;
		font-family: inherit;
		font-size: 0.85rem;
	}

	.discipline-btn:hover {
		background: rgba(255, 255, 255, 0.12);
		border-color: rgba(255, 255, 255, 0.2);
	}

	.discipline-btn.selected {
		background: rgba(var(--theme-primary-rgb), 0.2);
		border-color: rgba(var(--theme-primary-rgb), 0.5);
		color: var(--theme-primary);
	}

	.d-icon {
		font-size: 1.75rem;
	}

	.d-name {
		font-weight: 600;
		text-align: center;
	}

	.custom-input {
		width: 100%;
		padding: 0.75rem 1rem;
		margin-top: 1rem;
		font-size: 0.95rem;
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

	/* Step 3: Syllabus */
	.syllabus-input {
		width: 100%;
		padding: 1rem;
		font-size: 0.95rem;
		resize: vertical;
		min-height: 200px;
		font-family: inherit;
		line-height: 1.6;
	}

	/* Step 6: Training */
	.train-summary {
		padding: 1.5rem;
	}

	.summary-title {
		font-size: 1.25rem;
		font-weight: 700;
		margin: 0 0 1rem;
		text-align: center;
	}

	.summary-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 0.75rem;
	}

	.summary-item {
		display: flex;
		flex-direction: column;
		gap: 0.2rem;
		padding: 0.75rem;
		background: rgba(255, 255, 255, 0.04);
		border-radius: 10px;
	}

	.summary-label {
		font-size: 0.75rem;
		color: var(--theme-text-muted);
		text-transform: uppercase;
		letter-spacing: 0.05em;
		font-weight: 600;
	}

	.summary-value {
		font-size: 0.95rem;
		font-weight: 600;
		color: var(--theme-text);
	}

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

		.discipline-grid {
			grid-template-columns: repeat(auto-fill, minmax(105px, 1fr));
		}
	}
</style>
