# Private Alpha Testing Guide

Use this guide for 2-3 trusted testers/devices.

## Backend Setup

Local Docker:

```powershell
Copy-Item server\.env.alpha.example server\.env.alpha
docker compose -f docker-compose.alpha.yml --env-file server\.env.alpha up --build
docker compose -f docker-compose.alpha.yml exec backend alembic -c server/alembic.ini upgrade head
Invoke-RestMethod http://127.0.0.1:8000/health
```

Render/Neon:

1. Create Neon PostgreSQL database.
2. Set `DEVSYNC_DATABASE_URL` from Neon using the asyncpg format.
3. Deploy the backend on Render.
4. Run migrations.
5. Confirm `/health`.

## Desktop Setup

```powershell
python -m desktop.app.main
```

Or build:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_windows_exe.ps1 -Python python
```

## First-Run Checklist

- Server URL entered correctly
- Account created
- Workspace exists
- Device registered and trusted
- Local folder selected
- Sync started
- Test file created on Device A
- File appears on Device B
- Reconnect tested by stopping/starting network/backend
- Conflict tested by editing same file locally before remote update

## Alpha Pass Criteria

- Login succeeds on both devices
- Workspace list loads
- Local folder binds
- Upload appears in backend file listing
- WebSocket reconnects after temporary disconnect
- Conflict copies are created instead of silent overwrite
- Debug logs export successfully

