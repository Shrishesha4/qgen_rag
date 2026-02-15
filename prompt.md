# Complete AI Agent Prompt: Stateful RAG Question Generation System with Multi-User Authentication

## AI Agent Identity & Core Mission

You are **QuestionGeneration AI**, a specialized utility for professors and educators to generate high-quality examination questions from uploaded PDF documents. Your primary purpose is to generate 'n' number of questions based on specific topics, question types (MCQs, short/long answers), and marks distribution, while maintaining complete privacy and offline capability.

**Core Principles:**
- **Utility Focus**: This is NOT a learning app for students; it is a productivity tool for educators
- **Custom RAG Implementation**: Generate precise questions based on document content
- **Configurable Generation**: Support specific question types, marks, and topic focus
- **Statefulness**: Maintain history of generated questions to avoid duplicates
- **User Isolation**: Complete data separation between users
- **Privacy Guarantee**: All processing happens locally or on a private server—no data sharing
- **No Subscriptions/Payments**: This is a private utility tool, not a commercial SaaS product

---

## System Architecture Overview

### Four-Tier Architecture with Auth Layer

**Tier 0: Authentication & Authorization Layer**
- User registration and login management
- JWT token generation and validation
- Session tracking and refresh token handling
- Password hashing and security
- Rate limiting and abuse prevention
- OAuth2 integration (optional)

**Tier 1: Mobile Client (React Native/Expo)**
- User authentication flow (signup/login/logout)
- Secure token storage and management
- Biometric authentication (fingerprint/face ID)
- Document upload and management (user-scoped)
- Question display and response collection
- Progress tracking and analytics dashboard
- Offline-first design with local caching
- Auto-refresh token handling

**Tier 2: Backend API (FastAPI)**
- Protected endpoints with JWT middleware
- User-scoped data access control
- Session management and state tracking
- Request validation and rate limiting
- Streaming response handler for real-time generation
- Background job processor for heavy tasks
- Audit logging for security events

**Tier 3: AI Processing Layer (Local LLM + Vector Store)**
- User-isolated vector collections
- Document parsing and chunking (per-user)
- Embedding generation and similarity search
- Question generation with context injection
- Quality validation and deduplication
- Semantic analysis and clustering

---

## Complete Tech Stack Specification

### Frontend Layer
- **Framework**: React Native 0.74+ with Expo 51+
- **State Management**: Zustand with persist middleware (auth state)
- **Authentication**:
  - expo-secure-store (encrypted token storage)
  - expo-local-authentication (biometrics)
  - @react-native-async-storage/async-storage (user preferences)
- **Navigation**: React Navigation 6+ with auth flow guards
- **File Handling**: expo-document-picker + expo-file-system
- **UI Components**: React Native Paper or NativeBase
- **Networking**: Axios with JWT interceptors + React Query
- **Real-time**: EventSource (SSE) with auth headers
- **Local Storage**: expo-sqlite with user_id scoping
- **Form Validation**: React Hook Form + Zod schemas

### Backend Layer
- **API Framework**: FastAPI 0.110+ with Pydantic v2
- **Authentication**:
  - python-jose (JWT encoding/decoding)
  - passlib with bcrypt (password hashing)
  - python-multipart (form data handling)
  - fastapi-users (optional, full auth system)
- **Security**:
  - fastapi-limiter (rate limiting)
  - python-dotenv (secrets management)
  - cryptography (encryption utilities)
- **Async Runtime**: Uvicorn with Gunicorn for production
- **Task Queue**: Celery with Redis broker
- **Session Management**: Redis (TTL-based sessions + blacklist)
- **API Documentation**: Auto-generated via FastAPI's OpenAPI with auth
- **Monitoring**: Prometheus + Grafana for metrics
- **Logging**: Structlog with JSON output + audit trail

### AI/ML Layer
*(Same as before, but with user isolation in vector collections)*
- **LLM Inference**: Ollama with per-user request tracking
- **Vector Database**: ChromaDB with collections per user: `user_{user_id}_docs`
- **Document Processing**: PyMuPDF, Docling (with user_id tagging)

### Database Layer
- **Primary Database**: PostgreSQL 16+ with pgvector extension
- **Row-Level Security (RLS)**: Enforce user isolation at database level
- **Cache Layer**: Redis 7+ (sessions, tokens, rate limits)
- **Migration Tool**: Alembic (SQLAlchemy-based)

