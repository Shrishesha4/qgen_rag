<script lang="ts">
	import { onDestroy, onMount, tick } from 'svelte';
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import {
		ArrowLeft,
		BookOpen,
		ChevronDown,
		ChevronUp,
		ClipboardList,
		Eye,
		FileQuestion,
		Globe,
		Clock3,
		Link2,
		Plus,
		Save,
		Sparkles,
		Trash2,
		Upload,
		CheckSquare,
		SendIcon,
	} from 'lucide-svelte';
	import {
		addQuestionsToModule,
		createModule,
		deleteModule,
		generateModuleContent,
		getCourseById,
		listModuleQuestions,
		requestCourseApproval,
		removeQuestionFromModule,
		reorderModules,
		streamGenerateModuleContent,
		type ModuleContentStreamEvent,
		type CourseModuleResponse,
		type CourseResponse,
		updateCourse,
		updateModule,
		uploadCourseThumbnail,
	} from '$lib/api/courses';
	import { resolveApiAssetUrl } from '$lib/api/client';
	import { generateChapter } from '$lib/api/documents';
	import { getQuestion, listQuestions, type QuestionRecord } from '$lib/api/questions';
	import { getSubject, listSubjects, type SubjectDetailResponse, type SubjectResponse } from '$lib/api/subjects';

	type ModuleType = 'content' | 'quiz' | 'assignment';

	type ModuleDraft = {
		title: string;
		description: string;
		durationMinutes: string;
		isPreview: boolean;
		topicId: string;
		focus: string;
		summary: string;
		learningObjectives: string;
		bodyMarkdown: string;
		assignmentPrompt: string;
		videoUrl: string;
	};

	const courseId = $derived($page.params.id ?? '');

	function emptyDraft(): ModuleDraft {
		return {
			title: '',
			description: '',
			durationMinutes: '',
			isPreview: false,
			topicId: '',
			focus: '',
			summary: '',
			learningObjectives: '',
			bodyMarkdown: '',
			assignmentPrompt: '',
			videoUrl: '',
		};
	}

	let course = $state<CourseResponse | null>(null);
	let subjects = $state<SubjectResponse[]>([]);
	let subjectDetail = $state<SubjectDetailResponse | null>(null);
	let isLoading = $state(true);
	let error = $state<string | null>(null);
	let notice = $state<string | null>(null);
	let workStatus = $state<string | null>(null);

	let title = $state('');
	let description = $state('');
	let priceCents = $state(0);
	let currency = $state('INR');
	let selectedSubjectId = $state('');
	let activeEditorTab = $state<'details' | 'modules'>('details');

	let activeModuleId = $state<string | null>(null);
	let moduleDraft = $state<ModuleDraft>(emptyDraft());
	let isSavingCourse = $state(false);
	let isSavingModule = $state(false);
	let isUploadingThumbnail = $state(false);
	let isCreatingModule = $state(false);
	let isGeneratingContent = $state(false);
	let isGeneratingQuestions = $state(false);
	let isRefreshingQuestions = $state(false);
	let contentStreamAbortController: AbortController | null = null;
	let summaryTextarea = $state<HTMLTextAreaElement | null>(null);
	let objectivesTextarea = $state<HTMLTextAreaElement | null>(null);
	let bodyMarkdownTextarea = $state<HTMLTextAreaElement | null>(null);
	let assignmentTextarea = $state<HTMLTextAreaElement | null>(null);

	let newModuleTitle = $state('');
	let newModuleType = $state<ModuleType>('content');
	let questionGenerationCount = $state(4);
	let questionGenerationDifficulty = $state<'easy' | 'medium' | 'hard'>('medium');

	let attachedQuestions = $state<QuestionRecord[]>([]);
	let availableQuestions = $state<QuestionRecord[]>([]);

	let noticeTimer: ReturnType<typeof setTimeout> | null = null;

	const activeModule = $derived(
		course?.modules.find((module) => module.id === activeModuleId) ?? null
	);
	const coverImageUrl = $derived(resolveApiAssetUrl(course?.cover_image_url));
	const currentTopics = $derived(subjectDetail?.topics ?? []);
	const moduleCanManageQuestions = $derived(
		activeModule?.module_type === 'quiz' || activeModule?.module_type === 'assignment'
	);

	function setNotice(message: string) {
		notice = message;
		if (noticeTimer) {
			clearTimeout(noticeTimer);
		}
		noticeTimer = setTimeout(() => {
			notice = null;
		}, 3200);
	}

	function hydrateCourseForm(courseData: CourseResponse) {
		title = courseData.title;
		description = courseData.description ?? '';
		priceCents = courseData.price_cents;
		currency = courseData.currency;
		selectedSubjectId = courseData.subject_id ?? '';
	}

	function hydrateModuleDraft(module: CourseModuleResponse) {
		const contentData = (module.content_data ?? {}) as Record<string, unknown>;
		moduleDraft = {
			title: module.title,
			description: module.description ?? '',
			durationMinutes: module.duration_minutes ? String(module.duration_minutes) : '',
			isPreview: module.is_preview,
			topicId: typeof contentData.topic_id === 'string' ? contentData.topic_id : '',
			focus: '',
			summary: typeof contentData.summary === 'string' ? contentData.summary : '',
			learningObjectives: Array.isArray(contentData.learning_objectives)
				? contentData.learning_objectives.map((item) => String(item)).join('\n')
				: '',
			bodyMarkdown: typeof contentData.body_markdown === 'string'
				? contentData.body_markdown
				: typeof contentData.markdown === 'string'
					? contentData.markdown
					: '',
			assignmentPrompt: typeof contentData.assignment_prompt === 'string' ? contentData.assignment_prompt : '',
			videoUrl: typeof contentData.video_url === 'string' ? contentData.video_url : '',
		};
	}

	function resetGeneratedModuleFields() {
		moduleDraft.summary = '';
		moduleDraft.learningObjectives = '';
		moduleDraft.bodyMarkdown = '';
		moduleDraft.assignmentPrompt = '';
		moduleDraft.videoUrl = '';
		moduleDraft.durationMinutes = '';
	}

	async function scrollGeneratedField(field: 'summary' | 'learning_objectives' | 'body_markdown' | 'assignment_prompt') {
		await tick();
		const target =
			field === 'summary'
				? summaryTextarea
				: field === 'learning_objectives'
					? objectivesTextarea
					: field === 'body_markdown'
						? bodyMarkdownTextarea
						: assignmentTextarea;

		if (target) {
			target.scrollTop = target.scrollHeight;
		}
	}

	function applyStreamDelta(event: ModuleContentStreamEvent) {
		if (event.type === 'field_start' && event.field) {
			const labelMap: Record<string, string> = {
				summary: 'summary',
				learning_objectives: 'learning objectives',
				body_markdown: 'lesson markdown',
				assignment_prompt: 'assignment brief',
				video_url: 'video URL',
				suggested_duration_minutes: 'duration',
			};
			workStatus = `Generating ${labelMap[event.field] ?? event.field}…`;
			return;
		}

		if (event.type !== 'field_delta' || !event.field || !event.delta) {
			return;
		}

		switch (event.field) {
			case 'summary':
				moduleDraft.summary += event.delta;
				void scrollGeneratedField('summary');
				break;
			case 'learning_objectives':
				moduleDraft.learningObjectives += event.delta;
				void scrollGeneratedField('learning_objectives');
				break;
			case 'body_markdown':
				moduleDraft.bodyMarkdown += event.delta;
				void scrollGeneratedField('body_markdown');
				break;
			case 'assignment_prompt':
				moduleDraft.assignmentPrompt += event.delta;
				void scrollGeneratedField('assignment_prompt');
				break;
			case 'video_url':
				moduleDraft.videoUrl += event.delta;
				break;
			case 'suggested_duration_minutes': {
				const nextValue = `${moduleDraft.durationMinutes}${event.delta}`.replace(/[^\d]/g, '');
				moduleDraft.durationMinutes = nextValue;
				break;
			}
		}
	}

	onDestroy(() => {
		contentStreamAbortController?.abort();
	});

	function replaceModule(updatedModule: CourseModuleResponse) {
		if (!course) return;
		course = {
			...course,
			modules: course.modules
				.map((module) => (module.id === updatedModule.id ? updatedModule : module))
				.sort((left, right) => left.order_index - right.order_index),
		};
	}

	function normalizeAttachedQuestion(question: QuestionRecord) {
		const options = Array.isArray(question.options) ? question.options : [];
		const correctAnswer = question.correct_answer ?? '';
		let correctIndex: number | null = null;
		if (options.length && correctAnswer) {
			const normalizedCorrect = correctAnswer.trim().toUpperCase();
			const index = options.findIndex((option) => {
				const normalizedOption = option.trim().toUpperCase();
				return (
					normalizedOption === normalizedCorrect ||
					normalizedOption.startsWith(`${normalizedCorrect})`) ||
					normalizedOption.startsWith(`${normalizedCorrect}.`) ||
					normalizedOption.startsWith(`${normalizedCorrect}:`)
				);
			});
			correctIndex = index >= 0 ? index : null;
		}

		return {
			question_id: question.id,
			question: question.question_text,
			question_text: question.question_text,
			question_type: question.question_type ?? (options.length ? 'mcq' : 'short_answer'),
			options,
			correct: correctIndex,
			correct_answer: correctAnswer,
			sample_answer: correctAnswer,
			explanation: question.explanation ?? '',
			difficulty_level: question.difficulty_level,
			marks: question.marks,
		};
	}

	function syncAttachedQuestionsIntoActiveModule(questions: QuestionRecord[]) {
		if (!course || !activeModuleId) return;
		course = {
			...course,
			modules: course.modules.map((module) =>
				module.id === activeModuleId
					? {
						...module,
						content_data: {
							...(module.content_data ?? {}),
							questions: questions.map(normalizeAttachedQuestion),
						},
					}
					: module,
			),
		};
	}

	function questionMatchesModuleType(question: QuestionRecord, moduleType: ModuleType) {
		const type = question.question_type ?? (question.options?.length ? 'mcq' : 'short_answer');
		if (moduleType === 'quiz') return type === 'mcq';
		if (moduleType === 'assignment') return type !== 'mcq';
		return false;
	}

	function buildModulePayload(module: CourseModuleResponse) {
		const contentData = {
			...(module.content_data ?? {}),
			topic_id: moduleDraft.topicId || null,
			summary: moduleDraft.summary.trim(),
			learning_objectives: moduleDraft.learningObjectives
				.split('\n')
				.map((item) => item.trim())
				.filter(Boolean),
			body_markdown: moduleDraft.bodyMarkdown,
			markdown: moduleDraft.bodyMarkdown,
			assignment_prompt: moduleDraft.assignmentPrompt,
			video_url: moduleDraft.videoUrl.trim(),
		};

		return {
			title: moduleDraft.title.trim(),
			description: moduleDraft.description.trim() || undefined,
			duration_minutes: moduleDraft.durationMinutes ? Number(moduleDraft.durationMinutes) : undefined,
			is_preview: moduleDraft.isPreview,
			content_data: contentData,
		};
	}

	async function loadSubjectDetail(subjectId: string) {
		if (!subjectId) {
			subjectDetail = null;
			return;
		}

		subjectDetail = await getSubject(subjectId);
	}

	async function refreshQuestionCollections() {
		if (!course || !activeModule || !moduleCanManageQuestions) {
			attachedQuestions = [];
			availableQuestions = [];
			return;
		}

		isRefreshingQuestions = true;
		workStatus = 'Loading question library…';
		try {
			const moduleQuestionRefs = await listModuleQuestions(course.id, activeModule.id);
			const attachedIds = moduleQuestionRefs.map((item) => item.question_id);

			let libraryQuestions: QuestionRecord[] = [];
			if (selectedSubjectId && moduleDraft.topicId) {
				const response = await listQuestions({
					subjectId: selectedSubjectId,
					topicId: moduleDraft.topicId,
					page: 1,
					limit: 50,
					includeAllVersions: false,
					showArchived: false,
				});
				libraryQuestions = response.questions.filter((question) =>
					questionMatchesModuleType(question, activeModule.module_type as ModuleType)
				);
			}

			const libraryMap = new Map(libraryQuestions.map((question) => [question.id, question]));
			const missingIds = attachedIds.filter((id) => !libraryMap.has(id));
			const missingQuestions = await Promise.all(
				missingIds.map(async (id) => {
					try {
						return await getQuestion(id);
					} catch {
						return null;
					}
				})
			);
			const missingMap = new Map(
				missingQuestions
					.filter((question): question is QuestionRecord => !!question)
					.map((question) => [question.id, question])
			);

			attachedQuestions = attachedIds
				.map((id) => libraryMap.get(id) ?? missingMap.get(id))
				.filter((question): question is QuestionRecord => !!question);
			availableQuestions = libraryQuestions.filter((question) => !attachedIds.includes(question.id));
			syncAttachedQuestionsIntoActiveModule(attachedQuestions);
			workStatus = null;
		} catch (caughtError: unknown) {
			error = caughtError instanceof Error ? caughtError.message : 'Failed to load module questions.';
			workStatus = null;
		} finally {
			isRefreshingQuestions = false;
		}
	}

	async function persistCourse(showSuccess = true) {
		if (!course || isSavingCourse) return null;

		isSavingCourse = true;
		try {
			course = await updateCourse(course.id, {
				title: title.trim() || course.title,
				description: description.trim() || undefined,
				price_cents: priceCents,
				currency: currency.trim().toUpperCase() || 'INR',
				subject_id: selectedSubjectId || null,
			});
			hydrateCourseForm(course);
			if (selectedSubjectId) {
				await loadSubjectDetail(selectedSubjectId);
			}
			if (showSuccess) {
				setNotice('Course details saved.');
			}
			return course;
		} catch (caughtError: unknown) {
			error = caughtError instanceof Error ? caughtError.message : 'Failed to save course.';
			return null;
		} finally {
			isSavingCourse = false;
		}
	}

	async function persistActiveModule(showSuccess = true) {
		if (!course || !activeModule || isSavingModule) return null;

		isSavingModule = true;
		try {
			const updatedModule = await updateModule(course.id, activeModule.id, buildModulePayload(activeModule));
			replaceModule(updatedModule);
			hydrateModuleDraft(updatedModule);
			if (showSuccess) {
				setNotice('Module saved.');
			}
			return updatedModule;
		} catch (caughtError: unknown) {
			error = caughtError instanceof Error ? caughtError.message : 'Failed to save module.';
			return null;
		} finally {
			isSavingModule = false;
		}
	}

	async function loadInitial() {
		if (!courseId) {
			error = 'Course not found.';
			isLoading = false;
			return;
		}

		isLoading = true;
		error = null;
		try {
			const [courseResponse, subjectResponse] = await Promise.all([
				getCourseById(courseId),
				listSubjects(1, 100),
			]);

			course = courseResponse;
			subjects = subjectResponse.subjects;
			hydrateCourseForm(courseResponse);

			if (courseResponse.subject_id) {
				await loadSubjectDetail(courseResponse.subject_id);
			}

			if (courseResponse.modules.length > 0) {
				activeModuleId = courseResponse.modules[0].id;
				hydrateModuleDraft(courseResponse.modules[0]);
				await refreshQuestionCollections();
			}
		} catch (caughtError: unknown) {
			error = caughtError instanceof Error ? caughtError.message : 'Course not found.';
		} finally {
			isLoading = false;
		}
	}

	async function handleSubjectSelection() {
		try {
			await loadSubjectDetail(selectedSubjectId);
			if (activeModule && moduleDraft.topicId) {
				const topicExists = (subjectDetail?.topics ?? []).some((topic) => topic.id === moduleDraft.topicId);
				if (!topicExists) {
					moduleDraft = { ...moduleDraft, topicId: '' };
					attachedQuestions = [];
					availableQuestions = [];
				}
			}
		} catch (caughtError: unknown) {
			error = caughtError instanceof Error ? caughtError.message : 'Failed to load subject topics.';
		}
	}

	function selectModule(moduleId: string) {
		if (!course) return;
		const module = course.modules.find((item) => item.id === moduleId);
		if (!module) return;
		activeEditorTab = 'modules';
		activeModuleId = moduleId;
		hydrateModuleDraft(module);
		void refreshQuestionCollections();
	}

	async function addModuleToCourse() {
		if (!course || !newModuleTitle.trim() || isCreatingModule) return;

		isCreatingModule = true;
		try {
			const module = await createModule(course.id, {
				title: newModuleTitle.trim(),
				module_type: newModuleType,
				content_data: {},
			});
			course = {
				...course,
				modules: [...course.modules, module].sort((left, right) => left.order_index - right.order_index),
			};
			newModuleTitle = '';
			activeEditorTab = 'modules';
			activeModuleId = module.id;
			hydrateModuleDraft(module);
			attachedQuestions = [];
			availableQuestions = [];
			setNotice('Module created.');
		} catch (caughtError: unknown) {
			error = caughtError instanceof Error ? caughtError.message : 'Failed to create module.';
		} finally {
			isCreatingModule = false;
		}
	}

	async function removeModuleFromCourse(moduleId: string) {
		if (!course) return;
		if (typeof window !== 'undefined' && !window.confirm('Delete this module?')) {
			return;
		}

		try {
			await deleteModule(course.id, moduleId);
			const remainingModules = course.modules.filter((module) => module.id !== moduleId);
			course = { ...course, modules: remainingModules };
			if (activeModuleId === moduleId) {
				const nextModule = remainingModules[0] ?? null;
				activeModuleId = nextModule?.id ?? null;
				moduleDraft = nextModule ? emptyDraft() : emptyDraft();
				if (nextModule) {
					hydrateModuleDraft(nextModule);
					await refreshQuestionCollections();
				} else {
					attachedQuestions = [];
					availableQuestions = [];
				}
			}
			setNotice('Module deleted.');
		} catch (caughtError: unknown) {
			error = caughtError instanceof Error ? caughtError.message : 'Failed to delete module.';
		}
	}

	async function moveModule(index: number, direction: -1 | 1) {
		if (!course) return;
		const nextIndex = index + direction;
		if (nextIndex < 0 || nextIndex >= course.modules.length) return;

		const reordered = [...course.modules];
		[reordered[index], reordered[nextIndex]] = [reordered[nextIndex], reordered[index]];
		course = { ...course, modules: reordered };

		try {
			await reorderModules(course.id, reordered.map((module) => module.id));
			course = {
				...course,
				modules: reordered.map((module, position) => ({ ...module, order_index: position })),
			};
		} catch (caughtError: unknown) {
			error = caughtError instanceof Error ? caughtError.message : 'Failed to reorder modules.';
			await loadInitial();
		}
	}

	async function handleThumbnailSelection(event: Event) {
		if (!course) return;
		const target = event.currentTarget as HTMLInputElement;
		const file = target.files?.[0];
		if (!file) return;

		isUploadingThumbnail = true;
		workStatus = 'Uploading thumbnail…';
		try {
			const updatedCourse = await uploadCourseThumbnail(course.id, file);
			course = { ...course, cover_image_url: updatedCourse.cover_image_url };
			setNotice('Thumbnail uploaded.');
		} catch (caughtError: unknown) {
			error = caughtError instanceof Error ? caughtError.message : 'Failed to upload thumbnail.';
		} finally {
			isUploadingThumbnail = false;
			workStatus = null;
			target.value = '';
		}
	}

	async function generateDraftContent() {
		if (!course || !activeModule) return;
		if (!selectedSubjectId) {
			error = 'Assign a subject to this course before generating content.';
			return;
		}
		if (!moduleDraft.topicId) {
			error = 'Select a topic for this module before generating content.';
			return;
		}

		if (course.subject_id !== selectedSubjectId) {
			const savedCourse = await persistCourse(false);
			if (!savedCourse) return;
		}

		const savedModule = await persistActiveModule(false);
		if (!savedModule) return;

		isGeneratingContent = true;
		workStatus = 'Generating module draft…';
		resetGeneratedModuleFields();
		contentStreamAbortController?.abort();
		const abortCtrl = new AbortController();
		contentStreamAbortController = abortCtrl;
		try {
			for await (const event of streamGenerateModuleContent(
				course.id,
				savedModule.id,
				{
					topic_id: moduleDraft.topicId,
					focus: moduleDraft.focus.trim() || undefined,
				},
				abortCtrl.signal,
			)) {
				if (event.type === 'error') {
					throw new Error(event.message ?? 'Failed to generate module content.');
				}
				if (event.type === 'complete' && event.module) {
					replaceModule(event.module);
					hydrateModuleDraft(event.module);
					setNotice(event.message ?? 'Draft content generated.');
					continue;
				}
				applyStreamDelta(event);
			}
		} catch (caughtError: unknown) {
			if (!(caughtError instanceof Error && caughtError.name === 'AbortError')) {
				error = caughtError instanceof Error ? caughtError.message : 'Failed to generate module content.';
			}
		} finally {
			contentStreamAbortController = null;
			isGeneratingContent = false;
			workStatus = null;
		}
	}

	async function attachQuestions(questionIds: string[]) {
		if (!course || !activeModule || !questionIds.length) return;

		workStatus = 'Attaching questions…';
		try {
			await addQuestionsToModule(course.id, activeModule.id, questionIds);
			await refreshQuestionCollections();
			setNotice(`Attached ${questionIds.length} question${questionIds.length === 1 ? '' : 's'}.`);
		} catch (caughtError: unknown) {
			error = caughtError instanceof Error ? caughtError.message : 'Failed to attach questions.';
		} finally {
			workStatus = null;
		}
	}

	async function detachQuestion(questionId: string) {
		if (!course || !activeModule) return;

		workStatus = 'Removing question…';
		try {
			await removeQuestionFromModule(course.id, activeModule.id, questionId);
			await refreshQuestionCollections();
			setNotice('Question removed.');
		} catch (caughtError: unknown) {
			error = caughtError instanceof Error ? caughtError.message : 'Failed to remove question.';
		} finally {
			workStatus = null;
		}
	}

	async function generateAndAttachQuestions() {
		if (!course || !activeModule) return;
		if (!moduleDraft.topicId) {
			error = 'Select a topic for this module before generating questions.';
			return;
		}

		isGeneratingQuestions = true;
		workStatus = 'Generating questions…';
		const generatedIds = new Set<string>();
		try {
			for await (const event of generateChapter({
				topicId: moduleDraft.topicId,
				count: questionGenerationCount,
				types: activeModule.module_type === 'quiz' ? 'mcq' : 'short_answer',
				difficulty: questionGenerationDifficulty,
			})) {
				workStatus = event.message ?? workStatus;
				const question = event.question as { id?: unknown } | undefined;
				if (typeof question?.id === 'string') {
					generatedIds.add(question.id);
				}
			}

			if (!generatedIds.size) {
				throw new Error('Generation completed but no questions were returned.');
			}

			await addQuestionsToModule(course.id, activeModule.id, Array.from(generatedIds));
			await refreshQuestionCollections();
			setNotice(`Generated and attached ${generatedIds.size} question${generatedIds.size === 1 ? '' : 's'}.`);
		} catch (caughtError: unknown) {
			error = caughtError instanceof Error ? caughtError.message : 'Failed to generate questions.';
		} finally {
			isGeneratingQuestions = false;
			workStatus = null;
		}
	}

	onMount(() => {
		void loadInitial();
		return () => {
			if (noticeTimer) {
				clearTimeout(noticeTimer);
			}
		};
	});
