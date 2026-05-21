import json
import asyncio
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import redis.asyncio as redis
import httpx
from jinja2 import Environment, FileSystemLoader, select_autoescape

from config import settings
from logging_config import setup_logging

# Initialize production-grade logging
setup_logging()
logger = logging.getLogger(__name__)

# Initialize Jinja2 environment
TEMPLATES_DIR = Path(__file__).parent / "templates"
jinja_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(['html', 'xml'])
)

def get_base_context() -> dict:
    """Get base context variables for all templates."""
    return {
        "current_year": datetime.now().year,
        "company_website": "https://cpvmtraining.com",
        "help_center": "https://cpvmtraining.com/help",
        "privacy_policy": "https://cpvmtraining.com/privacy",
        "support_email": "support@cpvmtraining.com",
    }

async def send_email(to_email: str, subject: str, text_body: str, html_body: Optional[str] = None):
    if settings.USE_MAILGUN and settings.MAILGUN_API_KEY:
        recipient = to_email
        if settings.ENVIRONMENT == "dev":
            logger.info(f"Dev mode enabled. Redirecting email from {to_email} to {settings.MAILGUN_AUTHORIZED_RECIPIENT}")
            recipient = settings.MAILGUN_AUTHORIZED_RECIPIENT

        try:
            async with httpx.AsyncClient() as client:
                data = {
                    "from": settings.FROM_EMAIL,
                    "to": recipient,
                    "subject": subject,
                    "text": text_body
                }
                if html_body:
                    data["html"] = html_body
                
                # Handle Mailgun v3 API URL
                base_url = settings.MAILGUN_BASE_URL.rstrip('/')
                url = f"{base_url}/v3/{settings.MAILGUN_DOMAIN}/messages"
                
                response = await client.post(
                    url,
                    auth=("api", settings.MAILGUN_API_KEY),
                    data=data
                )
                response.raise_for_status()
                logger.info("Email sent successfully via Mailgun.")
        except Exception as e:
            logger.error(f"Failed to send email via Mailgun: {e}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Response: {e.response.text}")
    else:
        # Dry run / Sandbox mode
        logger.info("--- EMAIL SIMULATION (SANDBOX) ---")
        logger.info(f"TO: {to_email}")
        logger.info(f"SUBJECT: {subject}")
        logger.info(f"BODY (TEXT): {text_body[:100]}...")
        if html_body:
            logger.info("BODY (HTML): [Rich content provided]")
        logger.info("----------------------------------")

async def check_idempotency(r: redis.Redis, event_id: str) -> bool:
    if not event_id:
        return True
    is_new = await r.sadd("processed_email_events", event_id)
    if is_new:
        await r.expire("processed_email_events", 7 * 24 * 3600)
    return bool(is_new)

async def handle_event(event_type: str, payload: dict, event_id: str, r: redis.Redis):
    # Idempotency check for all events to prevent duplicates
    if not await check_idempotency(r, event_id):
        logger.info(f"Skipping duplicate email event: {event_id}")
        return

    context = get_base_context()
    context.update(payload)

    if event_type == "TRAINING_COMPLETED":
        template = jinja_env.get_template("course_completion.html")
        training_title = payload.get("training_title", "Course")
        full_name = payload.get("full_name", payload.get("user_email", "Learner"))
        
        context.update({
            "full_name": full_name,
            "training_title": training_title,
            "dashboard_url": f"{settings.FRONTEND_URL}/learner/certificates"
        })
        
        subject = f"Congratulations! You've completed {training_title}"
        text_body = f"Hi {full_name},\n\nCongratulations! You have successfully completed the training: {training_title}.\n\nYou can view your certificates at: {settings.FRONTEND_URL}/learner/certificates"
        html_body = template.render(**context)
        await send_email(payload.get("user_email") or payload.get("email"), subject, text_body, html_body)

    elif event_type == "USER_INVITED":
        template = jinja_env.get_template("registration_invite.html")
        email = payload.get("email")
        full_name = payload.get("full_name", email)
        reg_url = payload.get("registration_url") or payload.get("invite_url")
        token = payload.get("token")
        tenant_name = payload.get("tenant_name")
        
        subject = f"Invite: Join {'Your Team' if not tenant_name else tenant_name} on CustomLMS"
        text_body = f"Hi {full_name},\n\nYou have been invited to join CustomLMS. Complete your registration here: {reg_url}\n\nToken: {token}"
        
        # Ensure context has all needed vars
        context.update({
            "full_name": full_name,
            "registration_url": reg_url,
            "token": token,
            "tenant_name": tenant_name
        })
        
        html_body = template.render(**context)
        await send_email(email, subject, text_body, html_body)

    elif event_type == "PASSWORD_RESET_REQUESTED":
        template = jinja_env.get_template("password_reset.html")
        email = payload.get("email")
        full_name = payload.get("full_name", email)
        reset_url = payload.get("reset_url")
        exp_hours = payload.get("expiration_hours", 2)
        
        subject = "Reset Your CustomLMS Password"
        text_body = f"Hi {full_name},\n\nWe received a request to reset your password. Use this link: {reset_url}\n\nThis link expires in {exp_hours} hours."
        
        context.update({
            "full_name": full_name,
            "reset_url": reset_url,
            "expiration_hours": exp_hours
        })
        
        html_body = template.render(**context)
        await send_email(email, subject, text_body, html_body)

async def main():
    logger.info("Email worker starting (Unified Async Mode)...")
    r = redis.from_url(settings.REDIS_URL, decode_responses=True)
    pubsub = r.pubsub()
    await pubsub.subscribe("lms_events")
    
    logger.info(f"Email worker listening on 'lms_events' channel (Frontend: {settings.FRONTEND_URL})...")
    
    async for message in pubsub.listen():
        if message["type"] == "message":
            try:
                data = json.loads(message["data"])
                event_type = data.get("event_type")
                event_id = data.get("event_id")
                payload = data.get("payload")
                
                logger.info(f"Processing event: {event_type} (ID: {event_id})")
                await handle_event(event_type, payload, event_id, r)
            except Exception as e:
                logger.error(f"Error handling event: {e}", exc_info=True)

if __name__ == "__main__":
    async def run_worker():
        while True:
            try:
                await main()
            except Exception as e:
                logger.error(f"Worker crashed! Restarting in 5s... Error: {e}")
                await asyncio.sleep(5)
    
    asyncio.run(run_worker())
