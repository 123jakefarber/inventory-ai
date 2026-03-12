"""Authentication service — password hashing, JWT creation/validation, FastAPI dependency."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, Header, HTTPException, status
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

import config
from database import User, get_db

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ---------------------------------------------------------------------------
# Password helpers
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------

def create_access_token(user_id: int) -> str:
    expire = datetime.utcnow() + timedelta(minutes=config.JWT_ACCESS_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "exp": expire, "type": "access"}
    return jwt.encode(payload, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)


def create_refresh_token(user_id: int) -> str:
    expire = datetime.utcnow() + timedelta(days=config.JWT_REFRESH_EXPIRE_DAYS)
    payload = {"sub": str(user_id), "exp": expire, "type": "refresh"}
    return jwt.encode(payload, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and validate a JWT. Raises HTTPException on failure."""
    try:
        payload = jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------

def get_current_user(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> User:
    """Extract the Bearer token, decode it, and return the User."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
        )

    token = authorization[7:]  # Strip "Bearer "
    payload = decode_token(token)

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user = db.query(User).get(int(user_id))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return user