### Infrastructure & DevOps
- **Secrets Management**: HashiCorp Vault or AWS Secrets Manager
- **SSL/TLS**: Let's Encrypt certificates (for production)
- **Reverse Proxy**: Nginx with HTTPS enforcement
- **Containerization**: Docker + Docker Compose
- **Model Serving**: Ollama container (shared across users with tracking)

---

## Docker Development Environment

### Unified Service Stack
Deploy the entire backend infrastructure with a single command using Docker Compose. This ensures environment consistency across all developer machines.

**`docker-compose.yml` Configuration:**

```yaml
version: '3.8'

services:
  # Database Service
  db:
    image: pgvector/pgvector:pg16
    container_name: qgen_db
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-user}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-password}
      POSTGRES_DB: ${POSTGRES_DB:-qgen_db}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    networks:
      - qgen_net
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U user -d qgen_db"]
      interval: 10s
      timeout: 5s
      retries: 5

  # Cache & Session Store
  redis:
    image: redis:7-alpine
    container_name: qgen_redis
    volumes:
      - redis_data:/data
    ports:
      - "6379:6379"
    networks:
      - qgen_net
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  # AI Model Serving (Ollama)
  ollama:
    image: ollama/ollama:latest
    container_name: qgen_ollama
    volumes:
      - ollama_data:/root/.ollama
    ports:
      - "11434:11434"
    networks:
      - qgen_net
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

  # Backend API (FastAPI)
  api:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: qgen_api
    command: uvicorn main:app --host 0.0.0.0 --port 8000 --reload
    volumes:
      - ./backend:/app  # Hot-reload mapping
    environment:
      DATABASE_URL: postgresql://user:password@db:5432/qgen_db
      REDIS_URL: redis://redis:6379/0
      OLLAMA_BASE_URL: http://ollama:11434
    ports:
      - "8000:8000"
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
      ollama:
        condition: service_started
    networks:
      - qgen_net

volumes:
  postgres_data:
  redis_data:
  ollama_data:

networks:
  qgen_net:
```

### Development Workflow
1.  **Start Services**: `docker-compose up -d`
2.  **Pull Model**: `docker exec -it qgen_ollama ollama pull llama3`
3.  **Access Docs**: Navigate to `http://localhost:8000/docs`
4.  **Database Access**: Connect via `localhost:5432`

---

## Complete Database Schema Design

### PostgreSQL Schema with Authentication

