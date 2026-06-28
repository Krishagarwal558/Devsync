from __future__ import annotations

from pathlib import Path

import pytest

from desktop.app.core.path_utils import UnsafePathError, local_path_for_remote, normalize_remote_path, remote_path_for_local, sha256_file


def test_normalize_remote_path_accepts_safe_paths() -> None:
    assert normalize_remote_path("src\\app.py") == "src/app.py"


@pytest.mark.parametrize("path", ["", "/abs.txt", "C:/abs.txt", "../secret.txt", "src/../secret.txt"])
def test_normalize_remote_path_rejects_unsafe_paths(path: str) -> None:
    with pytest.raises(UnsafePathError):
        normalize_remote_path(path)


def test_local_remote_path_roundtrip(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    local_file = root / "src" / "app.py"
    local_file.parent.mkdir(parents=True)
    local_file.write_text("print('ok')", encoding="utf-8")

    remote = remote_path_for_local(root, local_file)
    resolved = local_path_for_remote(root, remote)

    assert remote == "src/app.py"
    assert resolved == local_file.resolve()
    assert sha256_file(local_file)


def test_local_path_for_remote_rejects_escape(tmp_path: Path) -> None:
    with pytest.raises(UnsafePathError):
        local_path_for_remote(tmp_path, "../escape.txt")

