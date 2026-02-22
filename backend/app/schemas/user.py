"""
User-related Pydantic schemas.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, field_validator
import uuid
import re


class UserBase(BaseModel):
    """Base user schema."""
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    full_name: Optional[str] = Field(None, max_length=255)

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        if not re.match(r"^[a-zA-Z0-9_]+$", v):
            raise ValueError("Username can only contain letters, numbers, and underscores")
        return v.lower()


class UserCreate(UserBase):
    """Schema for user registration."""
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        # Relaxed validation - just require 8+ characters
        # Uncomment below for stricter validation:
        # if not any(c.isupper() for c in v):
        #     raise ValueError("Password must contain at least one uppercase letter")
        # if not any(c.islower() for c in v):
        #     raise ValueError("Password must contain at least one lowercase letter")
        # if not any(c.isdigit() for c in v):
        #     raise ValueError("Password must contain at least one number")
        # special_chars = set("!@#$%^&*()_+-=[]{}|;:,.<>?")
        # if not any(c in special_chars for c in v):
        #     raise ValueError("Password must contain at least one special character")
        return v


class UserLogin(BaseModel):
    """Schema for user login."""
    email: EmailStr
    password: str


class UserUpdate(BaseModel):
    """Schema for updating user profile."""
    full_name: Optional[str] = Field(None, max_length=255)
    avatar_url: Optional[str] = Field(None, max_length=500)
    timezone: Optional[str] = Field(None, max_length=50)
    language: Optional[str] = Field(None, max_length=10)
    preferences: Optional[dict] = None



class UserResponse(BaseModel):
    """Schema for user response (public info)."""
    id: uuid.UUID
    email: EmailStr
    username: str
    full_name: Optional[str]
    avatar_url: Optional[str]
    timezone: str
    language: str
    is_active: bool
    created_at: datetime
    last_login_at: Optional[datetime]
    preferences: Optional[dict]

    subject_reference_materials: Optional[dict]

    model_config = {"from_attributes": True}


class UserInDB(UserResponse):
    """Schema for user in database (includes sensitive fields)."""
    password_hash: str
    is_superuser: bool
    failed_login_attempts: int
    locked_until: Optional[datetime]

    model_config = {"from_attributes": True}
