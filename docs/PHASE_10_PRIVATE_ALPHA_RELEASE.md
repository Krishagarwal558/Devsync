# Phase 10: Private Alpha Release Preparation

Phase 10 prepares DevSync for private alpha testing across 2-3 real devices.

## Added

- Backend Dockerfile
- Docker Compose for Postgres + backend
- Production environment example
- Alpha environment example
- Render deployment guide
- Neon PostgreSQL setup guide
- Windows exe build script
- App icon placeholder
- Clean install check script
- Private alpha guide
- Troubleshooting/security/limitations/demo docs

## Commands

Local backend:

```powershell
Copy-Item server\.env.alpha.example server\.env.alpha
docker compose -f docker-compose.alpha.yml --env-file server\.env.alpha up --build
docker compose -f docker-compose.alpha.yml exec backend alembic -c server/alembic.ini upgrade head
```

Desktop:

```powershell
python -m desktop.app.main
```

Package:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_windows_exe.ps1 -Python python
```

Checks:

```powershell
python -m pytest tests -q
python scripts\two_folder_reliability_smoke.py
python scripts\alpha_clean_install_check.py --server-url http://127.0.0.1:8000
```

