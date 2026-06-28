# Render Deployment Guide

## Service Type

Use a Render Web Service.

## Build Command

```bash
pip install -e .
```

## Start Command

```bash
uvicorn server.app.main:app --host 0.0.0.0 --port $PORT
```

## Environment Variables

Use `server/.env.production.example` as the checklist.

Required:

- `DEVSYNC_ENVIRONMENT=production`
- `DEVSYNC_DATABASE_URL`
- `DEVSYNC_JWT_SECRET_KEY`
- `DEVSYNC_STORAGE_ROOT`
- `DEVSYNC_CORS_ALLOWED_ORIGINS`

## Migrations

Run after deploy:

```bash
alembic -c server/alembic.ini upgrade head
```

## Health Check

```txt
/health
```

## Storage Warning

Render instance disk may be ephemeral depending on service type. For private alpha, local storage is acceptable only for short tests. Public beta needs object storage.

