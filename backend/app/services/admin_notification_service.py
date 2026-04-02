"""Admin notification helpers backed by the auth SQLite database."""

from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import AdminNotification
from app.models.user import ROLE_ADMIN, User

PASSWORD_RESET_NOTIFICATION_TYPE = "password_reset_requested"


class AdminNotificationService:
    """Create and manage per-admin notification items."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_password_reset_notifications(
        self,
        target_user: User,
        *,
        method: str,
        self_service_enabled: bool = True,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> int:
        """Create one notification per active admin for a password reset request."""
        result = await self.db.execute(
            select(User.id)
            .where(User.role == ROLE_ADMIN, User.is_active == True)
            .order_by(User.created_at.asc(), User.username.asc())
        )
        admin_ids = [str(admin_id) for admin_id in result.scalars().all()]
        if not admin_ids:
            return 0

        method_label = "security question" if method == "security_question" else "email link"
        display_name = target_user.full_name or target_user.username or target_user.email
        title = "Password reset requested"
        if self_service_enabled:
            message = f"{display_name} requested a password reset via {method_label}."
        else:
            message = f"{display_name} requested an admin-assisted password reset."
        action_url = f"/users/{target_user.id}?intent=reset-password"
        payload = {
            "method": method,
            "self_service_enabled": self_service_enabled,
            "ip_address": ip_address,
            "user_agent": user_agent,
        }

        notifications = [
            AdminNotification(
                recipient_user_id=admin_id,
                notification_type=PASSWORD_RESET_NOTIFICATION_TYPE,
                title=title,
                message=message,
                target_user_id=target_user.id,
                target_user_email=target_user.email,
                target_username=target_user.username,
                action_url=action_url,
                action_label="View",
                payload=payload,
            )
            for admin_id in admin_ids
        ]
        self.db.add_all(notifications)
        await self.db.commit()
        return len(notifications)

    async def list_for_admin(
        self,
        admin_user_id: str,
        *,
        unread_only: bool = False,
        limit: int = 100,
    ) -> Sequence[AdminNotification]:
        query = select(AdminNotification).where(AdminNotification.recipient_user_id == admin_user_id)
        if unread_only:
            query = query.where(AdminNotification.is_read == False)
        query = query.order_by(AdminNotification.created_at.desc()).limit(max(1, min(limit, 250)))
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_unread_count(self, admin_user_id: str) -> int:
        result = await self.db.execute(
            select(func.count(AdminNotification.id)).where(
                AdminNotification.recipient_user_id == admin_user_id,
                AdminNotification.is_read == False,
            )
        )
        return int(result.scalar() or 0)

    async def mark_read(self, admin_user_id: str, notification_id: str) -> AdminNotification | None:
        result = await self.db.execute(
            select(AdminNotification).where(
                AdminNotification.id == notification_id,
                AdminNotification.recipient_user_id == admin_user_id,
            )
        )
        notification = result.scalar_one_or_none()
        if not notification:
            return None
        if not notification.is_read:
            notification.is_read = True
            notification.read_at = datetime.now(timezone.utc)
            await self.db.commit()
            await self.db.refresh(notification)
        return notification

    async def mark_all_read(self, admin_user_id: str) -> int:
        result = await self.db.execute(
            update(AdminNotification)
            .where(
                AdminNotification.recipient_user_id == admin_user_id,
                AdminNotification.is_read == False,
            )
            .values(is_read=True, read_at=datetime.now(timezone.utc))
        )
        await self.db.commit()
        return int(result.rowcount or 0)