import os
from unittest.mock import AsyncMock, patch

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ["ADMIN_TOKEN"] = "test-admin-token"
os.environ["JWT_SECRET"] = "test-jwt-secret"
os.environ["GITHUB_CLIENT_ID"] = "test-client-id"
os.environ["GITHUB_CLIENT_SECRET"] = "test-client-secret"

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB

from app.audit.models import AuditLog  # noqa: F401
from app.auth.models import User  # noqa: F401
from app.base import Base
from app.database import get_db
from app.flags.models import Flag  # noqa: F401
from app.main import app as fastapi_app
from app.projects.models import Project  # noqa: F401
from app.rules.models import Rule  # noqa: F401

# Render JSONB as JSON for SQLite tests
compiles(JSONB, "sqlite")(lambda element, compiler, **kw: "JSON")

TEST_ENGINE = create_async_engine("sqlite+aiosqlite:///", echo=False)
TestSessionLocal = async_sessionmaker(TEST_ENGINE, expire_on_commit=False)


@pytest.fixture(autouse=True)
def _mock_cdn_publisher():
    with patch("app.flags.service.publish_flags", new_callable=AsyncMock) as m:
        with patch("app.rules.service.publish_flags", new_callable=AsyncMock):
            yield m


@pytest_asyncio.fixture()
async def db_session():
    async with TEST_ENGINE.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestSessionLocal() as session:
        yield session

    async with TEST_ENGINE.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture()
async def client(db_session):
    from httpx import ASGITransport, AsyncClient

    async def override_get_db():
        yield db_session

    fastapi_app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": "Bearer test-admin-token"},
    ) as c:
        yield c

    fastapi_app.dependency_overrides.clear()
