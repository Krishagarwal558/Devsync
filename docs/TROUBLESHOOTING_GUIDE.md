# Troubleshooting Guide

## Backend Does Not Start

- Check `DEVSYNC_DATABASE_URL`.
- Check `DEVSYNC_JWT_SECRET_KEY` is not the development default in production.
- Run migrations.

## Health Check Fails

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

If Docker is used:

```powershell
docker compose -f docker-compose.alpha.yml ps
docker compose -f docker-compose.alpha.yml logs backend
```

## Desktop Cannot Login

- Confirm server URL.
- Confirm backend `/health`.
- Confirm user exists.
- Export debug logs from desktop dashboard.

## Files Do Not Sync

- Confirm both devices use the same workspace.
- Confirm both devices are trusted.
- Confirm sync is started.
- Check ignored paths.
- Click `Retry queued`.

## Conflicts Appear

This is expected if local and remote both changed. Keep the desired file and delete the conflict copy manually for alpha.

