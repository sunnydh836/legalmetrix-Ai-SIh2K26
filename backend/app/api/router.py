from fastapi import APIRouter
from app.routers.health import router as health_router
from app.routers.auth import router as auth_router
from app.routers.scans import router as scans_router
from app.routers.products import router as products_router
from app.routers.declarations import router as declarations_router

api_router = APIRouter()

# Register endpoint routers
api_router.include_router(health_router, prefix="", tags=["Health"])
api_router.include_router(auth_router, prefix="", tags=["Authentication"])
api_router.include_router(scans_router, prefix="", tags=["Scans"])
api_router.include_router(products_router, prefix="", tags=["Products"])
api_router.include_router(declarations_router, prefix="", tags=["Declarations"])
