from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.core.enums import ImageType, ScanStatus, UserRole


# Product schemas for Scan Session
class ProductBase(BaseModel):
    name: Optional[str] = None
    brand: Optional[str] = None
    category: Optional[str] = None
    barcode: Optional[str] = None
    manufacturer_name: Optional[str] = None


class ProductCreate(ProductBase):
    pass


class ProductResponse(ProductBase):
    id: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# Inspector minimal schema
class InspectorResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: UserRole

    model_config = ConfigDict(from_attributes=True)


# Scan Image schemas
class ScanImageBase(BaseModel):
    image_type: ImageType = ImageType.FRONT
    original_filename: Optional[str] = None
    mime_type: str = "image/jpeg"
    file_size: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    display_order: int = 0


class ScanImageCreate(ScanImageBase):
    scan_session_id: str
    file_path: str
    stored_filename: Optional[str] = None
    sha256: Optional[str] = None


class ScanImageResponse(ScanImageBase):
    id: str
    scan_session_id: str
    created_at: datetime
    preview_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# Scan Session schemas
class ScanSessionBase(BaseModel):
    product_id: Optional[str] = None
    inspector_id: Optional[str] = None


class ScanSessionCreate(BaseModel):
    product: Optional[ProductCreate] = None


class ScanImageOrderRequest(BaseModel):
    image_ids: List[str] = Field(..., min_length=1, description="Ordered list of ScanImage IDs")


class ScanSessionResponse(BaseModel):
    id: str
    scan_code: str
    status: ScanStatus
    product: Optional[ProductResponse] = None
    inspector: Optional[InspectorResponse] = None
    images: List[ScanImageResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ScanListResponse(BaseModel):
    items: List[ScanSessionResponse]
    total: int
