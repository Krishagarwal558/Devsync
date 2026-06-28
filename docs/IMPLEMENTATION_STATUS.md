# DevSync Implementation Status

This repository now has two layers:

1. The original runnable Python local sync prototype in `devsync/`.
2. The production-oriented architecture skeleton in `backend/`, `core/`, `desktop/`, and `shared/`.

## Built Now

- Local workspace initialization, scan, chunking, snapshots, restore, and local folder sync.
- Backend domain models for users, devices, workspaces, members, permissions, and sync operations.
- Backend use cases for registration, login, device registration/trust, workspace creation/listing, and sync operation submission.
- Password hashing and signed token service using Python standard library.
- Repository interfaces and in-memory development repositories.
- FastAPI app factory ready for dependency installation.
- Desktop MVVM dashboard view model and PySide6 launch entry point.
- Shared WebSocket event constants.

## Not Yet Built

- PostgreSQL SQLAlchemy repositories.
- Alembic migrations.
- Real WebSocket gateway.
- PySide6 full UI screens.
- Cloud chunk relay and object storage.
- Device-to-device internet sync.
- Team invite flow.
- End-to-end encryption.

## How To Run Current Prototype

Use the CLI:

```powershell
python -m devsync --help
```

If `python` is not on PATH in Codex, use the bundled runtime:

```powershell
C:\Users\shrey\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m devsync --help
```

## How To Run The Future Backend

Install the project dependencies first. Then:

```powershell
uvicorn backend.app.main:app --reload
```

The backend currently uses in-memory repositories until the PostgreSQL implementation is added.

