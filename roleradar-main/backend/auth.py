"""Accounts: signup with email verification, login sessions, password reset.

Design notes
- Passwords: PBKDF2-HMAC-SHA256 with a per-user salt (standard library only).
- Verification, reset and session tokens are random, sent/stored raw only on the wire and
  kept in the database as SHA-256 hashes, so a database leak does not leak usable tokens.
- Sessions are an HttpOnly cookie (not readable by page scripts).
- Emails go out through Brevo's HTTPS API (Render's free tier blocks SMTP). With no
  API key configured locally, the email is written to the server log instead.
- All expiry/cooldown maths uses the database clock (NOW()) to avoid timezone drift.
"""
import asyncio
import hashlib
import hmac
import logging
import os
from email.utils import parseaddr
import secrets
from html import escape as html_escape
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field

from database import db_manager
from guards import rate_limit

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])

SESSION_COOKIE = "rr_session"
SESSION_SECONDS = 30 * 24 * 3600
VERIFY_SECONDS = 24 * 3600
RESET_SECONDS = 3600
RESEND_COOLDOWN_SECONDS = 60
PBKDF2_ITERATIONS = 240_000
COMMON_PASSWORDS = {"password", "password1", "12345678", "123456789", "qwertyui", "iloveyou", "11111111", "letmein1"}
GENERIC_SENT = "If that email can receive messages, a link is on its way. Check your inbox and spam folder."


# ---------------------------------------------------------------- passwords and tokens
def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iterations, salt_hex, hash_hex = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations))
        return hmac.compare_digest(digest.hex(), hash_hex)
    except (ValueError, TypeError):
        return False


_dummy_hash: Optional[str] = None


def _dummy_verify(password: str) -> None:
    """Spend the same time as a real check when the email is unknown (blunts timing probes)."""
    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = hash_password("not-a-real-password")
    verify_password(password, _dummy_hash)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def check_password_strength(password: str) -> Optional[str]:
    if len(password) < 8:
        return "Password must be at least 8 characters."
    if password.lower() in COMMON_PASSWORDS:
        return "That password is too common. Please choose another."
    return None


# ---------------------------------------------------------------- database helpers
def _get_user(email: str) -> Optional[dict]:
    return db_manager.execute_single(
        "SELECT id, email, full_name, password_hash, email_verified FROM users WHERE email = :email", {"email": email})


def _issue_token(user_id: int, purpose: str, ttl_seconds: int) -> str:
    raw = secrets.token_urlsafe(32)
    db_manager.execute_query(
        "INSERT INTO auth_tokens (user_id, token_hash, purpose, expires_at) "
        "VALUES (:u, :h, :p, DATE_ADD(NOW(), INTERVAL :s SECOND))",
        {"u": user_id, "h": hash_token(raw), "p": purpose, "s": ttl_seconds})
    return raw


def _find_token(raw: str, purpose: str) -> Optional[dict]:
    return db_manager.execute_single(
        "SELECT id, user_id FROM auth_tokens WHERE token_hash = :h AND purpose = :p "
        "AND used_at IS NULL AND expires_at > NOW()", {"h": hash_token(raw), "p": purpose})


def _mark_used(token_id: int) -> None:
    db_manager.execute_query("UPDATE auth_tokens SET used_at = NOW() WHERE id = :id", {"id": token_id})


def _drop_open_tokens(user_id: int, purpose: str) -> None:
    db_manager.execute_query(
        "DELETE FROM auth_tokens WHERE user_id = :u AND purpose = :p AND used_at IS NULL", {"u": user_id, "p": purpose})


def _cooldown_active(user_id: int, purpose: str) -> bool:
    row = db_manager.execute_single(
        "SELECT TIMESTAMPDIFF(SECOND, created_at, NOW()) AS age FROM auth_tokens "
        "WHERE user_id = :u AND purpose = :p ORDER BY id DESC LIMIT 1", {"u": user_id, "p": purpose})
    return bool(row) and row["age"] is not None and row["age"] < RESEND_COOLDOWN_SECONDS


