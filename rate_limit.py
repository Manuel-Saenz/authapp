from collections import defaultdict
from datetime import datetime, timedelta, timezone

# {email: [attempt_datetime, ...]}
_attempts: dict[str, list[datetime]] = defaultdict(list)

MAX_ATTEMPTS = 5
WINDOW_SECONDS = 900  # 15 minutes


def _purge(email: str) -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=WINDOW_SECONDS)
    _attempts[email] = [t for t in _attempts[email] if t > cutoff]


def is_rate_limited(email: str) -> bool:
    _purge(email)
    return len(_attempts[email]) >= MAX_ATTEMPTS


def record_attempt(email: str) -> None:
    _purge(email)
    _attempts[email].append(datetime.now(timezone.utc))


def clear_attempts(email: str) -> None:
    _attempts[email] = []
