# Phase 6: File Storage and File Versioning

Phase 6 adds real file upload/download support to DevSync Cloud. It stores binary file versions on the local filesystem for the MVP and keeps version metadata in PostgreSQL.

This phase does not implement WebSockets, snapshots, conflict resolution, team invitations, chunk/delta sync, cloud object storage, or desktop client code.

## Design Choice

Uploads automatically create the matching Phase 5 sync event.

Reason: the MVP should not allow a stored blob with no synchronization event. The upload and event metadata are committed together, so other devices can rely on the event stream after the upload succeeds.

Restores create a new latest metadata version that points to the previous stored blob. This preserves version history without duplicating binary data.

## Migration

```powershell
alembic -c server/alembic.ini upgrade head
```

Added migration:

- `20260626_0005_create_file_storage_tables.py`

## Tables

### files

- `id`
- `workspace_id`
- `path`
- `file_type`
- `current_version_id`
- `deleted_at`
- `created_at`
- `updated_at`

### file_versions

- `id`
- `file_id`
- `workspace_id`
- `created_by_device_id`
- `content_checksum`
- `size_bytes`
- `storage_key`
- `version_number`
- `created_at`

Important constraints:

- `workspace_id + path` is unique
- `file_id + version_number` is unique
- `current_version_id` points to the active version

## Storage Layout

```txt
server/storage/
  workspaces/
    {workspace_id}/
      versions/
        {file_id}/
          {version_id}.bin
```

Files are stored by internal IDs, not user paths. This prevents path collision and unsafe path problems when files are renamed or moved later.

## APIs

- `POST /v1/workspaces/{workspace_id}/files/upload`
- `GET /v1/workspaces/{workspace_id}/files`
- `GET /v1/workspaces/{workspace_id}/files/{file_id}/download`
- `DELETE /v1/workspaces/{workspace_id}/files/{file_id}`
- `GET /v1/workspaces/{workspace_id}/files/{file_id}/versions`
- `POST /v1/workspaces/{workspace_id}/files/{file_id}/restore`

## Example Upload

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/v1/workspaces/<workspace_id>/files/upload `
  -Headers @{ Authorization = "Bearer <access_token>" } `
  -Form @{
    path = "src/app.py"
    sender_device_id = "<trusted_device_id>"
    checksum = "<optional_sha256>"
    file_type = "file"
    file = Get-Item ".\src\app.py"
  }
```

## Example Download

```powershell
Invoke-WebRequest http://127.0.0.1:8000/v1/workspaces/<workspace_id>/files/<file_id>/download `
  -Headers @{ Authorization = "Bearer <access_token>" } `
  -OutFile ".\downloaded-app.py"
```

## Example Restore

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/v1/workspaces/<workspace_id>/files/<file_id>/restore `
  -Headers @{ Authorization = "Bearer <access_token>" } `
  -ContentType "application/json" `
  -Body '{ "version_id": "<version_id>", "sender_device_id": "<trusted_device_id>" }'
```

## Settings

```env
DEVSYNC_STORAGE_ROOT=server/storage
DEVSYNC_MAX_UPLOAD_BYTES=52428800
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

- WebSockets
- Snapshots
- Conflict resolution
- Team invitations
- Chunk/delta sync
- Cloud object storage
- Desktop client code
