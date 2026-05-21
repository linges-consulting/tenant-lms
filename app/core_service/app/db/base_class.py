import uuid
from datetime import datetime, timezone
from typing import Any, Optional
from sqlalchemy import MetaData, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

naming_convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}

from sqlalchemy.ext.declarative import declared_attr

class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=naming_convention)
    
    @declared_attr.directive
    def __tablename__(cls) -> str:
        return cls.__name__.lower()
        
    id: Mapped[str] = mapped_column(default=lambda: str(uuid.uuid4()), primary_key=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc), 
        onupdate=lambda: datetime.now(timezone.utc)
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), default=None)

