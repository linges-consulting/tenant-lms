import asyncio
import os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Config
DB_URL = os.getenv("DB_URL", "postgresql+asyncpg://lms_user:lms_pass@localhost:5433/auth_db")

async def sync_statuses():
    engine = create_async_engine(DB_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    print(f"Connecting to {DB_URL}...")
    async with async_session() as session:
        # 1. Users who are globally ACTIVE should have ACTIVE memberships (unless deactivated)
        res1 = await session.execute(text("""
            UPDATE tenant_memberships 
            SET status = 'ACTIVE' 
            WHERE status = 'PENDING' 
            AND user_id IN (SELECT id FROM users WHERE status = 'ACTIVE');
        """))
        print(f"Updated {res1.rowcount} memberships to ACTIVE for globally registered users.")

        # 2. Users who are globally PENDING should have PENDING memberships
        res2 = await session.execute(text("""
            UPDATE tenant_memberships 
            SET status = 'PENDING' 
            WHERE status = 'ACTIVE' 
            AND user_id IN (SELECT id FROM users WHERE status = 'PENDING');
        """))
        print(f"Updated {res2.rowcount} memberships to PENDING for users yet to register.")

        await session.commit()
    
    print("Done.")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(sync_statuses())
