"""
Email template rendering utilities.
Renders Jinja2 templates with context variables.
"""
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from jinja2 import Environment, FileSystemLoader, select_autoescape

# Initialize Jinja2 environment
TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
jinja_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(['html', 'xml'])
)

class TemplateRenderer:
    """Renders email templates with provided context."""
    
    @staticmethod
    def get_base_context() -> dict:
        """Get base context variables for all templates."""
        return {
            "current_year": datetime.now().year,
            "company_website": "https://customlms.com",
            "help_center": "https://help.customlms.com",
            "privacy_policy": "https://customlms.com/privacy",
            "support_email": "support@customlms.com",
        }
    
    @staticmethod
    def render_registration_invite(
        full_name: str,
        registration_url: str,
        token: str,
        tenant_name: Optional[str] = None,
    ) -> str:
        """
        Render registration invite email template.
        
        Args:
            full_name: User's full name
            registration_url: Full URL to registration page with token
            token: Registration token (for manual entry)
            tenant_name: Optional tenant/organization name
            
        Returns:
            Rendered HTML string
        """
        template = jinja_env.get_template("registration_invite.html")
        context = TemplateRenderer.get_base_context()
        context.update({
            "full_name": full_name,
            "registration_url": registration_url,
            "token": token,
            "tenant_name": tenant_name,
        })
        return template.render(**context)
    
    @staticmethod
    def render_token_regenerated(
        full_name: str,
        registration_url: str,
        token: str,
        expires_at: datetime,
    ) -> str:
        """
        Render token regeneration email template.
        
        Args:
            full_name: User's full name
            registration_url: Full URL to registration page with new token
            token: New registration token
            expires_at: Datetime when token expires
            
        Returns:
            Rendered HTML string
        """
        template = jinja_env.get_template("token_regenerated.html")
        context = TemplateRenderer.get_base_context()
        context.update({
            "full_name": full_name,
            "registration_url": registration_url,
            "token": token,
            "expires_at": expires_at.strftime("%B %d, %Y at %I:%M %p %Z"),
        })
        return template.render(**context)
    
    @staticmethod
    def render_password_reset(
        full_name: str,
        reset_url: str,
        expiration_hours: int = 2,
    ) -> str:
        """
        Render password reset email template.
        
        Args:
            full_name: User's full name
            reset_url: Full URL to password reset page with token
            expiration_hours: Hours until link expires (default 2)
            
        Returns:
            Rendered HTML string
        """
        template = jinja_env.get_template("password_reset.html")
        context = TemplateRenderer.get_base_context()
        context.update({
            "full_name": full_name,
            "reset_url": reset_url,
            "expiration_hours": expiration_hours,
        })
        return template.render(**context)
