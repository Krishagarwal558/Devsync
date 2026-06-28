# Security Notes

- Change `DEVSYNC_JWT_SECRET_KEY` before any internet-facing deployment.
- Use HTTPS only for hosted alpha testing.
- Use Neon/managed PostgreSQL credentials with least privilege.
- Do not use wildcard CORS in production.
- Desktop stores tokens in local SQLite for alpha; public beta should use OS credential storage.
- File blobs are not encrypted at rest by DevSync yet.
- Local filesystem storage is not suitable for public beta durability; use Cloudflare R2.
- Review dependencies before public beta.
