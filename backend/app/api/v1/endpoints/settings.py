"""System settings API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user
from app.core.auth_database import get_auth_db
from app.models.system_settings import (
    PASSWORD_RESET_METHOD_SECURITY_QUESTION,
    PASSWORD_RESET_METHOD_SMTP,
    SETTING_SIGNUP_ENABLED,
    SETTING_PROVIDER_GENERATION_CONFIG,
    SETTING_EMAIL_DOMAIN_RESTRICTION,
    DEFAULT_BACKGROUND_GENERATION_CONCURRENCY,
    DEFAULT_SETTINGS,
    MAX_BACKGROUND_GENERATION_CONCURRENCY,
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
    domain_restriction_enabled: bool = False
    allowed_domains: list[str] = []


class SignupSettingsUpdate(BaseModel):
    signup_enabled: bool | None = None
    domain_restriction_enabled: bool | None = None
    allowed_domains: list[str] | None = None


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
    background_generation_concurrency: int
    providers: list[ProviderGenerationItem]


class ProviderGenerationSettingsUpdate(BaseModel):
    background_generation_concurrency: int | None = Field(
        default=None,
        ge=1,
        le=MAX_BACKGROUND_GENERATION_CONCURRENCY,
    )
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
    self_service_enabled: bool


class PasswordResetSettingsResponse(BaseModel):
    method: str
    self_service_enabled: bool
    smtp: SMTPSettingsPayload
    smtp_password_set: bool = False


class PasswordResetSettingsUpdate(BaseModel):
    method: str
    self_service_enabled: bool = True
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


def _normalize_background_generation_concurrency(value: object) -> int:
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        normalized = DEFAULT_BACKGROUND_GENERATION_CONCURRENCY
    return max(1, min(normalized, MAX_BACKGROUND_GENERATION_CONCURRENCY))


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
    background_generation_concurrency = _normalize_background_generation_concurrency(
        value.get("background_generation_concurrency")
    )

    return ProviderGenerationSettingsResponse(
        generation_batch_size=generation_batch_size,
        background_generation_concurrency=background_generation_concurrency,
        providers=providers,
    )


@router.get("/signup", response_model=SignupSettingsResponse)
async def get_signup_settings(
    db: AsyncSession = Depends(get_auth_db),
):
    """Get signup settings (public endpoint)."""
    signup_value = await get_setting(db, SETTING_SIGNUP_ENABLED)
    domain_value = await get_setting(db, SETTING_EMAIL_DOMAIN_RESTRICTION)
    return SignupSettingsResponse(
        signup_enabled=signup_value.get("enabled", True),
        domain_restriction_enabled=domain_value.get("enabled", False),
        allowed_domains=domain_value.get("allowed_domains", []),
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
    current_domain = await get_setting(db, SETTING_EMAIL_DOMAIN_RESTRICTION)

    new_signup_enabled = update.signup_enabled
    if new_signup_enabled is None:
        new_signup_enabled = current_signup.get("enabled", True)

    new_domain_restriction_enabled = update.domain_restriction_enabled
    if new_domain_restriction_enabled is None:
        new_domain_restriction_enabled = current_domain.get("enabled", False)

    new_allowed_domains = update.allowed_domains
    if new_allowed_domains is None:
        new_allowed_domains = current_domain.get("allowed_domains", [])
    else:
        # Normalize domains: lowercase, strip whitespace, remove empty
        new_allowed_domains = [
            d.lower().strip().lstrip("@")
            for d in new_allowed_domains
            if d and d.strip()
        ]

    await set_setting(
        db,
        SETTING_SIGNUP_ENABLED,
        {"enabled": new_signup_enabled},
        current_user.id,
        description="Whether public signup is enabled",
    )

    await set_setting(
        db,
        SETTING_EMAIL_DOMAIN_RESTRICTION,
        {"enabled": new_domain_restriction_enabled, "allowed_domains": new_allowed_domains},
        current_user.id,
        description="Email domain restrictions for signup",
    )

    return SignupSettingsResponse(
        signup_enabled=new_signup_enabled,
        domain_restriction_enabled=new_domain_restriction_enabled,
        allowed_domains=new_allowed_domains,
    )


@router.get("/providers-generation", response_model=ProviderGenerationSettingsResponse)
async def get_provider_generation_settings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_auth_db),
):
    """Get provider generation controls (admin only)."""
    _ensure_admin(current_user)

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
    _ensure_admin(current_user)

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

    current_value = await get_setting(db, SETTING_PROVIDER_GENERATION_CONFIG)
    background_generation_concurrency = _normalize_background_generation_concurrency(
        update.background_generation_concurrency
        if update.background_generation_concurrency is not None
        else current_value.get("background_generation_concurrency")
    )

    value = {
        "background_generation_concurrency": background_generation_concurrency,
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
    """Get the currently active public password-reset policy."""
    value = await get_password_reset_settings(db, include_secret=False)
    return PasswordResetPublicSettingsResponse(
        method=value["method"],
        self_service_enabled=bool(value.get("self_service_enabled", True)),
    )


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
        {
            "method": method,
            "self_service_enabled": update.self_service_enabled,
            "smtp": update.smtp.model_dump(),
        },
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


# ===================== User Preferences =====================


class UserPreferencesResponse(BaseModel):
    theme: str = "fire"
    color_mode: str = "light"
    zen_mode: bool = False


class UserPreferencesUpdate(BaseModel):
    theme: str | None = None
    color_mode: str | None = None
    zen_mode: bool | None = None


@router.get("/preferences", response_model=UserPreferencesResponse)
async def get_user_preferences(
    current_user: User = Depends(get_current_user),
):
    """Get the current user's theme and display preferences."""
    prefs = current_user.preferences or {}
    return UserPreferencesResponse(
        theme=prefs.get("theme", "fire"),
        color_mode=prefs.get("color_mode", "light"),
        zen_mode=prefs.get("zen_mode", False),
    )


@router.put("/preferences", response_model=UserPreferencesResponse)
async def update_user_preferences(
    update: UserPreferencesUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_auth_db),
):
    """Update the current user's theme and display preferences."""
    from sqlalchemy import select
    from app.models.user import User as UserModel

    # Get fresh user from db
    result = await db.execute(select(UserModel).where(UserModel.id == current_user.id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    prefs = dict(user.preferences or {})
    
    if update.theme is not None:
        prefs["theme"] = update.theme
    if update.color_mode is not None:
        prefs["color_mode"] = update.color_mode
    if update.zen_mode is not None:
        prefs["zen_mode"] = update.zen_mode

    user.preferences = prefs
    await db.commit()

    return UserPreferencesResponse(
        theme=prefs.get("theme", "fire"),
        color_mode=prefs.get("color_mode", "light"),
        zen_mode=prefs.get("zen_mode", False),
    )
