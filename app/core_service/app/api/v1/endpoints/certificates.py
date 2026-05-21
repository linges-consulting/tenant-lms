from typing import List, Optional, Any, Dict
from fastapi import APIRouter, Depends, HTTPException, status, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.orm import selectinload
from datetime import datetime, timezone
import uuid

from app.api import deps
from app.models.certificate_template import CertificateTemplate
from app.models.certificate import Certificate
from app.models.enrollment import Enrollment
from app.models.training import Training
from app.schemas.certificate import (
    CertificateTemplate as CertificateTemplateSchema,
    CertificateTemplateWithUsage,
    CertificateTemplateCreate,
    CertificateTemplateUpdate,
    Certificate as CertificateSchema,
    CertificatePreviewRequest,
    CertificatePreviewResponse
)
from app.utils.pdf import render_certificate_pdf

router = APIRouter()

# --- Templates ---

@router.get("/templates", response_model=List[CertificateTemplateWithUsage])
async def read_templates(
    target_tenant_id: Optional[List[str]] = Query(None),
    db: AsyncSession = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    current_user: deps.UserAuth = Depends(deps.get_current_tenant_user),
):
    """
    List all certificate templates, annotated with is_in_use.
    SysAdmins can pass target_tenant_id to list for a specific tenant,
    or no target_tenant_id to see all templates across all tenants.
    """
    is_sysadmin = "SysAdmin" in current_user.roles

    stmt = select(CertificateTemplate)
    if not is_sysadmin:
        stmt = stmt.where(CertificateTemplate.tenant_id == tenant_id)
        stmt = stmt.where(CertificateTemplate.is_active == True)
    elif target_tenant_id:
        stmt = stmt.where(CertificateTemplate.tenant_id.in_(target_tenant_id))

    result = await db.execute(stmt)
    templates = result.scalars().all()

    # Determine which templates are referenced by at least one training
    template_ids = [t.id for t in templates]
    in_use_ids: set[str] = set()
    if template_ids:
        in_use_result = await db.execute(
            select(Training.template_id)
            .where(Training.template_id.in_(template_ids))
            .distinct()
        )
        in_use_ids = {row[0] for row in in_use_result.fetchall() if row[0]}

    return [
        CertificateTemplateWithUsage(
            **CertificateTemplateSchema.model_validate(t).model_dump(),
            is_in_use=t.id in in_use_ids,
        )
        for t in templates
    ]

@router.post("/templates", response_model=CertificateTemplateSchema, status_code=status.HTTP_201_CREATED)
async def create_template(
    template_in: CertificateTemplateCreate,
    db: AsyncSession = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    current_user: deps.UserAuth = Depends(deps.get_current_tenant_user),
):
    """
    Create a new certificate template.
    SysAdmins may pass target_tenant_id to create for a specific tenant.
    """
    # BR-701: Certificate template CRUD is SysAdmin-only
    if "SysAdmin" not in current_user.roles:
        raise HTTPException(status_code=403, detail="Only SysAdmins can manage certificate templates.")

    # SysAdmin can override the target tenant
    is_sysadmin = "SysAdmin" in current_user.roles
    effective_tenant_id = (
        template_in.target_tenant_id
        if is_sysadmin and template_in.target_tenant_id
        else tenant_id
    )

    template_data = template_in.model_dump(exclude={"target_tenant_id"})
    template = CertificateTemplate(**template_data, tenant_id=effective_tenant_id)
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return template

class _InternalTemplateCreate(CertificateTemplateCreate):
    """Internal-only: tenant_id is required for service-to-service provisioning."""
    tenant_id: str

@router.post("/templates/internal/provision", response_model=CertificateTemplateSchema, include_in_schema=False)
async def provision_default_template(
    template_in: _InternalTemplateCreate,
    db: AsyncSession = Depends(deps.get_db),
    _: None = Depends(deps.validate_internal_api),
):
    """
    Internal endpoint called by auth-service to provision a default certificate
    template when a new tenant is created. Secured by X-Internal-Api-Key.
    """
    template_data = template_in.model_dump(exclude={"target_tenant_id"})
    template = CertificateTemplate(**template_data, is_default=True)
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return template


@router.get("/templates/{template_id}", response_model=CertificateTemplateSchema)
async def read_template(
    template_id: str,
    db: AsyncSession = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    current_user: deps.UserAuth = Depends(deps.get_current_tenant_user),
):
    """
    Get a specific certificate template.
    """
    is_sysadmin = "SysAdmin" in current_user.roles
    stmt = select(CertificateTemplate).where(CertificateTemplate.id == template_id)
    
    if not is_sysadmin:
        stmt = stmt.where(CertificateTemplate.tenant_id == tenant_id)
        
    result = await db.execute(stmt)
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template

