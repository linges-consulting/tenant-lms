from sqlalchemy import String, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base_class import Base

class CertificateTemplate(Base):
    """
    Represents an HTML-based certificate template.
    """
    __tablename__ = "certificate_templates"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    html_content: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    tenant_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
