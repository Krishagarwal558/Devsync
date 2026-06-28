# DevSync Cloud Phase 3: Workspace Management

Phase 3 implements workspace management only, on top of Phase 2 authentication.

Included:

- Create workspace
- List current user's workspaces
- Get workspace details
- Rename workspace
- Update workspace settings
- Archive workspace
- Soft delete workspace
- Owner membership row on workspace creation
- Permission checks using the current authenticated user

Not included:

- Sync
- Storage
- WebSocket
- Devices
- Snapshots
- Conflicts
- Team invitations

## Migration

Migration file:

```text
server/app/database/migrations/versions/20260626_0002_create_workspace_tables.py
```

Tables:

```text
workspaces
workspace_members
```

Run:

```powershell
C:\Users\shrey\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m alembic -c server\alembic.ini upgrade head
```

## Endpoints

```text
POST   /v1/workspaces
GET    /v1/workspaces
GET    /v1/workspaces/{workspace_id}
PATCH  /v1/workspaces/{workspace_id}
POST   /v1/workspaces/{workspace_id}/archive
DELETE /v1/workspaces/{workspace_id}
```

All endpoints require:

```text
Authorization: Bearer ACCESS_TOKEN
```

## Example Requests

Create workspace:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/v1/workspaces -Headers @{
  Authorization = "Bearer PASTE_ACCESS_TOKEN"
} -ContentType 'application/json' -Body '{
  "name": "Game Project",
  "settings": {
    "auto_sync": true
  }
}'
```

List workspaces:

```powershell
Invoke-RestMethod -Method Get -Uri http://127.0.0.1:8000/v1/workspaces -Headers @{
  Authorization = "Bearer PASTE_ACCESS_TOKEN"
}
```

Include archived workspaces:

```powershell
Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8000/v1/workspaces?include_archived=true" -Headers @{
  Authorization = "Bearer PASTE_ACCESS_TOKEN"
}
```

Rename/update settings:

```powershell
Invoke-RestMethod -Method Patch -Uri http://127.0.0.1:8000/v1/workspaces/WORKSPACE_ID -Headers @{
  Authorization = "Bearer PASTE_ACCESS_TOKEN"
} -ContentType 'application/json' -Body '{
  "name": "Renamed Project",
  "settings": {
    "auto_sync": false
  }
}'
```

Archive:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/v1/workspaces/WORKSPACE_ID/archive -Headers @{
  Authorization = "Bearer PASTE_ACCESS_TOKEN"
}
```

Soft delete:

```powershell
Invoke-RestMethod -Method Delete -Uri http://127.0.0.1:8000/v1/workspaces/WORKSPACE_ID -Headers @{
  Authorization = "Bearer PASTE_ACCESS_TOKEN"
}
```

## Tests

Unit tests:

```powershell
C:\Users\shrey\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest tests\server\unit
```

PostgreSQL API tests:

```powershell
$env:DEVSYNC_TEST_DATABASE_URL = "postgresql+asyncpg://devsync:devsync@localhost:5432/devsync_test"
C:\Users\shrey\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest tests\server\api
```