@router.put("/templates/{template_id}", response_model=CertificateTemplateSchema)
async def update_template(
    template_id: str,
    template_in: CertificateTemplateUpdate,
    db: AsyncSession = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    current_user: deps.UserAuth = Depends(deps.get_current_tenant_user),
):
    """
    Update a certificate template.
    """
    # BR-701: Certificate template CRUD is SysAdmin-only
    is_sysadmin = "SysAdmin" in current_user.roles
    if not is_sysadmin:
        raise HTTPException(status_code=403, detail="Only SysAdmins can manage certificate templates.")

    stmt = select(CertificateTemplate).where(CertificateTemplate.id == template_id)
        
    result = await db.execute(stmt)
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    update_data = template_in.model_dump(exclude_unset=True)

    # Guard: default template cannot be deactivated
    if update_data.get("is_active") is False and template.is_default:
        raise HTTPException(status_code=400, detail="Default template cannot be deactivated/deleted")

    # Guard: in-use template cannot be deactivated
    if update_data.get("is_active") is False:
        in_use = await db.execute(
            select(Training.id).where(Training.template_id == template_id).limit(1)
        )
        if in_use.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Template in use by active trainings cannot be deactivated/deleted")

    for field, value in update_data.items():
        setattr(template, field, value)

    await db.commit()
    await db.refresh(template)
    return template

@router.delete("/templates/{template_id}")
async def delete_template(
    template_id: str,
    db: AsyncSession = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    current_user: deps.UserAuth = Depends(deps.get_current_tenant_user),
):
    """
    Delete a certificate template.
    """
    # BR-701: Certificate template CRUD is SysAdmin-only
    is_sysadmin = "SysAdmin" in current_user.roles
    if not is_sysadmin:
        raise HTTPException(status_code=403, detail="Only SysAdmins can manage certificate templates.")

    stmt = select(CertificateTemplate).where(CertificateTemplate.id == template_id)
        
    result = await db.execute(stmt)
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    if template.is_default:
        raise HTTPException(status_code=400, detail="Default template cannot be deactivated/deleted")

    in_use = await db.execute(
        select(Training.id).where(Training.template_id == template_id).limit(1)
    )
    if in_use.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Template in use by active trainings cannot be deactivated/deleted")

    await db.delete(template)
    await db.commit()
    return {"status": "success"}

@router.post("/templates/preview", response_model=CertificatePreviewResponse)
async def preview_template(
    preview_in: CertificatePreviewRequest,
):
    """
    Preview a certificate template with mock data.
    """
    html = preview_in.html_content
    data = preview_in.data or {
        "user_name": "Learner Name",
        "course_name": "Training Course",
        "completion_date": datetime.now().strftime("%Y-%m-%d"),
        "certificate_number": f"CERT-{uuid.uuid4().hex[:8].upper()}"
    }
    
    for key, value in data.items():
        placeholder = f"{{{{{key}}}}}"
        html = html.replace(placeholder, str(value))
    
    return CertificatePreviewResponse(rendered_html=html)

