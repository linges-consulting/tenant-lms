"""
Certificate template permission tests — Phase 3 Task 3.

BR-701: Certificate template CRUD is SysAdmin-only.
Business Managers and other non-SysAdmin roles must receive 403 on
template create / update / delete endpoints.

Auth pattern:
  Override get_current_user AND get_current_tenant_id via
  app.dependency_overrides — Bearer tokens have no effect in core-service
  unit tests (auth-service call is bypassed).
"""

import pytest
import uuid
from datetime import datetime, timezone

from app.main import app
from app.api.deps import get_current_user, get_current_tenant_id
from tests.conftest import override_current_user, make_user_auth


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_TEMPLATE_PAYLOAD = {
    "name": "Default Certificate",
    "html_content": "<html><body><p>Certificate for {{user_name}}</p></body></html>",
    "is_default": False,
}


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
# T-CO-CERT-01 (BR-701): Business Manager cannot create a certificate template
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_business_manager_cannot_create_template(client, db_session):
    """
    BR-701: Certificate template creation is SysAdmin-only.
    A Business Manager must receive 403 Forbidden.
    """
    tenant_id = str(uuid.uuid4())
    manager = make_user_auth(
        user_id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        roles=["Business Manager"],
    )
    _set_user(manager)
    try:
        resp = await client.post("/api/v1/certificates/templates", json=SAMPLE_TEMPLATE_PAYLOAD)
        assert resp.status_code == 403, (
            f"Expected 403 for Business Manager creating template, got {resp.status_code}: {resp.text}"
        )
    finally:
        _clear_overrides()


# ---------------------------------------------------------------------------
# T-CO-CERT-02 (BR-701): Training Creator cannot create a certificate template
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_training_creator_cannot_create_template(client, db_session):
    """
    BR-701: Certificate template creation is SysAdmin-only.
    A Training Creator must receive 403 Forbidden.
    """
    tenant_id = str(uuid.uuid4())
    creator = make_user_auth(
        user_id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        roles=["Training Creator"],
    )
    _set_user(creator)
    try:
        resp = await client.post("/api/v1/certificates/templates", json=SAMPLE_TEMPLATE_PAYLOAD)
        assert resp.status_code == 403, (
            f"Expected 403 for Training Creator creating template, got {resp.status_code}: {resp.text}"
        )
    finally:
        _clear_overrides()


# ---------------------------------------------------------------------------
# T-CO-CERT-03 (BR-701): SysAdmin can create a certificate template
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sysadmin_can_create_template(client, db_session):
    """
    BR-701: SysAdmins are the only role permitted to create certificate templates.
    """
    tenant_id = str(uuid.uuid4())
    sysadmin = make_user_auth(
        user_id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        roles=["SysAdmin"],
        is_global=True,
    )
    _set_user(sysadmin)
    try:
        resp = await client.post("/api/v1/certificates/templates", json=SAMPLE_TEMPLATE_PAYLOAD)
        assert resp.status_code in (200, 201), (
            f"Expected 200/201 for SysAdmin creating template, got {resp.status_code}: {resp.text}"
        )
        data = resp.json()
        assert data["name"] == SAMPLE_TEMPLATE_PAYLOAD["name"]
    finally:
        _clear_overrides()


# ---------------------------------------------------------------------------
# T-CO-CERT-04 (BR-701): Business Manager cannot update a certificate template
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_business_manager_cannot_update_template(client, db_session):
    """
    BR-701: Certificate template update is SysAdmin-only.
    A Business Manager must receive 403 Forbidden.
    """
    tenant_id = str(uuid.uuid4())

    # Create a template as SysAdmin
    sysadmin = make_user_auth(
        user_id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        roles=["SysAdmin"],
        is_global=True,
    )
    _set_user(sysadmin)
    try:
        create_resp = await client.post("/api/v1/certificates/templates", json=SAMPLE_TEMPLATE_PAYLOAD)
        assert create_resp.status_code in (200, 201), (
            f"Template creation failed: {create_resp.status_code}: {create_resp.text}"
        )
        template_id = create_resp.json()["id"]
    finally:
        _clear_overrides()

    # Attempt update as Business Manager — must be 403
    manager = make_user_auth(
        user_id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        roles=["Business Manager"],
    )
    _set_user(manager)
    try:
        resp = await client.put(
            f"/api/v1/certificates/templates/{template_id}",
            json={"name": "Manager Updated Name"},
        )
        assert resp.status_code == 403, (
            f"Expected 403 for Business Manager updating template, got {resp.status_code}: {resp.text}"
        )
    finally:
        _clear_overrides()


