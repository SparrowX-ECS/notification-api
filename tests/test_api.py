import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_health_and_api_documentation(client: AsyncClient) -> None:
    assert (await client.get("/health")).json() == {"status": "ok"}

    metrics = await client.get("/metrics")
    assert metrics.status_code == 200
    assert "notification_api_http_requests_total" in metrics.text

    assert (await client.get("/docs")).status_code == 200

    openapi = await client.get("/openapi.json")
    assert openapi.status_code == 200
    assert "/api/notifications/{notification_id}/status" in openapi.json()["paths"]

    routed_openapi = await client.get("/api/notifications/openapi.json")
    assert routed_openapi.status_code == 200
    assert routed_openapi.json()["paths"] == openapi.json()["paths"]


@pytest.mark.anyio
async def test_notification_lifecycle_and_filters(client: AsyncClient) -> None:
    created = await client.post(
        "/api/notifications/",
        json={"recipient": "person@example.com", "message": "Welcome", "channel": "email"},
    )
    assert created.status_code == 201

    notification = created.json()
    assert notification["status"] == "pending"
    notification_id = notification["id"]

    assert (await client.get(f"/api/notifications/{notification_id}")).json()["id"] == notification_id

    assert len(
        (await client.get("/api/notifications/?channel=email&status=pending")).json()
    ) == 1

    updated = await client.post(
        f"/api/notifications/{notification_id}/status",
        json={"status": "sent"},
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "sent"

    assert (await client.get("/api/notifications/?status=pending")).json() == []


@pytest.mark.anyio
async def test_validation_and_not_found_errors(client: AsyncClient) -> None:
    invalid = await client.post(
        "/api/notifications/",
        json={"recipient": "", "message": "Hi", "channel": "fax"},
    )
    assert invalid.status_code == 422

    assert (await client.get("/api/notifications/999999")).status_code == 404

    assert (
        await client.post(
            "/api/notifications/999999/status",
            json={"status": "sent"},
        )
    ).status_code == 404
