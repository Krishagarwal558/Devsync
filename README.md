# DevSync

DevSync is a private-alpha developer folder sync system. It includes a FastAPI cloud backend and a Python/PySide6 desktop client for syncing local folders across trusted devices.

## Current Alpha Scope

Implemented:

- Auth with JWT access tokens and refresh-token rotation
- Workspaces
- Trusted devices
- Sync event protocol
- File upload/download/versioning
- WebSocket realtime gateway
- Python desktop sync client MVP
- Local filesystem storage provider
- Reliability hardening, retry queues, conflict copies, and debug export

Not implemented yet:

- Team invitations
- Snapshots in cloud sync
- Delta/chunk sync for cloud
- Cloud object storage
- Public deployment automation
- Full conflict resolver UI

## Run Backend Locally

Copy alpha env:

```powershell
Copy-Item server\.env.alpha.example server\.env.alpha
```

Start local Postgres + backend:

```powershell
docker compose -f docker-compose.alpha.yml --env-file server\.env.alpha up --build
```

Run migrations inside the backend container:

```powershell
docker compose -f docker-compose.alpha.yml exec backend alembic -c server/alembic.ini upgrade head
```

Health check:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

## Run Desktop Client

```powershell
python -m desktop.app.main
```

Build Windows exe:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_windows_exe.ps1 -Python python
```

## Alpha Test Scripts

```powershell
python -m compileall desktop server tests scripts
python -m pytest tests -q
python scripts\two_folder_reliability_smoke.py
python scripts\alpha_clean_install_check.py --server-url http://127.0.0.1:8000
```

## Important Folders

```text
server/                 FastAPI backend
desktop/app/            PySide6 desktop client
docs/                   phase docs and alpha guides
scripts/                packaging and reliability scripts
server/storage/         local MVP file storage
~/.devsync/             desktop state and logs
```

## Private Alpha Path

1. Deploy backend or run local Docker compose.
2. Run migrations.
3. Create an account and workspace through API or desktop flow.
4. Install/run the desktop client on 2-3 devices.
5. Log in using the same backend URL.
6. Trust each device.
7. Attach local folders to the same workspace.
8. Edit files and verify uploads/downloads/reconnects/conflict copies.

