"""Auth routes: sign up, sign in, sign out, OAuth callbacks."""

import logging
import os

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from app.database import async_session
from app.auth.utils import create_access_token
from app.auth.dependencies import get_current_user
from app.services.user_service import (
    create_user, get_user_by_email, authenticate_user,
    get_user_by_provider, update_last_login,
)

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")

# OAuth config (optional — works without these)
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GITHUB_CLIENT_ID = os.environ.get("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.environ.get("GITHUB_CLIENT_SECRET", "")


@router.get("/signup")
async def signup_page(request: Request):
    user = await get_current_user(request)
    if user:
        return RedirectResponse("/app", status_code=303)
    return templates.TemplateResponse("auth/signup.html", {
        "request": request,
        "google_enabled": bool(GOOGLE_CLIENT_ID),
        "github_enabled": bool(GITHUB_CLIENT_ID),
    })


@router.post("/signup")
async def signup_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    name: str = Form(""),
):
    errors = []
    if len(password) < 8:
        errors.append("Password must be at least 8 characters.")
    if not email or "@" not in email:
        errors.append("Please enter a valid email address.")

    if errors:
        return templates.TemplateResponse("auth/signup.html", {
            "request": request, "errors": errors, "email": email, "name": name,
            "google_enabled": bool(GOOGLE_CLIENT_ID),
            "github_enabled": bool(GITHUB_CLIENT_ID),
        })

    async with async_session() as db:
        existing = await get_user_by_email(db, email)
        if existing:
            return templates.TemplateResponse("auth/signup.html", {
                "request": request,
                "errors": ["An account with this email already exists. Try signing in."],
                "email": email, "name": name,
                "google_enabled": bool(GOOGLE_CLIENT_ID),
                "github_enabled": bool(GITHUB_CLIENT_ID),
            })

        user = await create_user(db, email=email, password=password, name=name)

    token = create_access_token(user.id, user.email)
    request.session["auth_token"] = token
    return RedirectResponse("/app", status_code=303)


@router.get("/login")
async def login_page(request: Request):
    user = await get_current_user(request)
    if user:
        return RedirectResponse("/app", status_code=303)
    return templates.TemplateResponse("auth/login.html", {
        "request": request,
        "google_enabled": bool(GOOGLE_CLIENT_ID),
        "github_enabled": bool(GITHUB_CLIENT_ID),
    })


@router.post("/login")
async def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
):
    async with async_session() as db:
        user = await authenticate_user(db, email, password)

    if not user:
        return templates.TemplateResponse("auth/login.html", {
            "request": request,
            "errors": ["Invalid email or password."],
            "email": email,
            "google_enabled": bool(GOOGLE_CLIENT_ID),
            "github_enabled": bool(GITHUB_CLIENT_ID),
        })

    token = create_access_token(user.id, user.email)
    request.session["auth_token"] = token
    return RedirectResponse("/app", status_code=303)


@router.get("/logout")
async def logout(request: Request):
    request.session.pop("auth_token", None)
    return RedirectResponse("/", status_code=303)


# ── OAuth: Google ─────────────────────────────────────────

@router.get("/auth/google")
async def google_login(request: Request):
    if not GOOGLE_CLIENT_ID:
        return RedirectResponse("/login", status_code=303)
    from authlib.integrations.starlette_client import OAuth
    oauth = OAuth()
    oauth.register(
        name="google",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )
    redirect_uri = str(request.url_for("google_callback"))
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/auth/google/callback")
async def google_callback(request: Request):
    if not GOOGLE_CLIENT_ID:
        return RedirectResponse("/login", status_code=303)
    from authlib.integrations.starlette_client import OAuth
    oauth = OAuth()
    oauth.register(
        name="google",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )
    token = await oauth.google.authorize_access_token(request)
    userinfo = token.get("userinfo", {})
    email = userinfo.get("email")
    name = userinfo.get("name", "")
    sub = userinfo.get("sub")

    if not email:
        return RedirectResponse("/login?error=no_email", status_code=303)

    async with async_session() as db:
        user = await get_user_by_provider(db, "google", sub)
        if not user:
            user = await get_user_by_email(db, email)
        if not user:
            user = await create_user(db, email=email, name=name, provider="google", provider_id=sub)
        else:
            await update_last_login(db, user)

    auth_token = create_access_token(user.id, user.email)
    request.session["auth_token"] = auth_token
    return RedirectResponse("/app", status_code=303)


# ── OAuth: GitHub ─────────────────────────────────────────

@router.get("/auth/github")
async def github_login(request: Request):
    if not GITHUB_CLIENT_ID:
        return RedirectResponse("/login", status_code=303)
    from authlib.integrations.starlette_client import OAuth
    oauth = OAuth()
    oauth.register(
        name="github",
        client_id=GITHUB_CLIENT_ID,
        client_secret=GITHUB_CLIENT_SECRET,
        authorize_url="https://github.com/login/oauth/authorize",
        access_token_url="https://github.com/login/oauth/access_token",
        api_base_url="https://api.github.com/",
        client_kwargs={"scope": "user:email"},
    )
    redirect_uri = str(request.url_for("github_callback"))
    return await oauth.github.authorize_redirect(request, redirect_uri)


@router.get("/auth/github/callback")
async def github_callback(request: Request):
    if not GITHUB_CLIENT_ID:
        return RedirectResponse("/login", status_code=303)
    from authlib.integrations.starlette_client import OAuth
    oauth = OAuth()
    oauth.register(
        name="github",
        client_id=GITHUB_CLIENT_ID,
        client_secret=GITHUB_CLIENT_SECRET,
        authorize_url="https://github.com/login/oauth/authorize",
        access_token_url="https://github.com/login/oauth/access_token",
        api_base_url="https://api.github.com/",
        client_kwargs={"scope": "user:email"},
    )
    token = await oauth.github.authorize_access_token(request)
    resp = await oauth.github.get("user", token=token)
    profile = resp.json()
    github_id = str(profile.get("id"))
    email = profile.get("email")
    name = profile.get("name") or profile.get("login", "")

    # If email not public, fetch from emails endpoint
    if not email:
        emails_resp = await oauth.github.get("user/emails", token=token)
        emails = emails_resp.json()
        primary = next((e for e in emails if e.get("primary")), None)
        email = primary["email"] if primary else None

    if not email:
        return RedirectResponse("/login?error=no_email", status_code=303)

    async with async_session() as db:
        user = await get_user_by_provider(db, "github", github_id)
        if not user:
            user = await get_user_by_email(db, email)
        if not user:
            user = await create_user(db, email=email, name=name, provider="github", provider_id=github_id)
        else:
            await update_last_login(db, user)

    auth_token = create_access_token(user.id, user.email)
    request.session["auth_token"] = auth_token
    return RedirectResponse("/app", status_code=303)
