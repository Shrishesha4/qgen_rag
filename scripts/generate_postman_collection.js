const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const endpointsDir = path.join(root, 'backend', 'app', 'api', 'v1', 'endpoints');
const outputDir = path.join(root, 'postman');
const outputFile = path.join(outputDir, 'QGen_RAG_API.postman_collection.json');

const prefixByFile = {
  auth: '/api/v1/auth',
  documents: '/api/v1/documents',
  questions: '/api/v1/questions',
  subjects: '/api/v1/subjects',
  rubrics: '/api/v1/rubrics',
  vetter: '/api/v1/vetter',
  training: '/api/v1/training',
  models: '/api/v1/models',
};

const folderNameByFile = {
  auth: 'Authentication',
  documents: 'Documents',
  questions: 'Questions',
  subjects: 'Subjects',
  rubrics: 'Rubrics',
  vetter: 'Vetter Portal',
  training: 'Training Pipeline',
  models: 'Model Operations',
};

const variableAliasByPathParam = {
  subject_id: 'subjectId',
  topic_id: 'topicId',
  question_id: 'questionId',
  document_id: 'documentId',
  rubric_id: 'rubricId',
  session_id: 'sessionId',
  version_id: 'versionId',
  dataset_id: 'datasetId',
  teacher_id: 'teacherId',
  filename: 'filename',
};

function jsonBody(value) {
  return {
    mode: 'raw',
    raw: JSON.stringify(value, null, 2),
    options: { raw: { language: 'json' } },
  };
}

function formBody(entries) {
  return {
    mode: 'formdata',
    formdata: entries.map((entry) => ({ ...entry })),
  };
}

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

