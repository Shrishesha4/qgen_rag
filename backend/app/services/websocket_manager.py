"""
WebSocket manager for real-time generation status updates.
Handles connection management and broadcasting to connected clients.
"""

import asyncio
import json
import logging
from typing import Dict, Set, Optional
from fastapi import WebSocket, WebSocketDisconnect
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ConnectionInfo:
    """Information about a WebSocket connection."""
    websocket: WebSocket
    user_id: str
    subscribed_subjects: Set[str] = field(default_factory=set)
    subscribed_topics: Set[str] = field(default_factory=set)
    subscribed_to_global_stats: bool = False


class GenerationWebSocketManager:
    """
    Manages WebSocket connections for real-time generation status updates.
    Supports subscribing to specific subjects/topics for targeted updates.
    """
    
    def __init__(self):
        # Map of connection_id -> ConnectionInfo
        self._connections: Dict[str, ConnectionInfo] = {}
        # Map of subject_id -> set of connection_ids
        self._subject_subscribers: Dict[str, Set[str]] = {}
        # Map of topic_id -> set of connection_ids
        self._topic_subscribers: Dict[str, Set[str]] = {}
        # Lock for thread-safe operations
        self._lock = asyncio.Lock()
    
    async def connect(self, websocket: WebSocket, connection_id: str, user_id: str) -> None:
        """Accept a new WebSocket connection."""
        await websocket.accept()
        async with self._lock:
            self._connections[connection_id] = ConnectionInfo(
                websocket=websocket,
                user_id=user_id,
            )
        logger.info(f"WebSocket connected: {connection_id} (user: {user_id})")
    
    async def disconnect(self, connection_id: str) -> None:
        """Handle WebSocket disconnection and cleanup subscriptions."""
        async with self._lock:
            if connection_id not in self._connections:
                return
            
            conn_info = self._connections[connection_id]
            
            # Remove from subject subscriptions
            for subject_id in conn_info.subscribed_subjects:
                if subject_id in self._subject_subscribers:
                    self._subject_subscribers[subject_id].discard(connection_id)
                    if not self._subject_subscribers[subject_id]:
                        del self._subject_subscribers[subject_id]
            
            # Remove from topic subscriptions
            for topic_id in conn_info.subscribed_topics:
                if topic_id in self._topic_subscribers:
                    self._topic_subscribers[topic_id].discard(connection_id)
                    if not self._topic_subscribers[topic_id]:
                        del self._topic_subscribers[topic_id]
            
            del self._connections[connection_id]
        
        logger.info(f"WebSocket disconnected: {connection_id}")
    
    async def subscribe_subject(self, connection_id: str, subject_id: str) -> None:
        """Subscribe a connection to updates for a specific subject."""
        async with self._lock:
            if connection_id not in self._connections:
                return
            
            self._connections[connection_id].subscribed_subjects.add(subject_id)
            
            if subject_id not in self._subject_subscribers:
                self._subject_subscribers[subject_id] = set()
            self._subject_subscribers[subject_id].add(connection_id)
        
        logger.debug(f"Connection {connection_id} subscribed to subject {subject_id}")
    
    async def subscribe_topic(self, connection_id: str, topic_id: str) -> None:
        """Subscribe a connection to updates for a specific topic."""
        async with self._lock:
            if connection_id not in self._connections:
                return
            
            self._connections[connection_id].subscribed_topics.add(topic_id)
            
            if topic_id not in self._topic_subscribers:
                self._topic_subscribers[topic_id] = set()
            self._topic_subscribers[topic_id].add(connection_id)
        
        logger.debug(f"Connection {connection_id} subscribed to topic {topic_id}")
    
    async def unsubscribe_subject(self, connection_id: str, subject_id: str) -> None:
        """Unsubscribe a connection from a subject."""
        async with self._lock:
            if connection_id in self._connections:
                self._connections[connection_id].subscribed_subjects.discard(subject_id)
            
            if subject_id in self._subject_subscribers:
                self._subject_subscribers[subject_id].discard(connection_id)
                if not self._subject_subscribers[subject_id]:
                    del self._subject_subscribers[subject_id]
    
    async def unsubscribe_topic(self, connection_id: str, topic_id: str) -> None:
        """Unsubscribe a connection from a topic."""
        async with self._lock:
            if connection_id in self._connections:
                self._connections[connection_id].subscribed_topics.discard(topic_id)
            
            if topic_id in self._topic_subscribers:
                self._topic_subscribers[topic_id].discard(connection_id)
                if not self._topic_subscribers[topic_id]:
                    del self._topic_subscribers[topic_id]
    
    async def broadcast_to_subject(self, subject_id: str, message: dict) -> None:
        """Broadcast a message to all connections subscribed to a subject."""
        async with self._lock:
            connection_ids = self._subject_subscribers.get(subject_id, set()).copy()
        
        if not connection_ids:
            return
        
        await self._send_to_connections(connection_ids, message)
    
    async def broadcast_to_topic(self, topic_id: str, message: dict) -> None:
        """Broadcast a message to all connections subscribed to a topic."""
        async with self._lock:
            connection_ids = self._topic_subscribers.get(topic_id, set()).copy()
        
        if not connection_ids:
            return
        
        await self._send_to_connections(connection_ids, message)
    
    async def broadcast_generation_update(
        self,
        subject_id: str,
        topic_id: str,
        status_data: dict,
    ) -> None:
        """
        Broadcast a generation status update to all relevant subscribers.
        Sends to both subject and topic subscribers.
        """
        message = {
            "type": "generation_status",
            "subject_id": subject_id,
            "topic_id": topic_id,
            "data": status_data,
        }
        
        # Get all relevant connection IDs
        async with self._lock:
            subject_connections = self._subject_subscribers.get(subject_id, set()).copy()
            topic_connections = self._topic_subscribers.get(topic_id, set()).copy()
        
        # Combine and deduplicate
        all_connections = subject_connections | topic_connections
        
        if all_connections:
            await self._send_to_connections(all_connections, message)
            logger.debug(f"Broadcast generation update to {len(all_connections)} connections")
    
    async def _send_to_connections(self, connection_ids: Set[str], message: dict) -> None:
        """Send a message to multiple connections, handling failures gracefully."""
        disconnected = []
        
        for conn_id in connection_ids:
            async with self._lock:
                conn_info = self._connections.get(conn_id)
            
            if not conn_info:
                continue
            
            try:
                await conn_info.websocket.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send to {conn_id}: {e}")
                disconnected.append(conn_id)
        
        # Clean up disconnected connections
        for conn_id in disconnected:
            await self.disconnect(conn_id)
    
    async def send_to_connection(self, connection_id: str, message: dict) -> bool:
        """Send a message to a specific connection."""
        async with self._lock:
            conn_info = self._connections.get(connection_id)
        
        if not conn_info:
            return False
        
        try:
            await conn_info.websocket.send_json(message)
            return True
        except Exception as e:
            logger.warning(f"Failed to send to {connection_id}: {e}")
            await self.disconnect(connection_id)
            return False
    
    def get_connection_count(self) -> int:
        """Get the total number of active connections."""
        return len(self._connections)
    
    def get_subject_subscriber_count(self, subject_id: str) -> int:
        """Get the number of subscribers for a subject."""
        return len(self._subject_subscribers.get(subject_id, set()))
    
    async def subscribe_global_stats(self, connection_id: str) -> None:
        """Subscribe a connection to global stats updates."""
        async with self._lock:
            if connection_id in self._connections:
                self._connections[connection_id].subscribed_to_global_stats = True
        logger.debug(f"Connection {connection_id} subscribed to global stats")
    
    async def unsubscribe_global_stats(self, connection_id: str) -> None:
        """Unsubscribe a connection from global stats updates."""
        async with self._lock:
            if connection_id in self._connections:
                self._connections[connection_id].subscribed_to_global_stats = False
    
    async def broadcast_stats_update(self, stats_data: dict) -> None:
        """
        Broadcast stats update to all connections subscribed to global stats.
        """
        message = {
            "type": "stats_update",
            "data": stats_data,
        }
        
        async with self._lock:
            connection_ids = {
                conn_id for conn_id, conn_info in self._connections.items()
                if conn_info.subscribed_to_global_stats
            }
        
        if connection_ids:
            await self._send_to_connections(connection_ids, message)
            logger.debug(f"Broadcast stats update to {len(connection_ids)} connections")
    
    async def broadcast_subject_stats_update(self, subject_id: str, stats_data: dict) -> None:
        """
        Broadcast subject-specific stats update to subscribers.
        """
        message = {
            "type": "subject_stats_update",
            "subject_id": subject_id,
            "data": stats_data,
        }
        
        async with self._lock:
            # Get subject subscribers and global stats subscribers
            subject_connections = self._subject_subscribers.get(subject_id, set()).copy()
            global_connections = {
                conn_id for conn_id, conn_info in self._connections.items()
                if conn_info.subscribed_to_global_stats
            }
        
        all_connections = subject_connections | global_connections
        
        if all_connections:
            await self._send_to_connections(all_connections, message)
            logger.debug(f"Broadcast subject stats update to {len(all_connections)} connections")
    
    async def broadcast_topic_stats_update(self, subject_id: str, topic_id: str, stats_data: dict) -> None:
        """
        Broadcast topic-specific stats update to subscribers.
        """
        message = {
            "type": "topic_stats_update",
            "subject_id": subject_id,
            "topic_id": topic_id,
            "data": stats_data,
        }
        
        async with self._lock:
            subject_connections = self._subject_subscribers.get(subject_id, set()).copy()
            topic_connections = self._topic_subscribers.get(topic_id, set()).copy()
            global_connections = {
                conn_id for conn_id, conn_info in self._connections.items()
                if conn_info.subscribed_to_global_stats
            }
        
        all_connections = subject_connections | topic_connections | global_connections
        
        if all_connections:
            await self._send_to_connections(all_connections, message)
            logger.debug(f"Broadcast topic stats update to {len(all_connections)} connections")
    
    async def broadcast_all(self, message: dict) -> None:
        """Broadcast a message to all connected clients."""
        async with self._lock:
            connection_ids = set(self._connections.keys())
        
        if connection_ids:
            await self._send_to_connections(connection_ids, message)


# Global singleton instance
generation_ws_manager = GenerationWebSocketManager()
