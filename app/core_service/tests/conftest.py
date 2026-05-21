import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from datetime import datetime, timedelta, timezone
from jose import jwt
import uuid
from unittest.mock import AsyncMock, patch

from app.main import app as fastapi_app
from app.db.session import get_db
from app.db.base_class import Base
import app.db.base  # noqa: F401 — ensures all models are registered with Base.metadata
from app.api.deps import get_current_user, UserAuth

# Alias for callers that reference `app` directly (e.g. app.dependency_overrides)
app = fastapi_app

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
EXTERNAL_JWT_SECRET = "test-external"


# ---------------------------------------------------------------------------
# Redis lifespan suppression
#
# The app lifespan starts consume_events() which immediately tries to connect
# to Redis.  In the test environment there is no Redis, so we patch
# consume_events to a no-op coroutine for the entire test session.
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def mock_consume_events():
    """Suppress the Redis event consumer so it does not attempt a real connection."""
    async def _noop():
        pass

    with patch("app.main.consume_events", return_value=_noop()):
        yield


# ---------------------------------------------------------------------------
# Database fixtures
#
# Uses async_sessionmaker (SQLAlchemy 2.x) to match the production session
# factory in app/db/session.py.  The legacy sessionmaker(class_=AsyncSession)
# form still works on SQLAlchemy 2.x but is deprecated; using async_sessionmaker
# avoids the deprecation warning and ensures behaviour matches production.
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
# IMPORTANT — auth pattern for core-service tests
# ------------------------------------------------
# The core service validates JWTs by calling validate_token_with_auth_service()
# (an outbound HTTP call to auth-service).  It does NOT decode tokens locally.
# This means make_jwt() / auth() produce tokens that nothing in the core
# service ever verifies — attaching them as Bearer headers in tests has NO
# effect on authentication.
#
# The correct pattern is to override the get_current_user dependency directly:
#
#   user = make_user_auth(user_id=uid, tenant_id=tid, roles=["Training Creator"])
#   app.dependency_overrides[get_current_user] = override_current_user(user)
#   # … make requests with `client` …
#   app.dependency_overrides.pop(get_current_user, None)
#
# make_jwt() and auth() are retained for completeness (e.g. testing the auth
# service itself or integration tests against a real stack) but must NOT be
# relied upon for authenticating requests in core-service unit tests.
# ---------------------------------------------------------------------------

def make_jwt(user_id: str, tenant_id: str, roles: list[str], expires_in: int = 3600) -> str:
    """
    Build a signed JWT.

    NOTE: The core service validates tokens via an outbound HTTP call to
    auth-service and never decodes them locally.  This token will NOT
    authenticate requests in core-service unit tests.  Use
    override_current_user() / make_user_auth() instead.
    """
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "roles": roles,
        "exp": datetime.now(timezone.utc) + timedelta(seconds=expires_in),
    }
    return jwt.encode(payload, EXTERNAL_JWT_SECRET, algorithm="HS256")


def auth(user_id: str, tenant_id: str, roles: list[str] = None) -> dict:
    """
    Build an Authorization header dict containing a signed JWT.

    NOTE: The core service validates tokens via an outbound HTTP call to
    auth-service and never decodes them locally.  Attaching this header in
    core-service unit tests has NO effect.  Use override_current_user() /
    make_user_auth() instead.
    """
    token = make_jwt(user_id, tenant_id, roles or ["Employee"])
    return {"Authorization": f"Bearer {token}"}


def make_user_auth(
    user_id: str = None,
    tenant_id: str = None,
    roles: list[str] = None,
    email: str = "test@example.com",
    is_active: bool = True,
    is_global: bool = False,
    full_name: str = "Test User",
) -> UserAuth:
    """Build a UserAuth object for use in dependency overrides."""
    return UserAuth(
        id=user_id or str(uuid.uuid4()),
        email=email,
        tenant_id=tenant_id,
        roles=roles or ["Employee"],
        groups=[],
        is_active=is_active,
        is_global=is_global,
        full_name=full_name,
    )


def override_current_user(user: UserAuth):
    """
    Return a dependency-override function that injects a pre-built UserAuth,
    bypassing the outbound auth-service token validation call.

    This is the ONLY correct way to authenticate requests in core-service
    unit tests.

    Usage:
        user = make_user_auth(user_id=uid, tenant_id=tid, roles=["Training Creator"])
        app.dependency_overrides[get_current_user] = override_current_user(user)
        response = await client.get("/api/v1/trainings/")
        app.dependency_overrides.pop(get_current_user, None)

    Or via a per-test fixture:
        @pytest.fixture
        def as_creator(client):
            user = make_user_auth(roles=["Training Creator"], tenant_id=tid)
            app.dependency_overrides[get_current_user] = override_current_user(user)
            yield user
            app.dependency_overrides.pop(get_current_user, None)
    """
    async def _override():
        return user
    return _override
