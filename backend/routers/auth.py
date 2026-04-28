"""Authentication and Square OAuth endpoints."""

from __future__ import annotations

import logging
import secrets
from typing import Any, Dict, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

import config
from database import SquareConnection, User, get_db
from mock_data import seed_database
from services.auth_service import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    hash_password,
    verify_password,
)
from services.prediction_engine import run_all_predictions

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# Request/Response models
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    email: str
    password: str
    business_name: Optional[str] = None


class LoginRequest(BaseModel):
    email: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    user: Dict[str, Any]


def _user_dict(user: User, square_connected: bool = False) -> Dict[str, Any]:
    return {
        "id": user.id,
        "email": user.email,
        "business_name": user.business_name,
        "square_connected": square_connected,
    }


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------

@router.post("/register", response_model=TokenResponse)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    """Create a new user account."""
    existing = db.query(User).filter(User.email == req.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    user = User(
        email=req.email,
        hashed_password=hash_password(req.password),
        business_name=req.business_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
        user=_user_dict(user),
    )


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    """Login with email and password."""
    user = db.query(User).filter(User.email == req.email).first()
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    sq = db.query(SquareConnection).filter(SquareConnection.user_id == user.id).first()

    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
        user=_user_dict(user, square_connected=sq is not None),
    )


@router.post("/refresh")
def refresh(req: RefreshRequest, db: Session = Depends(get_db)):
    """Get a new access token using a refresh token."""
    payload = decode_token(req.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user_id = int(payload["sub"])
    user = db.query(User).get(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return {
        "access_token": create_access_token(user.id),
        "user": _user_dict(user),
    }


@router.get("/me")
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Return the current user's profile and Square connection status."""
    sq = db.query(SquareConnection).filter(SquareConnection.user_id == user.id).first()
    result = _user_dict(user, square_connected=sq is not None)
    if sq:
        result["square"] = {
            "merchant_id": sq.merchant_id,
            "location_id": sq.location_id,
            "connected_at": sq.connected_at.isoformat() if sq.connected_at else None,
        }
    return result


# ---------------------------------------------------------------------------
# Demo data
# ---------------------------------------------------------------------------

@router.post("/seed-demo")
def seed_demo(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Load demo/mock data into the current user's account."""
    seed_database(db, user.id)
    run_all_predictions(db, user.id)
    return {"status": "ok", "message": "Demo data loaded"}


# ---------------------------------------------------------------------------
# Square OAuth
# ---------------------------------------------------------------------------

@router.get("/square/authorize")
def square_authorize(user: User = Depends(get_current_user)):
    """Return the Square OAuth authorization URL."""
    if not config.SQUARE_APP_ID:
        raise HTTPException(status_code=400, detail="SQUARE_APP_ID not configured")

    state = secrets.token_urlsafe(32)
    # In production, store state in DB/cache and validate on callback.
    # For MVP, we encode the user_id in the state.
    state_payload = f"{user.id}:{state}"

    from urllib.parse import quote
    url = (
        f"{config.SQUARE_BASE_URL}/oauth2/authorize"
        f"?client_id={config.SQUARE_APP_ID}"
        f"&scope=ITEMS_READ+INVENTORY_READ+ORDERS_READ+MERCHANT_PROFILE_READ"
        f"&redirect_uri={quote(config.SQUARE_OAUTH_REDIRECT_URL, safe='')}"
        f"&session=false"
        f"&state={state_payload}"
    )
    return {"url": url}


@router.get("/square/callback")
async def square_callback(
    state: str = Query(""),
    code: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    error_description: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Handle the Square OAuth callback — exchange code for tokens."""
    from urllib.parse import quote as urlquote

    # Handle Square sending back an error (e.g. user denied, invalid app)
    if error:
        detail = urlquote((error_description or error)[:300])
        return RedirectResponse(f"{config.FRONTEND_URL}/settings?square=error&detail={detail}")

    if not code:
        return RedirectResponse(f"{config.FRONTEND_URL}/settings?square=error&detail=No+authorization+code+received")

    # Extract user_id from state
    try:
        user_id_str = state.split(":")[0]
        user_id = int(user_id_str)
    except (ValueError, IndexError):
        return RedirectResponse(f"{config.FRONTEND_URL}/settings?square=error&detail=Invalid+state+parameter")

    user = db.query(User).get(user_id)
    if not user:
        return RedirectResponse(f"{config.FRONTEND_URL}/settings?square=error&detail=User+not+found+-+please+sign+in+again")

    # Exchange authorization code for tokens
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            f"{config.SQUARE_BASE_URL}/oauth2/token",
            json={
                "client_id": config.SQUARE_APP_ID,
                "client_secret": config.SQUARE_APP_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": config.SQUARE_OAUTH_REDIRECT_URL,
            },
        )

    if response.status_code != 200:
        logger.error("Square OAuth token exchange failed: status=%s body=%s", response.status_code, response.text)
        from urllib.parse import quote
        error_msg = quote(response.text[:200])
        return RedirectResponse(f"{config.FRONTEND_URL}/settings?square=error&detail={error_msg}")

    data = response.json()
    access_token = data.get("access_token", "")
    refresh_token = data.get("refresh_token", "")
    merchant_id = data.get("merchant_id", "")
    expires_at = data.get("expires_at")

    # Upsert SquareConnection
    existing = db.query(SquareConnection).filter(SquareConnection.user_id == user.id).first()
    if existing:
        existing.access_token = access_token
        existing.refresh_token = refresh_token
        existing.merchant_id = merchant_id
        if expires_at:
            from datetime import datetime
            existing.token_expires_at = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    else:
        conn = SquareConnection(
            user_id=user.id,
            access_token=access_token,
            refresh_token=refresh_token,
            merchant_id=merchant_id,
        )
        if expires_at:
            from datetime import datetime
            conn.token_expires_at = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        db.add(conn)

    db.commit()
    logger.info("Square connected for user %d (merchant: %s)", user.id, merchant_id)

    return RedirectResponse(f"{config.FRONTEND_URL}/settings?square=connected")


@router.post("/square/disconnect")
async def square_disconnect(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Disconnect Square — revoke token and delete connection."""
    conn = db.query(SquareConnection).filter(SquareConnection.user_id == user.id).first()
    if not conn:
        raise HTTPException(status_code=400, detail="No Square connection found")

    # Revoke token with Square
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                f"{config.SQUARE_BASE_URL}/oauth2/revoke",
                json={
                    "client_id": config.SQUARE_APP_ID,
                    "access_token": conn.access_token,
                },
                headers={"Authorization": f"Client {config.SQUARE_APP_SECRET}"},
            )
    except Exception:
        logger.warning("Failed to revoke Square token for user %d", user.id)

    db.delete(conn)
    db.commit()
    return {"status": "ok", "message": "Square disconnected"}


@router.get("/square/locations")
async def square_locations(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """List Square locations for the connected account."""
    conn = db.query(SquareConnection).filter(SquareConnection.user_id == user.id).first()
    if not conn:
        raise HTTPException(status_code=400, detail="No Square connection. Connect Square first.")

    from services.square_service import SquareService
    svc = SquareService(access_token=conn.access_token, location_id=conn.location_id or "")
    locations = await svc.list_locations()
    return {"locations": locations}


@router.post("/square/set-location")
def set_location(
    location_id: str = Query(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Set the Square location to sync from."""
    conn = db.query(SquareConnection).filter(SquareConnection.user_id == user.id).first()
    if not conn:
        raise HTTPException(status_code=400, detail="No Square connection")

    conn.location_id = location_id
    db.commit()
    return {"status": "ok", "location_id": location_id}
