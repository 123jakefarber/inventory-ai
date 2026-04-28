"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Base paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'inventory.db'}").strip()

# ---------------------------------------------------------------------------
# JWT / Auth
# ---------------------------------------------------------------------------
JWT_SECRET: str = os.getenv("JWT_SECRET", "change-me-in-production-use-a-random-string")
JWT_ALGORITHM: str = "HS256"
JWT_ACCESS_EXPIRE_MINUTES: int = int(os.getenv("JWT_ACCESS_EXPIRE_MINUTES", "15"))
JWT_REFRESH_EXPIRE_DAYS: int = int(os.getenv("JWT_REFRESH_EXPIRE_DAYS", "7"))

# ---------------------------------------------------------------------------
# Square OAuth (developer app credentials — NOT per-user)
# ---------------------------------------------------------------------------
SQUARE_APP_ID: str = os.getenv("SQUARE_APP_ID", "").strip()
SQUARE_APP_SECRET: str = os.getenv("SQUARE_APP_SECRET", "").strip()
SQUARE_ENVIRONMENT: str = os.getenv("SQUARE_ENVIRONMENT", "sandbox").strip()  # sandbox | production
SQUARE_BASE_URL: str = (
    "https://connect.squareupsandbox.com"
    if SQUARE_ENVIRONMENT == "sandbox"
    else "https://connect.squareup.com"
)
SQUARE_OAUTH_REDIRECT_URL: str = os.getenv(
    "SQUARE_OAUTH_REDIRECT_URL", "http://localhost:8000/api/auth/square/callback"
).strip()
FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3000").strip()

# ---------------------------------------------------------------------------
# SMTP / Email alerts
# ---------------------------------------------------------------------------
SMTP_HOST: str = os.getenv("SMTP_HOST", "")
SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER: str = os.getenv("SMTP_USER", "")
SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
ALERT_EMAIL_FROM: str = os.getenv("ALERT_EMAIL_FROM", SMTP_USER)

# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------
ALERT_TIME: str = os.getenv("ALERT_TIME", "08:00")  # HH:MM in local time

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"