def _purge_expired() -> None:
    db_manager.execute_query("DELETE FROM auth_tokens WHERE expires_at < DATE_SUB(NOW(), INTERVAL 1 DAY)")


# ---------------------------------------------------------------- email
def _base_url(request: Request) -> str:
    configured = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
    return configured or str(request.base_url).rstrip("/")


def _email_html(heading: str, intro: str, button: str, link: str, footer: str) -> str:
    return (
        '<div style="font-family:Arial,Helvetica,sans-serif;max-width:520px;margin:0 auto;color:#1e293b">'
        '<p style="font-size:22px;font-weight:700;margin:0 0 4px"><span style="color:#0f172a">Role</span>'
        '<span style="color:#22c55e">Radar</span></p>'
        f'<h2 style="margin:18px 0 8px;color:#0f172a">{heading}</h2><p style="line-height:1.5">{intro}</p>'
        f'<p style="margin:24px 0"><a href="{link}" style="background:#22c55e;color:#0f172a;text-decoration:none;'
        f'font-weight:700;padding:12px 22px;border-radius:999px;display:inline-block">{button}</a></p>'
        f'<p style="font-size:13px;color:#64748b;line-height:1.5">If the button does not work, copy this link into your browser:<br>{link}</p>'
        f'<p style="font-size:13px;color:#64748b">{footer}</p></div>')


async def send_email(to: str, subject: str, html: str, text: str) -> bool:
    api_key = os.environ.get("BREVO_API_KEY")
    name, address = parseaddr(os.environ.get("EMAIL_FROM", ""))
    if not api_key or not address:
        if os.environ.get("RENDER"):
            logger.error("Email not sent: BREVO_API_KEY / EMAIL_FROM are not configured")
            return False
        logger.warning("[DEV EMAIL, not sent: no BREVO_API_KEY] to=%s subject=%s\n%s", to, subject, text)
        return True
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post("https://api.brevo.com/v3/smtp/email", headers={"api-key": api_key},
                                     json={"sender": {"name": name or "RoleRadar", "email": address}, "to": [{"email": to}],
                                           "subject": subject, "htmlContent": html, "textContent": text})
        if resp.status_code >= 300:
            logger.error("Brevo rejected email (%s): %s", resp.status_code, resp.text[:300])
            return False
        return True
    except Exception as exc:
        logger.error("Email send failed: %s: %s", type(exc).__name__, exc)
        return False


def verification_email(name: str, link: str):
    """Returns (plain_text, html). The name is user-supplied, so it is escaped for the HTML part."""
    text = (f"Hi {name},\n\nConfirm your email to finish creating your RoleRadar account:\n{link}\n\n"
            "The link works for 24 hours. If you did not sign up, ignore this email.")
    body = _email_html("Confirm your email",
                       f"Hi {html_escape(name)}, welcome to RoleRadar. Confirm your email address to finish creating your account.",
                       "Verify my email", link, "This link works for 24 hours. If you did not sign up, you can ignore this email.")
    return text, body


def reset_email(link: str):
    text = (f"We received a request to reset your RoleRadar password:\n{link}\n\nThe link works for 1 hour. "
            "If you did not ask for this, ignore this email; your password stays the same.")
    body = _email_html("Reset your password", "We received a request to reset your RoleRadar password.", "Choose a new password", link,
                       "This link works for 1 hour. If you did not ask for this, ignore this email; your password stays the same.")
    return text, body


async def _send_verification(request: Request, user: dict) -> bool:
    _drop_open_tokens(user["id"], "verify")
    token = _issue_token(user["id"], "verify", VERIFY_SECONDS)
    text, body = verification_email(user.get("full_name") or "there", f"{_base_url(request)}/verify.html?token={token}")
    return await send_email(user["email"], "Verify your RoleRadar email", body, text)


