"""
Configuration file generator module.
Dynamically generates .env files, docker-compose.yml, and service configs
based on user selections from the wizard UI.
"""

import os
import secrets
import string
import json
import logging
import copy
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default values matching .env.local.example
# ---------------------------------------------------------------------------

DEFAULT_ENV = {
    # Database
    "POSTGRES_USER": "qgen_user",
    "POSTGRES_PASSWORD": "qgen_password",
    "POSTGRES_DB": "qgen_db",
    "POSTGRES_PORT": "5432",
    # Redis
    "REDIS_PORT": "6379",
    # Security
    "SECRET_KEY": "",
    "ACCESS_TOKEN_EXPIRE_MINUTES": "60",
    "REFRESH_TOKEN_EXPIRE_DAYS": "30",
    # LLM
    "LLM_PROVIDER": "ollama",
    "OLLAMA_BASE_URL": "http://host.docker.internal:11434",
    "OLLAMA_MODEL": "llama3.1:8b",
    "GEMINI_API_KEY": "",
    "GEMINI_MODEL": "gemini-2.0-flash",
    "GEMINI_MAX_OUTPUT_TOKENS": "2048",
    "GEMINI_SAFETY_BLOCK_NONE": "true",
    "DEEPSEEK_API_KEY": "",
    "DEEPSEEK_MODEL": "deepseek-chat",
    "DEEPSEEK_BASE_URL": "https://api.deepseek.com/v1",
    # Embedding
    "EMBEDDING_MODEL": "nomic-embed-text",
    "EMBEDDING_DIMENSION": "768",
    "EMBEDDING_USE_INSTRUCTION": "false",
    "EMBEDDING_REDIS_CACHE": "true",
    "EMBEDDING_CACHE_TTL": "604800",
    # Reranker
    "RERANKER_MODEL": "mixedbread-ai/mxbai-rerank-large-v1",
    "RERANKER_ENABLED": "true",
    # Auth DB
    "AUTH_DATABASE_URL": "sqlite+aiosqlite:///./auth.db",
    # Document processing
    "MAX_UPLOAD_SIZE_MB": "500",
    "CHUNK_SIZE": "1000",
    "CHUNK_OVERLAP": "200",
    "MAX_QUESTIONS_PER_REQUEST": "50",
    # Rate limiting
    "RATE_LIMIT_REQUESTS": "100",
    "RATE_LIMIT_WINDOW_SECONDS": "3600",
    # Logging
    "LOG_LEVEL": "info",
    "LOG_JSON": "false",
    "ENABLE_METRICS": "true",
    # Ports
    "API_PORT": "8000",
    # CORS
    "CORS_ORIGINS": "*",
    # Client
    "DEV_MACHINE_IP": "10.0.0.4",
    "USE_SIMULATOR": "false",
    "PRODUCTION_API_URL": "http://10.0.0.4:8000/api/v1",
    "USE_PRODUCTION_API": "false",
    # Training
    "TRAINING_DATA_DIR": "./training_data",
    "LORA_ADAPTERS_DIR": "./lora_adapters",
    "TRAINING_BASE_MODEL": "deepseek-ai/DeepSeek-R1-Distill-Llama-1.7B",
}

