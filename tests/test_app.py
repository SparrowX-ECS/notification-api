import asyncio

import httpx
import pytest
from sqlmodel import SQLModel, create_engine
from sqlalchemy.pool import StaticPool

import app as notification_app


@pytest.fixture()
def client(monkeypatch):
    test_engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    monkeypatch.setattr(notification_app, "engine", test_engine)
    SQLModel.metadata.create_all(test_engine)
    notification_app.create_db_and_tables()
    yield AsyncClientWrapper(notification_app.app)


class AsyncClientWrapper:
    def __init__(self, application):
        self.application = application

    def request(self, method, path, **kwargs):
        async def make_request():
            transport = httpx.ASGITransport(app=self.application)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                return await client.request(method, path, **kwargs)

        return asyncio.run(make_request())

    def get(self, path, **kwargs):
        return self.request("GET", path, **kwargs)

    def post(self, path, **kwargs):
        return self.request("POST", path, **kwargs)


def test_health_and_observability_endpoints(client):
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/docs").status_code == 200
    openapi = client.get("/openapi.json")
    assert openapi.status_code == 200
    assert "/notifications/{notification_id}/status" in openapi.json()["paths"]
    assert client.get("/metrics").status_code == 200


def test_notification_lifecycle_and_filters(client):
    created = client.post(
        "/notifications",
        json={"recipient": "person@example.com", "message": "Welcome", "channel": "email"},
    )
    assert created.status_code == 201
    notification = created.json()
    assert notification["status"] == "pending"
    notification_id = notification["id"]

    assert client.get(f"/notifications/{notification_id}").json()["id"] == notification_id
    assert len(client.get("/notifications?channel=email&status=pending").json()) == 1

    updated = client.post(
        f"/notifications/{notification_id}/status", json={"status": "sent"}
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "sent"
    assert client.get("/notifications?status=pending").json() == []


def test_validation_and_not_found_errors(client):
    invalid = client.post(
        "/notifications", json={"recipient": "", "message": "Hi", "channel": "fax"}
    )
    assert invalid.status_code == 422
    assert client.get("/notifications/999").status_code == 404
    assert client.post("/notifications/999/status", json={"status": "sent"}).status_code == 404
