import os
import secrets
import smtplib
import urllib.request
import urllib.error
import json
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


def _resend_api_key() -> str:
    return os.environ.get("RESEND_API_KEY", "")


def send_verification_email(to_email: str, verify_url: str) -> None:
    """Send a verification email.
    Uses Resend HTTP API if RESEND_API_KEY is set (recommended for Railway).
    Falls back to SMTP otherwise. Logs URL if neither is configured (local dev).
    """
    body_text = (
        f"Click the link below to verify your email address and complete registration:\n\n"
        f"{verify_url}\n\n"
        f"This link expires in {TOKEN_TTL_MINUTES} minutes.\n"
        f"If you did not request this, you can safely ignore this email."
    )

    api_key = _resend_api_key()
    if api_key:
        _send_via_resend(api_key, to_email, body_text)
        return

    smtp_host = os.environ.get("SMTP_HOST", "")
    smtp_user = os.environ.get("SMTP_USER", "")
    if not smtp_host or not smtp_user:
        print(f"[email_verify] No email provider configured. Verification URL: {verify_url}")
        return

    _send_via_smtp(smtp_host, smtp_user, to_email, body_text)


def _send_via_resend(api_key: str, to_email: str, body_text: str) -> None:
    from_addr = os.environ.get("SMTP_FROM", "noreply@manuelsaenz.info")
    payload = json.dumps({
        "from": from_addr,
        "to": [to_email],
        "subject": "Verify your email — AuthService",
        "text": body_text,
    }).encode()
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        if resp.status not in (200, 201):
            raise RuntimeError(f"Resend API returned {resp.status}")


def _send_via_smtp(smtp_host: str, smtp_user: str, to_email: str, body_text: str) -> None:
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_pass = os.environ.get("SMTP_PASSWORD", "")
    smtp_from = os.environ.get("SMTP_FROM", smtp_user)

    msg = EmailMessage()
    msg["Subject"] = "Verify your email — AuthService"
    msg["From"] = smtp_from
    msg["To"] = to_email
    msg.set_content(body_text)

    # Port 465 = implicit SSL; anything else = STARTTLS
    if smtp_port == 465:
        with smtplib.SMTP_SSL(smtp_host, smtp_port) as s:
            s.ehlo()
            s.login(smtp_user, smtp_pass)
            s.send_message(msg)
    else:
        with smtplib.SMTP(smtp_host, smtp_port) as s:
            s.ehlo()
            s.starttls()
            s.login(smtp_user, smtp_pass)
            s.send_message(msg)
