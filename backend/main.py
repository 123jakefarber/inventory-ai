"""FastAPI application entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers.auth import router as auth_router
from routers.inventory import router as inventory_router
from scheduler import on_shutdown, on_startup

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)


# ---------------------------------------------------------------------------
# Lifespan (startup / shutdown)
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    on_startup()
    yield
    on_shutdown()


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Inventory AI",
    description="AI-powered inventory management for Square ecommerce brands.",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow the Next.js frontend on localhost:3000
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth_router)
app.include_router(inventory_router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
