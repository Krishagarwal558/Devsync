# Known Limitations

- Local filesystem storage is for development only; public beta should use Cloudflare R2.
- Realtime dispatcher is in-process and does not support multiple backend instances.
- Rate limiting is in-memory and resets on restart.
- Desktop client is an MVP, not a polished installer/service.
- Conflict handling creates copies but does not merge.
- Cloud snapshots are not implemented.
- Delta/chunk sync is not implemented for cloud uploads.
- Team invitations and roles beyond owner-only workspace membership are not implemented.
- Background tray/service mode is not packaged yet.
