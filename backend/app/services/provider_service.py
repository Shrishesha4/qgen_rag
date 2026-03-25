"""
Provider Service for dynamic multi-provider LLM management.

Reads provider configuration from the database and distributes
question generation work across enabled providers based on their
configured questions_per_batch allocation.
"""

import logging
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_database import AuthSessionLocal
from app.models.system_settings import (
    SystemSettings,
    SETTING_PROVIDER_GENERATION_CONFIG,
    DEFAULT_SETTINGS,
)
from app.services.llm_service import LLMProvider


logger = logging.getLogger(__name__)


def _normalize_openai_base_url(base_url: str) -> str:
    """Normalize OpenAI-compatible base URLs to provider roots.

    Some provider configs are saved as full endpoint URLs (for example,
    https://api.x.ai/v1/chat/completions). The DeepSeek-compatible client
    appends /chat/completions itself, so endpoint suffixes must be stripped.
    """
    normalized = (base_url or "").strip().rstrip("/")
    if not normalized:
        return normalized

    for suffix in ("/chat/completions", "/completions"):
        if normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)].rstrip("/")
            break

    return normalized


@dataclass
class ProviderConfig:
    """Configuration for a single LLM provider."""
    key: str
    name: str
    base_url: str
    enabled: bool = True
    questions_per_batch: int = 10
    model: str = ""
    api_key: str = ""

    def __post_init__(self):
        self.key = (self.key or "").strip().lower()
        self.name = (self.name or self.key).strip()
        self.base_url = (self.base_url or "").strip().rstrip("/")
        if self.key not in {"ollama", "gemini"}:
            self.base_url = _normalize_openai_base_url(self.base_url)
        self.model = (self.model or "").strip()
        self.api_key = (self.api_key or "").strip()

    def get_api_key(self) -> Optional[str]:
        """Get API key from provider config."""
        return self.api_key


@dataclass
class GenerationBatchConfig:
    """Configuration for a generation batch."""
    generation_batch_size: int = 30
    providers: List[ProviderConfig] = field(default_factory=list)

    @property
    def enabled_providers(self) -> List[ProviderConfig]:
        """Return only enabled providers."""
        return [p for p in self.providers if p.enabled]

    @property
    def total_questions_per_cycle(self) -> int:
        """Total questions generated per full provider cycle."""
        return sum(p.questions_per_batch for p in self.enabled_providers)


@dataclass
class ProviderAllocation:
    """Allocation of questions to a specific provider."""
    provider: ProviderConfig
    question_count: int


