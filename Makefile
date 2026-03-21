.PHONY: help setup setup-backend setup-frontend db-reset db-check db-migrate start stop clean

help:
	@echo "QGen RAG - Development Commands"
	@echo ""
	@echo "Setup Commands:"
	@echo "  make setup          - Complete first-time setup (recommended for new machines)"
	@echo "  make setup-backend  - Setup backend only"
	@echo "  make setup-frontend - Setup frontend only"
	@echo ""
	@echo "Database Commands:"
	@echo "  make db-check       - Check database health"
	@echo "  make db-reset       - Reset database (WARNING: deletes all data)"
	@echo "  make db-migrate     - Run database migrations"
	@echo ""
	@echo "Service Commands:"
	@echo "  make start          - Start all services"
	@echo "  make stop           - Stop all services"
	@echo "  make clean          - Clean up temporary files and caches"
	@echo ""

# Complete setup for new machines
setup: setup-backend setup-frontend
	@echo ""
	@echo "✅ Setup complete!"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Edit backend/.env.local and add your API keys"
	@echo "  2. Run: make db-check"
	@echo "  3. Run: make db-migrate"
	@echo "  4. Run: make start"
	@echo ""

# Backend setup
setup-backend:
	@echo "🔧 Setting up backend..."
	@docker compose --env-file .env.local up -d db redis
	@echo "⏳ Waiting for database to be ready..."
	@sleep 5
	@cd backend && python -m venv .venv
	@cd backend && .venv/bin/pip install --upgrade pip
	@cd backend && .venv/bin/pip install -r requirements.txt
	@if [ ! -f backend/.env.local ]; then \
		cp backend/.env.local.example backend/.env.local; \
		echo "📝 Created backend/.env.local - please configure it"; \
	fi
	@echo "🔐 Setting up auth database permissions..."
	@cd backend && .venv/bin/python -c "from app.core.auth_database import auth_db_path; import os; auth_db_path.parent.mkdir(parents=True, exist_ok=True); os.chmod(auth_db_path.parent, 0o755); print('✅ Auth database directory permissions set')"
	@echo "✅ Backend setup complete"

# Frontend setup
setup-frontend:
	@echo "🔧 Setting up frontend..."
	@cd trainer-web && npm install
	@echo "✅ Frontend setup complete"

# Check database health
db-check:
	@echo "🔍 Checking database health..."
	@cd backend && .venv/bin/python scripts/check_database.py

# Reset database (with confirmation)
db-reset:
	@echo "⚠️  WARNING: This will delete all data!"
	@cd backend && .venv/bin/python scripts/reset_database.py

# Run database migrations
db-migrate:
	@echo "🔄 Setting up database schema..."
	@cd backend && .venv/bin/alembic upgrade head
	@cd backend && .venv/bin/python scripts/check_database.py
	@echo "✅ Database setup complete"

# Start all services
start:
	@echo "🚀 Starting services..."
	@docker compose --env-file .env.local up -d db redis
	@echo ""
	@echo "Services started! Open separate terminals and run:"
	@echo ""
	@echo "Terminal 1 (API):"
	@echo "  cd backend && source .venv/bin/activate && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --env-file .env.local"
	@echo "  (For development with auto-reload: use --reload instead of --workers 1)"
	@echo ""
	@echo "Terminal 2 (Training Worker):"
	@echo "  cd backend && source .venv/bin/activate && python -m app.workers.runner"
	@echo ""
	@echo "Terminal 3 (Frontend):"
	@echo "  cd trainer-web && npm run dev"
	@echo ""

# Stop all services
stop:
	@echo "🛑 Stopping services..."
	@docker compose --env-file .env.local down
	@pkill -f "uvicorn app.main" || true
	@pkill -f "python -m app.workers.runner" || true
	@pkill -f "vite dev" || true
	@echo "✅ All services stopped"

# Clean up
clean:
	@echo "🧹 Cleaning up..."
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@rm -rf backend/.venv 2>/dev/null || true
	@rm -rf trainer-web/node_modules 2>/dev/null || true
	@rm -rf trainer-web/.svelte-kit 2>/dev/null || true
	@echo "✅ Cleanup complete"
