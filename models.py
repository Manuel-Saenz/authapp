from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Integer, String

from database import Base


class User(Base):
    __tablename__ = "users"

    id             = Column(Integer, primary_key=True, index=True)
    email          = Column(String, unique=True, index=True, nullable=False)
    password_hash  = Column(String, nullable=True, default=None)
    totp_secret    = Column(String, nullable=True, default=None)
    totp_confirmed = Column(Boolean, default=False, nullable=False)
    created_at     = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
