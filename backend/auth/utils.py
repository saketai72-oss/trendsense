import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from core.config.backend_settings import (
    JWT_SECRET_KEY,
    JWT_ALGORITHM,
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
    JWT_REFRESH_TOKEN_EXPIRE_DAYS,
)

# ── Password Hashing ─────────────────────────────────────────────────────────
# Dùng bcrypt trực tiếp (tránh xung đột passlib vs bcrypt>=4.0.0 trên Python 3.12)
def hash_password(password: str) -> str:
    """Hash a plain-text password using bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against its bcrypt hash."""
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


# ── JWT Token Creation ───────────────────────────────────────────────────────
def create_access_token(user_id: str, email: str, extra_claims: dict = None) -> str:
    """
    Create a short-lived JWT access token.

    Args:
        user_id: UUID string of the user
        email:   User's email address
        extra_claims: Optional additional claims to include

    Returns:
        Encoded JWT string
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "email": email,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
        "jti": secrets.token_hex(16),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> tuple:
    """
    Create a long-lived JWT refresh token.

    Returns:
        Tuple of (token_string, token_hash, expires_at)
        Store the hash in DB, return the token to the client.
    """
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    jti = secrets.token_hex(32)

    payload = {
        "sub": user_id,
        "type": "refresh",
        "iat": now,
        "exp": expires_at,
        "jti": jti,
    }
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    return token, token_hash, expires_at


# ── JWT Token Verification ───────────────────────────────────────────────────
def decode_token(token: str) -> dict:
    """
    Decode and verify a JWT token.

    Args:
        token: JWT string to decode

    Returns:
        Decoded payload dict

    Raises:
        jwt.ExpiredSignatureError: Token has expired
        jwt.InvalidTokenError: Token is invalid
    """
    return jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])


def hash_token(token: str) -> str:
    """SHA256 hash of a token string (for storing refresh tokens in DB)."""
    return hashlib.sha256(token.encode()).hexdigest()
