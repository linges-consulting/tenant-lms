import logging
import os
from datetime import datetime

import httpx
from jinja2 import Environment, FileSystemLoader

from app.core.config import settings

logger = logging.getLogger(__name__)

_template_dir = os.path.join(os.path.dirname(__file__), "templates")
_jinja_env = Environment(loader=FileSystemLoader(_template_dir))


async def send_email(to: str, subject: str, template_name: str, context: dict) -> bool:
    """Send email via Mailgun. Returns True on success. No-op if USE_MAILGUN=False."""
    if not settings.USE_MAILGUN:
        return True

    # Inject base vars available to every template; caller context takes priority
    full_context = {
        "current_year": datetime.utcnow().year,
        "frontend_url": settings.FRONTEND_URL,
    }
    full_context.update(context)
    context = full_context

    recipient = to
    if settings.ENVIRONMENT != "prod" and settings.MAILGUN_AUTHORIZED_RECIPIENT:
        recipient = settings.MAILGUN_AUTHORIZED_RECIPIENT

    template = _jinja_env.get_template(template_name)
    html_body = template.render(**context)  # noqa: S701 — Jinja2 autoescape not needed for email HTML

    async with httpx.AsyncClient(timeout=10) as http_client:
        try:
            response = await http_client.post(
                f"{settings.MAILGUN_BASE_URL}/v3/{settings.MAILGUN_DOMAIN}/messages",
                auth=("api", settings.MAILGUN_API_KEY),
                data={
                    "from": settings.FROM_EMAIL,
                    "to": recipient,
                    "subject": subject,
                    "html": html_body,
                },
            )
            if response.status_code != 200:
                logger.error("Mailgun returned %s: %s", response.status_code, response.text)
            return response.status_code == 200
        except httpx.RequestError as exc:
            logger.error("Mailgun request failed: %s", exc)
            return False