const requestBodyByModel = {
  UserCreate: {
    email: 'teacher@example.com',
    username: 'teacher_demo',
    full_name: 'Demo Teacher',
    password: 'StrongPass123',
    role: 'teacher',
  },
  UserLogin: {
    email: 'teacher@example.com',
    password: 'StrongPass123',
  },
  TokenRefresh: {
    refresh_token: '{{refreshToken}}',
  },
  LogoutRequest: {
    refresh_token: '{{refreshToken}}',
  },
  UserUpdate: {
    full_name: 'Updated Teacher Name',
    avatar_url: null,
    timezone: 'Asia/Kolkata',
    language: 'en',
    preferences: {
      theme: 'dark',
      notifications: true,
    },
  },
  PasswordChange: {
    current_password: 'StrongPass123',
    new_password: 'NewStrongPass456',
  },
  SubjectCreate: {
    name: 'Data Structures',
    code: 'CS201',
    description: 'Core data structures course',
    learning_outcomes: [
      { id: 'LO1', name: 'Understand arrays', description: 'Explain array operations and trade-offs' },
      { id: 'LO2', name: 'Apply trees', description: 'Solve problems using tree traversals' },
    ],
    course_outcomes: [
      { id: 'CO1', name: 'Foundational Knowledge', description: 'Demonstrate core understanding of data structures' },
    ],
  },
  SubjectUpdate: {
    name: 'Advanced Data Structures',
    code: 'CS201',
    description: 'Updated course description',
    learning_outcomes: [
      { id: 'LO1', name: 'Analyse arrays', description: 'Compare contiguous storage strategies' },
    ],
    course_outcomes: [
      { id: 'CO1', name: 'Problem Solving', description: 'Solve complex data-structure problems' },
    ],
  },
  TopicCreate: {
    subject_id: '{{subjectId}}',
    name: 'Binary Trees',
    description: 'Tree terminology, traversal, and BST basics',
    order_index: 1,
    syllabus_content: 'Binary tree properties, traversals, and binary search tree operations.',
  },
  TopicUpdate: {
    name: 'Balanced Trees',
    description: 'AVL and red-black tree basics',
    order_index: 2,
    has_syllabus: true,
    syllabus_content: 'Rotations, balancing, and performance trade-offs.',
    learning_outcome_mappings: {
      mapped_outcomes: [{ id: 'LO2', name: 'Apply trees', level: 2 }],
    },
  },
  RubricCreate: {
    name: 'Midterm Exam',
    exam_type: 'mid_term',
    duration_minutes: 90,
    subject_id: '{{subjectId}}',
    question_type_distribution: {
      mcq: { count: 10, marks_each: 1 },
      short_answer: { count: 5, marks_each: 4 },
    },
    learning_outcomes_distribution: {
      LO1: 40,
      LO2: 60,
    },
  },
  RubricUpdate: {
    name: 'Updated Midterm Exam',
    exam_type: 'mid_term',
    duration_minutes: 120,
    question_type_distribution: {
      mcq: { count: 12, marks_each: 1 },
      short_answer: { count: 4, marks_each: 5 },
    },
    learning_outcomes_distribution: {
      LO1: 50,
      LO2: 50,
    },
  },
  QuestionGenerationRequest: {
    document_id: '{{documentId}}',
    count: 5,
    types: ['mcq', 'short_answer'],
    difficulty: 'medium',
    marks: 2,
    focus_topics: ['Binary Trees', 'Tree Traversal'],
    bloom_levels: ['understand', 'apply'],
    exclude_question_ids: [],
  },
  QuestionRatingRequest: {
    rating: 4,
    difficulty_rating: 'just_right',
  },
  TriggerTrainingRequest: {
    training_method: 'sft+dpo',
    base_model: 'meta-llama/Llama-3.1-8B-Instruct',
    hyperparameters: {
      epochs: 3,
      learning_rate: 0.0002,
      batch_size: 8,
    },
  },
  DatasetBuildRequest: {
    snapshot_filter: {
      days: 30,
      confidence_min: 0.0,
      subject_id: '{{subjectId}}',
    },
  },
  VettingRequest: {
    status: 'approved',
    course_outcome_mapping: { CO1: 2 },
    notes: 'Looks accurate and aligned to the syllabus.',
    rejection_reasons: [],
    custom_feedback: null,
    regeneration_mode: null,
  },
  RubricGenerationRequest: {
    rubric_id: '{{rubricId}}',
    topic_id: '{{topicId}}',
    count_override: 10,
  },
  ChapterGenerationRequest: {
    topic_id: '{{topicId}}',
    question_types: {
      mcq: { count: 5, marks_each: 1 },
      short_answer: { count: 2, marks_each: 4 },
    },
    difficulty: 'medium',
    lo_filter: ['LO1', 'LO2'],
    lo_distribution: { LO1: 50, LO2: 50 },
    count_override: 7,
  },
  ReasonCodeCreateRequest: {
    code: 'quality_issue',
    label: 'Quality Issue',
    description: 'Question quality is below the acceptance threshold',
    severity_default: 'major',
    is_active: true,
  },
  VetQuestionRequest: {
    status: 'approved',
    notes: 'Approved after review.',
    course_outcome_mapping: { CO1: 2 },
    rejection_reasons: [],
    custom_feedback: null,
  },
  VetQuestionSubmitRequest: {
    question_id: '{{questionId}}',
    decision: 'edit',
    edited_text: 'What is the time complexity of binary search in a sorted array?',
    edited_options: ['A) O(1)', 'B) O(log n)', 'C) O(n)', 'D) O(n log n)'],
    edited_answer: 'B',
    edited_explanation: 'Binary search halves the search space on each step.',
    rejection_reasons: ['clarity_issue'],
    reason_codes: ['quality_issue'],
    severity_level: 'major',
    quality_score: 0.75,
    review_version: 1,
    rubric_snapshot: null,
    field_change_rationale: {
      question_text: 'Made the wording more precise.',
    },
    feedback: 'Improved clarity and distractors.',
    notes: 'Edited and approved.',
    approved_difficulty: null,
    course_outcome_mapping: { CO1: 2 },
    time_spent_seconds: 45,
  },
  BulkVetRequest: {
    question_ids: ['{{questionId}}'],
    status: 'approved',
    notes: 'Bulk-approved after spot check.',
  },
  RejectWithFeedbackRequest: {
    feedback: 'Replace ambiguous wording and improve distractor quality.',
    rejection_reasons: ['quality_issue', 'clarity_issue'],
    generate_new: false,
  },
  RejectAndRegenerateRequest: {
    notes: 'Question needs regeneration due to ambiguity.',
    rejection_reasons: ['quality_issue'],
    custom_feedback: 'Generate a more precise conceptual question.',
  },
  VetterUpdateQuestionRequest: {
    marks: 2,
    difficulty_level: 'medium',
    bloom_taxonomy_level: 'apply',
    correct_answer: 'B',
    options: ['A) O(1)', 'B) O(log n)', 'C) O(n)', 'D) O(n log n)'],
    question_text: 'What is the time complexity of binary search in a sorted array?',
    course_outcome_mapping: { CO1: 2 },
    learning_outcome_id: 'LO2',
  },
};