```sql
-- ============================================
-- USERS TABLE (Core Authentication)
-- ============================================
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(50) UNIQUE NOT NULL,
    
    -- Authentication
    password_hash VARCHAR(255) NOT NULL,  -- bcrypt hash
    is_active BOOLEAN DEFAULT TRUE,
    is_superuser BOOLEAN DEFAULT FALSE,
    
    -- Profile
    full_name VARCHAR(255),
    avatar_url VARCHAR(500),
    timezone VARCHAR(50) DEFAULT 'UTC',
    language VARCHAR(10) DEFAULT 'en',
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    last_login_at TIMESTAMP,
    
    -- Security
    failed_login_attempts INTEGER DEFAULT 0,
    locked_until TIMESTAMP,
    password_changed_at TIMESTAMP DEFAULT NOW(),
    
    -- Preferences
    preferences JSONB DEFAULT '{}',  -- Theme, notification settings, etc.
    
    INDEX idx_email (email),
    INDEX idx_username (username),
    INDEX idx_active_users (is_active, created_at DESC)
);

-- ============================================
-- REFRESH TOKENS TABLE (Session Management)
-- ============================================
CREATE TABLE refresh_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(255) NOT NULL UNIQUE,  -- SHA-256 hash of token
    
    -- Device tracking
    device_id VARCHAR(255),  -- Unique device identifier
    device_name VARCHAR(100),  -- "iPhone 14 Pro"
    device_type VARCHAR(20),  -- mobile|tablet|desktop
    
    -- Network info
    ip_address INET,
    user_agent TEXT,
    
    -- Token lifecycle
    issued_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL,
    last_used_at TIMESTAMP DEFAULT NOW(),
    revoked_at TIMESTAMP,
    is_revoked BOOLEAN DEFAULT FALSE,
    
    INDEX idx_user_tokens (user_id, is_revoked, expires_at),
    INDEX idx_token_hash (token_hash),
    INDEX idx_expires_at (expires_at)  -- Cleanup expired tokens
);



-- ============================================
-- AUDIT LOG TABLE (Security Events)
-- ============================================
CREATE TABLE audit_log (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    
    -- Event details
    event_type VARCHAR(50) NOT NULL,  -- login|logout|password_change|document_upload|etc.
    event_category VARCHAR(20),  -- auth|data|security|system
    severity VARCHAR(20) DEFAULT 'info',  -- info|warning|error|critical
    
    -- Context
    ip_address INET,
    user_agent TEXT,
    device_id VARCHAR(255),
    endpoint VARCHAR(255),
    http_method VARCHAR(10),
    
    -- Details
    event_data JSONB,  -- Flexible metadata
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT,
    
    -- Timestamp
    timestamp TIMESTAMP DEFAULT NOW(),
    
    INDEX idx_user_audit (user_id, timestamp DESC),
    INDEX idx_event_type (event_type, timestamp DESC),
    INDEX idx_timestamp (timestamp DESC),
    INDEX idx_severity (severity, timestamp DESC)
);

-- ============================================
-- USER SESSIONS TABLE (Optional: Active Session Tracking)
-- ============================================
CREATE TABLE user_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_token_hash VARCHAR(255) NOT NULL UNIQUE,
    
    -- Session info
    started_at TIMESTAMP DEFAULT NOW(),
    last_activity_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    
    -- Device tracking
    device_id VARCHAR(255),
    device_name VARCHAR(100),
    ip_address INET,
    
    INDEX idx_user_sessions (user_id, is_active),
    INDEX idx_expires_at (expires_at)
);

-- ============================================
-- OAUTH ACCOUNTS TABLE (Optional: Social Login)
-- ============================================
CREATE TABLE oauth_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- OAuth provider
    provider VARCHAR(50) NOT NULL,  -- google|github|apple|facebook
    provider_user_id VARCHAR(255) NOT NULL,
    
    -- Tokens
    access_token TEXT,
    refresh_token TEXT,
    token_expires_at TIMESTAMP,
    
    -- Profile data
    provider_email VARCHAR(255),
    provider_username VARCHAR(100),
    provider_data JSONB,
    
    -- Timestamps
    linked_at TIMESTAMP DEFAULT NOW(),
    last_used_at TIMESTAMP,
    
    UNIQUE (provider, provider_user_id),
    INDEX idx_user_oauth (user_id, provider)
);

-- ============================================
-- DOCUMENTS TABLE (Now User-Scoped)
-- ============================================
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,  -- NEW: User isolation
    
    filename VARCHAR(255) NOT NULL,
    file_hash SHA256 NOT NULL,  -- Not unique anymore (users can upload same file)
    file_size_bytes BIGINT NOT NULL,
    mime_type VARCHAR(100),
    
    -- Storage
    storage_path VARCHAR(500) NOT NULL,  -- Path includes user_id
    
    -- Processing
    upload_timestamp TIMESTAMP DEFAULT NOW(),
    processing_status VARCHAR(20) DEFAULT 'pending',
    total_chunks INTEGER,
    total_tokens INTEGER,
    
    -- Metadata
    document_metadata JSONB,
    
    -- Sharing (optional feature)
    is_public BOOLEAN DEFAULT FALSE,
    share_token VARCHAR(100) UNIQUE,  -- For sharing with others
    
    INDEX idx_user_documents (user_id, upload_timestamp DESC),
    INDEX idx_file_hash_user (file_hash, user_id),  -- User-specific deduplication
    INDEX idx_share_token (share_token)
);

-- Enable Row-Level Security for user isolation
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;

CREATE POLICY documents_isolation_policy ON documents
    USING (user_id = current_setting('app.current_user_id')::UUID);

-- ============================================
-- DOCUMENT CHUNKS TABLE (User-Scoped via FK)
-- ============================================
CREATE TABLE document_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    chunk_text TEXT NOT NULL,
    chunk_embedding VECTOR(384),
    token_count INTEGER,
    page_number INTEGER,
    section_heading VARCHAR(500),
    chunk_metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    
    INDEX idx_document_chunks (document_id, chunk_index),
    INDEX idx_chunk_embedding USING ivfflat (chunk_embedding vector_cosine_ops)
);

-- ============================================
-- QUESTIONS TABLE (User-Scoped via FK)
-- ============================================
CREATE TABLE questions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    session_id UUID,
    
    question_text TEXT NOT NULL,
    question_embedding VECTOR(384),
    
    -- Classification
    question_type VARCHAR(50),  -- mcq|short_answer|long_answer
    marks INTEGER,              -- Marks assigned to this question
    difficulty_level VARCHAR(20),
    bloom_taxonomy_level VARCHAR(30),
    
    -- Context
    source_chunk_ids UUID[],
    topic_tags TEXT[],
    
    -- Quality
    answerability_score FLOAT CHECK (answerability_score BETWEEN 0 AND 1),
    specificity_score FLOAT CHECK (specificity_score BETWEEN 0 AND 1),
    generation_confidence FLOAT,
    
    -- User interaction
    times_shown INTEGER DEFAULT 0,
    user_rating INTEGER CHECK (user_rating BETWEEN 1 AND 5),
    user_difficulty_rating VARCHAR(20),
    user_answer TEXT,
    answer_correctness BOOLEAN,
    
    -- Metadata
    generated_at TIMESTAMP DEFAULT NOW(),
    last_shown_at TIMESTAMP,
    is_archived BOOLEAN DEFAULT FALSE,
    generation_metadata JSONB,
    
    INDEX idx_document_questions (document_id, generated_at DESC),
    INDEX idx_session_questions (session_id),
    INDEX idx_question_embedding USING ivfflat (question_embedding vector_cosine_ops),
    INDEX idx_question_type (question_type, difficulty_level)
);

-- ============================================
-- GENERATION SESSIONS TABLE (User-Scoped)
-- ============================================
CREATE TABLE generation_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,  -- Direct user reference
    
    -- Request parameters
    requested_count INTEGER NOT NULL,
    requested_types TEXT[],
    requested_marks INTEGER,    -- Target total marks or marks per question configuration
    requested_difficulty VARCHAR(20),
    focus_topics TEXT[],
    
    -- Generation tracking
    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    status VARCHAR(20) DEFAULT 'in_progress',
    
    -- Results
    questions_generated INTEGER DEFAULT 0,
    questions_failed INTEGER DEFAULT 0,
    questions_duplicate INTEGER DEFAULT 0,
    
    -- Performance
    total_duration_seconds FLOAT,
    llm_calls INTEGER,
    tokens_used INTEGER,
    
    -- Context
    blacklist_size INTEGER,
    chunks_used INTEGER,
    
    error_message TEXT,
    generation_config JSONB,
    
    INDEX idx_user_sessions (user_id, started_at DESC),
    INDEX idx_document_sessions (document_id, started_at DESC)
);

-- ============================================
-- USER PROGRESS TABLE (Already User-Scoped)
-- ============================================
CREATE TABLE user_progress (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    
    -- Coverage metrics
    chunks_covered UUID[],
    coverage_percentage FLOAT,
    topics_covered TEXT[],
    topics_remaining TEXT[],
    
    -- Performance metrics
    total_questions_seen INTEGER DEFAULT 0,
    correct_answers INTEGER DEFAULT 0,
    average_difficulty_rating FLOAT,
    
    -- Adaptive learning
    weak_topics TEXT[],
    strong_topics TEXT[],
    recommended_focus_areas TEXT[],
    
    last_updated TIMESTAMP DEFAULT NOW(),
    
    UNIQUE (user_id, document_id),
    INDEX idx_user_progress (user_id)
);

-- ============================================
-- RATE LIMIT TRACKING TABLE
-- ============================================
CREATE TABLE rate_limits (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    
    -- Limit tracking
    endpoint VARCHAR(255),
    window_start TIMESTAMP NOT NULL,
    request_count INTEGER DEFAULT 1,
    
    -- Abuse detection
    violations_count INTEGER DEFAULT 0,
    
    INDEX idx_user_rate_limit (user_id, endpoint, window_start),
    INDEX idx_window_cleanup (window_start)  -- Cleanup old records
);

-- ============================================
-- INVITATIONS TABLE (Optional: Team Feature)
-- ============================================
CREATE TABLE invitations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    inviter_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    email VARCHAR(255) NOT NULL,
    token_hash VARCHAR(255) NOT NULL UNIQUE,
    
    -- Invitation details
    role VARCHAR(20) DEFAULT 'member',  -- admin|member|viewer
    message TEXT,
    
    -- Status
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL,
    accepted_at TIMESTAMP,
    accepted_by_user_id UUID REFERENCES users(id),
    
    INDEX idx_inviter (inviter_id, created_at DESC),
    INDEX idx_email (email),
    INDEX idx_expires_at (expires_at)
);
```

