from __future__ import annotations

from pathlib import Path


def test_private_alpha_release_files_exist() -> None:
    required = [
        "Dockerfile.backend",
        "docker-compose.alpha.yml",
        "server/.env.production.example",
        "server/.env.alpha.example",
        "scripts/build_windows_exe.ps1",
        "scripts/alpha_clean_install_check.py",
        "desktop/assets/app-icon-placeholder.svg",
        "docs/PRIVATE_ALPHA_TESTING_GUIDE.md",
        "docs/RENDER_DEPLOYMENT_GUIDE.md",
        "docs/NEON_POSTGRES_SETUP.md",
        "docs/KNOWN_LIMITATIONS.md",
        "docs/TROUBLESHOOTING_GUIDE.md",
        "docs/SECURITY_NOTES.md",
        "docs/DEMO_SCRIPT.md",
    ]

    for path in required:
        assert Path(path).exists(), path
