from unittest.mock import AsyncMock, patch


async def test_create_environment_returns_sdk_key(client):
    proj = (await client.post("/projects", json={"name": "app"})).json()
    resp = await client.get(f"/projects/{proj['id']}/environments")
    envs = resp.json()
    assert len(envs) == 2
    for env in envs:
        assert "sdk_key" in env
        assert len(env["sdk_key"]) > 20


async def test_each_environment_has_unique_sdk_key(client):
    proj = (await client.post("/projects", json={"name": "app"})).json()
    resp = await client.get(f"/projects/{proj['id']}/environments")
    envs = resp.json()
    sdk_keys = [e["sdk_key"] for e in envs]
    assert len(sdk_keys) == len(set(sdk_keys))


async def test_new_environment_gets_sdk_key(client):
    proj = (await client.post("/projects", json={"name": "app"})).json()
    resp = await client.post(
        f"/projects/{proj['id']}/environments", json={"name": "staging"}
    )
    assert resp.status_code == 201
    env = resp.json()
    assert "sdk_key" in env
    assert len(env["sdk_key"]) > 20


async def test_rotate_sdk_key_returns_new_key(client):
    proj = (await client.post("/projects", json={"name": "app"})).json()
    envs = (await client.get(f"/projects/{proj['id']}/environments")).json()
    env = envs[0]
    old_key = env["sdk_key"]

    with patch("app.flags.cdn_publisher.publish_flags", new_callable=AsyncMock):
        resp = await client.post(f"/environments/{env['id']}/rotate-sdk-key")
    assert resp.status_code == 200
    rotated = resp.json()
    assert rotated["sdk_key"] != old_key
    assert rotated["previous_sdk_key"] == old_key
    assert rotated["previous_sdk_key_expires_at"] is not None


async def test_rotate_sdk_key_preserves_previous_key(client):
    proj = (await client.post("/projects", json={"name": "app"})).json()
    envs = (await client.get(f"/projects/{proj['id']}/environments")).json()
    env = envs[0]
    old_key = env["sdk_key"]

    with patch("app.flags.cdn_publisher.publish_flags", new_callable=AsyncMock):
        rotated = (
            await client.post(f"/environments/{env['id']}/rotate-sdk-key")
        ).json()

    assert rotated["previous_sdk_key"] == old_key


async def test_rotate_sdk_key_twice_succeeds(client):
    """Rotating twice should work — second rotation overwrites first previous key."""
    proj = (await client.post("/projects", json={"name": "app"})).json()
    envs = (await client.get(f"/projects/{proj['id']}/environments")).json()
    env = envs[0]

    with patch("app.flags.cdn_publisher.publish_flags", new_callable=AsyncMock):
        first = (
            await client.post(f"/environments/{env['id']}/rotate-sdk-key")
        ).json()
        first_key = first["sdk_key"]

        second = (
            await client.post(f"/environments/{env['id']}/rotate-sdk-key")
        ).json()

    assert second["sdk_key"] != first_key
    assert second["previous_sdk_key"] == first_key


async def test_rotate_sdk_key_triggers_cdn_publish(client):
    proj = (await client.post("/projects", json={"name": "app"})).json()
    envs = (await client.get(f"/projects/{proj['id']}/environments")).json()
    env = envs[0]

    with patch("app.flags.cdn_publisher.publish_flags", new_callable=AsyncMock) as mock_pub:
        await client.post(f"/environments/{env['id']}/rotate-sdk-key")
        assert mock_pub.called


async def test_environment_response_has_no_grace_period_by_default(client):
    proj = (await client.post("/projects", json={"name": "app"})).json()
    envs = (await client.get(f"/projects/{proj['id']}/environments")).json()
    for env in envs:
        assert env["previous_sdk_key"] is None
        assert env["previous_sdk_key_expires_at"] is None


async def test_environment_name_allows_spaces(client):
    proj = (await client.post("/projects", json={"name": "app"})).json()
    resp = await client.post(
        f"/projects/{proj['id']}/environments", json={"name": "Staging 2"}
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "Staging 2"
