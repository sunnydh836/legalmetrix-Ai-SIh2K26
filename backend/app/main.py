from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.router import api_router
from app.core.config import settings
from app.core.constants import APP_DESCRIPTION, APP_TITLE, APP_VERSION
from app.routers.health import HealthResponse, RootResponse

app = FastAPI(
    title=APP_TITLE,
    description=APP_DESCRIPTION,
    version=APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS Middleware configuration
if settings.CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.get("/", response_model=RootResponse, tags=["Root"])
def root():
    """Root endpoint verifying API service status."""
    return {"name": "LegalMetrix AI API", "status": "running"}


@app.get("/health", response_model=HealthResponse, tags=["Health"])
def health():
    """Global health check endpoint."""
    return {"status": "healthy"}


# Mount centralized versioned API router
app.include_router(api_router, prefix=settings.API_V1_STR)
