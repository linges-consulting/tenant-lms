from fastapi import APIRouter, Header, HTTPException
from app.core.security import decode_token

router = APIRouter()


@router.get("/validate-media")
async def validate_media_access(
    authorization: str | None = Header(default=None),
    x_original_uri: str | None = Header(default=None),
):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401)
    token = authorization.removeprefix("Bearer ")
    try:
        decode_token(token)
    except Exception:
        raise HTTPException(status_code=401)
    return {"status": "ok"}
