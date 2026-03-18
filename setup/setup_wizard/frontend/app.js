/* ============================================================
   QGen RAG Setup Wizard — Frontend Application
   Step-by-step guided configuration wizard
   ============================================================ */

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

const STATE = {
    currentStep: 0,
    totalSteps: 8,
    systemInfo: null,
    envValues: {},
    envSchema: [],
    defaults: {},
    advancedMode: false,
    useCase: 'development',  // 'development' or 'production'
    dockerConfig: {
        enabled: true,
        mode: 'development',
        services: { db: true, redis: true, api: true, trainer_web: true, ollama: false },
        ports: {},
        container_names: {},
        volume_names: {},
        network_name: 'qgen_net',
    },
    installOptions: {
        install_trainer: true,
        setup_ollama: false,
        ollama_model: 'llama3.1:8b',
    },
    installing: false,
    installComplete: false,
    installLog: [],
    pollTimer: null,
};

const STEPS = [
    { id: 'welcome',   label: 'Welcome',    icon: 'home' },
    { id: 'system',    label: 'System',      icon: 'cpu' },
    { id: 'backend',   label: 'Backend',     icon: 'server' },
    { id: 'frontend',  label: 'Frontend',    icon: 'layout' },
    { id: 'docker',    label: 'Docker',      icon: 'box' },
    { id: 'review',    label: 'Review',      icon: 'check-circle' },
    { id: 'install',   label: 'Install',     icon: 'download' },
    { id: 'logs',      label: 'Logs',        icon: 'file-text' },
];

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------

async function api(method, path, body) {
    const opts = { method, headers: {} };
    if (body) {
        opts.headers['Content-Type'] = 'application/json';
        opts.body = JSON.stringify(body);
    }
    const res = await fetch('/api/' + path, opts);
    return res.json();
}

const apiGet  = (path) => api('GET', path);
const apiPost = (path, body) => api('POST', path, body);

// ---------------------------------------------------------------------------
// Initialization
// ---------------------------------------------------------------------------

document.addEventListener('DOMContentLoaded', async () => {
    renderStepIndicators();

    try {
        const [sysInfo, schema, defaults, state] = await Promise.all([
            apiGet('detect'),
            apiGet('env-schema'),
            apiGet('defaults'),
            apiGet('state'),
        ]);
        STATE.systemInfo = sysInfo;
        STATE.envSchema = schema;
        STATE.defaults = defaults;

        // Merge server-side state
        if (state.env_values && Object.keys(state.env_values).length) {
            STATE.envValues = { ...defaults, ...state.env_values };
        } else {
            STATE.envValues = { ...defaults };
        }
        if (state.docker_config) {
            STATE.dockerConfig = { ...STATE.dockerConfig, ...state.docker_config };
        }
        if (state.current_step) {
            STATE.currentStep = state.current_step;
        }

        debugLog('System info loaded', sysInfo);
        debugLog('Env schema loaded', schema.length + ' groups');
    } catch (e) {
        debugLog('Init error', e.message);
    }

    renderCurrentStep();
    updateNav();
});

// ---------------------------------------------------------------------------
// Navigation
// ---------------------------------------------------------------------------

function nextStep() {
    if (STATE.currentStep < STATE.totalSteps - 1) {
        saveCurrentStepData();
        STATE.currentStep++;
        apiPost('step', { step: STATE.currentStep });
        renderCurrentStep();
        updateNav();
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }
}

function prevStep() {
    if (STATE.currentStep > 0) {
        saveCurrentStepData();
        STATE.currentStep--;
        apiPost('step', { step: STATE.currentStep });
        renderCurrentStep();
        updateNav();
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }
}

function goToStep(idx) {
    if (idx >= 0 && idx < STATE.totalSteps) {
        saveCurrentStepData();
        STATE.currentStep = idx;
        apiPost('step', { step: STATE.currentStep });
        renderCurrentStep();
        updateNav();
    }
}

function updateNav() {
    const prev = document.getElementById('btnPrev');
    const next = document.getElementById('btnNext');
    const counter = document.getElementById('stepCounter');
    const fill = document.getElementById('progressFill');

    prev.disabled = STATE.currentStep === 0;
    counter.textContent = `Step ${STATE.currentStep + 1} of ${STATE.totalSteps}`;
    fill.style.width = `${((STATE.currentStep + 1) / STATE.totalSteps) * 100}%`;

    if (STATE.currentStep === STATE.totalSteps - 1) {
        if (STATE.installing) {
            next.disabled = true;
            next.innerHTML = '<span class="spinner"></span> Installing...';
        } else if (STATE.installComplete) {
            next.disabled = true;
            next.innerHTML = 'Complete!';
        } else {
            next.disabled = true;
            next.textContent = 'Finish';
        }
    } else if (STATE.currentStep === STATE.totalSteps - 2) {
        next.disabled = false;
        next.innerHTML = 'Install <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14m0 0l-7-7m7 7l-7 7"/></svg>';
    } else {
        next.disabled = false;
        next.innerHTML = 'Next <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14m0 0l-7-7m7 7l-7 7"/></svg>';
    }

    // Update step dots
    document.querySelectorAll('.step-dot').forEach((dot, i) => {
        dot.classList.remove('active', 'completed');
        if (i === STATE.currentStep) dot.classList.add('active');
        else if (i < STATE.currentStep) dot.classList.add('completed');
    });
}

function renderStepIndicators() {
    const container = document.getElementById('stepIndicators');
    container.innerHTML = STEPS.map((s, i) => `
        <div class="step-dot" onclick="goToStep(${i})">
            <div class="step-dot-circle">${i < STATE.currentStep ? '&#10003;' : i + 1}</div>
            <div class="step-dot-label">${s.label}</div>
        </div>
    `).join('');
}

// ---------------------------------------------------------------------------
// Save form data from current step
// ---------------------------------------------------------------------------