async def _send_reset(request: Request, user: dict) -> bool:
    _drop_open_tokens(user["id"], "reset")
    token = _issue_token(user["id"], "reset", RESET_SECONDS)
    text, body = reset_email(f"{_base_url(request)}/reset.html?token={token}")
    return await send_email(user["email"], "Reset your RoleRadar password", body, text)


# ---------------------------------------------------------------- sessions
def _is_https(request: Request) -> bool:
    return request.url.scheme == "https" or request.headers.get("x-forwarded-proto", "").lower() == "https"


def _start_session(request: Request, response: Response, user_id: int) -> None:
    raw = _issue_token(user_id, "session", SESSION_SECONDS)
    response.set_cookie(SESSION_COOKIE, raw, max_age=SESSION_SECONDS, httponly=True,
                        secure=_is_https(request), samesite="lax", path="/")


def require_user(request: Request) -> dict:
    """Dependency for endpoints that need a logged-in, verified user."""
    raw = request.cookies.get(SESSION_COOKIE)
    if not raw:
        raise HTTPException(status_code=401, detail="Please log in to use this feature.")
    row = db_manager.execute_single(
        "SELECT u.id, u.email, u.full_name, u.email_verified FROM auth_tokens t JOIN users u ON u.id = t.user_id "
        "WHERE t.token_hash = :h AND t.purpose = 'session' AND t.expires_at > NOW()", {"h": hash_token(raw)})
    if not row or not row["email_verified"]:
        raise HTTPException(status_code=401, detail="Your session has expired. Please log in again.")
    return row


# ---------------------------------------------------------------- request models
class SignupIn(BaseModel):
    full_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class EmailIn(BaseModel):
    email: EmailStr


class TokenIn(BaseModel):
    token: str = Field(min_length=1, max_length=200)


class ResetIn(BaseModel):
    token: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=1, max_length=128)


class ChangePasswordIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=1, max_length=128)


# ---------------------------------------------------------------- routes
@router.post("/signup", status_code=202, dependencies=[Depends(rate_limit("auth-signup", 5, 40))])
async def signup(body: SignupIn, request: Request):
    email = body.email.lower().strip()
    problem = check_password_strength(body.password)
    if problem:
        raise HTTPException(status_code=422, detail=problem)
    name = body.full_name.strip()
    password_hash = await asyncio.to_thread(hash_password, body.password)
    _purge_expired()

    existing = _get_user(email)
    if existing and existing["email_verified"]:
        raise HTTPException(status_code=409, detail="An account with this email already exists. Please log in.")
    if existing:
        # Unverified: the latest signup wins so nobody is stuck with a stale password.
        db_manager.execute_query("UPDATE users SET full_name = :n, password_hash = :p WHERE id = :id AND email_verified = 0",
                                 {"n": name, "p": password_hash, "id": existing["id"]})
        user = _get_user(email)
    else:
        db_manager.execute_query("INSERT INTO users (email, full_name, password_hash, email_verified) VALUES (:e, :n, :p, 0)",
                                 {"e": email, "n": name, "p": password_hash})
        user = _get_user(email)

    if not await _send_verification(request, user):
        raise HTTPException(status_code=503, detail="We could not send the verification email. Please try again in a minute.")
    return {"message": "Account created. Check your email for a verification link.", "email": email}


@router.post("/verify", dependencies=[Depends(rate_limit("auth-verify", 10, 60))])
async def verify_email(body: TokenIn):
    token = _find_token(body.token, "verify")
    if not token:
        raise HTTPException(status_code=400, detail="This verification link is invalid or has expired.")
    db_manager.execute_query("UPDATE users SET email_verified = 1 WHERE id = :id", {"id": token["user_id"]})
    _mark_used(token["id"])
    return {"message": "Email verified. You can now log in."}


@router.post("/resend", status_code=202, dependencies=[Depends(rate_limit("auth-resend", 3, 20))])
async def resend_verification(body: EmailIn, request: Request):
    user = _get_user(body.email.lower().strip())
    if user and not user["email_verified"] and not _cooldown_active(user["id"], "verify"):
        await _send_verification(request, user)
    return {"message": GENERIC_SENT}


