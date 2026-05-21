from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    REDIS_URL: str = "redis://redis:6379/2"
    SMTP_SERVER: str = "smtp.mailgun.org"
    MAILGUN_API_KEY: str = ""
    MAILGUN_DOMAIN: str = ""
    MAILGUN_BASE_URL: str = "https://api.mailgun.net"
    FROM_EMAIL: str = "CustomLMS <noreply@lms.com>"
    
    # Set to True to actually send emails via Mailgun
    USE_MAILGUN: bool = False
    
    # Dev-mode redirection
    ENVIRONMENT: str = "dev"
    MAILGUN_AUTHORIZED_RECIPIENT: str = ""
    
    # Frontend URL for constructing links
    FRONTEND_URL: str = "http://localhost"

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