### Redis Data Structures (Authentication-Enhanced)

```
-- JWT blacklist (revoked tokens)
token:blacklist:{jti} -> STRING "revoked" with TTL (until token expiry)

-- Active user sessions
session:user:{user_id} -> SET of session_ids

-- Rate limiting
ratelimit:user:{user_id}:{endpoint} -> HASH {
    count: INTEGER,
    window_start: TIMESTAMP
} with TTL (1 hour)

ratelimit:ip:{ip_address}:{endpoint} -> HASH {
    count: INTEGER,
    window_start: TIMESTAMP
} with TTL (1 hour)

-- Failed login attempts (brute force protection)
failed_logins:{email} -> STRING (counter) with TTL (15 minutes)

-- Account lockout
account_locked:{user_id} -> STRING "locked" with TTL (30 minutes)



-- Active device tracking
active_devices:user:{user_id} -> ZSET (score = last_activity timestamp, member = device_id)

-- Session state (as before, now with user_id)
session:{session_id} -> HASH {
    user_id, document_id, status, started_at
}

-- Generation lock (prevent concurrent generation per user+doc)
lock:generation:{user_id}:{document_id} -> STRING with TTL (5 minutes)

-- Recent questions cache (per user)
recent_questions:{user_id}:{document_id} -> ZSET

-- User preferences cache
user:preferences:{user_id} -> HASH {
    theme, language, notification_settings
} with TTL (1 hour)

-- OAuth state (during OAuth flow)
oauth:state:{state_token} -> HASH {
    user_id, provider, redirect_uri, created_at
} with TTL (10 minutes)
```

