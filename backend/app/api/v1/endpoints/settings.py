"""
System settings API endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_database import get_auth_db
from app.models.system_settings import SystemSettings, SETTING_SIGNUP_ENABLED, DEFAULT_SETTINGS
from app.models.user import User, ROLE_ADMIN
from app.api.v1.deps import get_current_user


router = APIRouter()


class SignupSettingsResponse(BaseModel):
    signup_enabled: bool


class SignupSettingsUpdate(BaseModel):
    signup_enabled: bool


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