@router.post("/login", dependencies=[Depends(rate_limit("auth-login", 10, 80))])
async def login(body: LoginIn, request: Request, response: Response):
    user = _get_user(body.email.lower().strip())
    if not user:
        await asyncio.to_thread(_dummy_verify, body.password)
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    if not await asyncio.to_thread(verify_password, body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    if not user["email_verified"]:
        raise HTTPException(status_code=403, detail={"code": "email_not_verified",
                                                    "message": "Please verify your email before logging in. Check your inbox for the link."})
    _start_session(request, response, user["id"])
    return {"email": user["email"], "full_name": user["full_name"]}


@router.post("/logout")
async def logout(request: Request, response: Response):
    raw = request.cookies.get(SESSION_COOKIE)
    if raw:
        db_manager.execute_query("DELETE FROM auth_tokens WHERE token_hash = :h AND purpose = 'session'", {"h": hash_token(raw)})
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"message": "Logged out."}


@router.post("/delete-account", dependencies=[Depends(rate_limit("auth-delete", 3, 20))])
async def delete_account(response: Response, user: dict = Depends(require_user)):
    """Permanently removes the signed-in account (its tokens go with it through the cascade)."""
    db_manager.execute_query("DELETE FROM users WHERE id = :id", {"id": user["id"]})
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"message": "Your account has been deleted."}


@router.post("/change-password", dependencies=[Depends(rate_limit("auth-change-password", 5, 30))])
async def change_password(body: ChangePasswordIn, request: Request, user: dict = Depends(require_user)):
    """Password change for a signed-in user (as opposed to /reset, which uses an emailed token
    for someone who is locked out). Keeps the current session signed in and revokes the rest."""
    full_user = _get_user(user["email"])
    if not full_user or not await asyncio.to_thread(verify_password, body.current_password, full_user["password_hash"]):
        raise HTTPException(status_code=401, detail="Your current password is incorrect.")
    problem = check_password_strength(body.new_password)
    if problem:
        raise HTTPException(status_code=422, detail=problem)
    password_hash = await asyncio.to_thread(hash_password, body.new_password)
    db_manager.execute_query("UPDATE users SET password_hash = :p WHERE id = :id", {"p": password_hash, "id": user["id"]})
    raw = request.cookies.get(SESSION_COOKIE)
    db_manager.execute_query(
        "DELETE FROM auth_tokens WHERE user_id = :u AND purpose = 'session' AND token_hash != :keep",
        {"u": user["id"], "keep": hash_token(raw) if raw else ""})
    return {"message": "Password updated."}


@router.get("/me")
async def me(user: dict = Depends(require_user)):
    return {"email": user["email"], "full_name": user["full_name"]}


@router.post("/forgot", status_code=202, dependencies=[Depends(rate_limit("auth-forgot", 3, 20))])
async def forgot_password(body: EmailIn, request: Request):
    user = _get_user(body.email.lower().strip())
    if user and not _cooldown_active(user["id"], "reset"):
        await _send_reset(request, user)
    return {"message": GENERIC_SENT}


@router.post("/reset", dependencies=[Depends(rate_limit("auth-reset", 10, 60))])
async def reset_password(body: ResetIn):
    problem = check_password_strength(body.password)
    if problem:
        raise HTTPException(status_code=422, detail=problem)
    token = _find_token(body.token, "reset")
    if not token:
        raise HTTPException(status_code=400, detail="This reset link is invalid or has expired.")
    password_hash = await asyncio.to_thread(hash_password, body.password)
    db_manager.execute_query("UPDATE users SET password_hash = :p, email_verified = 1 WHERE id = :id",
                             {"p": password_hash, "id": token["user_id"]})
    _mark_used(token["id"])
    # Everyone signed in with the old password is signed out.
    db_manager.execute_query("DELETE FROM auth_tokens WHERE user_id = :u AND purpose = 'session'", {"u": token["user_id"]})
    return {"message": "Password updated. You can now log in."}
