from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from enum import Enum
from time import perf_counter
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from sqlmodel import Field, Session, SQLModel, create_engine, select


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
    recipient: str
    message: str
    channel: NotificationChannel
    status: NotificationStatus = Field(default=NotificationStatus.PENDING)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


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


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./notifications.db")
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)

HTTP_REQUESTS = Counter(
    "notification_api_http_requests_total",
    "Total HTTP requests handled by the Notification API",
    ("method", "path", "status"),
)
HTTP_DURATION = Histogram(
    "notification_api_http_request_duration_seconds",
    "HTTP request duration in seconds",
    ("method", "path"),
)
NOTIFICATIONS_CREATED = Counter(
    "notification_api_notifications_created_total",
    "Notifications created",
    ("channel",),
)
NOTIFICATIONS_BY_STATUS = Gauge(
    "notification_api_notifications_by_status",
    "Current number of notifications by status",
    ("status",),
)


def refresh_status_metrics(session: Session) -> None:
    counts = {value: 0 for value in NotificationStatus}
    for notification in session.exec(select(Notification)).all():
        counts[notification.status] += 1
    for notification_status, count in counts.items():
        NOTIFICATIONS_BY_STATUS.labels(status=notification_status.value).set(count)


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)


@asynccontextmanager
async def lifespan(_: FastAPI):
    create_db_and_tables()
    with Session(engine) as session:
        refresh_status_metrics(session)
    yield


app = FastAPI(
        title="SparrowX Notification API",
    version="1.0.0",
    description="Creates and tracks customer notifications for the Communications Team.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:8080,http://localhost:3000").split(","),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class MetricsMiddleware:
    """Small pure ASGI middleware, avoiding an extra request/response abstraction."""

    def __init__(self, application):
        self.application = application

    @staticmethod
    def metric_path(path: str) -> str:
        if path.startswith("/notifications/"):
            if path.endswith("/status"):
                return "/notifications/{id}/status"
            return "/notifications/{id}"
        return path

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["path"] == "/metrics":
            await self.application(scope, receive, send)
            return
        started = perf_counter()
        status_code = 500

        async def record_response(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        await self.application(scope, receive, record_response)
        path = self.metric_path(scope["path"])
        HTTP_REQUESTS.labels(scope["method"], path, str(status_code)).inc()
        HTTP_DURATION.labels(scope["method"], path).observe(perf_counter() - started)


app.add_middleware(MetricsMiddleware)


async def get_session():
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]


@app.get("/health", tags=["health"], summary="Check service health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post(
    "/notifications",
    response_model=NotificationRead,
    status_code=status.HTTP_201_CREATED,
    responses={201: {"description": "Notification created"}},
    tags=["notifications"],
    summary="Create a notification",
)
async def create_notification(payload: NotificationCreate, session: SessionDep) -> Notification:
    notification = Notification.model_validate(payload)
    session.add(notification)
    session.commit()
    session.refresh(notification)
    NOTIFICATIONS_CREATED.labels(channel=notification.channel.value).inc()
    refresh_status_metrics(session)
    return notification


@app.get(
    "/notifications",
    response_model=list[NotificationRead],
    tags=["notifications"],
    summary="List notifications",
)
async def list_notifications(
    session: SessionDep,
    channel: NotificationChannel | None = Query(default=None),
    notification_status: NotificationStatus | None = Query(default=None, alias="status"),
) -> list[Notification]:
    statement = select(Notification).order_by(Notification.created_at.desc())
    if channel is not None:
        statement = statement.where(Notification.channel == channel)
    if notification_status is not None:
        statement = statement.where(Notification.status == notification_status)
    return list(session.exec(statement).all())


@app.get(
    "/notifications/{notification_id}",
    response_model=NotificationRead,
    responses={404: {"description": "Notification not found"}},
    tags=["notifications"],
    summary="Retrieve a notification",
)
async def get_notification(notification_id: int, session: SessionDep) -> Notification:
    notification = session.get(Notification, notification_id)
    if notification is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    return notification


@app.post(
    "/notifications/{notification_id}/status",
    response_model=NotificationRead,
    responses={404: {"description": "Notification not found"}},
    tags=["notifications"],
    summary="Update notification status",
)
async def update_notification_status(
    notification_id: int, payload: NotificationStatusUpdate, session: SessionDep
) -> Notification:
    notification = session.get(Notification, notification_id)
    if notification is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    notification.status = payload.status
    session.add(notification)
    session.commit()
    session.refresh(notification)
    refresh_status_metrics(session)
    return notification
