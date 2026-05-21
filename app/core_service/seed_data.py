import asyncio
import os
import sys
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from datetime import datetime

# Add app to path
sys.path.append(os.getcwd())

from app.core.config import settings


async def ensure_training(conn, id: str, tenant_id: str, title: str, category: str, duration: str, is_published: bool = True):
    # use naive UTC datetimes for direct SQL inserts to avoid driver timezone issues
    now = datetime.utcnow()
    await conn.execute(
        text(
            """
            INSERT INTO trainings (id, tenant_id, title, category, duration, is_published, version, requires_certificate, created_at, updated_at)
            VALUES (:id, :tenant_id, :title, :category, :duration, :is_published, :version, :requires_certificate, :created_at, :updated_at)
            ON CONFLICT (id) DO UPDATE SET title = EXCLUDED.title, category = EXCLUDED.category, duration = EXCLUDED.duration, is_published = EXCLUDED.is_published, version = EXCLUDED.version, requires_certificate = EXCLUDED.requires_certificate
            """
        ),
        {
            "id": id,
            "tenant_id": tenant_id,
            "title": title,
            "category": category,
            "duration": duration,
            "is_published": is_published,
            "version": 1,
            "requires_certificate": True,
            "created_at": now,
            "updated_at": now,
        },
    )


async def seed():
    engine = create_async_engine(settings.ASYNC_DB_URL)
    async def clear_tables(conn):
        tables = [
            "training_history",
            "progress",
            "enrollments",
            "chapters",
            "modules",
            "trainings",
        ]
        # TRUNCATE preserves schema while clearing data and resetting sequences
        for t in tables:
            # check existence using to_regclass to avoid aborting transaction on missing tables
            res = await conn.execute(text("SELECT to_regclass(:name)"), {"name": t})
            exists = res.scalar()
            if exists:
                await conn.execute(text(f"TRUNCATE TABLE {t} RESTART IDENTITY CASCADE;"))
                print(f"Truncated table: {t}")
            else:
                print(f"Skipping truncate for {t} (does not exist)")

    async with engine.begin() as conn:
        print("Seeding Core Service Data (trainings)...")
        # clear core tables first to ensure clean slate
        await clear_tables(conn)

        cp_id = "tenant-cp"
        vm_id = "tenant-vm"

        await ensure_training(conn, "6ea3ebf4-3c06-44da-8a93-d26231469fbb", cp_id, "CP Security training", "Compliance", "30m", True)
        await ensure_training(conn, "f063fff4-50a4-4746-ad0c-b5d982adef1e", vm_id, "VM Sales Kickoff", "Sales", "1h", True)

    print("Core Service Seeding complete.")


if __name__ == "__main__":
    asyncio.run(seed())