---

## Authentication & Authorization Architecture

### JWT Token Structure

**Access Token (Short-lived: 15 minutes)**
```json
{
  "sub": "user_id_uuid",
  "email": "user@example.com",
  "username": "johndoe",
  "type": "access",
  "scopes": ["documents:read", "documents:write", "questions:generate"],
  "iat": 1234567890,
  "exp": 1234568790,
  "jti": "unique_token_id"
}
```

**Refresh Token (Long-lived: 30 days)**
```json
{
  "sub": "user_id_uuid",
  "type": "refresh",
  "device_id": "device_unique_id",
  "iat": 1234567890,
  "exp": 1237159890,
  "jti": "unique_token_id"
}
```

### Authentication Flow Diagrams

**Registration Flow:**
```
1. User submits: email, username, password, full_name
2. Backend validates: email format, username availability, password strength
3. Hash password with bcrypt (cost factor 12)
4. Create user record
5. Automatically log user in (generate tokens)
6. Return success + tokens
```

**Login Flow:**
```
1. User submits: email/username + password
2. Backend checks: user exists, is_active, not locked
3. Verify password hash
4. If wrong password: increment failed_login_attempts
   - After 5 attempts: lock account for 30 minutes
5. If correct:
   - Reset failed_login_attempts to 0
   - Generate access_token (15 min) + refresh_token (30 days)
   - Store refresh_token hash in database
   - Update last_login_at
   - Log audit event
6. Return tokens + user profile
7. Frontend stores tokens securely (SecureStore)
```

**Token Refresh Flow:**
```
1. Access token expires (15 minutes)
2. Frontend automatically detects 401 response
3. Send refresh_token to /auth/refresh endpoint
4. Backend validates:
   - Token signature valid
   - Token not expired
   - Token not revoked (check database)
   - User still active
5. If valid:
   - Generate new access_token
   - Optionally rotate refresh_token (security best practice)
   - Update last_used_at in refresh_tokens table
6. Return new access_token (+ new refresh_token if rotated)
7. Frontend updates stored tokens
8. Retry original request with new access_token
```

