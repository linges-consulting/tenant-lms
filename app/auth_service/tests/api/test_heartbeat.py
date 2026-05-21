import pytest
import uuid
from datetime import datetime, timezone, timedelta
from tests.conftest import make_jwt, TEST_EXTERNAL_JWT_SECRET


@pytest.mark.asyncio
async def test_heartbeat_valid_token(client):
    from app.core.config import settings as app_settings
    token = make_jwt(str(uuid.uuid4()), "tenant-1", ["Employee"], secret=app_settings.EXTERNAL_JWT_SECRET)
    resp = await client.post("/api/v1/auth/heartbeat", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_heartbeat_returns_new_token_when_near_expiry(client):
    from app.core.config import settings as app_settings
    # Token that expires in 5 minutes (under the 10-min threshold)
    token = make_jwt(str(uuid.uuid4()), "tenant-1", ["Employee"], secret=app_settings.EXTERNAL_JWT_SECRET, expires_in=300)
    resp = await client.post("/api/v1/auth/heartbeat", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert "new_token" in resp.headers


@pytest.mark.asyncio
async def test_heartbeat_no_new_token_when_not_near_expiry(client):
    from app.core.config import settings as app_settings
    # Token with >10 min remaining — no refresh needed
    token = make_jwt(str(uuid.uuid4()), "tenant-1", ["Employee"], secret=app_settings.EXTERNAL_JWT_SECRET, expires_in=3600)
    resp = await client.post("/api/v1/auth/heartbeat", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert "new_token" not in resp.headers


@pytest.mark.asyncio
async def test_heartbeat_rejects_expired_token(client):
    from app.core.config import settings as app_settings
    from jose import jwt as jose_jwt
    payload = {
        "sub": str(uuid.uuid4()),
        "tenant_id": "t1",
        "roles": ["Employee"],
        "is_global": False,
        "exp": datetime.now(timezone.utc) - timedelta(seconds=60),
        "iat": datetime.now(timezone.utc) - timedelta(seconds=120),
    }
    token = jose_jwt.encode(payload, app_settings.EXTERNAL_JWT_SECRET, algorithm="HS256")
    resp = await client.post("/api/v1/auth/heartbeat", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401