# Environment variable metadata for the wizard UI
ENV_SCHEMA = [
    {
        "group": "Database",
        "icon": "database",
        "description": "PostgreSQL with pgvector for vector similarity search",
        "vars": [
            {"key": "POSTGRES_USER", "label": "Database User", "type": "text",
             "tooltip": "PostgreSQL username for the application database."},
            {"key": "POSTGRES_PASSWORD", "label": "Database Password", "type": "password",
             "tooltip": "PostgreSQL password. Use a strong password in production."},
            {"key": "POSTGRES_DB", "label": "Database Name", "type": "text",
             "tooltip": "Name of the PostgreSQL database to create/use."},
            {"key": "POSTGRES_PORT", "label": "PostgreSQL Port", "type": "number",
             "tooltip": "Port for PostgreSQL. Default 5432."},
        ],
    },
    {
        "group": "Redis",
        "icon": "zap",
        "description": "Redis for caching, sessions, and rate limiting",
        "vars": [
            {"key": "REDIS_PORT", "label": "Redis Port", "type": "number",
             "tooltip": "Port for Redis server. Default 6379."},
        ],
    },
    {
        "group": "Security",
        "icon": "shield",
        "description": "Authentication and security settings",
        "vars": [
            {"key": "SECRET_KEY", "label": "Secret Key", "type": "password",
             "tooltip": "JWT signing key. Must be at least 32 characters. Auto-generated if left empty."},
            {"key": "ACCESS_TOKEN_EXPIRE_MINUTES", "label": "Access Token Expiry (min)", "type": "number",
             "tooltip": "How long access tokens remain valid, in minutes."},
            {"key": "REFRESH_TOKEN_EXPIRE_DAYS", "label": "Refresh Token Expiry (days)", "type": "number",
             "tooltip": "How long refresh tokens remain valid, in days."},
        ],
    },
    {
        "group": "LLM Provider",
        "icon": "brain",
        "description": "Choose your LLM backend: local Ollama, Google Gemini, or DeepSeek",
        "vars": [
            {"key": "LLM_PROVIDER", "label": "Provider", "type": "select",
             "options": ["ollama", "gemini", "deepseek"],
             "tooltip": "Select the LLM provider. Ollama runs locally; Gemini and DeepSeek are cloud APIs."},
            {"key": "OLLAMA_BASE_URL", "label": "Ollama Base URL", "type": "text",
             "tooltip": "URL for your Ollama instance. Use host.docker.internal for Docker access to local Ollama.",
             "show_if": {"LLM_PROVIDER": "ollama"}},
            {"key": "OLLAMA_MODEL", "label": "Ollama Model", "type": "text",
             "tooltip": "Which Ollama model to use for question generation.",
             "show_if": {"LLM_PROVIDER": "ollama"}},
            {"key": "GEMINI_API_KEY", "label": "Gemini API Key", "type": "password",
             "tooltip": "Your Google Gemini API key from aistudio.google.com/apikey",
             "show_if": {"LLM_PROVIDER": "gemini"}},
            {"key": "GEMINI_MODEL", "label": "Gemini Model", "type": "select",
             "options": ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"],
             "tooltip": "Which Gemini model to use.",
             "show_if": {"LLM_PROVIDER": "gemini"}},
            {"key": "GEMINI_MAX_OUTPUT_TOKENS", "label": "Gemini Max Tokens", "type": "number",
             "tooltip": "Maximum output tokens per Gemini response.",
             "show_if": {"LLM_PROVIDER": "gemini"}},
            {"key": "DEEPSEEK_API_KEY", "label": "DeepSeek API Key", "type": "password",
             "tooltip": "Your DeepSeek API key from platform.deepseek.com",
             "show_if": {"LLM_PROVIDER": "deepseek"}},
            {"key": "DEEPSEEK_MODEL", "label": "DeepSeek Model", "type": "select",
             "options": ["deepseek-chat", "deepseek-reasoner"],
             "tooltip": "Which DeepSeek model to use.",
             "show_if": {"LLM_PROVIDER": "deepseek"}},
            {"key": "DEEPSEEK_BASE_URL", "label": "DeepSeek Base URL", "type": "text",
             "tooltip": "DeepSeek API endpoint URL.",
             "show_if": {"LLM_PROVIDER": "deepseek"}},
        ],
    },
    {
        "group": "Embedding & Reranker",
        "icon": "search",
        "description": "Models for document embedding and search reranking",
        "vars": [
            {"key": "EMBEDDING_MODEL", "label": "Embedding Model", "type": "text",
             "tooltip": "Sentence-transformer or Ollama embedding model name."},
            {"key": "EMBEDDING_DIMENSION", "label": "Embedding Dimension", "type": "number",
             "tooltip": "Vector dimension of the embedding model. Must match the model's output."},
            {"key": "EMBEDDING_USE_INSTRUCTION", "label": "Use Instruction Prefix", "type": "select",
             "options": ["false", "true"],
             "tooltip": "Enable for BGE-style models that need instruction prefixes."},
            {"key": "EMBEDDING_REDIS_CACHE", "label": "Redis Embedding Cache", "type": "select",
             "options": ["true", "false"],
             "tooltip": "Cache embeddings in Redis for faster subsequent lookups."},
            {"key": "RERANKER_MODEL", "label": "Reranker Model", "type": "text",
             "tooltip": "Cross-encoder model for search result reranking."},
            {"key": "RERANKER_ENABLED", "label": "Enable Reranker", "type": "select",
             "options": ["true", "false"],
             "tooltip": "Toggle cross-encoder reranking. Improves retrieval quality but adds latency."},
        ],
    },
    {
        "group": "Document Processing",
        "icon": "file-text",
        "description": "File upload and text chunking settings",
        "vars": [
            {"key": "MAX_UPLOAD_SIZE_MB", "label": "Max Upload Size (MB)", "type": "number",
             "tooltip": "Maximum file upload size in megabytes."},
            {"key": "CHUNK_SIZE", "label": "Chunk Size (tokens)", "type": "number",
             "tooltip": "Size of text chunks for the RAG pipeline."},
            {"key": "CHUNK_OVERLAP", "label": "Chunk Overlap (tokens)", "type": "number",
             "tooltip": "Overlap between consecutive chunks for context continuity."},
            {"key": "MAX_QUESTIONS_PER_REQUEST", "label": "Max Questions per Request", "type": "number",
             "tooltip": "Maximum number of questions that can be generated in one request."},
        ],
    },
    {
        "group": "Rate Limiting & Logging",
        "icon": "activity",
        "description": "API rate limiting and monitoring configuration",
        "vars": [
            {"key": "RATE_LIMIT_REQUESTS", "label": "Rate Limit (requests)", "type": "number",
             "tooltip": "Maximum requests per window per user."},
            {"key": "RATE_LIMIT_WINDOW_SECONDS", "label": "Rate Limit Window (sec)", "type": "number",
             "tooltip": "Duration of the rate limit window in seconds."},
            {"key": "LOG_LEVEL", "label": "Log Level", "type": "select",
             "options": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
             "tooltip": "Application logging verbosity."},
            {"key": "LOG_JSON", "label": "JSON Logs", "type": "select",
             "options": ["false", "true"],
             "tooltip": "Use structured JSON logs (recommended for production)."},
            {"key": "ENABLE_METRICS", "label": "Prometheus Metrics", "type": "select",
             "options": ["true", "false"],
             "tooltip": "Enable /metrics endpoint for Prometheus scraping."},
        ],
    },
    {
        "group": "Network & CORS",
        "icon": "globe",
        "description": "API port and cross-origin resource sharing",
        "vars": [
            {"key": "API_PORT", "label": "API Port", "type": "number",
             "tooltip": "Port for the FastAPI backend server."},
            {"key": "CORS_ORIGINS", "label": "CORS Origins", "type": "text",
             "tooltip": "Allowed CORS origins. Use * for development, restrict in production."},
        ],
    },
    {
        "group": "Mobile Client",
        "icon": "smartphone",
        "description": "Expo React Native client configuration",
        "vars": [
            {"key": "DEV_MACHINE_IP", "label": "Dev Machine IP", "type": "text",
             "tooltip": "Your machine's local IP address for mobile dev (used by Expo)."},
            {"key": "USE_SIMULATOR", "label": "Use Simulator", "type": "select",
             "options": ["false", "true"],
             "tooltip": "Set to true if testing on iOS Simulator / Android Emulator."},
            {"key": "PRODUCTION_API_URL", "label": "Production API URL", "type": "text",
             "tooltip": "Full URL to the production API endpoint."},
            {"key": "USE_PRODUCTION_API", "label": "Use Production API", "type": "select",
             "options": ["false", "true"],
             "tooltip": "Toggle between local and production API for the mobile client."},
        ],
    },
    {
        "group": "Training Pipeline",
        "icon": "cpu",
        "description": "LoRA fine-tuning configuration (requires GPU)",
        "vars": [
            {"key": "TRAINING_DATA_DIR", "label": "Training Data Directory", "type": "text",
             "tooltip": "Path to store exported SFT/DPO training JSONL files."},
            {"key": "LORA_ADAPTERS_DIR", "label": "LoRA Adapters Directory", "type": "text",
             "tooltip": "Path to store LoRA adapter checkpoints."},
            {"key": "TRAINING_BASE_MODEL", "label": "Base Model (HuggingFace)", "type": "text",
             "tooltip": "HuggingFace model ID for the base model to fine-tune."},
        ],
    },
]


