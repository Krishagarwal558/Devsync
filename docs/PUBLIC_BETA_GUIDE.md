# Public Beta Guide

DevSync public beta is meant for small real-world testing with people who understand the current limitations.

## Beta Scope

Supported:

- One account using multiple trusted devices
- Workspace folder sync through the FastAPI backend
- File upload/download/version metadata
- WebSocket realtime notifications
- Local desktop conflict copies when a safe overwrite is not possible

Not supported:

- Team collaboration
- End-to-end encryption
- Snapshot restore from the cloud
- Large-file delta sync

## Before You Invite Testers

1. Rotate any database password or secret that was ever shared in chat, screenshots, or logs.
2. Deploy the backend behind HTTPS.
3. Set `DEVSYNC_ENVIRONMENT=beta`.
4. Set a strong random `DEVSYNC_JWT_SECRET_KEY`.
5. Create a Cloudflare R2 bucket and set `DEVSYNC_STORAGE_PROVIDER=r2`.
6. Set `DEVSYNC_CORS_ALLOWED_ORIGINS` to the exact public backend/UI origins.
7. Run Alembic migrations.
8. Confirm `/health` returns `status: ok`.
9. Run `python scripts/public_beta_check.py`.
10. Create a test account, workspace, and trusted device.
11. Run the two-folder simulation before using two real devices.

## Tester Instructions

Give testers:

- Backend URL
- Known limitations
- Troubleshooting guide
- A test folder recommendation
- A request not to sync private keys, passwords, production databases, or irreplaceable files

## Beta Exit Criteria

Move toward public beta 2 only after:

- Reconnect behavior is stable across sleep/wake
- Conflict copies are understandable to testers
- Logs are exportable and useful
- Oversized uploads fail clearly
- A fresh device can join and catch up from event replay
