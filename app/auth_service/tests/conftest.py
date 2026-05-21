import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta, timezone
from jose import jwt
import uuid

# main.py is at the root of app/auth_service/ (tests run with cwd = app/auth_service/)
from main import app
from app.db.session import get_db
from app.db.base import Base  # imports all models so metadata is populated
from app.core.cache import get_redis


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """
    Reset the in-memory rate limiter between tests.
    Slowapi uses limits.storage.MemoryStorage by default; clearing its _storage
    dict prevents cross-test rate limit bleed-through (e.g. 5/min endpoints
    failing after the 5th test hits the same URL).
    """
    from app.core.limiter import limiter
    try:
        storage = limiter._limiter.storage
        if hasattr(storage, "_storage"):
            storage._storage.clear()
        elif hasattr(storage, "storage"):
            storage.storage.clear()
    except Exception:
        pass  # ignore if storage layout changes; tests may still pass
    yield

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
TEST_EXTERNAL_JWT_SECRET = "test-external-secret"
TEST_INTERNAL_JWT_SECRET = "test-internal-secret"


class FakeRedis:
    """
    Minimal in-memory Redis stub for tests.
    Implements the subset of commands used by the token blacklist and login lockout modules.
    All values are stored as bytes to match the real client (decode_responses=False).
    """

    def __init__(self):
        self._store: dict = {}
        self._ttls: dict = {}

    async def get(self, key: str):
        return self._store.get(key)

    async def set(self, key: str, value):
        self._store[key] = value if isinstance(value, bytes) else str(value).encode()

    async def setex(self, key: str, ttl: int, value):
        self._store[key] = value if isinstance(value, bytes) else str(value).encode()
        self._ttls[key] = ttl

    async def incr(self, key: str) -> int:
        current = int(self._store.get(key, b"0"))
        new_val = current + 1
        self._store[key] = str(new_val).encode()
        return new_val

    async def expire(self, key: str, ttl: int):
        self._ttls[key] = ttl

    async def ttl(self, key: str) -> int:
        # Return the stored TTL if key exists, -2 if key doesn't exist
        if key not in self._store:
            return -2
        return self._ttls.get(key, -1)

    async def delete(self, *keys):
        for key in keys:
            self._store.pop(key, None)
            self._ttls.pop(key, None)

    async def exists(self, key: str) -> int:
        return 1 if key in self._store else 0

    async def keys(self, pattern: str):
        import fnmatch
        pat = pattern.replace("*", "**")
        return [k for k in self._store if fnmatch.fnmatch(k, pattern)]


@pytest_asyncio.fixture(scope="function")
async def db_session():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def client(db_session):
    fake_redis = FakeRedis()

    async def override_get_db():
        yield db_session

    async def override_get_redis():
        return fake_redis

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


def make_jwt(
    user_id: str,
    tenant_id: str | None,
    roles: list[str],
    secret: str = TEST_EXTERNAL_JWT_SECRET,
    expires_in: int = 3600,
) -> str:
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "roles": roles,
        "is_global": tenant_id is None,
        "exp": datetime.now(timezone.utc) + timedelta(seconds=expires_in),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def make_sysadmin_jwt(
    user_id: str | None = None,
    secret: str = TEST_EXTERNAL_JWT_SECRET,
) -> str:
    return make_jwt(user_id or str(uuid.uuid4()), None, ["SysAdmin"], secret)


def make_manager_jwt(
    user_id: str,
    tenant_id: str,
    secret: str = TEST_EXTERNAL_JWT_SECRET,
) -> str:
    return make_jwt(user_id, tenant_id, ["Business Manager"], secret)
