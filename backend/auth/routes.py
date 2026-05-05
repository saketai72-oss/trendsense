"""
Authentication Routes — Register, Login, OAuth, Token Refresh
=============================================================
Production-grade auth endpoints with JWT + OAuth support.
"""
import logging
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr, field_validator

from backend.auth.utils import (
    hash_password, verify_password,
    create_access_token, create_refresh_token, hash_token, decode_token,
)
from backend.auth.oauth import (
    get_google_auth_url, exchange_google_code,
    get_github_auth_url, exchange_github_code,
)
from backend.auth.dependencies import get_current_user
from core.config.backend_settings import FRONTEND_URL, JWT_REFRESH_TOKEN_EXPIRE_DAYS
from core.db.models import (
    get_user_by_email, get_user_by_provider,
    create_user, update_user_login, store_refresh_token,
    get_refresh_token, revoke_refresh_token, revoke_all_user_tokens,
    get_user_by_id,
)

import jwt as pyjwt

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ── Request/Response Schemas ─────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    display_name: Optional[str] = None

    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError("Mật khẩu phải có ít nhất 8 ký tự")
        if len(v) > 128:
            raise ValueError("Mật khẩu không được quá 128 ký tự")
        if not re.search(r"[A-Za-z]", v) or not re.search(r"\d", v):
            raise ValueError("Mật khẩu phải chứa ít nhất 1 chữ cái và 1 chữ số")
        return v

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, v):
        if v is not None:
            v = v.strip()
            if len(v) > 100:
                raise ValueError("Tên hiển thị không được quá 100 ký tự")
            if not v:
                return None
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    user: dict


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: str
    email: str
    display_name: Optional[str]
    avatar_url: Optional[str]
    auth_provider: str
    created_at: Optional[str]


# ── Helper ───────────────────────────────────────────────────────────────────

def _build_token_response(user: dict) -> dict:
    """Create access + refresh tokens, store refresh token hash, return response."""
    user_id = str(user["id"])
    email = user["email"]

    access_token = create_access_token(user_id, email)
    refresh_token, refresh_hash, expires_at = create_refresh_token(user_id)

    # Store refresh token hash in DB
    store_refresh_token(user_id, refresh_hash, expires_at)

    from core.config.backend_settings import JWT_ACCESS_TOKEN_EXPIRE_MINUTES

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user": _serialize_user(user),
    }


def _serialize_user(user: dict) -> dict:
    """Serialize user dict for API response (exclude sensitive fields)."""
    result = {}
    for key in ["id", "email", "display_name", "avatar_url", "auth_provider", "created_at"]:
        val = user.get(key)
        if hasattr(val, "isoformat"):
            val = val.isoformat()
        result[key] = str(val) if key == "id" else val
    return result


# ── POST /api/auth/register ─────────────────────────────────────────────────

@router.post("/register", status_code=201)
def register(body: RegisterRequest):
    """Register a new user with email and password."""
    # Check if email already exists
    existing = get_user_by_email(body.email.lower().strip())
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email đã được đăng ký. Vui lòng đăng nhập.",
        )

    # Create user
    user = create_user(
        email=body.email.lower().strip(),
        password_hash=hash_password(body.password),
        display_name=body.display_name,
        auth_provider="local",
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể tạo tài khoản. Vui lòng thử lại.",
        )

    logger.info(f"[Auth] New user registered: {user['email']}")
    return _build_token_response(user)


# ── POST /api/auth/login ────────────────────────────────────────────────────

@router.post("/login")
def login(body: LoginRequest):
    """Authenticate user with email and password."""
    user = get_user_by_email(body.email.lower().strip())

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email hoặc mật khẩu không đúng.",
        )

    # OAuth users cannot login with password
    if user.get("auth_provider") != "local" or not user.get("password_hash"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tài khoản này được tạo qua {user['auth_provider'].title()}. Vui lòng đăng nhập bằng {user['auth_provider'].title()}.",
        )

    if not verify_password(body.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email hoặc mật khẩu không đúng.",
        )

    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản đã bị vô hiệu hóa.",
        )

    # Update last login
    update_user_login(str(user["id"]))

    logger.info(f"[Auth] User logged in: {user['email']}")
    return _build_token_response(user)


# ── POST /api/auth/refresh ──────────────────────────────────────────────────

@router.post("/refresh")
def refresh_token(body: RefreshRequest):
    """Exchange a valid refresh token for a new access + refresh token pair."""
    try:
        payload = decode_token(body.refresh_token)
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token đã hết hạn. Vui lòng đăng nhập lại.",
        )
    except pyjwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token không hợp lệ.",
        )

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Loại token không hợp lệ. Cần refresh token.",
        )

    user_id = payload.get("sub")
    token_hash = hash_token(body.refresh_token)

    # Verify refresh token exists in DB and not revoked
    stored = get_refresh_token(token_hash)
    if not stored or stored.get("revoked"):
        # Possible token reuse attack — revoke all user tokens
        if user_id:
            revoke_all_user_tokens(user_id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token đã bị thu hồi. Vui lòng đăng nhập lại.",
        )

    user = get_user_by_id(user_id)
    if not user or not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tài khoản không tồn tại hoặc đã bị vô hiệu hóa.",
        )

    # Revoke old refresh token (rotation)
    revoke_refresh_token(token_hash)

    # Issue new token pair
    return _build_token_response(user)


