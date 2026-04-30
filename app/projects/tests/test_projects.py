async def test_create_project_returns_expected_fields(client):
    resp = await client.post("/projects", json={"name": "my-app"})
    assert resp.status_code == 201
    data = resp.json()
    assert "id" in data
    assert "name" in data
    assert "created_at" in data


async def test_list_projects_returns_all(client):
    await client.post("/projects", json={"name": "p1"})
    await client.post("/projects", json={"name": "p2"})
    resp = await client.get("/projects")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


async def test_create_project_empty_name_returns_422(client):
    resp = await client.post("/projects", json={"name": ""})
    assert resp.status_code == 422


async def test_create_project_long_name_returns_422(client):
    resp = await client.post("/projects", json={"name": "x" * 256})
    assert resp.status_code == 422
