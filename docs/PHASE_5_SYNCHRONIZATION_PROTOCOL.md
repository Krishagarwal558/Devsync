# Phase 5: Synchronization Protocol and Event System

Phase 5 defines the REST synchronization metadata protocol. It records ordered file-system change events, but it does not transfer file bytes.

## Migration

```powershell
alembic -c server/alembic.ini upgrade head
```

Added migration:

- `20260626_0004_create_sync_events_table.py`

## Database Schema

Table: `sync_events`

- `id`
- `workspace_id`
- `sender_device_id`
- `sequence`
- `event_type`
- `path`
- `payload`
- `checksum`
- `bandwidth_bytes`
- `status`
- `created_at`

Important constraints:

- `sequence` is unique per `workspace_id`
- `sequence` is assigned by the server
- `event_type` is constrained to supported protocol events
- `status` is constrained to `accepted` or `acknowledged`

Supported event types:

- `file_created`
- `file_modified`
- `file_deleted`
- `folder_created`
- `folder_deleted`
- `rename`
- `move`
- `metadata_changed`

## APIs

- `POST /v1/workspaces/{workspace_id}/sync/events`
- `GET /v1/workspaces/{workspace_id}/sync/events`
- `GET /v1/workspaces/{workspace_id}/sync/events/replay`
- `POST /v1/workspaces/{workspace_id}/sync/ack`

## Example Requests

Create event:

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/v1/workspaces/<workspace_id>/sync/events `
  -Headers @{ Authorization = "Bearer <access_token>" } `
  -ContentType "application/json" `
  -Body '{
    "sender_device_id": "<trusted_device_id>",
    "event_type": "file_modified",
    "path": "src/app.py",
    "checksum": "sha256-example",
    "bandwidth_bytes": 128,
    "payload": {
      "file_size": 128,
      "modified_at": "2026-06-26T10:30:00Z",
      "metadata": { "language": "python" }
    }
  }'
```

Replay after sequence:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/v1/workspaces/<workspace_id>/sync/events/replay?after_sequence=381" `
  -Headers @{ Authorization = "Bearer <access_token>" }
```

Acknowledge:

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/v1/workspaces/<workspace_id>/sync/ack `
  -Headers @{ Authorization = "Bearer <access_token>" } `
  -ContentType "application/json" `
  -Body '{ "device_id": "<trusted_device_id>", "up_to_sequence": 382 }'
```

## Example Responses

Created event:

```json
{
  "id": "4cf6d2cb-93fd-4d1e-8bd3-48b4f190b083",
  "workspace_id": "a1a4710f-bb72-4215-9242-0c60349bd3af",
  "sender_device_id": "826bcdb5-09f5-44c6-993a-4074a91d3daa",
  "sequence": 382,
  "event_type": "file_modified",
  "path": "src/app.py",
  "payload": {
    "file_size": 128,
    "modified_at": "2026-06-26T10:30:00Z",
    "metadata": {
      "language": "python"
    }
  },
  "checksum": "sha256-example",
  "bandwidth_bytes": 128,
  "status": "accepted",
  "created_at": "2026-06-26T10:30:02Z"
}
```

Replay:

```json
{
  "after_sequence": 381,
  "items": [],
  "next_after_sequence": null
}
```

## Tests

```powershell
python -m pytest tests\server -q
```

API tests require PostgreSQL:

```powershell
$env:DEVSYNC_TEST_DATABASE_URL="postgresql+asyncpg://devsync:devsync@127.0.0.1:5432/devsync_test"
python -m pytest tests\server\api -q
```

## Not Implemented Yet

- WebSocket gateway
- File uploads/downloads
- Local storage
- Snapshots
- Conflict resolution
- Team invitations