def generate_secret_key(length: int = 64) -> str:
    """Generate a cryptographically secure secret key."""
    alphabet = string.ascii_letters + string.digits + "-_"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def build_env_values(user_config: Dict[str, str]) -> Dict[str, str]:
    """Merge user config over defaults, auto-generate secret key if needed."""
    env = copy.deepcopy(DEFAULT_ENV)
    env.update({k: v for k, v in user_config.items() if v is not None and v != ""})

    if not env.get("SECRET_KEY"):
        env["SECRET_KEY"] = generate_secret_key()

    return env


def generate_env_file(env_values: Dict[str, str]) -> str:
    """Generate the contents of a .env.local file."""
    sections = [
        ("Database", ["POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB", "POSTGRES_PORT"]),
        ("Redis", ["REDIS_PORT"]),
        ("Security", ["SECRET_KEY", "ACCESS_TOKEN_EXPIRE_MINUTES", "REFRESH_TOKEN_EXPIRE_DAYS"]),
        ("LLM Provider", ["LLM_PROVIDER"]),
        ("Ollama", ["OLLAMA_BASE_URL", "OLLAMA_MODEL"]),
        ("Gemini API", ["GEMINI_API_KEY", "GEMINI_MODEL", "GEMINI_MAX_OUTPUT_TOKENS", "GEMINI_SAFETY_BLOCK_NONE"]),
        ("DeepSeek API", ["DEEPSEEK_API_KEY", "DEEPSEEK_MODEL", "DEEPSEEK_BASE_URL"]),
        ("Embedding", ["EMBEDDING_MODEL", "EMBEDDING_DIMENSION", "EMBEDDING_USE_INSTRUCTION",
                        "EMBEDDING_REDIS_CACHE", "EMBEDDING_CACHE_TTL"]),
        ("Reranker", ["RERANKER_MODEL", "RERANKER_ENABLED"]),
        ("Auth Database", ["AUTH_DATABASE_URL"]),
        ("Document Processing", ["MAX_UPLOAD_SIZE_MB", "CHUNK_SIZE", "CHUNK_OVERLAP",
                                  "MAX_QUESTIONS_PER_REQUEST"]),
        ("Rate Limiting", ["RATE_LIMIT_REQUESTS", "RATE_LIMIT_WINDOW_SECONDS"]),
        ("Logging & Monitoring", ["LOG_LEVEL", "LOG_JSON", "ENABLE_METRICS"]),
        ("API Port", ["API_PORT"]),
        ("CORS", ["CORS_ORIGINS"]),
        ("Mobile Client", ["DEV_MACHINE_IP", "USE_SIMULATOR", "PRODUCTION_API_URL", "USE_PRODUCTION_API"]),
        ("Training Pipeline", ["TRAINING_DATA_DIR", "LORA_ADAPTERS_DIR", "TRAINING_BASE_MODEL"]),
    ]

    lines = ["# Generated by QGen RAG Setup Wizard", ""]

    for section_name, keys in sections:
        lines.append(f"# {'=' * 60}")
        lines.append(f"# {section_name}")
        lines.append(f"# {'=' * 60}")
        for key in keys:
            val = env_values.get(key, "")
            lines.append(f"{key}={val}")
        lines.append("")

    return "\n".join(lines)


