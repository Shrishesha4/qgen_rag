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
)
from app.models.user import ROLE_ADMIN, User
from app.schemas.auth import MessageResponse
from app.services.email_service import EmailService
from app.services.system_settings_service import (
    get_password_reset_settings,
    get_setting,
    set_setting,
    update_password_reset_settings,
)


router = APIRouter()


class SignupSettingsResponse(BaseModel):
    signup_enabled: bool


class SignupSettingsUpdate(BaseModel):
    signup_enabled: bool


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


@router.get("/signup", response_model=SignupSettingsResponse)
async def get_signup_settings(
    db: AsyncSession = Depends(get_auth_db),
):
    """Get signup settings (public endpoint)."""
    value = await get_setting(db, SETTING_SIGNUP_ENABLED)
    return SignupSettingsResponse(signup_enabled=value.get("enabled", True))


@router.put("/signup", response_model=SignupSettingsResponse)
async def update_signup_settings(
    update: SignupSettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_auth_db),
):
    """Update signup settings (admin only)."""
    _ensure_admin(current_user)

    await set_setting(
        db,
        SETTING_SIGNUP_ENABLED,
        {"enabled": update.signup_enabled},
        current_user.id,
        description="Whether public signup is enabled",
    )

    return SignupSettingsResponse(signup_enabled=update.signup_enabled)


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
