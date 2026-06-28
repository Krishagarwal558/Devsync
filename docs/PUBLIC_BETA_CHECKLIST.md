# Public Beta Checklist

## Repository

- [ ] README says public beta
- [ ] `.gitignore` exists and protects secrets/runtime files
- [ ] `.env.example` files contain placeholders only
- [ ] Security policy exists
- [ ] Issue templates exist
- [ ] License exists or private licensing is documented

## Backend

- [ ] `DEVSYNC_ENVIRONMENT=beta`
- [ ] Strong JWT secret configured
- [ ] HTTPS public URL configured
- [ ] CORS is not wildcard
- [ ] Cloudflare R2 bucket configured
- [ ] `DEVSYNC_STORAGE_PROVIDER=r2`
- [ ] Upload limit configured
- [ ] Migrations run successfully
- [ ] `/health` returns `ok`

## Desktop

- [ ] Fresh install starts
- [ ] User can configure backend URL
- [ ] User can log in
- [ ] Device registration works
- [ ] Trusted device can join workspace
- [ ] Logs export works
- [ ] Pause/resume works

## Sync

- [ ] Device A upload appears on Device B
- [ ] Device B reconnect replays missed events
- [ ] Conflict copy is created instead of unsafe overwrite
- [ ] Revoked device is blocked
- [ ] Oversized upload is rejected clearly
