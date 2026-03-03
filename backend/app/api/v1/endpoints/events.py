"""
Server-Sent Events endpoint — streams real-time table-change notifications
to authenticated clients.

GET /api/v1/events
  Authorization: Bearer <access_token>

The stream emits events of the form:

    event: table_change
    data: {"table":"questions","op":"INSERT","id":"...","user_id":"...","ts":1234567890.123}

A keepalive comment (``: keepalive``) is sent every 30 s to prevent
proxies / load-balancers from closing the connection.
"""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.api.v1.deps import get_current_active_user
from app.models.user import User
from app.services.event_broadcaster import broadcaster

logger = logging.getLogger(__name__)

router = APIRouter()

KEEPALIVE_INTERVAL = 30  # seconds


async def _event_generator(request: Request, user: User):
    """Async generator that yields SSE-formatted text frames."""
    user_id = str(user.id)
    sub = await broadcaster.subscribe(user_id=user_id)

    try:
        # Initial connection confirmation
        yield _sse_frame("connected", {"user_id": user_id})

        # We run two concurrent coroutines:
        #   1. Drain events from the subscription queue
        #   2. Emit keepalive pings
        # When the client disconnects, ``request.is_disconnected()`` becomes
        # True and we break out.
        queue_iter = sub.__aiter__()

        while True:
            if await request.is_disconnected():
                break

            try:
                # Wait for next event, but time-out so we can send keepalives
                event = await asyncio.wait_for(
                    queue_iter.__anext__(),
                    timeout=KEEPALIVE_INTERVAL,
                )
                yield _sse_frame("table_change", {
                    "table": event.table,
                    "op": event.op,
                    "id": event.id,
                    "user_id": event.user_id,
                    "ts": event.ts,
                })
            except asyncio.TimeoutError:
                # No event within the keepalive window → send comment ping
                yield ": keepalive\n\n"
            except StopAsyncIteration:
                # Subscription closed server-side
                break
    finally:
        await broadcaster.unsubscribe(sub)
        logger.debug("SSE client disconnected (user=%s)", user_id)


def _sse_frame(event: str, data: dict) -> str:
    """Format a single SSE frame."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.get(
    "",
    summary="Real-time event stream",
    description="SSE stream of database change notifications scoped to the authenticated user.",
    response_class=StreamingResponse,
)
async def event_stream(
    request: Request,
    current_user: User = Depends(get_current_active_user),
):
    return StreamingResponse(
        _event_generator(request, current_user),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )
