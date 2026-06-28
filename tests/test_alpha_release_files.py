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


def test_public_beta_release_files_exist() -> None:
    required = [
        ".gitignore",
        "LICENSE",
        "SECURITY.md",
        "CONTRIBUTING.md",
        ".github/ISSUE_TEMPLATE/bug_report.yml",
        ".github/ISSUE_TEMPLATE/feature_request.yml",
        ".github/PULL_REQUEST_TEMPLATE.md",
        "server/.env.beta.example",
        "server/.env.beta.yaml.example",
        "docs/PUBLIC_BETA_GUIDE.md",
        "docs/PUBLIC_BETA_CHECKLIST.md",
        "docs/CLOUD_RUN_DEPLOYMENT_GUIDE.md",
        "docs/R2_SETUP_GUIDE.md",
        "scripts/public_beta_check.py",
        "scripts/deploy_cloud_run.ps1",
        "scripts/run_neon_migrations.ps1",
    ]

    for path in required:
        assert Path(path).exists(), path
