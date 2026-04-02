# Current Project Documentation

## 1. Project Overview

**Product Name**: VQuest / VQuest Trainer

**Main Purpose**: A stateful RAG-based question generation system for educators. The platform enables teachers to upload educational documents (PDFs, DOCX, TXT), generate examination questions using AI with Retrieval-Augmented Generation (RAG), and have those questions vetted/approved by human reviewers. The system supports continuous learning through a training pipeline that fine-tunes models based on approved questions and vetting feedback.

**Main User Types**:
1. **Teacher** - Creates subjects, uploads documents, generates questions, can also vet questions
2. **Vetter** - Reviews and approves/rejects generated questions
3. **Admin** - Manages users, system settings, monitors overall platform statistics

**System Architecture**: 
- **Frontend**: SvelteKit SPA with responsive mobile-first design
- **Backend**: FastAPI with PostgreSQL (pgvector) for document storage and SQLite for auth
- **ML Pipeline**: Embedding models (nomic-embed-text), cross-encoder reranking, LLM providers (DeepSeek, Gemini, Ollama)
- **Training Pipeline**: LoRA fine-tuning with SFT and DPO training pairs

## 2. Project Structure

```
qgen_rag/
├── backend/                     # FastAPI Backend
│   ├── app/
│   │   ├── api/v1/               # API endpoints
│   │   │   ├── endpoints/        # Route handlers
│   │   │   │   ├── auth.py       # Authentication endpoints
│   │   │   │   ├── admin.py      # Admin dashboard endpoints
│   │   │   │   ├── questions.py  # Question generation endpoints
│   │   │   │   ├── vetter.py     # Vetting workflow endpoints
│   │   │   │   ├── training.py   # Training pipeline endpoints
│   │   │   │   ├── subjects.py   # Subject/topic management
│   │   │   │   ├── documents.py  # Document upload/management
│   │   │   │   ├── rubrics.py    # Rubric management
│   │   │   │   ├── settings.py   # System settings
│   │   │   │   └── websocket.py  # WebSocket endpoints
│   │   │   ├── deps.py           # Authentication dependencies
│   │   │   └── router.py         # API router assembly
│   │   ├── core/                 # Core infrastructure
│   │   │   ├── config.py         # Environment configuration
│   │   │   ├── database.py       # PostgreSQL connection (pgvector)
│   │   │   ├── auth_database.py  # SQLite auth database
│   │   │   ├── security.py       # Password hashing, JWT
│   │   │   └── logging.py        # Structured logging
│   │   ├── models/               # Database models
│   │   │   ├── user.py           # User model (SQLite)
│   │   │   ├── question.py       # Question, GenerationSession
│   │   │   ├── document.py       # Document, DocumentChunk
│   │   │   ├── subject.py        # Subject, Topic, SubjectGroup
│   │   │   ├── training.py       # TrainingJob, ModelVersion, VettingLog, TrainingPair
│   │   │   ├── vetting_progress.py # TeacherVettingProgress
│   │   │   └── system_settings.py # System configuration storage
│   │   ├── schemas/              # Pydantic request/response schemas
│   │   └── services/             # Business logic services
│   │       ├── question_service.py    # RAG question generation
│   │       ├── training_service.py    # LoRA fine-tuning pipeline
│   │       ├── document_service.py    # Document processing
│   │       ├── embedding_service.py   # Vector embeddings
│   │       ├── vetting_service.py     # Vetting workflow
│   │       ├── novelty_service.py     # Duplicate detection
│   │       ├── llm_service.py         # LLM abstraction
│   │       ├── deepseek_service.py    # DeepSeek provider
│   │       ├── gemini_service.py       # Gemini provider
│   │       ├── provider_service.py    # Multi-provider management
│   │       ├── redis_service.py       # Redis caching/queues
│   │       └── websocket_manager.py   # WebSocket broadcasting
│   ├── alembic/                # Database migrations
│   ├── scripts/                # Utility scripts
│   └── auth.db                 # SQLite auth database
├── trainer-web/                # SvelteKit Frontend
│   ├── src/
│   │   ├── routes/             # SvelteKit routes
│   │   │   ├── +layout.svelte  # Main layout with navigation
│   │   │   ├── +page.svelte    # Landing/home page
│   │   │   ├── teacher/        # Teacher portal routes
│   │   │   │   ├── dashboard/      # Teacher home with mode selection
│   │   │   │   ├── subjects/       # Subject/topic management
│   │   │   │   ├── train/          # Training/vetting interface
│   │   │   │   ├── stats/          # Statistics view
│   │   │   │   ├── verify/         # Verifier mode (voice comments)
│   │   │   │   ├── ab-test/        # A/B testing (commented)
│   │   │   │   ├── ops/            # AI Ops status
│   │   │   │   ├── profile/        # User profile
│   │   │   │   └── login/          # Teacher login
│   │   │   ├── vetter/         # Vetter portal routes
│   │   │   │   ├── dashboard/      # Vetter home
│   │   │   │   ├── subjects/       # Subject selection for vetting
│   │   │   │   ├── loop/             # Vetting loop UI
│   │   │   │   ├── profile/
│   │   │   │   └── login/
│   │   │   ├── admin/          # Admin portal routes
│   │   │   │   ├── dashboard/
│   │   │   │   ├── users/
│   │   │   │   ├── teachers/
│   │   │   │   ├── vetters/
│   │   │   │   ├── subjects/
│   │   │   │   ├── settings/
│   │   │   │   ├── profile/
│   │   │   │   └── login/
│   │   │   ├── login/          # Generic login
│   │   │   ├── privacy-policy/
│   │   │   └── disclaimer/
│   │   ├── lib/                # Shared libraries
│   │   │   ├── api/            # API client modules
│   │   │   │   ├── client.ts       # HTTP client
│   │   │   │   ├── auth.ts         # Auth API
│   │   │   │   ├── subjects.ts     # Subjects API
│   │   │   │   ├── documents.ts    # Documents API
│   │   │   │   ├── vetting.ts      # Vetting API
│   │   │   │   ├── training.ts     # Training API
│   │   │   │   ├── admin.ts        # Admin API
│   │   │   │   ├── generation-websocket.ts  # WebSocket client
│   │   │   │   └── ops.ts          # AI Ops API
│   │   │   ├── components/     # Reusable Svelte components
│   │   │   │   ├── AuthForm.svelte
│   │   │   │   ├── MobileNavBar.svelte
│   │   │   │   ├── ThemePicker.svelte
│   │   │   │   ├── FileUploadZone.svelte
│   │   │   │   ├── VoiceRecorder.svelte
│   │   │   │   └── WorkflowWizard.svelte
│   │   │   ├── session/        # Auth session store
│   │   │   ├── theme/          # Theme management
│   │   │   ├── vetting-progress.ts  # Frontend vetting progress persistence
│   │   │   └── vetter-progress.ts   # Vetter progress store
│   │   └── app.html            # HTML template
│   ├── static/                 # Static assets
│   │   ├── icons/              # PWA icons
│   │   ├── theme-pictures/     # Theme backgrounds
│   │   └── manifest.webmanifest # PWA manifest
│   └── package.json
├── postman/                    # API testing collections
├── docker-compose.yml          # Docker orchestration
└── README.md
```

