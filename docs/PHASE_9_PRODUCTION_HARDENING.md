# Phase 9: Production Hardening and Reliability

Phase 9 improves release safety without adding major product features.

## Backend Hardening

- Added `/health` alongside `/v1/health`.
- Switched backend logging to structured JSON logs.
- Preserved `X-Request-ID` in success and error responses.
- Added consistent handlers for validation and HTTP errors.
- Added basic in-memory HTTP rate limiting.
- Added safer CORS settings through `DEVSYNC_CORS_ALLOWED_ORIGINS`.
- Added production settings validation for JWT secrets and CORS wildcards.
- Added early upload size rejection using `Content-Length`.
- Retained streaming upload size enforcement in the storage provider.

## Desktop Reliability

- Added retry queues for failed uploads, deletes, and downloads.
- Added retry button in the desktop dashboard.
- Added visible conflict warning label.
- Added export debug logs button.
- Improved safe shutdown of watcher and realtime WebSocket.
- Preserved conflict-copy behavior:
  - `filename.LOCAL-CONFLICT`
  - `filename.REMOTE-CONFLICT`
- Realtime WebSocket client already reconnects automatically; now covered by unit tests.

## Integration Smoke Script

Run:

```powershell
python scripts\two_folder_reliability_smoke.py
```

It verifies:

- failed upload is queued
- retry queue replays successfully
- conflict copies are created safely

## Reliability Test Commands

```powershell
python -m compileall desktop server tests scripts
python -m pytest tests -q
python scripts\two_folder_reliability_smoke.py
```

PostgreSQL-backed API tests still require:

```powershell
$env:DEVSYNC_TEST_DATABASE_URL="postgresql+asyncpg://devsync:devsync@127.0.0.1:5432/devsync_test"
python -m pytest tests\server\api -q
```

## Remaining Blockers Before Public Release

- Real deployment environment and domain
- Managed PostgreSQL backups
- Multi-instance realtime broker instead of in-process dispatcher
- Durable distributed rate limiting
- Object storage for production file blobs
- End-to-end packaged desktop installer
- Full conflict resolver UI
- Security review and dependency audit
- Observability dashboard and alerting
