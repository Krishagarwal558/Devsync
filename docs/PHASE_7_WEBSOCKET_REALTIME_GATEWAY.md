# Phase 7: WebSocket Realtime Gateway

Phase 7 adds realtime workspace updates through a WebSocket gateway. Connected trusted devices can join workspace rooms, receive replayed sync events after reconnect, send heartbeats, acknowledge processed sequences, and receive broadcasts when REST APIs create sync events.

This phase does not implement snapshots, conflict resolution, team invitations, chunk/delta sync, cloud object storage, or desktop client code.

## Endpoint

```txt
/v1/ws?token=<access_token>
```

The access token is the same JWT access token returned by Phase 2 authentication.

## Client Events

Join workspace:

```json
{
  "type": "workspace_join",
  "workspace_id": "workspace-uuid",
  "device_id": "trusted-device-uuid",
  "last_sequence": 0
}
```

Leave workspace:

```json
{
  "type": "workspace_leave",
  "workspace_id": "workspace-uuid"
}
```

Heartbeat:

```json
{
  "type": "device_heartbeat",
  "workspace_id": "workspace-uuid",
  "device_id": "trusted-device-uuid"
}
```

Ack:

```json
{
  "type": "sync_ack",
  "workspace_id": "workspace-uuid",
  "sequence": 44
}
```

## Server Events

Joined:

```json
{
  "type": "workspace_joined",
  "workspace_id": "workspace-uuid",
  "replayed_events": 3
}
```

Sync event:

```json
{
  "type": "sync_event",
  "workspace_id": "workspace-uuid",
  "sequence": 44,
  "event_type": "file_modified",
  "path": "src/app.py",
  "payload": {
    "metadata": {
      "file_id": "file-uuid",
      "version_id": "version-uuid"
    }
  },
  "checksum": "sha256-example",
  "size_bytes": 128
}
```

Presence:

```json
{
  "type": "device_connected",
  "workspace_id": "workspace-uuid",
  "device_id": "device-uuid",
  "device_name": "Krish Laptop"
}
```

```json
{
  "type": "device_disconnected",
  "workspace_id": "workspace-uuid",
  "device_id": "device-uuid"
}
```

Error:

```json
{
  "type": "error",
  "code": "permission_denied",
  "message": "Trusted device required"
}
```

## Connection Flow

1. Client connects to `/v1/ws?token=<access_token>`.
2. Server authenticates the JWT access token and active session.
3. Client sends `workspace_join`.
4. Server validates workspace membership, active workspace status, device ownership, and trusted device status.
5. Server subscribes the connection to the workspace room.
6. Server replays sync events after `last_sequence`.
7. Server broadcasts presence to other devices.
8. REST-created sync events are broadcast to joined devices except the sender device.

## REST Integration

The Phase 5 sync event service publishes accepted events after commit.

The Phase 6 file upload and restore flows publish their automatically-created sync events after commit.

This is implemented through an internal process-local realtime dispatcher. It is intentionally simple for the MVP and can later be replaced with Redis, Postgres NOTIFY, or another broker when multiple backend instances are introduced.

## Tests

```powershell
python -m pytest tests\server -q
```

PostgreSQL-gated WebSocket API tests require:

```powershell
$env:DEVSYNC_TEST_DATABASE_URL="postgresql+asyncpg://devsync:devsync@127.0.0.1:5432/devsync_test"
python -m pytest tests\server\api\test_websocket_api.py -q
```

## Not Implemented Yet

- Snapshots
- Conflict resolution
- Team invitations
- Chunk/delta sync
- Cloud object storage
- Desktop client code
- Multi-instance realtime broker
