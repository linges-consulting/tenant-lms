import os
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from unittest.mock import AsyncMock, patch
import uuid

# ---------------------------------------------------------------------------
# Provide required env vars before any app module is imported.
# REDIS_URL and INTERNAL_API_KEY have no defaults in config.py; without these
# the pydantic Settings() call fails at import time.
# ---------------------------------------------------------------------------
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("INTERNAL_API_KEY", "test-internal-key")
os.environ.setdefault("ENVIRONMENT", "test")

from app.main import app
from app.db.session import get_db
from app.api.deps import get_current_user, get_current_tenant_id, UserAuth
from app.models.notification import Base

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


# ---------------------------------------------------------------------------
# Cache suppression
#
# The list_notifications endpoint uses @cache_response which calls get_redis()
# at request time and attempts a real Redis connection.  In tests there is no
# Redis, so we patch get_redis to return an AsyncMock that silently no-ops
# all cache reads/writes.  This lets endpoint logic run normally without Redis.
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def mock_redis_cache():
    """Replace the Redis client with a no-op mock for all tests."""
    mock_r = AsyncMock()
    mock_r.get = AsyncMock(return_value=None)   # cache always misses
    mock_r.setex = AsyncMock(return_value=True)
    mock_r.keys = AsyncMock(return_value=[])
    mock_r.delete = AsyncMock(return_value=0)

    with patch("app.core.cache.get_redis", return_value=mock_r):
        yield


# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture(scope="function")
async def db_session():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False, autocommit=False, autoflush=False)
    async with factory() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


# ---------------------------------------------------------------------------
# HTTP client fixture
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture(scope="function")
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Auth helpers
#
# The notification service validates JWTs by calling the auth service over
# HTTP (validate_token_with_auth_service).  In tests we override
# get_current_user and get_current_tenant_id directly — never attach Bearer
# tokens and expect them to work.
# ---------------------------------------------------------------------------

def make_user_auth(
    user_id: str = None,
    tenant_id: str = None,
    roles: list[str] = None,
    email: str = "test@example.com",
    is_active: bool = True,
    full_name: str = "Test User",
) -> UserAuth:
    """Build a UserAuth object for use in dependency overrides."""
    return UserAuth(
        id=user_id or str(uuid.uuid4()),
        email=email,
        tenant_id=tenant_id,
        roles=roles or ["Employee"],
        is_active=is_active,
        full_name=full_name,
    )


def override_current_user(user: UserAuth):
    """
    Return a dependency-override callable that injects a pre-built UserAuth,
    bypassing the outbound auth-service token validation call.

    WARNING: This only overrides get_current_user, NOT get_current_tenant_id.
    Endpoints that depend on get_current_tenant_id will still use the real
    dependency and may fail or return incorrect tenant context.
    Most tests should use make_auth_overrides() instead, which overrides both
    get_current_user and get_current_tenant_id in a single call.

    Usage:
        user = make_user_auth(user_id=uid, tenant_id=tid, roles=["Employee"])
        app.dependency_overrides[get_current_user] = override_current_user(user)
        response = await client.get("/api/v1/notifications")
        app.dependency_overrides.pop(get_current_user, None)
    """
    async def _override():
        return user
    return _override


def make_auth_overrides(user_id: str, tenant_id: str, roles: list[str] = None) -> dict:
    """
    Return a dict of dependency overrides for both get_current_user and
    get_current_tenant_id.  Apply with app.dependency_overrides.update(...)
    and clear with app.dependency_overrides.clear() or selective .pop() after.

    Usage:
        app.dependency_overrides.update(
            make_auth_overrides(user_id=uid, tenant_id=tid, roles=["Employee"])
        )
        response = await client.get("/api/v1/notifications")
    """
    user = make_user_auth(user_id=user_id, tenant_id=tenant_id, roles=roles)

    async def _get_user():
        return user

    async def _get_tenant():
        return tenant_id

    return {
        get_current_user: _get_user,
        get_current_tenant_id: _get_tenant,
    }