class ProviderService:
    """
    Service for managing LLM providers and distributing generation work.
    
    Reads configuration from the database (system_settings table) and
    provides methods for:
    - Getting the current provider configuration
    - Allocating questions across providers for a batch
    - Creating LLM service instances for specific providers
    """

    def __init__(self):
        self._cached_config: Optional[GenerationBatchConfig] = None
        self._cache_valid = False

    def invalidate_cache(self) -> None:
        """Invalidate the cached configuration."""
        self._cache_valid = False
        self._cached_config = None

    async def get_config(self, force_refresh: bool = False) -> GenerationBatchConfig:
        """
        Get the current provider configuration from the database.
        
        Args:
            force_refresh: If True, bypass cache and fetch fresh config.
            
        Returns:
            GenerationBatchConfig with all provider settings.
        """
        if self._cache_valid and self._cached_config and not force_refresh:
            return self._cached_config

        async with AuthSessionLocal() as db:
            result = await db.execute(
                select(SystemSettings).where(
                    SystemSettings.key == SETTING_PROVIDER_GENERATION_CONFIG
                )
            )
            setting = result.scalar_one_or_none()

        if setting and setting.value:
            raw_config = setting.value
        else:
            raw_config = DEFAULT_SETTINGS.get(SETTING_PROVIDER_GENERATION_CONFIG, {})

        providers = []
        for p in raw_config.get("providers", []):
            if not isinstance(p, dict):
                continue
            providers.append(
                ProviderConfig(
                    key=str(p.get("key", "unknown")),
                    name=str(p.get("name", p.get("key", "Provider"))),
                    base_url=str(p.get("base_url", "")),
                    enabled=bool(p.get("enabled", True)),
                    questions_per_batch=int(p.get("questions_per_batch", 10) or 10),
                    model=str(p.get("model", "")),
                    api_key=str(p.get("api_key", "")),
                )
            )

        computed_batch_size = sum(
            int(p.questions_per_batch) for p in providers if p.enabled
        )

        config = GenerationBatchConfig(
            generation_batch_size=computed_batch_size,
            providers=providers,
        )

        self._cached_config = config
        self._cache_valid = True
        return config

    async def get_enabled_providers(self) -> List[ProviderConfig]:
        """Get list of enabled providers."""
        config = await self.get_config()
        return config.enabled_providers

    async def allocate_batch(
        self,
        total_questions: int,
    ) -> List[ProviderAllocation]:
        """
        Allocate a batch of questions across enabled providers.
        
        Uses each provider's questions_per_batch as a weight to distribute
        the total questions proportionally.
        
        Args:
            total_questions: Total number of questions to generate.
            
        Returns:
            List of ProviderAllocation with provider and question count.
            
        Raises:
            ValueError: If no enabled providers are configured.
        """
        config = await self.get_config()
        enabled = config.enabled_providers

        if not enabled:
            raise ValueError(
                "No enabled providers configured. At least one provider must be enabled."
            )

        # Calculate total weight (sum of questions_per_batch)
        total_weight = sum(p.questions_per_batch for p in enabled)
        if total_weight == 0:
            # Fallback: distribute evenly
            total_weight = len(enabled)
            for p in enabled:
                p.questions_per_batch = 1

        allocations: List[ProviderAllocation] = []
        remaining = total_questions

        # Allocate proportionally
        for i, provider in enumerate(enabled):
            if i == len(enabled) - 1:
                # Last provider gets the remainder
                count = remaining
            else:
                # Proportional allocation
                count = int(total_questions * provider.questions_per_batch / total_weight)
                count = min(count, remaining)

            if count > 0:
                allocations.append(ProviderAllocation(provider=provider, question_count=count))
                remaining -= count

        # If we have remaining questions (due to rounding), add to first provider
        if remaining > 0 and allocations:
            allocations[0] = ProviderAllocation(
                provider=allocations[0].provider,
                question_count=allocations[0].question_count + remaining,
            )

        logger.info(
            f"Allocated {total_questions} questions across {len(allocations)} providers: "
            f"{[(a.provider.key, a.question_count) for a in allocations]}"
        )

        return allocations

    def create_llm_service(
        self,
        provider: ProviderConfig,
        model_override: Optional[str] = None,
    ) -> Tuple[LLMProvider, Dict[str, Any]]:
        """
        Create an LLM service instance for a specific provider.
        
        Args:
            provider: The provider configuration.
            model_override: Optional model override (uses provider.model if not set).
            
        Returns:
            Tuple of (LLMProvider instance, metadata dict for tracking).
        """
        from app.core.config import settings

        provider_key = provider.key.lower()
        model = model_override or provider.model
        api_key = provider.get_api_key()
        normalized_base_url = provider.base_url

        metadata = {
            "provider_key": provider_key,
            "provider": provider_key,
            "llm_provider": provider_key,
            "base_url": provider.base_url,
            "llm_model": model,
        }

        # Handle Ollama (local, no API key needed)
        if provider_key == "ollama" or "localhost:11434" in provider.base_url:
            from app.services.llm_service import OllamaLLMService
            # Override base URL if custom
            if provider.base_url and provider.base_url != settings.OLLAMA_BASE_URL:
                service = _create_ollama_service(provider.base_url, model or settings.OLLAMA_MODEL)
            else:
                service = OllamaLLMService(model=model or None)
            metadata["llm_model"] = model or settings.OLLAMA_MODEL
            logger.info(f"Created OllamaLLMService for provider={provider_key}")
            return service, metadata

        # Handle Gemini
        if provider_key == "gemini" or "generativelanguage.googleapis.com" in provider.base_url:
            from app.services.gemini_service import GeminiService
            service = GeminiService(model=model or None, api_key=api_key or None)
            metadata["llm_model"] = model or settings.GEMINI_MODEL
            logger.info(f"Created GeminiService for provider={provider_key}")
            return service, metadata

        # For OpenAI-compatible providers (deepseek, openrouter, custom, etc.)
        normalized_base_url = _normalize_openai_base_url(provider.base_url)
        metadata["base_url"] = normalized_base_url

        if not api_key:
            logger.warning(
                f"No API key configured for provider {provider_key}. "
                "Set the key in Admin Settings > Provider Controls."
            )

        # Create a custom OpenAI-compatible service with the provider's base_url
        service = _create_openai_compatible_service(
            base_url=normalized_base_url,
            api_key=api_key or "",
            model=model or settings.DEEPSEEK_MODEL,
            provider_key=provider_key,
        )

        metadata["llm_model"] = model or settings.DEEPSEEK_MODEL
        logger.info(f"Created OpenAI-compatible service for provider={provider_key}, base_url={normalized_base_url}")

        return service, metadata


