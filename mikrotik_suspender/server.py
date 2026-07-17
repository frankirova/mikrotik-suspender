"""HTTP server entry point using the same bind configuration that security validates."""

from __future__ import annotations

import uvicorn

from core.config import AppConfig


def main() -> None:
    config = AppConfig()
    config.validate_security()
    uvicorn.run("main:api", host=config.host, port=config.port)


if __name__ == "__main__":
    main()
