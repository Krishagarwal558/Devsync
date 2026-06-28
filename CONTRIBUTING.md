# Contributing

Thanks for helping DevSync improve. This repo is in public beta, so stability, safety, and clear bug reports matter more than new features.

## Local Checks

Run before opening a pull request:

```powershell
python -m compileall desktop server tests scripts
python -m pytest tests -q
python scripts\public_beta_check.py
```

## Development Rules

- Keep routes thin.
- Put workflows in services.
- Put database access in repositories.
- Do not commit secrets or local runtime files.
- Add tests for bug fixes.
- Prefer small, reviewable changes.

## Good First Areas

- Better tester documentation
- Clearer desktop error messages
- More reliability tests
- Packaging fixes
- Accessibility polish in the desktop UI
