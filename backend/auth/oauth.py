"""
OAuth Flows — Google & GitHub
==============================
Handles OAuth authorization URL generation and code-to-user exchange.
"""
import logging
import secrets
from urllib.parse import urlencode

import requests

from core.config.backend_settings import (
    FRONTEND_URL,
    GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI,
    GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET, GITHUB_REDIRECT_URI,
)

logger = logging.getLogger(__name__)


# ── Google OAuth ─────────────────────────────────────────────────────────────

def get_google_auth_url(state: str = None) -> str:
    """
    Generate Google OAuth authorization URL.
    User will be redirected to Google to grant permission.
    """
    if not GOOGLE_CLIENT_ID:
        raise ValueError("Google OAuth not configured: GOOGLE_CLIENT_ID missing")

    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent",
    }
    if state:
        params["state"] = state

    return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"


def exchange_google_code(code: str) -> dict:
    """
    Exchange Google authorization code for user info.

    Returns:
        Dict with keys: email, name, picture, provider_id
    """
    # Step 1: Exchange code for tokens
    token_resp = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code",
        },
        timeout=15,
    )
    token_resp.raise_for_status()
    tokens = token_resp.json()

    # Step 2: Get user info using access token
    userinfo_resp = requests.get(
        "https://www.googleapis.com/oauth2/v2/userinfo",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
        timeout=15,
    )
    userinfo_resp.raise_for_status()
    user_info = userinfo_resp.json()

    return {
        "email": user_info.get("email", ""),
        "name": user_info.get("name", ""),
        "picture": user_info.get("picture", ""),
        "provider_id": str(user_info.get("id", "")),
    }


# ── GitHub OAuth ─────────────────────────────────────────────────────────────

def get_github_auth_url(state: str = None) -> str:
    """
    Generate GitHub OAuth authorization URL.
    """
    if not GITHUB_CLIENT_ID:
        raise ValueError("GitHub OAuth not configured: GITHUB_CLIENT_ID missing")

    params = {
        "client_id": GITHUB_CLIENT_ID,
        "redirect_uri": GITHUB_REDIRECT_URI,
        "scope": "read:user user:email",
    }
    if state:
        params["state"] = state

    return f"https://github.com/login/oauth/authorize?{urlencode(params)}"


def exchange_github_code(code: str) -> dict:
    """
    Exchange GitHub authorization code for user info.

    Returns:
        Dict with keys: email, name, picture, provider_id
    """
    # Step 1: Exchange code for access token
    token_resp = requests.post(
        "https://github.com/login/oauth/access_token",
        json={
            "client_id": GITHUB_CLIENT_ID,
            "client_secret": GITHUB_CLIENT_SECRET,
            "code": code,
        },
        headers={"Accept": "application/json"},
        timeout=15,
    )
    token_resp.raise_for_status()
    tokens = token_resp.json()

    access_token = tokens.get("access_token")
    if not access_token:
        raise ValueError(f"GitHub token exchange failed: {tokens}")

    # Step 2: Get user profile
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.github+json",
    }

    user_resp = requests.get(
        "https://api.github.com/user",
        headers=headers,
        timeout=15,
    )
    user_resp.raise_for_status()
    user_info = user_resp.json()

    # Step 3: Get email (may be private)
    email = user_info.get("email")
    if not email:
        email_resp = requests.get(
            "https://api.github.com/user/emails",
            headers=headers,
            timeout=15,
        )
        if email_resp.ok:
            emails = email_resp.json()
            primary = next((e for e in emails if e.get("primary") and e.get("verified")), None)
            if primary:
                email = primary["email"]
            elif emails:
                email = emails[0].get("email", "")

    return {
        "email": email or "",
        "name": user_info.get("name") or user_info.get("login", ""),
        "picture": user_info.get("avatar_url", ""),
        "provider_id": str(user_info.get("id", "")),
    }