function saveCurrentStepData() {
    // Collect all form inputs on the page
    document.querySelectorAll('[data-env-key]').forEach(el => {
        const key = el.getAttribute('data-env-key');
        if (el.type === 'checkbox') {
            STATE.envValues[key] = el.checked ? 'true' : 'false';
        } else {
            STATE.envValues[key] = el.value;
        }
    });

    // Docker toggles
    document.querySelectorAll('[data-docker-service]').forEach(el => {
        const svc = el.getAttribute('data-docker-service');
        STATE.dockerConfig.services[svc] = el.checked;
    });
    document.querySelectorAll('[data-docker-key]').forEach(el => {
        const key = el.getAttribute('data-docker-key');
        if (key === 'enabled') STATE.dockerConfig.enabled = el.checked;
        else if (key === 'mode') STATE.dockerConfig.mode = el.value;
        else if (key === 'network_name') STATE.dockerConfig.network_name = el.value;
        else if (key.startsWith('container_name_')) {
            const service = key.replace('container_name_', '');
            if (!STATE.dockerConfig.container_names) STATE.dockerConfig.container_names = {};
            STATE.dockerConfig.container_names[service] = el.value;
        }
        else if (key.startsWith('volume_')) {
            const volume = key.replace('volume_', '');
            if (!STATE.dockerConfig.volume_names) STATE.dockerConfig.volume_names = {};
            STATE.dockerConfig.volume_names[volume] = el.value;
        }
    });

    // Install options
    document.querySelectorAll('[data-install-key]').forEach(el => {
        const key = el.getAttribute('data-install-key');
        if (el.type === 'checkbox') {
            STATE.installOptions[key] = el.checked;
        } else {
            STATE.installOptions[key] = el.value;
        }
    });

    // Persist to server
    apiPost('env', { values: STATE.envValues });
    apiPost('docker', { config: STATE.dockerConfig });
    apiPost('install-options', { options: STATE.installOptions });
}

// ---------------------------------------------------------------------------
// Step renderers
// ---------------------------------------------------------------------------

function renderCurrentStep() {
    const container = document.getElementById('wizardContent');
    container.style.animation = 'none';
    container.offsetHeight; // trigger reflow
    container.style.animation = 'fadeIn 0.3s ease';

    const renderers = [
        renderWelcome,
        renderSystem,
        renderBackend,
        renderFrontend,
        renderDocker,
        renderReview,
        renderInstall,
        renderLogs,
    ];
    renderers[STATE.currentStep](container);
}

// --- Step 0: Welcome ---
function renderWelcome(el) {
    const sys = STATE.systemInfo || {};
    const osInfo = sys.os || {};
    const docker = sys.docker || {};
    const tools = sys.tools || {};

    el.innerHTML = `
        <div class="welcome-hero">
            <h1>Welcome to QGen RAG Setup</h1>
            <p>This wizard will guide you through configuring and deploying the QuestionGeneration AI platform. Let's get everything set up in a few simple steps.</p>
        </div>

        <div class="info-grid" style="margin-top:24px">
            <div class="info-item">
                <div class="info-label">Operating System</div>
                <div class="info-value">${osInfo.os_friendly || 'Detecting...'}</div>
            </div>
            <div class="info-item">
                <div class="info-label">Architecture</div>
                <div class="info-value">${sys.architecture?.arch || '...'} ${sys.architecture?.is_apple_silicon ? '(Apple Silicon)' : ''}</div>
            </div>
            <div class="info-item">
                <div class="info-label">Environment</div>
                <div class="info-value">${sys.environment?.details || '...'}</div>
            </div>
            <div class="info-item">
                <div class="info-label">Docker</div>
                <div class="info-value">${docker.docker_installed ? '<span class="badge badge-success">Installed</span>' : '<span class="badge badge-warning">Not found</span>'} ${docker.docker_running ? '<span class="badge badge-success">Running</span>' : ''}</div>
            </div>
        </div>

        <div class="card" style="margin-top:24px">
            <div class="card-header">
                <div class="card-icon purple">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/></svg>
                </div>
                <div>
                    <div class="card-title">What this wizard configures</div>
                    <div class="card-desc">Everything you need to run QGen RAG</div>
                </div>
            </div>
            <div class="info-grid">
                <div class="info-item">
                    <div class="info-label">Backend</div>
                    <div class="info-value" style="font-size:12px;color:var(--text-muted)">FastAPI, PostgreSQL + pgvector, Redis, LLM providers</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Frontend</div>
                    <div class="info-value" style="font-size:12px;color:var(--text-muted)">Expo React Native client, SvelteKit trainer web</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Docker</div>
                    <div class="info-value" style="font-size:12px;color:var(--text-muted)">Container orchestration, volume mounts, networking</div>
                </div>
                <div class="info-item">
                    <div class="info-label">AI/ML</div>
                    <div class="info-value" style="font-size:12px;color:var(--text-muted)">Ollama, Gemini, DeepSeek, embeddings, reranker</div>
                </div>
            </div>
        </div>

        <div class="card" style="margin-top:24px">
            <div class="card-header">
                <div class="card-icon green">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/></svg>
                </div>
                <div>
                    <div class="card-title">How will you use this?</div>
                    <div class="card-desc">This determines default settings for the entire setup</div>
                </div>
            </div>
            <div style="display:flex;gap:12px">
                <label class="radio-label" style="flex:1">
                    <input type="radio" name="useCase" value="development" ${STATE.useCase === 'development' ? 'checked' : ''} onchange="setUseCase('development')">
                    <div>
                        <strong>Development</strong>
                        <small style="display:block;color:var(--text-muted);margin-top:4px">Hot reload, source mounts, debug logging, single worker</small>
                    </div>
                </label>
                <label class="radio-label" style="flex:1">
                    <input type="radio" name="useCase" value="production" ${STATE.useCase === 'production' ? 'checked' : ''} onchange="setUseCase('production')">
                    <div>
                        <strong>Production</strong>
                        <small style="display:block;color:var(--text-muted);margin-top:4px">Multi-worker, optimized builds, JSON logs, restricted CORS</small>
                    </div>
                </label>
            </div>
        </div>

        ${!docker.docker_installed ? `
        <div class="alert alert-warning" style="margin-top:12px">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 9v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
            <div>Docker is not installed. You'll need Docker for the recommended containerized deployment. <a href="https://docs.docker.com/get-docker/" target="_blank" style="color:inherit;text-decoration:underline">Install Docker</a></div>
        </div>` : ''}

        <div class="alert alert-info" style="margin-top:12px">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4m0-4h.01"/></svg>
            <div>Click <strong>Next</strong> to begin configuration. Your progress is saved automatically.</div>
        </div>
    `;
}

