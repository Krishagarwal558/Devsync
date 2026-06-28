# DevSync

DevSync is a public beta developer workspace sync system. It includes a FastAPI cloud backend and a Python/PySide6 desktop client for syncing project folders across trusted devices.

> Public beta means usable for testing with real devices, but not yet suitable for important production data.

## What Works

- Authentication with JWT access tokens and refresh-token rotation
- Workspaces and owner-only membership
- Trusted device registration
- Ordered sync event protocol
- File upload, download, soft delete, and version metadata
- WebSocket realtime updates
- Python desktop sync client MVP
- Local filesystem storage provider
- Retry queues, conflict copies, sync status, debug logs, and release checks

## Not Ready Yet

- Team invitations
- Cloud snapshots
- Delta/chunk sync for large files
- S3/R2 object storage
- End-to-end encryption
- Full conflict resolver UI
- Paid plans or hosted SaaS operations

## Quick Start

Clone the repo:

```powershell
git clone https://github.com/Krishagarwal558/Devsync.git
cd Devsync
```

Copy a local env file:

```powershell
Copy-Item server\.env.example server\.env
```

Start local Postgres + backend:

```powershell
docker compose -f docker-compose.alpha.yml --env-file server\.env up --build
```

Run migrations inside the backend container:

```powershell
docker compose -f docker-compose.alpha.yml exec backend alembic -c server/alembic.ini upgrade head
```

Health check:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Run the desktop client:

```powershell
python -m desktop.app.main
```

## Public Beta Deployment

Use `server/.env.beta.example` as the template for an internet-facing beta deployment.

Minimum requirements:

- HTTPS public backend URL
- Managed PostgreSQL, such as Neon
- Strong `DEVSYNC_JWT_SECRET_KEY`
- No wildcard CORS
- Persistent `DEVSYNC_STORAGE_ROOT`
- Migrations run before accepting users

Read:

- [Public Beta Guide](docs/PUBLIC_BETA_GUIDE.md)
- [Render Deployment Guide](docs/RENDER_DEPLOYMENT_GUIDE.md)
- [Neon PostgreSQL Setup](docs/NEON_POSTGRES_SETUP.md)
- [Security Notes](docs/SECURITY_NOTES.md)
- [Known Limitations](docs/KNOWN_LIMITATIONS.md)

## Test And Release Checks

```powershell
python -m compileall desktop server tests scripts
python -m pytest tests -q
python scripts\two_folder_reliability_smoke.py
python scripts\public_beta_check.py
```

## Build Windows Desktop App

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_windows_exe.ps1 -Python python
```

## Important Folders

```text
server/                 FastAPI backend
desktop/app/            PySide6 desktop client
docs/                   release, deployment, and testing guides
scripts/                packaging, smoke, and release-check scripts
server/storage/         local MVP file storage, ignored by Git
~/.devsync/             desktop state and logs
```

## Security

Do not commit real `.env` files, database URLs, JWT secrets, local SQLite state, logs, or uploaded file storage. If you accidentally expose a database URL or token, rotate it immediately.

Report vulnerabilities using the guidance in [SECURITY.md](SECURITY.md).