def generate_client_env(env_values: Dict[str, str]) -> str:
    """Generate client/.env.local for Expo."""
    ip = env_values.get("DEV_MACHINE_IP", "10.0.0.4")
    sim = env_values.get("USE_SIMULATOR", "false")
    prod_url = env_values.get("PRODUCTION_API_URL", f"http://{ip}:8000/api/v1")
    use_prod = env_values.get("USE_PRODUCTION_API", "false")

    return (
        "# Auto-generated by QGen RAG Setup Wizard\n"
        "# DO NOT commit this file\n\n"
        f"EXPO_PUBLIC_DEV_MACHINE_IP={ip}\n"
        f"EXPO_PUBLIC_USE_SIMULATOR={sim}\n"
        f"EXPO_PUBLIC_PRODUCTION_API_URL={prod_url}\n"
        f"EXPO_PUBLIC_USE_PRODUCTION_API={use_prod}\n"
    )


def generate_trainer_web_env(env_values: Dict[str, str]) -> str:
    """Generate trainer-web/.env.local for SvelteKit."""
    port = env_values.get("API_PORT", "8000")
    return (
        "# Auto-generated by QGen RAG Setup Wizard\n"
        f"VITE_API_BASE=http://localhost:{port}/api/v1\n"
    )


def generate_docker_compose(
    docker_config: Dict[str, Any],
    env_values: Dict[str, str],
) -> str:
    """Generate docker-compose.yml dynamically based on user selections."""

    services_enabled = docker_config.get("services", {})
    deployment_mode = docker_config.get("mode", "development")
    custom_ports = docker_config.get("ports", {})
    custom_names = docker_config.get("container_names", {})
    custom_volumes = docker_config.get("volume_names", {})
    custom_network = docker_config.get("network_name", "qgen_net")

    pg_port = custom_ports.get("db", env_values.get("POSTGRES_PORT", "5432"))
    redis_port = custom_ports.get("redis", env_values.get("REDIS_PORT", "6379"))
    api_port = custom_ports.get("api", env_values.get("API_PORT", "8000"))

    db_name = custom_names.get("db", "qgen_db")
    redis_name = custom_names.get("redis", "qgen_redis")
    api_name = custom_names.get("api", "qgen_api")
    ollama_name = custom_names.get("ollama", "qgen_ollama")

    postgres_vol = custom_volumes.get("postgres_data", "qgen_postgres_data")
    redis_vol = custom_volumes.get("redis_data", "qgen_redis_data")
    upload_vol = custom_volumes.get("upload_data", "qgen_upload_data")
    model_vol = custom_volumes.get("model_cache", "qgen_model_cache")
    ollama_vol = custom_volumes.get("ollama_data", "qgen_ollama_data")

    lines = [
        "# Generated by QGen RAG Setup Wizard",
        f"# Mode: {deployment_mode}",
        "",
        "services:",
    ]

    # ---- PostgreSQL ----
    if services_enabled.get("db", True):
        lines.extend([
            "  db:",
            "    image: pgvector/pgvector:pg16",
            f"    container_name: {db_name}",
            "    restart: unless-stopped",
            "    environment:",
            f"      POSTGRES_USER: ${{POSTGRES_USER:-{env_values.get('POSTGRES_USER', 'qgen_user')}}}",
            f"      POSTGRES_PASSWORD: ${{POSTGRES_PASSWORD:-{env_values.get('POSTGRES_PASSWORD', 'qgen_password')}}}",
            f"      POSTGRES_DB: ${{POSTGRES_DB:-{env_values.get('POSTGRES_DB', 'qgen_db')}}}",
            '      POSTGRES_INITDB_ARGS: "--encoding=UTF8 --locale=C"',
            "    volumes:",
            f"      - {postgres_vol}:/var/lib/postgresql/data",
            "      - ./backend/init_db.sql:/docker-entrypoint-initdb.d/init.sql:ro",
            "    ports:",
            f'      - "${{{f"POSTGRES_PORT:-{pg_port}"}}}:{pg_port}"',
            "    networks:",
            f"      - {custom_network}",
            "    healthcheck:",
            "      test:",
            "        [",
            '          "CMD-SHELL",',
            f'          "pg_isready -U ${{POSTGRES_USER:-{env_values.get("POSTGRES_USER", "qgen_user")}}} -d ${{POSTGRES_DB:-{env_values.get("POSTGRES_DB", "qgen_db")}}}",',
            "        ]",
            "      interval: 10s",
            "      timeout: 5s",
            "      retries: 5",
            "      start_period: 10s",
            "    deploy:",
            "      resources:",
            "        limits:",
            "          memory: 2G",
            "        reservations:",
            "          memory: 512M",
            "",
        ])

    # ---- Redis ----
    if services_enabled.get("redis", True):
        lines.extend([
            "  redis:",
            "    image: redis:7-alpine",
            f"    container_name: {redis_name}",
            "    restart: unless-stopped",
            "    command: >",
            "      redis-server",
            "      --appendonly yes",
            "      --maxmemory 512mb",
            "      --maxmemory-policy allkeys-lru",
            "      --save 60 1000",
            "    volumes:",
            f"      - {redis_vol}:/data",
            "    ports:",
            f'      - "${{{f"REDIS_PORT:-{redis_port}"}}}:{redis_port}"',
            "    networks:",
            f"      - {custom_network}",
            "    healthcheck:",
            '      test: ["CMD", "redis-cli", "ping"]',
            "      interval: 10s",
            "      timeout: 5s",
            "      retries: 5",
            "      start_period: 5s",
            "    deploy:",
            "      resources:",
            "        limits:",
            "          memory: 512M",
            "        reservations:",
            "          memory: 128M",
            "",
        ])

    # ---- Ollama (optional) ----
    if services_enabled.get("ollama", False):
        lines.extend([
            "  ollama:",
            "    image: ollama/ollama:latest",
            f"    container_name: {ollama_name}",
            "    restart: unless-stopped",
            "    volumes:",
            f"      - {ollama_vol}:/root/.ollama",
            "    ports:",
            '      - "11434:11434"',
            "    networks:",
            f"      - {custom_network}",
            "",
        ])

    # ---- API ----
    if services_enabled.get("api", True):
        reload_flag = "--reload" if deployment_mode == "development" else ""
        workers = "1" if deployment_mode == "development" else "4"
        log_json = "false" if deployment_mode == "development" else "true"

        cmd_parts = [
            "uvicorn app.main:app",
            "--host 0.0.0.0",
            f"--port {api_port}",
        ]
        if deployment_mode == "development":
            cmd_parts.append("--reload")
        else:
            cmd_parts.append(f"--workers {workers}")
        cmd_parts.append("--log-level ${LOG_LEVEL:-info}")
        cmd_str = "\n      ".join(cmd_parts)

        lines.extend([
            "  api:",
            "    build:",
            "      context: ./backend",
            "      dockerfile: Dockerfile",
            "      args:",
            "        - PYTHON_VERSION=3.11",
            f"    container_name: {api_name}",
            "    restart: unless-stopped",
            "    env_file: .env.local",
            "    command: >",
            f"      {cmd_str}",
            "    extra_hosts:",
            '      - "host.docker.internal:host-gateway"',
            "    volumes:",
        ])

        if deployment_mode == "development":
            lines.append("      - ./backend:/app")

        lines.extend([
            f"      - {upload_vol}:/app/uploads",
            f"      - {model_vol}:/root/.cache",
            "    environment:",
        ])

        api_env_lines = [
            f"      - DATABASE_URL=postgresql+asyncpg://${{POSTGRES_USER:-{env_values.get('POSTGRES_USER', 'qgen_user')}}}:${{POSTGRES_PASSWORD:-{env_values.get('POSTGRES_PASSWORD', 'qgen_password')}}}@db:5432/${{POSTGRES_DB:-{env_values.get('POSTGRES_DB', 'qgen_db')}}}",
            "      - REDIS_URL=redis://redis:6379/0",
            "      - LLM_PROVIDER=${LLM_PROVIDER:-ollama}",
            "      - OLLAMA_BASE_URL=${OLLAMA_BASE_URL:-http://host.docker.internal:11434}",
            "      - OLLAMA_MODEL=${OLLAMA_MODEL:-llama3.1:8b}",
            "      - GEMINI_API_KEY=${GEMINI_API_KEY:-}",
            "      - GEMINI_MODEL=${GEMINI_MODEL:-gemini-2.0-flash}",
            "      - GEMINI_MAX_OUTPUT_TOKENS=${GEMINI_MAX_OUTPUT_TOKENS:-2048}",
            "      - GEMINI_SAFETY_BLOCK_NONE=${GEMINI_SAFETY_BLOCK_NONE:-true}",
            "      - SECRET_KEY=${SECRET_KEY:-change-me}",
            "      - ACCESS_TOKEN_EXPIRE_MINUTES=${ACCESS_TOKEN_EXPIRE_MINUTES:-60}",
            "      - REFRESH_TOKEN_EXPIRE_DAYS=${REFRESH_TOKEN_EXPIRE_DAYS:-30}",
            "      - UPLOAD_DIR=/app/uploads",
            "      - MAX_UPLOAD_SIZE_MB=${MAX_UPLOAD_SIZE_MB:-500}",
            "      - EMBEDDING_MODEL=${EMBEDDING_MODEL:-nomic-embed-text}",
            "      - EMBEDDING_DIMENSION=${EMBEDDING_DIMENSION:-768}",
            "      - EMBEDDING_USE_INSTRUCTION=${EMBEDDING_USE_INSTRUCTION:-false}",
            "      - EMBEDDING_REDIS_CACHE=${EMBEDDING_REDIS_CACHE:-true}",
            "      - EMBEDDING_CACHE_TTL=${EMBEDDING_CACHE_TTL:-604800}",
            "      - RERANKER_MODEL=${RERANKER_MODEL:-mixedbread-ai/mxbai-rerank-large-v1}",
            "      - RERANKER_ENABLED=${RERANKER_ENABLED:-true}",
            "      - MAX_QUESTIONS_PER_REQUEST=${MAX_QUESTIONS_PER_REQUEST:-50}",
            "      - CHUNK_SIZE=${CHUNK_SIZE:-1000}",
            "      - CHUNK_OVERLAP=${CHUNK_OVERLAP:-200}",
            "      - LOG_LEVEL=${LOG_LEVEL:-INFO}",
            f"      - LOG_JSON={log_json}",
            "      - ENABLE_METRICS=${ENABLE_METRICS:-true}",
            "      - RATE_LIMIT_REQUESTS=${RATE_LIMIT_REQUESTS:-100}",
            "      - RATE_LIMIT_WINDOW_SECONDS=${RATE_LIMIT_WINDOW_SECONDS:-3600}",
            "      - CORS_ORIGINS=${CORS_ORIGINS:-*}",
        ]
        lines.extend(api_env_lines)

        lines.extend([
            "    ports:",
            f'      - "${{API_PORT:-{api_port}}}:{api_port}"',
            "    depends_on:",
        ])

        if services_enabled.get("db", True):
            lines.extend([
                "      db:",
                "        condition: service_healthy",
            ])
        if services_enabled.get("redis", True):
            lines.extend([
                "      redis:",
                "        condition: service_healthy",
            ])

        lines.extend([
            "    networks:",
            f"      - {custom_network}",
            "    deploy:",
            "      resources:",
            "        limits:",
            "          memory: 4G",
            "        reservations:",
            "          memory: 1G",
            "",
        ])

    # ---- Volumes ----
    lines.extend(["", "volumes:"])
    if services_enabled.get("db", True):
        lines.extend([f"  postgres_data:", f"    name: {postgres_vol}", ""])
    if services_enabled.get("redis", True):
        lines.extend([f"  redis_data:", f"    name: {redis_vol}", ""])
    if services_enabled.get("api", True):
        lines.extend([
            f"  upload_data:", f"    name: {upload_vol}", "",
            f"  model_cache:", f"    name: {model_vol}", "",
        ])
    if services_enabled.get("ollama", False):
        lines.extend([f"  ollama_data:", f"    name: {ollama_vol}", ""])

    # ---- Networks ----
    lines.extend([
        "",
        "networks:",
        f"  {custom_network}:",
        f"    name: {custom_network}",
        "    driver: bridge",
        "",
    ])

    return "\n".join(lines)