</script>

<div class="editor-page">
	{#if isLoading}
		<div class="loading-state"><div class="spinner"></div></div>
	{:else if error && !course}
		<div class="error-state">{error}</div>
	{:else if course}
		<header class="editor-header">
			<div>
				<button class="back-btn" onclick={() => goto('/teacher/courses')}>
					<ArrowLeft class="h-4 w-4" /> Back to courses
				</button>
				<p class="eyebrow"></p>
				<h1 class="page-title">{course.title}</h1>
			</div>

			<div class="header-actions">
				{#if notice}
					<span class="notice-pill">{notice}</span>
				{/if}
				<button class="secondary-btn" onclick={() => void persistCourse()} disabled={isSavingCourse}>
					<Save class="h-4 w-4" />
					{isSavingCourse ? 'Saving…' : 'Save course'}
				</button>
				{#if course.status === 'draft'}
					<button class="primary-btn" onclick={async () => {
						const savedCourse = await persistCourse(false);
						if (!savedCourse) return;
						try {
							course = await requestCourseApproval(savedCourse.id);
							setNotice('Approval request sent to admin.');
						} catch (caughtError: unknown) {
							error = caughtError instanceof Error ? caughtError.message : 'Failed to request approval.';
						}
					}}>
						<SendIcon class="h-4 w-4" /> Submit
					</button>
				{:else if course.status === 'pending_approval'}
					<span class="pending-pill">
						<Clock3 class="h-4 w-4" /> Awaiting admin approval
					</span>
				{/if}
			</div>
		</header>

		{#if error}
			<div class="error-banner">
				<span>{error}</span>
				<button onclick={() => (error = null)}>×</button>
			</div>
		{/if}

		{#if workStatus}
			<div class="status-banner">{workStatus}</div>
		{/if}

		<div class="editor-tabs">
			<button class:active={activeEditorTab === 'details'} onclick={() => (activeEditorTab = 'details')}>
				Course Details
			</button>
			<button class:active={activeEditorTab === 'modules'} onclick={() => (activeEditorTab = 'modules')}>
				Modules
			</button>
		</div>

		<div class="editor-grid">
			{#if activeEditorTab === 'details'}
			<section class="course-panel glass-panel">
				<div class="panel-head">
					<h2>Course details</h2>
					<span class="status-chip" class:published={course.status === 'published'} class:pending={course.status === 'pending_approval'}>{course.status}</span>
				</div>

				<label class="field">
					<span class="field-label">Title</span>
					<input type="text" bind:value={title} maxlength="255" />
				</label>

				<label class="field">
					<span class="field-label">Subject</span>
					<select bind:value={selectedSubjectId} onchange={() => void handleSubjectSelection()}>
						<option value="">Select a subject</option>
						{#each subjects as subject}
							<option value={subject.id}>{subject.name} ({subject.code})</option>
						{/each}
					</select>
				</label>

				<label class="field">
					<span class="field-label">Description</span>
					<textarea bind:value={description} rows="5"></textarea>
				</label>

				<div class="field-row">
					<label class="field">
						<span class="field-label">Price (cents)</span>
						<input type="number" min="0" bind:value={priceCents} />
					</label>
					<label class="field">
						<span class="field-label">Currency</span>
						<input type="text" maxlength="3" bind:value={currency} />
					</label>
				</div>

				<div class="thumbnail-card">
					<div>
						<p class="field-label">Thumbnail</p>
						<p class="field-help">Upload a local image file. It will be stored on the backend server.</p>
					</div>
					{#if coverImageUrl}
						<img src={coverImageUrl} alt={course.title} class="thumbnail-preview" />
					{:else}
						<div class="thumbnail-placeholder">No thumbnail uploaded</div>
					{/if}
					<label class="upload-btn" class:disabled={isUploadingThumbnail}>
						<input type="file" accept="image/png,image/jpeg,image/webp" onchange={handleThumbnailSelection} disabled={isUploadingThumbnail} hidden />
						<Upload class="h-4 w-4" />
						{isUploadingThumbnail ? 'Uploading…' : 'Choose file'}
					</label>
				</div>
			</section>
			{:else}

			<section class="modules-panel glass-panel">
				<div class="panel-head">
					<h2>Modules</h2>
					<span class="count-pill">{course.modules.length}</span>
				</div>

				<div class="module-layout">
					<aside class="module-list-column">
						<div class="module-list">
							{#each course.modules as module, index (module.id)}
								<div class="module-row" class:active={module.id === activeModuleId}>
									<button class="module-row-main" onclick={() => selectModule(module.id)}>
										<div class="module-row-copy">
											<span class="module-row-type">
												{#if module.module_type === 'content'}
													<BookOpen class="h-3.5 w-3.5" /> Content
												{:else if module.module_type === 'quiz'}
													<FileQuestion class="h-3.5 w-3.5" /> Quiz
												{:else}
													<ClipboardList class="h-3.5 w-3.5" /> Assignment
												{/if}
											</span>
											<strong>{module.title}</strong>
										</div>
									</button>
									<div class="module-row-actions">
										<button onclick={() => void moveModule(index, -1)} disabled={index === 0} aria-label="Move module up">
											<ChevronUp class="h-4 w-4" />
										</button>
										<button onclick={() => void moveModule(index, 1)} disabled={index === course.modules.length - 1} aria-label="Move module down">
											<ChevronDown class="h-4 w-4" />
										</button>
										<button class="danger-icon" onclick={() => void removeModuleFromCourse(module.id)} aria-label="Delete module">
											<Trash2 class="h-4 w-4" />
										</button>
									</div>
								</div>
							{/each}
						</div>

						<div class="add-module-card">
							<input type="text" bind:value={newModuleTitle} placeholder="New module title" />
							<select bind:value={newModuleType}>
								<option value="content">Content</option>
								<option value="quiz">Quiz</option>
								<option value="assignment">Assignment</option>
							</select>
							<button class="primary-btn" onclick={() => void addModuleToCourse()} disabled={!newModuleTitle.trim() || isCreatingModule}>
								<Plus class="h-4 w-4" />
								{isCreatingModule ? 'Adding…' : 'Add module'}
							</button>
						</div>
					</aside>

					<div class="module-editor-column">
						{#if activeModule}
							<div class="module-editor-head">
								<div>
									<p class="field-label">Active module</p>
									<h3>{activeModule.title}</h3>
								</div>
								<div class="module-editor-actions">
									<button class="secondary-btn" onclick={() => void persistActiveModule()} disabled={isSavingModule}>
										<Save class="h-4 w-4" />
										{isSavingModule ? 'Saving…' : 'Save module'}
									</button>
									<button class="primary-btn" onclick={() => void generateDraftContent()} disabled={isGeneratingContent || !moduleDraft.topicId || !selectedSubjectId}>
										<Sparkles class="h-4 w-4" />
										{isGeneratingContent ? 'Generating…' : 'Generate draft'}
									</button>
								</div>
							</div>

							<div class="module-fields">
								<label class="field">
									<span class="field-label">Module title</span>
									<input type="text" bind:value={moduleDraft.title} />
								</label>

								<div class="field-row three-up">
									<label class="field">
										<span class="field-label">Topic</span>
										<select bind:value={moduleDraft.topicId} onchange={() => void refreshQuestionCollections()}>
											<option value="">Select a topic</option>
											{#each currentTopics as topic}
												<option value={topic.id}>{topic.name}</option>
											{/each}
										</select>
									</label>

									<label class="field">
										<span class="field-label">Duration (minutes)</span>
										<input type="number" min="0" bind:value={moduleDraft.durationMinutes} />
									</label>

									<label class="toggle-field">
										<input type="checkbox" bind:checked={moduleDraft.isPreview} />
										<span>Preview module</span>
									</label>
								</div>

								<label class="field">
									<span class="field-label">Short description</span>
									<textarea bind:value={moduleDraft.description} rows="3"></textarea>
								</label>

								<label class="field">
									<span class="field-label">Generation focus</span>
									<textarea bind:value={moduleDraft.focus} rows="2" placeholder="Optional steering notes for AI-generated content."></textarea>
								</label>

								<div class="field-row two-up">
									<label class="field">
										<span class="field-label">Summary</span>
										<textarea bind:this={summaryTextarea} bind:value={moduleDraft.summary} rows="3"></textarea>
									</label>
									<label class="field">
										<span class="field-label">Learning objectives</span>
										<textarea bind:this={objectivesTextarea} bind:value={moduleDraft.learningObjectives} rows="3" placeholder="One objective per line"></textarea>
									</label>
								</div>

								<label class="field">
									<span class="field-label">Lesson markdown</span>
									<textarea bind:this={bodyMarkdownTextarea} bind:value={moduleDraft.bodyMarkdown} rows="12" placeholder="Write or generate the lesson content in Markdown."></textarea>
								</label>

								{#if activeModule.module_type === 'assignment'}
									<label class="field">
										<span class="field-label">Assignment brief</span>
										<textarea bind:this={assignmentTextarea} bind:value={moduleDraft.assignmentPrompt} rows="6" placeholder="Describe the assignment task, deliverables, and grading expectations."></textarea>
									</label>
								{/if}

								<label class="field">
									<span class="field-label">Video URL</span>
									<div class="input-with-icon">
										<Link2 class="h-4 w-4" />
										<input type="url" bind:value={moduleDraft.videoUrl} placeholder="https://..." />
									</div>
								</label>
							</div>

							{#if moduleCanManageQuestions}
								<section class="question-manager">
									<div class="question-head">
										<div>
											<p class="field-label">Question bank</p>
											<h3>{activeModule.module_type === 'quiz' ? 'Quiz questions' : 'Assignment prompts'}</h3>
										</div>
										<div class="generation-controls">
											<input type="number" min="1" max="20" bind:value={questionGenerationCount} />
											<select bind:value={questionGenerationDifficulty}>
												<option value="easy">Easy</option>
												<option value="medium">Medium</option>
												<option value="hard">Hard</option>
											</select>
											<button class="primary-btn" onclick={() => void generateAndAttachQuestions()} disabled={isGeneratingQuestions || !moduleDraft.topicId}>
												<Sparkles class="h-4 w-4" />
												{isGeneratingQuestions ? 'Generating…' : 'Generate questions'}
											</button>
										</div>
									</div>

									<div class="question-grid">
										<div class="question-column">
											<div class="column-head">
												<strong>Attached</strong>
												<span>{attachedQuestions.length}</span>
											</div>
											{#if attachedQuestions.length === 0}
												<p class="empty-copy">Attach existing questions or generate fresh ones for this topic.</p>
											{:else}
												<div class="question-list">
													{#each attachedQuestions as question (question.id)}
														<article class="question-card attached">
															<p>{question.question_text}</p>
															<div class="question-meta">{question.question_type ?? 'question'} • {question.vetting_status}</div>
															<button class="link-btn danger" onclick={() => void detachQuestion(question.id)}>Remove</button>
														</article>
													{/each}
												</div>
											{/if}
										</div>

										<div class="question-column">
											<div class="column-head">
												<strong>Available for topic</strong>
												<span>{availableQuestions.length}</span>
											</div>
											{#if isRefreshingQuestions}
												<p class="empty-copy">Refreshing question list…</p>
											{:else if !moduleDraft.topicId}
												<p class="empty-copy">Choose a topic to load the recent question bank.</p>
											{:else if availableQuestions.length === 0}
												<p class="empty-copy">No reusable questions found yet for this topic.</p>
											{:else}
												<div class="question-list">
													{#each availableQuestions as question (question.id)}
														<article class="question-card">
															<p>{question.question_text}</p>
															<div class="question-meta">{question.question_type ?? 'question'} • {question.vetting_status}</div>
															<button class="link-btn" onclick={() => void attachQuestions([question.id])}>Attach</button>
														</article>
													{/each}
												</div>
											{/if}
										</div>
									</div>
								</section>
							{/if}
						{:else}
							<div class="empty-module-state">
								<p>No modules yet.</p>
								<p>Create a content, quiz, or assignment module to start authoring.</p>
							</div>
						{/if}
					</div>
				</div>
			</section>
			{/if}
		</div>
	{/if}
</div>

<style>
	.editor-page {
		max-width: 1400px;
		margin: 0 auto;
		padding: clamp(1rem, 2vw, 1.5rem) clamp(1.25rem, 3vw, 2.25rem) clamp(2rem, 3vw, 2.75rem);
		color: var(--theme-text-primary);
	}

	.editor-header {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 1rem;
		margin-bottom: 1.5rem;
	}

	.back-btn,
	.secondary-btn,
	.primary-btn,
	.upload-btn {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		gap: 0.45rem;
		padding: 0.65rem 1rem;
		border-radius: 12px;
		font-size: 0.85rem;
		font-weight: 700;
		cursor: pointer;
		text-decoration: none;
	}

	.back-btn,
	.secondary-btn,
	.upload-btn {
		border: 1px solid var(--theme-glass-border);
		background: var(--theme-input-bg);
		color: var(--theme-text-primary);
	}

	.primary-btn {
		border: none;
		background: rgba(var(--theme-primary-rgb), 0.92);
		color: white;
	}

	.secondary-btn:disabled,
	.primary-btn:disabled,
	.upload-btn.disabled {
		opacity: 0.55;
		cursor: not-allowed;
	}

	.eyebrow {
		margin: 0.95rem 0 0.3rem;
		font-size: 0.74rem;
		font-weight: 700;
		letter-spacing: 0.14em;
		text-transform: uppercase;
		color: rgba(var(--theme-primary-rgb), 0.82);
	}

	.page-title {
		margin: 0;
		font-size: clamp(1.8rem, 3vw, 2.25rem);
		font-weight: 800;
	}
/* 
	.page-subtitle {
		margin: 0.4rem 0 0;
		max-width: 780px;
		font-size: 0.92rem;
		line-height: 1.6;
		color: var(--theme-text-secondary);
	} */

	.header-actions {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		flex-wrap: wrap;
		justify-content: flex-end;
	}

	.notice-pill {
		display: inline-flex;
		align-items: center;
		padding: 0.45rem 0.8rem;
		border-radius: 999px;
		background: rgba(34, 197, 94, 0.12);
		border: 1px solid rgba(34, 197, 94, 0.24);
		color: rgb(134, 239, 172);
		font-size: 0.78rem;
		font-weight: 700;
	}

	.pending-pill {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		padding: 0.45rem 0.8rem;
		border-radius: 999px;
		background: rgba(245, 158, 11, 0.12);
		border: 1px solid rgba(245, 158, 11, 0.26);
		color: rgb(253, 224, 71);
		font-size: 0.78rem;
		font-weight: 700;
	}

	.error-banner,
	.status-banner {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1rem;
		padding: 0.8rem 1rem;
		border-radius: 14px;
		margin-bottom: 1rem;
	}

	.error-banner {
		background: rgba(239, 68, 68, 0.08);
		border: 1px solid rgba(239, 68, 68, 0.2);
		color: #ef4444;
	}

	.error-banner button {
		border: none;
		background: transparent;
		color: inherit;
		font-size: 1.2rem;
		cursor: pointer;
	}

	.status-banner {
		background: rgba(var(--theme-primary-rgb), 0.08);
		border: 1px solid rgba(var(--theme-primary-rgb), 0.18);
		color: var(--theme-text-primary);
	}

	.editor-tabs {
		display: inline-flex;
		gap: 0.4rem;
		padding: 0.35rem;
		margin-bottom: 1rem;
		border-radius: 999px;
		background: color-mix(in srgb, var(--theme-nav-glass) 88%, transparent);
		border: 1px solid var(--theme-glass-border);
	}

	.editor-tabs button {
		border: none;
		background: transparent;
		color: var(--theme-text-secondary);
		padding: 0.55rem 1rem;
		border-radius: 999px;
		font-size: 0.84rem;
		font-weight: 700;
		cursor: pointer;
	}

	.editor-tabs button.active {
		background: rgba(var(--theme-primary-rgb), 0.14);
		color: var(--theme-text-primary);
	}

	.editor-grid {
		display: block;
	}

	.glass-panel {
		background: color-mix(in srgb, var(--theme-nav-glass) 88%, transparent);
		border: 1px solid var(--theme-glass-border);
		border-radius: 22px;
		box-shadow: 0 18px 48px rgba(0, 0, 0, 0.18);
		backdrop-filter: blur(18px);
	}

	.course-panel,
	.modules-panel {
		padding: 1.1rem;
	}

	.panel-head {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.75rem;
		margin-bottom: 1rem;
	}

	.panel-head h2,
	.module-editor-head h3,
	.question-head h3 {
		margin: 0;
		font-size: 1rem;
		font-weight: 800;
	}

	.status-chip,
	.count-pill {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		padding: 0.3rem 0.65rem;
		border-radius: 999px;
		font-size: 0.76rem;
		font-weight: 700;
		border: 1px solid var(--theme-glass-border);
		background: var(--theme-input-bg);
		color: var(--theme-text-secondary);
	}

	.status-chip.published {
		color: rgb(134, 239, 172);
		border-color: rgba(34, 197, 94, 0.28);
		background: rgba(34, 197, 94, 0.12);
	}

	.status-chip.pending {
		color: rgb(253, 224, 71);
		border-color: rgba(245, 158, 11, 0.26);
		background: rgba(245, 158, 11, 0.12);
	}

	.field,
	.toggle-field {
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
		margin-bottom: 0.95rem;
	}

	.field-label {
		font-size: 0.75rem;
		font-weight: 700;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: var(--theme-text-secondary);
	}

	.field-help,
	.empty-copy,
	.question-meta {
		margin: 0;
		font-size: 0.82rem;
		line-height: 1.55;
		color: var(--theme-text-secondary);
	}

	.field input,
	.field textarea,
	.field select,
	.generation-controls input,
	.generation-controls select {
		width: 100%;
		padding: 0.7rem 0.85rem;
		border-radius: 14px;
		border: 1px solid var(--theme-glass-border);
		background: var(--theme-input-bg);
		color: var(--theme-text-primary);
		font-size: 0.9rem;
		font-family: inherit;
	}

	.field textarea {
		resize: vertical;
	}

	.field-row {
		display: grid;
		gap: 0.85rem;
	}

	.field-row.two-up {
		grid-template-columns: repeat(2, minmax(0, 1fr));
	}

	.field-row.three-up {
		grid-template-columns: 1.6fr 1fr auto;
		align-items: end;
	}

	.toggle-field {
		align-items: flex-start;
		justify-content: center;
		margin-bottom: 1.2rem;
	}

	.toggle-field input {
		margin: 0;
	}

	.toggle-field span {
		font-size: 0.9rem;
		color: var(--theme-text-primary);
	}

	.thumbnail-card {
		display: grid;
		gap: 0.9rem;
		padding: 1rem;
		border-radius: 18px;
		border: 1px solid var(--theme-glass-border);
		background: rgba(var(--theme-primary-rgb), 0.05);
	}

	.thumbnail-preview,
	.thumbnail-placeholder {
		width: 100%;
		height: 190px;
		border-radius: 16px;
		border: 1px solid var(--theme-glass-border);
	}

	.thumbnail-preview {
		object-fit: cover;
	}

	.thumbnail-placeholder {
		display: grid;
		place-items: center;
		background: var(--theme-input-bg);
		color: var(--theme-text-secondary);
		font-size: 0.88rem;
	}

	.module-layout {
		display: grid;
		grid-template-columns: minmax(240px, 300px) minmax(0, 1fr);
		gap: 1rem;
	}

	.module-list-column,
	.module-editor-column {
		display: flex;
		flex-direction: column;
		gap: 0.9rem;
	}

	.module-list {
		display: flex;
		flex-direction: column;
		gap: 0.65rem;
	}

	.module-row {
		display: grid;
		grid-template-columns: minmax(0, 1fr) auto;
		gap: 0.5rem;
		padding: 0.65rem;
		border-radius: 16px;
		border: 1px solid var(--theme-glass-border);
		background: var(--theme-input-bg);
	}

	.module-row.active {
		border-color: rgba(var(--theme-primary-rgb), 0.32);
		background: rgba(var(--theme-primary-rgb), 0.08);
	}

	.module-row-main {
		padding: 0;
		border: none;
		background: transparent;
		cursor: pointer;
		text-align: left;
		color: inherit;
	}

	.module-row-copy {
		display: flex;
		flex-direction: column;
		gap: 0.3rem;
	}

	.module-row-copy strong {
		font-size: 0.9rem;
		line-height: 1.45;
	}

	.module-row-type {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		font-size: 0.73rem;
		font-weight: 700;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--theme-text-secondary);
	}

	.module-row-actions {
		display: flex;
		align-items: center;
		gap: 0.25rem;
	}

	.module-row-actions button,
	.link-btn {
		border: none;
		background: transparent;
		color: var(--theme-text-secondary);
		cursor: pointer;
		padding: 0.35rem;
		border-radius: 10px;
	}

	.module-row-actions button:disabled {
		opacity: 0.35;
		cursor: not-allowed;
	}

	.danger-icon:hover,
	.link-btn.danger {
		color: #ef4444;
	}

	.add-module-card,
	.question-manager {
		display: grid;
		gap: 0.75rem;
		padding: 0.95rem;
		border-radius: 18px;
		border: 1px solid var(--theme-glass-border);
		background: var(--theme-input-bg);
	}

	.module-editor-head,
	.question-head,
	.column-head {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 0.75rem;
	}

	.module-editor-actions,
	.generation-controls {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		flex-wrap: wrap;
	}

	.generation-controls input {
		width: 84px;
	}

	.module-fields {
		display: grid;
		gap: 0.2rem;
	}

	.input-with-icon {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		padding: 0 0.85rem;
		border-radius: 14px;
		border: 1px solid var(--theme-glass-border);
		background: var(--theme-input-bg);
	}

	.input-with-icon input {
		border: none;
		background: transparent;
		padding-inline: 0;
	}

	.question-grid {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 0.9rem;
	}

	.question-column {
		display: grid;
		gap: 0.75rem;
	}

	.question-list {
		display: grid;
		gap: 0.65rem;
	}

	.question-card {
		display: grid;
		gap: 0.55rem;
		padding: 0.85rem 0.9rem;
		border-radius: 14px;
		border: 1px solid var(--theme-glass-border);
		background: rgba(255, 255, 255, 0.02);
	}

	.question-card p {
		margin: 0;
		font-size: 0.88rem;
		line-height: 1.55;
	}

	.question-card.attached {
		background: rgba(var(--theme-primary-rgb), 0.06);
	}

	.link-btn {
		justify-self: flex-start;
		padding: 0;
		font-size: 0.82rem;
		font-weight: 700;
		color: rgba(var(--theme-primary-rgb), 0.9);
	}

	.empty-module-state,
	.loading-state,
	.error-state {
		display: grid;
		place-items: center;
		gap: 0.5rem;
		padding: 4rem 1.5rem;
		text-align: center;
		color: var(--theme-text-secondary);
	}

	.spinner {
		width: 42px;
		height: 42px;
		border-radius: 50%;
		border: 3px solid rgba(var(--theme-primary-rgb), 0.14);
		border-top-color: rgba(var(--theme-primary-rgb), 0.84);
		animation: spin 0.8s linear infinite;
	}

	@keyframes spin {
		0% { transform: rotate(0deg); }
		100% { transform: rotate(360deg); }
	}

	@media (max-width: 1180px) {
		.editor-grid,
		.question-grid {
			grid-template-columns: 1fr;
		}
	}

	@media (max-width: 760px) {
		.editor-header,
		.header-actions,
		.module-editor-head,
		.question-head,
		.field-row.two-up,
		.field-row.three-up {
			grid-template-columns: 1fr;
			flex-direction: column;
			align-items: stretch;
		}

		.module-editor-actions,
		.generation-controls {
			width: 100%;
		}

		.generation-controls input,
		.generation-controls select,
		.generation-controls button,
		.secondary-btn,
		.primary-btn,
		.upload-btn {
			width: 100%;
		}
	}
</style>