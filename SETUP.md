# QGen RAG - Setup Guide

This guide ensures a clean, error-free setup on any new machine.

## Prerequisites

- Python 3.10+
- Node.js 18+
- Docker & Docker Compose
- PostgreSQL 14+ (or use Docker)
- Redis 6+ (or use Docker)

## Quick Start (Recommended)

### 1. Clone and Navigate
```bash
git clone <repository-url>
cd qgen_rag
```

### 2. Start Infrastructure (Docker)
```bash
docker-compose up -d db redis
```

Wait for services to be healthy (~30 seconds):
```bash
docker-compose ps
```

### 3. Backend Setup
```bash
cd backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.local.example .env.local
```

### 4. Configure Environment

Edit `backend/.env.local` and set:
- `DEEPSEEK_API_KEY` (or your LLM provider API key)
- Other settings as needed (defaults work for local development)

### 5. Initialize Database

**IMPORTANT**: Always use Alembic migrations, never create tables manually.

```bash
# Reset database to clean state (recommended for fresh setup)
python scripts/reset_database.py --confirm

# Mark database as migrated (migrations have conflicts, use stamp instead)
alembic stamp head

# Verify database health (includes auth database permission check)
python scripts/check_database.py
```

**Note**: 
- Due to migration history conflicts, we use `alembic stamp head` instead of `alembic upgrade head` for fresh installations
- The auth database (SQLite) permissions are automatically set during setup
- If you ever run the app with `sudo`, fix permissions with: `sudo chown $USER:$USER auth.db && sudo chmod 664 auth.db`

### 6. Frontend Setup
```bash
cd ../trainer-web
npm install
```

### 7. Start Services

**Terminal 1 - API Server:**
```bash
cd backend
source .venv/bin/activate
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 2 - Celery Worker:**
```bash
cd backend
source .venv/bin/activate
celery -A app.workers.celery_app worker --loglevel=info --concurrency=2
```

**Terminal 3 - Celery Flower (Optional):**
```bash
cd backend
source .venv/bin/activate
celery -A app.workers.celery_app flower --port=5555
```

**Terminal 4 - Frontend:**
```bash
cd trainer-web
npm run dev
```

## Access Points

- **Frontend**: http://localhost:5173
- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Flower Monitor**: http://localhost:5555

## Common Issues & Solutions

### Issue: "duplicate key value violates unique constraint pg_type_typname_nsp_index"

**Cause**: PostgreSQL type name conflicts from previous installations or manual table creation.

**Solution**:
```bash
cd backend
python scripts/reset_database.py
alembic upgrade head
```

### Issue: "Application startup failed" or "Table does not exist"

**Cause**: Database migrations not run.

**Solution**:
```bash
cd backend
source .venv/bin/activate
alembic upgrade head
```

### Issue: Port already in use

**Cause**: Previous processes still running.

**Solution**:
```bash
# Find and kill processes
lsof -i :8000  # API
lsof -i :5173  # Frontend
lsof -i :5555  # Flower

# Kill specific process
kill <PID>

# Or kill all related processes
pkill -f "uvicorn app.main"
pkill -f "celery.*worker"
pkill -f "vite dev"
```

### Issue: Database connection refused

**Cause**: PostgreSQL not running or wrong credentials.

**Solution**:
```bash
# Check Docker containers
docker-compose ps

# Restart if needed
docker-compose restart db

# Verify connection
docker-compose exec db psql -U qgen_user -d qgen_db -c "SELECT 1;"
```

## Database Management

### View Current Migration Status
```bash
cd backend
alembic current
```

### View Migration History
```bash
alembic history
```

### Create New Migration (After Model Changes)
```bash
alembic revision --autogenerate -m "Description of changes"
```

### Rollback Migration
```bash
alembic downgrade -1  # Go back one migration
```

### Complete Database Reset
```bash
# Stop all services
docker-compose down

# Remove volumes (WARNING: Deletes all data)
docker-compose down -v

# Start fresh
docker-compose up -d db redis
cd backend
alembic upgrade head
```

## Production Deployment

For production deployment, see `docs/ENVIRONMENT_SETUP.md` and `docs/DGX_SPARK_DEPLOYMENT.md`.

## Development Workflow

1. **Make code changes**
2. **Update models** (if needed)
3. **Create migration**: `alembic revision --autogenerate -m "description"`
4. **Review migration** in `backend/alembic/versions/`
5. **Apply migration**: `alembic upgrade head`
6. **Test changes**
7. **Commit** migration files with code changes

## Important Notes

- ✅ **Always use Alembic migrations** for database schema changes
- ❌ **Never use `Base.metadata.create_all()`** - it causes type conflicts
- ✅ **Run `reset_database.py`** on fresh installations if you encounter errors
- ✅ **Commit migration files** to version control
- ✅ **Test migrations** before deploying to production

## Environment Variables

Key environment variables in `backend/.env.local`:

```bash
# Database
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=qgen_user
POSTGRES_PASSWORD=qgen_password
POSTGRES_DB=qgen_db

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# API
API_PORT=8000
API_WORKERS=4

# LLM Provider
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=your-api-key-here
DEEPSEEK_MODEL=deepseek-chat

# Frontend
TRAINER_WEB_PORT=5173
```

## Troubleshooting

### Common Issues

**SQLite "attempt to write a readonly database" error:**
```bash
# Fix permissions (run as the user who owns the app)
sudo chown $USER:$USER auth.db auth.db-wal auth.db-shm
sudo chmod 664 auth.db auth.db-wal auth.db-shm
```

**PostgreSQL connection errors:**
```bash
# Check if database is running
docker compose ps

# Restart database
docker compose restart db
```

**Migration errors:**
```bash
# Reset and re-stamp
python scripts/reset_database.py --confirm
alembic stamp head
```

### General Troubleshooting

1. Check logs in `backend/logs/`
2. Verify all services are running: `docker compose ps`
3. Check environment variables are set correctly
4. Run database health check: `python scripts/check_database.py`
5. Try resetting the database: `python scripts/reset_database.py`
5. Check the issue tracker or create a new issue

## Getting Help

- Documentation: `docs/`
- API Documentation: http://localhost:8000/docs (when running)
- Issues: GitHub Issues
