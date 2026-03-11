async def test_create_flag_creates_audit_entry(client):
    proj = (await client.post("/projects", json={"name": "app"})).json()
    flag = (
        await client.post(
            f"/projects/{proj['id']}/flags",
            json={"key": "my_flag", "name": "F", "environment": "dev"},
        )
    ).json()
    resp = await client.get(f"/flags/{flag['id']}/audit")
    assert resp.status_code == 200
    entries = resp.json()
    assert any(e["action"] == "created" for e in entries)


async def test_toggle_creates_audit_with_old_new_values(client):
    proj = (await client.post("/projects", json={"name": "app"})).json()
    flag = (
        await client.post(
            f"/projects/{proj['id']}/flags",
            json={"key": "my_flag", "name": "F", "environment": "dev"},
        )
    ).json()
    await client.post(f"/flags/{flag['id']}/toggle")
    resp = await client.get(f"/flags/{flag['id']}/audit")
    toggle_entry = next(e for e in resp.json() if e["action"] == "toggled")
    assert toggle_entry["old_value"] == {"enabled": False}
    assert toggle_entry["new_value"] == {"enabled": True}


async def test_update_rollout_creates_audit_with_old_new_pct(client):
    proj = (await client.post("/projects", json={"name": "app"})).json()
    flag = (
        await client.post(
            f"/projects/{proj['id']}/flags",
            json={"key": "my_flag", "name": "F", "environment": "dev"},
        )
    ).json()
    await client.patch(f"/flags/{flag['id']}", json={"rollout_pct": 50})
    resp = await client.get(f"/flags/{flag['id']}/audit")
    update_entry = next(e for e in resp.json() if e["action"] == "updated")
    assert update_entry["old_value"]["rollout_pct"] == 0
    assert update_entry["new_value"]["rollout_pct"] == 50


async def test_add_rule_creates_audit_entry(client):
    proj = (await client.post("/projects", json={"name": "app"})).json()
    flag = (
        await client.post(
            f"/projects/{proj['id']}/flags",
            json={"key": "my_flag", "name": "F", "environment": "dev"},
        )
    ).json()
    await client.post(
        f"/flags/{flag['id']}/rules",
        json={"attribute": "country", "operator": "equals", "value": "US"},
    )
    resp = await client.get(f"/flags/{flag['id']}/audit")
    assert any(e["action"] == "rule_added" for e in resp.json())


async def test_remove_rule_creates_audit_entry(client):
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
            json={"attribute": "country", "operator": "equals", "value": "US"},
        )
    ).json()
    await client.delete(f"/rules/{rule['id']}")
    resp = await client.get(f"/flags/{flag['id']}/audit")
    assert any(e["action"] == "rule_removed" for e in resp.json())


async def test_audit_entries_ordered_by_timestamp_desc(client):
    proj = (await client.post("/projects", json={"name": "app"})).json()
    flag = (
        await client.post(
            f"/projects/{proj['id']}/flags",
            json={"key": "my_flag", "name": "F", "environment": "dev"},
        )
    ).json()
    await client.post(f"/flags/{flag['id']}/toggle")
    await client.patch(f"/flags/{flag['id']}", json={"name": "Updated"})
    resp = await client.get(f"/flags/{flag['id']}/audit")
    entries = resp.json()
    timestamps = [e["timestamp"] for e in entries]
    assert timestamps == sorted(timestamps, reverse=True)


async def test_audit_entries_include_changed_by(client):
    """changed_by is currently None since auth doesn't populate it, but field should exist."""
    proj = (await client.post("/projects", json={"name": "app"})).json()
    flag = (
        await client.post(
            f"/projects/{proj['id']}/flags",
            json={"key": "my_flag", "name": "F", "environment": "dev"},
        )
    ).json()
    resp = await client.get(f"/flags/{flag['id']}/audit")
    for entry in resp.json():
        assert "changed_by" in entry
