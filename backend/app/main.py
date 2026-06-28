"""Backend entry point."""

from __future__ import annotations

import logging

from backend.app.api.app_factory import create_app


app = create_app()


def main() -> int:
    """Run the backend with uvicorn when dependencies are installed."""
    try:
        import uvicorn
    except ImportError as exc:
        raise RuntimeError("uvicorn is not installed. Install project dependencies first.") from exc
    logging.basicConfig(level=logging.INFO)
    uvicorn.run("backend.app.main:app", host="127.0.0.1", port=8000, reload=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