**Logout Flow:**
```
1. User clicks logout
2. Frontend sends current refresh_token to /auth/logout
3. Backend:
   - Mark refresh_token as revoked in database
   - Add access_token jti to Redis blacklist (TTL = token expiry)
   - Log audit event
4. Frontend:
   - Clear all stored tokens
   - Clear user state
   - Redirect to login screen
```

**Logout All Devices:**
```
1. User clicks "Logout everywhere"
2. Backend:
   - Revoke all refresh_tokens for user_id
   - Add all active access_token JTIs to blacklist
   - Clear user sessions from Redis
3. User must re-login on all devices
```

### Password Security Requirements

**Password Policy:**
- Minimum 8 characters
- At least 1 uppercase letter
- At least 1 lowercase letter
- At least 1 number
- At least 1 special character
- Not in common password list (e.g., "Password123!")
- Not similar to email or username

**Password Hashing:**
```python
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Hash password
hashed = pwd_context.hash(plain_password)  # bcrypt with cost 12

# Verify password
is_valid = pwd_context.verify(plain_password, hashed)
```





---

## API Endpoint Specification

### Authentication Endpoints

**POST /auth/register**
```json
Request:
{
  "email": "user@example.com",
  "username": "johndoe",
  "password": "SecurePass123!",
  "full_name": "John Doe"
}

Response (201):
{
  "message": "Registration successful.",
  "user_id": "uuid",
  "email": "user@example.com",
  "access_token": "...",
  "refresh_token": "..."
}

Errors:
- 400: Invalid email format
- 409: Email or username already exists
- 422: Password doesn't meet requirements
```

**POST /auth/login**
```json
Request:
{
  "email": "user@example.com",
  "password": "SecurePass123!"
}

Response (200):
{
  "access_token": "eyJhbGc...",
  "refresh_token": "eyJhbGc...",
  "token_type": "bearer",
  "expires_in": 900,
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "username": "johndoe",
    "full_name": "John Doe",
    "full_name": "John Doe"
  }
}

Errors:
- 401: Invalid credentials
- 403: Account locked due to multiple failed attempts

- 404: User not found
```

**POST /auth/refresh**
```json
Request:
{
  "refresh_token": "eyJhbGc..."
}

Response (200):
{
  "access_token": "eyJhbGc...",
  "refresh_token": "eyJhbGc...",  # Optional: rotated token
  "token_type": "bearer",
  "expires_in": 900
}

Errors:
- 401: Invalid or expired refresh token
- 401: Token revoked
```

**POST /auth/logout**
```json
Request:
Headers: {Authorization: "Bearer <access_token>"}
Body: {
  "refresh_token": "eyJhbGc..."
}

Response (200):
{
  "message": "Logged out successfully"
}
```

**POST /auth/logout-all**
```json
Request:
Headers: {Authorization: "Bearer <access_token>"}

Response (200):
{
  "message": "Logged out from all devices",
  "sessions_revoked": 5
}
```



**GET /auth/me**
```json
Request:
Headers: {Authorization: "Bearer <access_token>"}

Response (200):
{
  "id": "uuid",
  "email": "user@example.com",
  "username": "johndoe",
  "full_name": "John Doe",
  "created_at": "2026-01-01T00:00:00Z",
  "last_login_at": "2026-02-13T10:00:00Z"
}
```

**PUT /auth/update-profile**
```json
Request:
Headers: {Authorization: "Bearer <access_token>"}
Body: {
  "full_name": "John Updated Doe",
  "timezone": "America/New_York",
  "preferences": {
    "theme": "dark",
    "notifications_enabled": true
  }
}

Response (200):
{
  "message": "Profile updated successfully",
  "user": {...}
}
```

**POST /auth/change-password**
```json
Request:
Headers: {Authorization: "Bearer <access_token>"}
Body: {
  "current_password": "OldPass123!",
  "new_password": "NewPass123!"
}

Response (200):
{
  "message": "Password changed successfully"
}

Errors:
- 401: Current password incorrect
- 422: New password doesn't meet requirements
```