## 3. Architecture Overview

### Frontend Structure
- **Framework**: SvelteKit with Svelte 5 runes
- **Styling**: CSS with custom glass-morphism design system
- **State Management**: Svelte stores for session, reactive state with `$state` and `$derived`
- **PWA Features**: Service worker, manifest, theme-color, offline support
- **Responsive**: Mobile-first design with desktop sidebar layout

### Backend Structure
- **Framework**: FastAPI with async SQLAlchemy
- **Dual Database**:
  - PostgreSQL with pgvector extension (document chunks, questions, training data)
  - SQLite (user auth, sessions, audit logs)
- **Redis**: Caching, rate limiting, WebSocket pub/sub, generation locks
- **File Storage**: Local filesystem for uploads, LoRA adapters, training data

### Data Layer
- **Vector Store**: pgvector for document chunk embeddings
- **ORM**: SQLAlchemy 2.0 with asyncpg (PostgreSQL) and aiosqlite (SQLite)
- **Schema Validation**: Pydantic for request/response validation
- **Migration**: Alembic for database migrations

### Key Integrations
- **LLM Providers**: DeepSeek (default), Google Gemini, Ollama (local)
- **Embedding**: Ollama API with nomic-embed-text (768 dims)
- **Reranker**: Optional cross-encoder (mxbai-rerank-large-v1)
- **Training**: LoRA fine-tuning with unsloth/training libraries

### Auth/Session/RBAC
- **Auth**: JWT tokens (access + refresh) with Bearer scheme
- **Password**: bcrypt hashing
- **RBAC**: Three roles (teacher, vetter, admin) + action-level permissions (can_generate, can_vet, can_manage_groups)
- **Session**: Refresh token rotation, multi-device session tracking

## 4. User Roles and Permissions

### Teacher
**Authentication Path**: `/teacher/login` or `/login`

**Role Identifier**: `teacher` (default)

**Default Permissions**:
- `can_generate: true` - Can generate questions
- `can_vet: true` - Can vet questions (self-vetting)
- `can_manage_groups: true` - Can manage subject groups

**Accessible Pages**:
- `/teacher/dashboard` - Mode selection home
- `/teacher/subjects` - Subject/topic management with group hierarchy
- `/teacher/train` - Vetting/training interface (routes to existing/new topics)
- `/teacher/train/loop` - Loop vetting interface for generated questions
- `/teacher/stats` - Personal statistics
- `/teacher/profile` - User profile management
- `/teacher/verify` - Voice verification mode (commented in UI)

**Key Actions**:
- Create subjects with code and name
- Create hierarchical subject groups (top-level departments only for subjects)
- Upload documents (PDF, DOCX, TXT) per topic
- Generate questions from documents using RAG
- Vet/approve/reject own generated questions
- View generation statistics

**Supporting Files**:
- `trainer-web/src/routes/teacher/+layout.svelte` - Teacher layout
- `trainer-web/src/routes/teacher/subjects/+page.svelte` - Subject management
- `trainer-web/src/routes/teacher/train/+page.svelte` - Train interface
- `trainer-web/src/lib/api/subjects.ts` - Subject API client
- `backend/app/api/v1/endpoints/subjects.py` - Subject API endpoints

### Vetter
**Authentication Path**: `/vetter/login`

**Role Identifier**: `vetter`

**Default Permissions**:
- `can_generate: false` - Cannot generate questions
- `can_vet: true` - Can vet questions from all teachers
- `can_manage_groups: false` - Cannot manage groups

**Accessible Pages**:
- `/vetter/dashboard` - Dashboard with pending stats
- `/vetter/subjects` - Subject selection for vetting
- `/vetter/loop` - Vetting loop for reviewing questions
- `/vetter/profile` - Profile management

**Key Actions**:
- View questions across all teachers (scoped by subject/topic)
- Approve questions with quality scores
- Reject questions with reason codes
- Edit questions and submit corrections (creates DPO training pairs)
- Resume incomplete vetting sessions (auto-saved progress)

**Supporting Files**:
- `trainer-web/src/routes/vetter/+page.svelte` - Vetter home
- `trainer-web/src/routes/vetter/dashboard/+page.svelte` - Vetter dashboard
- `trainer-web/src/routes/vetter/loop/+page.svelte` - Vetting loop
- `trainer-web/src/lib/vetter-progress.ts` - Progress persistence
- `backend/app/api/v1/endpoints/vetter.py` - Vetter API endpoints

### Admin
**Authentication Path**: `/admin/login`

**Role Identifier**: `admin`

**Default Permissions**:
- `can_generate: true`
- `can_vet: true`
- `can_manage_groups: true`
- Full system access via `is_superuser` privileges

**Accessible Pages**:
- `/admin/dashboard` - System-wide statistics
- `/admin/users` - User management (CRUD)
- `/admin/teachers` - Teacher overview
- `/admin/vetters` - Vetter overview
- `/admin/subjects` - All subjects view
- `/admin/settings` - System configuration
- `/admin/profile` - Profile management
- `/admin/ops` - AI Ops status page

**Key Actions**:
- Create/update/delete users with any role
- Toggle user permissions (can_generate, can_vet, can_manage_groups)
- Enable/disable user signup system-wide
- Configure generation provider settings
- View provider metrics and rejection rates
- View training pipeline status
- Trigger manual training runs
- Activate/deactivate model versions

