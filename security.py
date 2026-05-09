import io
from datetime import datetime, timezone

import pyotp
import qrcode
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Dummy hash used to normalise timing when a user is not found,
# preventing timing-based email enumeration.
_DUMMY_HASH = pwd_context.hash("dummy-password-for-timing-safety")

# Cache of recently used TOTP codes: {(email, code): expiry_datetime}
_used_codes: dict[tuple[str, str], datetime] = {}


# ── Password helpers ──────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def dummy_verify() -> None:
    """Run a bcrypt verify against a dummy hash to equalise timing."""
    pwd_context.verify("dummy", _DUMMY_HASH)


# ── TOTP helpers ──────────────────────────────────────────────────────────────

def generate_totp_secret() -> str:
    return pyotp.random_base32()


def build_totp_uri(secret: str, email: str, issuer: str = "AuthService") -> str:
    return pyotp.totp.TOTP(secret).provisioning_uri(email, issuer_name=issuer)


def generate_qr_png(totp_uri: str) -> bytes:
    img = qrcode.make(totp_uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def verify_totp(secret: str, code: str) -> bool:
    """Verify a 6-digit TOTP code. valid_window=1 allows ±30 s clock skew."""
    return pyotp.TOTP(secret).verify(code, valid_window=1)


# ── Replay-attack prevention ──────────────────────────────────────────────────

def _purge_expired() -> None:
    now = datetime.now(timezone.utc)
    expired = [k for k, exp in _used_codes.items() if exp <= now]
    for k in expired:
        del _used_codes[k]


def is_code_used(email: str, code: str) -> bool:
    _purge_expired()
    return (email, code) in _used_codes


def mark_code_used(email: str, code: str) -> None:
    """Mark a TOTP code as used. Expires after 90 s (covers the valid_window)."""
    from datetime import timedelta
    _purge_expired()
    _used_codes[(email, code)] = datetime.now(timezone.utc) + timedelta(seconds=90)
