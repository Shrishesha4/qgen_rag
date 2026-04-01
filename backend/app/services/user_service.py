"""
User service for authentication and user management.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
import uuid
import hashlib

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, default_permissions_for_role
from app.models.auth import RefreshToken, AuditLog
from app.schemas.user import UserCreate, UserUpdate
from app.core.security import (
    hash_password,
    verify_password,
    hash_security_answer,
    verify_security_answer,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.core.config import settings


class UserService:
    """Service for user-related operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _as_utc(dt: datetime) -> datetime:
        """Normalize datetime to UTC-aware for safe comparisons."""
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    @staticmethod
    def _normalize_security_question(question: str) -> str:
        """Normalize security-question text for storage."""
        return " ".join((question or "").strip().split())

    async def create_user(self, user_data: UserCreate) -> User:
        """Create a new user."""
        # Check if email exists
        existing_email = await self.db.execute(
            select(User).where(User.email == user_data.email)
        )
        if existing_email.scalar_one_or_none():
            raise ValueError("Email already registered")

        # Check if username exists
        existing_username = await self.db.execute(
            select(User).where(User.username == user_data.username.lower())
        )
        if existing_username.scalar_one_or_none():
            raise ValueError("Username already taken")

        role = getattr(user_data, 'role', 'teacher')
        role_defaults = default_permissions_for_role(role)
        security_question = self._normalize_security_question(user_data.security_question)
        security_answer = str(user_data.security_answer or "").strip()
        if not security_question or not security_answer:
            raise ValueError("Security question and answer are required")

        # Create user with role and action permissions
        user = User(
            email=user_data.email,
            username=user_data.username.lower(),
            password_hash=hash_password(user_data.password),
            full_name=user_data.full_name,
            security_question=security_question,
            security_answer_hash=hash_security_answer(security_answer),
            role=role,
            can_manage_groups=role_defaults["can_manage_groups"],
            can_generate=role_defaults["can_generate"],
            can_vet=role_defaults["can_vet"],
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def authenticate_user(
        self,
        email: str,
        password: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Optional[User]:
        """Authenticate user with email and password."""
        result = await self.db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if not user:
            # Log failed attempt
            await self._log_auth_event(
                user_id=None,
                event_type="login_failed",
                ip_address=ip_address,
                user_agent=user_agent,
                success=False,
                error_message="User not found",
            )
            return None

        # Check if account is locked
        if user.locked_until:
            locked_until = self._as_utc(user.locked_until)
            if locked_until > datetime.now(timezone.utc):
                await self._log_auth_event(
                    user_id=user.id,
                    event_type="login_blocked",
                    ip_address=ip_address,
                    user_agent=user_agent,
                    success=False,
                    error_message="Account locked",
                )
                raise ValueError("Account is locked. Please try again later.")

        # Verify password
        if not verify_password(password, user.password_hash):
            # Increment failed attempts
            user.failed_login_attempts += 1
            
            # Lock account after 5 failed attempts
            if user.failed_login_attempts >= 5:
                user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=30)
            
            await self.db.commit()
            
            await self._log_auth_event(
                user_id=user.id,
                event_type="login_failed",
                ip_address=ip_address,
                user_agent=user_agent,
                success=False,
                error_message="Invalid password",
            )
            return None

        # Check if user is active
        if not user.is_active:
            await self._log_auth_event(
                user_id=user.id,
                event_type="login_failed",
                ip_address=ip_address,
                user_agent=user_agent,
                success=False,
                error_message="Account deactivated",
            )
            raise ValueError("Account is deactivated")

        # Reset failed attempts and update last login
        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login_at = datetime.now(timezone.utc)
        await self.db.commit()

        # Log successful login
        await self._log_auth_event(
            user_id=user.id,
            event_type="login_success",
            ip_address=ip_address,
            user_agent=user_agent,
            success=True,
        )

        return user

    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def update_user(self, user_id: str, update_data: UserUpdate) -> User:
        """Update user profile."""
        user = await self.get_user_by_id(user_id)
        if not user:
            raise ValueError("User not found")

        update_dict = update_data.model_dump(exclude_unset=True)
        security_question_provided = "security_question" in update_dict
        security_answer_provided = "security_answer" in update_dict

        if security_question_provided != security_answer_provided:
            raise ValueError("Security question and answer must be updated together")

        security_question = update_dict.pop("security_question", None)
        security_answer = update_dict.pop("security_answer", None)

        new_username = update_dict.get("username")
        if new_username and new_username != user.username:
            existing_username = await self.db.execute(
                select(User).where(User.username == new_username)
            )
            if existing_username.scalar_one_or_none():
                raise ValueError("Username already taken")

        for key, value in update_dict.items():
            setattr(user, key, value)

        if security_question_provided and security_answer_provided:
            normalized_question = self._normalize_security_question(str(security_question or ""))
            normalized_answer = str(security_answer or "").strip()
            if not normalized_question or not normalized_answer:
                raise ValueError("Security question and answer cannot be empty")
            user.security_question = normalized_question
            user.security_answer_hash = hash_security_answer(normalized_answer)

        user.updated_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def change_password(
        self,
        user_id: str,
        current_password: str,
        new_password: str,
    ) -> bool:
        """Change user password."""
        user = await self.get_user_by_id(user_id)
        if not user:
            raise ValueError("User not found")

        if not verify_password(current_password, user.password_hash):
            raise ValueError("Current password is incorrect")

        await self._update_password(user, new_password, revoke_sessions=False)
        return True

    async def reset_password(
        self,
        user_id: str,
        new_password: str,
        *,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> bool:
        """Reset a user's password and revoke all active refresh tokens."""
        user = await self.get_user_by_id(user_id)
        if not user:
            raise ValueError("User not found")

        await self._update_password(user, new_password, revoke_sessions=True)
        await self._log_auth_event(
            user_id=user.id,
            event_type="password_reset_success",
            ip_address=ip_address,
            user_agent=user_agent,
            success=True,
        )
        return True

    async def get_security_question_for_email(self, email: str) -> Optional[str]:
        """Return the stored security question for an active user."""
        user = await self.get_user_by_email(email)
        if not user or not user.is_active or not user.security_question or not user.security_answer_hash:
            return None
        return user.security_question

    async def reset_password_with_security_question(
        self,
        email: str,
        security_answer: str,
        new_password: str,
        *,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> bool:
        """Reset a user's password after verifying their security answer."""
        user = await self.get_user_by_email(email)
        if not user or not user.is_active or not user.security_answer_hash:
            raise ValueError("Security question is not available for this account")

        if not verify_security_answer(security_answer, user.security_answer_hash):
            await self._log_auth_event(
                user_id=user.id,
                event_type="password_reset_security_question_failed",
                ip_address=ip_address,
                user_agent=user_agent,
                success=False,
                error_message="Incorrect security answer",
            )
            raise ValueError("Security question answer is incorrect")

        await self._update_password(user, new_password, revoke_sessions=True)
        await self._log_auth_event(
            user_id=user.id,
            event_type="password_reset_security_question_success",
            ip_address=ip_address,
            user_agent=user_agent,
            success=True,
        )
        return True

    async def record_password_reset_request(
        self,
        user: User,
        *,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        """Record that a password reset email was requested."""
        await self._log_auth_event(
            user_id=user.id,
            event_type="password_reset_requested",
            ip_address=ip_address,
            user_agent=user_agent,
            success=True,
        )

    async def _update_password(
        self,
        user: User,
        new_password: str,
        *,
        revoke_sessions: bool,
    ) -> None:
        """Persist password changes and optionally invalidate active refresh tokens."""
        now = datetime.now(timezone.utc)
        user.password_hash = hash_password(new_password)
        user.password_changed_at = now
        user.failed_login_attempts = 0
        user.locked_until = None

        if revoke_sessions:
            await self.db.execute(
                update(RefreshToken)
                .where(
                    RefreshToken.user_id == user.id,
                    RefreshToken.is_revoked == False,
                )
                .values(is_revoked=True, revoked_at=now)
            )

        await self.db.commit()

    async def create_refresh_token(
        self,
        user_id: str,
        device_id: Optional[str] = None,
        device_name: Optional[str] = None,
        device_type: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> tuple[str, str]:
        """Create access and refresh tokens for user."""
        user = await self.get_user_by_id(user_id)
        if not user:
            raise ValueError("User not found")

        # Generate tokens
        access_token = create_access_token(
            data={"sub": str(user_id), "email": user.email, "username": user.username}
        )
        refresh_token = create_refresh_token(
            data={"sub": str(user_id)},
            device_id=device_id,
        )

        # Store refresh token hash
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

        refresh_token_record = RefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            device_id=device_id,
            device_name=device_name,
            device_type=device_type,
            ip_address=ip_address,
            user_agent=user_agent,
            expires_at=expires_at,
        )
        self.db.add(refresh_token_record)
        await self.db.commit()

        return access_token, refresh_token

    async def refresh_access_token(self, refresh_token: str) -> Optional[tuple[str, str]]:
        """Refresh access token using refresh token."""
        payload = decode_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            return None

        # Verify token in database
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        result = await self.db.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == token_hash,
                RefreshToken.is_revoked == False,
                RefreshToken.expires_at > datetime.now(timezone.utc),
            )
        )
        token_record = result.scalar_one_or_none()
        if not token_record:
            return None

        # Get user
        user_id = payload["sub"]
        user = await self.get_user_by_id(user_id)
        if not user or not user.is_active:
            return None

        # Update last used
        token_record.last_used_at = datetime.now(timezone.utc)
        await self.db.commit()

        # Generate new access token
        access_token = create_access_token(
            data={"sub": str(user_id), "email": user.email, "username": user.username}
        )

        # Optionally rotate refresh token
        new_refresh_token = create_refresh_token(
            data={"sub": str(user_id)},
            device_id=token_record.device_id,
        )

        # Revoke old token and create new one
        token_record.is_revoked = True
        token_record.revoked_at = datetime.now(timezone.utc)

        new_token_hash = hashlib.sha256(new_refresh_token.encode()).hexdigest()
        new_token_record = RefreshToken(
            user_id=user_id,
            token_hash=new_token_hash,
            device_id=token_record.device_id,
            device_name=token_record.device_name,
            device_type=token_record.device_type,
            ip_address=token_record.ip_address,
            user_agent=token_record.user_agent,
            expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
        self.db.add(new_token_record)
        await self.db.commit()

        return access_token, new_refresh_token

    async def revoke_refresh_token(self, refresh_token: str) -> bool:
        """Revoke a single refresh token."""
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        result = await self.db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        token_record = result.scalar_one_or_none()
        
        if token_record:
            token_record.is_revoked = True
            token_record.revoked_at = datetime.now(timezone.utc)
            await self.db.commit()
            return True
        return False

    async def revoke_all_user_tokens(self, user_id: str) -> int:
        """Revoke all refresh tokens for a user."""
        result = await self.db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.is_revoked == False)
            .values(is_revoked=True, revoked_at=datetime.now(timezone.utc))
        )
        await self.db.commit()
        return result.rowcount

    async def get_user_sessions(self, user_id: str, current_token: str) -> List[Dict[str, Any]]:
        """Get all active sessions for a user."""
        current_token_hash = hashlib.sha256(current_token.encode()).hexdigest()
        
        result = await self.db.execute(
            select(RefreshToken).where(
                RefreshToken.user_id == user_id,
                RefreshToken.is_revoked == False,
                RefreshToken.expires_at > datetime.now(timezone.utc),
            )
        )
        tokens = result.scalars().all()
        
        sessions = []
        for token in tokens:
            sessions.append({
                "id": token.id,
                "device_name": token.device_name,
                "device_type": token.device_type,
                "ip_address": token.ip_address,
                "last_activity": token.last_used_at,
                "is_current": token.token_hash == current_token_hash,
            })
        
        return sessions

    async def _log_auth_event(
        self,
        user_id: Optional[str],
        event_type: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None,
    ):
        """Log authentication event."""
        audit_log = AuditLog(
            user_id=user_id,
            event_type=event_type,
            event_category="auth",
            severity="info" if success else "warning",
            ip_address=ip_address,
            user_agent=user_agent,
            success=success,
            error_message=error_message,
        )
        self.db.add(audit_log)
        await self.db.commit()
