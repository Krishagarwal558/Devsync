# Security Policy

DevSync is currently public beta software. Do not use it for secrets, production credentials, private keys, or irreplaceable files.

## Supported Versions

| Version | Status |
| --- | --- |
| `0.2.x-beta` | Security fixes accepted |
| `0.1.x-alpha` | Unsupported |

## Reporting A Vulnerability

Open a private GitHub security advisory if available. If not, contact the maintainer directly before publishing details.

Please include:

- A clear description of the issue
- Steps to reproduce
- Affected endpoint or desktop flow
- Expected impact
- Logs with secrets removed

## Secret Handling

Never commit:

- Real `.env` files
- Database URLs with passwords
- JWT secrets
- Refresh tokens or access tokens
- Local SQLite state
- Uploaded file blobs
- Debug logs containing user data

If a secret is exposed, rotate it immediately.
