"""
Authentication dependencies and utilities.
"""

from typing import Optional
import uuid
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.auth_database import get_auth_db
from app.core.security import decode_token
from app.models.user import User
from app.services.user_service import UserService
from app.services.redis_service import RedisService


security = HTTPBearer()


def _ensure_action_permission(current_user: User, permission: str, error_detail: str) -> None:
    """Raise 403 when a user lacks an action-level permission."""
    if current_user.is_superuser:
        return
    if bool(getattr(current_user, permission, False)):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=error_detail,
    )


def ensure_user_can_generate(current_user: User) -> None:
    _ensure_action_permission(current_user, "can_generate", "You do not have permission to generate questions")


def ensure_user_can_vet(current_user: User) -> None:
    _ensure_action_permission(current_user, "can_vet", "You do not have permission to vet questions")


def ensure_user_can_manage_groups(current_user: User) -> None:
    _ensure_action_permission(current_user, "can_manage_groups", "You do not have permission to manage groups")


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    auth_db: AsyncSession = Depends(get_auth_db),
) -> User:
    """
    Dependency to get current authenticated user from JWT token.
    """
    token = credentials.credentials
    
    # Decode token
    payload = decode_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check token type
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check if token is blacklisted
    redis_service = RedisService()
    jti = payload.get("jti")
    if jti and await redis_service.is_token_blacklisted(jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Get user from database
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_service = UserService(auth_db)
    user = await user_service.get_user_by_id(user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )

    if not user.is_approved:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is pending admin approval",
        )
    
    # Store user ID in request state for database RLS
    request.state.user_id = user.id
    
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Dependency to get current active user.
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )
    return current_user


async def get_current_superuser(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Dependency to get current superuser.
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    return current_user


async def get_current_vetter(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Dependency to get current user with vetter, teacher, or admin role.
    Teachers can access vetter endpoints scoped to their own data.
    """
    if current_user.role not in ("vetter", "admin", "teacher") and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vetter access required",
        )

    ensure_user_can_vet(current_user)
    return current_user


async def get_current_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Dependency to get current user with admin role.
    """
    if current_user.role != "admin" and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


async def get_current_teacher_or_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Dependency to get current user with teacher or admin role.
    """
    if current_user.role not in ("teacher", "admin") and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Teacher access required",
        )
    return current_user


def rate_limit(requests: int = 100, window_seconds: int = 3600):
    """
    Rate limiting dependency factory.
    """
    async def check_rate_limit(
        request: Request,
        current_user: User = Depends(get_current_user),
    ):
        redis_service = RedisService()
        endpoint = request.url.path
        
        is_allowed, remaining = await redis_service.check_rate_limit(
            identifier=str(current_user.id),
            endpoint=endpoint,
            limit=requests,
            window_seconds=window_seconds,
        )
        
        if not is_allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
                headers={
                    "X-RateLimit-Limit": str(requests),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(window_seconds),
                },
            )
        
        # Add rate limit headers
        request.state.rate_limit_remaining = remaining
        
        return current_user
    
    return check_rate_limit


def get_client_info(request: Request) -> dict:
    """
    Extract client information from request.
    """
    return {
        "ip_address": request.client.host if request.client else None,
        "user_agent": request.headers.get("User-Agent"),
        "device_id": request.headers.get("X-Device-ID"),
        "device_name": request.headers.get("X-Device-Name"),
        "device_type": request.headers.get("X-Device-Type"),
    }
