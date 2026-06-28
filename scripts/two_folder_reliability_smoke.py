"""Two-folder DevSync reliability smoke simulation.

This script exercises local safety behaviors without requiring a cloud deployment:

- safe path checks
- checksum tracking
- conflict-copy creation
- retry queue behavior
"""

from __future__ import annotations

import argparse
import asyncio
import shutil
import sys
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from desktop.app.core.local_state import LocalStateStore
from desktop.app.services.sync_service import DesktopSyncService


class SmokeFileClient:
    """Small fake cloud file client for local reliability simulation."""

    def __init__(self) -> None:
        self.fail_upload = True
        self.uploads: list[str] = []

    async def upload_file(self, workspace_id: str, device_id: str, local_file: Path, remote_path: str, checksum: str) -> dict[str, object]:
        if self.fail_upload:
            raise RuntimeError("simulated network disconnect")
        self.uploads.append(remote_path)
        return {"file_id": str(uuid.uuid4()), "version_id": str(uuid.uuid4()), "checksum": checksum, "size_bytes": local_file.stat().st_size}

    async def download_file(self, workspace_id: str, file_id: str) -> bytes:
        return b"remote update"

    async def delete_file(self, workspace_id: str, file_id: str) -> None:
        return None


async def run(root: Path) -> None:
    """Run smoke test."""
    device_a = root / "device-a"
    device_b = root / "device-b"
    shutil.rmtree(root, ignore_errors=True)
    device_a.mkdir(parents=True)
    device_b.mkdir(parents=True)
    state = LocalStateStore(root / "state.sqlite")
    workspace_id = uuid.uuid4()
    device_id = uuid.uuid4()
    state.save_setting("workspace_id", str(workspace_id))
    state.save_setting("device_id", str(device_id))
    state.save_setting("local_folder_path", str(device_a))
    client = SmokeFileClient()
    service = DesktopSyncService(state, client, "http://localhost:8000", "token")

    local_file = device_a / "src" / "app.py"
    local_file.parent.mkdir()
    local_file.write_text("first change", encoding="utf-8")
    try:
        await service.upload_changed_file(local_file)
    except RuntimeError:
        print("queued failed upload")
    client.fail_upload = False
    uploads, downloads = await service.retry_pending()
    print(f"retried uploads={uploads} downloads={downloads}")

    state.save_known_file(workspace_id, "src/app.py", "known-old")
    local_file.write_text("local edit", encoding="utf-8")
    service.apply_remote_file(local_file, "src/app.py", b"remote edit", "remote-new")
    print(f"local conflict exists={(local_file.with_name('app.py.LOCAL-CONFLICT')).exists()}")
    print(f"remote conflict exists={(local_file.with_name('app.py.REMOTE-CONFLICT')).exists()}")
    print(f"simulation root={root}")


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("work") / "phase9-reliability-smoke")
    args = parser.parse_args()
    asyncio.run(run(args.root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
