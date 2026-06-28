"""Desktop client configuration helpers."""

from __future__ import annotations

from desktop.app.core.local_state import LocalStateStore
from desktop.app.models.settings import ClientSettings


def load_client_settings(state: LocalStateStore) -> ClientSettings:
    """Load settings from local state with defaults."""
    defaults = ClientSettings()
    server_url = state.get_setting("server_url") or defaults.server_url
    return ClientSettings(server_url=server_url, state_path=defaults.state_path)