**Supporting Files**:
- `trainer-web/src/routes/admin/+layout.svelte` - Admin layout
- `trainer-web/src/routes/admin/dashboard/+page.svelte` - Admin dashboard
- `trainer-web/src/routes/admin/users/+page.svelte` - User management
- `trainer-web/src/routes/admin/settings/+page.svelte` - Settings UI
- `backend/app/api/v1/endpoints/admin.py` - Admin API
- `backend/app/api/v1/endpoints/settings.py` - Settings API

## 5. Complete Feature List

### Authentication
| Feature | Status | Roles | Files |
|---------|--------|-------|-------|
| JWT Token Authentication | **Implemented** | All | `backend/app/core/security.py`, `deps.py` |
| Access Token (60min expiry) | **Implemented** | All | `backend/app/api/v1/endpoints/auth.py` |
| Refresh Token (30day expiry) | **Implemented** | All | `backend/app/models/auth.py` |
| Multi-device Session Tracking | **Implemented** | All | `backend/app/services/user_service.py` |
| Logout from single device | **Implemented** | All | `/auth/logout` endpoint |
| Logout from all devices | **Implemented** | All | `/auth/logout-all` endpoint |
| Password Change | **Implemented** | All | `/auth/change-password` endpoint |
| Avatar Upload | **Implemented** | All | `/auth/upload-avatar`, `/auth/avatar` DELETE |
| Signup Enable/Disable Toggle | **Implemented** | Admin | `/settings/signup` endpoints |
| Rate Limiting (per endpoint) | **Implemented** | All | `deps.py` rate_limit() |
| Account Lockout (failed logins) | **Implemented** | All | `user_service.py` authenticate_user() |

### User Management
| Feature | Status | Roles | Files |
|---------|--------|-------|-------|
| User Registration | **Implemented** | Public (if enabled) | `/auth/register` |
| User Login | **Implemented** | All | `/auth/login` |
| Get Current User | **Implemented** | All | `/auth/me` |
| Update Profile | **Implemented** | All | `/auth/update-profile` |
| Create User (Admin) | **Implemented** | Admin | `/admin/users` POST |
| Update User (Admin) | **Implemented** | Admin | `/admin/users/{id}` PUT |
| Delete User (Admin) | **Implemented** | Admin | `/admin/users/{id}` DELETE |
| List All Users (Admin) | **Implemented** | Admin | `/admin/users` GET |
| Permission Management | **Implemented** | Admin | User.can_generate, can_vet, can_manage_groups |

### Subject & Topic Management
| Feature | Status | Roles | Files |
|---------|--------|-------|-------|
| Create Subject | **Implemented** | Teacher, Admin | `/subjects` POST |
| List Subjects | **Implemented** | All | `/subjects` GET |
| Update Subject | **Implemented** | Owner/Admin | `/subjects/{id}` PUT |
| Delete Subject | **Implemented** | Owner/Admin | `/subjects/{id}` DELETE |
| Subject Tree View | **Implemented** | All | `/subjects/tree` GET |
| Create Topic | **Implemented** | Teacher, Admin | `/subjects/{id}/topics` POST |
| Update Topic | **Implemented** | Owner/Admin | `/subjects/{id}/topics/{tid}` PUT |
| Delete Topic | **Implemented** | Owner/Admin | `/subjects/{id}/topics/{tid}` DELETE |
| Syllabus Upload per Topic | **Implemented** | Teacher, Admin | `/subjects/{id}/topics/{tid}/syllabus` |
| Learning Outcomes (LO) | **Implemented** | Teacher, Admin | Subject model learning_outcomes |
| Course Outcomes (CO) | **Implemented** | Teacher, Admin | Subject model course_outcomes |
| Subject Groups (Departments) | **Implemented** | Teacher, Admin | SubjectGroup model |
| Hierarchical Groups | **Implemented** | Teacher, Admin | Groups with parent/children |
| Move Subject to Group | **Implemented** | Teacher, Admin | `/subjects/{id}/move` POST |
| Move Group (reparent) | **Implemented** | Teacher, Admin | `/subjects/groups/{id}/move` POST |
| Drag-and-Drop Organization | **Implemented** | Teacher, Admin | Frontend drag handlers |

### Document Management
| Feature | Status | Roles | Files |
|---------|--------|-------|-------|
| Upload Document | **Implemented** | Teacher, Admin | `/documents/upload` POST |
| Supported Formats | **Implemented** | All | PDF, DOCX, TXT |
| Document Chunking | **Implemented** | Backend | `document_service.py` |
| Vector Embedding | **Implemented** | Backend | `embedding_service.py` |
| OCR for Scanned PDFs | **Implemented** | Backend | pytesseract integration |
| List Documents | **Implemented** | Owner | `/documents` GET |
| Delete Document | **Implemented** | Owner | `/documents/{id}` DELETE |
| View Document Chunks | **Implemented** | Owner | `/documents/{id}/chunks` GET |
| Document Index Types | **Implemented** | Teacher, Admin | `index_type`: primary, reference_book, template_paper |
| Reference Books per Subject | **Implemented** | Teacher, Admin | User.subject_reference_materials |
| Multi-Document Search | **Implemented** | Backend | `hybrid_search_multi_document()` |

### Question Generation
| Feature | Status | Roles | Files |
|---------|--------|-------|-------|
| Quick Generate | **Implemented** | Teacher (can_generate) | `generate_questions()` streaming |
| MCQ Generation | **Implemented** | Teacher (can_generate) | With 4 options |
| Short Answer Generation | **Implemented** | Teacher (can_generate) | 3-5 sentence responses |
| Long Answer/Essay Generation | **Implemented** | Teacher (can_generate) | 2-3 paragraph responses |
| Streaming Progress Updates | **Implemented** | Teacher (can_generate) | SSE streaming response |
| WebSocket Real-time Stats | **Implemented** | All | WebSocket `/ws/stats` |
| Duplicate Detection (Semantic) | **Implemented** | Backend | Similarity threshold 0.987 |
| Novelty Validation | **Implemented** | Backend | `novelty_service.py` |
| Blacklisting Previous Questions | **Implemented** | Backend | Session-level blacklist |
| RAG Retrieval | **Implemented** | Backend | Hybrid search with reranking |
| Bloom's Taxonomy Levels | **Implemented** | Teacher, Admin | remember → create |
| Difficulty Levels | **Implemented** | Teacher, Admin | easy, medium, hard |
| Question Type Distribution | **Implemented** | Teacher, Admin | Percentage per type |
| Focus Topics Filter | **Implemented** | Teacher, Admin | Query expansion for retrieval |
| Generation Session Tracking | **Implemented** | Backend | GenerationSession model |
| Redis Queue for Generations | **Implemented** | Backend | RedisQueueService |
| Generation Locks | **Implemented** | Backend | Per-user/document locking |

