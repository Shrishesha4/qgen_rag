"""
Authentication API endpoints.
"""

import logging
import os
import uuid as uuid_lib
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Request, UploadFile, File
from fastapi.responses import FileResponse
from typing import Dict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.core.auth_database import get_auth_db
from app.core.config import settings
from app.schemas.user import UserCreate, UserLogin, UserUpdate, UserResponse
from app.schemas.auth import (
    Token,
    TokenResponse,
    TokenRefresh,
    PasswordChange,
    PasswordResetRequest,
    PasswordResetConfirm,
    SecurityQuestionRequest,
    SecurityQuestionResponse,
    SecurityQuestionPasswordReset,
    MessageResponse,
    SessionResponse,
    SessionInfo,
    LogoutRequest,
    LogoutAllResponse,
)
from app.core.security import create_password_reset_token, decode_token, password_token_version
from app.services.user_service import UserService
from app.services.email_service import EmailService
from app.services.system_settings_service import get_password_reset_settings
from app.api.v1.deps import get_current_user, get_client_info
from app.models.user import User, ROLE_STUDENT, ROLE_ADMIN
from app.models.system_settings import (
    DEFAULT_SETTINGS,
    PASSWORD_RESET_METHOD_SECURITY_QUESTION,
    PASSWORD_RESET_METHOD_SMTP,
    SETTING_SIGNUP_ENABLED,
    SETTING_STUDENT_SIGNUP_ENABLED,
    SystemSettings,
)


router = APIRouter()
logger = logging.getLogger(__name__)


class BootstrapStatus(BaseModel):
    admin_exists: bool


async def is_signup_enabled(db: AsyncSession) -> bool:
    """Check if signup is enabled in system settings."""
    result = await db.execute(
        select(SystemSettings).where(SystemSettings.key == SETTING_SIGNUP_ENABLED)
    )
    setting = result.scalar_one_or_none()
    if setting and setting.value:
        return setting.value.get("enabled", True)
    return DEFAULT_SETTINGS.get(SETTING_SIGNUP_ENABLED, {}).get("enabled", True)


async def is_student_signup_enabled(db: AsyncSession) -> bool:
    """Check if student self-signup is enabled in system settings."""
    result = await db.execute(
        select(SystemSettings).where(SystemSettings.key == SETTING_STUDENT_SIGNUP_ENABLED)
    )
    setting = result.scalar_one_or_none()
    if setting and setting.value:
        return setting.value.get("enabled", False)
    return DEFAULT_SETTINGS.get(SETTING_STUDENT_SIGNUP_ENABLED, {}).get("enabled", False)


@router.get("/bootstrap-status", response_model=BootstrapStatus)
async def get_bootstrap_status(
    db: AsyncSession = Depends(get_auth_db),
):
    """Return whether an admin account already exists (public)."""
    user_service = UserService(db)
    return BootstrapStatus(admin_exists=await user_service.admin_exists())


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: Request,
    user_data: UserCreate,
    db: AsyncSession = Depends(get_auth_db),
):
    """
    Register a new user account.
    """
    user_service = UserService(db)
    admin_exists = await user_service.admin_exists()

    # On first run, force creation of an admin before allowing any other role.
    if not admin_exists:
        if user_data.role != ROLE_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="First account must be an admin. Create an admin user to continue.",
            )
        user_data = user_data.model_copy(update={"role": ROLE_ADMIN})
    else:
        # Check signup toggles per role once an admin already exists
        if user_data.role == ROLE_STUDENT:
            if not await is_student_signup_enabled(db):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Student self-signup is currently disabled. Please contact your teacher or an administrator.",
                )
        else:
            if not await is_signup_enabled(db):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="User registration is currently disabled. Please contact an administrator.",
                )
    client_info = get_client_info(request)
    
    try:
        # Create user
        user = await user_service.create_user(user_data)
        
        # Generate tokens
        access_token, refresh_token = await user_service.create_refresh_token(
            user_id=user.id,
            **client_info,
        )
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=UserResponse.model_validate(user),
        )
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )


@router.post("/login", response_model=TokenResponse)
async def login(
    request: Request,
    credentials: UserLogin,
    db: AsyncSession = Depends(get_auth_db),
):
    """
    Authenticate user and return tokens.
    """
    user_service = UserService(db)
    client_info = get_client_info(request)
    
    try:
        user = await user_service.authenticate_user(
            email=credentials.email,
            password=credentials.password,
            ip_address=client_info.get("ip_address"),
            user_agent=client_info.get("user_agent"),
        )
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )
        
        # Generate tokens
        access_token, refresh_token = await user_service.create_refresh_token(
            user_id=user.id,
            **client_info,
        )
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=UserResponse.model_validate(user),
        )
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    request: Request,
    payload: PasswordResetRequest,
    db: AsyncSession = Depends(get_auth_db),
):
    """Request a password reset email without revealing whether the account exists."""
    password_reset_settings = await get_password_reset_settings(db, include_secret=True)
    if password_reset_settings["method"] != PASSWORD_RESET_METHOD_SMTP:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password reset via email is currently disabled",
        )

    email_service = EmailService(config=password_reset_settings["smtp"])
    if not email_service.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Password reset email is not configured",
        )

    user_service = UserService(db)
    client_info = get_client_info(request)
    user = await user_service.get_user_by_email(payload.email)

    if user and user.is_active:
        token = create_password_reset_token(
            data={
                "sub": str(user.id),
                "email": user.email,
                "pwd": password_token_version(user.password_changed_at),
            },
            expires_delta=timedelta(minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES),
        )
        try:
            await email_service.send_password_reset_email(
                to_email=user.email,
                token=token,
                recipient_name=user.full_name,
            )
            await user_service.record_password_reset_request(
                user,
                ip_address=client_info.get("ip_address"),
                user_agent=client_info.get("user_agent"),
            )
        except Exception as exc:
            # Keep the response generic to avoid account enumeration.
            logger.warning("Password reset email send failed for %s: %s", user.email, exc)

    return MessageResponse(
        message="If an account exists for that email, a password reset link has been sent."
    )


@router.post("/security-question", response_model=SecurityQuestionResponse)
async def get_security_question(
    payload: SecurityQuestionRequest,
    db: AsyncSession = Depends(get_auth_db),
):
    """Return the stored security question for password-reset flows."""
    password_reset_settings = await get_password_reset_settings(db, include_secret=False)
    if password_reset_settings["method"] != PASSWORD_RESET_METHOD_SECURITY_QUESTION:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Security-question reset is currently disabled",
        )

    user_service = UserService(db)
    question = await user_service.get_security_question_for_email(payload.email)
    if not question:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Security question is not available for this account",
        )

    return SecurityQuestionResponse(security_question=question)


@router.post("/security-question/reset-password", response_model=MessageResponse)
async def reset_password_with_security_question(
    request: Request,
    payload: SecurityQuestionPasswordReset,
    db: AsyncSession = Depends(get_auth_db),
):
    """Reset a password using the user's configured security answer."""
    password_reset_settings = await get_password_reset_settings(db, include_secret=False)
    if password_reset_settings["method"] != PASSWORD_RESET_METHOD_SECURITY_QUESTION:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Security-question reset is currently disabled",
        )

    user_service = UserService(db)
    client_info = get_client_info(request)
    try:
        await user_service.reset_password_with_security_question(
            email=payload.email,
            security_answer=payload.security_answer,
            new_password=payload.new_password,
            ip_address=client_info.get("ip_address"),
            user_agent=client_info.get("user_agent"),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    return MessageResponse(message="Password reset successful")


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    request: Request,
    payload: PasswordResetConfirm,
    db: AsyncSession = Depends(get_auth_db),
):
    """Reset a password using a signed password-reset token."""
    token_payload = decode_token(payload.token)
    if not token_payload or token_payload.get("type") != "password_reset":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset token",
        )

    user_id = str(token_payload.get("sub") or "").strip()
    token_email = str(token_payload.get("email") or "").strip().lower()

    user_service = UserService(db)
    user = await user_service.get_user_by_id(user_id) if user_id else None
    if not user or not user.is_active or user.email.strip().lower() != token_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset token",
        )

    token_version = int(token_payload.get("pwd") or 0)
    if token_version != password_token_version(user.password_changed_at):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This password reset link has already been used or has expired",
        )

    client_info = get_client_info(request)
    await user_service.reset_password(
        user_id=user.id,
        new_password=payload.new_password,
        ip_address=client_info.get("ip_address"),
        user_agent=client_info.get("user_agent"),
    )

    return MessageResponse(message="Password reset successful")


@router.post("/refresh", response_model=Token)
async def refresh_token(
    token_data: TokenRefresh,
    db: AsyncSession = Depends(get_auth_db),
):
    """
    Refresh access token using refresh token.
    """
    user_service = UserService(db)
    
    result = await user_service.refresh_access_token(token_data.refresh_token)
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )
    
    access_token, new_refresh_token = result
    
    return Token(
        access_token=access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/logout")
async def logout(
    logout_data: LogoutRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_auth_db),
):
    """
    Logout from current session.
    """
    user_service = UserService(db)
    
    await user_service.revoke_refresh_token(logout_data.refresh_token)
    
    return {"message": "Logged out successfully"}


@router.post("/logout-all", response_model=LogoutAllResponse)
async def logout_all(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_auth_db),
):
    """
    Logout from all devices.
    """
    user_service = UserService(db)
    
    sessions_revoked = await user_service.revoke_all_user_tokens(current_user.id)
    
    return LogoutAllResponse(
        message="Logged out from all devices",
        sessions_revoked=sessions_revoked,
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
):
    """
    Get current user profile.
    """
    return UserResponse.model_validate(current_user)


