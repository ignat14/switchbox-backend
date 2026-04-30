from unittest.mock import AsyncMock, patch

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.auth.models import User
from app.auth.service import create_access_token
from app.base import Base
from app.conftest import TEST_ENGINE, TestSessionLocal
from app.database import get_db
from app.main import app as fastapi_app


# --- Existing admin token tests ---


async def test_no_auth_header_returns_422(client):
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as no_auth:
        resp = await no_auth.get("/projects")
        assert resp.status_code == 422  # missing required header


async def test_invalid_token_returns_401(client):
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": "Bearer wrong-token"},
    ) as bad_auth:
        resp = await bad_auth.get("/projects")
        assert resp.status_code == 401


async def test_valid_admin_token_succeeds(client):
    resp = await client.get("/projects")
    assert resp.status_code == 200


# --- JWT / GitHub OAuth tests ---


@pytest_asyncio.fixture()
async def auth_db():
    async with TEST_ENGINE.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with TestSessionLocal() as session:
        yield session
    async with TEST_ENGINE.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture()
async def test_user(auth_db):
    user = User(
        github_id=12345,
        github_login="testuser",
        email="test@example.com",
        avatar_url="https://avatars.githubusercontent.com/u/12345",
    )
    auth_db.add(user)
    await auth_db.commit()
    await auth_db.refresh(user)
    return user


@pytest_asyncio.fixture()
async def user_client(auth_db, test_user):
    async def override_get_db():
        yield auth_db

    fastapi_app.dependency_overrides[get_db] = override_get_db

    token = create_access_token(test_user)
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as c:
        yield c

    fastapi_app.dependency_overrides.clear()


@pytest_asyncio.fixture()
async def admin_client_auth(auth_db):
    async def override_get_db():
        yield auth_db

    fastapi_app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": "Bearer test-admin-token"},
    ) as c:
        yield c

    fastapi_app.dependency_overrides.clear()


async def test_github_login_url():
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/auth/github/login")
    assert resp.status_code == 200
    data = resp.json()
    assert "url" in data
    assert "github.com/login/oauth/authorize" in data["url"]
    assert "test-client-id" in data["url"]


async def test_github_callback_success(auth_db):
    async def override_get_db():
        yield auth_db

    fastapi_app.dependency_overrides[get_db] = override_get_db

    mock_github_user = {
        "id": 99999,
        "login": "octocat",
        "email": "octocat@github.com",
        "avatar_url": "https://github.com/octocat.png",
    }

    with (
        patch("app.auth.router.exchange_github_code", new_callable=AsyncMock, return_value="fake-token"),
        patch("app.auth.router.fetch_github_user", new_callable=AsyncMock, return_value=mock_github_user),
    ):
        transport = ASGITransport(app=fastapi_app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.post("/auth/github/callback", json={"code": "test-code"})

    fastapi_app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["user"]["github_login"] == "octocat"
    assert data["user"]["email"] == "octocat@github.com"
    assert data["token_type"] == "bearer"


async def test_github_callback_invalid_code(auth_db):
    async def override_get_db():
        yield auth_db

    fastapi_app.dependency_overrides[get_db] = override_get_db

    with patch(
        "app.auth.router.exchange_github_code",
        new_callable=AsyncMock,
        side_effect=Exception("bad code"),
    ):
        transport = ASGITransport(app=fastapi_app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.post("/auth/github/callback", json={"code": "bad-code"})

    fastapi_app.dependency_overrides.clear()
    assert resp.status_code == 400


async def test_auth_me_returns_user(user_client, test_user):
    resp = await user_client.get("/auth/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["github_login"] == "testuser"
    assert data["email"] == "test@example.com"


async def test_auth_me_invalid_token(auth_db):
    async def override_get_db():
        yield auth_db

    fastapi_app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": "Bearer invalid-jwt-token"},
    ) as c:
        resp = await c.get("/auth/me")

    fastapi_app.dependency_overrides.clear()
    assert resp.status_code == 401


async def test_jwt_user_can_create_and_list_projects(user_client):
    resp = await user_client.post("/projects", json={"name": "My Project"})
    assert resp.status_code == 201
    assert resp.json()["name"] == "My Project"

    resp = await user_client.get("/projects")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


async def test_user_projects_scoped_to_user(user_client, admin_client_auth):
    # Admin creates a project (no user_id)
    await admin_client_auth.post("/projects", json={"name": "Admin Project"})

    # User creates a project (has user_id)
    await user_client.post("/projects", json={"name": "User Project"})

    # Admin sees all projects
    resp = await admin_client_auth.get("/projects")
    assert len(resp.json()) == 2

    # User sees only their project
    resp = await user_client.get("/projects")
    assert len(resp.json()) == 1
    assert resp.json()[0]["name"] == "User Project"


async def test_audit_log_includes_changed_by(user_client):
    resp = await user_client.post("/projects", json={"name": "Audit Test"})
    project_id = resp.json()["id"]

    resp = await user_client.post(
        f"/projects/{project_id}/flags",
        json={"key": "test_flag", "name": "Test Flag", "flag_type": "boolean"},
    )
    flag_data = resp.json()
    flag_id = flag_data["id"]
    dev_fe = next(fe for fe in flag_data["environments"] if fe["environment_name"] == "development")

    await user_client.post(f"/flag-environments/{dev_fe['id']}/toggle")

    resp = await user_client.get(f"/flags/{flag_id}/audit")
    assert resp.status_code == 200
    entries = resp.json()
    assert len(entries) >= 2
    for entry in entries:
        assert entry["changed_by"] == "testuser"