// --- Step 1: System Info ---
function renderSystem(el) {
    const sys = STATE.systemInfo || {};
    const tools = sys.tools || {};
    const ports = sys.ports || {};
    const configs = sys.existing_config || {};

    el.innerHTML = `
        <h2 class="step-title">System Overview</h2>
        <p class="step-subtitle">Detected environment details and tool availability</p>

        <div class="card">
            <div class="card-header">
                <div class="card-icon purple"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8m-4-4v4"/></svg></div>
                <div>
                    <div class="card-title">System Details</div>
                    <div class="card-desc">Hardware and OS information</div>
                </div>
            </div>
            <div class="info-grid">
                <div class="info-item">
                    <div class="info-label">OS</div>
                    <div class="info-value">${sys.os?.os_friendly || 'Unknown'}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Kernel</div>
                    <div class="info-value">${sys.os?.os_release || 'Unknown'}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Architecture</div>
                    <div class="info-value">${sys.architecture?.arch || 'Unknown'} (${sys.architecture?.bits || '?'}-bit)</div>
                </div>
                <div class="info-item">
                    <div class="info-label">CPU</div>
                    <div class="info-value">${sys.architecture?.cpu_brand || sys.architecture?.processor || 'Unknown'}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Environment</div>
                    <div class="info-value">${sys.environment?.details || 'Unknown'}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Hostname</div>
                    <div class="info-value">${sys.os?.hostname || 'Unknown'}</div>
                </div>
            </div>
        </div>

        <div class="card">
            <div class="card-header">
                <div class="card-icon green"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14.7 6.3a1 1 0 000 1.4l1.6 1.6a1 1 0 001.4 0l3.77-3.77a6 6 0 01-7.94 7.94l-6.91 6.91a2.12 2.12 0 01-3-3l6.91-6.91a6 6 0 017.94-7.94l-3.76 3.76z"/></svg></div>
                <div>
                    <div class="card-title">Tools &amp; Dependencies</div>
                    <div class="card-desc">Required and optional tools</div>
                </div>
            </div>
            <div class="info-grid">
                ${Object.entries(tools).map(([name, info]) => `
                    <div class="info-item">
                        <div class="info-label">${name}</div>
                        <div class="info-value">
                            ${info.installed
                                ? `<span class="badge badge-success">Installed</span> <span style="font-size:11px;color:var(--text-dim)">${(info.version || '').substring(0, 40)}</span>`
                                : `<span class="badge badge-error">Not found</span>`}
                        </div>
                    </div>
                `).join('')}
            </div>
        </div>

        <div class="card">
            <div class="card-header">
                <div class="card-icon yellow"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg></div>
                <div>
                    <div class="card-title">Port Availability</div>
                    <div class="card-desc">Checking required ports</div>
                </div>
            </div>
            <div class="info-grid">
                ${Object.entries(ports).map(([port, info]) => `
                    <div class="info-item">
                        <div class="info-label">:${port} — ${info.label}</div>
                        <div class="info-value">
                            ${info.available
                                ? '<span class="badge badge-success">Available</span>'
                                : '<span class="badge badge-warning">In use</span>'}
                        </div>
                    </div>
                `).join('')}
            </div>
        </div>

        <div class="card">
            <div class="card-header">
                <div class="card-icon purple"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><path d="M14 2v6h6M16 13H8m8 4H8m2-8H8"/></svg></div>
                <div>
                    <div class="card-title">Existing Configuration</div>
                    <div class="card-desc">Previously created config files</div>
                </div>
            </div>
            <div class="info-grid">
                ${Object.entries(configs).map(([file, info]) => `
                    <div class="info-item">
                        <div class="info-label">${file}</div>
                        <div class="info-value">
                            ${info.exists
                                ? '<span class="badge badge-success">Exists</span>'
                                : '<span class="badge badge-info">Will create</span>'}
                        </div>
                    </div>
                `).join('')}
            </div>
        </div>
    </div>
    `;
}

// --- Step 2: Backend config ---
function renderBackend(el) {
    // Show groups: Database, Redis, Security, LLM Provider, Embedding & Reranker, Document Processing, Rate Limiting & Logging, Network & CORS, Training Pipeline
    const backendGroups = ['Database', 'Redis', 'Security', 'LLM Provider', 'Embedding & Reranker', 'Document Processing', 'Rate Limiting & Logging', 'Network & CORS', 'Training Pipeline'];

    el.innerHTML = `
        <h2 class="step-title">Backend Configuration</h2>
        <p class="step-subtitle">Configure your FastAPI backend, database, LLM provider, and more</p>
        ${renderEnvGroups(backendGroups)}
    `;

    // Set up conditional visibility
    setupConditionalFields();
}

// --- Step 3: Frontend config ---
function renderFrontend(el) {
    const frontendGroups = ['Frontend'];

    el.innerHTML = `
        <h2 class="step-title">Frontend Configuration</h2>
        <p class="step-subtitle">Configure the trainer web application ports and settings</p>

        ${renderEnvGroups(frontendGroups)}

        <div class="card">
            <div class="card-header">
                <div class="card-icon purple"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8m-4-4v4"/></svg></div>
                <div>
                    <div class="card-title">Trainer Web (SvelteKit)</div>
                    <div class="card-desc">The trainer web app auto-configures based on your API port setting</div>
                </div>
            </div>
            <div class="info-grid">
                <div class="info-item">
                    <div class="info-label">API Base URL</div>
                    <div class="info-value" style="font-family:var(--font-mono);font-size:13px">http://localhost:${STATE.envValues.API_PORT || '8000'}/api/v1</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Dev Server</div>
                    <div class="info-value" style="font-family:var(--font-mono);font-size:13px">http://localhost:5173</div>
                </div>
            </div>
        </div>

        <div class="card">
            <div class="card-header">
                <div class="card-icon green"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 19.5A2.5 2.5 0 016.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z"/></svg></div>
                <div>
                    <div class="card-title">Install Options</div>
                    <div class="card-desc">Choose which frontend apps to set up</div>
                </div>
            </div>
            <div class="toggle-row">
                <div class="toggle-info">
                    <div class="toggle-label">Install Trainer Web Dependencies</div>
                    <div class="toggle-desc">Run npm install in the trainer-web/ directory</div>
                </div>
                <label class="toggle-switch">
                    <input type="checkbox" data-install-key="install_trainer" ${STATE.installOptions.install_trainer ? 'checked' : ''}>
                    <span class="toggle-slider"></span>
                </label>
            </div>
        </div>
    `;
}

