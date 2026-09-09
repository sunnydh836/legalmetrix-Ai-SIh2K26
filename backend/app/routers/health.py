from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["Health"])


class HealthResponse(BaseModel):
    status: str = "healthy"


class RootResponse(BaseModel):
    name: str = "LegalMetrix AI API"
    status: str = "running"


@router.get("/health", response_model=HealthResponse)
def health_check():
    """Health check endpoint for container orchestrators and load balancers."""
    return {"status": "healthy"}
