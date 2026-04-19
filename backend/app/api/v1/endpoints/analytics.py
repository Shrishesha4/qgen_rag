"""
Analytics API endpoints for real-time activity tracking and historical data.
"""

import uuid
import logging
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.auth_database import get_auth_db
from app.api.v1.deps import get_current_user
from app.models.user import User, ROLE_ADMIN
from app.models.training import VettingLog
from app.models.generation_run import GenerationRun
from app.services.analytics_websocket_manager import analytics_ws_manager

logger = logging.getLogger(__name__)

router = APIRouter()


class ActivityItem(BaseModel):
    user_id: str
    username: str
    email: str
    activity: str
    subject_name: str | None
    topic_name: str | None
    started_at: str
    duration_seconds: int


class ActiveUsersResponse(BaseModel):
    active_users: list[ActivityItem]
    vetting_count: int
    generating_count: int
    queued_count: int
    timestamp: str


class HistoricalActivityItem(BaseModel):
    date: str
    hour: int | None = None
    vetting_count: int
    generation_count: int
    questions_vetted: int
    questions_generated: int
    unique_vetters: int
    unique_generators: int


class HistoricalResponse(BaseModel):
    items: list[HistoricalActivityItem]
    total_vetting_sessions: int
    total_generation_runs: int
    total_questions_vetted: int
    total_questions_generated: int


class RecentActivityItem(BaseModel):
    id: str
    user_id: str
    username: str
    activity_type: str
    subject_name: str | None
    topic_name: str | None
    count: int
    started_at: str
    ended_at: str | None


class RecentActivityResponse(BaseModel):
    items: list[RecentActivityItem]


def _ensure_admin(current_user: User) -> None:
    if current_user.role != ROLE_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can access analytics",
        )


def _get_background_generation_counts() -> tuple[int, int]:
    from app.api.v1.endpoints.questions import (
        _BACKGROUND_GENERATION_QUEUE,
        _get_current_running_count,
    )

    return _get_current_running_count(), len(_BACKGROUND_GENERATION_QUEUE)


