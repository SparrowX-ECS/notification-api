from datetime import datetime

from sqlmodel import Field, SQLModel

from src.models import NotificationChannel, NotificationStatus


class NotificationCreate(SQLModel):
    recipient: str = Field(min_length=1, max_length=320)
    message: str = Field(min_length=1, max_length=10_000)
    channel: NotificationChannel


class NotificationStatusUpdate(SQLModel):
    status: NotificationStatus


class NotificationRead(SQLModel):
    id: int
    recipient: str
    message: str
    channel: NotificationChannel
    status: NotificationStatus
    created_at: datetime
