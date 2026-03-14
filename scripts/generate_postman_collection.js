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

function parseRoutes(filePath) {
  const text = fs.readFileSync(filePath, 'utf8');
  const lines = text.split(/\r?\n/);
  const routes = [];
  const re = /@router\.(get|post|put|patch|delete)\("([^"]+)"/;

  for (let i = 0; i < lines.length; i += 1) {
    const m = lines[i].match(re);
    if (!m) continue;
    routes.push({ method: m[1].toUpperCase(), path: m[2] });
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

function buildRequestBody(method, fullPath) {
  if (method === 'GET' || method === 'DELETE') return undefined;

  if (isFileUploadPath(fullPath)) {
    return {
      mode: 'formdata',
      formdata: [{ key: 'file', type: 'file', src: '' }],
    };
  }

  return {
    mode: 'raw',
    raw: JSON.stringify({}, null, 2),
    options: { raw: { language: 'json' } },
  };
}

function routeToItem(route, fullPath) {
  const headers = [{ key: 'Accept', value: 'application/json' }];

  if (route.method !== 'GET' && route.method !== 'DELETE' && !isFileUploadPath(fullPath)) {
    headers.push({ key: 'Content-Type', value: 'application/json' });
  }

  if (needsAuth(fullPath)) {
    headers.push({ key: 'Authorization', value: 'Bearer {{accessToken}}' });
  }

  const request = {
    method: route.method,
    header: headers,
    url: `{{baseUrl}}${fullPath}`,
    description: `Auto-generated from backend route: ${route.method} ${fullPath}`,
  };

  const body = buildRequestBody(route.method, fullPath);
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
    description: 'Complete Postman collection generated from FastAPI route decorators in backend/app/api/v1/endpoints and backend/app/main.py.',
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
