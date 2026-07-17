"""Application entry point — composition root.

Only this file knows how everything is assembled.

The app can be driven three different ways:
  - HTTP server: mikrotik-suspender-server
  - CLI:         mikrotik-suspender plan --router <alias>
  - Docker:      docker compose up -d
"""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import bootstrap
from api.router import router
from core.config import AppConfig, RouterConfig

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
config = AppConfig()

HERE = Path(__file__).parent
STATIC_DIR = (
    HERE / "static"
    if (HERE / "static").exists()
    else Path(sys.prefix) / "share" / "mikrotik-suspender" / "static"
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.ready = False
    config.validate_security()
    app.state.router_config = RouterConfig()
    bootstrap.run(config)
    if not config.api_key:
        logging.warning(
            "\n" + "=" * 70 + "\n"
            "  API authentication is DISABLED.\n"
            "  To enable, set API_KEY in your .env file. Generate one with:\n"
            '    python -c "import secrets; print(secrets.token_urlsafe(32))"\n'
            "  Do NOT expose this service to the public internet without auth.\n" + "=" * 70
        )
    app.state.ready = True
    try:
        yield
    finally:
        app.state.ready = False
        del app.state.router_config


api = FastAPI(title="MikroTik Suspender", version="0.1.0", lifespan=lifespan)

api.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

api.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
api.include_router(router)


@api.get("/")
async def root() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
