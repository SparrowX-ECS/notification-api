# Notification API

Notification lifecycle service for the fictional SparrowX SaaS platform. This demonstration workload shows how a PostgreSQL-backed microservice is onboarded to AWS ECS/Fargate and deployed independently to `dev` and `prod`.

## Service responsibilities

- Create and list customer notifications.
- Retrieve notifications and update their delivery status.
- Persist data in the dedicated private RDS database `notificationdb`.
- Expose health and Prometheus-compatible metrics endpoints.

## API documentation

FastAPI documentation is available at `/docs` (Swagger UI), `/redoc` (ReDoc), and `/openapi.json` (OpenAPI schema). The main API prefix is `/api/notifications`:

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/notifications/` | Create a notification |
| `GET` | `/api/notifications/` | List/filter notifications |
| `GET` | `/api/notifications/{notification_id}` | Retrieve a notification |
| `POST` | `/api/notifications/{notification_id}/status` | Update notification status |
| `GET` | `/health` | Container/target-group health check |
| `GET` | `/api/notifications/health` | API smoke-test health check |
| `GET` | `/metrics` | Prometheus metrics |

Append these paths to the relevant environment base URL when testing a deployment.

## Runtime environment variables

| Variable | Required | Description |
| --- | --- | --- |
| `DB_HOST` | Yes | Private RDS PostgreSQL endpoint for `notificationdb`. |
| `DB_PORT` | No | PostgreSQL port; defaults to `5432`. |
| `DB_NAME` | Yes | Database name, normally `notificationdb`. |
| `DB_USERNAME` | Yes | Database username injected from the service secret. |
| `DB_PASSWORD` | Yes | Database password injected from the service secret. |
| `CORS_ALLOW_ORIGINS` | No | Comma-separated browser origins; defaults to local development origins. |

## Local development

```bash
python -m pip install -r requirements-dev.txt
pytest
uvicorn src.main:app --reload --port 8000
```

Open <http://localhost:8000/docs> after configuring the database variables.

## CI/CD cycle

Pull requests use the shared Python/database workflow to detect relevant changes, run tests, build an immutable Git-SHA image, scan it with Trivy, and publish image metadata. A merge to `main` resolves that image, deploys it to `dev`, runs the configured smoke test, and publishes its tag and digest as the production candidate.

The manually triggered production workflow requires `PROMOTE`, verifies the candidate digest, copies the exact image from the `dev` ECR namespace to `prod`, deploys it, smoke-tests it, and records the deployed metadata. Production is promoted, not rebuilt: this is **Build Once, Promote Many**.

## Environments and deployment tracking

`dev` is deployed automatically from `main`; `prod` is promoted manually after development validation. Each environment has its own ECS stack, ECR namespace, parameter file, URL, SSM metadata path, and GitHub deployment history. See [`ecs-parameters-dev.yaml`](ecs-parameters-dev.yaml) and [`ecs-parameters-prod.yaml`](ecs-parameters-prod.yaml).

## Rollback options

### Git revert

Revert the problematic source or configuration commit and merge the revert. The normal pipeline will test, build, scan, and deploy the corrective commit.

### Quicker manual image rollback

1. Open the repository **Deployments** tab.
2. Select the `prod` environment and open the desired previous deployment.
3. Copy its deployed image tag.
4. Open **Actions → Manual Rollback Production To Selected Image Tag → Run workflow**.
5. Enter `ROLLBACK`, paste the image tag, and run the workflow.

The workflow redeploys that immutable image to `prod`, runs the production smoke test, and publishes rollback metadata. ECS deployment circuit-breaker rollback is also enabled for unhealthy rolling deployments.

## Repository variables

| Variable | Description |
| --- | --- |
| `AWS_ACCOUNT_ID` | AWS account containing ECS, ECR, and environment resources. |
| `AWS_REGION` | AWS region used by the workflows. |
| `AWS_ROLE_NAME` | IAM role assumed through GitHub OIDC. |
| `DEV_BASE_URL` | Development smoke-test origin: protocol plus domain only, such as `https://sparrowx-dev.example.com`. |
| `DEV_DEPLOYED_PARAM_STORE_PATH` | SSM path for the image last deployed successfully to `dev`. |
| `PROD_BASE_URL` | Production smoke-test origin: protocol plus domain only. |
| `PROD_CANDIDATE_PARAM_STORE_PATH` | SSM path for the candidate published after development smoke tests. |
| `PROD_DEPLOYED_PARAM_STORE_PATH` | SSM path for the image last deployed successfully to `prod`. |

The smoke-test workflow appends the configured path to each base URL.

## Container and deployment configuration

- Container port: `8000`.
- ALB path: `/api/notifications/*`.
- Health check: `/health`.
- Smoke-test path: `/api/notifications/health`.
- Database: enabled in both environments.

## License

This is a proprietary portfolio project. It is publicly viewable but not open source. All rights are reserved. See [LICENSE.md](LICENSE.md).
