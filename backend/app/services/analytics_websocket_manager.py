"""
Analytics WebSocket manager for real-time activity tracking.
Tracks active users who are vetting or generating.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Set, Optional
from dataclasses import dataclass, field
from fastapi import WebSocket

logger = logging.getLogger(__name__)
STALE_ACTIVITY_SECONDS = 90


@dataclass
class ActiveUser:
    """Information about an active user."""
    user_id: str
    username: str
    email: str
    activity: str  # 'vetting' | 'generating' | 'idle'
    subject_name: Optional[str] = None
    topic_name: Optional[str] = None
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_heartbeat: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class AnalyticsConnection:
    """Information about an analytics WebSocket connection."""
    websocket: WebSocket
    user_id: str
    is_admin: bool = False


class AnalyticsWebSocketManager:
    """
    Manages WebSocket connections for real-time analytics.
    Tracks active users and their current activities.
    """
    
    def __init__(self):
        # Active analytics viewers
        self._connections: Dict[str, AnalyticsConnection] = {}
        # Active users doing work (vetting/generating)
        self._active_users: Dict[str, ActiveUser] = {}
        # Lock for thread-safe operations
        self._lock = asyncio.Lock()
        # Coalesce bursty live refresh requests into a single broadcast loop.
        self._broadcast_task: Optional[asyncio.Task] = None
        self._broadcast_requested = False
    
    async def connect(self, websocket: WebSocket, connection_id: str, user_id: str, is_admin: bool = False) -> None:
        """Accept a new analytics WebSocket connection."""
        await websocket.accept()
        async with self._lock:
            self._connections[connection_id] = AnalyticsConnection(
                websocket=websocket,
                user_id=user_id,
                is_admin=is_admin,
            )
        logger.info(f"Analytics WebSocket connected: {connection_id} (admin: {is_admin})")
    
    async def disconnect(self, connection_id: str) -> None:
        """Handle WebSocket disconnection."""
        async with self._lock:
            if connection_id in self._connections:
                del self._connections[connection_id]
        logger.info(f"Analytics WebSocket disconnected: {connection_id}")
    
    async def register_activity(
        self,
        user_id: str,
        username: str,
        email: str,
        activity: str,
        subject_name: Optional[str] = None,
        topic_name: Optional[str] = None,
    ) -> None:
        """Register a user's activity (vetting or generating)."""
        now = datetime.now(timezone.utc)
        async with self._lock:
            existing = self._active_users.get(user_id)
            keep_existing_session = bool(existing and existing.activity == activity)
            self._active_users[user_id] = ActiveUser(
                user_id=user_id,
                username=username,
                email=email,
                activity=activity,
                subject_name=(
                    subject_name
                    if subject_name is not None
                    else existing.subject_name if keep_existing_session and existing else None
                ),
                topic_name=(
                    topic_name
                    if topic_name is not None
                    else existing.topic_name if keep_existing_session and existing else None
                ),
                started_at=existing.started_at if keep_existing_session and existing else now,
                last_heartbeat=now,
            )
        
        self.request_live_refresh()
    
    async def update_heartbeat(self, user_id: str) -> None:
        """Update the last heartbeat time for a user."""
        async with self._lock:
            if user_id in self._active_users:
                self._active_users[user_id].last_heartbeat = datetime.now(timezone.utc)
    
    async def clear_activity(self, user_id: str) -> None:
        """Clear a user's active status."""
        async with self._lock:
            if user_id in self._active_users:
                del self._active_users[user_id]
        
        self.request_live_refresh()

    def request_live_refresh(self) -> None:
        """Schedule a coalesced live analytics refresh for all connected viewers."""
        if not self._connections:
            return
        self._broadcast_requested = True
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return

        if self._broadcast_task and not self._broadcast_task.done():
            return

        self._broadcast_task = loop.create_task(self._drain_live_refresh_requests())

    async def _drain_live_refresh_requests(self) -> None:
        """Process queued refresh requests without flooding the analytics WebSocket."""
        while True:
            self._broadcast_requested = False
            await self._broadcast_activity_update()
            await asyncio.sleep(0.1)
            if not self._broadcast_requested:
                break
    
    async def get_active_users(self) -> list[dict]:
        """Get all currently active users."""
        async with self._lock:
            now = datetime.now(timezone.utc)
            # Filter out stale entries so stopped vetting sessions clear quickly.
            active = []
            stale_ids = []
            
            for user_id, user in self._active_users.items():
                age = (now - user.last_heartbeat).total_seconds()
                if age < STALE_ACTIVITY_SECONDS:
                    active.append({
                        "user_id": user.user_id,
                        "username": user.username,
                        "email": user.email,
                        "activity": user.activity,
                        "subject_name": user.subject_name,
                        "topic_name": user.topic_name,
                        "started_at": user.started_at.isoformat(),
                        "duration_seconds": int((now - user.started_at).total_seconds()),
                    })
                else:
                    stale_ids.append(user_id)
            
            # Clean up stale entries
            for uid in stale_ids:
                del self._active_users[uid]
            
            return active

    def _get_background_generation_counts(self) -> tuple[int, int]:
        """Return the currently running and queued automatic generation counts."""
        try:
            from app.api.v1.endpoints.questions import (
                _BACKGROUND_GENERATION_QUEUE,
                _get_current_running_count,
            )

            return _get_current_running_count(), len(_BACKGROUND_GENERATION_QUEUE)
        except Exception as exc:
            logger.debug("Could not load background generation counts: %s", exc)
            return 0, 0
    
    async def _broadcast_activity_update(self) -> None:
        """Broadcast activity update to all connected analytics viewers."""
        try:
            from app.api.v1.endpoints.analytics import _build_live_activity_response, _dump_model

            snapshot = await _build_live_activity_response()
            payload = _dump_model(snapshot)
        except Exception as exc:
            logger.warning("Falling back to minimal analytics snapshot broadcast: %s", exc)
            active_users = await self.get_active_users()
            vetting_users = [user for user in active_users if user["activity"] == "vetting"]
            generating_count, queued_count = self._get_background_generation_counts()
            payload = {
                "active_users": vetting_users,
                "vetting_count": len(vetting_users),
                "generating_count": generating_count,
                "queued_count": queued_count,
                "eligible_topics_count": 0,
                "generated_questions_total": 0,
                "target_questions_total": 0,
                "remaining_questions": 0,
                "topics_below_target_count": 0,
                "topic_backlog_questions_total": 0,
                "surplus_questions_total": 0,
                "generating_items": [],
                "queued_items": [],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        message = {
            "type": "activity_update",
            "data": payload,
        }
        
        async with self._lock:
            connection_ids = list(self._connections.keys())
        
        disconnected = []
        for conn_id in connection_ids:
            async with self._lock:
                conn = self._connections.get(conn_id)
            
            if not conn:
                continue
            
            try:
                await conn.websocket.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send analytics update to {conn_id}: {e}")
                disconnected.append(conn_id)
        
        # Clean up disconnected
        for conn_id in disconnected:
            await self.disconnect(conn_id)
    
    async def broadcast_to_admins(self, message: dict) -> None:
        """Broadcast a message to all admin connections."""
        async with self._lock:
            admin_ids = [
                conn_id for conn_id, conn in self._connections.items()
                if conn.is_admin
            ]
        
        for conn_id in admin_ids:
            async with self._lock:
                conn = self._connections.get(conn_id)
            
            if conn:
                try:
                    await conn.websocket.send_json(message)
                except Exception as e:
                    logger.warning(f"Failed to send to admin {conn_id}: {e}")
    
    def get_connection_count(self) -> int:
        """Get the total number of analytics connections."""
        return len(self._connections)


# Global singleton instance
analytics_ws_manager = AnalyticsWebSocketManager()
