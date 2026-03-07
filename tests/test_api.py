async def test_create_project(client):
    resp = await client.post("/projects", json={"name": "my-app"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "my-app"
    assert "api_key" in data
    assert "id" in data


async def test_list_projects(client):
    await client.post("/projects", json={"name": "p1"})
    await client.post("/projects", json={"name": "p2"})
    resp = await client.get("/projects")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


async def test_rotate_api_key(client):
    create_resp = await client.post("/projects", json={"name": "my-app"})
    project_id = create_resp.json()["id"]
    old_key = create_resp.json()["api_key"]
    resp = await client.post(f"/projects/{project_id}/rotate-key")
    assert resp.status_code == 200
    assert resp.json()["api_key"] != old_key


async def test_create_flag(client):
    proj = (await client.post("/projects", json={"name": "app"})).json()
    resp = await client.post(
        f"/projects/{proj['id']}/flags",
        json={
            "key": "new_checkout",
            "name": "New Checkout",
            "environment": "production",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["key"] == "new_checkout"
    assert data["enabled"] is False
    assert data["flag_type"] == "boolean"


async def test_list_flags(client):
    proj = (await client.post("/projects", json={"name": "app"})).json()
    pid = proj["id"]
    await client.post(f"/projects/{pid}/flags", json={"key": "f_one", "name": "F1", "environment": "dev"})
    await client.post(f"/projects/{pid}/flags", json={"key": "f_two", "name": "F2", "environment": "production"})
    resp = await client.get(f"/projects/{pid}/flags")
    assert len(resp.json()) == 2

    resp = await client.get(f"/projects/{pid}/flags?environment=dev")
    assert len(resp.json()) == 1
    assert resp.json()[0]["key"] == "f_one"


async def test_get_flag(client):
    proj = (await client.post("/projects", json={"name": "app"})).json()
    flag = (await client.post(
        f"/projects/{proj['id']}/flags",
        json={"key": "my_flag", "name": "My Flag", "environment": "dev"},
    )).json()
    resp = await client.get(f"/flags/{flag['id']}")
    assert resp.status_code == 200
    assert resp.json()["key"] == "my_flag"


async def test_update_flag(client):
    proj = (await client.post("/projects", json={"name": "app"})).json()
    flag = (await client.post(
        f"/projects/{proj['id']}/flags",
        json={"key": "my_flag", "name": "My Flag", "environment": "dev"},
    )).json()
    resp = await client.patch(f"/flags/{flag['id']}", json={"name": "Updated", "rollout_pct": 50})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated"
    assert resp.json()["rollout_pct"] == 50


async def test_toggle_flag(client):
    proj = (await client.post("/projects", json={"name": "app"})).json()
    flag = (await client.post(
        f"/projects/{proj['id']}/flags",
        json={"key": "my_flag", "name": "My Flag", "environment": "dev"},
    )).json()
    assert flag["enabled"] is False
    resp = await client.post(f"/flags/{flag['id']}/toggle")
    assert resp.json()["enabled"] is True
    resp = await client.post(f"/flags/{flag['id']}/toggle")
    assert resp.json()["enabled"] is False


async def test_delete_flag(client):
    proj = (await client.post("/projects", json={"name": "app"})).json()
    flag = (await client.post(
        f"/projects/{proj['id']}/flags",
        json={"key": "my_flag", "name": "My Flag", "environment": "dev"},
    )).json()
    resp = await client.delete(f"/flags/{flag['id']}")
    assert resp.status_code == 204
    resp = await client.get(f"/flags/{flag['id']}")
    assert resp.status_code == 404


async def test_flag_key_validation(client):
    proj = (await client.post("/projects", json={"name": "app"})).json()
    resp = await client.post(
        f"/projects/{proj['id']}/flags",
        json={"key": "Invalid Key!", "name": "Bad", "environment": "dev"},
    )
    assert resp.status_code == 422

    resp = await client.post(
        f"/projects/{proj['id']}/flags",
        json={"key": "1starts_with_num", "name": "Bad", "environment": "dev"},
    )
    assert resp.status_code == 422


async def test_rollout_pct_validation(client):
    proj = (await client.post("/projects", json={"name": "app"})).json()
    flag = (await client.post(
        f"/projects/{proj['id']}/flags",
        json={"key": "my_flag", "name": "F", "environment": "dev"},
    )).json()
    resp = await client.patch(f"/flags/{flag['id']}", json={"rollout_pct": 101})
    assert resp.status_code == 422
    resp = await client.patch(f"/flags/{flag['id']}", json={"rollout_pct": -1})
    assert resp.status_code == 422


async def test_add_and_remove_rule(client):
    proj = (await client.post("/projects", json={"name": "app"})).json()
    flag = (await client.post(
        f"/projects/{proj['id']}/flags",
        json={"key": "my_flag", "name": "F", "environment": "dev"},
    )).json()

    rule_resp = await client.post(
        f"/flags/{flag['id']}/rules",
        json={"attribute": "email", "operator": "ends_with", "value": "@test.com"},
    )
    assert rule_resp.status_code == 201
    rule = rule_resp.json()
    assert rule["attribute"] == "email"

    # Verify rule appears on flag
    flag_resp = await client.get(f"/flags/{flag['id']}")
    assert len(flag_resp.json()["rules"]) == 1

    # Remove rule
    resp = await client.delete(f"/rules/{rule['id']}")
    assert resp.status_code == 204

    flag_resp = await client.get(f"/flags/{flag['id']}")
    assert len(flag_resp.json()["rules"]) == 0


async def test_audit_log_on_mutations(client):
    proj = (await client.post("/projects", json={"name": "app"})).json()
    flag = (await client.post(
        f"/projects/{proj['id']}/flags",
        json={"key": "my_flag", "name": "F", "environment": "dev"},
    )).json()

    await client.post(f"/flags/{flag['id']}/toggle")
    await client.patch(f"/flags/{flag['id']}", json={"name": "Updated"})
    await client.post(
        f"/flags/{flag['id']}/rules",
        json={"attribute": "country", "operator": "equals", "value": "US"},
    )

    resp = await client.get(f"/flags/{flag['id']}/audit")
    assert resp.status_code == 200
    actions = [entry["action"] for entry in resp.json()]
    assert "created" in actions
    assert "toggled" in actions
    assert "updated" in actions
    assert "rule_added" in actions


async def test_auth_required(client):
    # Make requests without auth header
    from httpx import ASGITransport, AsyncClient
    from app.main import app as fastapi_app

    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as no_auth:
        resp = await no_auth.get("/projects")
        assert resp.status_code == 422  # missing header

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": "Bearer wrong-token"},
    ) as bad_auth:
        resp = await bad_auth.get("/projects")
        assert resp.status_code == 401


async def test_health_unauthenticated(client):
    from httpx import ASGITransport, AsyncClient
    from app.main import app as fastapi_app

    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as no_auth:
        resp = await no_auth.get("/health")
        assert resp.status_code == 200


async def test_cdn_publisher_called_on_mutations(client, _mock_cdn_publisher):
    proj = (await client.post("/projects", json={"name": "app"})).json()
    flag = (await client.post(
        f"/projects/{proj['id']}/flags",
        json={"key": "my_flag", "name": "F", "environment": "production"},
    )).json()
    assert _mock_cdn_publisher.called

    _mock_cdn_publisher.reset_mock()
    await client.post(f"/flags/{flag['id']}/toggle")
    assert _mock_cdn_publisher.called
