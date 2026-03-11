async def test_add_rule_returns_rule_with_id(client):
    proj = (await client.post("/projects", json={"name": "app"})).json()
    flag = (
        await client.post(
            f"/projects/{proj['id']}/flags",
            json={"key": "my_flag", "name": "F", "environment": "dev"},
        )
    ).json()
    resp = await client.post(
        f"/flags/{flag['id']}/rules",
        json={"attribute": "email", "operator": "ends_with", "value": "@test.com"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "id" in data
    assert data["attribute"] == "email"
    assert data["operator"] == "ends_with"


async def test_add_rule_flag_includes_rule(client):
    proj = (await client.post("/projects", json={"name": "app"})).json()
    flag = (
        await client.post(
            f"/projects/{proj['id']}/flags",
            json={"key": "my_flag", "name": "F", "environment": "dev"},
        )
    ).json()
    await client.post(
        f"/flags/{flag['id']}/rules",
        json={"attribute": "email", "operator": "ends_with", "value": "@test.com"},
    )
    resp = await client.get(f"/flags/{flag['id']}")
    assert len(resp.json()["rules"]) == 1


async def test_add_rule_invalid_operator_returns_422(client):
    proj = (await client.post("/projects", json={"name": "app"})).json()
    flag = (
        await client.post(
            f"/projects/{proj['id']}/flags",
            json={"key": "my_flag", "name": "F", "environment": "dev"},
        )
    ).json()
    resp = await client.post(
        f"/flags/{flag['id']}/rules",
        json={"attribute": "email", "operator": "invalid_op", "value": "x"},
    )
    assert resp.status_code == 422


async def test_add_rule_empty_attribute_returns_422(client):
    proj = (await client.post("/projects", json={"name": "app"})).json()
    flag = (
        await client.post(
            f"/projects/{proj['id']}/flags",
            json={"key": "my_flag", "name": "F", "environment": "dev"},
        )
    ).json()
    # attribute is a required field; missing attribute should return 422
    resp = await client.post(
        f"/flags/{flag['id']}/rules",
        json={"operator": "equals", "value": "x"},
    )
    assert resp.status_code == 422


async def test_remove_rule_deletes_it(client):
    proj = (await client.post("/projects", json={"name": "app"})).json()
    flag = (
        await client.post(
            f"/projects/{proj['id']}/flags",
            json={"key": "my_flag", "name": "F", "environment": "dev"},
        )
    ).json()
    rule = (
        await client.post(
            f"/flags/{flag['id']}/rules",
            json={"attribute": "email", "operator": "equals", "value": "x"},
        )
    ).json()
    resp = await client.delete(f"/rules/{rule['id']}")
    assert resp.status_code == 204
    flag_resp = await client.get(f"/flags/{flag['id']}")
    assert len(flag_resp.json()["rules"]) == 0


async def test_remove_rule_triggers_cdn_publish(client):
    """Rule removal triggers CDN publish via the rule_service mock."""
    from unittest.mock import AsyncMock, patch

    proj = (await client.post("/projects", json={"name": "app"})).json()
    flag = (
        await client.post(
            f"/projects/{proj['id']}/flags",
            json={"key": "my_flag", "name": "F", "environment": "dev"},
        )
    ).json()
    rule = (
        await client.post(
            f"/flags/{flag['id']}/rules",
            json={"attribute": "email", "operator": "equals", "value": "x"},
        )
    ).json()
    with patch("app.services.rule_service.publish_flags", new_callable=AsyncMock) as mock_pub:
        await client.delete(f"/rules/{rule['id']}")
        assert mock_pub.called


async def test_remove_nonexistent_rule_returns_404(client):
    import uuid

    resp = await client.delete(f"/rules/{uuid.uuid4()}")
    assert resp.status_code == 404
