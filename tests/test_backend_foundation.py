from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from backend.app.application.auth import (
    LoginCommand,
    LoginUseCase,
    RegisterDeviceCommand,
    RegisterDeviceUseCase,
    RegisterUserCommand,
    RegisterUserUseCase,
    TrustDeviceUseCase,
)
from backend.app.application.sync import SubmitSyncOperationCommand, SubmitSyncOperationUseCase
from backend.app.application.workspaces import CreateWorkspaceCommand, CreateWorkspaceUseCase, ListWorkspacesUseCase
from backend.app.container import build_container
from backend.app.domain.identity import DeviceTrustStatus
from backend.app.domain.sync import SyncOperationType
from core.devsync_core.files.local_indexer import LocalWorkspaceIndexer


class BackendFoundationTests(unittest.TestCase):
    def test_register_login_device_and_workspace_flow(self) -> None:
        container = build_container()

        user = RegisterUserUseCase(container.users, container.password_hasher).execute(
            RegisterUserCommand(
                email="Ada@Example.com",
                display_name="Ada",
                password="correct horse battery staple",
            )
        )
        self.assertEqual(user.email, "ada@example.com")

        tokens = LoginUseCase(
            container.users,
            container.devices,
            container.password_hasher,
            container.token_service,
        ).execute(LoginCommand(email="ada@example.com", password="correct horse battery staple"))
        payload = container.token_service.verify(tokens.access_token, "access")
        self.assertEqual(payload["sub"], str(user.id))

        device = RegisterDeviceUseCase(container.users, container.devices).execute(
            RegisterDeviceCommand(user_id=user.id, name="Laptop", public_key="local-public-key")
        )
        self.assertEqual(device.trust_status, DeviceTrustStatus.PENDING)
        trusted = TrustDeviceUseCase(container.devices).execute(device.id)
        self.assertEqual(trusted.trust_status, DeviceTrustStatus.TRUSTED)

        workspace = CreateWorkspaceUseCase(container.users, container.workspaces).execute(
            CreateWorkspaceCommand(owner_id=user.id, name="Game Project")
        )
        visible = ListWorkspacesUseCase(container.workspaces).execute(user.id)
        self.assertEqual([item.id for item in visible], [workspace.id])

        operation = SubmitSyncOperationUseCase(container.workspaces, container.sync_operations).execute(
            SubmitSyncOperationCommand(
                workspace_id=workspace.id,
                device_id=device.id,
                operation_type=SyncOperationType.FILE_UPDATED,
                path="src/main.py",
                payload={"content_hash": "abc123"},
            )
        )
        self.assertEqual(operation.sequence, 1)


class CoreAdapterTests(unittest.TestCase):
    def test_local_indexer_initializes_and_scans_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "app.py").write_text("print('hello')\n", encoding="utf-8")

            indexer = LocalWorkspaceIndexer(root)
            meta_dir = indexer.initialize("test-workspace")
            self.assertTrue(meta_dir.exists())

            summary = indexer.scan()
            self.assertEqual(summary.added, 2)
            status = indexer.status()
            self.assertEqual(status["active_files"], 2)
            self.assertGreaterEqual(int(status["chunks"] or 0), 1)


if __name__ == "__main__":
    unittest.main()

