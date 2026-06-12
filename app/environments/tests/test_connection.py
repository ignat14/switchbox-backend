from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.auth.models import User
from app.auth.service import create_access_token
from app.config import settings
from app.environments import connection


@pytest.fixture(autouse=True)
def _kv_configured(monkeypatch):
    connection._cache.clear()
    monkeypatch.setattr(settings, "CF_KV_API_TOKEN", "test-cf-token")
    monkeypatch.setattr(settings, "CF_KV_NAMESPACE_ID", "test-namespace")
    monkeypatch.setattr(settings, "R2_ACCOUNT_ID", "test-account")
    yield
    connection._cache.clear()


async def _first_environment(client):
    proj = (await client.post("/projects", json={"name": "app"})).json()
    envs = (await client.get(f"/projects/{proj['id']}/environments")).json()
    return envs[0]


async def test_unknown_when_kv_unconfigured(client, monkeypatch):
    monkeypatch.setattr(settings, "CF_KV_API_TOKEN", "")
    env = await _first_environment(client)
    resp = await client.get(f"/environments/{env['id']}/connection")
    assert resp.status_code == 200
    assert resp.json() == {"status": "unknown", "last_seen_at": None}


async def test_never_when_kv_key_absent(client):
    env = await _first_environment(client)
    with patch.object(connection, "_read_last_seen", new=AsyncMock(return_value=None)):
        resp = await client.get(f"/environments/{env['id']}/connection")
    assert resp.status_code == 200
    assert resp.json() == {"status": "never", "last_seen_at": None}


async def test_connected_when_seen_recently(client):
    env = await _first_environment(client)
    last_seen = datetime.now(timezone.utc) - timedelta(minutes=2)
    with patch.object(
        connection, "_read_last_seen", new=AsyncMock(return_value=last_seen)
    ):
        resp = await client.get(f"/environments/{env['id']}/connection")
    body = resp.json()
    assert body["status"] == "connected"
    assert body["last_seen_at"] is not None


async def test_stale_when_seen_long_ago(client):
    env = await _first_environment(client)
    last_seen = datetime.now(timezone.utc) - timedelta(hours=3)
    with patch.object(
        connection, "_read_last_seen", new=AsyncMock(return_value=last_seen)
    ):
        resp = await client.get(f"/environments/{env['id']}/connection")
    body = resp.json()
    assert body["status"] == "stale"
    assert body["last_seen_at"] is not None


async def test_unknown_when_kv_read_fails(client):
    env = await _first_environment(client)
    with patch.object(
        connection, "_read_last_seen", new=AsyncMock(side_effect=RuntimeError("boom"))
    ):
        resp = await client.get(f"/environments/{env['id']}/connection")
    assert resp.json() == {"status": "unknown", "last_seen_at": None}


async def test_grace_period_uses_freshest_of_both_keys(client):
    """After a rotation, clients still polling the old key must count."""
    env = await _first_environment(client)
    with patch("app.flags.cdn_publisher.publish_flags", new_callable=AsyncMock):
        rotated = (
            await client.post(f"/environments/{env['id']}/rotate-sdk-key")
        ).json()

    previous_key = rotated["previous_sdk_key"]
    last_seen = datetime.now(timezone.utc) - timedelta(minutes=1)

    async def read(http_client, sdk_key):
        return last_seen if sdk_key == previous_key else None

    with patch.object(connection, "_read_last_seen", new=read):
        resp = await client.get(f"/environments/{rotated['id']}/connection")
    body = resp.json()
    assert body["status"] == "connected"
    assert body["last_seen_at"] is not None


async def test_result_is_cached(client):
    env = await _first_environment(client)
    mock = AsyncMock(return_value=datetime.now(timezone.utc))
    with patch.object(connection, "_read_last_seen", new=mock):
        await client.get(f"/environments/{env['id']}/connection")
        await client.get(f"/environments/{env['id']}/connection")
    assert mock.call_count == 1


async def test_connection_scoped_to_project_owner(client, db_session):
    owner = User(github_id=1, github_login="owner")
    intruder = User(github_id=2, github_login="intruder")
    db_session.add_all([owner, intruder])
    await db_session.commit()

    owner_headers = {"Authorization": f"Bearer {create_access_token(owner)}"}
    intruder_headers = {"Authorization": f"Bearer {create_access_token(intruder)}"}

    proj = (
        await client.post("/projects", json={"name": "app"}, headers=owner_headers)
    ).json()
    envs = (await client.get(f"/projects/{proj['id']}/environments")).json()
    env_id = envs[0]["id"]

    with patch.object(connection, "_read_last_seen", new=AsyncMock(return_value=None)):
        denied = await client.get(
            f"/environments/{env_id}/connection", headers=intruder_headers
        )
        assert denied.status_code == 404

        allowed = await client.get(
            f"/environments/{env_id}/connection", headers=owner_headers
        )
        assert allowed.status_code == 200

        # Admin token (default client headers) is superadmin and sees all.
        admin = await client.get(f"/environments/{env_id}/connection")
        assert admin.status_code == 200
