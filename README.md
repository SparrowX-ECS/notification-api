# Notification API

The SparrowX Labs Notification API is a small FastAPI and SQLModel service owned by Emma Carter's Communications Team. It creates and tracks customer notifications in SQLite; it does not deliver messages.

## API contract

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/notifications` | Create a notification (`recipient`, `message`, `channel`) |
| `GET` | `/notifications` | List notifications; optionally filter by `channel` or `status` |
| `GET` | `/notifications/{id}` | Retrieve one notification |
| `POST` | `/notifications/{id}/status` | Set status (`pending`, `sent`, or `failed`) |

Channels are `email`, `sms`, and `push`. New notifications start as `pending`. The generated contract is available at `/docs` and `/openapi.json`.

## Local development

From this directory:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -q
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

The default database is `./notifications.db`. Set `DATABASE_URL` to use another SQLite URL, such as `sqlite:///./local.db`.

Operational endpoints:

- `GET /health` returns `{"status":"ok"}`.
- `GET /metrics` exposes Prometheus-compatible HTTP and notification metrics.

## Docker

```bash
docker build -t notification-api .
docker run --rm -p 8000:8000 -v notification-data:/data notification-api
```

The container runs as a non-root user and stores its SQLite database in `/data`.
