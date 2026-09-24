import os
import time
from typing import Any

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from sqlmodel import SQLModel, Session

from src.database import create_database_engine, database_url_from_environment
from src.models import Notification  # noqa: F401 - registers the table
from src.routes.notifications import refresh_status_metrics, router as notifications_router


http_requests_total = Counter(
    "notification_api_http_requests_total",
    "Total HTTP requests handled by the Notification API",
    ("method", "path", "status"),
)
http_request_duration_seconds = Histogram(
    "notification_api_http_request_duration_seconds",
    "HTTP request duration in seconds",
    ("method", "path"),
)


class MetricsMiddleware:
    def __init__(self, application: Any):
        self.application = application

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http" or scope.get("path") == "/metrics":
            await self.application(scope, receive, send)
            return
        started = time.perf_counter()
        response_status = 500

        async def record_response(message: dict[str, Any]) -> None:
            nonlocal response_status
            if message["type"] == "http.response.start":
                response_status = message["status"]
            await send(message)

        await self.application(scope, receive, record_response)
        path = scope.get("path", "unknown")
        if path.startswith("/api/notification/"):
            parts = path.strip("/").split("/")
            if len(parts) >= 3 and parts[2].isdigit():
                path = "/api/notification/{notification_id}"
                if len(parts) == 4 and parts[3] == "status":
                    path += "/status"
        http_requests_total.labels(scope["method"], path, str(response_status)).inc()
        http_request_duration_seconds.labels(scope["method"], path).observe(time.perf_counter() - started)


def create_app(database_url: str | None = None, enable_metrics: bool = True) -> FastAPI:
    application = FastAPI(
        title="SparrowX Notification API",
        version="1.0.0",
        description="Creates and tracks customer notifications for the Communications Team.",
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:8080,http://localhost:3000").split(","),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.state.engine = create_database_engine(database_url or database_url_from_environment())
    SQLModel.metadata.create_all(application.state.engine)
    with Session(application.state.engine) as session:
        refresh_status_metrics(session)

    if enable_metrics:
        application.add_middleware(MetricsMiddleware)

    @application.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/api/notification/health", tags=["health"])
    def api_health() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/metrics", include_in_schema=False)
    def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    application.include_router(notifications_router)
    return application


app = create_app()
