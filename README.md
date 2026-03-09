# Switchbox Backend

Feature flag service with a CDN publish pipeline. When flags change, a static JSON config is generated and uploaded to Cloudflare R2 so SDKs can fetch flags without hitting the API.

## Architecture

```
┌──────────────┐       ┌──────────────┐       ┌──────────────┐
│   Dashboard  │──────>│  FastAPI      │──────>│ Neon Postgres│
│   (future)   │ HTTP  │  (Fly.io)    │  SQL  │  (database)  │
└──────────────┘       └──────┬───────┘       └──────────────┘
                              │
                              │ on every mutation
                              v
                       ┌──────────────┐       ┌──────────────┐
                       │ CDN Publisher │──────>│ Cloudflare R2│
                       │ (boto3/S3)   │  PUT  │ (static JSON)│
                       └──────────────┘       └──────┬───────┘
                                                     │
                                                     │ public URL
                                                     v
                                              ┌──────────────┐
                                              │   SDKs       │
                                              │ (fetch JSON) │
                                              └──────────────┘
```

## Production stack

| Service          | Provider         | Details                                      |
|------------------|------------------|----------------------------------------------|
| API server       | Fly.io           | `switchbox-backend.fly.dev`, Amsterdam (ams)  |
| Database         | Neon Postgres    | Serverless, auto-scaling                      |
| Flag configs CDN | Cloudflare R2    | S3-compatible, public bucket                  |
| Migrations       | Alembic          | Runs on deploy via `release_command`           |

## Database tables

- **projects** -- each project has a name and a hashed API key
- **flags** -- feature flags with key, type, environment, rollout %, enabled state
- **rules** -- targeting rules attached to flags (attribute/operator/value)
- **audit_logs** -- tracks every mutation (created, toggled, updated, rule_added, etc.)

## API endpoints

All endpoints except `/health` require `Authorization: Bearer {ADMIN_TOKEN}`.

### Projects

| Method | Path                          | Description                        |
|--------|-------------------------------|------------------------------------|
| POST   | `/projects`                   | Create project (returns API key)   |
| GET    | `/projects`                   | List all projects                  |
| POST   | `/projects/{id}/rotate-key`   | Rotate API key                     |

### Flags

| Method | Path                              | Description                            |
|--------|-----------------------------------|----------------------------------------|
| POST   | `/projects/{project_id}/flags`    | Create flag                            |
| GET    | `/projects/{project_id}/flags`    | List flags (optional `?environment=`)  |
| GET    | `/flags/{flag_id}`                | Get flag with rules                    |
| PATCH  | `/flags/{flag_id}`                | Update flag (name, rollout_pct, etc.)  |
| POST   | `/flags/{flag_id}/toggle`         | Toggle enabled on/off                  |
| DELETE | `/flags/{flag_id}`                | Delete flag (cascades to rules)        |
| GET    | `/flags/{flag_id}/audit`          | Get audit log                          |

### Rules

| Method | Path                        | Description  |
|--------|-----------------------------|--------------|
| POST   | `/flags/{flag_id}/rules`    | Add rule     |
| DELETE | `/rules/{rule_id}`          | Remove rule  |

### Admin

| Method | Path                                        | Description                  |
|--------|---------------------------------------------|------------------------------|
| POST   | `/admin/publish/{project_id}/{environment}` | Manually re-publish to CDN   |
| GET    | `/health`                                   | Health check (no auth)       |

## CDN publish pipeline

Every flag or rule mutation triggers `publish_flags()`, which:

1. Queries all flags + rules for the project/environment
2. Builds a JSON config keyed by flag name (O(1) SDK lookups)
3. Uploads to R2 at `{project_id}/{environment}/flags.json`
4. Sets `Cache-Control: public, max-age=30`

If R2 is not configured, it writes to `cdn_output/` locally instead.

If the upload fails, the error is logged but the API request still succeeds -- the database is the source of truth.

Example output (`{project_id}/production/flags.json`):

```json
{
  "version": "2026-03-07T12:00:00+00:00",
  "flags": {
    "new_checkout": {
      "enabled": true,
      "rollout_pct": 100,
      "flag_type": "boolean",
      "default_value": false,
      "rules": [
        {
          "attribute": "email",
          "operator": "ends_with",
          "value": "@company.com"
        }
      ]
    }
  }
}
```

## Local development

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/)
- [uv](https://docs.astral.sh/uv/getting-started/installation/)

### Run with Docker

```sh
docker compose up
```

This starts the API on http://localhost:8000 and a PostgreSQL database on port 5432.

Run migrations:

```sh
docker compose exec api uv run alembic upgrade head
```

### Run without Docker

Copy the example env file and fill in your database URL:

```sh
cp .env.example .env
```

Install dependencies and start the server:

```sh
uv sync --dev
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

### Environment variables

| Variable              | Required | Description                          |
|-----------------------|----------|--------------------------------------|
| `DATABASE_URL`        | Yes      | Postgres connection string           |
| `ADMIN_TOKEN`         | Yes      | Bearer token for admin endpoints     |
| `R2_ACCOUNT_ID`       | No       | Cloudflare account ID                |
| `R2_ACCESS_KEY_ID`    | No       | R2 S3-compatible access key          |
| `R2_SECRET_ACCESS_KEY`| No       | R2 S3-compatible secret key          |
| `R2_BUCKET_NAME`      | No       | R2 bucket name (default: flaggy-configs) |
| `R2_PUBLIC_URL`       | No       | Public R2 URL for SDK consumption    |

When R2 vars are empty, the CDN publisher writes JSON files to `cdn_output/` locally.

### Run tests

```sh
uv run pytest
```

Tests use an in-memory SQLite database and mock the CDN publisher.

### Lint

```sh
uv run ruff check .
uv run ruff format --check .
```

## Deploy

The app deploys to Fly.io. Alembic migrations run automatically on deploy.

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
  R2_BUCKET_NAME="..." \
  R2_PUBLIC_URL="..."
```
