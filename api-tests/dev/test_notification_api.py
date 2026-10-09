import os
import uuid

import httpx


BASE_URL = os.environ.get("BASE_URL", "").rstrip("/")


def client() -> httpx.Client:
    if not BASE_URL:
        raise RuntimeError("BASE_URL must point to the deployed notification-api service")
    return httpx.Client(base_url=BASE_URL, timeout=15.0, follow_redirects=True)


def test_notification_lifecycle() -> None:
    recipient = f"deployment-{uuid.uuid4().hex}@example.com"
    payload = {
        "recipient": recipient,
        "message": "Deployment validation notification",
        "channel": "email",
    }

    with client() as api:
        created = api.post("/api/notifications/", json=payload)
        assert created.status_code == 201, created.text
        notification = created.json()
        notification_id = notification["id"]
        assert notification["recipient"] == recipient
        assert notification["channel"] == "email"
        assert notification["status"] == "pending"

        fetched = api.get(f"/api/notifications/{notification_id}")
        assert fetched.status_code == 200, fetched.text
        assert fetched.json()["id"] == notification_id

        pending = api.get(
            "/api/notifications/",
            params={"channel": "email", "status": "pending"},
        )
        assert pending.status_code == 200, pending.text
        assert any(item["id"] == notification_id for item in pending.json())

        sent = api.post(
            f"/api/notifications/{notification_id}/status",
            json={"status": "sent"},
        )
        assert sent.status_code == 200, sent.text
        assert sent.json()["status"] == "sent"

        sent_notifications = api.get(
            "/api/notifications/",
            params={"channel": "email", "status": "sent"},
        )
        assert sent_notifications.status_code == 200, sent_notifications.text
        assert any(item["id"] == notification_id for item in sent_notifications.json())


def test_notification_api_rejects_invalid_requests() -> None:
    with client() as api:
        invalid = api.post(
            "/api/notifications/",
            json={"recipient": "", "message": "Hi", "channel": "fax"},
        )
        assert invalid.status_code == 422, invalid.text

        unknown_notification = api.get("/api/notifications/999999")
        assert unknown_notification.status_code == 404, unknown_notification.text

        unknown_status = api.post(
            "/api/notifications/999999/status",
            json={"status": "sent"},
        )
        assert unknown_status.status_code == 404, unknown_status.text
