"""Synchronization protocol API routes."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from server.app.auth.dependencies import get_current_user
from server.app.auth.models import User
from server.app.sync.dependencies import get_sync_event_service
from server.app.sync.schemas import (
    AcknowledgeSyncEventsRequest,
    AcknowledgeSyncEventsResponse,
    CreateSyncEventRequest,
    ReplaySyncEventsResponse,
    SyncEventPage,
    SyncEventResponse,
)
from server.app.sync.services import SyncEventService

router = APIRouter(prefix="/v1/workspaces/{workspace_id}/sync", tags=["sync"])


@router.post("/events", response_model=SyncEventResponse, status_code=status.HTTP_201_CREATED)
async def create_sync_event(
    workspace_id: UUID,
    request: CreateSyncEventRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    sync_service: Annotated[SyncEventService, Depends(get_sync_event_service)],
) -> SyncEventResponse:
    """Submit synchronization event metadata."""
    event = await sync_service.create_event(current_user, workspace_id, request)
    return SyncEventResponse.model_validate(event)


@router.get("/events", response_model=SyncEventPage)
async def list_sync_events(
    workspace_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    sync_service: Annotated[SyncEventService, Depends(get_sync_event_service)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    after_sequence: Annotated[int | None, Query(ge=0)] = None,
) -> SyncEventPage:
    """Retrieve ordered synchronization history."""
    events = await sync_service.list_events(
        current_user,
        workspace_id,
        limit=limit,
        offset=offset,
        after_sequence=after_sequence,
    )
    next_offset = offset + limit if len(events) == limit else None
    return SyncEventPage(
        items=[SyncEventResponse.model_validate(event) for event in events],
        limit=limit,
        offset=offset,
        next_offset=next_offset,
    )


@router.get("/events/replay", response_model=ReplaySyncEventsResponse)
async def replay_sync_events(
    workspace_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    sync_service: Annotated[SyncEventService, Depends(get_sync_event_service)],
    after_sequence: Annotated[int, Query(ge=0)],
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> ReplaySyncEventsResponse:
    """Replay events after the client's last processed sequence."""
    events = await sync_service.replay_events(current_user, workspace_id, after_sequence=after_sequence, limit=limit)
    next_after_sequence = events[-1].sequence if len(events) == limit else None
    return ReplaySyncEventsResponse(
        after_sequence=after_sequence,
        items=[SyncEventResponse.model_validate(event) for event in events],
        next_after_sequence=next_after_sequence,
    )


@router.post("/ack", response_model=AcknowledgeSyncEventsResponse)
async def acknowledge_sync_events(
    workspace_id: UUID,
    request: AcknowledgeSyncEventsRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    sync_service: Annotated[SyncEventService, Depends(get_sync_event_service)],
) -> AcknowledgeSyncEventsResponse:
    """Acknowledge processed synchronization events."""
    count = await sync_service.acknowledge_events(current_user, workspace_id, request)
    return AcknowledgeSyncEventsResponse(acknowledged_count=count)

