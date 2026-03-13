# Switchbox API

Backend service for the Switchbox feature flag platform. When flags change, a static JSON config is generated and uploaded to Cloudflare R2 so SDKs can fetch flags without hitting the API.

## Architecture

```
┌──────────────┐       ┌──────────────┐       ┌──────────────┐
│   Dashboard  │──────>│   FastAPI    │──────>│ Neon Postgres│
│              │ HTTP  │   (Fly.io)   │  SQL  │  (database)  │
└──────────────┘       └──────┬───────┘       └──────────────┘
                              │
                              │ on every mutation
                              v
                       ┌──────────────┐       ┌──────────────┐
                       │ CDN Publisher│──────>│ Cloudflare R2│
                       │  (boto3/S3)  │  PUT  │ (static JSON)│
                       └──────────────┘       └──────┬───────┘
                                                     │
                                                     │ public URL
                                                     v
                                              ┌──────────────┐
                                              │    SDKs      │
                                              │ (fetch JSON) │
                                              └──────────────┘
```

The API server handles writes only. All read traffic from SDKs goes directly to the CDN.

## Stack

| Component        | Provider         | Details                                       |
|------------------|------------------|-----------------------------------------------|
| API server       | Fly.io           | `switchbox-backend.fly.dev`, Amsterdam (ams)   |
| Database         | Neon Postgres    | Serverless, auto-scaling                       |
| Flag configs CDN | Cloudflare R2    | S3-compatible, public bucket                   |
| Migrations       | Alembic          | Runs on deploy via `release_command`           |

## Local Development

### Prerequisites

- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- [Docker](https://docs.docker.com/get-docker/) (optional, for local Postgres)

### Setup with Docker

```sh
docker compose up
docker compose exec api uv run alembic upgrade head
```

API runs on http://localhost:8000 with Postgres on port 5432.

### Setup without Docker

```sh
cp .env.example .env    # fill in DATABASE_URL and ADMIN_TOKEN
uv sync --dev
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

### Run Tests

```sh
uv run pytest
```

Tests use an in-memory SQLite database and mock the CDN publisher.

### Lint

```sh
uv run ruff check .
uv run ruff format --check .
```

## API Endpoints

All endpoints except `/health` require `Authorization: Bearer {ADMIN_TOKEN}`.

### Projects

| Method | Path                        | Description                      |
|--------|-----------------------------|----------------------------------|
| POST   | `/projects`                 | Create project (returns API key) |
| GET    | `/projects`                 | List all projects                |
| POST   | `/projects/{id}/rotate-key` | Rotate API key                   |

### Flags

| Method | Path                           | Description                           |
|--------|--------------------------------|---------------------------------------|
| POST   | `/projects/{project_id}/flags` | Create flag                           |
| GET    | `/projects/{project_id}/flags` | List flags (optional `?environment=`) |
| GET    | `/flags/{flag_id}`             | Get flag with rules                   |
| PATCH  | `/flags/{flag_id}`             | Update flag (name, rollout_pct, etc.) |
| POST   | `/flags/{flag_id}/toggle`      | Toggle enabled on/off                 |
| DELETE | `/flags/{flag_id}`             | Delete flag (cascades to rules)       |
| GET    | `/flags/{flag_id}/audit`       | Get audit log                         |

### Environments

| Method | Path                                        | Description                |
|--------|---------------------------------------------|----------------------------|
| GET    | `/projects/{project_id}/environments`       | List environments          |
| POST   | `/projects/{project_id}/environments`       | Create environment         |
| PATCH  | `/environments/{environment_id}`            | Rename environment         |
| DELETE | `/environments/{environment_id}`            | Delete environment         |
| POST   | `/environments/{environment_id}/rotate-sdk-key` | Rotate SDK key (24h grace) |

Each environment has a unique SDK key used for CDN paths and SDK authentication. On rotation, the old key remains active for 24 hours.

### Rules

| Method | Path                     | Description |
|--------|--------------------------|-------------|
| POST   | `/flags/{flag_id}/rules` | Add rule    |
| DELETE | `/rules/{rule_id}`       | Remove rule |

### Admin

| Method | Path                                        | Description                |
|--------|---------------------------------------------|----------------------------|
| POST   | `/admin/publish/{project_id}/{environment}` | Manually re-publish to CDN |
| GET    | `/health`                                   | Health check (no auth)     |

## CDN Publish Pipeline

Every flag or rule mutation triggers `publish_flags()`:

1. Queries all flags + rules for the project/environment
2. Builds a JSON config keyed by flag key (O(1) SDK lookups)
3. Uploads to R2 at `{sdk_key}/flags.json` (and `{previous_sdk_key}/flags.json` during grace period)
4. Sets `Cache-Control: public, max-age=30`

If R2 is not configured, it writes to `cdn_output/` locally. If the upload fails, the error is logged but the API request still succeeds — the database is the source of truth.

## Deployment

Push to `main` triggers deploy via GitHub Actions to Fly.io. Alembic migrations run automatically on deploy.

Manual deploy:

```sh
fly deploy
```

Set production secrets:

```sh
fly secrets set \
  ADMIN_TOKEN="..." \
  R2_ACCOUNT_ID="..." \
  R2_ACCESS_KEY_ID="..." \
  R2_SECRET_ACCESS_KEY="..." \
  R2_BUCKET_NAME="..."
```

## Environment Variables

| Variable              | Required | Description                                         |
|-----------------------|----------|-----------------------------------------------------|
| `DATABASE_URL`        | Yes      | Postgres connection string (`postgresql+asyncpg://`) |
| `ADMIN_TOKEN`         | Yes      | Bearer token for all admin endpoints                |
| `R2_ACCOUNT_ID`       | No       | Cloudflare account ID                               |
| `R2_ACCESS_KEY_ID`    | No       | R2 S3-compatible access key                         |
| `R2_SECRET_ACCESS_KEY`| No       | R2 S3-compatible secret key                         |
| `R2_BUCKET_NAME`      | No       | R2 bucket name (default: `switchbox-configs`)       |

When R2 vars are empty, the CDN publisher writes JSON files to `cdn_output/` locally.

## Database Migrations

Create a new migration:

```sh
uv run alembic revision --autogenerate -m "description of change"
```

Run migrations:

```sh
uv run alembic upgrade head
```

In production, migrations run automatically on deploy via Fly.io's `release_command`.