### Vetting / Review Workflow
| Feature | Status | Roles | Files |
|---------|--------|-------|-------|
| View Questions to Vet | **Implemented** | Vetter, Teacher (can_vet) | `/vetter/questions` GET |
| Approve Question | **Implemented** | Vetter, Teacher (can_vet) | `/vetter/submit` POST |
| Reject Question | **Implemented** | Vetter, Teacher (can_vet) | With reason codes |
| Edit & Approve | **Implemented** | Vetter, Teacher (can_vet) | Creates DPO pairs |
| Reason Codes (Taxonomy) | **Implemented** | Admin | VettingReasonCode model |
| Quality Score Assignment | **Implemented** | Vetter | 0-1 normalized score |
| Bulk Vetting | **Implemented** | Vetter | `/vetter/bulk-submit` |
| Vetting Progress Persistence | **Implemented** | Vetter, Teacher | localStorage + backend |
| Resume Interrupted Vetting | **Implemented** | Vetter, Teacher | Query params: resume, resume_key |
| Teacher Self-Vetting | **Implemented** | Teacher (can_vet) | Can vet own questions |
| Vetter Dashboard Stats | **Implemented** | Vetter | Pending/approved/rejected counts |
| Subject-based Filtering | **Implemented** | Vetter | Filter by subject/topic |
| Time Spent Tracking | **Implemented** | Frontend | Tracks review duration |

### Training Pipeline (LoRA Fine-tuning)
| Feature | Status | Roles | Files |
|---------|--------|-------|-------|
| SFT Data Export | **Implemented** | Admin | `/training/export/sft` |
| DPO Data Export | **Implemented** | Admin | `/training/export/dpo` |
| Training Pair Generation | **Implemented** | Backend | VettingLog → TrainingPair |
| Synthetic DPO Pairs | **Implemented** | Backend | Fallback when real pairs scarce |
| Trigger Training Job | **Implemented** | Teacher, Admin | `/training/trigger` POST |
| Training Job Monitoring | **Implemented** | All | `/training/jobs` GET |
| Model Version Tracking | **Implemented** | Admin | ModelVersion model |
| Model Activation | **Implemented** | Admin | Activate specific version |
| Training Status Endpoint | **Implemented** | All | `/training/status` GET |
| Dataset Snapshot | **Implemented** | Admin | TrainingDataset model |
| Stratified Sampling | **Implemented** | Backend | Balance by difficulty |
| Sample Size Guardrails | **Implemented** | Backend | max_samples, sample_strategy |
| Training Replay | **Implemented** | Admin | `/training/jobs/{id}/replay` |
| Idempotency Keys | **Implemented** | Backend | Prevent duplicate jobs |

### Evaluation Pipeline
| Feature | Status | Roles | Files |
|---------|--------|-------|-------|
| Automatic Post-Training Eval | **Implemented** | Backend | `run_training_job()` triggers eval |
| Held-out Test Set Evaluation | **Implemented** | Backend | Offline pass rate metrics |
| Quality Gates (8 gates) | **Implemented** | Backend | `_run_quality_gates()` |
| Gate Checks | **Implemented** | Backend | pass/fail per gate |
| Spot Check Sampling | **Implemented** | Backend | Random samples for human review |
| Spot Check Completion | **Implemented** | Admin | POST `/evaluations/{id}/spot-check` |
| Evaluation Listing | **Implemented** | Admin | `/evaluations` GET |
| Promotion Gate Check | **Implemented** | Backend | Requires eval + spot_check_clear |

### Admin Dashboard & Analytics
| Feature | Status | Roles | Files |
|---------|--------|-------|-------|
| System Statistics | **Implemented** | Admin | Total questions, users, etc. |
| User Breakdown | **Implemented** | Admin | Per-user generation/vetting stats |
| Vetter Performance | **Implemented** | Admin | Approved/rejected per vetter |
| Provider Metrics | **Implemented** | Admin | Rejection rates by provider |
| Subject Overview | **Implemented** | Admin | All subjects with counts |
| Teacher Overview | **Implemented** | Admin | Teacher-specific stats |
| Real-time WebSocket Stats | **Implemented** | Admin | Global + subject stats |

### System Settings
| Feature | Status | Roles | Files |
|---------|--------|-------|-------|
| Signup Toggle | **Implemented** | Admin | `/settings/signup` |
| Provider Generation Config | **Implemented** | Admin | Multi-provider setup |
| Generation Limits | **Implemented** | Admin | Batch size per provider |
| System Settings Storage | **Implemented** | Backend | SystemSettings model |

### UI/UX Features
| Feature | Status | Roles | Files |
|---------|--------|-------|-------|
| Glass-morphism Design | **Implemented** | All | Throughout UI |
| Dark/Light Theme | **Implemented** | All | Theme picker, CSS variables |
| Mobile-Responsive | **Implemented** | All | MobileNavBar, responsive CSS |
| PWA Support | **Implemented** | All | manifest.webmanifest, service-worker |
| Desktop Sidebar Navigation | **Implemented** | All | +layout.svelte desktop chrome |
| Voice Recorder (Verify Mode) | **Implemented** | Teacher | VoiceRecorder.svelte |
| File Upload Zone | **Implemented** | Teacher | FileUploadZone.svelte |
| Progress Indicators | **Implemented** | All | ProgressIndicator.svelte |
| Step Cards/Wizard | **Implemented** | All | StepCard.svelte, WorkflowWizard.svelte |

## 6. Workflow Documentation

### Login Flow
1. **Trigger**: User navigates to `/login` or role-specific login (`/teacher/login`, `/vetter/login`, `/admin/login`)
2. **Authentication**: POST `/auth/login` with email/password
3. **Token Storage**: Frontend stores access_token in memory, refresh_token in localStorage
4. **Role-Based Redirect**: On successful login, user redirected to role-appropriate dashboard:
   - Teacher → `/teacher/subjects`
   - Vetter → `/vetter/dashboard`
   - Admin → `/admin/dashboard`