const requestBodyByRoute = {
  'POST /api/v1/documents/upload': formBody([
    { key: 'file', type: 'file', src: '' },
  ]),
  'POST /api/v1/documents/reference/upload': formBody([
    { key: 'file', type: 'file', src: '' },
    { key: 'subject_id', value: '{{subjectId}}', type: 'text' },
    { key: 'index_type', value: 'reference_book', type: 'text' },
  ]),
  'POST /api/v1/questions/quick-generate': formBody([
    { key: 'file', type: 'file', src: '' },
    { key: 'context', value: 'Chapter 5: Data Structures', type: 'text' },
    { key: 'count', value: '5', type: 'text' },
    { key: 'types', value: 'mcq,short_answer', type: 'text' },
    { key: 'difficulty', value: 'medium', type: 'text' },
    { key: 'bloom_levels', value: 'remember,understand', type: 'text' },
    { key: 'marks_mcq', value: '1', type: 'text' },
    { key: 'marks_short', value: '2', type: 'text' },
    { key: 'marks_long', value: '5', type: 'text' },
    { key: 'subject_id', value: '{{subjectId}}', type: 'text' },
    { key: 'topic_id', value: '{{topicId}}', type: 'text' },
    { key: 'existing_session_id', value: '{{sessionId}}', type: 'text' },
  ]),
  'POST /api/v1/questions/quick-generate-from-subject': formBody([
    { key: 'subject_id', value: '{{subjectId}}', type: 'text' },
    { key: 'context', value: 'Generate questions on binary tree traversal', type: 'text' },
    { key: 'count', value: '5', type: 'text' },
    { key: 'types', value: 'mcq,short_answer', type: 'text' },
    { key: 'difficulty', value: 'medium', type: 'text' },
    { key: 'marks_mcq', value: '1', type: 'text' },
    { key: 'marks_short', value: '2', type: 'text' },
    { key: 'marks_long', value: '5', type: 'text' },
    { key: 'topic_id', value: '{{topicId}}', type: 'text' },
    { key: 'existing_session_id', value: '{{sessionId}}', type: 'text' },
    { key: 'allow_without_reference', value: 'false', type: 'text' },
  ]),
  'POST /api/v1/questions/cancel-generation': formBody([
    { key: 'subject_id', value: '{{subjectId}}', type: 'text' },
  ]),
  'POST /api/v1/questions/schedule-background-generation': formBody([
    { key: 'subject_id', value: '{{subjectId}}', type: 'text' },
    { key: 'count', value: '10', type: 'text' },
    { key: 'types', value: 'mcq,short_answer', type: 'text' },
    { key: 'difficulty', value: 'medium', type: 'text' },
    { key: 'topic_id', value: '{{topicId}}', type: 'text' },
    { key: 'topic_ids', value: '{{topicId}}', type: 'text' },
    { key: 'allow_without_reference', value: 'false', type: 'text' },
  ]),
  'POST /api/v1/questions/backfill-topic-mapping': formBody([
    { key: 'subject_id', value: '{{subjectId}}', type: 'text' },
    { key: 'limit', value: '500', type: 'text' },
    { key: 'dry_run', value: 'false', type: 'text' },
  ]),
  'POST /api/v1/questions/import': formBody([
    { key: 'file', type: 'file', src: '' },
    { key: 'subject_id', value: '{{subjectId}}', type: 'text' },
    { key: 'topic_id', value: '{{topicId}}', type: 'text' },
  ]),
  'POST /api/v1/auth/upload-avatar': formBody([
    { key: 'file', type: 'file', src: '' },
  ]),
  'POST /api/v1/subjects/{subject_id}/topics/{topic_id}/upload-syllabus': formBody([
    { key: 'file', type: 'file', src: '' },
  ]),
  'POST /api/v1/subjects/{subject_id}/extract-chapters': formBody([
    { key: 'file', type: 'file', src: '' },
  ]),
  'PUT /api/v1/questions/{question_id}/co-mapping': jsonBody({
    CO1: 2,
    CO2: 1,
  }),
  'PUT /api/v1/questions/{question_id}': jsonBody({
    marks: 2,
    difficulty_level: 'medium',
    bloom_taxonomy_level: 'apply',
    subject_id: '{{subjectId}}',
    topic_id: '{{topicId}}',
    learning_outcome_id: 'LO2',
    course_outcome_mapping: { CO1: 2 },
    question_text: 'What is the time complexity of binary search in a sorted array?',
    correct_answer: 'B',
    options: ['A) O(1)', 'B) O(log n)', 'C) O(n)', 'D) O(n log n)'],
  }),
};

