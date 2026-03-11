import json
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import UUID

from app.flags.cdn_publisher import publish_flags


def _get_fe(flag_data, env_name="development"):
    return next(fe for fe in flag_data["environments"] if fe["environment_name"] == env_name)


async def _get_env_id(client, project_id, env_name="development"):
    """Get environment ID by name for a project."""
    resp = await client.get(f"/projects/{project_id}/environments")
    envs = resp.json()
    return next(e["id"] for e in envs if e["name"] == env_name)


async def _publish_and_capture(db_session, pid, environment_id, environment_name):
    """Call publish_flags with local file output and return the written JSON dict."""
    written = {}

    def capture_write(self, content, *args, **kwargs):
        written["content"] = content

    with (
        patch("app.flags.cdn_publisher.settings") as mock_settings,
        patch.object(Path, "write_text", capture_write),
        patch.object(Path, "mkdir"),
    ):
        mock_settings.R2_ACCOUNT_ID = ""
        await publish_flags(db_session, UUID(pid), UUID(environment_id), environment_name)

    assert "content" in written, "publish_flags did not write any output"
    return json.loads(written["content"])


async def test_publish_generates_correct_json_structure(client, db_session):
    proj = (await client.post("/projects", json={"name": "app"})).json()
    pid = proj["id"]
    await client.post(
        f"/projects/{pid}/flags",
        json={"key": "test_flag", "name": "TF"},
    )
    env_id = await _get_env_id(client, pid, "development")
    data = await _publish_and_capture(db_session, pid, env_id, "development")
    assert "version" in data
    assert "flags" in data
    assert "test_flag" in data["flags"]


async def test_publish_includes_all_flags_for_environment(client, db_session):
    proj = (await client.post("/projects", json={"name": "app"})).json()
    pid = proj["id"]
    await client.post(
        f"/projects/{pid}/flags",
        json={"key": "flag_a", "name": "A"},
    )
    await client.post(
        f"/projects/{pid}/flags",
        json={"key": "flag_b", "name": "B"},
    )

    env_id = await _get_env_id(client, pid, "development")
    data = await _publish_and_capture(db_session, pid, env_id, "development")
    assert "flag_a" in data["flags"]
    assert "flag_b" in data["flags"]


async def test_publish_includes_rules(client, db_session):
    proj = (await client.post("/projects", json={"name": "app"})).json()
    pid = proj["id"]
    flag = (
        await client.post(
            f"/projects/{pid}/flags",
            json={"key": "my_flag", "name": "F"},
        )
    ).json()
    dev_fe = _get_fe(flag)
    await client.post(
        f"/flag-environments/{dev_fe['id']}/rules",
        json={"attribute": "email", "operator": "ends_with", "value": "@test.com"},
    )

    env_id = await _get_env_id(client, pid, "development")
    data = await _publish_and_capture(db_session, pid, env_id, "development")
    flag_data = data["flags"]["my_flag"]
    assert len(flag_data["rules"]) == 1
    assert flag_data["rules"][0]["attribute"] == "email"


async def test_publish_version_is_iso_timestamp(client, db_session):
    proj = (await client.post("/projects", json={"name": "app"})).json()
    pid = proj["id"]
    await client.post(
        f"/projects/{pid}/flags",
        json={"key": "my_flag", "name": "F"},
    )

    env_id = await _get_env_id(client, pid, "development")
    data = await _publish_and_capture(db_session, pid, env_id, "development")
    datetime.fromisoformat(data["version"])


async def test_cdn_called_after_flag_create(client, _mock_cdn_publisher):
    proj = (await client.post("/projects", json={"name": "app"})).json()
    _mock_cdn_publisher.reset_mock()
    await client.post(
        f"/projects/{proj['id']}/flags",
        json={"key": "f", "name": "F"},
    )
    assert _mock_cdn_publisher.called


async def test_cdn_called_after_flag_toggle(client, _mock_cdn_publisher):
    proj = (await client.post("/projects", json={"name": "app"})).json()
    flag = (
        await client.post(
            f"/projects/{proj['id']}/flags",
            json={"key": "f", "name": "F"},
        )
    ).json()
    dev_fe = _get_fe(flag)
    _mock_cdn_publisher.reset_mock()
    await client.post(f"/flag-environments/{dev_fe['id']}/toggle")
    assert _mock_cdn_publisher.called


async def test_cdn_called_after_flag_update(client, _mock_cdn_publisher):
    proj = (await client.post("/projects", json={"name": "app"})).json()
    flag = (
        await client.post(
            f"/projects/{proj['id']}/flags",
            json={"key": "f", "name": "F"},
        )
    ).json()
    dev_fe = _get_fe(flag)
    _mock_cdn_publisher.reset_mock()
    await client.patch(
        f"/flag-environments/{dev_fe['id']}", json={"rollout_pct": 50}
    )
    assert _mock_cdn_publisher.called


async def test_cdn_called_after_flag_delete(client, _mock_cdn_publisher):
    proj = (await client.post("/projects", json={"name": "app"})).json()
    flag = (
        await client.post(
            f"/projects/{proj['id']}/flags",
            json={"key": "f", "name": "F"},
        )
    ).json()
    _mock_cdn_publisher.reset_mock()
    await client.delete(f"/flags/{flag['id']}")
    assert _mock_cdn_publisher.called


async def test_cdn_called_after_rule_add(client):
    proj = (await client.post("/projects", json={"name": "app"})).json()
    flag = (
        await client.post(
            f"/projects/{proj['id']}/flags",
            json={"key": "f", "name": "F"},
        )
    ).json()
    dev_fe = _get_fe(flag)
    with patch("app.rules.service.publish_flags", new_callable=AsyncMock) as mock_pub:
        await client.post(
            f"/flag-environments/{dev_fe['id']}/rules",
            json={"attribute": "x", "operator": "equals", "value": "y"},
        )
        assert mock_pub.called


async def test_cdn_called_after_rule_remove(client):
    proj = (await client.post("/projects", json={"name": "app"})).json()
    flag = (
        await client.post(
            f"/projects/{proj['id']}/flags",
            json={"key": "f", "name": "F"},
        )
    ).json()
    dev_fe = _get_fe(flag)
    rule = (
        await client.post(
            f"/flag-environments/{dev_fe['id']}/rules",
            json={"attribute": "x", "operator": "equals", "value": "y"},
        )
    ).json()
    with patch("app.rules.service.publish_flags", new_callable=AsyncMock) as mock_pub:
        await client.delete(f"/rules/{rule['id']}")
        assert mock_pub.called
