from datetime import datetime, timezone
from enum import Enum

from sqlmodel import Field, SQLModel


class NotificationChannel(str, Enum):
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"


class NotificationStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class Notification(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    recipient: str = Field(min_length=1, max_length=320)
    message: str = Field(min_length=1, max_length=10_000)
    channel: NotificationChannel
    status: NotificationStatus = Field(default=NotificationStatus.PENDING)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
