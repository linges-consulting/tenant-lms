"""
Group Management tests — TC-GRP-01 through TC-GRP-38.

Covers:
  - Group CRUD (create, update, delete, list) — TC-GRP-01 to TC-GRP-19
  - Group Membership (add, remove, view) — TC-GRP-20 to TC-GRP-38
"""
import pytest
import uuid
import bcrypt
from tests.conftest import make_manager_jwt, make_jwt


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hash(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


async def _make_tenant(db, label="T") -> str:
    from app.models.tenant import Tenant
    tid = str(uuid.uuid4())
    db.add(Tenant(id=tid, name=f"{label}-{tid[:6]}", is_active=True,
                  primary_color="#000000", secondary_color="#ffffff"))
    await db.flush()
    return tid


async def _make_user(db, email_prefix, *, active=True, sysadmin=False) -> str:
    from app.models.user import User, UserStatus
    uid = str(uuid.uuid4())
    db.add(User(
        id=uid,
        email=f"{email_prefix}_{uid[:6]}@example.com",
        username=f"u_{uid[:8]}",
        hashed_password=_hash("Pass1!"),
        full_name="Test User",
        is_sysadmin=sysadmin,
        is_active=active,
        status=UserStatus.ACTIVE if active else UserStatus.INACTIVE,
    ))
    await db.flush()
    return uid


async def _make_membership(db, user_id, tenant_id, *, manager=False, creator=False, active=True) -> None:
    from app.models.membership import TenantMembership
    from app.models.user import UserStatus
    db.add(TenantMembership(
        user_id=user_id,
        tenant_id=tenant_id,
        is_active=active,
        is_employee=True,
        is_business_manager=manager,
        is_training_creator=creator,
        status=UserStatus.ACTIVE if active else UserStatus.INACTIVE,
    ))
    await db.flush()


async def _make_group(db, tenant_id, name="Test Group", description=None) -> str:
    from app.models.group import Group
    gid = str(uuid.uuid4())
    db.add(Group(id=gid, tenant_id=tenant_id, name=name, description=description))
    await db.flush()
    return gid


async def _add_member(db, group_id, user_id) -> None:
    from app.models.group import GroupMembership
    db.add(GroupMembership(group_id=group_id, user_id=user_id))
    await db.flush()


def _auth(token, tenant_id):
    return {"Authorization": f"Bearer {token}", "X-Tenant-Id": tenant_id}


# ===========================================================================
# GROUP CRUD — Create
# ===========================================================================

# TC-GRP-01: Manager can create a group
@pytest.mark.asyncio
async def test_manager_can_create_group(client, db_session):
    from app.core.config import settings as app_settings

    tid = await _make_tenant(db_session, "GrpCreate")
    mgr_id = await _make_user(db_session, "mgr_create")
    await _make_membership(db_session, mgr_id, tid, manager=True)
    await db_session.commit()

    token = make_manager_jwt(mgr_id, tid, secret=app_settings.EXTERNAL_JWT_SECRET)
    resp = await client.post(
        "/api/v1/groups",
        json={"name": "My Group"},
        headers=_auth(token, tid),
    )
    assert resp.status_code == 201, f"TC-GRP-01: expected 201, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["name"] == "My Group"


# TC-GRP-02: Group created with optional description
@pytest.mark.asyncio
async def test_create_group_with_description(client, db_session):
    from app.core.config import settings as app_settings

    tid = await _make_tenant(db_session, "GrpDesc")
    mgr_id = await _make_user(db_session, "mgr_desc")
    await _make_membership(db_session, mgr_id, tid, manager=True)
    await db_session.commit()

    token = make_manager_jwt(mgr_id, tid, secret=app_settings.EXTERNAL_JWT_SECRET)
    resp = await client.post(
        "/api/v1/groups",
        json={"name": "Described Group", "description": "Some description"},
        headers=_auth(token, tid),
    )
    assert resp.status_code == 201, f"TC-GRP-02: expected 201, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["description"] == "Some description"


# TC-GRP-03: Group name is required — missing name returns 422
@pytest.mark.asyncio
async def test_create_group_name_required(client, db_session):
    from app.core.config import settings as app_settings

    tid = await _make_tenant(db_session, "GrpNoName")
    mgr_id = await _make_user(db_session, "mgr_noname")
    await _make_membership(db_session, mgr_id, tid, manager=True)
    await db_session.commit()

    token = make_manager_jwt(mgr_id, tid, secret=app_settings.EXTERNAL_JWT_SECRET)
    resp = await client.post(
        "/api/v1/groups",
        json={},
        headers=_auth(token, tid),
    )
    assert resp.status_code == 422, f"TC-GRP-03: expected 422, got {resp.status_code}: {resp.text}"


# TC-GRP-04: Group scoped to manager's active tenant
@pytest.mark.asyncio
async def test_group_scoped_to_active_tenant(client, db_session):
    from app.core.config import settings as app_settings

    tid = await _make_tenant(db_session, "GrpScope")
    mgr_id = await _make_user(db_session, "mgr_scope")
    await _make_membership(db_session, mgr_id, tid, manager=True)
    await db_session.commit()

    token = make_manager_jwt(mgr_id, tid, secret=app_settings.EXTERNAL_JWT_SECRET)
    resp = await client.post(
        "/api/v1/groups",
        json={"name": "Scoped Group"},
        headers=_auth(token, tid),
    )
    assert resp.status_code == 201, f"TC-GRP-04: expected 201, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["tenant_id"] == tid, "Group tenant_id must match the manager's active tenant"


# TC-GRP-05: Non-manager (Base Employee) cannot create a group
@pytest.mark.asyncio
async def test_employee_cannot_create_group(client, db_session):
    from app.core.config import settings as app_settings

    tid = await _make_tenant(db_session, "GrpEmpCreate")
    emp_id = await _make_user(db_session, "emp_grp_create")
    await _make_membership(db_session, emp_id, tid, manager=False)
    await db_session.commit()

    token = make_jwt(emp_id, tid, ["Employee"], secret=app_settings.EXTERNAL_JWT_SECRET)
    resp = await client.post(
        "/api/v1/groups",
        json={"name": "Forbidden Group"},
        headers=_auth(token, tid),
    )
    assert resp.status_code == 403, f"TC-GRP-05: expected 403, got {resp.status_code}: {resp.text}"


# TC-GRP-06: Manager cannot create group in another tenant
@pytest.mark.asyncio
async def test_manager_cannot_create_group_in_other_tenant(client, db_session):
    from app.core.config import settings as app_settings

    tid_a = await _make_tenant(db_session, "GrpTA")
    tid_b = await _make_tenant(db_session, "GrpTB")
    mgr_id = await _make_user(db_session, "mgr_cross_create")
    await _make_membership(db_session, mgr_id, tid_a, manager=True)
    await db_session.commit()

    # Manager's JWT is scoped to Tenant A, but we send Tenant B header
    # The token itself carries tenant_id=tid_a, so tenant_id extracted from JWT = tid_a
    # The endpoint scopes creation to that JWT tenant, so it should not create in Tenant B.
    token = make_manager_jwt(mgr_id, tid_a, secret=app_settings.EXTERNAL_JWT_SECRET)
    resp = await client.post(
        "/api/v1/groups",
        json={"name": "Cross Tenant Group"},
        headers=_auth(token, tid_b),  # Header says B, JWT says A
    )
    # The endpoint uses JWT tenant_id, not header — the group is created in Tenant A, not B.
    # A Tenant B manager check would 403 since mgr is not in Tenant B.
    # Either the group is scoped to A (201) or rejected (403). Either way Tenant B is not polluted.
    if resp.status_code == 201:
        data = resp.json()
        assert data["tenant_id"] == tid_a, "Group must be in JWT tenant (Tenant A), not Tenant B"
    else:
        assert resp.status_code == 403, f"TC-GRP-06: expected 403 or scoped to A, got {resp.status_code}: {resp.text}"


# TC-GRP-07: Duplicate group name within same tenant (document actual behaviour)
@pytest.mark.asyncio
async def test_duplicate_group_name_same_tenant(client, db_session):
    from app.core.config import settings as app_settings

    tid = await _make_tenant(db_session, "GrpDup")
    mgr_id = await _make_user(db_session, "mgr_dup")
    await _make_membership(db_session, mgr_id, tid, manager=True)
    await _make_group(db_session, tid, name="Duplicate Name")
    await db_session.commit()

    token = make_manager_jwt(mgr_id, tid, secret=app_settings.EXTERNAL_JWT_SECRET)
    resp = await client.post(
        "/api/v1/groups",
        json={"name": "Duplicate Name"},
        headers=_auth(token, tid),
    )
    # Spec says 409 or accepted — document actual behaviour
    assert resp.status_code in (201, 409), (
        f"TC-GRP-07: expected 201 or 409 for duplicate name, got {resp.status_code}: {resp.text}"
    )


# ===========================================================================
# GROUP CRUD — Update
# ===========================================================================

# TC-GRP-08: Manager can rename a group
@pytest.mark.asyncio
async def test_manager_can_rename_group(client, db_session):
    from app.core.config import settings as app_settings

    tid = await _make_tenant(db_session, "GrpRename")
    mgr_id = await _make_user(db_session, "mgr_rename")
    await _make_membership(db_session, mgr_id, tid, manager=True)
    gid = await _make_group(db_session, tid, name="Old Name")
    await db_session.commit()

    token = make_manager_jwt(mgr_id, tid, secret=app_settings.EXTERNAL_JWT_SECRET)
    resp = await client.patch(
        f"/api/v1/groups/{gid}",
        json={"name": "New Name"},
        headers=_auth(token, tid),
    )
    assert resp.status_code == 200, f"TC-GRP-08: expected 200, got {resp.status_code}: {resp.text}"
    assert resp.json()["name"] == "New Name"


# TC-GRP-09: Manager can update group description
@pytest.mark.asyncio
async def test_manager_can_update_group_description(client, db_session):
    from app.core.config import settings as app_settings

    tid = await _make_tenant(db_session, "GrpUpdDesc")
    mgr_id = await _make_user(db_session, "mgr_upddesc")
    await _make_membership(db_session, mgr_id, tid, manager=True)
    gid = await _make_group(db_session, tid, name="A Group", description="Old description")
    await db_session.commit()

    token = make_manager_jwt(mgr_id, tid, secret=app_settings.EXTERNAL_JWT_SECRET)
    resp = await client.patch(
        f"/api/v1/groups/{gid}",
        json={"description": "New description"},
        headers=_auth(token, tid),
    )
    assert resp.status_code == 200, f"TC-GRP-09: expected 200, got {resp.status_code}: {resp.text}"
    assert resp.json()["description"] == "New description"


# TC-GRP-10: Manager cannot update group from another tenant
@pytest.mark.asyncio
async def test_manager_cannot_update_other_tenant_group(client, db_session):
    from app.core.config import settings as app_settings

    tid_a = await _make_tenant(db_session, "GrpUpdTA")
    tid_b = await _make_tenant(db_session, "GrpUpdTB")
    mgr_id = await _make_user(db_session, "mgr_upd_cross")
    await _make_membership(db_session, mgr_id, tid_a, manager=True)
    gid_b = await _make_group(db_session, tid_b, name="Tenant B Group")
    await db_session.commit()

    token = make_manager_jwt(mgr_id, tid_a, secret=app_settings.EXTERNAL_JWT_SECRET)
    resp = await client.patch(
        f"/api/v1/groups/{gid_b}",
        json={"name": "Hijacked Name"},
        headers=_auth(token, tid_a),
    )
    # Group is in tenant_b; JWT scoped to tenant_a — should 404 (not found in tenant) or 403
    assert resp.status_code in (403, 404), (
        f"TC-GRP-10: expected 403 or 404, got {resp.status_code}: {resp.text}"
    )


# TC-GRP-11: Non-manager cannot update a group
@pytest.mark.asyncio
async def test_employee_cannot_update_group(client, db_session):
    from app.core.config import settings as app_settings

    tid = await _make_tenant(db_session, "GrpEmpUpd")
    emp_id = await _make_user(db_session, "emp_grp_upd")
    await _make_membership(db_session, emp_id, tid, manager=False)
    gid = await _make_group(db_session, tid, name="Protected Group")
    await db_session.commit()

    token = make_jwt(emp_id, tid, ["Employee"], secret=app_settings.EXTERNAL_JWT_SECRET)
    resp = await client.patch(
        f"/api/v1/groups/{gid}",
        json={"name": "Illegal Name"},
        headers=_auth(token, tid),
    )
    assert resp.status_code == 403, f"TC-GRP-11: expected 403, got {resp.status_code}: {resp.text}"


# ===========================================================================
# GROUP CRUD — Delete
# ===========================================================================

# TC-GRP-12: Manager can delete an empty group
@pytest.mark.asyncio
async def test_manager_can_delete_empty_group(client, db_session):
    from app.core.config import settings as app_settings

    tid = await _make_tenant(db_session, "GrpDelEmpty")
    mgr_id = await _make_user(db_session, "mgr_del_empty")
    await _make_membership(db_session, mgr_id, tid, manager=True)
    gid = await _make_group(db_session, tid, name="Empty Group")
    await db_session.commit()

    token = make_manager_jwt(mgr_id, tid, secret=app_settings.EXTERNAL_JWT_SECRET)
    resp = await client.delete(
        f"/api/v1/groups/{gid}",
        headers=_auth(token, tid),
    )
    assert resp.status_code in (200, 204), f"TC-GRP-12: expected 200/204, got {resp.status_code}: {resp.text}"


# TC-GRP-13: Manager can delete a group that has members
@pytest.mark.asyncio
async def test_manager_can_delete_group_with_members(client, db_session):
    from app.core.config import settings as app_settings

    tid = await _make_tenant(db_session, "GrpDelMem")
    mgr_id = await _make_user(db_session, "mgr_del_mem")
    emp_id = await _make_user(db_session, "emp_del_mem")
    await _make_membership(db_session, mgr_id, tid, manager=True)
    await _make_membership(db_session, emp_id, tid)
    gid = await _make_group(db_session, tid, name="Group With Members")
    await _add_member(db_session, gid, emp_id)
    await db_session.commit()

    token = make_manager_jwt(mgr_id, tid, secret=app_settings.EXTERNAL_JWT_SECRET)
    resp = await client.delete(
        f"/api/v1/groups/{gid}",
        headers=_auth(token, tid),
    )
    assert resp.status_code in (200, 204), f"TC-GRP-13: expected 200/204, got {resp.status_code}: {resp.text}"


# TC-GRP-14: Deleting a group does not delete its members (users still exist)
@pytest.mark.asyncio
async def test_delete_group_does_not_delete_members(client, db_session):
    from app.core.config import settings as app_settings
    from app.models.user import User
    from sqlalchemy import select

    tid = await _make_tenant(db_session, "GrpDelNoUsr")
    mgr_id = await _make_user(db_session, "mgr_del_nousr")
    emp_id = await _make_user(db_session, "emp_del_nousr")
    await _make_membership(db_session, mgr_id, tid, manager=True)
    await _make_membership(db_session, emp_id, tid)
    gid = await _make_group(db_session, tid, name="Group To Delete")
    await _add_member(db_session, gid, emp_id)
    await db_session.commit()

    token = make_manager_jwt(mgr_id, tid, secret=app_settings.EXTERNAL_JWT_SECRET)
    del_resp = await client.delete(f"/api/v1/groups/{gid}", headers=_auth(token, tid))
    assert del_resp.status_code in (200, 204), f"TC-GRP-14 setup: delete failed: {del_resp.text}"

    # User should still exist in DB
    result = await db_session.execute(select(User).where(User.id == emp_id))
    user = result.scalar_one_or_none()
    assert user is not None, "TC-GRP-14: User was deleted when group was deleted — must not happen"


# TC-GRP-16: Manager cannot delete group from another tenant
@pytest.mark.asyncio
async def test_manager_cannot_delete_other_tenant_group(client, db_session):
    from app.core.config import settings as app_settings

    tid_a = await _make_tenant(db_session, "GrpDelTA")
    tid_b = await _make_tenant(db_session, "GrpDelTB")
    mgr_id = await _make_user(db_session, "mgr_del_cross")
    await _make_membership(db_session, mgr_id, tid_a, manager=True)
    gid_b = await _make_group(db_session, tid_b, name="Tenant B Group Del")
    await db_session.commit()

    token = make_manager_jwt(mgr_id, tid_a, secret=app_settings.EXTERNAL_JWT_SECRET)
    resp = await client.delete(f"/api/v1/groups/{gid_b}", headers=_auth(token, tid_a))
    assert resp.status_code in (403, 404), (
        f"TC-GRP-16: expected 403/404, got {resp.status_code}: {resp.text}"
    )


# TC-GRP-17: Non-manager cannot delete a group
@pytest.mark.asyncio
async def test_employee_cannot_delete_group(client, db_session):
    from app.core.config import settings as app_settings

    tid = await _make_tenant(db_session, "GrpEmpDel")
    emp_id = await _make_user(db_session, "emp_grp_del")
    await _make_membership(db_session, emp_id, tid, manager=False)
    gid = await _make_group(db_session, tid, name="Protected Delete Group")
    await db_session.commit()

    token = make_jwt(emp_id, tid, ["Employee"], secret=app_settings.EXTERNAL_JWT_SECRET)
    resp = await client.delete(f"/api/v1/groups/{gid}", headers=_auth(token, tid))
    assert resp.status_code == 403, f"TC-GRP-17: expected 403, got {resp.status_code}: {resp.text}"


# TC-GRP-18: Bulk delete removes all selected groups
@pytest.mark.asyncio
async def test_bulk_delete_removes_all_selected_groups(client, db_session):
    from app.core.config import settings as app_settings
    from app.models.group import Group
    from sqlalchemy import select

    tid = await _make_tenant(db_session, "GrpBulkDel")
    mgr_id = await _make_user(db_session, "mgr_bulk_del")
    await _make_membership(db_session, mgr_id, tid, manager=True)
    gid1 = await _make_group(db_session, tid, name="Bulk1")
    gid2 = await _make_group(db_session, tid, name="Bulk2")
    gid3 = await _make_group(db_session, tid, name="Bulk3")
    await db_session.commit()

    token = make_manager_jwt(mgr_id, tid, secret=app_settings.EXTERNAL_JWT_SECRET)
    # Delete each group individually (no bulk endpoint documented separately — use single DELETE)
    for gid in [gid1, gid2, gid3]:
        resp = await client.delete(f"/api/v1/groups/{gid}", headers=_auth(token, tid))
        assert resp.status_code in (200, 204), f"TC-GRP-18: delete {gid} failed: {resp.text}"

    # Verify all three are gone
    result = await db_session.execute(
        select(Group).where(Group.id.in_([gid1, gid2, gid3]))
    )
    remaining = result.scalars().all()
    assert len(remaining) == 0, f"TC-GRP-18: expected 0 remaining groups, got {len(remaining)}"


# TC-GRP-19: Deleted group no longer appears in group list
@pytest.mark.asyncio
async def test_deleted_group_absent_from_list(client, db_session):
    from app.core.config import settings as app_settings

    tid = await _make_tenant(db_session, "GrpDelList")
    mgr_id = await _make_user(db_session, "mgr_del_list")
    await _make_membership(db_session, mgr_id, tid, manager=True)
    gid = await _make_group(db_session, tid, name="Soon Deleted")
    await db_session.commit()

    token = make_manager_jwt(mgr_id, tid, secret=app_settings.EXTERNAL_JWT_SECRET)
    del_resp = await client.delete(f"/api/v1/groups/{gid}", headers=_auth(token, tid))
    assert del_resp.status_code in (200, 204), f"TC-GRP-19 setup failed: {del_resp.text}"

    list_resp = await client.get("/api/v1/groups", headers=_auth(token, tid))
    assert list_resp.status_code == 200
    ids = [g["id"] for g in list_resp.json()]
    assert gid not in ids, "TC-GRP-19: Deleted group still appears in group list"


# ===========================================================================
# GROUP MEMBERSHIP — Adding Members
# ===========================================================================

# TC-GRP-20: Manager can add one user to a group
@pytest.mark.asyncio
async def test_manager_can_add_one_member(client, db_session):
    from app.core.config import settings as app_settings

    tid = await _make_tenant(db_session, "GrpAddOne")
    mgr_id = await _make_user(db_session, "mgr_add_one")
    emp_id = await _make_user(db_session, "emp_add_one")
    await _make_membership(db_session, mgr_id, tid, manager=True)
    await _make_membership(db_session, emp_id, tid)
    gid = await _make_group(db_session, tid, name="Add One Group")
    await db_session.commit()

    token = make_manager_jwt(mgr_id, tid, secret=app_settings.EXTERNAL_JWT_SECRET)
    resp = await client.post(
        f"/api/v1/groups/{gid}/members",
        json={"user_ids": [emp_id]},
        headers=_auth(token, tid),
    )
    assert resp.status_code in (200, 201), f"TC-GRP-20: expected 200/201, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data.get("added", 0) == 1, f"TC-GRP-20: expected 1 added, got {data}"


# TC-GRP-21: Manager can add multiple users in one call
@pytest.mark.asyncio
async def test_manager_can_add_multiple_members(client, db_session):
    from app.core.config import settings as app_settings

    tid = await _make_tenant(db_session, "GrpAddMulti")
    mgr_id = await _make_user(db_session, "mgr_add_multi")
    await _make_membership(db_session, mgr_id, tid, manager=True)
    user_ids = []
    for i in range(5):
        uid = await _make_user(db_session, f"emp_multi_{i}")
        await _make_membership(db_session, uid, tid)
        user_ids.append(uid)
    gid = await _make_group(db_session, tid, name="Multi Add Group")
    await db_session.commit()

    token = make_manager_jwt(mgr_id, tid, secret=app_settings.EXTERNAL_JWT_SECRET)
    resp = await client.post(
        f"/api/v1/groups/{gid}/members",
        json={"user_ids": user_ids},
        headers=_auth(token, tid),
    )
    assert resp.status_code in (200, 201), f"TC-GRP-21: expected 200/201, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data.get("added", 0) == 5, f"TC-GRP-21: expected 5 added, got {data}"


# TC-GRP-22: Adding user already in group is handled gracefully (idempotent)
@pytest.mark.asyncio
async def test_add_already_existing_member_is_idempotent(client, db_session):
    from app.core.config import settings as app_settings

    tid = await _make_tenant(db_session, "GrpAddDup")
    mgr_id = await _make_user(db_session, "mgr_add_dup")
    emp_id = await _make_user(db_session, "emp_add_dup")
    await _make_membership(db_session, mgr_id, tid, manager=True)
    await _make_membership(db_session, emp_id, tid)
    gid = await _make_group(db_session, tid, name="Idempotent Group")
    await _add_member(db_session, gid, emp_id)
    await db_session.commit()

    token = make_manager_jwt(mgr_id, tid, secret=app_settings.EXTERNAL_JWT_SECRET)
    resp = await client.post(
        f"/api/v1/groups/{gid}/members",
        json={"user_ids": [emp_id]},
        headers=_auth(token, tid),
    )
    assert resp.status_code in (200, 201), f"TC-GRP-22: expected 200/201 (idempotent), got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data.get("added", 0) == 0, f"TC-GRP-22: expected 0 added (already member), got {data}"


# TC-GRP-25: Non-manager cannot add members
@pytest.mark.asyncio
async def test_employee_cannot_add_members(client, db_session):
    from app.core.config import settings as app_settings

    tid = await _make_tenant(db_session, "GrpEmpAddMem")
    emp_id = await _make_user(db_session, "emp_add_mem")
    other_id = await _make_user(db_session, "other_add_mem")
    await _make_membership(db_session, emp_id, tid, manager=False)
    await _make_membership(db_session, other_id, tid)
    gid = await _make_group(db_session, tid, name="Protected Member Group")
    await db_session.commit()

    token = make_jwt(emp_id, tid, ["Employee"], secret=app_settings.EXTERNAL_JWT_SECRET)
    resp = await client.post(
        f"/api/v1/groups/{gid}/members",
        json={"user_ids": [other_id]},
        headers=_auth(token, tid),
    )
    assert resp.status_code == 403, f"TC-GRP-25: expected 403, got {resp.status_code}: {resp.text}"


# TC-GRP-26: Manager cannot add members to group in another tenant
@pytest.mark.asyncio
async def test_manager_cannot_add_members_to_other_tenant_group(client, db_session):
    from app.core.config import settings as app_settings

    tid_a = await _make_tenant(db_session, "GrpAddMemTA")
    tid_b = await _make_tenant(db_session, "GrpAddMemTB")
    mgr_id = await _make_user(db_session, "mgr_add_cross")
    emp_b_id = await _make_user(db_session, "emp_add_cross")
    await _make_membership(db_session, mgr_id, tid_a, manager=True)
    await _make_membership(db_session, emp_b_id, tid_b)
    gid_b = await _make_group(db_session, tid_b, name="Tenant B Only Group")
    await db_session.commit()

    token = make_manager_jwt(mgr_id, tid_a, secret=app_settings.EXTERNAL_JWT_SECRET)
    resp = await client.post(
        f"/api/v1/groups/{gid_b}/members",
        json={"user_ids": [emp_b_id]},
        headers=_auth(token, tid_a),
    )
    assert resp.status_code in (403, 404), (
        f"TC-GRP-26: expected 403/404, got {resp.status_code}: {resp.text}"
    )


# ===========================================================================
# GROUP MEMBERSHIP — Removing Members
# ===========================================================================

# TC-GRP-27: Manager can remove a member from a group
@pytest.mark.asyncio
async def test_manager_can_remove_member(client, db_session):
    from app.core.config import settings as app_settings

    tid = await _make_tenant(db_session, "GrpRemMem")
    mgr_id = await _make_user(db_session, "mgr_rem_mem")
    emp_id = await _make_user(db_session, "emp_rem_mem")
    await _make_membership(db_session, mgr_id, tid, manager=True)
    await _make_membership(db_session, emp_id, tid)
    gid = await _make_group(db_session, tid, name="Remove Member Group")
    await _add_member(db_session, gid, emp_id)
    await db_session.commit()

    token = make_manager_jwt(mgr_id, tid, secret=app_settings.EXTERNAL_JWT_SECRET)
    resp = await client.delete(
        f"/api/v1/groups/{gid}/members/{emp_id}",
        headers=_auth(token, tid),
    )
    assert resp.status_code in (200, 204), f"TC-GRP-27: expected 200/204, got {resp.status_code}: {resp.text}"


# TC-GRP-28: Removing member does not delete the user account
@pytest.mark.asyncio
async def test_remove_member_does_not_delete_user(client, db_session):
    from app.core.config import settings as app_settings
    from app.models.user import User
    from sqlalchemy import select

    tid = await _make_tenant(db_session, "GrpRemNoUsr")
    mgr_id = await _make_user(db_session, "mgr_rem_nousr")
    emp_id = await _make_user(db_session, "emp_rem_nousr")
    await _make_membership(db_session, mgr_id, tid, manager=True)
    await _make_membership(db_session, emp_id, tid)
    gid = await _make_group(db_session, tid, name="Remove No Delete Group")
    await _add_member(db_session, gid, emp_id)
    await db_session.commit()

    token = make_manager_jwt(mgr_id, tid, secret=app_settings.EXTERNAL_JWT_SECRET)
    resp = await client.delete(f"/api/v1/groups/{gid}/members/{emp_id}", headers=_auth(token, tid))
    assert resp.status_code in (200, 204), f"TC-GRP-28 setup: {resp.text}"

    result = await db_session.execute(select(User).where(User.id == emp_id))
    user = result.scalar_one_or_none()
    assert user is not None, "TC-GRP-28: User was deleted when removed from group — must not happen"


# TC-GRP-30: Removing non-existent member returns 404
@pytest.mark.asyncio
async def test_remove_nonexistent_member_returns_404(client, db_session):
    from app.core.config import settings as app_settings

    tid = await _make_tenant(db_session, "GrpRemNone")
    mgr_id = await _make_user(db_session, "mgr_rem_none")
    await _make_membership(db_session, mgr_id, tid, manager=True)
    gid = await _make_group(db_session, tid, name="Empty For Remove")
    await db_session.commit()

    nonexistent_user_id = str(uuid.uuid4())
    token = make_manager_jwt(mgr_id, tid, secret=app_settings.EXTERNAL_JWT_SECRET)
    resp = await client.delete(
        f"/api/v1/groups/{gid}/members/{nonexistent_user_id}",
        headers=_auth(token, tid),
    )
    assert resp.status_code == 404, f"TC-GRP-30: expected 404, got {resp.status_code}: {resp.text}"


# TC-GRP-31: Non-manager cannot remove members
@pytest.mark.asyncio
async def test_employee_cannot_remove_members(client, db_session):
    from app.core.config import settings as app_settings

    tid = await _make_tenant(db_session, "GrpEmpRemMem")
    emp_id = await _make_user(db_session, "emp_grp_rem")
    other_id = await _make_user(db_session, "other_grp_rem")
    await _make_membership(db_session, emp_id, tid, manager=False)
    await _make_membership(db_session, other_id, tid)
    gid = await _make_group(db_session, tid, name="Protected Remove Group")
    await _add_member(db_session, gid, other_id)
    await db_session.commit()

    token = make_jwt(emp_id, tid, ["Employee"], secret=app_settings.EXTERNAL_JWT_SECRET)
    resp = await client.delete(
        f"/api/v1/groups/{gid}/members/{other_id}",
        headers=_auth(token, tid),
    )
    assert resp.status_code == 403, f"TC-GRP-31: expected 403, got {resp.status_code}: {resp.text}"


# TC-GRP-32: Manager cannot remove members from another tenant's group
@pytest.mark.asyncio
async def test_manager_cannot_remove_members_from_other_tenant_group(client, db_session):
    from app.core.config import settings as app_settings

    tid_a = await _make_tenant(db_session, "GrpRemTA")
    tid_b = await _make_tenant(db_session, "GrpRemTB")
    mgr_id = await _make_user(db_session, "mgr_rem_cross")
    emp_b_id = await _make_user(db_session, "emp_rem_cross")
    await _make_membership(db_session, mgr_id, tid_a, manager=True)
    await _make_membership(db_session, emp_b_id, tid_b)
    gid_b = await _make_group(db_session, tid_b, name="Tenant B Rem Group")
    await _add_member(db_session, gid_b, emp_b_id)
    await db_session.commit()

    token = make_manager_jwt(mgr_id, tid_a, secret=app_settings.EXTERNAL_JWT_SECRET)
    resp = await client.delete(
        f"/api/v1/groups/{gid_b}/members/{emp_b_id}",
        headers=_auth(token, tid_a),
    )
    assert resp.status_code in (403, 404), (
        f"TC-GRP-32: expected 403/404, got {resp.status_code}: {resp.text}"
    )


# ===========================================================================
# GROUP MEMBERSHIP — Viewing Members
# ===========================================================================

# TC-GRP-33: Manager can list members of a group
@pytest.mark.asyncio
async def test_manager_can_list_group_members(client, db_session):
    from app.core.config import settings as app_settings

    tid = await _make_tenant(db_session, "GrpListMem")
    mgr_id = await _make_user(db_session, "mgr_list_mem")
    await _make_membership(db_session, mgr_id, tid, manager=True)
    gid = await _make_group(db_session, tid, name="List Members Group")

    emp_ids = []
    for i in range(3):
        uid = await _make_user(db_session, f"emp_list_mem_{i}")
        await _make_membership(db_session, uid, tid)
        await _add_member(db_session, gid, uid)
        emp_ids.append(uid)
    await db_session.commit()

    token = make_manager_jwt(mgr_id, tid, secret=app_settings.EXTERNAL_JWT_SECRET)
    resp = await client.get(f"/api/v1/groups/{gid}/members", headers=_auth(token, tid))
    assert resp.status_code == 200, f"TC-GRP-33: expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert len(data) == 3, f"TC-GRP-33: expected 3 members, got {len(data)}"
    # Verify expected fields present
    for member in data:
        assert "user_id" in member, "TC-GRP-33: member missing user_id"
        assert "added_at" in member, "TC-GRP-33: member missing added_at"


# TC-GRP-34: Empty group returns empty member list
@pytest.mark.asyncio
async def test_empty_group_returns_empty_member_list(client, db_session):
    from app.core.config import settings as app_settings

    tid = await _make_tenant(db_session, "GrpEmptyMem")
    mgr_id = await _make_user(db_session, "mgr_empty_mem")
    await _make_membership(db_session, mgr_id, tid, manager=True)
    gid = await _make_group(db_session, tid, name="Empty Members Group")
    await db_session.commit()

    token = make_manager_jwt(mgr_id, tid, secret=app_settings.EXTERNAL_JWT_SECRET)
    resp = await client.get(f"/api/v1/groups/{gid}/members", headers=_auth(token, tid))
    assert resp.status_code == 200, f"TC-GRP-34: expected 200, got {resp.status_code}: {resp.text}"
    assert resp.json() == [], f"TC-GRP-34: expected empty list, got {resp.json()}"


# TC-GRP-35: member_count in group listing is accurate
@pytest.mark.asyncio
async def test_member_count_in_group_list_is_accurate(client, db_session):
    from app.core.config import settings as app_settings

    tid = await _make_tenant(db_session, "GrpCntList")
    mgr_id = await _make_user(db_session, "mgr_cnt_list")
    await _make_membership(db_session, mgr_id, tid, manager=True)
    gid = await _make_group(db_session, tid, name="Count Group")

    for i in range(3):
        uid = await _make_user(db_session, f"emp_cnt_{i}")
        await _make_membership(db_session, uid, tid)
        await _add_member(db_session, gid, uid)
    await db_session.commit()

    token = make_manager_jwt(mgr_id, tid, secret=app_settings.EXTERNAL_JWT_SECRET)
    resp = await client.get("/api/v1/groups", headers=_auth(token, tid))
    assert resp.status_code == 200, f"TC-GRP-35: expected 200, got {resp.status_code}: {resp.text}"
    groups = resp.json()
    matching = [g for g in groups if g["id"] == gid]
    assert len(matching) == 1, "TC-GRP-35: target group not found in list"
    assert matching[0]["member_count"] == 3, (
        f"TC-GRP-35: expected member_count=3, got {matching[0]['member_count']}"
    )


# TC-GRP-36: Member count updates after add/remove operations
@pytest.mark.asyncio
async def test_member_count_updates_after_add_and_remove(client, db_session):
    from app.core.config import settings as app_settings

    tid = await _make_tenant(db_session, "GrpCntUpd")
    mgr_id = await _make_user(db_session, "mgr_cnt_upd")
    await _make_membership(db_session, mgr_id, tid, manager=True)
    gid = await _make_group(db_session, tid, name="Count Update Group")

    # Start with 2 members
    uid1 = await _make_user(db_session, "emp_cnt_upd_1")
    uid2 = await _make_user(db_session, "emp_cnt_upd_2")
    uid3 = await _make_user(db_session, "emp_cnt_upd_3")
    for uid in [uid1, uid2]:
        await _make_membership(db_session, uid, tid)
        await _add_member(db_session, gid, uid)
    await _make_membership(db_session, uid3, tid)
    await db_session.commit()

    token = make_manager_jwt(mgr_id, tid, secret=app_settings.EXTERNAL_JWT_SECRET)

    # Add uid3 -> count should be 3
    add_resp = await client.post(
        f"/api/v1/groups/{gid}/members",
        json={"user_ids": [uid3]},
        headers=_auth(token, tid),
    )
    assert add_resp.status_code in (200, 201), f"TC-GRP-36 add failed: {add_resp.text}"

    # Remove uid1 -> count should be back to 2
    rem_resp = await client.delete(f"/api/v1/groups/{gid}/members/{uid1}", headers=_auth(token, tid))
    assert rem_resp.status_code in (200, 204), f"TC-GRP-36 remove failed: {rem_resp.text}"

    # Check count = 2
    list_resp = await client.get("/api/v1/groups", headers=_auth(token, tid))
    assert list_resp.status_code == 200
    groups = list_resp.json()
    matching = [g for g in groups if g["id"] == gid]
    assert len(matching) == 1
    assert matching[0]["member_count"] == 2, (
        f"TC-GRP-36: expected member_count=2, got {matching[0]['member_count']}"
    )


# TC-GRP-37: Non-manager cannot list group members
@pytest.mark.asyncio
async def test_employee_cannot_list_group_members(client, db_session):
    from app.core.config import settings as app_settings

    tid = await _make_tenant(db_session, "GrpEmpListMem")
    emp_id = await _make_user(db_session, "emp_list_mem_deny")
    await _make_membership(db_session, emp_id, tid, manager=False)
    gid = await _make_group(db_session, tid, name="Protected Members List")
    await db_session.commit()

    token = make_jwt(emp_id, tid, ["Employee"], secret=app_settings.EXTERNAL_JWT_SECRET)
    resp = await client.get(f"/api/v1/groups/{gid}/members", headers=_auth(token, tid))
    assert resp.status_code == 403, f"TC-GRP-37: expected 403, got {resp.status_code}: {resp.text}"


# TC-GRP-38: Manager cannot list members of group in another tenant
@pytest.mark.asyncio
async def test_manager_cannot_list_members_of_other_tenant_group(client, db_session):
    from app.core.config import settings as app_settings

    tid_a = await _make_tenant(db_session, "GrpListMemTA")
    tid_b = await _make_tenant(db_session, "GrpListMemTB")
    mgr_id = await _make_user(db_session, "mgr_list_cross")
    await _make_membership(db_session, mgr_id, tid_a, manager=True)
    gid_b = await _make_group(db_session, tid_b, name="Tenant B Members Group")
    await db_session.commit()

    token = make_manager_jwt(mgr_id, tid_a, secret=app_settings.EXTERNAL_JWT_SECRET)
    resp = await client.get(f"/api/v1/groups/{gid_b}/members", headers=_auth(token, tid_a))
    assert resp.status_code in (403, 404), (
        f"TC-GRP-38: expected 403/404, got {resp.status_code}: {resp.text}"
    )
