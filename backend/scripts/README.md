# Database Management Scripts

This directory contains scripts for managing the PostgreSQL database and fixing common setup issues.

## Quick Fix (Current Error)

If you're seeing the error:
```
duplicate key value violates unique constraint "pg_type_typname_nsp_index"
```

**Run this immediately:**
```bash
cd backend
source .venv/bin/activate
python scripts/fix_type_conflict.py
alembic upgrade head
```

## Scripts Overview

### 1. `fix_type_conflict.py` - Quick Fix for Type Conflicts

**Use when:** You see PostgreSQL type name conflicts during startup.

**What it does:**
- Drops conflicting custom types
- Preserves existing data
- Prepares database for migrations

**Usage:**
```bash
python scripts/fix_type_conflict.py
```

### 2. `check_database.py` - Database Health Check

**Use when:** Before running migrations or troubleshooting issues.

**What it does:**
- Checks database connectivity
- Verifies required extensions
- Detects type name conflicts
- Shows current migration status
- Reports database size

**Usage:**
```bash
python scripts/check_database.py
```

**Example output:**
```
✅ Database connection successful
✅ pgvector extension installed
✅ No type name conflicts
ℹ️  Found 15 existing tables
✅ Alembic version: abc123def456
ℹ️  Database size: 45 MB

✅ Database health check passed!
```

### 3. `reset_database.py` - Complete Database Reset

**Use when:** 
- Fresh installation on new machine
- Unrecoverable database corruption
- Need to start completely clean

**⚠️ WARNING:** This deletes ALL data!

**What it does:**
- Drops all tables and data
- Recreates public schema
- Enables required extensions
- Leaves database ready for migrations

**Usage:**
```bash
# Interactive (asks for confirmation)
python scripts/reset_database.py

# Non-interactive (auto-confirm)
python scripts/reset_database.py --confirm
```

## Common Workflows

### First-Time Setup (New Machine)

```bash
# 1. Start infrastructure
docker compose up -d db redis

# 2. Reset database and create functions
python scripts/reset_database.py --confirm

# 3. Apply migrations
alembic upgrade head

# 4. Check database health
python scripts/check_database.py

# 5. Start application (with 6 workers for production-like setup)
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 6
```

### Fixing Type Conflicts

```bash
# 1. Fix conflicts
python scripts/fix_type_conflict.py

# 2. Run migrations
alembic upgrade head

# 3. Restart application
```

### Complete Reset (Nuclear Option)

```bash
# 1. Reset database
python scripts/reset_database.py

# 2. Run migrations
alembic upgrade head

# 3. Start application
```

### Health Check Before Deployment

```bash
# Check everything is OK
python scripts/check_database.py

# Should show:
# ✅ All checks passed
# ✅ Current migration version
```

## Troubleshooting

### Script fails with "Cannot connect to database"

**Cause:** PostgreSQL not running or wrong credentials.

**Fix:**
```bash
# Check Docker containers
docker-compose ps

# Restart database
docker-compose restart db

# Verify credentials in .env.local
cat .env.local | grep POSTGRES
```

### Script fails with "Permission denied"

**Cause:** Script not executable or wrong Python environment.

**Fix:**
```bash
# Ensure virtual environment is activated
source .venv/bin/activate

# Make script executable
chmod +x scripts/*.py

# Run with python explicitly
python scripts/check_database.py
```

### "Module not found" errors

**Cause:** Dependencies not installed or wrong directory.

**Fix:**
```bash
# Ensure you're in backend directory
cd backend

# Activate virtual environment
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Script Dependencies

All scripts require:
- Python 3.10+
- Virtual environment activated
- Dependencies from `requirements.txt` installed
- PostgreSQL running (Docker or local)
- Correct `.env.local` configuration

## When to Use Each Script

| Scenario | Script | Command |
|----------|--------|---------|
| First-time setup | `check_database.py` | Check before migrations |
| Type conflict error | `fix_type_conflict.py` | Quick fix |
| Pre-migration check | `check_database.py` | Verify health |
| Complete fresh start | `reset_database.py` | Nuclear option |
| Before deployment | `check_database.py` | Final verification |

## Best Practices

1. **Always check first:** Run `check_database.py` before making changes
2. **Use migrations:** Never manually create tables, always use Alembic
3. **Backup data:** Before running `reset_database.py`, backup important data
4. **Test locally:** Test database changes locally before deploying
5. **Version control:** Commit migration files with code changes

## Integration with Makefile

These scripts are integrated into the project Makefile:

```bash
# Check database health
make db-check

# Reset database (with confirmation)
make db-reset

# Run migrations
make db-migrate
```

## Support

If these scripts don't resolve your issue:

1. Check the main `SETUP.md` documentation
2. Review Alembic migration history: `alembic history`
3. Check application logs in `backend/logs/`
4. Create an issue with error details
