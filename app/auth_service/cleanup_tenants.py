import asyncio
import os
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy import text

# Database connection details
db_user = os.getenv("POSTGRES_USER", "lms_user")
db_pass = os.getenv("POSTGRES_PASSWORD", "lms_pass")
DB_URL = os.getenv("ASYNC_DB_URL") or os.getenv("DB_URL") or f"postgresql+asyncpg://{db_user}:{db_pass}@postgres:5432/auth_db"

async def cleanup_creator_tenant():
    engine = create_async_engine(DB_URL)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session() as session:
        print("🔍 Checking for 'Creator Tenant' (tenant-1)...")
        
        # 1. Delete memberships associated with tenant-1
        memberships_deleted = await session.execute(
            text("DELETE FROM tenant_memberships WHERE tenant_id = 'tenant-1'")
        )
        print(f"✅ Deleted {memberships_deleted.rowcount} memberships for tenant-1.")

        # 2. Delete the tenant itself
        tenant_deleted = await session.execute(
            text("DELETE FROM tenants WHERE id = 'tenant-1'")
        )
        print(f"✅ Deleted tenant-1: {tenant_deleted.rowcount}")

        await session.commit()
    
    await engine.dispose()
    print("✨ Cleanup complete.")

if __name__ == "__main__":
    asyncio.run(cleanup_creator_tenant())
