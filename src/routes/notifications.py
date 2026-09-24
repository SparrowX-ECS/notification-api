from collections.abc import Generator

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from prometheus_client import Counter, Gauge
from sqlmodel import Session, select

from src.models import Notification, NotificationChannel, NotificationStatus
from src.schemas import NotificationCreate, NotificationRead, NotificationStatusUpdate


router = APIRouter(prefix="/api/notification", tags=["notifications"])
notifications_created = Counter(
    "notification_api_notifications_created_total",
    "Notifications created",
    ("channel",),
)
notifications_by_status = Gauge(
    "notification_api_notifications_by_status",
    "Current number of notifications by status",
    ("status",),
)


def refresh_status_metrics(session: Session) -> None:
    counts = {notification_status: 0 for notification_status in NotificationStatus}
    for notification in session.exec(select(Notification)).all():
        counts[notification.status] += 1
    for notification_status, count in counts.items():
        notifications_by_status.labels(status=notification_status.value).set(count)


def get_session(request: Request) -> Generator[Session, None, None]:
    with Session(request.app.state.engine) as session:
        yield session


@router.post("/", response_model=NotificationRead, status_code=status.HTTP_201_CREATED)
def create_notification(payload: NotificationCreate, session: Session = Depends(get_session)) -> Notification:
    notification = Notification.model_validate(payload)
    session.add(notification)
    session.commit()
    session.refresh(notification)
    notifications_created.labels(channel=notification.channel.value).inc()
    refresh_status_metrics(session)
    return notification


@router.get("/", response_model=list[NotificationRead])
def list_notifications(
    session: Session = Depends(get_session),
    channel: NotificationChannel | None = Query(default=None),
    notification_status: NotificationStatus | None = Query(default=None, alias="status"),
) -> list[Notification]:
    statement = select(Notification).order_by(Notification.created_at.desc())
    if channel is not None:
        statement = statement.where(Notification.channel == channel)
    if notification_status is not None:
        statement = statement.where(Notification.status == notification_status)
    return list(session.exec(statement).all())


@router.get("/{notification_id}", response_model=NotificationRead)
def get_notification(notification_id: int, session: Session = Depends(get_session)) -> Notification:
    notification = session.get(Notification, notification_id)
    if notification is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    return notification


@router.post("/{notification_id}/status", response_model=NotificationRead)
def update_notification_status(
    notification_id: int,
    payload: NotificationStatusUpdate,
    session: Session = Depends(get_session),
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
