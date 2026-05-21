"""
Category CRUD endpoint tests.

Auth pattern:
  Override get_current_user AND get_current_tenant_id via app.dependency_overrides.
  Bearer tokens have no effect in core-service unit tests.
"""

import pytest
import uuid

from app.main import app
from app.api.deps import get_current_user, get_current_tenant_id
from tests.conftest import override_current_user, make_user_auth


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_manager(tenant_id: str):
    """Return a UserAuth object for a Business Manager in the given tenant."""
    return make_user_auth(
        user_id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        roles=["Business Manager"],
    )


def _make_creator(tenant_id: str):
    """Return a UserAuth object for a Training Creator in the given tenant."""
    return make_user_auth(
        user_id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        roles=["Training Creator"],
    )


def _set_user(user):
    """Install dependency overrides for current user and tenant_id."""
    tenant_id = user.tenant_id
    app.dependency_overrides[get_current_user] = override_current_user(user)

    async def _tenant_id():
        return tenant_id

    app.dependency_overrides[get_current_tenant_id] = _tenant_id


def _clear_overrides():
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_current_tenant_id, None)


# ---------------------------------------------------------------------------
# GET /api/v1/categories — list categories (Creator or Manager)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_categories_returns_active_only(client, db_session):
    """GET /categories returns only is_active=True categories for the tenant."""
    tenant_id = str(uuid.uuid4())
    manager = _make_manager(tenant_id)
    _set_user(manager)
    try:
        # Create an active category
        resp = await client.post(
            "/api/v1/categories/",
            json={"name": "Safety", "is_active": True},
        )
        assert resp.status_code == 201, resp.text

        # Create a second category then soft-delete it
        resp2 = await client.post(
            "/api/v1/categories/",
            json={"name": "Inactive Cat", "is_active": True},
        )
        assert resp2.status_code == 201, resp2.text
        cat_id = resp2.json()["id"]

        del_resp = await client.delete(f"/api/v1/categories/{cat_id}")
        assert del_resp.status_code == 204, del_resp.text

        # List — should only return the active one
        list_resp = await client.get("/api/v1/categories/")
        assert list_resp.status_code == 200, list_resp.text
        names = [c["name"] for c in list_resp.json()]
        assert "Safety" in names
        assert "Inactive Cat" not in names
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_list_categories_tenant_isolation(client, db_session):
    """GET /categories must not return categories belonging to another tenant."""
    tenant_a = str(uuid.uuid4())
    tenant_b = str(uuid.uuid4())

    # Tenant A creates a category
    _set_user(_make_manager(tenant_a))
    resp = await client.post("/api/v1/categories/", json={"name": "Tenant A Cat"})
    assert resp.status_code == 201, resp.text
    _clear_overrides()

    # Tenant B lists — should not see Tenant A's category
    _set_user(_make_manager(tenant_b))
    list_resp = await client.get("/api/v1/categories/")
    assert list_resp.status_code == 200, list_resp.text
    names = [c["name"] for c in list_resp.json()]
    assert "Tenant A Cat" not in names
    _clear_overrides()


@pytest.mark.asyncio
async def test_creator_can_list_categories(client, db_session):
    """Training Creator (non-Manager) can GET /categories."""
    tenant_id = str(uuid.uuid4())

    # Manager creates a category
    _set_user(_make_manager(tenant_id))
    resp = await client.post("/api/v1/categories/", json={"name": "HR"})
    assert resp.status_code == 201, resp.text
    _clear_overrides()

    # Creator lists
    _set_user(_make_creator(tenant_id))
    list_resp = await client.get("/api/v1/categories/")
    assert list_resp.status_code == 200, list_resp.text
    names = [c["name"] for c in list_resp.json()]
    assert "HR" in names
    _clear_overrides()


