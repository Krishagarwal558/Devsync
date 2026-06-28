# Phase 8: Desktop Sync Client MVP

Phase 8 adds a Python desktop client that connects a local folder to DevSync Cloud. It can log in, register or reuse a trusted device, attach a folder to an existing workspace, watch local file changes, upload changed files, receive realtime sync events, download remote updates, and keep local state in SQLite.

This phase intentionally avoids snapshots, conflict resolution UI, team invitations, chunk/delta sync, cloud object storage, and advanced UI polish.

## Main Modules

- `desktop/app/core/auth_client.py`
- `desktop/app/core/workspace_client.py`
- `desktop/app/core/device_client.py`
- `desktop/app/core/file_client.py`
- `desktop/app/core/sync_client.py`
- `desktop/app/core/websocket_client.py`
- `desktop/app/core/watcher.py`
- `desktop/app/core/local_state.py`
- `desktop/app/core/ignore_rules.py`
- `desktop/app/core/path_utils.py`
- `desktop/app/core/config.py`
- `desktop/app/services/sync_service.py`
- `desktop/app/services/workspace_service.py`
- `desktop/app/services/device_service.py`
- `desktop/app/models/settings.py`
- `desktop/app/models/sync_state.py`
- `desktop/app/ui/windows/main_window.py`

## Local State

SQLite stores:

- `server_url`
- `access_token`
- `refresh_token`
- user profile
- `device_id`
- `workspace_id`
- `local_folder_path`
- `last_sequence`
- known file checksums
- upload/download queues
- ignored paths
- recent activity

Default path:

```txt
~/.devsync/desktop_state.sqlite
```

## Ignore Rules

The watcher ignores:

- `.devsync/`
- `node_modules/`
- `.venv/`
- `__pycache__/`
- `dist/`
- `build/`
- `target/`
- `.git/`
- `*.log`

## Upload Flow

1. Watchdog detects local create/modify/delete.
2. Ignore rules are checked.
3. File checksum is calculated.
4. Known local checksum is compared.
5. Changed files upload through `/files/upload`.
6. Backend creates sync event automatically.
7. Local SQLite state is updated.
8. Activity log is updated.

## Download Flow

1. WebSocket receives `sync_event`.
2. Client reads `file_id` and `version_id` from payload metadata.
3. Client downloads current file bytes.
4. File is written through a temp file and atomic replace.
5. Known checksum and `last_sequence` are updated.
6. Activity log is updated.

## Conflict MVP

If a remote update arrives but the local file changed since the last known checksum, the client creates:

```txt
filename.LOCAL-CONFLICT
filename.REMOTE-CONFLICT
```

It does not silently overwrite local work.

## Run Desktop Client

```powershell
python -m desktop.app.main
```

Or, after installing the package:

```powershell
devsync-desktop
```

## Example Setup Flow

1. Start DevSync Cloud.
2. Run the desktop app.
3. Enter server URL, email, and password.
4. Select an existing cloud workspace.
5. Select a local folder.
6. Click `Connect Workspace`.
7. Click `Start sync`.
8. Edit files in the folder; changed files upload to cloud.

## Required Packages

- `PySide6`
- `watchdog`
- `httpx`
- `websockets`
- `pydantic`

## Tests

```powershell
python -m pytest tests\desktop -q
python -m pytest tests -q
```

## Not Implemented Yet

- Snapshots
- Full conflict resolver UI
- Team invitations
- Chunk/delta sync
- Cloud object storage
- Advanced UI polish
- Background OS tray/service packaging
