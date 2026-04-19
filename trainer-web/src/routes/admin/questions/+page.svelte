<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { session } from '$lib/session';
	import {
		downloadAdminQuestionExport,
		getAdminSubject,
		listAdminQuestionProviders,
		listAdminQuestions,
		listAdminSubjects,
		previewAdminQuestionExport,
		type AdminQuestionExportColumn,
		type AdminQuestionExportField,
		type AdminQuestionFeedParams,
		type AdminQuestionSummary,
		type AdminSubjectSummary,
		type AdminTopicSummary
	} from '$lib/api/admin';

	const PAGE_SIZE = 40;
	const EXPORT_PREVIEW_DEBOUNCE_MS = 220;
	const topicsBySubject = new Map<string, AdminTopicSummary[]>();

	type FilterOption = {
		value: string;
		label: string;
	};

	type ExportFieldGroup = {
		group: string;
		fields: AdminQuestionExportField[];
	};

	const VETTING_STATUS_OPTIONS: FilterOption[] = [
		{ value: 'all', label: 'All' },
		{ value: 'pending', label: 'Pendin' },
		{ value: 'approved', label: 'Appr' },
		{ value: 'rejected', label: 'Reject' }
	];

	const QUESTION_TYPE_OPTIONS: FilterOption[] = [
		{ value: 'all', label: 'Any type' },
		{ value: 'mcq', label: 'MCQ' },
		{ value: 'short_answer', label: 'Short answer' },
		{ value: 'long_answer', label: 'Long answer' },
		{ value: 'essay', label: 'Essay' },
		{ value: 'true_false', label: 'True/false' },
		{ value: 'unspecified', label: 'Unspecified' }
	];

	const DIFFICULTY_OPTIONS: FilterOption[] = [
		{ value: 'all', label: 'Any difficulty' },
		{ value: 'easy', label: 'Easy' },
		{ value: 'medium', label: 'Medium' },
		{ value: 'hard', label: 'Hard' },
		{ value: 'unspecified', label: 'Unspecified' }
	];

	const BLOOM_OPTIONS: FilterOption[] = [
		{ value: 'all', label: 'Any Bloom level' },
		{ value: 'remember', label: 'Remember' },
		{ value: 'understand', label: 'Understand' },
		{ value: 'apply', label: 'Apply' },
		{ value: 'analyze', label: 'Analyze' },
		{ value: 'evaluate', label: 'Evaluate' },
		{ value: 'create', label: 'Create' },
		{ value: 'unspecified', label: 'Unspecified' }
	];

	const GENERATION_STATUS_OPTIONS: FilterOption[] = [
		{ value: 'all', label: 'Any generation result' },
		{ value: 'accepted', label: 'Accepted' },
		{ value: 'discarded', label: 'Discarded' }
	];

	const REFERENCE_OPTIONS: FilterOption[] = [
		{ value: 'all', label: 'Any source basis' },
		{ value: 'with_reference', label: 'Reference-backed' },
		{ value: 'without_reference', label: 'No references used' }
	];

	const VERSION_SCOPE_OPTIONS: FilterOption[] = [
		{ value: 'latest', label: 'Latest records only' },
		{ value: 'all', label: 'All versions' }
	];

	const ARCHIVED_OPTIONS: FilterOption[] = [
		{ value: 'active', label: 'Active only' },
		{ value: 'archived', label: 'Archived only' },
		{ value: 'all', label: 'Active + archived' }
	];

	const PROVIDER_FILTER_ALL = '__all__';

	let loading = $state(true);
	let loadingMore = $state(false);
	let error = $state('');
	let subjects = $state<AdminSubjectSummary[]>([]);
	let topics = $state<AdminTopicSummary[]>([]);
	let providerKeys = $state<string[]>([]);
	let questions = $state<AdminQuestionSummary[]>([]);
	let totalQuestions = $state(0);

	let selectedSubjectId = $state('');
	let selectedTopicId = $state('');
	let selectedStatus = $state<'all' | 'pending' | 'approved' | 'rejected'>('all');
	let selectedQuestionType = $state('all');
	let selectedDifficulty = $state('all');
	let selectedBloom = $state('all');
	let selectedGenerationStatus = $state('all');
	let selectedReferenceMode = $state('all');
	let selectedProviderKey = $state(PROVIDER_FILTER_ALL);
	let selectedVersionScope = $state('latest');
	let selectedArchivedState = $state('active');

	let subjectSearch = $state('');
	let topicSearch = $state('');
	let subjectMenuOpen = $state(false);
	let topicMenuOpen = $state(false);

	let nextCursor = $state<string | null>(null);
	let hasMore = $state(true);
	let requestSequence = 0;
	let exportFields = $state<AdminQuestionExportField[]>([]);
	let selectedExportFieldKeys = $state<string[]>([]);
	let previewColumns = $state<AdminQuestionExportColumn[]>([]);
	let previewRows = $state<Record<string, string>[]>([]);
	let previewLoading = $state(false);
	let previewError = $state('');
	let exporting = $state(false);
	let exportModalOpen = $state(false);
	let exportRequestSequence = 0;
	let exportPreviewDebounce: ReturnType<typeof setTimeout> | null = null;

	onMount(() => {
		const unsub = session.subscribe((s) => {
			if (!s || s.user.role !== 'admin') {
				goto('/admin/login');
			}
		});

		void loadInitialData();
		return () => {
			if (exportPreviewDebounce) {
				clearTimeout(exportPreviewDebounce);
			}
			unsub();
		};
	});

	function clickOutside(node: HTMLElement, onClose: () => void) {
		function handle(event: MouseEvent) {
			if (node.contains(event.target as Node)) return;
			onClose();
		}

		document.addEventListener('mousedown', handle);
		return {
			destroy() {
				document.removeEventListener('mousedown', handle);
			}
		};
	}

	function getLoadErrorMessage(value: unknown, fallback: string): string {
		const message = value instanceof Error ? value.message : fallback;
		if (message === 'Not Found') {
			return 'Admin questions API is unavailable. Reload the backend service and retry.';
		}
		return message || fallback;
	}

	function currentQuestionFilters(): AdminQuestionFeedParams {
		return {
			subject_id: selectedSubjectId || undefined,
			topic_id: selectedTopicId || undefined,
			vetting_status: selectedStatus,
			question_type: selectedQuestionType as
				| 'mcq'
				| 'short_answer'
				| 'long_answer'
				| 'essay'
				| 'true_false'
				| 'unspecified'
				| 'all',
			difficulty_level: selectedDifficulty as 'easy' | 'medium' | 'hard' | 'unspecified' | 'all',
			bloom_taxonomy_level: selectedBloom as
				| 'remember'
				| 'understand'
				| 'apply'
				| 'analyze'
				| 'evaluate'
				| 'create'
				| 'unspecified'
				| 'all',
			generation_status: selectedGenerationStatus as 'accepted' | 'discarded' | 'all',
			reference_mode: selectedReferenceMode as 'with_reference' | 'without_reference' | 'all',
			provider_key: selectedProviderKey === PROVIDER_FILTER_ALL ? undefined : selectedProviderKey,
			version_scope: selectedVersionScope as 'latest' | 'all',
			archived_state: selectedArchivedState as 'active' | 'archived' | 'all'
		};
	}

	async function loadInitialData() {
		loading = true;
		error = '';
		try {
			subjects = await listAdminSubjects();
			providerKeys = await listAdminQuestionProviders();
			await loadQuestions(true);
		} catch (e: unknown) {
			error = getLoadErrorMessage(e, 'Failed to load admin questions');
			loading = false;
		}
	}

	function closeSubjectMenu() {
		subjectMenuOpen = false;
		if (selectedSubjectId) {
			subjectSearch = subjects.find((subject) => subject.id === selectedSubjectId)?.name ?? subjectSearch;
		}
	}

	function closeTopicMenu() {
		topicMenuOpen = false;
		if (selectedTopicId) {
			topicSearch = topics.find((topic) => topic.id === selectedTopicId)?.name ?? topicSearch;
		}
	}

	async function loadTopicsForSubject(subjectId: string) {
		if (!subjectId) {
			topics = [];
			return;
		}

		const cachedTopics = topicsBySubject.get(subjectId);
		if (cachedTopics) {
			topics = cachedTopics;
			return;
		}

		const subject = await getAdminSubject(subjectId);
		const nextTopics = [...subject.topics].sort((left, right) => left.order_index - right.order_index);
		topicsBySubject.set(subjectId, nextTopics);
		topics = nextTopics;
	}

	async function loadQuestions(reset = false) {
		if (!reset && (loading || loadingMore || !hasMore || !nextCursor)) {
			return;
		}

		const requestId = ++requestSequence;
		if (reset) {
			loading = true;
			loadingMore = false;
			error = '';
			questions = [];
			totalQuestions = 0;
			nextCursor = null;
			hasMore = true;
		} else {
			loadingMore = true;
		}

		try {
			const response = await listAdminQuestions({
				...currentQuestionFilters(),
				cursor: reset ? undefined : nextCursor || undefined,
				limit: PAGE_SIZE
			});

			if (requestId !== requestSequence) {
				return;
			}

			questions = reset ? response.questions : [...questions, ...response.questions];
			totalQuestions = response.total_count;
			nextCursor = response.next_cursor;
			hasMore = response.has_more;
			if (reset) {
				scheduleExportPreview();
			}
		} catch (e: unknown) {
			if (requestId !== requestSequence) {
				return;
			}
			error = getLoadErrorMessage(e, 'Failed to load questions');
		} finally {
			if (requestId === requestSequence) {
				loading = false;
				loadingMore = false;
			}
		}
	}

	async function handleSubjectChange(subjectId: string) {
		selectedSubjectId = subjectId;
		selectedTopicId = '';
		topicSearch = '';
		error = '';

		if (!subjectId) {
			topics = [];
			await loadQuestions(true);
			return;
		}

		try {
			await loadTopicsForSubject(subjectId);
		} catch (e: unknown) {
			topics = [];
			error = getLoadErrorMessage(e, 'Failed to load topics');
		}

		await loadQuestions(true);
	}

	async function handleTopicChange(topicId: string) {
		selectedTopicId = topicId;
		await loadQuestions(true);
	}

	async function selectSubject(subject: AdminSubjectSummary | null) {
		subjectMenuOpen = false;
		subjectSearch = subject?.name ?? '';
		await handleSubjectChange(subject?.id ?? '');
	}

	async function selectTopic(topic: AdminTopicSummary | null) {
		topicMenuOpen = false;
		topicSearch = topic?.name ?? '';
		await handleTopicChange(topic?.id ?? '');
	}

	async function clearSubjectFilter() {
		subjectSearch = '';
		subjectMenuOpen = false;
		await handleSubjectChange('');
	}

	async function clearTopicFilter() {
		topicSearch = '';
		topicMenuOpen = false;
		await handleTopicChange('');
	}

	async function setStatusFilter(value: 'all' | 'pending' | 'approved' | 'rejected') {
		selectedStatus = value;
		await loadQuestions(true);
	}

	async function handleAdvancedFilterChange() {
		await loadQuestions(true);
	}

	async function clearFilters() {
		selectedSubjectId = '';
		selectedTopicId = '';
		selectedStatus = 'all';
		selectedQuestionType = 'all';
		selectedDifficulty = 'all';
		selectedBloom = 'all';
		selectedGenerationStatus = 'all';
		selectedReferenceMode = 'all';
		selectedProviderKey = PROVIDER_FILTER_ALL;
		selectedVersionScope = 'latest';
		selectedArchivedState = 'active';
		subjectSearch = '';
		topicSearch = '';
		subjectMenuOpen = false;
		topicMenuOpen = false;
		topics = [];
		await loadQuestions(true);
	}

	async function loadMoreQuestions() {
		await loadQuestions(false);
	}

	function scheduleExportPreview() {
		if (exportPreviewDebounce) {
			clearTimeout(exportPreviewDebounce);
		}
		exportPreviewDebounce = setTimeout(() => {
			void loadExportPreview();
		}, EXPORT_PREVIEW_DEBOUNCE_MS);
	}

	async function loadExportPreview() {
		const requestId = ++exportRequestSequence;
		previewLoading = true;
		previewError = '';

		try {
			const response = await previewAdminQuestionExport(currentQuestionFilters(), selectedExportFieldKeys);
			if (requestId !== exportRequestSequence) {
				return;
			}

			exportFields = response.available_fields;
			selectedExportFieldKeys = response.selected_fields.map((column) => column.key);
			previewColumns = response.selected_fields;
			previewRows = response.rows;
		} catch (e: unknown) {
			if (requestId !== exportRequestSequence) {
				return;
			}
			previewError = getLoadErrorMessage(e, 'Failed to load export preview');
		} finally {
			if (requestId === exportRequestSequence) {
				previewLoading = false;
			}
		}
	}

	function toggleExportField(fieldKey: string, checked: boolean) {
		const working = checked
			? [...selectedExportFieldKeys, fieldKey]
			: selectedExportFieldKeys.filter((value) => value !== fieldKey);

		const orderedKeys = (exportFields.length ? exportFields.map((field) => field.key) : working).filter(
			(key, index, allKeys) => working.includes(key) && allKeys.indexOf(key) === index
		);

		if (orderedKeys.length === 0) {
			previewError = 'Select at least one export column.';
			return;
		}

		selectedExportFieldKeys = orderedKeys;
		previewError = '';
		scheduleExportPreview();
	}

	function resetExportFieldsToDefault() {
		const defaultKeys = exportFields
			.filter((field) => field.selected_by_default)
			.map((field) => field.key);
		if (defaultKeys.length === 0) {
			return;
		}

		selectedExportFieldKeys = defaultKeys;
		previewError = '';
		scheduleExportPreview();
	}

	async function handleExportDownload() {
		exporting = true;
		previewError = '';
		try {
			const { blob, filename } = await downloadAdminQuestionExport(
				currentQuestionFilters(),
				selectedExportFieldKeys
			);
			const objectUrl = URL.createObjectURL(blob);
			const anchor = document.createElement('a');
			anchor.href = objectUrl;
			anchor.download = filename;
			document.body.append(anchor);
			anchor.click();
			anchor.remove();
			setTimeout(() => URL.revokeObjectURL(objectUrl), 0);
		} catch (e: unknown) {
			previewError = getLoadErrorMessage(e, 'Failed to export questions');
		} finally {
			exporting = false;
		}
	}

	function openExportModal() {
		exportModalOpen = true;
		if (previewColumns.length === 0 && !previewLoading) {
			scheduleExportPreview();
		}
	}

	function closeExportModal() {
		exportModalOpen = false;
	}

	function infiniteSentinel(node: HTMLElement) {
		const observer = new IntersectionObserver(
			(entries) => {
				if (entries[0]?.isIntersecting) {
					void loadMoreQuestions();
				}
			},
			{ rootMargin: '260px 0px 260px 0px', threshold: 0 }
		);

		observer.observe(node);
		return {
			destroy() {
				observer.disconnect();
			}
		};
	}

	function formatDate(value: string): string {
		const normalized = /[Zz]$|[+-]\d{2}:\d{2}$/.test(value) ? value : value + 'Z';
		return new Date(normalized).toLocaleString();
	}

	function typeLabel(value: string | null): string {
		if (value === 'mcq') return 'MCQ';
		if (value === 'short_answer') return 'Short answer';
		if (value === 'long_answer') return 'Long answer';
		if (value === 'true_false') return 'True/false';
		if (value === 'essay') return 'Essay';
		return value ? value.replace(/_/g, ' ') : 'Unspecified type';
	}

	function difficultyLabel(value: string | null): string {
		return value ? value.charAt(0).toUpperCase() + value.slice(1) : 'Unspecified difficulty';
	}

	function statusLabel(value: string): string {
		return value.charAt(0).toUpperCase() + value.slice(1);
	}

	function statusClass(value: string): string {
		if (value === 'approved') return 'approved';
		if (value === 'rejected') return 'rejected';
		return 'pending';
	}

	function generationClass(value: string): string {
		return value === 'discarded' ? 'rejected' : 'accepted';
	}

	function referenceClass(value: boolean): string {
		return value ? 'accepted' : 'neutral';
	}

	function archivedLabel(question: AdminQuestionSummary): string {
		return question.is_archived ? 'Archived' : question.is_latest ? `v${question.version_number} latest` : `v${question.version_number}`;
	}

	function formatScore(value: number | null): string {
		return value == null ? '—' : value.toFixed(2);
	}

	function formatOptionalText(value: string | null, fallback: string): string {
		return value && value.trim() ? value : fallback;
	}

	function questionOptions(question: AdminQuestionSummary): string[] {
		return Array.isArray(question.options) ? question.options.filter((option) => typeof option === 'string' && option.trim()) : [];
	}

	function optionLetter(index: number): string {
		return String.fromCharCode(65 + index);
	}

	function normalizeAnswerValue(value: string | null): string {
		return (value ?? '')
			.trim()
			.toLowerCase()
			.replace(/^[a-d][\).:\-\s]+/, '')
			.replace(/^option\s+[a-d][\).:\-\s]*/, '')
			.replace(/^answer\s*[:\-]\s*/, '');
	}

	function isCorrectOption(option: string, index: number, correctAnswer: string | null): boolean {
		const normalizedCorrect = normalizeAnswerValue(correctAnswer);
		if (!normalizedCorrect) return false;

		const letter = optionLetter(index).toLowerCase();
		const normalizedOption = normalizeAnswerValue(option);
		const prefixedOption = `${letter}. ${normalizedOption}`;

		return (
			normalizedCorrect === letter ||
			normalizedCorrect === normalizedOption ||
			normalizedCorrect === prefixedOption ||
			normalizedCorrect.endsWith(` ${letter}`)
		);
	}

	const filteredSubjects = $derived.by(() => {
		const query = subjectSearch.trim().toLowerCase();
		if (!query) return subjects.slice(0, 40);
		return subjects
			.filter((subject) => [subject.name, subject.code, subject.teacher_name ?? '', subject.teacher_email ?? ''].some((value) => value.toLowerCase().includes(query)))
			.slice(0, 60);
	});

	const filteredTopics = $derived.by(() => {
		const query = topicSearch.trim().toLowerCase();
		if (!query) return topics.slice(0, 50);
		return topics
			.filter((topic) => [topic.name, topic.description ?? ''].some((value) => value.toLowerCase().includes(query)))
			.slice(0, 60);
	});

	const activeFilterCount = $derived.by(() => {
		let count = 0;
		if (selectedSubjectId) count += 1;
		if (selectedTopicId) count += 1;
		if (selectedStatus !== 'all') count += 1;
		if (selectedQuestionType !== 'all') count += 1;
		if (selectedDifficulty !== 'all') count += 1;
		if (selectedBloom !== 'all') count += 1;
		if (selectedGenerationStatus !== 'all') count += 1;
		if (selectedReferenceMode !== 'all') count += 1;
		if (selectedProviderKey !== PROVIDER_FILTER_ALL) count += 1;
		if (selectedVersionScope !== 'latest') count += 1;
		if (selectedArchivedState !== 'active') count += 1;
		return count;
	});

	const selectedSubjectName = $derived.by(() => {
		return subjects.find((subject) => subject.id === selectedSubjectId)?.name ?? 'All subjects';
	});

	const selectedScopeLabel = $derived.by(() => {
		return selectedVersionScope === 'latest' ? 'Latest only' : 'All versions';
	});

	const exportFieldGroups = $derived.by((): ExportFieldGroup[] => {
		const groups = new Map<string, AdminQuestionExportField[]>();
		for (const field of exportFields) {
			const current = groups.get(field.group) ?? [];
			current.push(field);
			groups.set(field.group, current);
		}
		return Array.from(groups, ([group, fields]) => ({ group, fields }));
	});

	const selectedExportCount = $derived.by(() => selectedExportFieldKeys.length);