@router.get("/templates/{template_id}/pdf", response_class=StreamingResponse)
async def preview_template_pdf(
    template_id: str,
    db: AsyncSession = Depends(deps.get_db),
    tenant_id: str = Depends(deps.get_current_tenant_id),
    current_user: deps.UserAuth = Depends(deps.get_current_tenant_user),
):
    """
    Generate a PDF preview of a certificate template with dummy data.
    """
    is_sysadmin = "SysAdmin" in current_user.roles
    stmt = select(CertificateTemplate).where(CertificateTemplate.id == template_id)
    
    if not is_sysadmin:
        stmt = stmt.where(CertificateTemplate.tenant_id == tenant_id)
        
    result = await db.execute(stmt)
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
        
    # Fetch branding
    branding = await deps.get_tenant_branding(tenant_id)
    
    # Sample data for the certificate
    dummy_context = {
        "user_name": "John Doe",
        "training_title": "Introduction to Cybersecurity",
        "course_name": "Introduction to Cybersecurity",
        "completion_date": datetime.now().strftime("%B %d, %Y"),
        "certificate_number": f"CERT-{uuid.uuid4().hex[:8].upper()}",
        "tenant_name": branding["name"],
        "brand_color": branding["primary_color"],
        "primary_color": branding["primary_color"],
        "score": "95%",
        "duration": "10 hours"
    }
    
    try:
        pdf_bytes = render_certificate_pdf(template.html_content, dummy_context)
        from io import BytesIO
        return StreamingResponse(
            BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f"inline; filename=preview_{template.id}.pdf"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF rendering failed: {str(e)}")

# --- Issued Certificates ---

@router.get("/my", response_model=List[CertificateSchema])
async def read_my_certificates(
    db: AsyncSession = Depends(deps.get_db),
    current_user: deps.UserAuth = Depends(deps.get_current_tenant_user),
    tenant_id: str = Depends(deps.get_current_tenant_id),
):
    """
    List all certificates earned by the current user.
    """
    stmt = (
        select(Certificate)
        .where(
            Certificate.user_id == current_user.id,
            Certificate.tenant_id == tenant_id
        )
        .options(selectinload(Certificate.training))
    )
    result = await db.execute(stmt)
    return result.scalars().all()

@router.get("/{certificate_id}/view")
async def view_certificate(
    certificate_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: deps.UserAuth = Depends(deps.get_current_tenant_user),
    tenant_id: str = Depends(deps.get_current_tenant_id),
):
    """
    Get the rendered HTML of a specific certificate.
    """
    stmt = (
        select(Certificate)
        .where(
            Certificate.id == certificate_id,
            Certificate.tenant_id == tenant_id
        )
        .options(
            selectinload(Certificate.template),
            selectinload(Certificate.training)
        )
    )
    result = await db.execute(stmt)
    cert = result.scalar_one_or_none()
    if not cert:
        raise HTTPException(status_code=404, detail="Certificate not found")
    
    # Check permissions
    is_owner = cert.user_id == current_user.id
    is_privileged = any(role in ["Admin", "Business Manager"] for role in current_user.roles)
    
    if not (is_owner or is_privileged):
        raise HTTPException(status_code=403, detail="Not enough permissions")

    # Render template logic
    branding = await deps.get_tenant_branding(tenant_id)
    render_data = cert.data.copy()
    
    # Standard fields
    render_data.setdefault("user_name", "Learner")
    render_data.setdefault("training_title", cert.training.title)
    render_data.setdefault("course_name", cert.training.title)
    render_data.setdefault("completion_date", cert.issued_at.strftime("%Y-%m-%d"))
    render_data.setdefault("certificate_number", cert.certificate_number)
    render_data.setdefault("tenant_name", branding["name"])
    render_data.setdefault("brand_color", branding["primary_color"])
    render_data.setdefault("primary_color", branding["primary_color"])

    html = cert.template.html_content
    for key, value in render_data.items():
        placeholder = f"{{{{{key}}}}}"
        html = html.replace(placeholder, str(value))
    
    return {"rendered_html": html}

@router.get("/{certificate_id}/pdf")
async def download_certificate_pdf(
    certificate_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: deps.UserAuth = Depends(deps.get_current_tenant_user),
    tenant_id: str = Depends(deps.get_current_tenant_id),
):
    """
    Get the PDF version of a specific certificate.
    """
    stmt = (
        select(Certificate)
        .where(
            Certificate.id == certificate_id,
            Certificate.tenant_id == tenant_id
        )
        .options(
            selectinload(Certificate.template),
            selectinload(Certificate.training)
        )
    )
    result = await db.execute(stmt)
    cert = result.scalar_one_or_none()
    if not cert:
        raise HTTPException(status_code=404, detail="Certificate not found")
    
    # Check permissions
    is_owner = cert.user_id == current_user.id
    is_privileged = any(role in ["Admin", "Business Manager"] for role in current_user.roles)
    
    if not (is_owner or is_privileged):
        raise HTTPException(status_code=403, detail="Not enough permissions")

    # Render HTML template logic (consistent with view_certificate)
    branding = await deps.get_tenant_branding(tenant_id)
    render_data = cert.data.copy()
    
    render_data.setdefault("user_name", "Learner")
    render_data.setdefault("training_title", cert.training.title)
    render_data.setdefault("course_name", cert.training.title)
    render_data.setdefault("completion_date", cert.issued_at.strftime("%Y-%m-%d"))
    render_data.setdefault("certificate_number", cert.certificate_number)
    render_data.setdefault("tenant_name", branding["name"])
    render_data.setdefault("brand_color", branding["primary_color"])
    render_data.setdefault("primary_color", branding["primary_color"])

    html = cert.template.html_content
    for key, value in render_data.items():
        placeholder = f"{{{{{key}}}}}"
        html = html.replace(placeholder, str(value))
    
    # Generate PDF
    try:
        from io import BytesIO
        pdf_bytes = render_certificate_pdf(html, {})
        return StreamingResponse(
            BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f"inline; filename=certificate_{cert.certificate_number}.pdf"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF rendering failed: {str(e)}")
