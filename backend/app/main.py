from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import router as v1_router
from app.core.config import settings


app = FastAPI(
    title="UniPass AI + AgentX API",
    version=settings.app_version,
    description="Backend foundation for the UniPass AI + AgentX platform.",
)

# Never enable unrestricted CORS implicitly in production.
allowed_origins = settings.cors_origins
if settings.environment.lower() == "production":
    allowed_origins = [origin for origin in allowed_origins if origin != "*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root() -> dict[str, str]:
    return {
        "name": settings.app_name,
        "description": "Backend foundation for UniPass AI + AgentX.",
        "docs": "/docs",
    }


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "healthy"}


app.include_router(v1_router, prefix="/api/v1")
