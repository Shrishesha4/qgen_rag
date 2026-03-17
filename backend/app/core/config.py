"""
Application configuration using Pydantic Settings.
"""

from typing import List
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # API routing prefix
    API_PREFIX: str = Field(default="/api/v1")

    # Database (PostgreSQL + pgvector for vector data)
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://qgen_user:qgen_password@localhost:5432/qgen_db"
    )
    
    # Auth Database (SQLite for user/auth data, decoupled from pgvector)
    AUTH_DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./auth.db"
    )

    # Redis
    REDIS_URL: str = Field(default="redis://localhost:6379/0")

    # JWT Authentication
    SECRET_KEY: str = Field(default="your-super-secret-key-change-in-production")
    ALGORITHM: str = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=30)

    # LLM Provider Configuration
    # Options: "ollama", "gemini", "deepseek"
    LLM_PROVIDER: str = Field(default="deepseek")
    
    # Ollama LLM (local)
    OLLAMA_BASE_URL: str = Field(default="http://localhost:11434")
    OLLAMA_MODEL: str = Field(default="llama3.1:8b")
    
    # Google Gemini API (cloud)
    GEMINI_API_KEY: str = Field(default="")  # Get from aistudio.google.com/apikey
    GEMINI_MODEL: str = Field(default="gemini-2.0-flash")  # Options: gemini-2.0-flash, gemini-1.5-pro, gemini-1.5-flash
    GEMINI_MAX_OUTPUT_TOKENS: int = Field(default=2048)
    GEMINI_SAFETY_BLOCK_NONE: bool = Field(default=True)  # Disable safety filters for educational content

    # DeepSeek API (cloud, OpenAI-compatible)
    DEEPSEEK_API_KEY: str = Field(default="")  # Get from platform.deepseek.com
    DEEPSEEK_MODEL: str = Field(default="deepseek-chat")  # Options: deepseek-chat, deepseek-reasoner
    DEEPSEEK_BASE_URL: str = Field(default="https://api.deepseek.com/v1")

    # File Upload
    UPLOAD_DIR: str = Field(default="./uploads")
    MAX_UPLOAD_SIZE_MB: int = Field(default=500)
    ALLOWED_EXTENSIONS: List[str] = Field(default=[".pdf", ".docx", ".txt", ".xlsx", ".csv"])

    # Rate Limiting
    RATE_LIMIT_REQUESTS: int = Field(default=100)
    RATE_LIMIT_WINDOW_SECONDS: int = Field(default=3600)

    # CORS - Allow the mobile app and tunnel domain
    # React Native apps don't send Origin header, so "*" is needed
    # Comma-separated list: "*,https://yourdomain.com,https://app.example.com"
    CORS_ORIGINS: str = Field(default="*")

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS_ORIGINS from comma-separated string to list."""
        if not self.CORS_ORIGINS:
            return ["*"]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    # Embedding Model (via Ollama API)
    # nomic-embed-text: 768 dims, 8192 context window, excellent quality
    EMBEDDING_MODEL: str = Field(default="nomic-embed-text")
    EMBEDDING_DIMENSION: int = Field(default=768)
    
    # Set to True to use instruction-based embedding (recommended for bge models)
    EMBEDDING_USE_INSTRUCTION: bool = Field(default=False)
    EMBEDDING_QUERY_INSTRUCTION: str = Field(default="Represent this sentence for searching relevant passages:")
    EMBEDDING_DOCUMENT_INSTRUCTION: str = Field(default="")
    
    # Embedding Cache Settings
    # L1 cache is always in-memory LRU
    # L2 cache uses Redis for persistence across restarts
    EMBEDDING_REDIS_CACHE: bool = Field(default=True)   # Enable Redis L2 cache
    EMBEDDING_CACHE_TTL: int = Field(default=604800)    # 7 days in seconds

    # Reranker Model (Cross-encoder for retrieval refinement)
    # v1 = BERT-based, loads in seconds. v2 = Qwen2 LLM, very slow to load.
    RERANKER_MODEL: str = Field(default="mixedbread-ai/mxbai-rerank-large-v1")
    RERANKER_ENABLED: bool = Field(default=True)

    # Question Generation
    MAX_QUESTIONS_PER_REQUEST: int = Field(default=50)
    CHUNK_SIZE: int = Field(default=1500)
    CHUNK_OVERLAP: int = Field(default=300)

    # OCR Settings (for scanned PDFs)
    OCR_ENABLED: bool = Field(default=True)
    OCR_MIN_TEXT_PER_PAGE: int = Field(default=50)  # Min chars per page to consider it has text
    OCR_SPARSE_THRESHOLD: float = Field(default=0.3)  # If <30% of pages have text, consider it scanned
    OCR_LANGUAGE: str = Field(default="eng")  # Tesseract language code
    OCR_MAX_RETRIES: int = Field(default=2)  # Number of OCR retries on failure
    OCR_DPI: int = Field(default=300)  # DPI for rendering PDF pages to images

    # Logging & Monitoring
    LOG_LEVEL: str = Field(default="INFO")  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    LOG_JSON: bool = Field(default=False)    # True for production (structured JSON logs)
    ENABLE_METRICS: bool = Field(default=True)  # Enable Prometheus metrics endpoint

    # Training and Promotion Gates
    PROMOTION_MIN_OFFLINE_PASS_RATE: float = Field(default=0.8)
    PROMOTION_MAX_CANARY_APPROVE_DROP: float = Field(default=0.02)
    PROMOTION_MAX_CRITICAL_REJECT_INCREASE: float = Field(default=0.01)
    PROMOTION_MAX_P95_LATENCY_MS: int = Field(default=2500)
    PROMOTION_MAX_TIMEOUT_RATE: float = Field(default=0.02)

    # Queue + Worker Controls
    QUEUE_BACKEND: str = Field(default="redis")  # redis | celery
    QUEUE_MAX_RETRIES: int = Field(default=3)
    QUEUE_RETRY_BACKOFF_SECONDS: int = Field(default=30)
    QUEUE_DEAD_LETTER_PREFIX: str = Field(default="dlq")

    # Generation Controls
    ENABLE_TWO_PASS_GENERATION: bool = Field(default=False)
    GENERATION_SCHEMA_ENFORCEMENT: bool = Field(default=True)
    QUICK_GENERATE_PARALLEL_WORKERS: int = Field(default=1)
    QUESTION_DEDUPE_SIMILARITY_THRESHOLD: float = Field(default=0.85)
    QUESTION_OPTION_SIMILARITY_THRESHOLD: float = Field(default=0.96)

    # Server
    API_HOST: str = Field(default="0.0.0.0")
    API_PORT: int = Field(default=8000)

    # Training Pipeline (LoRA fine-tuning)
    TRAINING_DATA_DIR: str = Field(default="./training_data")
    LORA_ADAPTERS_DIR: str = Field(default="./lora_adapters")
    TRAINING_BASE_MODEL: str = Field(default="deepseek-ai/DeepSeek-R1-Distill-Llama-1.7B")

    # Docker Configuration
    DOCKER_ENABLED: bool = Field(default=True)
    DOCKER_MODE: str = Field(default="development")  # development | production
    DOCKER_COMPOSE_COMMAND: str = Field(default="docker compose")
    
    # Docker Network Configuration
    DOCKER_NETWORK_NAME: str = Field(default="qgen_net")
    
    # Docker Container Names
    DOCKER_DB_CONTAINER_NAME: str = Field(default="qgen_db")
    DOCKER_REDIS_CONTAINER_NAME: str = Field(default="qgen_redis")
    DOCKER_API_CONTAINER_NAME: str = Field(default="qgen_api")
    DOCKER_TRAINER_WEB_CONTAINER_NAME: str = Field(default="qgen_trainer")
    DOCKER_CLIENT_CONTAINER_NAME: str = Field(default="qgen_client")
    DOCKER_OLLAMA_CONTAINER_NAME: str = Field(default="qgen_ollama")
    
    # Docker Volume Names
    DOCKER_POSTGRES_VOLUME_NAME: str = Field(default="qgen_postgres_data")
    DOCKER_REDIS_VOLUME_NAME: str = Field(default="qgen_redis_data")
    DOCKER_UPLOAD_VOLUME_NAME: str = Field(default="qgen_upload_data")
    DOCKER_MODEL_CACHE_VOLUME_NAME: str = Field(default="qgen_model_cache")
    DOCKER_OLLAMA_VOLUME_NAME: str = Field(default="qgen_ollama_data")
    
    # Docker Service Ports
    DOCKER_DB_PORT: int = Field(default=5432)
    DOCKER_REDIS_PORT: int = Field(default=6379)
    DOCKER_API_PORT: int = Field(default=8000)
    DOCKER_TRAINER_WEB_PORT: int = Field(default=5173)
    DOCKER_CLIENT_PORT: int = Field(default=8081)
    DOCKER_OLLAMA_PORT: int = Field(default=11434)
    
    # Docker Services Control
    DOCKER_ENABLE_DB: bool = Field(default=True)
    DOCKER_ENABLE_REDIS: bool = Field(default=True)
    DOCKER_ENABLE_API: bool = Field(default=True)
    DOCKER_ENABLE_TRAINER_WEB: bool = Field(default=True)
    DOCKER_ENABLE_CLIENT: bool = Field(default=True)
    DOCKER_ENABLE_OLLAMA: bool = Field(default=False)
    
    # Docker Development Settings
    DOCKER_DEV_HOT_RELOAD: bool = Field(default=True)
    DOCKER_DEV_MOUNT_SOURCES: bool = Field(default=True)
    DOCKER_DEV_DEBUG_MODE: bool = Field(default=False)
    
    # Docker Production Settings
    DOCKER_PROD_WORKERS: int = Field(default=4)
    DOCKER_PROD_MAX_REQUESTS: int = Field(default=1000)
    DOCKER_PROD_MAX_REQUESTS_JITTER: int = Field(default=100)
    
    # Docker Resource Limits
    DOCKER_DB_MEMORY_LIMIT: str = Field(default="2G")
    DOCKER_DB_MEMORY_RESERVATION: str = Field(default="512M")
    DOCKER_REDIS_MEMORY_LIMIT: str = Field(default="512M")
    DOCKER_REDIS_MEMORY_RESERVATION: str = Field(default="128M")
    DOCKER_API_MEMORY_LIMIT: str = Field(default="4G")
    DOCKER_API_MEMORY_RESERVATION: str = Field(default="1G")
    
    # Docker Health Check Settings
    DOCKER_HEALTH_CHECK_ENABLED: bool = Field(default=True)
    DOCKER_HEALTH_CHECK_INTERVAL: int = Field(default=10)  # seconds
    DOCKER_HEALTH_CHECK_TIMEOUT: int = Field(default=5)   # seconds
    DOCKER_HEALTH_CHECK_RETRIES: int = Field(default=5)
    DOCKER_HEALTH_CHECK_START_PERIOD: int = Field(default=10)  # seconds
    
    # Frontend Development Settings
    FRONTEND_DEV_SERVER_HOST: str = Field(default="0.0.0.0")
    FRONTEND_DEV_AUTO_OPEN_BROWSER: bool = Field(default=False)
    FRONTEND_DEV_HMR_OVERLAY: bool = Field(default=True)
    
    # Mobile Client Development
    MOBILE_DEV_USE_SIMULATOR: bool = Field(default=False)
    MOBILE_DEV_MACHINE_IP: str = Field(default="localhost")
    MOBILE_DEV_PRODUCTION_API_URL: str = Field(default="")
    MOBILE_DEV_USE_PRODUCTION_API: bool = Field(default=False)

    class Config:
        # Load .env first (dev defaults), then .env.local overrides (secrets).
        # Actual environment variables always take highest priority.
        env_file = (".env", ".env.local")
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()