// --- Step 4: Docker config ---
function renderDocker(el) {
    const dc = STATE.dockerConfig;
    const dockerAvail = STATE.systemInfo?.docker?.docker_installed;

    el.innerHTML = `
        <h2 class="step-title">Docker &amp; Deployment</h2>
        <p class="step-subtitle">Configure containerized deployment or native mode</p>

        ${!dockerAvail ? `
        <div class="alert alert-warning">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 9v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
            <div>Docker is not detected on your system. You can still generate the docker-compose.yml for later use, or run services natively.</div>
        </div>` : ''}

        <div class="card">
            <div class="card-header">
                <div class="card-icon purple"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z"/></svg></div>
                <div>
                    <div class="card-title">Deployment Mode</div>
                    <div class="card-desc">Choose how to run the services</div>
                </div>
            </div>
            <div class="toggle-row">
                <div class="toggle-info">
                    <div class="toggle-label">Enable Docker Deployment</div>
                    <div class="toggle-desc">Use Docker Compose to run PostgreSQL, Redis, and the API</div>
                </div>
                <label class="toggle-switch">
                    <input type="checkbox" data-docker-key="enabled" ${dc.enabled ? 'checked' : ''} onchange="toggleDockerSection()">
                    <span class="toggle-slider"></span>
                </label>
            </div>

            <div id="dockerSettings" style="${dc.enabled ? '' : 'display:none'}">
                <div class="form-group" style="margin-top:16px">
                    <label class="form-label">
                        Mode
                        <span class="tooltip-icon" data-tip="Development: hot reload, source mounts. Production: optimized builds, no reload.">?</span>
                    </label>
                    <select class="form-select" data-docker-key="mode">
                        <option value="development" ${dc.mode === 'development' ? 'selected' : ''}>Development (hot reload, local mounts)</option>
                        <option value="production" ${dc.mode === 'production' ? 'selected' : ''}>Production (optimized, 4 workers)</option>
                    </select>
                </div>
            </div>
        </div>

        <div id="dockerServicesCard" class="card" style="${dc.enabled ? '' : 'display:none'}">
            <div class="card-header">
                <div class="card-icon green"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 12H2m20 0l-4-4m4 4l-4 4M2 12l4-4m-4 4l4 4"/></svg></div>
                <div>
                    <div class="card-title">Services</div>
                    <div class="card-desc">Toggle which services to containerize</div>
                </div>
            </div>
            <div class="toggle-row">
                <div class="toggle-info">
                    <div class="toggle-label">PostgreSQL + pgvector</div>
                    <div class="toggle-desc">Vector database for document embeddings</div>
                </div>
                <label class="toggle-switch">
                    <input type="checkbox" data-docker-service="db" ${dc.services.db ? 'checked' : ''}>
                    <span class="toggle-slider"></span>
                </label>
            </div>
            <div class="toggle-row">
                <div class="toggle-info">
                    <div class="toggle-label">Redis</div>
                    <div class="toggle-desc">Caching, sessions, rate limiting, embedding cache</div>
                </div>
                <label class="toggle-switch">
                    <input type="checkbox" data-docker-service="redis" ${dc.services.redis ? 'checked' : ''}>
                    <span class="toggle-slider"></span>
                </label>
            </div>
            <div class="toggle-row">
                <div class="toggle-info">
                    <div class="toggle-label">API Server (FastAPI)</div>
                    <div class="toggle-desc">Backend application server with ML models</div>
                </div>
                <label class="toggle-switch">
                    <input type="checkbox" data-docker-service="api" ${dc.services.api ? 'checked' : ''}>
                    <span class="toggle-slider"></span>
                </label>
            </div>
            <div class="toggle-row">
                <div class="toggle-info">
                    <div class="toggle-label">Trainer Web (SvelteKit)</div>
                    <div class="toggle-desc">Web interface for training pipeline with hot-reload</div>
                </div>
                <label class="toggle-switch">
                    <input type="checkbox" data-docker-service="trainer_web" ${dc.services.trainer_web ? 'checked' : ''}>
                    <span class="toggle-slider"></span>
                </label>
            </div>
            <div class="toggle-row">
                <div class="toggle-info">
                    <div class="toggle-label">Ollama (Docker)</div>
                    <div class="toggle-desc">Run Ollama in a container (local install recommended for GPU)</div>
                </div>
                <label class="toggle-switch">
                    <input type="checkbox" data-docker-service="ollama" ${dc.services.ollama ? 'checked' : ''}>
                    <span class="toggle-slider"></span>
                </label>
            </div>
        </div>

        <div class="card">
            <div class="card-header">
                <div class="card-icon green"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/></svg></div>
                <div>
                    <div class="card-title">Custom Names</div>
                    <div class="card-desc">Customize container names, volume names, and network name</div>
                </div>
            </div>
            <div class="form-row">
                <div class="form-group">
                    <label class="form-label">Network Name</label>
                    <input type="text" class="form-input" data-docker-key="network_name" value="${dc.network_name || 'qgen_net'}" placeholder="qgen_net">
                </div>
                <div class="form-group">
                    <label class="form-label">DB Container Name</label>
                    <input type="text" class="form-input" data-docker-key="container_name_db" value="${dc.container_names?.db || 'qgen_db'}" placeholder="qgen_db" onchange="syncContainerToEnv('db', this.value)">
                    <div class="form-hint">Changing this will auto-update the database name (POSTGRES_DB)</div>
                </div>
            </div>
            <div class="form-row">
                <div class="form-group">
                    <label class="form-label">Redis Container Name</label>
                    <input type="text" class="form-input" data-docker-key="container_name_redis" value="${dc.container_names?.redis || 'qgen_redis'}" placeholder="qgen_redis" onchange="syncContainerToEnv('redis', this.value)">
                </div>
                <div class="form-group">
                    <label class="form-label">API Container Name</label>
                    <input type="text" class="form-input" data-docker-key="container_name_api" value="${dc.container_names?.api || 'qgen_api'}" placeholder="qgen_api">
                </div>
            </div>
            <div class="form-row">
                <div class="form-group">
                    <label class="form-label">Trainer Web Container Name</label>
                    <input type="text" class="form-input" data-docker-key="container_name_trainer_web" value="${dc.container_names?.trainer_web || 'qgen_trainer'}" placeholder="qgen_trainer">
                </div>
                <div class="form-group">
                    <label class="form-label">Ollama Container Name</label>
                    <input type="text" class="form-input" data-docker-key="container_name_ollama" value="${dc.container_names?.ollama || 'qgen_ollama'}" placeholder="qgen_ollama">
                </div>
                <div class="form-group">
                    <label class="form-label">PostgreSQL Volume Name</label>
                    <input type="text" class="form-input" data-docker-key="volume_postgres" value="${dc.volume_names?.postgres_data || 'qgen_postgres_data'}" placeholder="qgen_postgres_data">
                </div>
                <div class="form-group">
                    <label class="form-label">Redis Volume Name</label>
                    <input type="text" class="form-input" data-docker-key="volume_redis" value="${dc.volume_names?.redis_data || 'qgen_redis_data'}" placeholder="qgen_redis_data">
                </div>
            </div>
            <div class="form-row">
                <div class="form-group">
                    <label class="form-label">Upload Volume Name</label>
                    <input type="text" class="form-input" data-docker-key="volume_upload" value="${dc.volume_names?.upload_data || 'qgen_upload_data'}" placeholder="qgen_upload_data">
                </div>
                <div class="form-group">
                    <label class="form-label">Model Cache Volume Name</label>
                    <input type="text" class="form-input" data-docker-key="volume_model" value="${dc.volume_names?.model_cache || 'qgen_model_cache'}" placeholder="qgen_model_cache">
                </div>
            </div>
        </div>

        <div class="card">
            <div class="card-header">
                <div class="card-icon yellow"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/></svg></div>
                <div>
                    <div class="card-title">Ollama Setup</div>
                    <div class="card-desc">Pull LLM and embedding models for local inference</div>
                </div>
            </div>
            <div class="toggle-row">
                <div class="toggle-info">
                    <div class="toggle-label">Pull Ollama Models During Install</div>
                    <div class="toggle-desc">Downloads the LLM and embedding models (may take 5-30 min)</div>
                </div>
                <label class="toggle-switch">
                    <input type="checkbox" data-install-key="setup_ollama" ${STATE.installOptions.setup_ollama ? 'checked' : ''}>
                    <span class="toggle-slider"></span>
                </label>
            </div>
            <div class="form-group" style="margin-top:12px">
                <label class="form-label">Ollama Model to Pull</label>
                <select class="form-select" data-install-key="ollama_model">
                    <option value="llama3.1:8b" ${STATE.installOptions.ollama_model === 'llama3.1:8b' ? 'selected' : ''}>llama3.1:8b (balanced, ~4.7GB)</option>
                    <option value="llama3.2:3b-instruct-q4_K_M" ${STATE.installOptions.ollama_model === 'llama3.2:3b-instruct-q4_K_M' ? 'selected' : ''}>llama3.2:3b-instruct-q4_K_M (fast, ~2GB)</option>
                    <option value="llama3.1:70b-instruct-q4_K_M" ${STATE.installOptions.ollama_model === 'llama3.1:70b-instruct-q4_K_M' ? 'selected' : ''}>llama3.1:70b (best quality, ~40GB)</option>
                    <option value="mistral:7b-instruct-q4_K_M" ${STATE.installOptions.ollama_model === 'mistral:7b-instruct-q4_K_M' ? 'selected' : ''}>mistral:7b-instruct (alternative, ~4.1GB)</option>
                </select>
            </div>
        </div>

    `;
}

