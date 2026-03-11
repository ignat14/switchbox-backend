async def test_create_project_returns_expected_fields(client):
    resp = await client.post("/projects", json={"name": "my-app"})
    assert resp.status_code == 201
    data = resp.json()
    assert "id" in data
    assert "name" in data
    assert "api_key" in data
    assert "created_at" in data


async def test_create_project_api_key_format(client):
    resp = await client.post("/projects", json={"name": "app"})
    api_key = resp.json()["api_key"]
    assert len(api_key) >= 32  # token_urlsafe(32) produces ~43 chars


async def test_list_projects_returns_all(client):
    await client.post("/projects", json={"name": "p1"})
    await client.post("/projects", json={"name": "p2"})
    resp = await client.get("/projects")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


async def test_list_projects_excludes_api_key_hash(client):
    await client.post("/projects", json={"name": "p1"})
    resp = await client.get("/projects")
    for p in resp.json():
        assert "api_key_hash" not in p
        assert "api_key" not in p


async def test_rotate_api_key_returns_new_key(client):
    create = (await client.post("/projects", json={"name": "app"})).json()
    resp = await client.post(f"/projects/{create['id']}/rotate-key")
    assert resp.status_code == 200
    assert resp.json()["api_key"] != create["api_key"]


async def test_rotate_api_key_old_key_invalid(client, db_session):
    """After rotation, the old key should no longer resolve to the project."""
    from app.services.project_service import get_project_by_api_key

    create = (await client.post("/projects", json={"name": "app"})).json()
    old_key = create["api_key"]

    # Old key works before rotation
    project = await get_project_by_api_key(db_session, old_key)
    assert project is not None

    # Rotate
    resp = await client.post(f"/projects/{create['id']}/rotate-key")
    new_key = resp.json()["api_key"]

    # Old key no longer works
    project = await get_project_by_api_key(db_session, old_key)
    assert project is None

    # New key works
    project = await get_project_by_api_key(db_session, new_key)
    assert project is not None
    assert str(project.id) == create["id"]


async def test_create_project_empty_name_returns_422(client):
    resp = await client.post("/projects", json={"name": ""})
    assert resp.status_code == 422


async def test_create_project_long_name_returns_422(client):
    resp = await client.post("/projects", json={"name": "x" * 256})
    assert resp.status_code == 422