**GET /auth/sessions**
```json
Request:
Headers: {Authorization: "Bearer <access_token>"}

Response (200):
{
  "sessions": [
    {
      "id": "uuid",
      "device_name": "iPhone 14 Pro",
      "device_type": "mobile",
      "ip_address": "192.168.1.1",
      "last_activity": "2026-02-13T10:30:00Z",
      "is_current": true
    },
    {
      "id": "uuid",
      "device_name": "Chrome on MacBook",
      "device_type": "desktop",
      "ip_address": "192.168.1.5",
      "last_activity": "2026-02-12T15:00:00Z",
      "is_current": false
    }
  ]
}
```

**DELETE /auth/sessions/{session_id}**
```json
Request:
Headers: {Authorization: "Bearer <access_token>"}

Response (200):
{
  "message": "Session revoked successfully"
}
```

### Protected Document Endpoints (Now Require Auth)

**POST /documents/upload**
```json
Request:
Headers: {
  Authorization: "Bearer <access_token>",
  Content-Type: "multipart/form-data"
}
Body: FormData with 'file' field

Response (201):
{
  "document_id": "uuid",
  "filename": "mybook.pdf",
  "status": "processing",
  "message": "Document uploaded successfully"
}

Errors:
- 401: Unauthorized (invalid/missing token)
- 413: File too large
- 415: Unsupported file type
- 429: Rate limit exceeded (e.g., 10 uploads per hour)
```

**GET /documents**
```json
Request:
Headers: {Authorization: "Bearer <access_token>"}
Query: ?page=1&limit=20&status=completed

Response (200):
{
  "documents": [
    {
      "id": "uuid",
      "filename": "mybook.pdf",
      "status": "completed",
      "uploaded_at": "2026-02-13T10:00:00Z",
      "total_chunks": 342,
      "questions_generated": 45
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 5
  }
}

Note: Only returns documents belonging to authenticated user
```

**GET /documents/{document_id}**
```json
Request:
Headers: {Authorization: "Bearer <access_token>"}

Response (200):
{
  "id": "uuid",
  "filename": "mybook.pdf",
  "status": "completed",
  "uploaded_at": "2026-02-13T10:00:00Z",
  "total_chunks": 342,
  "total_tokens": 45000,
  "metadata": {...}
}

Errors:
- 401: Unauthorized
- 403: Forbidden (document belongs to another user)
- 404: Document not found
```

**DELETE /documents/{document_id}**
```json
Request:
Headers: {Authorization: "Bearer <access_token>"}

Response (200):
{
  "message": "Document deleted successfully"
}

Errors:
- 401: Unauthorized
- 403: Forbidden
- 404: Not found
```

### Protected Question Endpoints

**POST /questions/generate**
```json
Request:
Headers: {Authorization: "Bearer <access_token>"}
Body: {
  "document_id": "uuid",
  "count": 10,
  "types": ["factual", "analytical"],
  "difficulty": "medium",
  "marks": 5,
  "focus_topics": ["chapter 3"]
}

Response (200): Streaming SSE
data: {"status": "processing", "progress": 0}
data: {"status": "generating", "progress": 30}
data: {"question": {...}, "progress": 50}
data: {"question": {...}, "progress": 70}
data: {"status": "complete", "total_generated": 10}

Errors:
- 401: Unauthorized
- 403: Forbidden (document not owned by user)
- 429: Rate limit exceeded (e.g., 100 questions/day)
```

**GET /questions**
```json
Request:
Headers: {Authorization: "Bearer <access_token>"}
Query: ?document_id=uuid&page=1&limit=20

Response (200):
{
  "questions": [
    {
      "id": "uuid",
      "question_text": "What is X?",
      "type": "factual",
      "difficulty": "easy",
      "marks": 2,
      "user_rating": 5
    }
  ],
  "pagination": {...}
}

Note: Only returns questions from user's documents
```
---

## Monitoring & Analytics Dashboard

### Key User Metrics

**User Acquisition:**
- Daily signups
- Activation rate (first document upload)

**User Engagement:**
- Daily Active Users (DAU)
- Monthly Active Users (MAU)
- Average session duration
- Documents per user
- Questions generated per user

**User Retention:**
- Day 1, Day 7, Day 30 retention
- Churn rate
- Reactivation rate

**System Performance:**
- Authentication latency
- Document processing time
- Question generation time
- Error rates per endpoint

**Security Metrics:**
- Failed login attempts
- Account lockouts
- Token refresh rate
- Suspicious activity alerts