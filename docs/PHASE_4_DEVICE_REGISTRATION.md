# Phase 4: Device Registration

Phase 4 adds authenticated device management for DevSync Cloud. Devices represent computers or laptops that a user owns and may later use for workspace synchronization.

## Migration

```powershell
alembic -c server/alembic.ini upgrade head
```

Added migration:

- `20260626_0003_create_devices_table.py`

## Table

- `devices`

Fields:

- `id`
- `user_id`
- `name`
- `platform`
- `public_key`
- `trust_status`
- `last_seen_at`
- `created_at`
- `updated_at`
- `deleted_at`

Trust statuses:

- `pending`
- `trusted`
- `revoked`

## Endpoints

- `POST /v1/devices`
- `GET /v1/devices`
- `GET /v1/devices/{device_id}`
- `PATCH /v1/devices/{device_id}`
- `POST /v1/devices/{device_id}/trust`
- `DELETE /v1/devices/{device_id}`
- `POST /v1/devices/{device_id}/heartbeat`

## Examples

Register:

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/v1/devices `
  -Headers @{ Authorization = "Bearer <access_token>" } `
  -ContentType "application/json" `
  -Body '{"name":"Shrey Laptop","platform":"windows","public_key":"public-key"}'
```

List:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/v1/devices `
  -Headers @{ Authorization = "Bearer <access_token>" }
```

Trust:

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/v1/devices/<device_id>/trust `
  -Headers @{ Authorization = "Bearer <access_token>" }
```

Heartbeat:

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/v1/devices/<device_id>/heartbeat `
  -Headers @{ Authorization = "Bearer <access_token>" }
```

Remove:

```powershell
Invoke-RestMethod -Method Delete http://127.0.0.1:8000/v1/devices/<device_id> `
  -Headers @{ Authorization = "Bearer <access_token>" }
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

- File sync
- Object storage
- WebSockets
- Snapshots
- Conflict handling
- Team invitations
- Device-to-workspace authorization
