import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr
from datetime import datetime, timezone, timedelta

from app.db.session import get_db
from app.models.user import User
from app.models.password_reset import PasswordResetToken
from app.core import security
from app.core.config import settings
from app.core.limiter import limiter
from app.core.cache import get_redis
from app.core.login_lockout import clear_lockout

logger = logging.getLogger(__name__)
router = APIRouter()


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


@router.post("/forgot-password")
@limiter.limit("5/minute")
async def forgot_password(request: Request, req: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    """
    Initiate a password reset. Always returns 200 to prevent email enumeration.
    Creates a single-use token valid for 1 hour and sends an email if Mailgun is configured.
    """
    result = await db.execute(select(User).where(User.email == req.email.lower().strip()))
    user = result.scalars().first()
    if user and user.is_active:
        token_value = str(uuid.uuid4())
        reset_token = PasswordResetToken(
            id=str(uuid.uuid4()),
            user_id=user.id,
            token=token_value,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            is_used=False,
        )
        db.add(reset_token)
        await db.commit()

        # Send email only when Mailgun is configured (USE_MAILGUN / non-dev environment)
        if settings.ENVIRONMENT != "dev" and settings.MAILGUN_API_KEY:
            try:
                from app.utils.email import EmailService
                reset_url = f"{settings.FRONTEND_URL}/reset-password?token={token_value}"
                full_name = user.full_name or user.email
                await EmailService.send_password_reset(
                    to_email=user.email,
                    full_name=full_name,
                    reset_url=reset_url,
                    expiration_hours=1,
                )
            except Exception as e:
                logger.warning("Failed to send password reset email: %s", type(e).__name__)

    return {"message": "If that email is registered, a reset link has been sent."}


@router.post("/reset-password")
@limiter.limit("5/minute")
async def reset_password(
    request: Request,
    req: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):
    """
    Complete a password reset using a valid single-use token.
    Validates the token, updates the user's password, and marks the token as used.
    Also clears any account lockout state so the user can log in normally again.
    """
    result = await db.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.token == req.token,
            PasswordResetToken.is_used == False,
            PasswordResetToken.expires_at > datetime.now(timezone.utc),
        )
    )
    reset_token = result.scalars().first()
    if not reset_token:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token.")

    user = await db.get(User, reset_token.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=404, detail="User not found.")

    if not security.validate_password_strength(req.new_password):
        raise HTTPException(
            status_code=422,
            detail="Password must be at least 8 characters and contain uppercase, lowercase, digit, and special character."
        )

    user.hashed_password = security.get_password_hash(req.new_password)
    reset_token.is_used = True
    await db.commit()

    # Clear any account lockout state so the user can log in normally again.
    # This is the recovery path for force-reset locked accounts.
    await clear_lockout(user.email, redis)

    return {"message": "Password updated successfully."}