function toggleDockerSection() {
    const cb = document.querySelector('[data-docker-key="enabled"]');
    const settings = document.getElementById('dockerSettings');
    const services = document.getElementById('dockerServicesCard');
    if (cb) {
        settings.style.display = cb.checked ? '' : 'none';
        services.style.display = cb.checked ? '' : 'none';
    }
}

// --- Step 5: Review ---
async function renderReview(el) {
    el.innerHTML = `
        <h2 class="step-title">Review Configuration</h2>
        <p class="step-subtitle">Review your settings before installation. Click the tabs to preview generated files.</p>
        <div class="tab-bar">
            <button class="tab-btn active" onclick="switchReviewTab('env', this)">Environment (.env.local)</button>
            <button class="tab-btn" onclick="switchReviewTab('compose', this)">Docker Compose</button>
            <button class="tab-btn" onclick="switchReviewTab('summary', this)">Summary</button>
        </div>
        <div id="reviewContent"><div class="spinner" style="margin:40px auto;display:block"></div></div>
    `;

    // Save current data first
    saveCurrentStepData();
    switchReviewTab('env', document.querySelector('.tab-btn.active'));
}

async function switchReviewTab(tab, btnEl) {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    if (btnEl) btnEl.classList.add('active');

    const container = document.getElementById('reviewContent');
    container.innerHTML = '<div class="spinner" style="margin:40px auto;display:block"></div>';

    if (tab === 'env') {
        const data = await apiGet('preview-env');
        container.innerHTML = `<pre class="code-preview">${escapeHtml(data.content || 'Error generating preview')}</pre>`;
    } else if (tab === 'compose') {
        if (STATE.dockerConfig.enabled) {
            const data = await apiGet('preview-compose');
            container.innerHTML = `<pre class="code-preview">${escapeHtml(data.content || 'Error generating preview')}</pre>`;
        } else {
            container.innerHTML = '<div class="alert alert-info">Docker deployment is disabled. No docker-compose.yml will be generated.</div>';
        }
    } else if (tab === 'summary') {
        const vals = STATE.envValues;
        container.innerHTML = `
            <div class="info-grid">
                <div class="info-item">
                    <div class="info-label">LLM Provider</div>
                    <div class="info-value">${vals.LLM_PROVIDER || 'ollama'}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Database</div>
                    <div class="info-value">${vals.POSTGRES_DB || 'qgen_db'} @ :${vals.POSTGRES_PORT || '5432'}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">API Port</div>
                    <div class="info-value">${vals.API_PORT || '8000'}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Deployment Mode</div>
                    <div class="info-value">${STATE.dockerConfig.enabled ? STATE.dockerConfig.mode : 'Native (no Docker)'}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Embedding Model</div>
                    <div class="info-value">${vals.EMBEDDING_MODEL || 'nomic-embed-text'}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Reranker</div>
                    <div class="info-value">${vals.RERANKER_ENABLED === 'true' ? vals.RERANKER_MODEL || 'Enabled' : 'Disabled'}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Use Case</div>
                    <div class="info-value">${STATE.useCase === 'production' ? 'Production' : 'Development'}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Install Trainer Web</div>
                    <div class="info-value">${STATE.installOptions.install_trainer ? 'Yes' : 'No'}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Pull Ollama Models</div>
                    <div class="info-value">${STATE.installOptions.setup_ollama ? STATE.installOptions.ollama_model : 'No'}</div>
                </div>
            </div>

            <div class="alert alert-info" style="margin-top:16px">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4m0-4h.01"/></svg>
                <div>
                    <strong>Files that will be created/updated:</strong><br>
                    .env.local, client/.env.local, trainer-web/.env.local${STATE.dockerConfig.enabled ? ', docker-compose.yml' : ''}
                </div>
            </div>
        `;
    }
}