def _create_ollama_service(base_url: str, model: str) -> LLMProvider:
    """Create an Ollama service with custom base URL."""
    from app.services.llm_service import OllamaLLMService

    class CustomOllamaService(OllamaLLMService):
        def __init__(self, custom_base_url: str, custom_model: str):
            super().__init__(model=custom_model)
            self.base_url = custom_base_url.rstrip("/")

    return CustomOllamaService(base_url, model)


def _create_openai_compatible_service(
    base_url: str,
    api_key: str,
    model: Optional[str] = None,
    provider_key: str = "custom",
) -> LLMProvider:
    """
    Create an OpenAI-compatible LLM service with custom base_url.
    
    This is a factory function that creates a DeepSeekService-like instance
    but with a custom base URL for providers like OpenRouter, Together, etc.
    """
    from app.services.deepseek_service import DeepSeekService
    from app.core.config import settings

    # Create a modified DeepSeekService with custom base_url
    class CustomOpenAIService(DeepSeekService):
        """OpenAI-compatible service with custom base URL."""

        def __init__(
            self,
            custom_base_url: str,
            custom_api_key: str,
            custom_model: Optional[str] = None,
            custom_provider_key: str = "custom",
        ):
            # Store custom values before calling parent init
            self._custom_base_url = _normalize_openai_base_url(custom_base_url)
            self._custom_api_key = custom_api_key
            self._custom_model = custom_model or settings.DEEPSEEK_MODEL
            self._custom_provider_key = custom_provider_key

            # Override settings temporarily for parent init
            self.api_key = self._custom_api_key
            self.model = self._custom_model
            self.base_url = self._custom_base_url

            # Skip parent __init__ validation if no API key
            # (we'll handle errors at call time)
            import httpx
            self._timeout = httpx.Timeout(
                connect=10.0,
                read=120.0,
                write=10.0,
                pool=5.0,
            )
            self._total_tokens_used = 0
            self._total_calls = 0

            logger.info(
                f"CustomOpenAIService initialized - "
                f"provider={custom_provider_key}, base_url={self.base_url}, model={self.model}"
            )

    return CustomOpenAIService(
        custom_base_url=base_url,
        custom_api_key=api_key,
        custom_model=model,
        custom_provider_key=provider_key,
    )


# Singleton instance for convenience
_provider_service: Optional[ProviderService] = None


def get_provider_service() -> ProviderService:
    """Get or create the singleton ProviderService instance."""
    global _provider_service
    if _provider_service is None:
        _provider_service = ProviderService()
    return _provider_service


async def create_question_service_for_provider(
    db,
    provider: ProviderConfig,
    embedding_service=None,
    redis_service=None,
    document_service=None,
    reranker_service=None,
    novelty_service=None,
):
    """
    Create a QuestionGenerationService configured for a specific provider.
    
    This is a convenience function for multi-provider batch generation.
    
    Args:
        db: Database session
        provider: Provider configuration from ProviderService
        Other args: Optional service overrides
        
    Returns:
        QuestionGenerationService configured with the provider's LLM service
    """
    from app.services.question_service import QuestionGenerationService

    provider_svc = get_provider_service()
    llm_service, metadata = provider_svc.create_llm_service(provider)

    return QuestionGenerationService(
        db=db,
        embedding_service=embedding_service,
        llm_service=llm_service,
        redis_service=redis_service,
        document_service=document_service,
        reranker_service=reranker_service,
        novelty_service=novelty_service,
        provider_metadata=metadata,
    )
