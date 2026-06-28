# Google Cloud Run Deployment Guide

This guide deploys the DevSync backend to Google Cloud Run with Neon PostgreSQL and Cloudflare R2 storage.

## Required Accounts

- GitHub repo with DevSync code
- Google Cloud project with billing enabled
- Neon PostgreSQL database
- Cloudflare R2 bucket and S3 API token

## One-Time Setup

Install and authenticate the Google Cloud CLI:

```powershell
gcloud auth login
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID
```

Enable APIs:

```powershell
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com
```

## Environment

Copy the example Cloud Run env file:

```powershell
Copy-Item server\.env.beta.yaml.example server\.env.beta.yaml
```

Fill in:

- `DEVSYNC_DATABASE_URL`
- `DEVSYNC_JWT_SECRET_KEY`
- `DEVSYNC_R2_ENDPOINT_URL`
- `DEVSYNC_R2_BUCKET_NAME`
- `DEVSYNC_R2_ACCESS_KEY_ID`
- `DEVSYNC_R2_SECRET_ACCESS_KEY`
- `DEVSYNC_CORS_ALLOWED_ORIGINS`

Do not commit `server/.env.beta.yaml`.

## Deploy

```powershell
powershell -ExecutionPolicy Bypass -File scripts\deploy_cloud_run.ps1 `
  -ProjectId YOUR_PROJECT_ID `
  -Region asia-south1 `
  -ServiceName devsync-backend `
  -EnvVarsFile server\.env.beta.yaml
```

After deployment, copy the Cloud Run URL and update:

```yaml
DEVSYNC_CORS_ALLOWED_ORIGINS: "[\"https://YOUR-CLOUD-RUN-URL.run.app\"]"
```

Redeploy after changing CORS.

## Health Check

```powershell
Invoke-RestMethod https://YOUR-CLOUD-RUN-URL.run.app/health
```

Expected:

```json
{
  "status": "ok",
  "environment": "beta",
  "version": "0.2.0b1"
}
```

## Migrations

Run migrations against Neon before testers use the backend:

```powershell
Copy-Item server\.env.beta.example server\.env.beta
powershell -ExecutionPolicy Bypass -File scripts\run_neon_migrations.ps1 `
  -EnvFile server\.env.beta `
  -Python "python"
```

The migration env must use the same `DEVSYNC_DATABASE_URL` as Cloud Run.
