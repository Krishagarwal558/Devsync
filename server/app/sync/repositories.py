"""Synchronization event repository."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Select, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.sync.models import SyncEvent
from server.app.workspaces.models import Workspace


class SyncEventRepository:
    """Database access for synchronization events."""

    def __init__(self, session: AsyncSession) -> None:
        """Create repository."""
        self._session = session

    async def lock_workspace_for_sequence(self, workspace_id: UUID) -> None:
        """Acquire a row lock for workspace-scoped sequence assignment."""
        statement = select(Workspace.id).where(Workspace.id == workspace_id).with_for_update()
        await self._session.execute(statement)

    async def next_sequence(self, workspace_id: UUID) -> int:
        """Return the next server-owned sequence number for a workspace."""
        statement = select(func.coalesce(func.max(SyncEvent.sequence), 0) + 1).where(SyncEvent.workspace_id == workspace_id)
        return int(await self._session.scalar(statement))

    async def find_duplicate(
        self,
        workspace_id: UUID,
        sender_device_id: UUID,
        event_type: str,
        path: str,
        payload: dict[str, object],
        checksum: str | None,
    ) -> SyncEvent | None:
        """Find an existing event that matches a repeated client submission."""
        statement: Select[tuple[SyncEvent]] = select(SyncEvent).where(
            SyncEvent.workspace_id == workspace_id,
            SyncEvent.sender_device_id == sender_device_id,
            SyncEvent.event_type == event_type,
            SyncEvent.path == path,
            SyncEvent.payload == payload,
            SyncEvent.checksum == checksum,
        )
        return await self._session.scalar(statement)

    async def create_event(
        self,
        workspace_id: UUID,
        sender_device_id: UUID,
        sequence: int,
        event_type: str,
        path: str,
        payload: dict[str, object],
        checksum: str | None,
        bandwidth_bytes: int,
    ) -> SyncEvent:
        """Persist a synchronization event."""
        event = SyncEvent(
            workspace_id=workspace_id,
            sender_device_id=sender_device_id,
            sequence=sequence,
            event_type=event_type,
            path=path,
            payload=payload,
            checksum=checksum,
            bandwidth_bytes=bandwidth_bytes,
            status="accepted",
        )
        self._session.add(event)
        await self._session.flush()
        await self._session.refresh(event)
        return event

    async def list_events(self, workspace_id: UUID, limit: int, offset: int, after_sequence: int | None = None) -> list[SyncEvent]:
        """Return ordered event history."""
        statement: Select[tuple[SyncEvent]] = (
            select(SyncEvent)
            .where(SyncEvent.workspace_id == workspace_id)
            .order_by(SyncEvent.sequence.asc())
            .limit(limit)
            .offset(offset)
        )
        if after_sequence is not None:
            statement = statement.where(SyncEvent.sequence > after_sequence)
        return list((await self._session.scalars(statement)).all())

    async def replay_events(self, workspace_id: UUID, after_sequence: int, limit: int) -> list[SyncEvent]:
        """Return ordered events after a processed sequence."""
        statement: Select[tuple[SyncEvent]] = (
            select(SyncEvent)
            .where(SyncEvent.workspace_id == workspace_id, SyncEvent.sequence > after_sequence)
            .order_by(SyncEvent.sequence.asc())
            .limit(limit)
        )
        return list((await self._session.scalars(statement)).all())

    async def acknowledge_by_ids(self, workspace_id: UUID, event_ids: list[UUID]) -> int:
        """Mark selected workspace events as acknowledged."""
        statement = (
            update(SyncEvent)
            .where(SyncEvent.workspace_id == workspace_id, SyncEvent.id.in_(event_ids))
            .values(status="acknowledged")
        )
        result = await self._session.execute(statement)
        return int(result.rowcount or 0)

    async def acknowledge_up_to_sequence(self, workspace_id: UUID, up_to_sequence: int) -> int:
        """Mark all workspace events up to a sequence as acknowledged."""
        statement = (
            update(SyncEvent)
            .where(SyncEvent.workspace_id == workspace_id, SyncEvent.sequence <= up_to_sequence)
            .values(status="acknowledged")
        )
        result = await self._session.execute(statement)
        return int(result.rowcount or 0)