</script>

<svelte:head>
	<title>Admin Questions - VQuest Trainer</title>
</svelte:head>

<div class="page">
	<div class="page-header animate-fade-in">
		<div class="header-copy">
			<h1 class="title">Question Feed</h1>
		</div>
		<nav class="header-nav glass-panel" aria-label="Admin navigation">
			<a class="header-link" href="/admin/dashboard">Dashboard</a>
			<a class="header-link" href="/admin/subjects">Subjects</a>
			<a class="header-link active" href="/admin/questions" aria-current="page">Questions</a>
		</nav>
	</div>

	<div class="stats-row animate-slide-up">
		<div class="stat-card glass-panel">
			<span class="stat-value amber-text">{loading ? '...' : totalQuestions}</span>
			<span class="stat-label">Matching Total</span>
		</div>
		<div class="stat-card glass-panel">
			<span class="stat-value blue-text">{selectedSubjectName}</span>
			<span class="stat-label">Subject Slice</span>
		</div>
		<div class="stat-card glass-panel">
			<span class="stat-value white-text">{selectedScopeLabel}</span>
			<span class="stat-label">Version Scope</span>
		</div>
		<div class="stat-card glass-panel">
			<span class="stat-value orange-text">{activeFilterCount}</span>
			<span class="stat-label">Active Filters</span>
		</div>
	</div>

	<div class="filters glass-panel animate-slide-up">
		<div class="panel-heading compact">
			<div class="panel-heading-main">
				<div class="panel-copy">
				<p class="panel-eyebrow">Filter Workspace</p>
				<h2>Search and narrow the feed</h2>
				</div>
			</div>
			<div class="panel-toolbar">
				<div class="panel-badges">
					<span class="summary-chip">{loading ? 'Loading feed' : `${totalQuestions} total`}</span>
					<span class="summary-chip">{activeFilterCount} active filters</span>
				</div>
				<div class="filter-actions compact">
					<button class="action-btn secondary" type="button" onclick={openExportModal}>
						Export ({selectedExportCount})
					</button>
					<button class="action-btn primary" type="button" onclick={() => void loadQuestions(true)} disabled={loading}>
						Refresh feed
					</button>
					<button class="action-btn secondary" type="button" onclick={() => void clearFilters()} disabled={loading && activeFilterCount === 0}>
						Clear filters
					</button>
				</div>
			</div>
		</div>

		<div class="combo-grid">
			<label class="field field-wide">
				<span>Subject Search</span>
				<div class="combo" use:clickOutside={closeSubjectMenu}>
					<div class="combo-shell" class:open={subjectMenuOpen}>
						<input
							type="text"
							bind:value={subjectSearch}
							placeholder="Search subjects by name, code, or teacher"
							onfocus={() => (subjectMenuOpen = true)}
							oninput={() => (subjectMenuOpen = true)}
						/>
						{#if subjectSearch || selectedSubjectId}
							<button type="button" class="combo-clear" aria-label="Clear subject filter" onclick={() => void clearSubjectFilter()}>
								&#10005;
							</button>
						{/if}
					</div>

					{#if subjectMenuOpen}
						<div class="combo-menu">
							<button type="button" class="combo-option combo-option-all" onclick={() => void selectSubject(null)}>
								<span class="combo-option-title">All subjects</span>
								<span class="combo-option-meta">Clear the subject constraint</span>
							</button>

							{#if filteredSubjects.length === 0}
								<div class="combo-empty">No subjects match that search.</div>
							{:else}
								{#each filteredSubjects as subject}
									<button type="button" class="combo-option" onclick={() => void selectSubject(subject)}>
										<span class="combo-option-title">{subject.name}</span>
										<span class="combo-option-meta">
											{subject.code} · {subject.total_questions} questions · {subject.teacher_name || 'No owner'}
										</span>
									</button>
								{/each}
							{/if}
						</div>
					{/if}
				</div>
			</label>

			<label class="field field-wide">
				<span>Topic Search</span>
				<div class="combo" use:clickOutside={closeTopicMenu}>
					<div class="combo-shell" class:open={topicMenuOpen} class:disabled={!selectedSubjectId}>
						<input
							type="text"
							bind:value={topicSearch}
							placeholder={selectedSubjectId ? 'Search topics in the selected subject' : 'Pick a subject first'}
							disabled={!selectedSubjectId}
							onfocus={() => {
								if (selectedSubjectId) topicMenuOpen = true;
							}}
							oninput={() => {
								if (selectedSubjectId) topicMenuOpen = true;
							}}
						/>
						{#if (topicSearch || selectedTopicId) && selectedSubjectId}
							<button type="button" class="combo-clear" aria-label="Clear topic filter" onclick={() => void clearTopicFilter()}>
								&#10005;
							</button>
						{/if}
					</div>

					{#if topicMenuOpen && selectedSubjectId}
						<div class="combo-menu">
							<button type="button" class="combo-option combo-option-all" onclick={() => void selectTopic(null)}>
								<span class="combo-option-title">All topics</span>
								<span class="combo-option-meta">Keep the subject, remove the topic constraint</span>
							</button>

							{#if filteredTopics.length === 0}
								<div class="combo-empty">No topics match that search.</div>
							{:else}
								{#each filteredTopics as topic}
									<button type="button" class="combo-option" onclick={() => void selectTopic(topic)}>
										<span class="combo-option-title">{topic.name}</span>
										<span class="combo-option-meta">
											{topic.total_questions} questions · {topic.has_syllabus ? 'Has syllabus' : 'No syllabus'}
										</span>
									</button>
								{/each}
							{/if}
						</div>
					{/if}
				</div>
			</label>

			<div class="field field-status">
				<span>Review Status</span>
				<div class="status-row">
					{#each VETTING_STATUS_OPTIONS as option}
						<button
							type="button"
							class="status-chip"
							class:active={selectedStatus === option.value}
							onclick={() => void setStatusFilter(option.value as 'all' | 'pending' | 'approved' | 'rejected')}
						>
							{option.label}
						</button>
					{/each}
				</div>
			</div>
		</div>

		<div class="advanced-grid">
			<!-- <label class="field">
				<span>Question Type</span>
				<select bind:value={selectedQuestionType} onchange={() => void handleAdvancedFilterChange()}>
					{#each QUESTION_TYPE_OPTIONS as option}
						<option value={option.value}>{option.label}</option>
					{/each}
				</select>
			</label> -->

			<label class="field">
				<span>Difficulty</span>
				<select bind:value={selectedDifficulty} onchange={() => void handleAdvancedFilterChange()}>
					{#each DIFFICULTY_OPTIONS as option}
						<option value={option.value}>{option.label}</option>
					{/each}
				</select>
			</label>

			<label class="field">
				<span>Bloom Level</span>
				<select bind:value={selectedBloom} onchange={() => void handleAdvancedFilterChange()}>
					{#each BLOOM_OPTIONS as option}
						<option value={option.value}>{option.label}</option>
					{/each}
				</select>
			</label>

			<!-- <label class="field">
				<span>Generation Result</span>
				<select bind:value={selectedGenerationStatus} onchange={() => void handleAdvancedFilterChange()}>
					{#each GENERATION_STATUS_OPTIONS as option}
						<option value={option.value}>{option.label}</option>
					{/each}
				</select>
			</label> -->

			<label class="field">
				<span>Source Basis</span>
				<select bind:value={selectedReferenceMode} onchange={() => void handleAdvancedFilterChange()}>
					{#each REFERENCE_OPTIONS as option}
						<option value={option.value}>{option.label}</option>
					{/each}
				</select>
			</label>

			<label class="field">
				<span>AI Provider</span>
				<select bind:value={selectedProviderKey} onchange={() => void handleAdvancedFilterChange()}>
					<option value={PROVIDER_FILTER_ALL}>Any provider</option>
					{#each providerKeys as providerKey}
						<option value={providerKey}>{providerKey}</option>
					{/each}
				</select>
			</label>

			<!-- <label class="field">
				<span>Version Scope</span>
				<select bind:value={selectedVersionScope} onchange={() => void handleAdvancedFilterChange()}>
					{#each VERSION_SCOPE_OPTIONS as option}
						<option value={option.value}>{option.label}</option>
					{/each}
				</select>
			</label> -->

			<label class="field">
				<span>Archive State</span>
				<select bind:value={selectedArchivedState} onchange={() => void handleAdvancedFilterChange()}>
					{#each ARCHIVED_OPTIONS as option}
						<option value={option.value}>{option.label}</option>
					{/each}
				</select>
			</label>
		</div>

	</div>		

	{#if exportModalOpen}
		<div
			class="modal-backdrop"
			role="presentation"
			onclick={(event) => {
				if (event.target === event.currentTarget) closeExportModal();
			}}
			onkeydown={(event) => {
				if (event.key === 'Escape') closeExportModal();
			}}
			tabindex="-1"
		>
			<div class="export-modal glass-panel" role="dialog" aria-modal="true" aria-labelledby="export-modal-title">
				<div class="export-modal-head">
					<div class="export-copy">
						<p class="eyebrow">Export Builder</p>
						<h2 id="export-modal-title">Configure export columns</h2>
						<p>The export uses the current feed filters. Preview stays compact and the CSV download streams in batches.</p>
					</div>
					<div class="export-actions">
						<button class="action-btn secondary" type="button" onclick={() => resetExportFieldsToDefault()} disabled={previewLoading || exportFields.length === 0}>
							Reset defaults
						</button>
						<button class="action-btn secondary" type="button" onclick={closeExportModal}>
							Close
						</button>
						<button class="action-btn primary" type="button" onclick={() => void handleExportDownload()} disabled={exporting || previewLoading || selectedExportCount === 0}>
							{exporting ? 'Preparing CSV...' : 'Export CSV'}
						</button>
					</div>
				</div>

				<div class="export-summary compact">
					<span class="summary-chip">{selectedExportCount} columns</span>
					<span class="summary-chip">Current filters included</span>
					<span class="summary-chip">Live preview</span>
				</div>

				<div class="export-modal-body">
					<div class="export-modal-fields">
						{#if exportFieldGroups.length > 0}
							<div class="export-groups compact">
								{#each exportFieldGroups as group}
									<section class="export-group compact">
										<div class="export-group-head">
											<h3>{group.group}</h3>
										</div>
										<div class="export-field-grid compact">
											{#each group.fields as field}
												<label class="export-toggle compact" class:selected={selectedExportFieldKeys.includes(field.key)}>
													<span class="export-toggle-control">
														<input
															type="checkbox"
															checked={selectedExportFieldKeys.includes(field.key)}
															onchange={(event) =>
																toggleExportField(field.key, (event.currentTarget as HTMLInputElement).checked)}
														/>
														<span class="export-toggle-check" aria-hidden="true">{selectedExportFieldKeys.includes(field.key) ? '✓' : ''}</span>
													</span>
													<div>
														<strong>{field.label}</strong>
														<span>{field.description}</span>
													</div>
												</label>
											{/each}
										</div>
									</section>
								{/each}
							</div>
						{/if}
					</div>

					<div class="preview-card modal-preview">
						<div class="preview-head">
							<div>
								<h3>Live sample preview</h3>
								<p>Showing {previewRows.length} matching row{previewRows.length === 1 ? '' : 's'} for the current filters and selected columns.</p>
							</div>
							{#if previewLoading}
								<div class="preview-loading-inline">
									<div class="spinner small"></div>
									<span>Refreshing preview...</span>
								</div>
							{/if}
						</div>

						{#if previewError}
							<div class="export-error" role="alert">{previewError}</div>
						{:else if previewLoading && previewColumns.length === 0}
							<div class="preview-empty">
								<div class="spinner"></div>
								<p>Loading export preview...</p>
							</div>
						{:else if previewColumns.length === 0}
							<div class="preview-empty">
								<p>Preparing export fields...</p>
							</div>
						{:else if previewRows.length === 0}
							<div class="preview-empty">
								<p>No questions match the current filters, so there is nothing to preview or export right now.</p>
							</div>
						{:else}
							<div class="preview-table-wrap compact">
								<table class="preview-table compact">
									<thead>
										<tr>
											{#each previewColumns as column}
												<th>{column.label}</th>
											{/each}
										</tr>
									</thead>
									<tbody>
										{#each previewRows as row}
											<tr>
												{#each previewColumns as column}
													<td>{row[column.key] || '—'}</td>
												{/each}
											</tr>
										{/each}
									</tbody>
								</table>
							</div>
						{/if}
					</div>
				</div>
			</div>
		</div>
	{/if}

	{#if error}
		<div class="error-banner" role="alert">{error}</div>
	{/if}

	{#if loading}
		<div class="center-state loading-state">
			<div class="spinner"></div>
			<p>Loading question feed...</p>
		</div>
	{:else if questions.length === 0}
		<div class="center-state glass-panel empty-state">
			<h2>No questions match the current filters</h2>
			<p>Change the subject, topic, or review filters to load a different slice of the question inventory.</p>
		</div>
	{:else}
		<div class="question-list animate-fade-in">
			{#each questions as question}
				<article class="question-card glass-panel">
					<div class="question-topline">
						<div class="pill-row">
							<span class="pill type-pill">{typeLabel(question.question_type)}</span>
							<span class={`pill status-pill ${statusClass(question.vetting_status)}`}>{statusLabel(question.vetting_status)}</span>
							<span class="pill neutral-pill">{difficultyLabel(question.difficulty_level)}</span>
							<span class={`pill status-pill ${generationClass(question.generation_status)}`}>{statusLabel(question.generation_status)}</span>
							<span class={`pill status-pill ${referenceClass(question.used_reference_materials)}`}>
								{question.used_reference_materials ? 'Reference-backed' : 'No references'}
							</span>
							<span class="pill neutral-pill">{question.provider_key}</span>
							<span class="pill neutral-pill">{archivedLabel(question)}</span>
							{#if question.marks != null}
								<span class="pill marks-pill">{question.marks} marks</span>
							{/if}
						</div>
						<time class="question-time" datetime={question.generated_at}>{formatDate(question.generated_at)}</time>
					</div>

					<div class="question-body">
						<div class="question-main">
							<!-- <div class="question-identifiers">
								<div class="identifier-block">
									<span>ID</span>
									<code>{question.id}</code>
								</div>
								{#if question.document_id}
									<div class="identifier-block">
										<span>Document</span>
										<code>{question.document_id}</code>
									</div>
								{/if}
								{#if question.session_id}
									<div class="identifier-block">
										<span>Session</span>
										<code>{question.session_id}</code>
									</div>
								{/if}
							</div> -->

							<p class="question-text">{question.question_text}</p>

							{#if questionOptions(question).length > 0}
								<div class="answer-block">
									<div class="answer-block-head">
										<span class="meta-label">Answer Options</span>
									</div>
									<div class="option-list">
										{#each questionOptions(question) as option, index}
											<div class="option-item" class:correct={isCorrectOption(option, index, question.correct_answer)}>
												<span class="option-badge">{optionLetter(index)}</span>
												<span class="option-text">{option}</span>
												{#if isCorrectOption(option, index, question.correct_answer)}
													<span class="option-flag">Correct</span>
												{/if}
											</div>
										{/each}
									</div>
								</div>
							{:else if question.correct_answer}
								<div class="answer-block">
									<div class="answer-block-head">
										<span class="meta-label">Correct Answer</span>
									</div>
									<div class="direct-answer">{question.correct_answer}</div>
								</div>
							{/if}
						</div>

						<div class="question-side">
							<div class="question-meta">
								<div>
									<span class="meta-label">Subject</span>
									<strong>{formatOptionalText(question.subject_name, 'Unassigned')}</strong>
								</div>
								<div>
									<span class="meta-label">Topic</span>
									<strong>{formatOptionalText(question.topic_name, 'No topic')}</strong>
								</div>
								<div>
									<span class="meta-label">Bloom</span>
									<strong>{formatOptionalText(question.bloom_taxonomy_level, 'Unspecified')}</strong>
								</div>
								<div>
									<span class="meta-label">Learning Outcome</span>
									<strong>{formatOptionalText(question.learning_outcome_id, 'None')}</strong>
								</div>
								<div>
									<span class="meta-label">Vetted At</span>
									<strong>{question.vetted_at ? formatDate(question.vetted_at) : 'Not vetted'}</strong>
								</div>
								<div>
									<span class="meta-label">Vetted By</span>
									<strong>{formatOptionalText(question.vetted_by, 'Pending review')}</strong>
								</div>
							</div>

							<div class="score-grid">
								<div class="score-card">
									<span>Confidence</span>
									<strong>{formatScore(question.generation_confidence)}</strong>
								</div>
								<div class="score-card">
									<span>Answerability</span>
									<strong>{formatScore(question.answerability_score)}</strong>
								</div>
								<div class="score-card">
									<span>Specificity</span>
									<strong>{formatScore(question.specificity_score)}</strong>
								</div>
								<div class="score-card">
									<span>Novelty</span>
									<strong>{formatScore(question.novelty_score)}</strong>
								</div>
								<!-- <div class="score-card">
									<span>Max Similarity</span>
									<strong>{formatScore(question.max_similarity)}</strong>
								</div>
								<div class="score-card">
									<span>Similarity Source</span>
									<strong>{formatOptionalText(question.similarity_source, '—')}</strong>
								</div> -->
							</div>
						</div>
					</div>

					{#if question.explanation || question.vetting_notes || question.discard_reason || question.replaces_id || question.replaced_by_id}
						<details class="detail-panel">
							<summary>Explanation and notes</summary>

							{#if question.explanation}
								<div class="detail-copy">
									<span>Explanation</span>
									<p>{question.explanation}</p>
								</div>
							{/if}

							{#if question.vetting_notes}
								<div class="detail-copy">
									<span>Vetting notes</span>
									<p>{question.vetting_notes}</p>
								</div>
							{/if}

							{#if question.discard_reason}
								<div class="detail-copy">
									<span>Discard reason</span>
									<p>{question.discard_reason}</p>
								</div>
							{/if}

							<!-- <div class="detail-grid">
								<div>
									<span>Generation attempts</span>
									<strong>{question.generation_attempt_count}</strong>
								</div>
								<div>
									<span>Replaces</span>
									<strong>{formatOptionalText(question.replaces_id, 'None')}</strong>
								</div>
								<div>
									<span>Replaced by</span>
									<strong>{formatOptionalText(question.replaced_by_id, 'None')}</strong>
								</div>
							</div> -->
						</details>
					{/if}
				</article>
			{/each}
		</div>

		{#if hasMore}
			<div class="lazy-sentinel" use:infiniteSentinel>
				{#if loadingMore}
					<div class="loading-more">
						<div class="spinner small"></div>
						<p>Loading more questions...</p>
					</div>
				{:else}
					<p>Scroll to load more questions</p>
				{/if}
			</div>
		{:else}
			<div class="end-cap glass-panel">
				<p>You have reached the end of the current result set.</p>
			</div>
		{/if}
	{/if}
</div>

<style>
	.page {
		--panel-bg: color-mix(in srgb, var(--theme-input-bg, rgba(15, 23, 42, 0.84)) 84%, rgba(7, 11, 21, 0.96));
		--panel-bg-soft: color-mix(in srgb, var(--theme-input-bg, rgba(15, 23, 42, 0.74)) 74%, rgba(255, 255, 255, 0.02));
		--panel-bg-strong: color-mix(in srgb, var(--theme-input-bg, rgba(15, 23, 42, 0.92)) 88%, rgba(5, 9, 18, 0.98));
		--panel-border: color-mix(in srgb, var(--theme-glass-border, rgba(255, 255, 255, 0.12)) 72%, rgba(148, 163, 184, 0.14));
		--panel-divider: rgba(148, 163, 184, 0.12);
		--chip-bg: color-mix(in srgb, var(--theme-input-bg, rgba(15, 23, 42, 0.72)) 84%, rgba(255, 255, 255, 0.03));
		--menu-bg: color-mix(in srgb, rgb(10 14 24) 92%, var(--theme-input-bg, rgb(15 23 42)) 8%);
		--menu-border: color-mix(in srgb, var(--panel-border) 70%, rgba(255, 255, 255, 0.12));
		--menu-hover: rgba(255, 255, 255, 0.06);
		--menu-shadow: 0 22px 44px rgba(2, 6, 23, 0.32);
		max-width: 1380px;
		margin: 0 auto;
		padding: 1.35rem 1.25rem 2rem;
		display: flex;
		flex-direction: column;
		gap: 0.9rem;
	}

	:global(:root[data-color-mode='light']) .page {
		--panel-bg: color-mix(in srgb, rgba(255, 255, 255, 0.92) 88%, rgba(241, 245, 249, 0.96));
		--panel-bg-soft: color-mix(in srgb, rgba(255, 255, 255, 0.9) 82%, rgba(248, 250, 252, 0.96));
		--panel-bg-strong: color-mix(in srgb, rgba(255, 255, 255, 0.96) 86%, rgba(226, 232, 240, 0.95));
		--panel-border: color-mix(in srgb, rgba(148, 163, 184, 0.28) 74%, rgba(255, 255, 255, 0.55));
		--panel-divider: rgba(148, 163, 184, 0.18);
		--chip-bg: color-mix(in srgb, rgba(255, 255, 255, 0.82) 78%, rgba(241, 245, 249, 0.92));
		--menu-bg: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(248, 250, 252, 0.97));
		--menu-border: rgba(148, 163, 184, 0.26);
		--menu-hover: rgba(148, 163, 184, 0.1);
		--menu-shadow: 0 18px 38px rgba(15, 23, 42, 0.14);
	}

	.page-header {
		display: flex;
		justify-content: space-between;
		gap: 1rem;
		align-items: flex-end;
		padding-bottom: 0.1rem;
	}

	.header-copy {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		min-width: 0;
	}

	.header-meta {
		display: inline-flex;
		align-items: center;
		gap: 0.55rem;
		flex-wrap: wrap;
	}

	.eyebrow {
		margin: 0;
		font-size: 0.72rem;
		font-weight: 700;
		letter-spacing: 0.12em;
		text-transform: uppercase;
		color: var(--theme-primary);
	}

	.header-dot {
		width: 0.3rem;
		height: 0.3rem;
		border-radius: 999px;
		background: rgba(var(--theme-primary-rgb), 0.65);
	}

	.header-context {
		margin: 0;
		font-size: 0.76rem;
		font-weight: 700;
		letter-spacing: 0.12em;
		text-transform: uppercase;
		color: var(--theme-text-muted);
	}

	.title {
		margin: 0;
		font-size: clamp(1.5rem, 3vw, 1.9rem);
		font-weight: 750;
		letter-spacing: -0.02em;
		color: var(--theme-text);
	}

	.subtitle {
		margin: 0.12rem 0 0;
		max-width: 44rem;
		font-size: 0.92rem;
		color: var(--theme-text-muted);
		line-height: 1.45;
	}

	.header-nav {
		display: inline-flex;
		gap: 0.35rem;
		padding: 0.28rem;
		border-radius: 0.8rem;
		align-self: start;
		background: var(--panel-bg-strong);
		border: 1px solid var(--panel-border);
		backdrop-filter: blur(10px);
		box-shadow: 0 10px 26px rgba(15, 23, 42, 0.1);
	}

	.header-nav::before,
	.header-nav::after,
	.stat-card::before,
	.stat-card::after,
	.filters::before,
	.filters::after,
	.export-panel::before,
	.export-panel::after,
	.question-card::before,
	.question-card::after,
	.end-cap::before,
	.end-cap::after,
	.empty-state::before,
	.empty-state::after {
		content: none;
	}

	.header-link {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		padding: 0.62rem 0.9rem;
		min-width: 5.8rem;
		border-radius: 0.62rem;
		text-decoration: none;
		font-size: 0.86rem;
		font-weight: 700;
		color: var(--theme-text-muted);
		background: transparent;
		border: 1px solid transparent;
		transition: background 0.18s ease, color 0.18s ease, border-color 0.18s ease;
	}

	.header-link:hover {
		color: var(--theme-text);
		background: rgba(255, 255, 255, 0.04);
	}

	.header-link.active {
		color: var(--theme-text);
		background: rgba(var(--theme-primary-rgb), 0.16);
		border-color: rgba(var(--theme-primary-rgb), 0.28);
		box-shadow: inset 0 0 0 1px rgba(var(--theme-primary-rgb), 0.08);
	}

	.stats-row {
		display: grid;
		grid-template-columns: repeat(4, minmax(11rem, 1fr));
		gap: 0.7rem;
	}

	.stat-card {
		display: flex;
		flex-direction: column;
		gap: 0.18rem;
		padding: 0.8rem 0.95rem;
		border-radius: 0.8rem;
		min-height: 0;
		background: var(--panel-bg);
		border: 1px solid var(--panel-border);
		box-shadow: 0 10px 28px rgba(15, 23, 42, 0.08);
	}

	.stat-value {
		font-size: 1.05rem;
		font-weight: 800;
		line-height: 1.2;
		word-break: break-word;
	}

	.stat-label {
		font-size: 0.7rem;
		text-transform: uppercase;
		letter-spacing: 0.12em;
		color: var(--theme-text-muted);
	}

	.filters {
		display: flex;
		flex-direction: column;
		gap: 0.65rem;
		padding: 0.8rem 0.85rem;
		border-radius: 0.9rem;
		background: var(--panel-bg);
		border: 1px solid var(--panel-border);
		box-shadow: 0 10px 28px rgba(15, 23, 42, 0.08);
		position: relative;
		isolation: isolate;
		overflow: visible;
	}

	.panel-heading {
		display: flex;
		justify-content: space-between;
		gap: 0.8rem;
		align-items: flex-start;
		padding-bottom: 0.75rem;
		border-bottom: 1px solid var(--panel-divider);
	}

	.panel-heading.compact {
		gap: 0.6rem;
		padding-bottom: 0.55rem;
		align-items: center;
	}

	.panel-heading-main {
		min-width: 0;
	}

	.panel-toolbar {
		display: flex;
		align-items: center;
		justify-content: flex-end;
		gap: 0.55rem;
		flex-wrap: wrap;
	}

	.panel-copy {
		display: flex;
		flex-direction: column;
		gap: 0.1rem;
	}

	.panel-copy h2,
	.export-copy h2,
	.preview-head h3,
	.export-group-head h3 {
		margin: 0;
		font-size: 0.95rem;
		font-weight: 700;
		letter-spacing: -0.01em;
		color: var(--theme-text);
	}

	.panel-eyebrow {
		margin: 0;
		font-size: 0.68rem;
		font-weight: 700;
		letter-spacing: 0.14em;
		text-transform: uppercase;
		color: var(--theme-text-muted);
	}

	.panel-badges {
		display: flex;
		align-items: center;
		gap: 0.35rem;
		flex-wrap: wrap;
	}

	.combo-grid {
		display: grid;
		grid-template-columns: minmax(0, 1.3fr) minmax(0, 1.3fr) minmax(0, 1fr);
		gap: 0.6rem;
		align-items: start;
	}

	.advanced-grid {
		display: grid;
		grid-template-columns: repeat(5, minmax(0, 1fr));
		gap: 0.6rem;
	}

	.field {
		display: flex;
		flex-direction: column;
		gap: 0.28rem;
		color: var(--theme-text-muted);
		font-size: 0.64rem;
		font-weight: 700;
		letter-spacing: 0.12em;
		text-transform: uppercase;
	}

	.field-wide {
		min-width: 0;
	}

	.field-status {
		justify-content: flex-start;
	}

	.field-span-2 {
		grid-column: span 2;
	}

	.field select,
	.combo-shell {
		width: 100%;
		min-height: 2.35rem;
		border-radius: 0.65rem;
		border: 1px solid var(--panel-border);
		background: var(--panel-bg-soft);
		color: var(--theme-text);
		transition: border-color 0.18s ease, box-shadow 0.18s ease, background 0.18s ease;
	}

	.field select {
		padding: 0.56rem 0.72rem;
		font-size: 0.84rem;
	}

	.field select:focus,
	.combo-shell.open {
		outline: none;
		border-color: rgba(var(--theme-primary-rgb), 0.34);
		box-shadow: 0 0 0 3px rgba(var(--theme-primary-rgb), 0.1);
	}

	.combo {
		position: relative;
		z-index: 2;
	}

	.combo:focus-within {
		z-index: 50;
	}

	.combo-shell {
		display: flex;
		align-items: center;
		padding: 0 0.22rem 0 0.62rem;
		gap: 0.35rem;
	}

	.combo-shell.disabled {
		opacity: 0.62;
		cursor: not-allowed;
	}

	.combo-shell input {
		flex: 1;
		min-width: 0;
		height: 2.2rem;
		border: none;
		background: transparent;
		color: var(--theme-text);
		font-size: 0.84rem;
	}

	.combo-shell input::placeholder {
		color: var(--theme-text-muted);
	}

	.combo-shell input:focus {
		outline: none;
	}

	.combo-clear {
		border: none;
		background: rgba(255, 255, 255, 0.05);
		color: var(--theme-text-muted);
		width: 1.55rem;
		height: 1.55rem;
		border-radius: 999px;
		cursor: pointer;
		font-size: 0.74rem;
	}

	.combo-menu {
		position: absolute;
		left: 0;
		right: 0;
		top: calc(100% + 0.45rem);
		z-index: 80;
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
		padding: 0.35rem;
		border-radius: 0.8rem;
		background: var(--menu-bg);
		border: 1px solid var(--menu-border);
		backdrop-filter: blur(12px);
		box-shadow: var(--menu-shadow);
		max-height: 18rem;
		overflow: auto;
		isolation: isolate;
	}

	.combo-option {
		display: flex;
		flex-direction: column;
		gap: 0.2rem;
		text-align: left;
		padding: 0.58rem 0.68rem;
		border-radius: 0.65rem;
		border: none;
		background: rgba(255, 255, 255, 0);
		color: var(--theme-text);
		cursor: pointer;
	}

	.combo-option:hover,
	.combo-option-all {
		background: var(--menu-hover);
	}

	.combo-option-title {
		font-size: 0.86rem;
		font-weight: 700;
		text-transform: none;
		letter-spacing: normal;
	}

	.combo-option-meta,
	.combo-empty {
		font-size: 0.74rem;
		color: var(--theme-text-muted);
		text-transform: none;
		letter-spacing: normal;
		line-height: 1.35;
	}

	.combo-empty {
		padding: 0.7rem 0.68rem;
	}

	.status-row {
		display: flex;
		gap: 0.4rem;
		flex-wrap: wrap;
		min-height: 2.7rem;
		align-items: center;
	}

	.status-chip {
		border: 1px solid var(--panel-border);
		background: var(--chip-bg);
		color: var(--theme-text-muted);
		padding: 0.6rem 0.85rem;
		border-radius: 999px;
		font-size: 0.78rem;
		font-weight: 700;
		cursor: pointer;
		transition: border-color 0.18s ease, background 0.18s ease, color 0.18s ease;
	}

	.status-chip.active {
		background: rgba(var(--theme-primary-rgb), 0.12);
		border-color: rgba(var(--theme-primary-rgb), 0.28);
		color: var(--theme-text);
	}

	.filter-actions {
		display: flex;
		gap: 0.55rem;
		justify-content: flex-end;
		flex-wrap: wrap;
		padding-top: 0.1rem;
	}

	.export-inline {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 0.8rem;
		padding: 0.8rem 0.95rem;
		border-radius: 0.9rem;
		background: var(--panel-bg);
		border: 1px solid var(--panel-border);
		box-shadow: 0 10px 28px rgba(15, 23, 42, 0.08);
	}

	.export-inline::before,
	.export-inline::after,
	.export-modal::before,
	.export-modal::after {
		content: none;
	}

	.export-inline-copy {
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
	}

	.export-inline-actions {
		display: flex;
		align-items: center;
		gap: 0.55rem;
		flex-wrap: wrap;
		justify-content: flex-end;
	}

	.modal-backdrop {
		position: fixed;
		inset: 0;
		z-index: 200;
		display: grid;
		place-items: center;
		padding: 1.2rem;
		background: rgba(2, 6, 23, 0.4);
		backdrop-filter: blur(6px);
	}

	.export-modal {
		width: min(1080px, 100%);
		max-height: min(82vh, 880px);
		overflow: hidden;
		display: flex;
		flex-direction: column;
		gap: 0.8rem;
		padding: 0.95rem;
		border-radius: 1rem;
		background: var(--panel-bg-strong);
		border: 1px solid var(--panel-border);
		box-shadow: 0 24px 60px rgba(2, 6, 23, 0.28);
	}

	.export-modal-head {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		gap: 0.75rem;
		padding-bottom: 0.75rem;
		border-bottom: 1px solid var(--panel-divider);
	}

	.export-modal-body {
		display: grid;
		grid-template-columns: minmax(0, 1.08fr) minmax(0, 0.92fr);
		gap: 0.8rem;
		min-height: 0;
		overflow: hidden;
	}

	.export-modal-fields,
	.modal-preview {
		min-height: 0;
	}

	.export-modal-fields {
		overflow: auto;
		padding-right: 0.15rem;
	}

	.export-summary.compact {
		padding-top: 0;
	}

	.export-groups.compact {
		gap: 0.65rem;
	}

	.export-group.compact {
		gap: 0.45rem;
	}

	.export-field-grid.compact {
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 0.45rem;
	}

	.export-toggle.compact {
		padding: 0.56rem 0.64rem;
		gap: 0.45rem;
	}

	.export-toggle.compact strong {
		font-size: 0.8rem;
	}

	.export-toggle.compact span {
		font-size: 0.7rem;
		line-height: 1.3;
	}

	.preview-table-wrap.compact {
		max-height: 100%;
	}

	.preview-table.compact {
		min-width: 28rem;
	}

	.preview-table.compact th,
	.preview-table.compact td {
		padding: 0.5rem 0.58rem;
	}

	.modal-preview {
		padding: 0.75rem;
		border-radius: 0.8rem;
		border: 1px solid var(--panel-border);
		background: rgba(255, 255, 255, 0.02);
		overflow: hidden;
	}

	.modal-preview .preview-table-wrap {
		flex: 1;
	}

	.export-panel {
		display: flex;
		flex-direction: column;
		gap: 0.85rem;
		padding: 0.95rem;
		border-radius: 0.9rem;
		background: var(--panel-bg);
		border: 1px solid var(--panel-border);
		box-shadow: 0 10px 28px rgba(15, 23, 42, 0.08);
	}

	.export-header {
		display: flex;
		justify-content: space-between;
		gap: 0.85rem;
		align-items: flex-start;
		padding-bottom: 0.75rem;
		border-bottom: 1px solid var(--panel-divider);
	}

	.export-copy {
		display: flex;
		flex-direction: column;
		gap: 0.2rem;
	}

	.export-copy p,
	.preview-head p {
		margin: 0;
		color: var(--theme-text-muted);
		font-size: 0.88rem;
		line-height: 1.45;
	}

	.export-actions {
		display: flex;
		gap: 0.42rem;
		flex-wrap: wrap;
		justify-content: flex-end;
	}

	.export-summary {
		display: flex;
		gap: 0.42rem;
		flex-wrap: wrap;
		padding-top: 0;
	}

	.filter-actions.compact {
		align-items: center;
	}

	.summary-chip {
		display: inline-flex;
		align-items: center;
		padding: 0.28rem 0.5rem;
		border-radius: 999px;
		background: var(--chip-bg);
		border: 1px solid var(--panel-border);
		color: var(--theme-text-muted);
		font-size: 0.68rem;
		font-weight: 700;
		letter-spacing: 0.06em;
		text-transform: uppercase;
	}

	.export-groups {
		display: grid;
		gap: 0.75rem;
	}

	.export-group {
		display: flex;
		flex-direction: column;
		gap: 0.55rem;
	}

	.export-field-grid {
		display: grid;
		grid-template-columns: repeat(4, minmax(0, 1fr));
		gap: 0.55rem;
	}

	.export-toggle {
		display: grid;
		grid-template-columns: auto minmax(0, 1fr);
		gap: 0.55rem;
		align-items: center;
		padding: 0.62rem 0.72rem;
		border-radius: 0.72rem;
		background: rgba(255, 255, 255, 0.025);
		border: 1px solid var(--panel-border);
		cursor: pointer;
		transition: border-color 0.18s ease, background 0.18s ease;
	}

	.export-toggle:hover {
		border-color: rgba(var(--theme-primary-rgb), 0.22);
	}

	.export-toggle.selected {
		background: rgba(var(--theme-primary-rgb), 0.08);
		border-color: rgba(var(--theme-primary-rgb), 0.28);
	}

	.export-toggle-control {
		position: relative;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 1rem;
		height: 1rem;
		margin-top: 0.05rem;
		flex: 0 0 auto;
	}

	.export-toggle-check {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 1rem;
		height: 1rem;
		border-radius: 999px;
		border: 1px solid rgba(var(--theme-primary-rgb), 0.24);
		background: rgba(var(--theme-primary-rgb), 0.08);
		color: rgba(var(--theme-primary-rgb), 0.96);
		font-size: 0.72rem;
		font-weight: 800;
		line-height: 1;
	}

	.export-toggle:not(.selected) .export-toggle-check {
		color: transparent;
		background: rgba(255, 255, 255, 0.02);
		border-color: var(--panel-border);
	}

	.export-toggle-control input {
		position: absolute;
		inset: 0;
		margin: 0;
		opacity: 0;
		cursor: pointer;
	}

	.export-toggle strong {
		display: block;
		color: var(--theme-text);
		font-size: 0.84rem;
		line-height: 1.25;
	}

	.export-toggle span {
		display: block;
		margin-top: 0.18rem;
		font-size: 0.74rem;
		line-height: 1.35;
		text-transform: none;
		letter-spacing: normal;
		color: var(--theme-text-muted);
	}

	.preview-card {
		display: flex;
		flex-direction: column;
		gap: 0.7rem;
	}

	.preview-head {
		display: flex;
		justify-content: space-between;
		gap: 0.8rem;
		align-items: flex-start;
	}

	.preview-loading-inline {
		display: inline-flex;
		align-items: center;
		gap: 0.5rem;
		color: var(--theme-text-muted);
		font-size: 0.8rem;
	}

	.preview-table-wrap {
		overflow: auto;
		border-radius: 0.75rem;
		border: 1px solid var(--panel-border);
		background: rgba(255, 255, 255, 0.02);
	}

	.preview-table {
		width: 100%;
		border-collapse: collapse;
		min-width: 42rem;
	}

	.preview-table th,
	.preview-table td {
		padding: 0.62rem 0.72rem;
		text-align: left;
		vertical-align: top;
		border-bottom: 1px solid var(--panel-divider);
	}

	.preview-table th {
		position: sticky;
		top: 0;
		background: var(--panel-bg-strong);
		color: var(--theme-text);
		font-size: 0.68rem;
		letter-spacing: 0.12em;
		text-transform: uppercase;
	}

	.preview-table td {
		color: var(--theme-text-muted);
		font-size: 0.82rem;
		line-height: 1.4;
		white-space: pre-wrap;
		word-break: break-word;
	}

	.preview-empty {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 0.65rem;
		padding: 1.6rem 1rem;
		border-radius: 0.8rem;
		border: 1px dashed var(--panel-border);
		color: var(--theme-text-muted);
		text-align: center;
	}

	.export-error {
		padding: 0.75rem 0.85rem;
		border-radius: 0.75rem;
		background: rgba(239, 68, 68, 0.12);
		border: 1px solid rgba(239, 68, 68, 0.24);
		color: #fecaca;
		font-size: 0.84rem;
	}

	.action-btn {
		border: 1px solid transparent;
		border-radius: 0.66rem;
		padding: 0.58rem 0.78rem;
		font-size: 0.78rem;
		font-weight: 700;
		cursor: pointer;
		letter-spacing: 0.04em;
		text-transform: uppercase;
		transition: background 0.18s ease, border-color 0.18s ease, color 0.18s ease;
	}

	.action-btn:hover {
		filter: brightness(1.03);
	}

	.action-btn.primary {
		background: rgba(var(--theme-primary-rgb), 0.18);
		border-color: rgba(var(--theme-primary-rgb), 0.28);
		color: var(--theme-text);
	}

	.action-btn.secondary {
		background: var(--chip-bg);
		border-color: var(--panel-border);
		color: var(--theme-text);
	}

	.action-btn:disabled,
	.status-chip:disabled,
	.combo-clear:disabled {
		opacity: 0.6;
		cursor: not-allowed;
		transform: none;
	}

	.error-banner {
		padding: 0.78rem 0.9rem;
		border-radius: 0.76rem;
		background: rgba(239, 68, 68, 0.16);
		color: #fecaca;
		border: 1px solid rgba(239, 68, 68, 0.28);
		font-size: 0.84rem;
	}

	.center-state {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 0.7rem;
		padding: 2.4rem 1.25rem;
		text-align: center;
		color: var(--theme-text-muted);
	}

	.loading-state {
		min-height: 14rem;
	}

	.empty-state h2 {
		margin: 0;
		font-size: 1.05rem;
		color: var(--theme-text);
	}

	.empty-state p {
		margin: 0;
		max-width: 30rem;
		font-size: 0.9rem;
		line-height: 1.45;
	}

	.question-list {
		display: grid;
		gap: 0.7rem;
	}

	.question-card {
		padding: 0.88rem 0.95rem;
		border-radius: 0.9rem;
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
		background: var(--panel-bg);
		border: 1px solid var(--panel-border);
		box-shadow: 0 10px 28px rgba(15, 23, 42, 0.08);
	}

	.question-topline {
		display: flex;
		justify-content: space-between;
		gap: 0.7rem;
		align-items: center;
		padding-bottom: 0.65rem;
		border-bottom: 1px solid var(--panel-divider);
	}

	.question-body {
		display: grid;
		grid-template-columns: minmax(0, 1.65fr) minmax(18rem, 0.95fr);
		gap: 0.9rem;
		align-items: start;
	}

	.question-main,
	.question-side {
		display: flex;
		flex-direction: column;
		gap: 0.72rem;
	}

	.pill-row {
		display: flex;
		gap: 0.4rem;
		flex-wrap: wrap;
	}

	.pill {
		display: inline-flex;
		align-items: center;
		padding: 0.28rem 0.5rem;
		border-radius: 999px;
		font-size: 0.68rem;
		font-weight: 700;
		letter-spacing: 0.08em;
		text-transform: uppercase;
	}

	.type-pill {
		background: rgba(56, 189, 248, 0.1);
		color: color-mix(in srgb, #7dd3fc 75%, var(--theme-text));
	}

	.status-pill.pending {
		background: rgba(245, 158, 11, 0.1);
		color: color-mix(in srgb, #fcd34d 76%, var(--theme-text));
	}

	.status-pill.approved,
	.status-pill.accepted {
		background: rgba(16, 185, 129, 0.1);
		color: color-mix(in srgb, #6ee7b7 76%, var(--theme-text));
	}

	.status-pill.rejected {
		background: rgba(239, 68, 68, 0.1);
		color: color-mix(in srgb, #fca5a5 76%, var(--theme-text));
	}

	.status-pill.neutral,
	.neutral-pill {
		background: var(--chip-bg);
		color: var(--theme-text-muted);
	}

	.marks-pill {
		background: rgba(129, 140, 248, 0.1);
		color: color-mix(in srgb, #c7d2fe 80%, var(--theme-text));
	}

	.question-time {
		font-size: 0.76rem;
		font-weight: 600;
		color: var(--theme-text-muted);
		white-space: nowrap;
	}

	.question-identifiers {
		display: flex;
		gap: 0.45rem;
		flex-wrap: wrap;
	}

	.identifier-block {
		display: flex;
		align-items: center;
		gap: 0.35rem;
		padding: 0.32rem 0.5rem;
		border-radius: 0.56rem;
		background: rgba(255, 255, 255, 0.025);
		border: 1px solid var(--panel-border);
		color: var(--theme-text-muted);
		font-size: 0.68rem;
		letter-spacing: 0.08em;
		text-transform: uppercase;
	}

	.identifier-block code {
		color: var(--theme-text);
		font-size: 0.72rem;
		letter-spacing: 0;
		text-transform: none;
		overflow-wrap: anywhere;
	}

	.question-text {
		margin: 0;
		font-size: 0.94rem;
		line-height: 1.55;
		color: var(--theme-text);
		line-clamp: 4;
		display: -webkit-box;
		-webkit-line-clamp: 3;
		-webkit-box-orient: vertical;
		overflow: hidden;
	}

	.answer-block {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		padding: 0.72rem;
		border-radius: 0.76rem;
		background: rgba(255, 255, 255, 0.025);
		border: 1px solid var(--panel-border);
	}

	.answer-block-head {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 0.5rem;
		flex-wrap: wrap;
	}

	.answer-key,
	.direct-answer {
		font-size: 0.8rem;
		font-weight: 700;
		color: var(--theme-text);
	}

	.option-list {
		display: grid;
		gap: 0.4rem;
	}

	.option-item {
		display: grid;
		grid-template-columns: auto minmax(0, 1fr) auto;
		align-items: start;
		gap: 0.5rem;
		padding: 0.58rem 0.62rem;
		border-radius: 0.68rem;
		background: rgba(255, 255, 255, 0.02);
		border: 1px solid var(--panel-border);
	}

	.option-item.correct {
		background: rgba(16, 185, 129, 0.1);
		border-color: rgba(16, 185, 129, 0.24);
	}

	.option-badge,
	.option-flag {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		border-radius: 999px;
		font-size: 0.68rem;
		font-weight: 700;
		letter-spacing: 0.08em;
		text-transform: uppercase;
	}

	.option-badge {
		min-width: 1.7rem;
		height: 1.7rem;
		padding: 0 0.45rem;
		background: rgba(255, 255, 255, 0.04);
		color: var(--theme-text-muted);
	}

	.option-text {
		font-size: 0.86rem;
		line-height: 1.45;
		color: var(--theme-text);
		word-break: break-word;
	}

	.option-flag {
		padding: 0.24rem 0.46rem;
		background: rgba(16, 185, 129, 0.18);
		color: color-mix(in srgb, #6ee7b7 82%, var(--theme-text));
	}

	.question-meta,
	.score-grid,
	.detail-grid {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 0.55rem;
	}

	.question-meta {
		padding: 0.7rem;
		border-radius: 0.72rem;
		background: rgba(255, 255, 255, 0.025);
		border: 1px solid var(--panel-border);
	}

	.question-meta strong,
	.score-card strong {
		display: block;
		font-size: 0.82rem;
		color: var(--theme-text);
		margin-top: 0.15rem;
		word-break: break-word;
	}

	.meta-label,
	.score-card span {
		font-size: 0.66rem;
		letter-spacing: 0.12em;
		text-transform: uppercase;
		color: var(--theme-text-muted);
	}

	.score-card {
		padding: 0.58rem 0.68rem;
		border-radius: 0.68rem;
		background: rgba(255, 255, 255, 0.025);
		border: 1px solid var(--panel-border);
	}

	.detail-panel {
		border-radius: 0.72rem;
		border: 1px solid var(--panel-border);
		background: rgba(255, 255, 255, 0.02);
		padding: 0.15rem 0.75rem 0.75rem;
	}

	.detail-panel summary {
		cursor: pointer;
		padding: 0.62rem 0 0.32rem;
		font-size: 0.82rem;
		font-weight: 700;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: var(--theme-text);
	}

	.detail-copy {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		padding: 0.45rem 0 0;
	}

	.detail-copy span {
		font-size: 0.66rem;
		letter-spacing: 0.12em;
		text-transform: uppercase;
		color: var(--theme-text-muted);
	}

	.detail-copy p {
		margin: 0;
		font-size: 0.86rem;
		line-height: 1.45;
		color: var(--theme-text);
	}

	.detail-grid {
		padding-top: 0.55rem;
	}

	.lazy-sentinel,
	.end-cap {
		display: flex;
		justify-content: center;
		align-items: center;
		padding: 0.7rem;
		color: var(--theme-text-muted);
	}

	.end-cap {
		border-radius: 0.75rem;
		background: var(--panel-bg);
		border: 1px solid var(--panel-border);
		box-shadow: 0 10px 28px rgba(15, 23, 42, 0.08);
		font-size: 0.84rem;
	}

	.loading-more {
		display: inline-flex;
		align-items: center;
		gap: 0.55rem;
		font-size: 0.82rem;
	}

	.spinner {
		width: 1.5rem;
		height: 1.5rem;
		border: 2px solid rgba(255, 255, 255, 0.1);
		border-top: 2px solid var(--theme-primary);
		border-radius: 50%;
		animation: spin 0.8s linear infinite;
	}

	.spinner.small {
		width: 0.9rem;
		height: 0.9rem;
	}

	.amber-text { color: color-mix(in srgb, #f59e0b 82%, var(--theme-text)); }
	.blue-text { color: color-mix(in srgb, #60a5fa 82%, var(--theme-text)); }
	.white-text { color: var(--theme-text); }
	.orange-text { color: color-mix(in srgb, #fb923c 84%, var(--theme-text)); }

	@keyframes spin {
		0% { transform: rotate(0deg); }
		100% { transform: rotate(360deg); }
	}

	@media (max-width: 1100px) {
		.page-header {
			flex-direction: column;
			align-items: stretch;
		}

		.header-nav {
			width: fit-content;
		}

		.combo-grid,
		.stats-row,
		.export-field-grid,
		.detail-grid {
			grid-template-columns: 1fr 1fr;
		}

		.advanced-grid {
			grid-template-columns: repeat(3, minmax(0, 1fr));
		}

		.question-body {
			grid-template-columns: 1fr;
		}

		.export-modal-body {
			grid-template-columns: 1fr;
		}

		.question-meta,
		.score-grid {
			grid-template-columns: repeat(3, minmax(0, 1fr));
		}

		.export-header,
		.preview-head,
		.panel-heading,
		.panel-toolbar {
			flex-direction: column;
			align-items: stretch;
		}

		.export-modal-head,
		.export-inline {
			flex-direction: column;
			align-items: stretch;
		}
	}

	@media (max-width: 760px) {
		.page {
			padding-inline: 0.9rem;
		}

		.header-nav,
		.filter-actions,
		.export-actions,
		.export-inline-actions {
			width: 100%;
			justify-content: stretch;
		}

		.header-link,
		.action-btn {
			flex: 1 1 0;
		}

		.combo-grid,
		.advanced-grid,
		.stats-row,
		.export-field-grid,
		.question-meta,
		.score-grid,
		.detail-grid {
			grid-template-columns: 1fr;
		}

		.export-field-grid.compact {
			grid-template-columns: 1fr;
		}

		.field-span-2 {
			grid-column: auto;
		}

		.preview-table {
			min-width: 0;
		}

		.question-topline {
			flex-direction: column;
			align-items: flex-start;
		}

		.question-time {
			white-space: normal;
		}

		.panel-badges,
		.export-summary {
			width: 100%;
		}

		.modal-backdrop {
			padding: 0.7rem;
		}

		.export-modal {
			max-height: 88vh;
			padding: 0.8rem;
		}
	}
</style>