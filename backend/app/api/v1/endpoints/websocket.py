"""
WebSocket endpoints for real-time updates.
"""

import uuid
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.services.websocket_manager import generation_ws_manager
from app.models.generation_run import GenerationRun

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/generation-status")
async def websocket_generation_status(
    websocket: WebSocket,
    token: str = Query(None, description="Auth token for user identification"),
):
    """
    WebSocket endpoint for real-time generation status updates.
    
    Connect and send messages to subscribe/unsubscribe:
    - {"action": "subscribe_subject", "subject_id": "..."}
    - {"action": "subscribe_topic", "topic_id": "..."}
    - {"action": "unsubscribe_subject", "subject_id": "..."}
    - {"action": "unsubscribe_topic", "topic_id": "..."}
    - {"action": "get_active_runs", "subject_id": "..."}
    
    Server will send:
    - {"type": "generation_status", "subject_id": "...", "topic_id": "...", "data": {...}}
    - {"type": "active_runs", "runs": [...]}
    - {"type": "error", "message": "..."}
    - {"type": "subscribed", "subject_id": "..." or "topic_id": "..."}
    """
    connection_id = str(uuid.uuid4())
    
    # For now, we'll use a simple token-based auth or allow anonymous connections
    # In production, you'd validate the token and extract user_id
    user_id = token or "anonymous"
    
    try:
        await generation_ws_manager.connect(websocket, connection_id, user_id)
        
        # Send initial connection confirmation
        await websocket.send_json({
            "type": "connected",
            "connection_id": connection_id,
        })
        
        while True:
            try:
                data = await websocket.receive_json()
                action = data.get("action")
                
                if action == "subscribe_subject":
                    subject_id = data.get("subject_id")
                    if subject_id:
                        await generation_ws_manager.subscribe_subject(connection_id, subject_id)
                        await websocket.send_json({
                            "type": "subscribed",
                            "subject_id": subject_id,
                        })
                        # Send current active runs for this subject
                        await _send_active_runs(websocket, subject_id)
                
                elif action == "subscribe_topic":
                    topic_id = data.get("topic_id")
                    if topic_id:
                        await generation_ws_manager.subscribe_topic(connection_id, topic_id)
                        await websocket.send_json({
                            "type": "subscribed",
                            "topic_id": topic_id,
                        })
                
                elif action == "unsubscribe_subject":
                    subject_id = data.get("subject_id")
                    if subject_id:
                        await generation_ws_manager.unsubscribe_subject(connection_id, subject_id)
                        await websocket.send_json({
                            "type": "unsubscribed",
                            "subject_id": subject_id,
                        })
                
                elif action == "unsubscribe_topic":
                    topic_id = data.get("topic_id")
                    if topic_id:
                        await generation_ws_manager.unsubscribe_topic(connection_id, topic_id)
                        await websocket.send_json({
                            "type": "unsubscribed",
                            "topic_id": topic_id,
                        })
                
                elif action == "get_active_runs":
                    subject_id = data.get("subject_id")
                    if subject_id:
                        await _send_active_runs(websocket, subject_id)
                
                elif action == "subscribe_global_stats":
                    await generation_ws_manager.subscribe_global_stats(connection_id)
                    await websocket.send_json({
                        "type": "subscribed",
                        "global_stats": True,
                    })
                
                elif action == "unsubscribe_global_stats":
                    await generation_ws_manager.unsubscribe_global_stats(connection_id)
                    await websocket.send_json({
                        "type": "unsubscribed",
                        "global_stats": True,
                    })
                
                elif action == "ping":
                    await websocket.send_json({"type": "pong"})
                
                else:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Unknown action: {action}",
                    })
            
            except ValueError as e:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Invalid message format: {str(e)}",
                })
    
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {connection_id}")
    except Exception as e:
        logger.error(f"WebSocket error for {connection_id}: {e}")
    finally:
        await generation_ws_manager.disconnect(connection_id)


async def _send_active_runs(websocket: WebSocket, subject_id: str) -> None:
    """Send all active generation runs for a subject."""
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(GenerationRun)
                .where(
                    GenerationRun.subject_id == subject_id,
                    GenerationRun.in_progress == True,
                )
            )
            runs = result.scalars().all()
            
            await websocket.send_json({
                "type": "active_runs",
                "subject_id": subject_id,
                "runs": [run.to_status_dict() for run in runs],
            })
    except Exception as e:
        logger.error(f"Failed to fetch active runs: {e}")
        await websocket.send_json({
            "type": "error",
            "message": "Failed to fetch active runs",
        })
