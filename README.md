# Notification API

The SparrowX Labs Notification API is a small FastAPI and SQLModel service owned by Emma Carter's Communications Team. It creates and tracks customer notifications in PostgreSQL; it does not deliver messages.

## API contract

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/notification/` | Create a notification (`recipient`, `message`, `channel`) |
| `GET` | `/api/notification/` | List notifications; optionally filter by `channel` or `status` |
| `GET` | `/api/notification/{id}` | Retrieve one notification |
| `POST` | `/api/notification/{id}/status` | Set status (`pending`, `sent`, or `failed`) |

Channels are `email`, `sms`, and `push`. New notifications start as `pending`. The generated contract is available at `/docs` and `/openapi.json`.

## Local development

From this directory:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -q
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

The application reads `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USERNAME`, and `DB_PASSWORD` from the environment.

Operational endpoints:

- `GET /health` returns `{"status":"ok"}`.
- `GET /metrics` exposes Prometheus-compatible HTTP and notification metrics.

## Docker

```bash
docker build -t notification-api .
docker run --rm --network sparrowx-local -p 8000:8000 \
  -e DB_HOST=local-customer-postgres-db \
  -e DB_PORT=5432 \
  -e DB_NAME=notificationdb \
  -e DB_USERNAME=postgres \
  -e DB_PASSWORD=postgres \
  notification-api
```
