# 🔧 Environment Configuration Guide

This guide explains how to configure and run the QGen RAG system using environment variables and Docker Compose.

## 📋 Overview

The system now uses **individual environment variables** instead of hardcoded database credentials and port configurations. This provides:

- 🔒 **Security**: No hardcoded passwords in code
- 🐳 **Docker Integration**: Seamless container orchestration
- 🔧 **Flexibility**: Easy configuration for different environments
- 🚀 **Portability**: Run anywhere with minimal setup

## 🚀 Quick Start

### 1. Automated Setup (Recommended)

```bash
# Clone the repository
git clone <repository-url>
cd qgen_rag

# Run the automated setup
python scripts/setup_env.py

# Follow the prompts to complete setup
```

### 2. Manual Setup

```bash
# Copy the environment template
cp .env.template .env.local

# Edit the configuration
nano .env.local

# Validate the configuration
python scripts/validate_config.py

# Start services
docker-compose --env-file .env.local up -d
```

## 📁 Configuration Files

| File | Purpose | Usage |
|------|---------|--------|
| `.env.template` | Complete configuration template | Copy to `.env.local` and customize |
| `.env.docker.example` | Docker-specific variables | For Docker Compose reference |
| `.env.local` | **Your actual configuration** | **Never commit this file** |
| `docker-compose.yml` | Development services | Uses `.env.local` |
| `docker-compose.env.yml` | Full environment config | Alternative to default compose |
| `docker-compose.prod.yml` | Production overrides | Production deployment |

## 🔐 Environment Variables

### Database Configuration

```bash
# PostgreSQL Database
POSTGRES_HOST=localhost          # Database host (use 'db' in Docker)
POSTGRES_PORT=5432              # Database port
POSTGRES_USER=qgen_user         # Database username
POSTGRES_PASSWORD=secure_pass   # Database password (change this!)
POSTGRES_DB=qgen_db             # Database name
```

### Redis Configuration

```bash
# Redis Cache
REDIS_HOST=localhost            # Redis host (use 'redis' in Docker)
REDIS_PORT=6379                # Redis port
REDIS_DB=0                     # Redis database number
REDIS_PASSWORD=redis_pass      # Redis password (optional)
REDIS_MAX_MEMORY=512mb         # Redis memory limit
```

### API Configuration

```bash
# FastAPI Backend
API_HOST=0.0.0.0              # API host
API_PORT=8000                  # API port
API_WORKERS=1                  # Number of worker processes
API_RELOAD=true                # Auto-reload in development
SECRET_KEY=your_secret_key     # JWT secret (change this!)
```

### LLM Provider Configuration

```bash
# Choose your LLM provider
LLM_PROVIDER=deepseek           # Options: ollama, gemini, deepseek

# Ollama (Local)
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=llama3.1:8b

# Gemini (Google Cloud)
GEMINI_API_KEY=your_gemini_key
GEMINI_MODEL=gemini-2.0-flash

# DeepSeek (Cloud API)
DEEPSEEK_API_KEY=your_deepseek_key
DEEPSEEK_MODEL=deepseek-chat
```

## 🐳 Docker Compose Usage

### Development

```bash
# Start development services
docker-compose --env-file .env.local up -d

# View logs
docker-compose --env-file .env.local logs -f

# Stop services
docker-compose --env-file .env.local down
```

### Production

```bash
# Start production services
docker-compose --env-file .env.local -f docker-compose.yml -f docker-compose.prod.yml up -d

# Or use the full environment config
docker-compose -f docker-compose.env.yml --env-file .env.local up -d
```

### With Monitoring

```bash
# Start with monitoring stack
docker-compose --env-file .env.local --profile monitoring up -d

# Access Grafana: http://localhost:3000 (admin/admin)
# Access Prometheus: http://localhost:9090
```

## 📊 Port Configuration

| Service | Default Port | Environment Variable | Notes |
|---------|--------------|---------------------|-------|
| PostgreSQL | 5432 | `POSTGRES_PORT` | Internal Docker port |
| Redis | 6379 | `REDIS_PORT` | Internal Docker port |
| FastAPI | 8000 | `API_PORT` | External API port |
| Trainer Web | 5173 | `TRAINER_WEB_PORT` | Frontend port |
| Grafana | 3000 | `GRAFANA_PORT` | Monitoring UI |
| Prometheus | 9090 | `PROMETHEUS_PORT` | Metrics API |

