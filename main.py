"""Application entry point — composition root.

Only this file knows how everything is assembled.

The app can be driven three different ways:
  - HTTP server: uvicorn main:api --reload
  - CLI:         python -m cli preview --mikrotik <ip>
  - Docker:      docker compose up -d
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import bootstrap
from api.router import router
from core.config import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

HERE = Path(__file__).parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    bootstrap.run()
    if not config.api_key:
        logging.warning(
            "\n" + "=" * 70 + "\n"
            "  API authentication is DISABLED.\n"
            "  To enable, set API_KEY in your .env file. Generate one with:\n"
            "    python -c \"import secrets; print(secrets.token_urlsafe(32))\"\n"
            "  Do NOT expose this service to the public internet without auth.\n"
            + "=" * 70
        )
    yield


api = FastAPI(title="IP Suspension Tool", lifespan=lifespan)

api.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
api.include_router(router)


@api.get("/")
async def root() -> FileResponse:
    return FileResponse(HERE / "static" / "index.html")