// --- Step 6: Install ---
function renderInstall(el) {
    if (!STATE.installing && !STATE.installComplete) {
        el.innerHTML = `
            <h2 class="step-title">Installation</h2>
            <p class="step-subtitle">Ready to generate configs and install dependencies</p>
            <div class="card" style="text-align:center;padding:40px">
                <p style="font-size:16px;margin-bottom:20px">Click the button below to start installation.</p>
                <button class="btn btn-primary" onclick="startInstall()" style="padding:14px 32px;font-size:16px">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4m4-5l5 5 5-5m-5 5V3"/></svg>
                    Start Installation
                </button>
            </div>
        `;
    } else {
        renderInstallProgress(el);
    }
}

async function startInstall() {
    STATE.installing = true;
    updateNav();

    const el = document.getElementById('wizardContent');
    renderInstallProgress(el);

    try {
        const result = await apiPost('install', {});
        debugLog('Install started', result);
    } catch (e) {
        debugLog('Install error', e.message);
    }

    // Start polling
    STATE.pollTimer = setInterval(pollInstallLog, 2000);
}

async function pollInstallLog() {
    try {
        const data = await apiGet('install-log');
        STATE.installLog = data.log || [];
        updateInstallLog();

        const stateData = await apiGet('state');
        if (stateData.completed) {
            STATE.installComplete = true;
            STATE.installing = false;
            clearInterval(STATE.pollTimer);
            STATE.installResults = stateData.install_results || {};
            updateNav();
            renderInstallComplete();
        }
    } catch (e) {
        debugLog('Poll error', e.message);
    }
}

function renderInstallProgress(el) {
    el.innerHTML = `
        <h2 class="step-title">Installing...</h2>
        <p class="step-subtitle">Generating configs, installing dependencies, and starting services</p>
        <div class="card">
            <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px">
                <div class="spinner"></div>
                <span style="color:var(--text-muted)">Installation in progress...</span>
            </div>
            <div class="log-container" id="installLog">
                <div class="log-entry"><span class="log-info">Waiting for logs...</span></div>
            </div>
        </div>
    `;
}

function updateInstallLog() {
    const container = document.getElementById('installLog');
    if (!container) return;

    container.innerHTML = STATE.installLog.map(line => {
        try {
            const entry = JSON.parse(line);
            const cls = entry.level === 'error' ? 'log-error' : entry.level === 'warning' ? 'log-warning' : 'log-info';
            return `<div class="log-entry"><span class="log-time">${entry.time || ''}</span><span class="${cls}">${escapeHtml(entry.msg || line)}</span></div>`;
        } catch {
            return `<div class="log-entry"><span class="log-info">${escapeHtml(line)}</span></div>`;
        }
    }).join('');

    container.scrollTop = container.scrollHeight;
}

async function renderInstallComplete() {
    const el = document.getElementById('wizardContent');
    const urls = await apiGet('service-urls');

    el.innerHTML = `
        <div class="welcome-hero">
            <h1 style="background:linear-gradient(135deg,var(--success),#4ade80);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text">Setup Complete!</h1>
            <p>Your QGen RAG instance is configured and ready.</p>
        </div>

        <div class="card">
            <div class="card-header">
                <div class="card-icon green"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 11-5.93-9.14"/><path d="M22 4L12 14.01l-3-3"/></svg></div>
                <div>
                    <div class="card-title">Service URLs</div>
                    <div class="card-desc">Access your running services</div>
                </div>
            </div>
            <div class="url-grid">
                ${(urls.urls || []).map(u => `
                    <a href="${u.url}" target="_blank" class="url-card" style="text-decoration:none;color:inherit">
                        <div class="url-card-info">
                            <div class="url-card-name">${u.name}</div>
                            <div class="url-card-url">${u.url}</div>
                            <div class="url-card-desc">${u.description}</div>
                        </div>
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--text-dim)" stroke-width="2"><path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6m4-3h6v6m-11 5L21 3"/></svg>
                    </a>
                `).join('')}
            </div>
        </div>

        <div class="card">
            <div class="card-header">
                <div class="card-icon purple"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><path d="M14 2v6h6M16 13H8m8 4H8m2-8H8"/></svg></div>
                <div>
                    <div class="card-title">Installation Log</div>
                    <div class="card-desc">Full log of the installation process</div>
                </div>
            </div>
            <div class="log-container" style="max-height:250px">
                ${STATE.installLog.map(line => {
                    try {
                        const entry = JSON.parse(line);
                        const cls = entry.level === 'error' ? 'log-error' : entry.level === 'warning' ? 'log-warning' : 'log-info';
                        return `<div class="log-entry"><span class="log-time">${entry.time || ''}</span><span class="${cls}">${escapeHtml(entry.msg || line)}</span></div>`;
                    } catch {
                        return `<div class="log-entry"><span class="log-info">${escapeHtml(line)}</span></div>`;
                    }
                }).join('')}
            </div>
        </div>

        <div class="card">
            <div class="card-header">
                <div class="card-icon yellow"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/></svg></div>
                <div>
                    <div class="card-title">Next Steps</div>
                    <div class="card-desc">What to do after setup</div>
                </div>
            </div>
            <ol style="padding-left:20px;color:var(--text-muted);font-size:14px;line-height:2">
                <li>Check service health: <code style="background:var(--bg-input);padding:2px 6px;border-radius:4px;font-size:12px">curl http://localhost:${STATE.envValues.API_PORT || '8000'}/health</code></li>
                <li>Open Swagger docs: <a href="http://localhost:${STATE.envValues.API_PORT || '8000'}/docs" target="_blank" style="color:var(--primary)">API Documentation</a></li>
                <li>Start the trainer web: <code style="background:var(--bg-input);padding:2px 6px;border-radius:4px;font-size:12px">cd trainer-web && npm run dev</code></li>
                <li>View logs: <code style="background:var(--bg-input);padding:2px 6px;border-radius:4px;font-size:12px">docker compose logs -f api</code></li>
            </ol>
        </div>

        <div class="alert alert-success" style="margin-top:12px">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 11-5.93-9.14"/><path d="M22 4L12 14.01l-3-3"/></svg>
            <div>You can safely close this wizard. Re-run <code style="background:rgba(0,0,0,0.2);padding:2px 6px;border-radius:4px">python setup_wizard.py</code> anytime to reconfigure.</div>
        </div>
    `;
}

