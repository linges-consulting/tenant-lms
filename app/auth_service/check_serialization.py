import asyncio
from sqlalchemy.ext.asyncio import create_async_session_maker, create_async_engine
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.models.user import User
from app.models.membership import TenantMembership
from app.schemas.user import User as UserSchema
import json
from pydantic import TypeAdapter

async def check_serialization():
    engine = create_async_engine("postgresql+asyncpg://lms_user:lms_pass@postgres/auth_db")
    async_session = create_async_session_maker(engine)
    
    async with async_session() as db:
        result = await db.execute(
            select(User)
            .options(selectinload(User.memberships))
            .limit(1)
        )
        user = result.scalar_one_or_none()
        if not user:
            print("No users found")
            return
            
        print(f"User: {user.email}")
        print(f"Memberships on model: {[m.tenant_id for m in user.memberships]}")
        
        # Serialize
        schema = UserSchema.model_validate(user)
        print(f"Members on schema: {schema.members}")
        
        # Check specific membership data
        if schema.members:
            m = schema.members[0]
            print(f"Membership data: is_manager={m.is_business_manager}, is_creator={m.is_training_creator}, is_employee={m.is_employee}")

if __name__ == "__main__":
    asyncio.run(check_serialization())