## 🔍 Configuration Validation

### Validate Your Setup

```bash
# Validate environment configuration
python scripts/validate_config.py

# Validate with specific file
python scripts/validate_config.py --env-file .env.local

# Generate docker-compose command
python scripts/validate_config.py --generate
```

### Common Validation Issues

1. **Missing Variables**: Ensure all required variables are set
2. **Port Conflicts**: Check that ports don't overlap
3. **Weak Passwords**: Use strong, unique passwords
4. **File Permissions**: Ensure directories are readable/writable
5. **Docker Issues**: Verify Docker is installed and running

## 🛠️ Advanced Configuration

### Custom Docker Compose Files

Create your own Docker Compose configuration:

```bash
# Use custom compose file
docker-compose -f my-compose.yml --env-file .env.local up -d
```

### Environment-Specific Configs

Create different configs for different environments:

```bash
# Development
cp .env.template .env.dev
# Edit .env.dev for development settings

# Production  
cp .env.template .env.prod
# Edit .env.prod for production settings

# Use specific environment
docker-compose --env-file .env.dev up -d
```

### Resource Limits

Configure memory and CPU limits:

```bash
# API Service
API_MIN_MEMORY=1G
API_MAX_MEMORY=4G
API_MIN_CPUS=0.5
API_MAX_CPUS=2

# Web Service
WEB_MIN_MEMORY=256M
WEB_MAX_MEMORY=1G

# Redis
REDIS_MAX_MEMORY=1gb
```

## 🔒 Security Best Practices

### 1. Never Commit Secrets

```bash
# Add .env.local to .gitignore
echo ".env.local" >> .gitignore

# Ensure it's not tracked
git rm --cached .env.local 2>/dev/null || true
```

### 2. Use Strong Passwords

```bash
# Generate secure passwords
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 3. Environment-Specific Keys

```bash
# Development
SECRET_KEY=dev_key_change_in_production

# Production
SECRET_KEY=$(openssl rand -base64 64)
```

### 4. Network Security

```bash
# Use internal Docker networking
# Services communicate via service names (db, redis)
# Not exposed to host unless explicitly mapped
```

## 🚨 Troubleshooting

### Common Issues

1. **Port Already in Use**
   ```bash
   # Check what's using the port
   lsof -i :8000
   
   # Change the port in .env.local
   API_PORT=8001
   ```

2. **Database Connection Failed**
   ```bash
   # Check database service
   docker-compose --env-file .env.local ps db
   
   # Check database logs
   docker-compose --env-file .env.local logs db
   ```

3. **Permission Denied**
   ```bash
   # Fix directory permissions
   sudo chown -R $USER:$USER ./uploads ./training_data ./lora_adapters
   chmod 755 ./uploads ./training_data ./lora_adapters
   ```

4. **Docker Issues**
   ```bash
   # Reset Docker
   docker-compose --env-file .env.local down -v
   docker system prune -f
   docker-compose --env-file .env.local up -d
   ```

### Debug Mode

Enable debug logging:

```bash
# Set debug mode
LOG_LEVEL=debug
LOG_JSON=false

# Restart services
docker-compose --env-file .env.local up -d
```

### Health Checks

Check service health:

```bash
# Check all services
docker-compose --env-file .env.local ps

# Check specific service
docker-compose --env-file .env.local exec api curl http://localhost:8000/health
```

## 📚 Additional Resources

- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Environment Variables Best Practices](https://12factor.net/config)
- [PostgreSQL Configuration](https://www.postgresql.org/docs/)
- [Redis Configuration](https://redis.io/docs/)

## 🆘 Getting Help

If you encounter issues:

1. **Check the logs**: `docker-compose --env-file .env.local logs`
2. **Validate config**: `python scripts/validate_config.py`
3. **Check permissions**: Ensure directories are accessible
4. **Verify Docker**: Ensure Docker is running properly
5. **Review environment**: Check all required variables are set

---

**🎉 Your QGen RAG system is now configured with secure, flexible environment variables!**
