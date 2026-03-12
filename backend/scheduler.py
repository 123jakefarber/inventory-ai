"""APScheduler setup for daily prediction runs and email alerts."""

from __future__ import annotations

import asyncio
import logging

from apscheduler.schedulers.background import BackgroundScheduler

import config
from database import SessionLocal, User, SquareConnection, init_db
from services.alert_service import send_alert_email
from services.prediction_engine import run_all_predictions
from services.square_service import SquareService

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def _daily_job() -> None:
    """For each user with a Square connection, sync and run predictions."""
    logger.info("Running scheduled daily job...")
    db = SessionLocal()
    try:
        users = db.query(User).all()
        for user in users:
            try:
                conn = db.query(SquareConnection).filter(SquareConnection.user_id == user.id).first()
                if conn and conn.access_token:
                    svc = SquareService(access_token=conn.access_token, location_id=conn.location_id or "")
                    asyncio.run(svc.full_sync(db, user.id))

                run_all_predictions(db, user.id)
            except Exception:
                logger.exception("Error in daily job for user %d", user.id)

        send_alert_email(db)
    except Exception:
        logger.exception("Error in daily job")
    finally:
        db.close()


def start_scheduler() -> None:
    """Parse ALERT_TIME, register the daily job, and start the scheduler."""
    hour, minute = (int(p) for p in config.ALERT_TIME.split(":"))
    scheduler.add_job(
        _daily_job,
        trigger="cron",
        hour=hour,
        minute=minute,
        id="daily_predictions",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started — daily job at %s", config.ALERT_TIME)


def on_startup() -> None:
    """Called once when the FastAPI app starts.

    1. Initialise (create) DB tables.
    2. Start the scheduler.

    Demo data is seeded per-user via POST /api/auth/seed-demo.
    """
    init_db()
    start_scheduler()


def on_shutdown() -> None:
    """Gracefully shut down the scheduler."""
    scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped.")