# ---------------------------------------------------------------------------
# POST /api/v1/categories — create category (Manager only)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_category_success(client, db_session):
    """Manager can create a category; response includes id, tenant_id, name, is_active."""
    tenant_id = str(uuid.uuid4())
    _set_user(_make_manager(tenant_id))
    try:
        resp = await client.post(
            "/api/v1/categories/",
            json={"name": "Compliance"},
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["name"] == "Compliance"
        assert data["is_active"] is True
        assert data["tenant_id"] == tenant_id
        assert "id" in data
        assert "created_at" in data
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_create_category_duplicate_name_returns_409(client, db_session):
    """Creating a second active category with the same name in the same tenant returns 409."""
    tenant_id = str(uuid.uuid4())
    _set_user(_make_manager(tenant_id))
    try:
        resp1 = await client.post("/api/v1/categories/", json={"name": "Safety"})
        assert resp1.status_code == 201, resp1.text

        resp2 = await client.post("/api/v1/categories/", json={"name": "Safety"})
        assert resp2.status_code == 409, resp2.text
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_creator_cannot_create_category(client, db_session):
    """Training Creator (non-Manager) gets 403 when trying to POST /categories."""
    tenant_id = str(uuid.uuid4())
    _set_user(_make_creator(tenant_id))
    try:
        resp = await client.post("/api/v1/categories/", json={"name": "Security"})
        assert resp.status_code == 403, resp.text
    finally:
        _clear_overrides()


# ---------------------------------------------------------------------------
# PUT /api/v1/categories/{id} — update category (Manager only)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_category_name(client, db_session):
    """Manager can update category name."""
    tenant_id = str(uuid.uuid4())
    _set_user(_make_manager(tenant_id))
    try:
        # Create
        create_resp = await client.post("/api/v1/categories/", json={"name": "OldName"})
        assert create_resp.status_code == 201, create_resp.text
        cat_id = create_resp.json()["id"]

        # Update
        update_resp = await client.put(
            f"/api/v1/categories/{cat_id}",
            json={"name": "NewName"},
        )
        assert update_resp.status_code == 200, update_resp.text
        assert update_resp.json()["name"] == "NewName"
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_update_category_not_found(client, db_session):
    """Updating a non-existent category returns 404."""
    tenant_id = str(uuid.uuid4())
    _set_user(_make_manager(tenant_id))
    try:
        resp = await client.put(
            f"/api/v1/categories/{uuid.uuid4()}",
            json={"name": "Anything"},
        )
        assert resp.status_code == 404, resp.text
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_update_category_cross_tenant_blocked(client, db_session):
    """Manager in tenant B cannot update a category owned by tenant A."""
    tenant_a = str(uuid.uuid4())
    tenant_b = str(uuid.uuid4())

    # Tenant A creates a category
    _set_user(_make_manager(tenant_a))
    resp = await client.post("/api/v1/categories/", json={"name": "A Cat"})
    assert resp.status_code == 201, resp.text
    cat_id = resp.json()["id"]
    _clear_overrides()

    # Tenant B tries to update it — should get 404 (not 200)
    _set_user(_make_manager(tenant_b))
    resp2 = await client.put(f"/api/v1/categories/{cat_id}", json={"name": "Hijacked"})
    assert resp2.status_code == 404, resp2.text
    _clear_overrides()


# ---------------------------------------------------------------------------
# DELETE /api/v1/categories/{id} — soft-delete (Manager only)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_category_soft_deletes(client, db_session):
    """DELETE sets is_active=False; the category no longer appears in list."""
    tenant_id = str(uuid.uuid4())
    _set_user(_make_manager(tenant_id))
    try:
        create_resp = await client.post("/api/v1/categories/", json={"name": "ToDelete"})
        assert create_resp.status_code == 201, create_resp.text
        cat_id = create_resp.json()["id"]

        del_resp = await client.delete(f"/api/v1/categories/{cat_id}")
        assert del_resp.status_code == 204, del_resp.text

        list_resp = await client.get("/api/v1/categories/")
        names = [c["name"] for c in list_resp.json()]
        assert "ToDelete" not in names
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_delete_category_not_found(client, db_session):
    """Deleting a non-existent category returns 404."""
    tenant_id = str(uuid.uuid4())
    _set_user(_make_manager(tenant_id))
    try:
        resp = await client.delete(f"/api/v1/categories/{uuid.uuid4()}")
        assert resp.status_code == 404, resp.text
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_creator_cannot_delete_category(client, db_session):
    """Training Creator gets 403 when trying to DELETE /categories/{id}."""
    tenant_id = str(uuid.uuid4())

    # Manager creates
    _set_user(_make_manager(tenant_id))
    resp = await client.post("/api/v1/categories/", json={"name": "SecureZone"})
    assert resp.status_code == 201, resp.text
    cat_id = resp.json()["id"]
    _clear_overrides()

    # Creator tries to delete
    _set_user(_make_creator(tenant_id))
    del_resp = await client.delete(f"/api/v1/categories/{cat_id}")
    assert del_resp.status_code == 403, del_resp.text
    _clear_overrides()


@pytest.mark.asyncio
async def test_deleted_duplicate_name_can_be_recreated(client, db_session):
    """After soft-deleting a category, a new one with the same name can be created."""
    tenant_id = str(uuid.uuid4())
    _set_user(_make_manager(tenant_id))
    try:
        resp1 = await client.post("/api/v1/categories/", json={"name": "Recycled"})
        assert resp1.status_code == 201, resp1.text
        cat_id = resp1.json()["id"]

        del_resp = await client.delete(f"/api/v1/categories/{cat_id}")
        assert del_resp.status_code == 204, del_resp.text

        resp2 = await client.post("/api/v1/categories/", json={"name": "Recycled"})
        assert resp2.status_code == 201, resp2.text
    finally:
        _clear_overrides()