// ---------------------------------------------------------------------------
// Env group renderer (reusable for backend/frontend steps)
// ---------------------------------------------------------------------------

function renderEnvGroups(groupNames) {
    const groups = STATE.envSchema.filter(g => groupNames.includes(g.group));
    return groups.map(group => {
        // Filter variables based on advanced mode
        const filteredVars = STATE.advancedMode 
            ? group.vars 
            : group.vars.filter(v => v.advanced !== true);
        
        const vars = filteredVars.map(v => renderEnvField(v)).join('');
        return `
            <div class="card">
                <div class="card-header">
                    <div class="card-icon purple">
                        ${getIconSvg(group.icon)}
                    </div>
                    <div>
                        <div class="card-title">${group.group}</div>
                        <div class="card-desc">${group.description}</div>
                    </div>
                    <div class="card-toggle">
                        <button class="btn btn-ghost btn-sm" onclick="toggleAdvancedMode(!STATE.advancedMode)" title="${STATE.advancedMode ? 'Switch to Basic Mode' : 'Switch to Advanced Mode'}">
                            ${getIconSvg(STATE.advancedMode ? 'cpu' : 'zap')}
                            <span style="margin-left:4px">${STATE.advancedMode ? 'Advanced' : 'Basic'}</span>
                        </button>
                    </div>
                </div>
                <div class="form-row-wrap">
                    ${vars}
                </div>
            </div>
        `;
    }).join('');
}

function renderEnvField(v) {
    const val = STATE.envValues[v.key] ?? STATE.defaults[v.key] ?? '';
    const showIf = v.show_if ? `data-show-if='${JSON.stringify(v.show_if)}'` : '';
    const hidden = v.show_if ? shouldHideField(v.show_if) : false;

    let input = '';
    if (v.type === 'select' && v.options) {
        const opts = v.options.map(o => `<option value="${o}" ${val === o ? 'selected' : ''}>${o}</option>`).join('');
        input = `<select class="form-select" data-env-key="${v.key}" ${v.key === 'LLM_PROVIDER' ? 'onchange="setupConditionalFields()"' : ''}>${opts}</select>`;
    } else if (v.type === 'password') {
        input = `<div style="display:flex;gap:8px"><input type="password" class="form-input" data-env-key="${v.key}" value="${escapeAttr(val)}" placeholder="${v.label}"><button class="btn btn-ghost btn-sm" onclick="togglePasswordVis(this)" type="button" style="flex-shrink:0">Show</button>${v.key === 'SECRET_KEY' ? `<button class="btn btn-ghost btn-sm" onclick="generateSecret('${v.key}')" type="button" style="flex-shrink:0">Gen</button>` : ''}</div>`;
    } else {
        input = `<input type="${v.type === 'number' ? 'number' : 'text'}" class="form-input" data-env-key="${v.key}" value="${escapeAttr(val)}" placeholder="${v.label}">`;
    }

    // Add recommended indicator
    const recommended = v.recommended ? `<small class="form-hint">Recommended: ${v.recommended}</small>` : '';

    return `
        <div class="form-group" ${showIf} style="${hidden ? 'display:none' : ''}">
            <label class="form-label">
                ${v.label}
                ${v.tooltip ? `<span class="tooltip-icon" data-tip="${escapeAttr(v.tooltip)}">?</span>` : ''}
            </label>
            ${input}
            ${recommended}
        </div>
    `;
}

function toggleAdvancedMode(advanced) {
    STATE.advancedMode = advanced;
    renderCurrentStep();
}

function setUseCase(mode) {
    STATE.useCase = mode;
    STATE.dockerConfig.mode = mode;

    if (mode === 'production') {
        // Production defaults
        STATE.envValues['LOG_LEVEL'] = 'warning';
        STATE.envValues['LOG_JSON'] = 'true';
        STATE.envValues['CORS_ORIGINS'] = 'https://yourdomain.com';
        STATE.envValues['QUICK_GENERATE_PARALLEL_WORKERS'] = '4';
        STATE.envValues['RATE_LIMIT_REQUESTS'] = '60';
        STATE.envValues['ACCESS_TOKEN_EXPIRE_MINUTES'] = '30';
        STATE.envValues['REFRESH_TOKEN_EXPIRE_DAYS'] = '7';
    } else {
        // Development defaults
        STATE.envValues['LOG_LEVEL'] = 'info';
        STATE.envValues['LOG_JSON'] = 'false';
        STATE.envValues['CORS_ORIGINS'] = '*';
        STATE.envValues['QUICK_GENERATE_PARALLEL_WORKERS'] = '6';
        STATE.envValues['RATE_LIMIT_REQUESTS'] = '100';
        STATE.envValues['ACCESS_TOKEN_EXPIRE_MINUTES'] = '60';
        STATE.envValues['REFRESH_TOKEN_EXPIRE_DAYS'] = '30';
    }
}

function shouldHideField(showIf) {
    for (const [key, val] of Object.entries(showIf)) {
        const current = STATE.envValues[key] ?? STATE.defaults[key] ?? '';
        if (current !== val) return true;
    }
    return false;
}

