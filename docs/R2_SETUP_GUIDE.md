# Cloudflare R2 Setup Guide

DevSync public beta uses Cloudflare R2 through its S3-compatible API for file blobs.

## Create Bucket

1. Open Cloudflare dashboard.
2. Go to **R2 Object Storage**.
3. Create a bucket, for example `devsync-beta`.
4. Keep the bucket private.

## Create R2 API Token

1. In R2, create an API token.
2. Grant object read/write access to the DevSync bucket.
3. Copy:
   - Account ID
   - Access Key ID
   - Secret Access Key

## DevSync Env

Use:

```text
DEVSYNC_STORAGE_PROVIDER=r2
DEVSYNC_R2_ENDPOINT_URL=https://ACCOUNT_ID.r2.cloudflarestorage.com
DEVSYNC_R2_BUCKET_NAME=devsync-beta
DEVSYNC_R2_ACCESS_KEY_ID=...
DEVSYNC_R2_SECRET_ACCESS_KEY=...
```

Do not commit real R2 credentials.

## Storage Layout

DevSync stores blobs by internal IDs, not user paths:

```text
workspaces/{workspace_id}/versions/{file_id}/{version_id}.bin
```

This keeps object keys stable even when files are renamed or moved.