async def _build_live_activity_response() -> ActiveUsersResponse:
    all_active_users = await analytics_ws_manager.get_active_users()
    active_users = [user for user in all_active_users if user["activity"] == "vetting"]
    generating_count, queued_count = _get_background_generation_counts()

    return ActiveUsersResponse(
        active_users=[ActivityItem(**u) for u in active_users],
        vetting_count=len(active_users),
        generating_count=generating_count,
        queued_count=queued_count,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


def _dump_model(model: BaseModel) -> dict:
    return model.model_dump() if hasattr(model, "model_dump") else model.dict()


@router.get("/active", response_model=ActiveUsersResponse)
async def get_active_users(
    current_user: User = Depends(get_current_user),
):
    """Get live vetting sessions and automatic generation queue counts."""
    _ensure_admin(current_user)

    return await _build_live_activity_response()


@router.get("/historical", response_model=HistoricalResponse)
async def get_historical_analytics(
    days: int = Query(default=7, ge=1, le=90),
    group_by: str = Query(default="day", pattern="^(day|hour)$"),
    current_user: User = Depends(get_current_user),
):
    """Get historical analytics data grouped by day or hour."""
    _ensure_admin(current_user)
    
    now = datetime.now(timezone.utc)
    start_date = now - timedelta(days=days)
    
    async with AsyncSessionLocal() as db:
        # Get vetting stats
        vetting_query = select(
            func.date(VettingLog.created_at).label("date"),
            func.count(VettingLog.id).label("vetting_count"),
            func.count(func.distinct(VettingLog.vetter_id)).label("unique_vetters"),
        ).where(
            VettingLog.created_at >= start_date
        ).group_by(
            func.date(VettingLog.created_at)
        )
        
        vetting_result = await db.execute(vetting_query)
        vetting_by_date = {str(r.date): {"count": r.vetting_count, "unique": r.unique_vetters} for r in vetting_result}
        
        # Get generation stats
        gen_query = select(
            func.date(GenerationRun.started_at).label("date"),
            func.count(GenerationRun.id).label("gen_count"),
            func.sum(GenerationRun.current_question).label("questions_generated"),
            func.count(func.distinct(GenerationRun.user_id)).label("unique_generators"),
        ).where(
            GenerationRun.started_at >= start_date
        ).group_by(
            func.date(GenerationRun.started_at)
        )
        
        gen_result = await db.execute(gen_query)
        gen_by_date = {
            str(r.date): {
                "count": r.gen_count,
                "questions": r.questions_generated or 0,
                "unique": r.unique_generators
            } for r in gen_result
        }
        
        # Combine into response
        items = []
        all_dates = set(vetting_by_date.keys()) | set(gen_by_date.keys())
        
        for date_str in sorted(all_dates):
            vetting = vetting_by_date.get(date_str, {"count": 0, "unique": 0})
            gen = gen_by_date.get(date_str, {"count": 0, "questions": 0, "unique": 0})
            
            items.append(HistoricalActivityItem(
                date=date_str,
                vetting_count=vetting["count"],
                generation_count=gen["count"],
                questions_vetted=vetting["count"],  # 1 log per question
                questions_generated=gen["questions"],
                unique_vetters=vetting["unique"],
                unique_generators=gen["unique"],
            ))
        
        # Calculate totals
        total_vetting = sum(v["count"] for v in vetting_by_date.values())
        total_gen = sum(g["count"] for g in gen_by_date.values())
        total_questions_vetted = total_vetting
        total_questions_generated = sum(g["questions"] for g in gen_by_date.values())
        
        return HistoricalResponse(
            items=items,
            total_vetting_sessions=total_vetting,
            total_generation_runs=total_gen,
            total_questions_vetted=total_questions_vetted,
            total_questions_generated=total_questions_generated,
        )


@router.get("/recent", response_model=RecentActivityResponse)
async def get_recent_activity(
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
):
    """Get recent activity log."""
    _ensure_admin(current_user)
    
    items = []
    
    async with AsyncSessionLocal() as db:
        # Get recent generation runs
        gen_query = select(GenerationRun).order_by(
            GenerationRun.started_at.desc()
        ).limit(limit // 2)
        
        gen_result = await db.execute(gen_query)
        for run in gen_result.scalars():
            items.append(RecentActivityItem(
                id=str(run.id),
                user_id=str(run.user_id) if run.user_id else "system",
                username=run.user_id or "System",
                activity_type="generation",
                subject_name=None,  # Would need to join
                topic_name=None,
                count=run.generated_count or 0,
                started_at=run.started_at.isoformat() if run.started_at else "",
                ended_at=run.completed_at.isoformat() if run.completed_at else None,
            ))
    
    # Get recent vetting from auth db
    auth_db = None
    try:
        async for db in get_auth_db():
            auth_db = db
            break
        
        if auth_db:
            # Get user lookup for vetting
            pass  # VettingLog is in main DB, users in auth DB
    except Exception as e:
        logger.warning(f"Could not get auth db for user lookup: {e}")
    
    # Sort by time
    items.sort(key=lambda x: x.started_at, reverse=True)
    
    return RecentActivityResponse(items=items[:limit])


@router.websocket("/ws")
async def analytics_websocket(
    websocket: WebSocket,
    token: str = Query(None, description="Auth token for admin identification"),
):
    """
    WebSocket endpoint for real-time analytics updates.
    
    Connect and receive:
    - {"type": "activity_update", "data": {...}}
    
    Send:
    - {"action": "ping"} -> {"type": "pong"}
    """
    connection_id = str(uuid.uuid4())
    
    # For now, allow connections with a token (production would validate)
    user_id = token or "anonymous"
    is_admin = bool(token)  # In production, validate token and check admin role
    
    try:
        await analytics_ws_manager.connect(websocket, connection_id, user_id, is_admin)
        
        # Send initial state
        live_snapshot = await _build_live_activity_response()
        await websocket.send_json({
            "type": "connected",
            "connection_id": connection_id,
        })
        await websocket.send_json({
            "type": "activity_update",
            "data": _dump_model(live_snapshot),
        })
        
        while True:
            try:
                data = await websocket.receive_json()
                action = data.get("action")
                
                if action == "ping":
                    await websocket.send_json({"type": "pong"})
                    await websocket.send_json({
                        "type": "activity_update",
                        "data": _dump_model(await _build_live_activity_response()),
                    })
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
        logger.info(f"Analytics WebSocket disconnected: {connection_id}")
    except Exception as e:
        logger.error(f"Analytics WebSocket error for {connection_id}: {e}")
    finally:
        await analytics_ws_manager.disconnect(connection_id)
