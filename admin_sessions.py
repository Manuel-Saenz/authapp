import uuid
from datetime import datetime, timedelta, timezone

_sessions: dict[str, datetime] = {}

SESSION_TTL_HOURS = 1


def _purge_expired() -> None:
    now = datetime.now(timezone.utc)
    expired = [t for t, exp in _sessions.items() if exp <= now]
    for t in expired:
        del _sessions[t]


def create_session() -> str:
    _purge_expired()
    token = str(uuid.uuid4())
    _sessions[token] = datetime.now(timezone.utc) + timedelta(hours=SESSION_TTL_HOURS)
    return token


def validate_session(token: str) -> bool:
    _purge_expired()
    return token in _sessions


def delete_session(token: str) -> None:
    _purge_expired()
    _sessions.pop(token, None)
