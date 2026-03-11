from httpx import ASGITransport, AsyncClient

from app.main import app as fastapi_app


async def test_no_auth_header_returns_422(client):
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as no_auth:
        resp = await no_auth.get("/projects")
        assert resp.status_code == 422  # missing required header


async def test_invalid_token_returns_401(client):
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": "Bearer wrong-token"},
    ) as bad_auth:
        resp = await bad_auth.get("/projects")
        assert resp.status_code == 401


async def test_valid_admin_token_succeeds(client):
    resp = await client.get("/projects")
    assert resp.status_code == 200


async def test_sdk_auth_valid_api_key(client, db_session):
    """Valid API key via X-Api-Key resolves to the correct project."""
    from app.services.project_service import get_project_by_api_key

    create_resp = await client.post("/projects", json={"name": "sdk-test"})
    api_key = create_resp.json()["api_key"]
    project_id = create_resp.json()["id"]
    project = await get_project_by_api_key(db_session, api_key)
    assert project is not None
    assert str(project.id) == project_id


async def test_sdk_auth_invalid_api_key(client, db_session):
    from app.services.project_service import get_project_by_api_key

    project = await get_project_by_api_key(db_session, "totally-invalid-key")
    assert project is None
