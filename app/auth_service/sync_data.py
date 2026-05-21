import asyncio
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# We can't easily import from app here without setup, so we'll use raw SQL or minimal models
# For safety, let's use the DB_URL from the env or a default
DB_URL = "postgresql+asyncpg://lms_user:lms_pass@localhost:5433/auth_db"

async def sync():
    engine = create_async_engine(DB_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        # Check ALL users
        res = await session.execute(text("SELECT email, status, is_active FROM users"))
        print("DEBUG | ALL USERS:")
        for row in res:
            print(f"DEBUG | User: {row.email}, Status: {row.status}, IsActive: {row.is_active}")
            
        # Check ALL memberships
        res = await session.execute(text("""
            SELECT u.email, m.tenant_id, m.status, m.is_active 
            FROM users u 
            JOIN tenant_memberships m ON u.id = m.user_id
        """))
        print("DEBUG | ALL MEMBERSHIPS:")
        for row in res:
            print(f"DEBUG | User: {row.email}, Tenant: {row.tenant_id}, Membership Status: {row.status}, Membership IsActive: {row.is_active}")


    
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(sync())