# ── POST /api/auth/logout ───────────────────────────────────────────────────

@router.post("/logout")
def logout(
    body: Optional[RefreshRequest] = None,
    user: dict = Depends(get_current_user),
):
    """Revoke the current user's refresh token (single device logout)."""
    if body and body.refresh_token:
        token_hash = hash_token(body.refresh_token)
        revoke_refresh_token(token_hash)

    return {"message": "Đã đăng xuất thành công."}


# ── POST /api/auth/logout-all ───────────────────────────────────────────────

@router.post("/logout-all")
def logout_all(user: dict = Depends(get_current_user)):
    """Revoke all refresh tokens for the current user (logout from all devices)."""
    revoke_all_user_tokens(str(user["id"]))
    return {"message": "Đã đăng xuất khỏi tất cả thiết bị."}


# ── GET /api/auth/me ────────────────────────────────────────────────────────

@router.get("/me")
def get_me(user: dict = Depends(get_current_user)):
    """Get the current authenticated user's profile."""
    return _serialize_user(user)


# ── OAuth: Google ────────────────────────────────────────────────────────────

@router.get("/google")
def google_auth():
    """Redirect user to Google OAuth consent screen."""
    try:
        url = get_google_auth_url()
        return RedirectResponse(url=url)
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/google/callback")
def google_callback(code: str = Query(...), state: Optional[str] = None):
    """Handle Google OAuth callback — exchange code for user info, issue JWT."""
    try:
        google_user = exchange_google_code(code)
    except Exception as e:
        logger.error(f"[OAuth] Google exchange failed: {e}")
        return RedirectResponse(
            url=f"{FRONTEND_URL}/login?error=google_exchange_failed"
        )

    if not google_user.get("email"):
        return RedirectResponse(
            url=f"{FRONTEND_URL}/login?error=google_no_email"
        )

    return _oauth_login_or_create(
        email=google_user["email"],
        name=google_user.get("name"),
        picture=google_user.get("picture"),
        provider="google",
        provider_id=google_user["provider_id"],
    )


# ── OAuth: GitHub ────────────────────────────────────────────────────────────

@router.get("/github")
def github_auth():
    """Redirect user to GitHub OAuth consent screen."""
    try:
        url = get_github_auth_url()
        return RedirectResponse(url=url)
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/github/callback")
def github_callback(code: str = Query(...), state: Optional[str] = None):
    """Handle GitHub OAuth callback — exchange code for user info, issue JWT."""
    try:
        github_user = exchange_github_code(code)
    except Exception as e:
        logger.error(f"[OAuth] GitHub exchange failed: {e}")
        return RedirectResponse(
            url=f"{FRONTEND_URL}/login?error=github_exchange_failed"
        )

    if not github_user.get("email"):
        return RedirectResponse(
            url=f"{FRONTEND_URL}/login?error=github_no_email"
        )

    return _oauth_login_or_create(
        email=github_user["email"],
        name=github_user.get("name"),
        picture=github_user.get("picture"),
        provider="github",
        provider_id=github_user["provider_id"],
    )


# ── Internal: OAuth login-or-create flow ─────────────────────────────────────

def _oauth_login_or_create(
    email: str, name: str, picture: str,
    provider: str, provider_id: str,
) -> RedirectResponse:
    """
    1. Check if user exists by provider+provider_id → login
    2. Check if user exists by email → link provider
    3. Create new user
    Then redirect to frontend with tokens in URL params.
    """
    email = email.lower().strip()

    # Try to find by provider
    user = get_user_by_provider(provider, provider_id)

    if not user:
        # Try to find by email (link existing account)
        user = get_user_by_email(email)
        if user:
            # Link OAuth provider to existing local account
            from core.db.models import link_oauth_provider
            link_oauth_provider(str(user["id"]), provider, provider_id, picture)
            user = get_user_by_id(str(user["id"]))

    if not user:
        # Create new OAuth user
        user = create_user(
            email=email,
            password_hash=None,
            display_name=name,
            avatar_url=picture,
            auth_provider=provider,
            provider_id=provider_id,
        )

    if not user:
        return RedirectResponse(
            url=f"{FRONTEND_URL}/login?error=oauth_create_failed"
        )

    update_user_login(str(user["id"]))

    # Generate tokens
    token_data = _build_token_response(user)

    # Redirect to frontend with tokens as URL params (frontend will store them)
    from urllib.parse import urlencode
    params = urlencode({
        "access_token": token_data["access_token"],
        "refresh_token": token_data["refresh_token"],
        "expires_in": token_data["expires_in"],
    })
    return RedirectResponse(url=f"{FRONTEND_URL}/auth/callback?{params}")
