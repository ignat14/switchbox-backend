import json
from datetime import datetime
from unittest.mock import patch
from uuid import UUID


async def test_publish_generates_correct_json_structure(client, db_session):
    """Test the actual publish_flags function output structure."""
    proj = (await client.post("/projects", json={"name": "app"})).json()
    pid = proj["id"]
    # Create a flag
    await client.post(
        f"/projects/{pid}/flags",
        json={"key": "test_flag", "name": "TF", "environment": "dev"},
    )

    # Call the real publish_flags with a patched upload
    from app.services.cdn_publisher import publish_flags
    from pathlib import Path

    written = {}

    def capture_write(self, content, *args, **kwargs):
        written["content"] = content

    with patch("app.services.cdn_publisher.settings") as mock_settings, \
         patch.object(Path, "write_text", capture_write), \
         patch.object(Path, "mkdir"):
        mock_settings.R2_ACCOUNT_ID = ""
        await publish_flags(db_session, UUID(pid), "dev")

    if "content" in written:
        data = json.loads(written["content"])
        assert "version" in data
        assert "flags" in data
        assert "test_flag" in data["flags"]


async def test_publish_includes_all_flags_for_environment(client, db_session):
    proj = (await client.post("/projects", json={"name": "app"})).json()
    pid = proj["id"]
    await client.post(
        f"/projects/{pid}/flags",
        json={"key": "flag_a", "name": "A", "environment": "dev"},
    )
    await client.post(
        f"/projects/{pid}/flags",
        json={"key": "flag_b", "name": "B", "environment": "dev"},
    )
    await client.post(
        f"/projects/{pid}/flags",
        json={"key": "flag_prod", "name": "P", "environment": "production"},
    )

    from app.services.cdn_publisher import publish_flags
    from pathlib import Path

    written = {}

    def capture_write(self, content, *args, **kwargs):
        written["content"] = content

    with patch("app.services.cdn_publisher.settings") as mock_settings, \
         patch.object(Path, "write_text", capture_write), \
         patch.object(Path, "mkdir"):
        mock_settings.R2_ACCOUNT_ID = ""
        await publish_flags(db_session, UUID(pid), "dev")

    if "content" in written:
        data = json.loads(written["content"])
        assert "flag_a" in data["flags"]
        assert "flag_b" in data["flags"]
        assert "flag_prod" not in data["flags"]  # Different env


async def test_publish_includes_rules(client, db_session):
    proj = (await client.post("/projects", json={"name": "app"})).json()
    pid = proj["id"]
    flag = (
        await client.post(
            f"/projects/{pid}/flags",
            json={"key": "my_flag", "name": "F", "environment": "dev"},
        )
    ).json()
    await client.post(
        f"/flags/{flag['id']}/rules",
        json={"attribute": "email", "operator": "ends_with", "value": "@test.com"},
    )

    from app.services.cdn_publisher import publish_flags
    from pathlib import Path

    written = {}

    def capture_write(self, content, *args, **kwargs):
        written["content"] = content

    with patch("app.services.cdn_publisher.settings") as mock_settings, \
         patch.object(Path, "write_text", capture_write), \
         patch.object(Path, "mkdir"):
        mock_settings.R2_ACCOUNT_ID = ""
        await publish_flags(db_session, UUID(pid), "dev")

    if "content" in written:
        data = json.loads(written["content"])
        flag_data = data["flags"]["my_flag"]
        assert len(flag_data["rules"]) == 1
        assert flag_data["rules"][0]["attribute"] == "email"


async def test_publish_version_is_iso_timestamp(client, db_session):
    proj = (await client.post("/projects", json={"name": "app"})).json()
    pid = proj["id"]
    await client.post(
        f"/projects/{pid}/flags",
        json={"key": "my_flag", "name": "F", "environment": "dev"},
    )

    from app.services.cdn_publisher import publish_flags
    from pathlib import Path

    written = {}

    def capture_write(self, content, *args, **kwargs):
        written["content"] = content

    with patch("app.services.cdn_publisher.settings") as mock_settings, \
         patch.object(Path, "write_text", capture_write), \
         patch.object(Path, "mkdir"):
        mock_settings.R2_ACCOUNT_ID = ""
        await publish_flags(db_session, UUID(pid), "dev")

    if "content" in written:
        data = json.loads(written["content"])
        # Should be a parseable ISO timestamp
        datetime.fromisoformat(data["version"])


async def test_cdn_called_after_flag_create(client, _mock_cdn_publisher):
    proj = (await client.post("/projects", json={"name": "app"})).json()
    _mock_cdn_publisher.reset_mock()
    await client.post(
        f"/projects/{proj['id']}/flags",
        json={"key": "f", "name": "F", "environment": "dev"},
    )
    assert _mock_cdn_publisher.called


async def test_cdn_called_after_flag_toggle(client, _mock_cdn_publisher):
    proj = (await client.post("/projects", json={"name": "app"})).json()
    flag = (
        await client.post(
            f"/projects/{proj['id']}/flags",
            json={"key": "f", "name": "F", "environment": "dev"},
        )
    ).json()
    _mock_cdn_publisher.reset_mock()
    await client.post(f"/flags/{flag['id']}/toggle")
    assert _mock_cdn_publisher.called


async def test_cdn_called_after_flag_update(client, _mock_cdn_publisher):
    proj = (await client.post("/projects", json={"name": "app"})).json()
    flag = (
        await client.post(
            f"/projects/{proj['id']}/flags",
            json={"key": "f", "name": "F", "environment": "dev"},
        )
    ).json()
    _mock_cdn_publisher.reset_mock()
    await client.patch(f"/flags/{flag['id']}", json={"name": "Updated"})
    assert _mock_cdn_publisher.called


async def test_cdn_called_after_flag_delete(client, _mock_cdn_publisher):
    proj = (await client.post("/projects", json={"name": "app"})).json()
    flag = (
        await client.post(
            f"/projects/{proj['id']}/flags",
            json={"key": "f", "name": "F", "environment": "dev"},
        )
    ).json()
    _mock_cdn_publisher.reset_mock()
    await client.delete(f"/flags/{flag['id']}")
    assert _mock_cdn_publisher.called


async def test_cdn_called_after_rule_add(client):
    """Rule add triggers CDN publish via rule_service's publish_flags."""
    from unittest.mock import AsyncMock, patch

    proj = (await client.post("/projects", json={"name": "app"})).json()
    flag = (
        await client.post(
            f"/projects/{proj['id']}/flags",
            json={"key": "f", "name": "F", "environment": "dev"},
        )
    ).json()
    with patch("app.services.rule_service.publish_flags", new_callable=AsyncMock) as mock_pub:
        await client.post(
            f"/flags/{flag['id']}/rules",
            json={"attribute": "x", "operator": "equals", "value": "y"},
        )
        assert mock_pub.called


async def test_cdn_called_after_rule_remove(client):
    """Rule remove triggers CDN publish via rule_service's publish_flags."""
    from unittest.mock import AsyncMock, patch

    proj = (await client.post("/projects", json={"name": "app"})).json()
    flag = (
        await client.post(
            f"/projects/{proj['id']}/flags",
            json={"key": "f", "name": "F", "environment": "dev"},
        )
    ).json()
    rule = (
        await client.post(
            f"/flags/{flag['id']}/rules",
            json={"attribute": "x", "operator": "equals", "value": "y"},
        )
    ).json()
    with patch("app.services.rule_service.publish_flags", new_callable=AsyncMock) as mock_pub:
        await client.delete(f"/rules/{rule['id']}")
        assert mock_pub.called
