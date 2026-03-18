"""
Application configuration using Pydantic Settings.
"""

from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # API routing prefix
    API_PREFIX: str = Field(default="/api/v1")

    # Database (PostgreSQL + pgvector for vector data)
    # Individual database connection parameters for Docker Compose
    POSTGRES_HOST: str = Field(default="localhost")
    POSTGRES_PORT: int = Field(default=5432)
    POSTGRES_USER: str = Field(default="qgen_user")
    POSTGRES_PASSWORD: str = Field(default="qgen_password")
    POSTGRES_DB: str = Field(default="qgen_db")
    
    @property
    def DATABASE_URL(self) -> str:
        """Construct database URL from individual components."""
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
    
    # Auth Database (SQLite for user/auth data, decoupled from pgvector)
    AUTH_DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./auth.db"
    )

    # Redis
    # Individual Redis connection parameters for Docker Compose
    REDIS_HOST: str = Field(default="localhost")
    REDIS_PORT: int = Field(default=6379)
    REDIS_DB: int = Field(default=0)
    REDIS_PASSWORD: Optional[str] = Field(default=None)
    
    @property
    def REDIS_URL(self) -> str:
        """Construct Redis URL from individual components."""
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

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
    QUEUE_MAX_RETRIES: int = Field(default=3)
    QUEUE_DEAD_LETTER_PREFIX: str = Field(default="dlq")

    # Generation Controls
    ENABLE_TWO_PASS_GENERATION: bool = Field(default=False)
    GENERATION_SCHEMA_ENFORCEMENT: bool = Field(default=True)
    QUICK_GENERATE_PARALLEL_WORKERS: int = Field(default=6)
    QUESTION_DEDUPE_SIMILARITY_THRESHOLD: float = Field(default=0.987)
    QUESTION_OPTION_SIMILARITY_THRESHOLD: float = Field(default=0.877)

    # Server
    API_PORT: int = Field(default=8000)
    
    # Training Pipeline (LoRA fine-tuning)
    TRAINING_DATA_DIR: str = Field(default="./training_data")
    LORA_ADAPTERS_DIR: str = Field(default="./lora_adapters")
    TRAINING_BASE_MODEL: str = Field(default="deepseek-ai/DeepSeek-R1-Distill-Llama-1.7B")


    class Config:
        # Load .env first (dev defaults), then .env.local overrides (secrets).
        # Actual environment variables always take highest priority.
        env_file = (".env", ".env.local")
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()
