import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Union, Dict

from jose import jwt
from passlib.context import CryptContext
from nanoid import generate

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def validate_password_strength(password: str) -> bool:
    """
    Validates a password against several criteria:
    - At least 8 characters long
    - Contains at least one uppercase letter
    - Contains at least one lowercase letter
    - Contains at least one digit
    - Contains at least one special character
    """
    if len(password) < 8:
        return False
    if not re.search(r"[a-z]", password):
        return False
    if not re.search(r"[A-Z]", password):
        return False
    if not re.search(r"\d", password):
        return False
    # Common special characters matching the frontend regex
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False
    return True

def create_access_token(
    subject: Union[str, Any], 
    expires_delta: timedelta = None, 
    additional_claims: Dict[str, Any] = None,
    secret: str = None
) -> str:
    if not secret:
        secret = settings.EXTERNAL_JWT_SECRET
        
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    
    to_encode = {"exp": expire, "sub": str(subject), "jti": str(uuid.uuid4())}
    if additional_claims:
        to_encode.update(additional_claims)
        
    encoded_jwt = jwt.encode(to_encode, secret, algorithm=settings.ALGORITHM)
    return encoded_jwt

def decode_token(token: str, secret: str = None) -> Dict[str, Any]:
    if not secret:
        secret = settings.EXTERNAL_JWT_SECRET
    return jwt.decode(token, secret, algorithms=[settings.ALGORITHM])

def decode_token_ignore_exp(token: str, secret: str = None) -> Dict[str, Any]:
    """Decode token without validating expiration. Used for token refresh."""
    if not secret:
        secret = settings.EXTERNAL_JWT_SECRET
    return jwt.decode(token, secret, algorithms=[settings.ALGORITHM], options={"verify_exp": False})

def decode_token_with_grace(token: str, grace_period_minutes: int = 5, secret: str = None) -> Dict[str, Any]:
    """
    Decode token and allow it to be refreshed if it expired within the grace period.
    This prevents indefinite renewal of leaked tokens.
    """
    if not secret:
        secret = settings.EXTERNAL_JWT_SECRET
        
    payload = jwt.decode(token, secret, algorithms=[settings.ALGORITHM], options={"verify_exp": False})
    
    # Manually check expiration
    exp = payload.get("exp")
    if exp:
        expire_time = datetime.fromtimestamp(exp, tz=timezone.utc)
        if datetime.now(timezone.utc) > expire_time + timedelta(minutes=grace_period_minutes):
            raise jwt.ExpiredSignatureError("Token has expired beyond grace period")
            
    return payload

def generate_registration_token() -> str:
    """Generate a secure registration token using nanoid."""
    return generate(size=16)