5. **Session Validation**: All protected pages check `session` store and redirect if expired

**Main Files**: `trainer-web/src/lib/session/index.ts`, `AuthForm.svelte`, `+layout.svelte` role redirect

### Teacher Question Generation Workflow
1. **Create Subject**: Teacher creates subject at `/teacher/subjects` (POST `/subjects`)
2. **Create Topic**: Within subject, create topic for syllabus organization
3. **Upload Document**: Upload PDF/DOCX/TXT to topic (POST `/documents/upload`)
   - Document processed into chunks
   - Chunks embedded via nomic-embed-text
4. **Start Generation**: Navigate to `/teacher/train`, select topic
5. **Configure Generation**: Set question count, types (MCQ/short/long), difficulty, focus topics
6. **Generate**: POST to streaming generation endpoint
   - Builds blacklist of existing questions
   - Selects relevant chunks via hybrid search (BM25 + vector similarity)
   - Reranks with cross-encoder if enabled
   - Calls LLM with structured prompt
   - Validates novelty (duplicate check)
   - Saves question with pending status
7. **Self-Vet (Optional)**: Teacher can vet own questions via vetting loop
8. **External Vetter**: Questions appear in vetter queue for review

**Main Files**: `teacher/train/+page.svelte`, `teacher/subjects/[id]/+page.svelte`, `question_service.py`

### Vetter Review Workflow
1. **Dashboard**: Vetter sees `/vetter/dashboard` with pending stats and resume option
2. **Subject Selection**: Navigate to `/vetter/subjects`, select subject/topic
3. **Start Vetting**: Click "Start Vetting" → navigates to `/vetter/loop`
4. **Review Loop**:
   - Fetch batch of pending questions (GET `/vetter/questions`)
   - Display question with source context
   - Vetter chooses: Approve, Reject, or Edit
   - On Approve: Optionally set quality score, CO mapping
   - On Reject: Select reason codes, provide feedback
   - On Edit: Modify question text/options/answer, then approve
5. **Progress Persistence**: Frontend saves state to localStorage on every action
6. **Submit Decision**: POST `/vetter/submit` with decision data
   - Creates VettingLog record
   - Updates Question status
   - If edited, creates TrainingPair for DPO
7. **Resume Support**: Can resume interrupted session via query params

**Main Files**: `vetter/dashboard/+page.svelte`, `vetter/loop/+page.svelte`, `vetter-progress.ts`, `vetter.py`

### Training Pipeline Workflow
1. **Data Accumulation**: As vetting occurs, TrainingPairs created from edits
2. **Trigger Training**: Admin or scheduled job calls POST `/training/trigger`
3. **Data Preparation**:
   - SFT: Export approved questions as instruction-tuning JSONL
   - DPO: Export training pairs as (prompt, chosen, rejected) triplets
   - Synthetic DPO: Generate fallback pairs if real data scarce
4. **Training Job**: 
   - Create ModelVersion record
   - Create TrainingJob record
   - Launch LoRA fine-tuning (unsloth)
5. **Post-Training Evaluation**:
   - Evaluate on held-out test set
   - Run 8 quality gates
   - Select spot-check samples
6. **Spot Check (Human Review)**:
   - Human reviews random sample of approved questions
   - Marks pass/fail for spot check
7. **Promotion Decision**:
   - If eval passes + spot check clear → activate new model
   - Else → keep current active model

**Main Files**: `training_service.py`, `training.py` endpoints, `ModelEvaluation` model

### Admin User Management Workflow
1. **Dashboard**: View system stats at `/admin/dashboard`
2. **User List**: Navigate to `/admin/users` to see all users
3. **Create User**: Click "Add User" → set email, username, password, role
4. **Edit User**: Click user → modify permissions (can_generate, can_vet, can_manage_groups)
5. **Toggle Signup**: Navigate to `/admin/settings` → enable/disable registration
6. **Configure Providers**: Add/edit LLM providers for generation

**Main Files**: `admin/users/+page.svelte`, `admin/settings/+page.svelte`, `admin.py`

## 7. Routes, Pages, and Screens

### Public Routes
| Route | Purpose | Auth Required |
|-------|---------|---------------|
| `/` | Landing with role-based redirect | No (redirects if logged in) |
| `/login` | Generic login page | No |
| `/teacher/login` | Teacher login | No |
| `/vetter/login` | Vetter login | No |
| `/admin/login` | Admin login | No |
| `/privacy-policy` | Privacy policy | No |
| `/disclaimer` | Disclaimer | No |

### Teacher Routes (requires teacher role)
| Route | Purpose |
|-------|---------|
| `/teacher/dashboard` | Mode selection home |
| `/teacher/subjects` | Subject list with group management |
| `/teacher/subjects/new` | Create new subject |
| `/teacher/subjects/[id]` | Subject detail, topic management |
| `/teacher/train` | Vetting/train landing (existing/new topics) |
| `/teacher/train/existing` | Select existing topic for vetting |
| `/teacher/train/loop` | Loop vetting interface with progress |
| `/teacher/stats` | Personal statistics |
| `/teacher/verify` | Voice verification mode |
| `/teacher/ops` | AI Ops status |
| `/teacher/profile` | User profile |

### Vetter Routes (requires vetter role or can_vet permission)
| Route | Purpose |
|-------|---------|
| `/vetter/dashboard` | Dashboard with stats and resume |
| `/vetter/subjects` | Subject selection for vetting |
| `/vetter/loop` | Vetting loop interface |
| `/vetter/profile` | User profile |

### Admin Routes (requires admin role)
| Route | Purpose |
|-------|---------|
| `/admin/dashboard` | System statistics |
| `/admin/users` | User management CRUD |
| `/admin/teachers` | Teacher overview |
| `/admin/vetters` | Vetter overview |
| `/admin/subjects` | All subjects view |
| `/admin/settings` | System settings |
| `/admin/profile` | User profile |
| `/admin/ops` | AI Ops status |

## 8. APIs, Services, and Data Models

### Main API Endpoints

