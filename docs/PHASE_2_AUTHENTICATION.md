# DevSync Cloud Phase 2: Authentication

Phase 2 implements authentication only.

Included:

- `POST /v1/auth/register`
- `POST /v1/auth/login`
- `POST /v1/auth/logout`
- `POST /v1/auth/refresh`
- `GET /v1/users/me`
- `users` table
- `sessions` table
- JWT access tokens
- Hashed rotating refresh tokens
- Passlib/bcrypt password hashing
- SQLAlchemy 2.0 async PostgreSQL models and repositories
- Alembic migration
- Consistent error responses

Not included in Phase 2:

- Workspaces
- Devices
- Sync
- Storage
- WebSockets
- Snapshots
- Conflicts

## Example `.env`

Copy `server/.env.example` to `.env` and update secrets:

```env
DEVSYNC_APP_NAME=DevSync Cloud
DEVSYNC_ENVIRONMENT=development
DEVSYNC_LOG_LEVEL=INFO
DEVSYNC_DATABASE_URL=postgresql+asyncpg://devsync:devsync@localhost:5432/devsync
DEVSYNC_JWT_SECRET_KEY=replace-this-with-at-least-32-random-characters
DEVSYNC_JWT_ALGORITHM=HS256
DEVSYNC_ACCESS_TOKEN_MINUTES=15
DEVSYNC_REFRESH_TOKEN_DAYS=30
DEVSYNC_BCRYPT_ROUNDS=12
```

## Run Migrations

From the repository root:

```powershell
C:\Users\shrey\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m alembic -c server\alembic.ini upgrade head
```

## Start Server

```powershell
C:\Users\shrey\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m uvicorn server.app.main:app --reload
```

Server URL:

```text
http://127.0.0.1:8000
```

OpenAPI docs:

```text
http://127.0.0.1:8000/docs
```

## Example API Requests

Register:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/v1/auth/register -ContentType 'application/json' -Body '{
  "email": "shrey@example.com",
  "password": "strong-password-123",
  "display_name": "Shrey"
}'
```

Login:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/v1/auth/login -ContentType 'application/json' -Body '{
  "email": "shrey@example.com",
  "password": "strong-password-123"
}'
```

Refresh:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/v1/auth/refresh -ContentType 'application/json' -Body '{
  "refresh_token": "PASTE_REFRESH_TOKEN"
}'
```

Current user:

```powershell
Invoke-RestMethod -Method Get -Uri http://127.0.0.1:8000/v1/users/me -Headers @{
  Authorization = "Bearer PASTE_ACCESS_TOKEN"
}
```

Logout:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/v1/auth/logout -ContentType 'application/json' -Body '{
  "refresh_token": "PASTE_REFRESH_TOKEN"
}'
```

## Tests

Unit tests:

```powershell
C:\Users\shrey\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest tests\server\unit
```

PostgreSQL API tests require a test database:

```powershell
$env:DEVSYNC_TEST_DATABASE_URL = "postgresql+asyncpg://devsync:devsync@localhost:5432/devsync_test"
C:\Users\shrey\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest tests\server\api
```

The API tests intentionally skip when `DEVSYNC_TEST_DATABASE_URL` is not set. They do not use an in-memory fake database.

