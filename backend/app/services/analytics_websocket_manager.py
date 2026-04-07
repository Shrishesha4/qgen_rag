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
        async with self._lock:
            self._active_users[user_id] = ActiveUser(
                user_id=user_id,
                username=username,
                email=email,
                activity=activity,
                subject_name=subject_name,
                topic_name=topic_name,
            )
        
        # Broadcast update to all analytics viewers (non-blocking)
        asyncio.create_task(self._broadcast_activity_update())
    
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
        
        # Broadcast update to all analytics viewers (non-blocking)
        asyncio.create_task(self._broadcast_activity_update())
    
    async def get_active_users(self) -> list[dict]:
        """Get all currently active users."""
        async with self._lock:
            now = datetime.now(timezone.utc)
            # Filter out stale entries (no heartbeat in 5 minutes)
            active = []
            stale_ids = []
            
            for user_id, user in self._active_users.items():
                age = (now - user.last_heartbeat).total_seconds()
                if age < 300:  # 5 minutes
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
    
    async def _broadcast_activity_update(self) -> None:
        """Broadcast activity update to all connected analytics viewers."""
        active_users = await self.get_active_users()
        message = {
            "type": "activity_update",
            "data": {
                "active_users": active_users,
                "vetting_count": len([u for u in active_users if u["activity"] == "vetting"]),
                "generating_count": len([u for u in active_users if u["activity"] == "generating"]),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
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
