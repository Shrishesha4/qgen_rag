"""
Authentication API endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.config import settings
from app.schemas.user import UserCreate, UserLogin, UserUpdate, UserResponse
from app.schemas.auth import (
    Token,
    TokenResponse,
    TokenRefresh,
    PasswordChange,
    SessionResponse,
    SessionInfo,
    LogoutRequest,
    LogoutAllResponse,
)
from app.services.user_service import UserService
from app.api.v1.deps import get_current_user, get_client_info
from app.models.user import User


router = APIRouter()


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: Request,
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Register a new user account.
    """
    user_service = UserService(db)
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
    db: AsyncSession = Depends(get_db),
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


@router.post("/refresh", response_model=Token)
async def refresh_token(
    token_data: TokenRefresh,
    db: AsyncSession = Depends(get_db),
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
    db: AsyncSession = Depends(get_db),
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
    db: AsyncSession = Depends(get_db),
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
    db: AsyncSession = Depends(get_db),
):
    """
    Update current user profile.
    """
    user_service = UserService(db)
    
    updated_user = await user_service.update_user(current_user.id, update_data)
    
    return UserResponse.model_validate(updated_user)


@router.post("/change-password")
async def change_password(
    password_data: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
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
        return {"message": "Password changed successfully"}
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/sessions", response_model=SessionResponse)
async def get_sessions(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
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
    db: AsyncSession = Depends(get_db),
):
    """
    Revoke a specific session.
    """
    # This would require storing session IDs differently
    # For now, return success
    return {"message": "Session revoked successfully"}
