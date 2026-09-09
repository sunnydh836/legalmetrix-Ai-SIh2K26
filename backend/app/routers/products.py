from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.core.database import get_db
from app.models.product import Product
from app.models.user import User
from app.schemas.scan import ProductResponse

router = APIRouter(prefix="/products", tags=["Products"])


@router.get("/by-barcode/{barcode}", response_model=ProductResponse)
def get_product_by_barcode(
    barcode: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Lookup existing product details by exact barcode match for autofill in scan creation.
    Protected: Authenticated users.
    """
    clean_barcode = barcode.strip()
    if not clean_barcode:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Barcode parameter cannot be empty.",
        )

    product = db.query(Product).filter(Product.barcode == clean_barcode).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No product found with matching barcode.",
        )

    return ProductResponse(
        id=product.id,
        name=product.name,
        brand=product.brand,
        category=product.category,
        barcode=product.barcode,
        manufacturer_name=product.manufacturer_name,
        created_at=product.created_at,
        updated_at=product.updated_at,
    )
