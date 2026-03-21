"""
Authentication-related Pydantic schemas.
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
import uuid

from app.schemas.user import UserResponse


class Token(BaseModel):
    """Schema for authentication tokens."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class TokenResponse(BaseModel):
    """Schema for token response with user info."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class TokenRefresh(BaseModel):
    """Schema for token refresh request."""
    refresh_token: str


class PasswordChange(BaseModel):
    """Schema for password change request."""
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)


class SessionInfo(BaseModel):
    """Schema for a single session."""
    id: uuid.UUID
    device_name: Optional[str]
    device_type: Optional[str]
    ip_address: Optional[str]
    last_activity: datetime
    is_current: bool


class SessionResponse(BaseModel):
    """Schema for sessions list response."""
    sessions: List[SessionInfo]


class LogoutRequest(BaseModel):
    """Schema for logout request."""
    refresh_token: str


class LogoutAllResponse(BaseModel):
    """Schema for logout all response."""
    message: str
    sessions_revoked: int
