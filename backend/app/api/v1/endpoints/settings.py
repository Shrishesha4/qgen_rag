"""System settings API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user
from app.core.auth_database import get_auth_db
from app.models.system_settings import (
    PASSWORD_RESET_METHOD_SECURITY_QUESTION,
    PASSWORD_RESET_METHOD_SMTP,
    SETTING_SIGNUP_ENABLED,
    SETTING_STUDENT_SIGNUP_ENABLED,
    SETTING_PROVIDER_GENERATION_CONFIG,
    SystemSettings,
    DEFAULT_SETTINGS,
)
from app.models.user import ROLE_ADMIN, User
from app.schemas.auth import MessageResponse
from app.services.email_service import EmailService
from app.services.provider_service import get_provider_service
from app.services.system_settings_service import (
    get_password_reset_settings,
    get_setting,
    set_setting,
    update_password_reset_settings,
)


router = APIRouter()


class SignupSettingsResponse(BaseModel):
    signup_enabled: bool
    student_signup_enabled: bool


class SignupSettingsUpdate(BaseModel):
    signup_enabled: bool | None = None
    student_signup_enabled: bool | None = None


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


class GenerationLimitsResponse(BaseModel):
    max_batch_size: int


class SMTPSettingsPayload(BaseModel):
    host: str = ""
    port: int = 587
    username: str = ""
    password: str = ""
    from_email: str = ""
    from_name: str = "VQuest"
    use_tls: bool = True
    use_ssl: bool = False
    timeout_seconds: int = Field(default=20, ge=1)
    password_reset_url_template: str = ""


class PasswordResetPublicSettingsResponse(BaseModel):
    method: str


class PasswordResetSettingsResponse(BaseModel):
    method: str
    smtp: SMTPSettingsPayload
    smtp_password_set: bool = False


class PasswordResetSettingsUpdate(BaseModel):
    method: str
    smtp: SMTPSettingsPayload


class PasswordResetTestEmailRequest(BaseModel):
    email: EmailStr | None = None


def _ensure_admin(current_user: User) -> None:
    if current_user.role != ROLE_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can update settings",
        )


def _validate_password_reset_method(method: str) -> str:
    normalized = (method or "").strip().lower()
    if normalized not in {PASSWORD_RESET_METHOD_SMTP, PASSWORD_RESET_METHOD_SECURITY_QUESTION}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid password reset method",
        )
    return normalized


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
    """Get signup settings (public endpoint)."""
    value = await get_setting(db, SETTING_SIGNUP_ENABLED)
    student_value = await get_setting(db, SETTING_STUDENT_SIGNUP_ENABLED)
    return SignupSettingsResponse(
        signup_enabled=value.get("enabled", True),
        student_signup_enabled=student_value.get("enabled", False),
    )


@router.put("/signup", response_model=SignupSettingsResponse)
async def update_signup_settings(
    update: SignupSettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_auth_db),
):
    """Update signup settings (admin only)."""
    _ensure_admin(current_user)

    current_signup = await get_setting(db, SETTING_SIGNUP_ENABLED)
    current_student_signup = await get_setting(db, SETTING_STUDENT_SIGNUP_ENABLED)

    new_signup_enabled = update.signup_enabled
    if new_signup_enabled is None:
        new_signup_enabled = current_signup.get("enabled", True)

    new_student_signup_enabled = update.student_signup_enabled
    if new_student_signup_enabled is None:
        new_student_signup_enabled = current_student_signup.get("enabled", False)

    await set_setting(
        db,
        SETTING_SIGNUP_ENABLED,
        {"enabled": new_signup_enabled},
        current_user.id,
        description="Whether public signup is enabled",
    )

    await set_setting(
        db,
        SETTING_STUDENT_SIGNUP_ENABLED,
        {"enabled": new_student_signup_enabled},
        current_user.id,
    )

    return SignupSettingsResponse(
        signup_enabled=new_signup_enabled,
        student_signup_enabled=new_student_signup_enabled,
    )


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


@router.get("/generation-limits", response_model=GenerationLimitsResponse)
async def get_generation_limits(
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_auth_db),
):
    """Return generation limits for authenticated users."""
    value = await get_setting(db, SETTING_PROVIDER_GENERATION_CONFIG)
    provider_settings = _provider_settings_response(value)
    return GenerationLimitsResponse(max_batch_size=provider_settings.generation_batch_size)


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


@router.get("/password-reset", response_model=PasswordResetPublicSettingsResponse)
async def get_password_reset_public_settings(
    db: AsyncSession = Depends(get_auth_db),
):
    """Get the currently active public password-reset method."""
    value = await get_password_reset_settings(db, include_secret=False)
    return PasswordResetPublicSettingsResponse(method=value["method"])


@router.get("/password-reset/admin", response_model=PasswordResetSettingsResponse)
async def get_password_reset_admin_settings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_auth_db),
):
    """Get full password-reset settings for the admin panel."""
    _ensure_admin(current_user)
    value = await get_password_reset_settings(db, include_secret=False)
    return PasswordResetSettingsResponse(**value)


@router.put("/password-reset/admin", response_model=PasswordResetSettingsResponse)
async def update_password_reset_admin_settings(
    update: PasswordResetSettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_auth_db),
):
    """Update password-reset strategy and SMTP settings (admin only)."""
    _ensure_admin(current_user)
    method = _validate_password_reset_method(update.method)
    value = await update_password_reset_settings(
        db,
        {"method": method, "smtp": update.smtp.model_dump()},
        current_user.id,
    )
    return PasswordResetSettingsResponse(**value)


@router.post("/password-reset/admin/test", response_model=MessageResponse)
async def send_password_reset_test_email(
    payload: PasswordResetTestEmailRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_auth_db),
):
    """Send a test email using the currently saved SMTP configuration."""
    _ensure_admin(current_user)
    value = await get_password_reset_settings(db, include_secret=True)
    email_service = EmailService(config=value["smtp"])
    if not email_service.config["host"] or not email_service.config["from_email"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SMTP host and from email are required before sending a test email",
        )

    target_email = payload.email or current_user.email
    await email_service.send_test_email(to_email=target_email)
    return MessageResponse(message=f"Test email sent to {target_email}")