**Authentication** (`/api/v1/auth/*`)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/register` | POST | Create new account |
| `/login` | POST | Authenticate, get tokens |
| `/refresh` | POST | Refresh access token |
| `/logout` | POST | Logout current session |
| `/logout-all` | POST | Logout all devices |
| `/me` | GET | Get current user |
| `/update-profile` | PUT | Update profile |
| `/upload-avatar` | POST | Upload avatar image |
| `/avatar` | DELETE | Remove avatar |
| `/change-password` | POST | Change password |
| `/sessions` | GET | List active sessions |

**Questions** (`/api/v1/questions/*`)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/generate` | POST | Stream question generation (SSE) |
| `/quick-generate` | POST | Quick generate with status |
| `/quick-generate/status/{id}` | GET | Check quick generate status |
| `/background-generate` | POST | Background generation |
| `/background-status/{user_id}/{subject_id}` | GET | Check background status |
| `/cancel-background/{user_id}/{subject_id}` | POST | Cancel background generation |
| `/queue-position/{user_id}/{subject_id}` | GET | Get queue position |
| `/submit` | POST | Submit vetting decision |
| `/bulk-submit` | POST | Bulk vetting decisions |

**Subjects** (`/api/v1/subjects/*`)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | List subjects (paginated) |
| `/` | POST | Create subject |
| `/tree` | GET | Get hierarchical tree |
| `/{id}` | GET | Get subject detail |
| `/{id}` | PUT | Update subject |
| `/{id}` | DELETE | Delete subject |
| `/{id}/topics` | POST | Create topic |
| `/{id}/topics/{tid}` | PUT | Update topic |
| `/{id}/topics/{tid}` | DELETE | Delete topic |
| `/{id}/move` | POST | Move subject to group |

**Documents** (`/api/v1/documents/*`)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/upload` | POST | Upload document |
| `/` | GET | List documents |
| `/{id}` | GET | Get document detail |
| `/{id}` | DELETE | Delete document |
| `/{id}/chunks` | GET | View document chunks |

**Vetter** (`/api/v1/vetter/*`)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/dashboard` | GET | Get vetter dashboard stats |
| `/subjects` | GET | List subjects with pending counts |
| `/questions` | GET | Get questions for vetting |
| `/submit` | POST | Submit vetting decision |
| `/bulk-submit` | POST | Bulk vetting |
| `/reason-codes` | GET | List reason codes |
| `/reason-codes` | POST | Create reason code (admin) |

**Training** (`/api/v1/training/*`)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/status` | GET | Get pipeline status |
| `/trigger` | POST | Trigger training run |
| `/versions` | GET | List model versions |
| `/versions/{id}/activate` | POST | Activate model version |
| `/jobs` | GET | List training jobs |
| `/jobs/{id}` | GET | Get job details |
| `/jobs/{id}/replay` | POST | Replay job with idempotency |
| `/pairs` | GET | List DPO training pairs |
| `/export/sft` | GET | Export SFT data |
| `/export/dpo` | GET | Export DPO data |
| `/datasets` | GET | List dataset snapshots |
| `/evaluations` | GET | List evaluations |
| `/evaluations/{id}` | GET | Get evaluation |
| `/evaluations/{id}/spot-check` | POST | Complete spot check |

**Admin** (`/api/v1/admin/*`)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/dashboard` | GET | Get admin dashboard |
| `/users` | GET | List all users |
| `/users` | POST | Create user |
| `/users/{id}` | PUT | Update user |
| `/users/{id}` | DELETE | Delete user |
| `/subjects` | GET | List all subjects |
| `/subjects/{id}` | GET | Get subject detail |
| `/teachers` | GET | List teacher stats |
| `/vetters` | GET | List vetter stats |
| `/provider-metrics` | GET | Get provider metrics |

**Settings** (`/api/v1/settings/*`)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/signup` | GET | Get signup enabled status |
| `/signup` | PUT | Toggle signup (admin) |
| `/providers-generation` | GET | Get provider config (admin) |
| `/providers-generation` | PUT | Update providers (admin) |
| `/generation-limits` | GET | Get batch size limits |

**WebSocket** (`/api/v1/ws/*`)
| Endpoint | Description |
|----------|-------------|
| `/stats` | WebSocket for real-time stats updates |

### Core Services

| Service | Responsibility | Key File |
|---------|----------------|----------|
| QuestionGenerationService | RAG pipeline, question generation | `question_service.py` |
| TrainingService | SFT/DPO export, LoRA training | `training_service.py` |
| DocumentService | Upload, chunking, OCR, search | `document_service.py` |
| EmbeddingService | Text embedding, similarity | `embedding_service.py` |
| NoveltyService | Duplicate detection | `novelty_service.py` |
| VettingService | Review workflow logic | `vetting_service.py` |
| LLMService | LLM provider abstraction | `llm_service.py` |
| DeepseekService | DeepSeek API integration | `deepseek_service.py` |
| GeminiService | Google Gemini integration | `gemini_service.py` |
| ProviderService | Multi-provider management | `provider_service.py` |
| RedisService | Caching, locks, rate limiting | `redis_service.py` |
| UserService | User CRUD, authentication | `user_service.py` |
| QueueService | Training job queuing | `queue_service.py` |
| StatsBroadcastService | WebSocket stats broadcasting | `stats_broadcast_service.py` |

### Data Models

**Auth Database (SQLite)**
| Model | Table | Purpose |
|-------|-------|---------|
| User | users | User accounts, roles, permissions |
| RefreshToken | refresh_tokens | Session tokens |
| AuditLog | audit_logs | Security audit trail |
| SystemSettings | system_settings | System configuration |

**Main Database (PostgreSQL with pgvector)**
| Model | Table | Purpose |
|-------|-------|---------|
| Subject | subjects | Courses with code/name |
| Topic | topics | Chapters within subjects |
| SubjectGroup | subject_groups | Hierarchical departments |
| Document | documents | Uploaded files |
| DocumentChunk | document_chunks | RAG chunks with embeddings |
| Question | questions | Generated questions with embeddings |
| GenerationSession | generation_sessions | Generation job tracking |
| VettingLog | vetting_logs | Detailed vetting records |
| TrainingPair | training_pairs | DPO (chosen/rejected) pairs |
| ModelVersion | model_versions | LoRA adapter versions |
| TrainingJob | training_jobs | Fine-tuning job runs |
| TrainingDataset | training_datasets | Immutable dataset snapshots |
| ModelEvaluation | model_evaluations | Evaluation results |
| VettingReasonCode | vetting_reason_codes | Controlled taxonomy |
| TeacherVettingProgress | teacher_vetting_progress | Progress tracking |

## 9. Config, Environment, and Deployment Signals

### Key Config Files
| File | Purpose |
|------|---------|
| `.env.defaults` | Default configuration values |
| `.env.local` | Local overrides (gitignored) |
| `backend/app/core/config.py` | Pydantic Settings class |
| `docker-compose.yml` | Docker services orchestration |
| `trainer-web/svelte.config.js` | SvelteKit configuration |
| `trainer-web/vite.config.ts` | Vite build configuration |

### Important Environment Variables

**Database**
- `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`
- `AUTH_DATABASE_URL` - SQLite auth DB path

**LLM Providers**
- `LLM_PROVIDER` - "deepseek" (default), "gemini", or "ollama"
- `DEEPSEEK_API_KEY`, `DEEPSEEK_MODEL`
- `GEMINI_API_KEY`, `GEMINI_MODEL`
- `OLLAMA_BASE_URL`, `OLLAMA_MODEL`

**Training**
- `TRAINING_BASE_MODEL` - Base model for LoRA (default: deepseek-ai/DeepSeek-R1-Distill-Llama-1.7B)
- `TRAINING_DATA_DIR` - SFT/DPO export path
- `LORA_ADAPTERS_DIR` - LoRA checkpoint path
- `DEFAULT_MAX_SFT_SAMPLES`, `DEFAULT_MAX_DPO_SAMPLES`
- `DEFAULT_SAMPLE_STRATEGY` - "recent_first", "stratified", "random"
- `SYNTHETIC_DPO_MIN_CONFIDENCE` - Threshold for synthetic pairs
- `SYNTHETIC_DPO_PAIR_WEIGHT` - Weight for synthetic pairs

**Redis**
- `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB`, `REDIS_PASSWORD`

**Features**
- `AUTO_TRAINING_ENABLED` - Daily scheduled training
- `AUTO_TRAINING_HOUR`, `AUTO_TRAINING_MINUTE` - Schedule time
- `RERANKER_ENABLED` - Enable cross-encoder reranking
- `OCR_ENABLED` - Enable PDF OCR for scanned documents
- `ENABLE_METRICS` - Enable Prometheus metrics

**Security**
- `SECRET_KEY` - JWT signing key
- `ACCESS_TOKEN_EXPIRE_MINUTES` - Default: 60
- `REFRESH_TOKEN_EXPIRE_DAYS` - Default: 30
- `CORS_ORIGINS` - Allowed origins (default: "*")

### Deployment Signals

**Docker Compose Services**:
- `backend` - FastAPI application
- `frontend` - SvelteKit (via Caddy or nginx)
- `postgres` - PostgreSQL 15 with pgvector
- `redis` - Redis for caching/queues
- `ollama` - Optional local LLM inference

**PM2 Configuration** (`ecosystem.config.js`):
- Backend on port 8000
- Frontend (Caddy) on port 3000

**Build Commands**:
- Backend: `uvicorn app.main:app --host 0.0.0.0 --port 8000`
- Frontend: `npm run build` (produces static SPA)

## 10. Tests and Coverage Signals

### Test Locations
The project does not appear to have a dedicated test directory in the current file structure. Testing appears to be done via:

1. **Postman Collections**: `postman/QGen_RAG_API.postman_collection.json`
2. **Manual Testing**: Via the trainer-web UI
3. **Scripts**: `backend/scripts/` contains utility scripts for database checks

### Untested Areas (Inferred)
Based on codebase analysis, the following areas may have limited automated test coverage:
- Training pipeline execution (relies on manual triggering and monitoring)
- LLM provider integrations (mocked or manual)
- WebSocket real-time functionality
- OCR processing for scanned PDFs
- LoRA fine-tuning orchestration

## 11. Gaps and Observations

### Fully Implemented Features
- Complete authentication system with JWT and refresh tokens
- Subject/topic hierarchy with drag-and-drop organization
- Document upload with chunking and vector embedding
- RAG-based question generation with hybrid search
- Comprehensive vetting workflow with progress persistence
- Training pipeline with SFT/DPO and LoRA fine-tuning
- Multi-provider LLM support (DeepSeek, Gemini, Ollama)
- Admin dashboard with user management
- WebSocket real-time statistics
- Dark/light theme system
- Mobile-responsive PWA interface

### Partial Implementations / Placeholder Features
| Feature | Status | Notes |
|---------|--------|-------|
| A/B Testing | **Placeholder** | Route exists (`/teacher/ab-test`) but commented in navigation |
| Voice Verification | **Partial** | Page exists but not linked in nav; VoiceRecorder component implemented |
| Student Features | **Not Present** | No student role or student-facing routes found |
| Quiz/Taking Mode | **Not Present** | No evidence of quiz delivery or student testing interface |
| Export to External Formats | **Unclear** | No explicit export endpoints for QTI, Moodle, etc. |
| Bulk Import Questions | **Not Present** | No evidence of CSV/question import functionality |

### Configuration vs. Wiring
| Config | Wired? | Notes |
|--------|--------|-------|
| `TRAINING_BASE_MODEL` | Partial | Config exists but training execution is complex |
| `AUTO_TRAINING_ENABLED` | Likely | Config exists, scheduled jobs referenced |
| `RERANKER_ENABLED` | Yes | Checked in question generation |
| `OCR_ENABLED` | Yes | Checked in document processing |
| `ENABLE_METRICS` | Yes | Prometheus instrumentator setup |
| `GEMINI_SAFETY_BLOCK_NONE` | Yes | Passed to Gemini client |

### Architecture Observations
1. **Dual Database**: Clean separation of auth (SQLite) from vector/RAG data (PostgreSQL) - good design
2. **Redis Usage**: Heavy reliance on Redis for caching, queues, and pub/sub - Redis is required for full functionality
3. **Async Throughout**: Proper async/await usage in backend
4. **Provider Abstraction**: Good abstraction for multiple LLM providers
5. **Progress Persistence**: Both frontend (localStorage) and backend (database) persistence for vetting

### Technical Debt Signals
1. **Commented Code**: Some features (A/B testing) are commented out rather than removed
2. **Complex Training Service**: `training_service.py` is large (2752 lines) and complex
3. **Frontend Vetters vs Teachers**: Some overlap in vetting functionality between roles may need consolidation
4. **WebSocket Manager**: Separate from main app - may need better integration

### Naming Inconsistencies
- Product referred to as both "VQuest" and "VQuest Trainer" in UI
- Some files use "vetting" prefix, others use "vetter" prefix
- Training vs Fine-tuning terminology may be used interchangeably

### Risk Areas
1. **Training Pipeline**: Complex LoRA fine-tuning with external dependencies
2. **OCR Dependencies**: Requires tesseract installation
3. **Redis Dependency**: System degrades without Redis but may have edge cases
4. **LLM API Costs**: DeepSeek/Gemini API usage needs monitoring
5. **File Storage**: Local filesystem storage may need S3 for production scale

## 12. File Reference Appendix

### Backend Core
| File | Description |
|------|-------------|
| `backend/app/main.py` | FastAPI application factory |
| `backend/app/api/v1/router.py` | API route assembly |
| `backend/app/api/v1/deps.py` | Auth dependencies, RBAC |
| `backend/app/core/config.py` | Environment configuration |
| `backend/app/core/database.py` | PostgreSQL connection |
| `backend/app/core/auth_database.py` | SQLite auth connection |
| `backend/app/core/security.py` | Password hashing, JWT |

### Backend Models
| File | Description |
|------|-------------|
| `backend/app/models/user.py` | User, roles, permissions |
| `backend/app/models/question.py` | Question, GenerationSession |
| `backend/app/models/document.py` | Document, DocumentChunk |
| `backend/app/models/subject.py` | Subject, Topic, SubjectGroup |
| `backend/app/models/training.py` | TrainingJob, ModelVersion, VettingLog, TrainingPair, ModelEvaluation |
| `backend/app/models/vetting_progress.py` | TeacherVettingProgress |
| `backend/app/models/system_settings.py` | SystemSettings |

### Backend Services
| File | Description |
|------|-------------|
| `backend/app/services/question_service.py` | RAG question generation |
| `backend/app/services/training_service.py` | LoRA fine-tuning pipeline |
| `backend/app/services/document_service.py` | Document processing |
| `backend/app/services/embedding_service.py` | Vector embeddings |
| `backend/app/services/novelty_service.py` | Duplicate detection |
| `backend/app/services/llm_service.py` | LLM abstraction |
| `backend/app/services/provider_service.py` | Multi-provider management |
| `backend/app/services/redis_service.py` | Redis caching |
| `backend/app/services/user_service.py` | User management |

### Backend Endpoints
| File | Description |
|------|-------------|
| `backend/app/api/v1/endpoints/auth.py` | Authentication |
| `backend/app/api/v1/endpoints/admin.py` | Admin dashboard |
| `backend/app/api/v1/endpoints/questions.py` | Question generation |
| `backend/app/api/v1/endpoints/vetter.py` | Vetting workflow |
| `backend/app/api/v1/endpoints/training.py` | Training pipeline |
| `backend/app/api/v1/endpoints/subjects.py` | Subject management |
| `backend/app/api/v1/endpoints/documents.py` | Document management |
| `backend/app/api/v1/endpoints/settings.py` | System settings |
| `backend/app/api/v1/endpoints/websocket.py` | WebSocket |

### Frontend Core
| File | Description |
|------|-------------|
| `trainer-web/src/routes/+layout.svelte` | Main layout, navigation, theming |
| `trainer-web/src/routes/+page.svelte` | Landing page |
| `trainer-web/src/lib/session/index.ts` | Auth session store |

### Frontend Teacher
| File | Description |
|------|-------------|
| `trainer-web/src/routes/teacher/dashboard/+page.svelte` | Teacher home |
| `trainer-web/src/routes/teacher/subjects/+page.svelte` | Subject management |
| `trainer-web/src/routes/teacher/subjects/[id]/+page.svelte` | Subject detail |
| `trainer-web/src/routes/teacher/train/+page.svelte` | Train interface |
| `trainer-web/src/routes/teacher/train/loop/+page.svelte` | Loop vetting |

### Frontend Vetter
| File | Description |
|------|-------------|
| `trainer-web/src/routes/vetter/dashboard/+page.svelte` | Vetter home |
| `trainer-web/src/routes/vetter/loop/+page.svelte` | Vetting loop |

### Frontend Admin
| File | Description |
|------|-------------|
| `trainer-web/src/routes/admin/dashboard/+page.svelte` | Admin dashboard |
| `trainer-web/src/routes/admin/users/+page.svelte` | User management |
| `trainer-web/src/routes/admin/settings/+page.svelte` | System settings |

### Frontend Libraries
| File | Description |
|------|-------------|
| `trainer-web/src/lib/api/client.ts` | HTTP client |
| `trainer-web/src/lib/api/auth.ts` | Auth API |
| `trainer-web/src/lib/api/subjects.ts` | Subjects API |
| `trainer-web/src/lib/api/vetting.ts` | Vetting API |
| `trainer-web/src/lib/api/training.ts` | Training API |
| `trainer-web/src/lib/api/generation-websocket.ts` | WebSocket client |
| `trainer-web/src/lib/vetting-progress.ts` | Vetting progress persistence |
| `trainer-web/src/lib/vetter-progress.ts` | Vetter progress store |

### Frontend Components
| File | Description |
|------|-------------|
| `trainer-web/src/lib/components/AuthForm.svelte` | Login form |
| `trainer-web/src/lib/components/MobileNavBar.svelte` | Mobile navigation |
| `trainer-web/src/lib/components/ThemePicker.svelte` | Theme selector |
| `trainer-web/src/lib/components/FileUploadZone.svelte` | Document upload |
| `trainer-web/src/lib/components/VoiceRecorder.svelte` | Voice capture |
| `trainer-web/src/lib/components/WorkflowWizard.svelte` | Step wizard |

---

**Documentation Confidence Level**: **High**

This documentation is based on comprehensive code analysis of:
- All backend API endpoints and models
- All frontend routes and components
- Service layer implementations
- Database schema definitions
- Configuration and environment files

**Areas Needing Manual Verification**:
1. Actual training pipeline execution (LoRA fine-tuning) - requires GPU environment
2. OCR functionality - requires tesseract installation
3. WebSocket real-time updates - requires Redis running
4. Some commented features (A/B testing, voice verification) - verify if production-ready
5. Provider-specific behavior differences (DeepSeek vs Gemini vs Ollama)