def write_configs(
    project_root: str,
    env_values: Dict[str, str],
    docker_config: Dict[str, Any],
) -> Dict[str, str]:
    """Write all configuration files. Returns dict of filename -> status."""
    root = Path(project_root)
    results = {}

    # .env.local
    env_content = generate_env_file(env_values)
    env_path = root / ".env.local"
    env_path.write_text(env_content)
    results[".env.local"] = "written"
    logger.info("Wrote %s", env_path)

    # client/.env.local
    client_env = generate_client_env(env_values)
    client_env_path = root / "client" / ".env.local"
    client_env_path.parent.mkdir(parents=True, exist_ok=True)
    client_env_path.write_text(client_env)
    results["client/.env.local"] = "written"
    logger.info("Wrote %s", client_env_path)

    # trainer-web/.env.local
    trainer_env = generate_trainer_web_env(env_values)
    trainer_env_path = root / "trainer-web" / ".env.local"
    trainer_env_path.parent.mkdir(parents=True, exist_ok=True)
    trainer_env_path.write_text(trainer_env)
    results["trainer-web/.env.local"] = "written"
    logger.info("Wrote %s", trainer_env_path)

    # docker-compose.yml (only if Docker deployment enabled)
    if docker_config.get("enabled", True):
        compose = generate_docker_compose(docker_config, env_values)
        compose_path = root / "docker-compose.yml"
        compose_path.write_text(compose)
        results["docker-compose.yml"] = "written"
        logger.info("Wrote %s", compose_path)

    return results
