import os
import secrets
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

_pending: dict[str, dict] = {}
TOKEN_TTL_MINUTES = 30


def _purge_expired() -> None:
    now = datetime.now(timezone.utc)
    expired = [k for k, v in _pending.items() if v["expires_at"] <= now]
    for k in expired:
        del _pending[k]


def create_pending(email: str, password_hash: str, totp_secret: str) -> str:
    _purge_expired()
    token = secrets.token_urlsafe(32)
    _pending[token] = {
        "email": email,
        "password_hash": password_hash,
        "totp_secret": totp_secret,
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=TOKEN_TTL_MINUTES),
    }
    return token


def consume_pending(token: str) -> dict | None:
    _purge_expired()
    entry = _pending.pop(token, None)
    if entry is None or entry["expires_at"] <= datetime.now(timezone.utc):
        return None
    return entry


def smtp_configured() -> bool:
    return bool(os.environ.get("SMTP_HOST") and os.environ.get("SMTP_USER"))


def send_verification_email(to_email: str, verify_url: str) -> None:
    """Send a verification email. Raises on SMTP failure. Logs URL if SMTP not configured."""
    smtp_host = os.environ.get("SMTP_HOST", "")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_pass = os.environ.get("SMTP_PASSWORD", "")
    smtp_from = os.environ.get("SMTP_FROM", smtp_user)

    if not smtp_host or not smtp_user:
        print(f"[email_verify] SMTP not configured. Verification URL: {verify_url}")
        return

    msg = EmailMessage()
    msg["Subject"] = "Verify your email — AuthService"
    msg["From"] = smtp_from
    msg["To"] = to_email
    msg.set_content(
        f"Click the link below to verify your email address and complete registration:\n\n"
        f"{verify_url}\n\n"
        f"This link expires in {TOKEN_TTL_MINUTES} minutes.\n"
        f"If you did not request this, you can safely ignore this email."
    )

    with smtplib.SMTP(smtp_host, smtp_port) as s:
        s.ehlo()
        s.starttls()
        s.login(smtp_user, smtp_pass)
        s.send_message(msg)