# ---------------------------------------------------------------------------
# T-CO-CERT-05 (BR-701): Business Manager cannot delete a certificate template
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_business_manager_cannot_delete_template(client, db_session):
    """
    BR-701: Certificate template deletion is SysAdmin-only.
    A Business Manager must receive 403 Forbidden.
    """
    tenant_id = str(uuid.uuid4())

    # Create a template as SysAdmin
    sysadmin = make_user_auth(
        user_id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        roles=["SysAdmin"],
        is_global=True,
    )
    _set_user(sysadmin)
    try:
        create_resp = await client.post("/api/v1/certificates/templates", json=SAMPLE_TEMPLATE_PAYLOAD)
        assert create_resp.status_code in (200, 201), (
            f"Template creation failed: {create_resp.status_code}: {create_resp.text}"
        )
        template_id = create_resp.json()["id"]
    finally:
        _clear_overrides()

    # Attempt delete as Business Manager — must be 403
    manager = make_user_auth(
        user_id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        roles=["Business Manager"],
    )
    _set_user(manager)
    try:
        resp = await client.delete(f"/api/v1/certificates/templates/{template_id}")
        assert resp.status_code == 403, (
            f"Expected 403 for Business Manager deleting template, got {resp.status_code}: {resp.text}"
        )
    finally:
        _clear_overrides()


# ---------------------------------------------------------------------------
# T-CO-CERT-06 (BR-701): SysAdmin can update and delete a certificate template
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sysadmin_can_update_and_delete_template(client, db_session):
    """
    BR-701: SysAdmins can update and delete certificate templates.
    """
    tenant_id = str(uuid.uuid4())
    sysadmin = make_user_auth(
        user_id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        roles=["SysAdmin"],
        is_global=True,
    )

    # Create
    _set_user(sysadmin)
    try:
        create_resp = await client.post("/api/v1/certificates/templates", json=SAMPLE_TEMPLATE_PAYLOAD)
        assert create_resp.status_code in (200, 201), (
            f"Template creation failed: {create_resp.status_code}: {create_resp.text}"
        )
        template_id = create_resp.json()["id"]
    finally:
        _clear_overrides()

    # Update
    _set_user(sysadmin)
    try:
        update_resp = await client.put(
            f"/api/v1/certificates/templates/{template_id}",
            json={"name": "SysAdmin Updated Name"},
        )
        assert update_resp.status_code == 200, (
            f"Expected 200 for SysAdmin updating template, got {update_resp.status_code}: {update_resp.text}"
        )
        assert update_resp.json()["name"] == "SysAdmin Updated Name"
    finally:
        _clear_overrides()

    # Delete
    _set_user(sysadmin)
    try:
        delete_resp = await client.delete(f"/api/v1/certificates/templates/{template_id}")
        assert delete_resp.status_code == 200, (
            f"Expected 200 for SysAdmin deleting template, got {delete_resp.status_code}: {delete_resp.text}"
        )
    finally:
        _clear_overrides()


# ---------------------------------------------------------------------------
# T-CO-97: Certificate PDF endpoint returns valid PDF bytes
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_certificate_pdf_generates(client, db_session):
    """
    T-CO-97: Certificate PDF endpoint returns a 200 response with content-type
    application/pdf.

    Note: WeasyPrint requires system-level libraries (Pango, Cairo, etc.).
    This test may fail in environments where those libraries are not installed.
    It is intentionally NOT skipped so CI can surface missing dependencies.
    """
    from app.models.training import Training
    from app.models.certificate import Certificate
    from app.models.certificate_template import CertificateTemplate

    tenant_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())

    # Create a minimal certificate template
    template = CertificateTemplate(
        id=str(uuid.uuid4()),
        name="Test Template",
        html_content=(
            "<html><head></head><body>"
            "<p>Certificate for {{learner_name}}</p>"
            "<p>Training: {{training_title}}</p>"
            "<p>Date: {{completion_date}}</p>"
            "<p>Number: {{certificate_number}}</p>"
            "</body></html>"
        ),
        is_active=True,
        tenant_id=tenant_id,
    )
    db_session.add(template)

    # Create a minimal training
    training = Training(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        title="Test Training",
        category="compliance",
        requires_certificate=True,
        template_id=template.id,
        structure_type="flat",
    )
    db_session.add(training)

    # Create a certificate record
    cert_number = f"CERT-{uuid.uuid4().hex[:8].upper()}"
    cert = Certificate(
        id=str(uuid.uuid4()),
        user_id=user_id,
        training_id=training.id,
        template_id=template.id,
        certificate_number=cert_number,
        issued_at=datetime.now(timezone.utc),
        data={
            "learner_name": "Jane Doe",
            "training_title": "Test Training",
            "completion_date": datetime.now(timezone.utc).date().isoformat(),
            "certificate_number": cert_number,
            "tenant_name": "Acme Corp",
            "tenant_logo": "",
            "tenant_primary_color": "#2c3e50",
        },
        tenant_id=tenant_id,
    )
    db_session.add(cert)
    await db_session.commit()

    # Set up user auth (certificate owner)
    learner = make_user_auth(
        user_id=user_id,
        tenant_id=tenant_id,
        roles=["Employee"],
        full_name="Jane Doe",
    )
    _set_user(learner)
    try:
        resp = await client.get(f"/api/v1/certificates/{cert.id}/pdf")
        assert resp.status_code == 200, (
            f"Expected 200 for certificate PDF, got {resp.status_code}: {resp.text}"
        )
        assert "application/pdf" in resp.headers.get("content-type", ""), (
            f"Expected content-type application/pdf, got {resp.headers.get('content-type')}"
        )
    finally:
        _clear_overrides()