@router.put("/update-profile", response_model=UserResponse)
async def update_profile(
    update_data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_auth_db),
):
    """
    Update current user profile.
    """
    user_service = UserService(db)
    
    try:
        updated_user = await user_service.update_user(current_user.id, update_data)
        return UserResponse.model_validate(updated_user)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )


@router.post("/upload-avatar", response_model=UserResponse)
async def upload_avatar(
    file: UploadFile = File(..., description="Profile image (JPEG, PNG, or WebP)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_auth_db),
):
    """
    Upload a profile avatar image.
    """
    # Validate file type
    allowed_types = ["image/jpeg", "image/png", "image/webp"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type. Allowed types: JPEG, PNG, WebP",
        )
    
    # Validate file size (max 5MB)
    max_size = 5 * 1024 * 1024
    content = await file.read()
    if len(content) > max_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File too large. Maximum size is 5MB",
        )
    
    # Create avatars directory
    avatars_dir = os.path.join(settings.UPLOAD_DIR, "avatars")
    os.makedirs(avatars_dir, exist_ok=True)
    
    # Generate unique filename
    ext = file.filename.split(".")[-1] if file.filename else "jpg"
    filename = f"{current_user.id}_{uuid_lib.uuid4().hex[:8]}.{ext}"
    file_path = os.path.join(avatars_dir, filename)
    
    # Delete old avatar if exists
    if current_user.avatar_url:
        old_filename = current_user.avatar_url.split("/")[-1]
        old_path = os.path.join(avatars_dir, old_filename)
        if os.path.exists(old_path):
            os.remove(old_path)
    
    # Save new avatar
    with open(file_path, "wb") as f:
        f.write(content)
    
    # Update user avatar_url
    avatar_url = f"{settings.API_PREFIX}/auth/avatars/{filename}"
    user_service = UserService(db)
    update_data = UserUpdate(avatar_url=avatar_url)
    updated_user = await user_service.update_user(current_user.id, update_data)
    
    return UserResponse.model_validate(updated_user)


@router.get("/avatars/{filename}")
async def get_avatar(filename: str):
    """
    Serve avatar image.
    """
    avatars_dir = os.path.join(settings.UPLOAD_DIR, "avatars")
    file_path = os.path.join(avatars_dir, filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Avatar not found",
        )
    
    return FileResponse(file_path)


@router.delete("/avatar", response_model=UserResponse)
async def delete_avatar(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_auth_db),
):
    """
    Delete current user's avatar.
    """
    if current_user.avatar_url:
        # Delete file
        filename = current_user.avatar_url.split("/")[-1]
        avatars_dir = os.path.join(settings.UPLOAD_DIR, "avatars")
        file_path = os.path.join(avatars_dir, filename)
        if os.path.exists(file_path):
            os.remove(file_path)
    
    # Clear avatar_url
    user_service = UserService(db)
    update_data = UserUpdate(avatar_url=None)
    updated_user = await user_service.update_user(current_user.id, update_data)
    
    return UserResponse.model_validate(updated_user)


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    password_data: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_auth_db),
):
    """
    Change current user's password.
    """
    user_service = UserService(db)
    
    try:
        await user_service.change_password(
            user_id=current_user.id,
            current_password=password_data.current_password,
            new_password=password_data.new_password,
        )
        return MessageResponse(message="Password changed successfully")
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/sessions", response_model=SessionResponse)
async def get_sessions(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_auth_db),
):
    """
    Get all active sessions for current user.
    """
    user_service = UserService(db)
    
    # Get refresh token from header for current session identification
    auth_header = request.headers.get("Authorization", "")
    current_token = auth_header.replace("Bearer ", "") if auth_header else ""
    
    sessions = await user_service.get_user_sessions(current_user.id, current_token)
    
    return SessionResponse(
        sessions=[SessionInfo(**s) for s in sessions]
    )


@router.delete("/sessions/{session_id}")
async def revoke_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_auth_db),
):
    """
    Revoke a specific session.
    """
    # This would require storing session IDs differently
    # For now, return success
    return {"message": "Session revoked successfully"}


@router.get("/admin-exists")
async def admin_exists(db: AsyncSession = Depends(get_auth_db)) -> Dict[str, bool]:
    """Check if any admin user exists in the system"""
    try:
        # Check if any user with admin role exists
        result = await db.execute(
            select(User).where(User.role == "admin").limit(1)
        )
        admin_user = result.scalar_one_or_none()
        return {"exists": admin_user is not None}
    except Exception:
        # If there's an error, assume no admin exists for bootstrap
        return {"exists": False}
