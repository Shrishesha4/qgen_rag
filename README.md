# QuestionGeneration AI

<div align="center">

![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.11+-green.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110-teal.svg)
![React Native](https://img.shields.io/badge/React%20Native-Expo%20SDK%2054-purple.svg)
![License](https://img.shields.io/badge/license-MIT-yellow.svg)

**A stateful RAG-based question generation system for educators**

[Features](#-features) • [Quick Start](#-quick-start) • [API Reference](#-api-reference) • [Configuration](#-configuration)

</div>

---

## 📋 Overview

QuestionGeneration AI is an intelligent exam question generation platform that leverages Retrieval-Augmented Generation (RAG) to create high-quality, contextually relevant questions from educational documents. Built for educators who want to save time while creating diverse, curriculum-aligned assessments.

### Key Capabilities

- 📄 **Document Processing**: Upload PDFs, DOCX, or TXT files and automatically extract content
- 🧠 **Intelligent Generation**: Generate MCQs, short-answer, and long-answer questions using LLMs
- 🔍 **Hybrid Search**: Combines BM25 keyword search with vector similarity for optimal retrieval
- 📊 **Bloom's Taxonomy**: Target specific cognitive levels (Remember → Create)
- ✅ **Quality Validation**: Automatic scoring for answerability, specificity, and confidence
- 📱 **Mobile-First**: Beautiful React Native app with real-time streaming updates

---

## ✨ Features

### RAG Pipeline
| Feature | Description |
|---------|-------------|
| **Hybrid Search** | BM25 + pgvector cosine similarity with score fusion |
| **Smart Chunking** | RecursiveCharacterTextSplitter (1000 tokens, 200 overlap) |
| **Cross-Encoder Reranking** | ms-marco-MiniLM-L-6-v2 for precision retrieval |
| **Query Expansion** | LLM-based query reformulation for better coverage |
| **Embedding Cache** | Two-tier caching (L1: LRU, L2: Redis) |

### Question Generation
| Feature | Description |
|---------|-------------|
| **Multiple Types** | MCQ, Short Answer, Long Answer |
| **Difficulty Levels** | Easy, Medium, Hard |
| **Bloom's Taxonomy** | Remember, Understand, Apply, Analyze, Evaluate, Create |
| **Deduplication** | Semantic similarity check against existing questions |
| **Quality Scoring** | Answerability, Specificity, Generation Confidence |

### Infrastructure
| Feature | Description |
|---------|-------------|
| **Vector Database** | PostgreSQL + pgvector with IVFFlat indexing |
| **Authentication** | JWT with refresh tokens + Redis blacklist |
| **Real-time Updates** | Server-Sent Events (SSE) streaming |
| **Error Recovery** | Exponential backoff with jitter for LLM calls |
| **Monitoring** | Structured logging (loguru) + Prometheus metrics |
| **Migrations** | Alembic for database schema management |

---

## 🚀 Quick Start

### Prerequisites

- **Docker** & **Docker Compose** (v2.0+)
- **Node.js** 18+ & **npm** (for mobile app)
- **Ollama** (local installation recommended for GPU)
- **Expo Go** app (for mobile testing)

### 1. Clone & Configure

```bash
# Clone the repository
git clone https://github.com/yourusername/qgen_llm_2.git
cd qgen_llm_2

# Copy environment template
cp .env.example .env

# Edit .env with your settings
nano .env
```

### 2. Setup Ollama (Local)

```bash
# Install Ollama (macOS)
brew install ollama

# Start Ollama service
ollama serve

# Pull the recommended model (in another terminal)
ollama pull llama3.2:3b-instruct-q4_K_M

# Or use a larger model for better quality
ollama pull llama3.1:8b-instruct-q4_K_M

# Pull the embedding model (required for RAG)
ollama pull nomic-embed-text
```

### 2b. Alternative: Use Google Gemini API (Cloud)

Instead of running Ollama locally, you can use Google's Gemini API for better quality and faster generation:

```bash
# Install the Gemini SDK
pip install google-genai

# Set environment variables in your .env file:
LLM_PROVIDER=gemini
GEMINI_API_KEY=your-gemini-api-key-here
GEMINI_MODEL=gemini-2.0-flash  # Options: gemini-2.0-flash, gemini-1.5-pro, gemini-1.5-flash
```

**Get an API key:** Visit [Google AI Studio](https://aistudio.google.com/apikey) to create a free API key.

**Available Gemini Models:**
| Model | Speed | Quality | Cost |
|-------|-------|---------|------|
| `gemini-2.0-flash` | Fast | Good | Low |
| `gemini-1.5-flash` | Fastest | Good | Lowest |
| `gemini-1.5-pro` | Moderate | Best | Higher |

### 3. Start Backend Services

```bash
# Start all services (PostgreSQL, Redis, API)
docker-compose up -d

# Check service health
docker-compose ps

# View API logs
docker-compose logs -f api

# Wait for "All services ready" message
```

### 4. Run Mobile App

```bash
# Navigate to client directory
cd client

# Install dependencies
npm install

# Start Expo development server
npx expo start

# Scan QR code with Expo Go app (iOS/Android)
```

### 5. Run Trainer Web App (SvelteKit)

```bash
# Navigate to trainer-web directory
cd trainer-web

# Install dependencies
npm install

# Start development server
npm run dev

# Opens at http://localhost:5173
```

### 6. Access Services

| Service | URL | Description |
|---------|-----|-------------|
| API | http://localhost:8000 | FastAPI backend |
| API Docs | http://localhost:8000/docs | Swagger UI |
| ReDoc | http://localhost:8000/redoc | Alternative docs |
| Health | http://localhost:8000/health | Health check |
| Trainer Web | http://localhost:5173 | SvelteKit trainer dashboard |

---

## 📖 API Reference

### Authentication

```bash
# Register new user
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "teacher@school.edu", "password": "securepass123", "full_name": "John Doe"}'

# Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "teacher@school.edu", "password": "securepass123"}'

# Response includes access_token and refresh_token
```

### Document Upload

```bash
# Upload PDF document
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -H "Authorization: Bearer <access_token>" \
  -F "file=@textbook.pdf" \
  -F "context=Chapter 5: Photosynthesis in Plants"
```

### Question Generation

```bash
# Generate questions (SSE streaming)
curl -X POST http://localhost:8000/api/v1/questions/generate \
  -H "Authorization: Bearer <access_token>" \
  -H "Accept: text/event-stream" \
  -H "Content-Type: application/json" \
  -d '{
    "document_id": "uuid-here",
    "count": 5,
    "types": ["mcq", "short_answer"],
    "difficulty": "medium",
    "bloom_levels": ["understand", "apply"]
  }'
```

### Quick Generate (Upload + Generate)

```bash
# Single-step: upload PDF and generate questions
curl -X POST http://localhost:8000/api/v1/questions/quick-generate \
  -H "Authorization: Bearer <access_token>" \
  -H "Accept: text/event-stream" \
  -F "file=@document.pdf" \
  -F "context=Biology exam preparation" \
  -F "count=10" \
  -F "types=mcq,short_answer" \
  -F "difficulty=medium"
```

### Full API Documentation

Interactive API documentation available at:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

## ⚙️ Configuration

### Environment Variables

Create a `.env` file in the project root:

```bash
# =============================================================================
# Database
# =============================================================================
POSTGRES_USER=qgen_user
POSTGRES_PASSWORD=qgen_password
POSTGRES_DB=qgen_db
POSTGRES_PORT=5432

# =============================================================================
# Redis
# =============================================================================
REDIS_PORT=6379

# =============================================================================
# Security (CHANGE IN PRODUCTION!)
# =============================================================================
SECRET_KEY=your-super-secret-key-minimum-32-characters-long
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=30

# =============================================================================
# Ollama LLM
# =============================================================================
# For local Ollama: http://host.docker.internal:11434 (Docker)
# For Docker Ollama: http://ollama:11434
OLLAMA_BASE_URL=http://host.docker.internal:11434

# Recommended models (in order of speed/quality tradeoff):
#   - llama3.2:3b-instruct-q4_K_M (fastest, good quality)
#   - llama3.1:8b-instruct-q4_K_M (balanced)
#   - llama3.1:70b-instruct-q4_K_M (best quality, slow)
#   - mistral:7b-instruct-q4_K_M (alternative)
OLLAMA_MODEL=llama3.2:3b-instruct-q4_K_M

# =============================================================================
# Embedding Model
# =============================================================================
# Options:
#   - all-MiniLM-L6-v2 (384 dims, fast, good) - DEFAULT
#   - all-mpnet-base-v2 (768 dims, better, slower)
#   - BAAI/bge-base-en-v1.5 (768 dims, best for Q&A)
EMBEDDING_MODEL=all-MiniLM-L6-v2
EMBEDDING_DIMENSION=384

# For BGE models, enable instruction prefixes
EMBEDDING_USE_INSTRUCTION=false

# Redis L2 cache for embeddings
EMBEDDING_REDIS_CACHE=true
EMBEDDING_CACHE_TTL=604800  # 7 days

# =============================================================================
# Reranker (Cross-Encoder)
# =============================================================================
RERANKER_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2
RERANKER_ENABLED=true

# =============================================================================
# Document Processing
# =============================================================================
MAX_UPLOAD_SIZE_MB=50
CHUNK_SIZE=1000
CHUNK_OVERLAP=200

# =============================================================================
# Question Generation
# =============================================================================
MAX_QUESTIONS_PER_REQUEST=50

# =============================================================================
# Rate Limiting
# =============================================================================
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW_SECONDS=3600

# =============================================================================
# Logging & Monitoring
# =============================================================================
# Levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_LEVEL=INFO

# Set to true for production (JSON structured logs)
LOG_JSON=false

# Prometheus metrics endpoint
ENABLE_METRICS=true

# =============================================================================
# API Port
# =============================================================================
API_PORT=8000
```

### Embedding Model Comparison

| Model | Dimensions | Speed | Quality | Best For |
|-------|------------|-------|---------|----------|
| `all-MiniLM-L6-v2` | 384 | ⚡⚡⚡ | ⭐⭐⭐ | General use, fast inference |
| `all-mpnet-base-v2` | 768 | ⚡⚡ | ⭐⭐⭐⭐ | Better semantic understanding |
| `BAAI/bge-base-en-v1.5` | 768 | ⚡⚡ | ⭐⭐⭐⭐⭐ | Q&A tasks, with instructions |

### LLM Model Comparison

| Model | VRAM | Speed | Quality | Notes |
|-------|------|-------|---------|-------|
| `llama3.2:3b-instruct-q4_K_M` | ~3GB | ⚡⚡⚡ | ⭐⭐⭐ | Best for quick iteration |
| `llama3.1:8b-instruct-q4_K_M` | ~6GB | ⚡⚡ | ⭐⭐⭐⭐ | Balanced choice |
| `llama3.1:70b-instruct-q4_K_M` | ~40GB | ⚡ | ⭐⭐⭐⭐⭐ | Best quality |
| `mistral:7b-instruct-q4_K_M` | ~5GB | ⚡⚡ | ⭐⭐⭐⭐ | Good alternative |
| `qwen2.5:7b-instruct-q4_K_M` | ~5GB | ⚡⚡ | ⭐⭐⭐⭐ | Strong reasoning |

---

## 🔧 Development

### Running Tests

```bash
# Backend tests
cd backend
pytest -v

# With coverage
pytest --cov=app --cov-report=html
```

### Database Migrations

```bash
# Enter API container
docker-compose exec api bash

# Create new migration
alembic revision --autogenerate -m "Add new column"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1
```

### Rebuilding Services

```bash
# Rebuild API after dependency changes
docker-compose up -d --build api

# Full rebuild (clears cache)
docker-compose build --no-cache

# Reset database (WARNING: deletes all data)
docker-compose down -v
docker-compose up -d
```

### Viewing Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f api

# Last 100 lines
docker-compose logs --tail=100 api
```

---

## 📊 Monitoring

### Health Check

```bash
curl http://localhost:8000/health
```

Response:
```json
{
  "status": "healthy",
  "database": "connected",
  "redis": "connected",
  "version": "1.0.0"
}
```

### Prometheus Metrics

When `ENABLE_METRICS=true`, metrics are available at:

```bash
curl http://localhost:8000/metrics
```

Exposed metrics:
- `http_requests_total` - Total HTTP requests
- `http_request_duration_seconds` - Request latency histogram
- `questions_generated_total` - Total questions generated
- `embedding_cache_hits` - Cache hit rate

### Logging

Structured JSON logs (when `LOG_JSON=true`):

```json
{
  "timestamp": "2024-01-15T10:30:00.000Z",
  "level": "INFO",
  "logger": "app.services.question_service",
  "message": "Question generated",
  "request_id": "abc123",
  "document_id": "doc-uuid",
  "question_type": "mcq",
  "duration_ms": 1523.45
}
```

---

## 🚢 Production Deployment

### Docker Compose Production

Create `docker-compose.prod.yml`:

```yaml
version: '3.8'

services:
  api:
    command: >
      gunicorn app.main:app
      --workers 4
      --worker-class uvicorn.workers.UvicornWorker
      --bind 0.0.0.0:8000
      --access-logfile -
      --error-logfile -
    environment:
      - LOG_JSON=true
      - LOG_LEVEL=WARNING
    deploy:
      resources:
        limits:
          memory: 8G
        reservations:
          memory: 2G
```

Run with:
```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Security Checklist

- [ ] Change `SECRET_KEY` to a secure random value
- [ ] Use strong `POSTGRES_PASSWORD`
- [ ] Configure HTTPS with reverse proxy (nginx/Traefik)
- [ ] Restrict CORS origins for production
- [ ] Enable rate limiting
- [ ] Set `LOG_JSON=true` for centralized logging
- [ ] Configure backup for PostgreSQL volumes
- [ ] Use Docker secrets for sensitive values

---

## 🧠 Training Pipeline (LoRA Fine-Tuning)

The trainer web app provides a full feedback loop: generate questions → vet/edit them → fine-tune the local model using approved/rejected data.

### How It Works

1. **Question Generation** — Teachers upload documents and generate questions via the RAG pipeline.
2. **Vetting** — Teachers or vetters review generated questions (approve, reject, or edit).
3. **Training Data Collection** — Approved questions become SFT training pairs. Edits and rejections become DPO pairs (chosen vs rejected).
4. **Fine-Tuning** — An admin triggers LoRA fine-tuning on the collected data, producing a new model version.
5. **Activation** — The new model version can be activated for subsequent question generation.

### Setup (GPU Required)

```bash
# 1. Install training dependencies
cd backend
pip install transformers>=4.40.0 peft>=0.10.0 trl>=0.8.0 \
            datasets>=2.18.0 accelerate>=0.29.0 bitsandbytes>=0.43.0

# 2. Configure environment variables (in .env)
TRAINING_DATA_DIR=./training_data       # Exported SFT/DPO JSONL files
LORA_ADAPTERS_DIR=./lora_adapters       # Saved LoRA adapter checkpoints
TRAINING_BASE_MODEL=deepseek-ai/DeepSeek-R1-Distill-Llama-8B  # HuggingFace model ID

# 3. The base model downloads automatically on first training run (~16 GB)
# Ensure you have sufficient disk space and a CUDA-capable GPU with >= 16 GB VRAM.
```

### Training API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/training/status` | GET | Current training status & data counts |
| `/api/v1/training/trigger` | POST | Start a new training job (admin only) |
| `/api/v1/training/versions` | GET | List all model versions |
| `/api/v1/training/versions/{id}/activate` | POST | Activate a model version (admin only) |
| `/api/v1/training/jobs` | GET | List training job history |
| `/api/v1/training/pairs` | GET | Browse collected training pairs |

### LoRA Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| Rank (r) | 16 | Low-rank dimension |
| Alpha | 32 | Scaling factor (alpha/r = 2) |
| Dropout | 0.05 | LoRA dropout rate |
| Target modules | q_proj, v_proj | Attention weight matrices |
| Training method | SFT (default), DPO | Supervised or preference-based |

---

## 🐛 Troubleshooting

### Common Issues

#### API can't connect to Ollama
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# If using Docker on Linux, ensure host.docker.internal works
docker run --rm alpine ping host.docker.internal
```

#### Database connection errors
```bash
# Check PostgreSQL logs
docker-compose logs db

# Verify connection
docker-compose exec db psql -U qgen_user -d qgen_db -c "SELECT 1"
```

#### Embedding model download issues
```bash
# Models download on first use - check API logs
docker-compose logs -f api

# Manually download in container
docker-compose exec api python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
```

#### Memory issues
```bash
# Check container memory usage
docker stats

# Increase limits in docker-compose.yml
deploy:
  resources:
    limits:
      memory: 8G
```

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- [Ollama](https://ollama.ai/) - Local LLM inference
- [Sentence Transformers](https://www.sbert.net/) - Embedding models
- [pgvector](https://github.com/pgvector/pgvector) - Vector similarity for PostgreSQL
- [FastAPI](https://fastapi.tiangolo.com/) - Modern Python web framework
- [Expo](https://expo.dev/) - React Native development platform

---

<div align="center">
  <sub>Built with ❤️ for educators everywhere</sub>
</div>
