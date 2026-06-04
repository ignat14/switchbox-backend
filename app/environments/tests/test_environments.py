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


async def test_default_environments_have_sequential_positions(client):
    proj = (await client.post("/projects", json={"name": "app"})).json()
    envs = (await client.get(f"/projects/{proj['id']}/environments")).json()
    assert [e["position"] for e in envs] == [0, 1]
    assert [e["name"] for e in envs] == ["development", "production"]


async def test_new_environment_appended_at_end(client):
    proj = (await client.post("/projects", json={"name": "app"})).json()
    await client.post(f"/projects/{proj['id']}/environments", json={"name": "staging"})
    envs = (await client.get(f"/projects/{proj['id']}/environments")).json()
    assert [e["name"] for e in envs] == ["development", "production", "staging"]
    assert [e["position"] for e in envs] == [0, 1, 2]


async def test_reorder_environments(client):
    proj = (await client.post("/projects", json={"name": "app"})).json()
    await client.post(f"/projects/{proj['id']}/environments", json={"name": "staging"})
    envs = (await client.get(f"/projects/{proj['id']}/environments")).json()

    reversed_ids = [e["id"] for e in reversed(envs)]
    resp = await client.patch(
        f"/projects/{proj['id']}/environments/reorder",
        json={"environment_ids": reversed_ids},
    )
    assert resp.status_code == 200
    reordered = resp.json()
    assert [e["id"] for e in reordered] == reversed_ids
    assert [e["position"] for e in reordered] == [0, 1, 2]

    # Order persists on subsequent listing
    again = (await client.get(f"/projects/{proj['id']}/environments")).json()
    assert [e["id"] for e in again] == reversed_ids


async def test_reorder_rejects_mismatched_ids(client):
    proj = (await client.post("/projects", json={"name": "app"})).json()
    envs = (await client.get(f"/projects/{proj['id']}/environments")).json()
    # Drop one id — not a full set
    resp = await client.patch(
        f"/projects/{proj['id']}/environments/reorder",
        json={"environment_ids": [envs[0]["id"]]},
    )
    assert resp.status_code == 400


async def test_reorder_reflected_in_flag_environments(client):
    proj = (await client.post("/projects", json={"name": "app"})).json()
    envs = (await client.get(f"/projects/{proj['id']}/environments")).json()

    with patch("app.flags.cdn_publisher.publish_flags", new_callable=AsyncMock):
        flag = (
            await client.post(
                f"/projects/{proj['id']}/flags",
                json={"key": "my_flag", "name": "My Flag", "flag_type": "boolean"},
            )
        ).json()

    reversed_ids = [e["id"] for e in reversed(envs)]
    await client.patch(
        f"/projects/{proj['id']}/environments/reorder",
        json={"environment_ids": reversed_ids},
    )

    flag = (await client.get(f"/flags/{flag['id']}")).json()
    assert [fe["environment_id"] for fe in flag["environments"]] == reversed_ids