function setupConditionalFields() {
    document.querySelectorAll('[data-show-if]').forEach(el => {
        const cond = JSON.parse(el.getAttribute('data-show-if'));
        let show = true;
        for (const [key, val] of Object.entries(cond)) {
            const input = document.querySelector(`[data-env-key="${key}"]`);
            const current = input ? input.value : (STATE.envValues[key] ?? STATE.defaults[key] ?? '');
            if (current !== val) { show = false; break; }
        }
        el.style.display = show ? '' : 'none';
    });
}

// ---------------------------------------------------------------------------
// Utility functions
// ---------------------------------------------------------------------------

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function syncContainerToEnv(service, containerName) {
    // Auto-update environment variables when container names change
    if (service === 'db') {
        // Update POSTGRES_DB to match container name (optional convention)
        const dbField = document.querySelector('[data-env-key="POSTGRES_DB"]');
        if (dbField && !dbField.value.includes('_db')) {
            // Only update if it's a default value
            dbField.value = containerName.replace(/_container$/, '').replace(/_db$/, '') + '_db';
            STATE.envValues['POSTGRES_DB'] = dbField.value;
        }
    }
    // Note: Redis and API don't have corresponding env vars that typically match container names
}

function escapeAttr(str) {
    return String(str).replace(/"/g, '&quot;').replace(/'/g, '&#39;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function togglePasswordVis(btn) {
    const input = btn.parentElement.querySelector('input');
    if (input.type === 'password') {
        input.type = 'text';
        btn.textContent = 'Hide';
    } else {
        input.type = 'password';
        btn.textContent = 'Show';
    }
}

async function generateSecret(key) {
    const data = await apiPost('generate-secret', { length: 64 });
    const input = document.querySelector(`[data-env-key="${key}"]`);
    if (input && data.key) {
        input.value = data.key;
        input.type = 'text';
        STATE.envValues[key] = data.key;
    }
}

// ---------------------------------------------------------------------------
// Step 7: Logs
// ---------------------------------------------------------------------------

function renderLogs(el) {
    el.innerHTML = `
        <div class="card">
            <div class="card-header">
                <div class="card-icon blue">${getIconSvg('file-text')}</div>
                <div>
                    <div class="card-title">Service Logs</div>
                    <div class="card-desc">Monitor real-time logs from all running services</div>
                </div>
            </div>
        </div>

        <div class="card">
            <div class="card-header">
                <div class="card-title">Log Controls</div>
            </div>
            <div class="form-row">
                <div class="form-group">
                    <label class="form-label">Service</label>
                    <select id="logServiceSelect" class="form-select">
                        <option value="all">All Services (Combined)</option>
                        <option value="db">PostgreSQL (db)</option>
                        <option value="redis">Redis (redis)</option>
                        <option value="api">API Server (api)</option>
                        <option value="trainer_web">Trainer Web (trainer_web)</option>
                        <option value="client">Client (client)</option>
                        <option value="ollama">Ollama (ollama)</option>
                    </select>
                </div>
                <div class="form-group">
                    <label class="form-label">Lines</label>
                    <select id="logLinesSelect" class="form-select">
                        <option value="50">Last 50 lines</option>
                        <option value="100">Last 100 lines</option>
                        <option value="200">Last 200 lines</option>
                        <option value="500">Last 500 lines</option>
                        <option value="follow">Follow (Live)</option>
                    </select>
                </div>
                <div class="form-group">
                    <label class="form-label">&nbsp;</label>
                    <button onclick="refreshLogs()" class="btn btn-primary">
                        ${getIconSvg('search')} Refresh
                    </button>
                </div>
            </div>
        </div>

        <div class="card">
            <div class="card-header">
                <div class="card-title">Log Output</div>
                <div id="logStatus" class="card-desc">Select a service and click refresh to view logs</div>
            </div>
            <div class="log-container">
                <pre id="logOutput" class="log-output"></pre>
            </div>
        </div>
    `;
}

async function refreshLogs() {
    const service = document.getElementById('logServiceSelect').value;
    const lines = document.getElementById('logLinesSelect').value;
    const output = document.getElementById('logOutput');
    const status = document.getElementById('logStatus');
    
    status.textContent = 'Fetching logs...';
    output.textContent = '';
    
    try {
        const response = await apiGet(`logs?service=${service}&lines=${lines}`);
        if (response.logs) {
            output.textContent = response.logs;
            status.textContent = `Showing logs for ${service === 'all' ? 'all services' : service}`;
        } else {
            output.textContent = 'No logs available';
            status.textContent = 'No logs found';
        }
    } catch (error) {
        output.textContent = `Error fetching logs: ${error.message}`;
        status.textContent = 'Failed to fetch logs';
    }
}

function getIconSvg(name) {
    const icons = {
        database: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg>',
        zap: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>',
        shield: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>',
        brain: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2a7 7 0 017 7c0 2.38-1.19 4.47-3 5.74V17a2 2 0 01-2 2h-4a2 2 0 01-2-2v-2.26C6.19 13.47 5 11.38 5 9a7 7 0 017-7z"/><path d="M10 21v1a2 2 0 104 0v-1"/></svg>',
        search: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/></svg>',
        'file-text': '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><path d="M14 2v6h6M16 13H8m8 4H8m2-8H8"/></svg>',
        activity: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>',
        globe: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M2 12h20M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z"/></svg>',
        smartphone: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="5" y="2" width="14" height="20" rx="2" ry="2"/><path d="M12 18h.01"/></svg>',
        cpu: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/><path d="M9 1v3m6-3v3M9 20v3m6-3v3M20 9h3M20 14h3M1 9h3M1 14h3"/></svg>',
        box: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z"/></svg>',
    };
    return icons[name] || icons.cpu;
}

// ---------------------------------------------------------------------------
// Debug
// ---------------------------------------------------------------------------

function toggleDebug() {
    const panel = document.getElementById('debugPanel');
    panel.style.display = panel.style.display === 'none' ? 'flex' : 'none';
}

function debugLog(label, data) {
    const el = document.getElementById('debugLog');
    if (!el) return;
    const ts = new Date().toLocaleTimeString();
    const msg = typeof data === 'object' ? JSON.stringify(data, null, 2) : data;
    el.textContent += `[${ts}] ${label}: ${msg}\n`;
    el.scrollTop = el.scrollHeight;
}
