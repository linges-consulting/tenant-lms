import logging
from fastapi import APIRouter, Response, HTTPException, Header
from datetime import datetime, timezone, timedelta
from jose import jwt as jose_jwt, JWTError
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

NEAR_EXPIRY_SECONDS = 600  # 10 minutes


@router.post("/heartbeat")
async def heartbeat(
    response: Response,
    authorization: Optional[str] = Header(default=None),
):
    """
    Training-viewer heartbeat. Keeps the session alive and refreshes the JWT
    when remaining lifetime is <= 10 minutes (BR-HB-01).
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = authorization[len("Bearer "):]
    try:
        payload = jose_jwt.decode(
            token,
            settings.EXTERNAL_JWT_SECRET,
            algorithms=[settings.ALGORITHM],
        )
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    exp = payload.get("exp")
    if exp is not None:
        remaining = exp - datetime.now(timezone.utc).timestamp()
        if remaining <= NEAR_EXPIRY_SECONDS:
            # Re-issue with a fresh expiry; preserve all other claims except exp/iat
            new_payload = {k: v for k, v in payload.items() if k not in ("exp", "iat")}
            new_payload["iat"] = datetime.now(timezone.utc)
            new_payload["exp"] = datetime.now(timezone.utc) + timedelta(
                minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
            )
            new_token = jose_jwt.encode(
                new_payload,
                settings.EXTERNAL_JWT_SECRET,
                algorithm=settings.ALGORITHM,
            )
            response.headers["new_token"] = new_token
            logger.info("Heartbeat issued token refresh (remaining=%.0fs)", remaining)

    return {"status": "ok"}
