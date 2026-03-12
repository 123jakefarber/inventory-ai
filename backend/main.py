"""FastAPI application entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import traceback

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

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
    from database import init_db
    init_db()
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
        "https://inventory-ai-3gp5.vercel.app",
        config.FRONTEND_URL,
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth_router)
app.include_router(inventory_router)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    tb = traceback.format_exc()
    logging.error(f"Unhandled error: {exc}\n{tb}")
    return JSONResponse(status_code=500, content={"detail": str(exc), "traceback": tb})

@app.get("/health")
def health_check():
    return {"status": "ok"}
