import httpx
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

def get_landscape_template(tenant_name: str, brand_color: str) -> str:
    """
    Returns a professional landscape HTML template for certificates.
    """
    # Fallback to a nice dark blue if no brand color
    color = brand_color or "#1e293b"
    
    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        @page {{
            size: A4 landscape;
            margin: 0;
        }}
        body {{
            margin: 0;
            padding: 0;
            font-family: 'Helvetica', 'Arial', sans-serif;
            color: #1e293b;
        }}
        .certificate-container {{
            width: 297mm;
            height: 210mm;
            padding: 20mm;
            box-sizing: border-box;
            background-color: #ffffff;
            position: relative;
            overflow: hidden;
        }}
        /* Elegant Border */
        .border-outer {{
            position: absolute;
            top: 10mm;
            bottom: 10mm;
            left: 10mm;
            right: 10mm;
            border: 2mm solid {color};
        }}
        .border-inner {{
            position: absolute;
            top: 14mm;
            bottom: 14mm;
            left: 14mm;
            right: 14mm;
            border: 0.5mm solid {color};
            padding: 15mm;
            text-align: center;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }}
        /* Corner Accents */
        .corner {{
            position: absolute;
            width: 30mm;
            height: 30mm;
            background-color: {color};
            opacity: 0.1;
        }}
        .top-left {{ top: 0; left: 0; border-bottom-right-radius: 100%; }}
        .bottom-right {{ bottom: 0; right: 0; border-top-left-radius: 100%; }}

        .tenant-header {{
            font-size: 18pt;
            font-weight: bold;
            color: {color};
            text-transform: uppercase;
            letter-spacing: 2px;
            margin-bottom: 10mm;
        }}
        .title {{
            font-size: 42pt;
            font-family: 'Georgia', serif;
            margin-bottom: 5mm;
            color: #0f172a;
        }}
        .subtitle {{
            font-size: 16pt;
            font-style: italic;
            color: #64748b;
            margin-bottom: 20mm;
        }}
        .recipient-name {{
            font-size: 32pt;
            font-weight: bold;
            color: {color};
            border-bottom: 1mm solid #e2e8f0;
            display: inline-block;
            padding: 0 20mm 2mm 20mm;
            margin-bottom: 15mm;
        }}
        .completion-text {{
            font-size: 14pt;
            line-height: 1.6;
            margin-bottom: 10mm;
        }}
        .course-name {{
            font-size: 20pt;
            font-weight: bold;
            color: #0f172a;
        }}
        .footer {{
            margin-top: auto;
            display: flex;
            justify-content: space-between;
            align-items: flex-end;
            padding-top: 10mm;
        }}
        .signature-block {{
            width: 60mm;
            border-top: 0.3mm solid #94a3b8;
            padding-top: 2mm;
            font-size: 10pt;
            color: #64748b;
        }}
        .cert-info {{
            font-size: 9pt;
            color: #94a3b8;
            text-align: right;
        }}
    </style>
</head>
<body>
    <div class="certificate-container">
        <div class="corner top-left"></div>
        <div class="corner bottom-right"></div>
        <div class="border-outer"></div>
        <div class="border-inner">
            <div class="tenant-header">{{{{tenant_name}}}}</div>
            <div class="title">Certificate of Completion</div>
            <div class="subtitle">This recognition is proudly presented to</div>
            
            <div class="recipient-name">{{{{user_name}}}}</div>
            
            <div class="completion-text">
                For the successful completion and mastery of the course<br>
                <span class="course-name">"{{{{training_title}}}}"</span>
            </div>
            
            <div class="footer">
                <div class="signature-block">
                    Authorized Signatory<br>
                    <strong>{{{{tenant_name}}}} Learning Management</strong>
                </div>
                <div class="cert-info">
                    Issued on: {{{{completion_date}}}}<br>
                    ID: {{{{certificate_number}}}}
                </div>
            </div>
        </div>
    </div>
</body>
</html>
"""

async def provision_default_certificate(tenant_id: str, tenant_name: str, brand_color: str = "#1e293b"):
    """
    Calls Core Service to provision a default certificate template for a tenant.
    """
    html_content = get_landscape_template(tenant_name, brand_color)
    
    payload = {
        "name": "Standard Professional Certificate",
        "html_content": html_content,
        "tenant_id": tenant_id
    }
    
    headers = {
        "X-Internal-Api-Key": settings.INTERNAL_API_KEY
    }
    
    url = f"{settings.CORE_SERVICE_URL}/api/v1/certificates/templates/internal/provision"
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.post(url, json=payload, headers=headers)
            if response.status_code in (200, 201):
                logger.info(f"Successfully provisioned certificate for tenant {tenant_id}")
                return True
            else:
                logger.error(f"Failed to provision certificate for {tenant_id}: {response.status_code} {response.text}")
                return False
        except Exception as e:
            logger.error(f"Error calling Core Service for certificate provisioning: {str(e)}")
            return False
