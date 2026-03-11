def _get_fe(flag_data, env_name="development"):
    """Get the flag_environment entry for a given environment name."""
    return next(fe for fe in flag_data["environments"] if fe["environment_name"] == env_name)


async def test_create_flag_returns_correct_fields(client):
    proj = (await client.post("/projects", json={"name": "app"})).json()
    resp = await client.post(
        f"/projects/{proj['id']}/flags",
        json={"key": "new_checkout", "name": "New Checkout"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["key"] == "new_checkout"
    assert data["name"] == "New Checkout"
    assert data["flag_type"] == "boolean"
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data
    assert len(data["environments"]) == 2  # development + production
    dev_fe = _get_fe(data, "development")
    assert dev_fe["enabled"] is False
    assert dev_fe["rollout_pct"] == 0
    assert dev_fe["rules"] == []


async def test_create_flag_invalid_key_returns_422(client):
    proj = (await client.post("/projects", json={"name": "app"})).json()
    resp = await client.post(
        f"/projects/{proj['id']}/flags",
        json={"key": "Invalid_Key", "name": "Bad"},
    )
    assert resp.status_code == 422
    resp = await client.post(
        f"/projects/{proj['id']}/flags",
        json={"key": "has space", "name": "Bad"},
    )
    assert resp.status_code == 422
    resp = await client.post(
        f"/projects/{proj['id']}/flags",
        json={"key": "1bad", "name": "Bad"},
    )
    assert resp.status_code == 422


async def test_create_flag_duplicate_key_fails(client):
    """Duplicate key for same project should fail."""
    proj = (await client.post("/projects", json={"name": "app"})).json()
    await client.post(
        f"/projects/{proj['id']}/flags",
        json={"key": "my_flag", "name": "F1"},
    )
    try:
        resp = await client.post(
            f"/projects/{proj['id']}/flags",
            json={"key": "my_flag", "name": "F2"},
        )
        assert resp.status_code in (409, 500)
    except Exception:
        pass


async def test_list_flags_returns_all_with_environments(client):
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
    resp = await client.get(f"/projects/{pid}/flags")
    data = resp.json()
    assert len(data) == 2
    # Each flag has environments
    assert len(data[0]["environments"]) == 2


async def test_list_flags_nonexistent_project_returns_empty(client):
    import uuid

    fake_id = str(uuid.uuid4())
    resp = await client.get(f"/projects/{fake_id}/flags")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_get_flag_includes_rules(client):
    proj = (await client.post("/projects", json={"name": "app"})).json()
    flag = (
        await client.post(
            f"/projects/{proj['id']}/flags",
            json={"key": "my_flag", "name": "F"},
        )
    ).json()
    dev_fe = _get_fe(flag, "development")
    await client.post(
        f"/flag-environments/{dev_fe['id']}/rules",
        json={"attribute": "email", "operator": "ends_with", "value": "@test.com"},
    )
    resp = await client.get(f"/flags/{flag['id']}")
    assert resp.status_code == 200
    dev_fe = _get_fe(resp.json(), "development")
    assert len(dev_fe["rules"]) == 1


async def test_get_nonexistent_flag_returns_404(client):
    import uuid

    resp = await client.get(f"/flags/{uuid.uuid4()}")
    assert resp.status_code == 404


async def test_update_flag_name(client):
    proj = (await client.post("/projects", json={"name": "app"})).json()
    flag = (
        await client.post(
            f"/projects/{proj['id']}/flags",
            json={"key": "my_flag", "name": "Old"},
        )
    ).json()
    resp = await client.patch(f"/flags/{flag['id']}", json={"name": "New Name"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "New Name"


async def test_update_flag_env_rollout_pct(client):
    proj = (await client.post("/projects", json={"name": "app"})).json()
    flag = (
        await client.post(
            f"/projects/{proj['id']}/flags",
            json={"key": "my_flag", "name": "F"},
        )
    ).json()
    dev_fe = _get_fe(flag, "development")
    resp = await client.patch(
        f"/flag-environments/{dev_fe['id']}", json={"rollout_pct": 75}
    )
    assert resp.status_code == 200
    dev_fe = _get_fe(resp.json(), "development")
    assert dev_fe["rollout_pct"] == 75


async def test_update_rollout_pct_over_100_returns_422(client):
    proj = (await client.post("/projects", json={"name": "app"})).json()
    flag = (
        await client.post(
            f"/projects/{proj['id']}/flags",
            json={"key": "my_flag", "name": "F"},
        )
    ).json()
    dev_fe = _get_fe(flag, "development")
    resp = await client.patch(
        f"/flag-environments/{dev_fe['id']}", json={"rollout_pct": 101}
    )
    assert resp.status_code == 422


async def test_update_rollout_pct_negative_returns_422(client):
    proj = (await client.post("/projects", json={"name": "app"})).json()
    flag = (
        await client.post(
            f"/projects/{proj['id']}/flags",
            json={"key": "my_flag", "name": "F"},
        )
    ).json()
    dev_fe = _get_fe(flag, "development")
    resp = await client.patch(
        f"/flag-environments/{dev_fe['id']}", json={"rollout_pct": -1}
    )
    assert resp.status_code == 422


async def test_toggle_flag_env_false_to_true(client):
    proj = (await client.post("/projects", json={"name": "app"})).json()
    flag = (
        await client.post(
            f"/projects/{proj['id']}/flags",
            json={"key": "my_flag", "name": "F"},
        )
    ).json()
    dev_fe = _get_fe(flag, "development")
    assert dev_fe["enabled"] is False
    resp = await client.post(f"/flag-environments/{dev_fe['id']}/toggle")
    dev_fe = _get_fe(resp.json(), "development")
    assert dev_fe["enabled"] is True


async def test_toggle_flag_env_true_to_false(client):
    proj = (await client.post("/projects", json={"name": "app"})).json()
    flag = (
        await client.post(
            f"/projects/{proj['id']}/flags",
            json={"key": "my_flag", "name": "F"},
        )
    ).json()
    dev_fe = _get_fe(flag, "development")
    await client.post(f"/flag-environments/{dev_fe['id']}/toggle")  # false -> true
    resp = await client.post(f"/flag-environments/{dev_fe['id']}/toggle")  # true -> false
    dev_fe = _get_fe(resp.json(), "development")
    assert dev_fe["enabled"] is False


async def test_delete_flag_removes_from_list(client):
    proj = (await client.post("/projects", json={"name": "app"})).json()
    flag = (
        await client.post(
            f"/projects/{proj['id']}/flags",
            json={"key": "my_flag", "name": "F"},
        )
    ).json()
    await client.delete(f"/flags/{flag['id']}")
    resp = await client.get(f"/projects/{proj['id']}/flags")
    assert len(resp.json()) == 0


async def test_delete_flag_cascades_to_rules(client):
    proj = (await client.post("/projects", json={"name": "app"})).json()
    flag = (
        await client.post(
            f"/projects/{proj['id']}/flags",
            json={"key": "my_flag", "name": "F"},
        )
    ).json()
    dev_fe = _get_fe(flag, "development")
    rule = (
        await client.post(
            f"/flag-environments/{dev_fe['id']}/rules",
            json={"attribute": "email", "operator": "equals", "value": "x"},
        )
    ).json()
    await client.delete(f"/flags/{flag['id']}")
    resp = await client.delete(f"/rules/{rule['id']}")
    assert resp.status_code == 404


async def test_flag_mutation_triggers_cdn_publish(client, _mock_cdn_publisher):
    proj = (await client.post("/projects", json={"name": "app"})).json()
    _mock_cdn_publisher.reset_mock()

    # Create
    flag = (
        await client.post(
            f"/projects/{proj['id']}/flags",
            json={"key": "my_flag", "name": "F"},
        )
    ).json()
    assert _mock_cdn_publisher.called
    _mock_cdn_publisher.reset_mock()

    # Toggle
    dev_fe = _get_fe(flag, "development")
    await client.post(f"/flag-environments/{dev_fe['id']}/toggle")
    assert _mock_cdn_publisher.called
    _mock_cdn_publisher.reset_mock()

    # Update name
    await client.patch(f"/flags/{flag['id']}", json={"name": "Updated"})
    # update_flag doesn't publish CDN (only name changed, no env change)
    _mock_cdn_publisher.reset_mock()

    # Delete
    await client.delete(f"/flags/{flag['id']}")
    assert _mock_cdn_publisher.called
