from __future__ import annotations

import uuid

from desktop.app.core.local_state import LocalStateStore


def test_local_state_persists_settings_files_queues_and_activity(tmp_path) -> None:  # type: ignore[no-untyped-def]
    state = LocalStateStore(tmp_path / "state.sqlite")
    workspace_id = uuid.uuid4()

    state.save_setting("server_url", "http://localhost:8000")
    state.save_known_file(workspace_id, "src/app.py", "abc", file_id="file", version_id="version")
    state.enqueue("upload", workspace_id, "src/app.py", {"reason": "changed"})
    state.add_activity("Uploaded src/app.py.")

    assert state.get_setting("server_url") == "http://localhost:8000"
    assert state.get_known_checksum(workspace_id, "src/app.py") == "abc"
    assert state.get_known_file(workspace_id, "src/app.py")["file_id"] == "file"  # type: ignore[index]
    assert state.list_queue("upload")[0]["payload"] == {"reason": "changed"}
    assert state.recent_activity() == ["Uploaded src/app.py."]


def test_local_state_reset_clears_alpha_config(tmp_path) -> None:  # type: ignore[no-untyped-def]
    state = LocalStateStore(tmp_path / "state.sqlite")
    workspace_id = uuid.uuid4()
    state.save_setting("server_url", "http://localhost:8000")
    state.save_known_file(workspace_id, "src/app.py", "abc")
    state.enqueue("upload", workspace_id, "src/app.py", {"reason": "changed"})
    state.add_activity("Uploaded.")

    state.reset()

    assert state.get_setting("server_url") is None
    assert state.get_known_checksum(workspace_id, "src/app.py") is None
    assert state.list_queue("upload") == []
    assert state.recent_activity() == []
