def _get_fe(flag_data, env_name="development"):
    return next(fe for fe in flag_data["environments"] if fe["environment_name"] == env_name)


async def test_add_rule_returns_rule_with_id(client):
    proj = (await client.post("/projects", json={"name": "app"})).json()
    flag = (
        await client.post(
            f"/projects/{proj['id']}/flags",
            json={"key": "my_flag", "name": "F"},
        )
    ).json()
    dev_fe = _get_fe(flag)
    resp = await client.post(
        f"/flag-environments/{dev_fe['id']}/rules",
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
            json={"key": "my_flag", "name": "F"},
        )
    ).json()
    dev_fe = _get_fe(flag)
    await client.post(
        f"/flag-environments/{dev_fe['id']}/rules",
        json={"attribute": "email", "operator": "ends_with", "value": "@test.com"},
    )
    resp = await client.get(f"/flags/{flag['id']}")
    dev_fe = _get_fe(resp.json())
    assert len(dev_fe["rules"]) == 1


async def test_add_rule_invalid_operator_returns_422(client):
    proj = (await client.post("/projects", json={"name": "app"})).json()
    flag = (
        await client.post(
            f"/projects/{proj['id']}/flags",
            json={"key": "my_flag", "name": "F"},
        )
    ).json()
    dev_fe = _get_fe(flag)
    resp = await client.post(
        f"/flag-environments/{dev_fe['id']}/rules",
        json={"attribute": "email", "operator": "invalid_op", "value": "x"},
    )
    assert resp.status_code == 422


async def test_add_rule_empty_attribute_returns_422(client):
    proj = (await client.post("/projects", json={"name": "app"})).json()
    flag = (
        await client.post(
            f"/projects/{proj['id']}/flags",
            json={"key": "my_flag", "name": "F"},
        )
    ).json()
    dev_fe = _get_fe(flag)
    resp = await client.post(
        f"/flag-environments/{dev_fe['id']}/rules",
        json={"operator": "equals", "value": "x"},
    )
    assert resp.status_code == 422


async def _make_rule(client, attribute="email", operator="equals", value="x"):
    proj = (await client.post("/projects", json={"name": "app"})).json()
    flag = (
        await client.post(
            f"/projects/{proj['id']}/flags",
            json={"key": "my_flag", "name": "F"},
        )
    ).json()
    dev_fe = _get_fe(flag)
    rule = (
        await client.post(
            f"/flag-environments/{dev_fe['id']}/rules",
            json={"attribute": attribute, "operator": operator, "value": value},
        )
    ).json()
    return flag, rule


async def test_update_rule_changes_fields(client):
    flag, rule = await _make_rule(client, "email", "equals", "a@x.com")
    resp = await client.patch(
        f"/rules/{rule['id']}",
        json={"attribute": "plan", "operator": "in_list", "value": "pro"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == rule["id"]
    assert data["attribute"] == "plan"
    assert data["operator"] == "in_list"
    assert data["value"] == "pro"


async def test_update_rule_partial(client):
    flag, rule = await _make_rule(client, "email", "equals", "a@x.com")
    resp = await client.patch(f"/rules/{rule['id']}", json={"operator": "not_equals"})
    assert resp.status_code == 200
    data = resp.json()
    # only operator changed; attribute and value preserved
    assert data["attribute"] == "email"
    assert data["operator"] == "not_equals"
    assert data["value"] == "a@x.com"


async def test_update_rule_reflected_on_flag(client):
    flag, rule = await _make_rule(client, "email", "equals", "a@x.com")
    await client.patch(f"/rules/{rule['id']}", json={"attribute": "country"})
    flag_resp = await client.get(f"/flags/{flag['id']}")
    dev_fe = _get_fe(flag_resp.json())
    assert dev_fe["rules"][0]["attribute"] == "country"


async def test_update_rule_invalid_operator_returns_422(client):
    flag, rule = await _make_rule(client)
    resp = await client.patch(f"/rules/{rule['id']}", json={"operator": "invalid_op"})
    assert resp.status_code == 422


async def test_update_rule_triggers_cdn_publish(client):
    from unittest.mock import AsyncMock, patch

    flag, rule = await _make_rule(client)
    with patch("app.rules.service.publish_flags", new_callable=AsyncMock) as mock_pub:
        await client.patch(f"/rules/{rule['id']}", json={"value": "y"})
        assert mock_pub.called


async def test_update_nonexistent_rule_returns_404(client):
    import uuid

    resp = await client.patch(f"/rules/{uuid.uuid4()}", json={"value": "y"})
    assert resp.status_code == 404


async def test_remove_rule_deletes_it(client):
    proj = (await client.post("/projects", json={"name": "app"})).json()
    flag = (
        await client.post(
            f"/projects/{proj['id']}/flags",
            json={"key": "my_flag", "name": "F"},
        )
    ).json()
    dev_fe = _get_fe(flag)
    rule = (
        await client.post(
            f"/flag-environments/{dev_fe['id']}/rules",
            json={"attribute": "email", "operator": "equals", "value": "x"},
        )
    ).json()
    resp = await client.delete(f"/rules/{rule['id']}")
    assert resp.status_code == 204
    flag_resp = await client.get(f"/flags/{flag['id']}")
    dev_fe = _get_fe(flag_resp.json())
    assert len(dev_fe["rules"]) == 0


async def test_remove_rule_triggers_cdn_publish(client):
    from unittest.mock import AsyncMock, patch

    proj = (await client.post("/projects", json={"name": "app"})).json()
    flag = (
        await client.post(
            f"/projects/{proj['id']}/flags",
            json={"key": "my_flag", "name": "F"},
        )
    ).json()
    dev_fe = _get_fe(flag)
    rule = (
        await client.post(
            f"/flag-environments/{dev_fe['id']}/rules",
            json={"attribute": "email", "operator": "equals", "value": "x"},
        )
    ).json()
    with patch("app.rules.service.publish_flags", new_callable=AsyncMock) as mock_pub:
        await client.delete(f"/rules/{rule['id']}")
        assert mock_pub.called


async def test_remove_nonexistent_rule_returns_404(client):
    import uuid

    resp = await client.delete(f"/rules/{uuid.uuid4()}")
    assert resp.status_code == 404
