from sqlalchemy import Column, String
from app.core.database import Base
from app.models.base import TimestampMixin, generate_uuid_str


class Product(Base, TimestampMixin):
    __tablename__ = "products"

    id = Column(String(36), primary_key=True, default=generate_uuid_str, index=True)
    name = Column(String(255), nullable=False, index=True)
    brand = Column(String(255), nullable=True, index=True)
    category = Column(String(100), nullable=True, index=True)
    barcode = Column(String(100), unique=True, nullable=True, index=True)
    manufacturer_name = Column(String(255), nullable=True)
