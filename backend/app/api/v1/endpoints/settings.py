"""
System settings API endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_database import get_auth_db
from app.models.system_settings import (
    SystemSettings,
    SETTING_SIGNUP_ENABLED,
    SETTING_PROVIDER_GENERATION_CONFIG,
    DEFAULT_SETTINGS,
)
from app.models.user import User, ROLE_ADMIN
from app.api.v1.deps import get_current_user
from app.services.provider_service import get_provider_service


router = APIRouter()


class SignupSettingsResponse(BaseModel):
    signup_enabled: bool


class SignupSettingsUpdate(BaseModel):
    signup_enabled: bool


class ProviderGenerationItem(BaseModel):
    key: str = Field(..., min_length=1, max_length=60)
    name: str = Field(..., min_length=1, max_length=100)
    base_url: str = Field(..., min_length=1, max_length=500)
    enabled: bool = True
    questions_per_batch: int = Field(default=10, ge=1, le=1000)
    model: str = Field(default="", max_length=100)
    api_key: str = Field(default="", max_length=500)


class ProviderGenerationSettingsResponse(BaseModel):
    generation_batch_size: int
    providers: list[ProviderGenerationItem]


class ProviderGenerationSettingsUpdate(BaseModel):
    providers: list[ProviderGenerationItem]


async def get_setting(db: AsyncSession, key: str) -> dict:
    """Get a setting value, returning default if not found."""
    result = await db.execute(
        select(SystemSettings).where(SystemSettings.key == key)
    )
    setting = result.scalar_one_or_none()
    if setting and setting.value:
        return setting.value
    return DEFAULT_SETTINGS.get(key, {})


async def set_setting(db: AsyncSession, key: str, value: dict, user_id: str) -> SystemSettings:
    """Set a setting value, creating or updating as needed."""
    result = await db.execute(
        select(SystemSettings).where(SystemSettings.key == key)
    )
    setting = result.scalar_one_or_none()
    
    if setting:
        setting.value = value
        setting.updated_by = user_id
    else:
        setting = SystemSettings(
            key=key,
            value=value,
            updated_by=user_id,
        )
        db.add(setting)
    
    await db.commit()
    await db.refresh(setting)
    return setting


def _normalize_provider_items(items: list[ProviderGenerationItem]) -> list[dict]:
    normalized: list[dict] = []
    seen: set[str] = set()

    for item in items:
        key = (item.key or "").strip().lower()
        if not key:
            continue
        if key in seen:
            continue
        seen.add(key)

        normalized.append(
            {
                "key": key,
                "name": (item.name or "").strip() or key,
                "base_url": (item.base_url or "").strip().rstrip("/"),
                "enabled": bool(item.enabled),
                "questions_per_batch": int(item.questions_per_batch),
                "model": (item.model or "").strip(),
                "api_key": (item.api_key or "").strip(),
            }
        )

    return normalized


def _provider_settings_response(value: dict) -> ProviderGenerationSettingsResponse:
    providers_raw = value.get("providers") or []
    providers: list[ProviderGenerationItem] = []

    for provider in providers_raw:
        if not isinstance(provider, dict):
            continue
        providers.append(
            ProviderGenerationItem(
                key=str(provider.get("key") or "unknown"),
                name=str(provider.get("name") or provider.get("key") or "Provider"),
                base_url=str(provider.get("base_url") or ""),
                enabled=bool(provider.get("enabled", True)),
                questions_per_batch=int(provider.get("questions_per_batch", 10) or 10),
                model=str(provider.get("model") or ""),
                api_key=str(provider.get("api_key") or ""),
            )
        )

    generation_batch_size = sum(
        int(p.questions_per_batch) for p in providers if p.enabled
    )

    return ProviderGenerationSettingsResponse(
        generation_batch_size=generation_batch_size,
        providers=providers,
    )


@router.get("/signup", response_model=SignupSettingsResponse)
async def get_signup_settings(
    db: AsyncSession = Depends(get_auth_db),
):
    """
    Get signup settings (public endpoint).
    """
    value = await get_setting(db, SETTING_SIGNUP_ENABLED)
    return SignupSettingsResponse(
        signup_enabled=value.get("enabled", True)
    )


@router.put("/signup", response_model=SignupSettingsResponse)
async def update_signup_settings(
    update: SignupSettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_auth_db),
):
    """
    Update signup settings (admin only).
    """
    if current_user.role != ROLE_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can update signup settings",
        )
    
    await set_setting(
        db,
        SETTING_SIGNUP_ENABLED,
        {"enabled": update.signup_enabled},
        current_user.id,
    )
    
    return SignupSettingsResponse(signup_enabled=update.signup_enabled)


@router.get("/providers-generation", response_model=ProviderGenerationSettingsResponse)
async def get_provider_generation_settings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_auth_db),
):
    """Get provider generation controls (admin only)."""
    if current_user.role != ROLE_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can view provider generation settings",
        )

    value = await get_setting(db, SETTING_PROVIDER_GENERATION_CONFIG)
    return _provider_settings_response(value)


@router.put("/providers-generation", response_model=ProviderGenerationSettingsResponse)
async def update_provider_generation_settings(
    update: ProviderGenerationSettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_auth_db),
):
    """Update provider generation controls (admin only)."""
    if current_user.role != ROLE_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can update provider generation settings",
        )

    normalized_providers = _normalize_provider_items(update.providers)
    if not normalized_providers:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one provider configuration is required",
        )

    # Ensure at least one provider is enabled
    enabled_count = sum(1 for p in normalized_providers if p.get("enabled", False))
    if enabled_count == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one provider must be enabled",
        )

    value = {
        "providers": normalized_providers,
    }

    await set_setting(
        db,
        SETTING_PROVIDER_GENERATION_CONFIG,
        value,
        current_user.id,
    )

    # Invalidate provider service cache so new settings take effect immediately
    get_provider_service().invalidate_cache()

    return _provider_settings_response(value)
