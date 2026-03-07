# TinyFlags Backend

Feature flag service built with FastAPI, SQLAlchemy, and PostgreSQL.

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

### Run tests

```sh
uv run pytest
```

### Lint

```sh
uv run ruff check .
uv run ruff format --check .
```
