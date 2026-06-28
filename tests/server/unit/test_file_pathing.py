from __future__ import annotations

import pytest

from server.app.files.pathing import normalize_workspace_path
from server.app.utils.errors import ResourceConflict


def test_normalize_workspace_path_accepts_relative_paths() -> None:
    assert normalize_workspace_path("src\\app.py") == "src/app.py"
    assert normalize_workspace_path(" src/app.py ") == "src/app.py"


@pytest.mark.parametrize("path", ["", "/absolute.txt", "C:/secret.txt", "../secret.txt", "src/../secret.txt"])
def test_normalize_workspace_path_rejects_unsafe_paths(path: str) -> None:
    with pytest.raises(ResourceConflict):
        normalize_workspace_path(path)

