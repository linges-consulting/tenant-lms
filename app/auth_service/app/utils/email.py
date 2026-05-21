import httpx
import logging
from typing import Optional
from app.core.config import settings
from app.utils.template_renderer import TemplateRenderer

logger = logging.getLogger(__name__)

class EmailService:
    @staticmethod
    async def send_email(
        to_email: str,
        subject: str,
        text: Optional[str] = None,
        html: Optional[str] = None
    ) -> bool:
        """
        Sends an email via Mailgun API.
        If ENVIRONMENT is 'dev', redirects all emails to the authorized recipient.
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            text: Plain text version of email (optional if html provided)
            html: HTML version of email (optional if text provided)
            
        Returns:
            True if successful, False otherwise
        """
        if not text and not html:
            logger.warning("Email must have either text or html content")
            return False
            
        recipient = to_email
        if settings.ENVIRONMENT == "dev":
            logger.info(f"Dev mode enabled. Redirecting email from {to_email} to {settings.MAILGUN_AUTHORIZED_RECIPIENT}")
            recipient = settings.MAILGUN_AUTHORIZED_RECIPIENT

        mailgun_url = f"{settings.MAILGUN_BASE_URL}/v3/{settings.MAILGUN_DOMAIN}/messages"
        
        data = {
            "from": f"CustomLMS <noreply@{settings.MAILGUN_DOMAIN}>",
            "to": recipient,
            "subject": subject,
        }
        
        if text:
            data["text"] = text
        if html:
            data["html"] = html
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    mailgun_url,
                    auth=("api", settings.MAILGUN_API_KEY),
                    data=data,
                    timeout=10.0
                )
                
                if response.status_code != 200:
                    logger.error(f"Failed to send email to {recipient}. Status: {response.status_code}, Response: {response.text}")
                    return False
                
                logger.info(f"Email successfully sent to {recipient} (Original: {to_email})")
                return True
                
            except Exception as e:
                logger.error(f"Error sending email: {str(e)}")
                return False

    @staticmethod
    async def send_registration_invite(
        to_email: str,
        full_name: str,
        registration_url: str,
        token: str,
        tenant_name: Optional[str] = None
    ) -> bool:
        """
        Send registration invitation email with HTML template.
        
        Args:
            to_email: Recipient email
            full_name: User's full name
            registration_url: Registration URL with token
            token: Registration token for manual entry
            tenant_name: Organization name (optional)
            
        Returns:
            True if successful, False otherwise
        """
        subject = "Complete Your Registration at CustomLMS"
        html = TemplateRenderer.render_registration_invite(
            full_name=full_name,
            registration_url=registration_url,
            token=token,
            tenant_name=tenant_name
        )
        
        return await EmailService.send_email(to_email, subject, html=html)

    @staticmethod
    async def send_token_regenerated(
        to_email: str,
        full_name: str,
        registration_url: str,
        token: str,
        expires_at
    ) -> bool:
        """
        Send token regeneration notification email.
        
        Args:
            to_email: Recipient email
            full_name: User's full name
            registration_url: New registration URL with token
            token: New registration token
            expires_at: Datetime when token expires
            
        Returns:
            True if successful, False otherwise
        """
        subject = "New Registration Link for CustomLMS"
        html = TemplateRenderer.render_token_regenerated(
            full_name=full_name,
            registration_url=registration_url,
            token=token,
            expires_at=expires_at
        )
        
        return await EmailService.send_email(to_email, subject, html=html)

    @staticmethod
    async def send_password_reset(
        to_email: str,
        full_name: str,
        reset_url: str,
        expiration_hours: int = 2
    ) -> bool:
        """
        Send password reset email.
        
        Args:
            to_email: Recipient email
            full_name: User's full name
            reset_url: Password reset URL with token
            expiration_hours: Hours until reset link expires (default 2)
            
        Returns:
            True if successful, False otherwise
        """
        subject = "Reset Your Password"
        html = TemplateRenderer.render_password_reset(
            full_name=full_name,
            reset_url=reset_url,
            expiration_hours=expiration_hours
        )
        
        return await EmailService.send_email(to_email, subject, html=html)

    @staticmethod
    async def send_invite_email(to_email: str, invite_url: str):
        """
        Legacy helper for user invitations (plain text).
        Use send_registration_invite for new invitations.
        """
        subject = "Welcome to CustomLMS - Completing your setup"
        text = f"""
Hello,

You have been invited to join CustomLMS. 
Please click the link below to set your password and activate your account:

{invite_url}

This link will expire in 24 hours.

Best regards,
The CustomLMS Team
"""
        return await EmailService.send_email(to_email, subject, text=text)
