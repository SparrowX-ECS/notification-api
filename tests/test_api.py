import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_health_and_observability_endpoints(client: AsyncClient) -> None:
    assert (await client.get("/health")).json() == {"status": "ok"}
    assert (await client.get("/docs")).status_code == 200
    openapi = await client.get("/openapi.json")
    assert openapi.status_code == 200
    assert "/api/notification/{notification_id}/status" in openapi.json()["paths"]
    assert (await client.get("/metrics")).status_code == 200


@pytest.mark.anyio
async def test_notification_lifecycle_and_filters(client: AsyncClient) -> None:
    created = await client.post(
        "/api/notification/",
        json={"recipient": "person@example.com", "message": "Welcome", "channel": "email"},
    )
    assert created.status_code == 201
    notification = created.json()
    assert notification["status"] == "pending"
    notification_id = notification["id"]

    assert (await client.get(f"/api/notification/{notification_id}")).json()["id"] == notification_id
    assert len((await client.get("/api/notification/?channel=email&status=pending")).json()) == 1

    updated = await client.post(f"/api/notification/{notification_id}/status", json={"status": "sent"})
    assert updated.status_code == 200
    assert updated.json()["status"] == "sent"
    assert (await client.get("/api/notification/?status=pending")).json() == []


@pytest.mark.anyio
async def test_validation_and_not_found_errors(client: AsyncClient) -> None:
    invalid = await client.post(
        "/api/notification/", json={"recipient": "", "message": "Hi", "channel": "fax"}
    )
    assert invalid.status_code == 422
    assert (await client.get("/api/notification/999999")).status_code == 404
    assert (await client.post("/api/notification/999999/status", json={"status": "sent"})).status_code == 404