const queryByRoute = {
  'POST /api/v1/training/evaluate/{version_id}': [
    { key: 'dataset_tag', value: 'latest' },
    { key: 'eval_type', value: 'offline' },
  ],
};

function normalizeVariableName(name) {
  if (variableAliasByPathParam[name]) {
    return variableAliasByPathParam[name];
  }

  return name.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase());
}

function normalizePath(fullPath) {
  return fullPath.replace(/\{([^}]+)\}/g, (_, name) => `{{${normalizeVariableName(name)}}}`);
}

function buildUrl(route, fullPath) {
  const base = `{{baseUrl}}${normalizePath(fullPath)}`;
  const key = `${route.method} ${fullPath}`;
  const query = queryByRoute[key] || [];

  if (!query.length) {
    return base;
  }

  const queryString = query.map((entry) => `${entry.key}=${encodeURIComponent(entry.value)}`).join('&');
  return `${base}?${queryString}`;
}

function parseRoutes(filePath) {
  const text = fs.readFileSync(filePath, 'utf8');
  const lines = text.split(/\r?\n/);
  const routes = [];
  const re = /@router\.(get|post|put|patch|delete)\("([^"]+)"/;

  for (let i = 0; i < lines.length; i += 1) {
    const m = lines[i].match(re);
    if (!m) continue;

    let handlerName = '';
    let signature = '';
    let cursor = i + 1;

    while (cursor < lines.length && !lines[cursor].trim().startsWith('async def ')) {
      cursor += 1;
    }

    if (cursor < lines.length) {
      const handlerMatch = lines[cursor].trim().match(/^async def\s+(\w+)\(/);
      handlerName = handlerMatch ? handlerMatch[1] : '';
      const signatureLines = [lines[cursor].trim()];

      while (cursor + 1 < lines.length && !signatureLines[signatureLines.length - 1].trim().endsWith('):')) {
        cursor += 1;
        signatureLines.push(lines[cursor].trim());
      }

      signature = signatureLines.join(' ').replace(/\s+/g, ' ');
    }

    routes.push({ method: m[1].toUpperCase(), path: m[2], handlerName, signature });
  }

  return routes;
}

function isFileUploadPath(fullPath) {
  const lower = fullPath.toLowerCase();
  return lower.includes('/upload') || lower.includes('/import') || lower.includes('/extract-chapters');
}

function needsAuth(fullPath) {
  if (fullPath === '/health' || fullPath === '/') return false;
  if (fullPath.startsWith('/api/v1/auth/register')) return false;
  if (fullPath.startsWith('/api/v1/auth/login')) return false;
  if (fullPath.startsWith('/api/v1/auth/refresh')) return false;
  if (fullPath.startsWith('/api/v1/auth/avatars/')) return false;
  return true;
}

function getBodyModelType(signature) {
  const excludedTypes = new Set(['Request', 'User', 'AsyncSession', 'BackgroundTasks', 'UploadFile']);
  const matches = signature.matchAll(/(\w+)\s*:\s*([A-Za-z_][A-Za-z0-9_]*)\s*(?=,|\))/g);

  for (const match of matches) {
    const typeName = match[2];
    if (!excludedTypes.has(typeName)) {
      return typeName;
    }
  }

  return null;
}

function buildRequestBody(route, fullPath) {
  if (route.method === 'GET' || route.method === 'DELETE') return undefined;

  const routeKey = `${route.method} ${fullPath}`;
  if (requestBodyByRoute[routeKey]) {
    return clone(requestBodyByRoute[routeKey]);
  }

  const modelType = getBodyModelType(route.signature);
  if (modelType && requestBodyByModel[modelType]) {
    return jsonBody(requestBodyByModel[modelType]);
  }

  return undefined;
}

function routeToItem(route, fullPath) {
  const body = buildRequestBody(route, fullPath);
  const headers = [{ key: 'Accept', value: 'application/json' }];

  if (body && body.mode === 'raw') {
    headers.push({ key: 'Content-Type', value: 'application/json' });
  }

  if (needsAuth(fullPath)) {
    headers.push({ key: 'Authorization', value: 'Bearer {{accessToken}}' });
  }

  const request = {
    method: route.method,
    header: headers,
    url: buildUrl(route, fullPath),
    description: `Auto-generated from backend route: ${route.method} ${fullPath}${route.handlerName ? ` (${route.handlerName})` : ''}`,
  };

  if (body) request.body = body;

  return {
    name: `${route.method} ${fullPath}`,
    request,
    response: [],
  };
}

const folders = Object.entries(prefixByFile).map(([fileKey, prefix]) => {
  const filePath = path.join(endpointsDir, `${fileKey}.py`);
  const routes = parseRoutes(filePath)
    .map((r) => ({ ...r, fullPath: `${prefix}${r.path}` }))
    .sort((a, b) => a.fullPath.localeCompare(b.fullPath) || a.method.localeCompare(b.method));

  return {
    name: folderNameByFile[fileKey],
    item: routes.map((r) => routeToItem(r, r.fullPath)),
  };
});

const collection = {
  info: {
    name: 'QGen RAG API (Complete)',
    _postman_id: '3d0d4720-5d10-4aa4-bec2-a9ea65cf6d77',
    description: 'Complete Postman collection generated from FastAPI route decorators with example request bodies derived from the current backend request models and multipart forms.',
    schema: 'https://schema.getpostman.com/json/collection/v2.1.0/collection.json',
  },
  auth: {
    type: 'bearer',
    bearer: [{ key: 'token', value: '{{accessToken}}', type: 'string' }],
  },
  variable: [
    { key: 'baseUrl', value: 'http://localhost:8000' },
    { key: 'accessToken', value: '' },
    { key: 'refreshToken', value: '' },
    { key: 'subjectId', value: '' },
    { key: 'topicId', value: '' },
    { key: 'questionId', value: '' },
    { key: 'documentId', value: '' },
    { key: 'rubricId', value: '' },
    { key: 'sessionId', value: '' },
    { key: 'versionId', value: '' },
    { key: 'datasetId', value: '' },
    { key: 'teacherId', value: '' },
    { key: 'filename', value: '' },
  ],
  item: [
    {
      name: 'Health',
      item: [
        {
          name: 'GET /',
          request: {
            method: 'GET',
            header: [{ key: 'Accept', value: 'application/json' }],
            url: '{{baseUrl}}/',
            description: 'Root health endpoint',
          },
          response: [],
        },
        {
          name: 'GET /health',
          request: {
            method: 'GET',
            header: [{ key: 'Accept', value: 'application/json' }],
            url: '{{baseUrl}}/health',
            description: 'Detailed health endpoint',
          },
          response: [],
        },
      ],
    },
    ...folders,
  ],
};

fs.mkdirSync(outputDir, { recursive: true });
fs.writeFileSync(outputFile, `${JSON.stringify(collection, null, 2)}\n`, 'utf8');

const requestCount = collection.item.reduce((sum, folder) => sum + (folder.item?.length || 0), 0);
console.log(`Created ${outputFile}`);
console.log(`Folders: ${collection.item.length}`);
console.log(`Requests: ${requestCount}`);
