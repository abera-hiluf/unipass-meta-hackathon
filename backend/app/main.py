import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.api.v1.router import router as v1_router
from app.core.config import settings


app = FastAPI(
    title="UniPass AI + AgentX API",
    version=settings.app_version,
    description="Backend foundation for the UniPass AI + AgentX platform.",
)
logger = logging.getLogger(__name__)


@app.exception_handler(SQLAlchemyError)
async def handle_database_error(_request: Request, error: SQLAlchemyError) -> JSONResponse:
    logger.error(
        "Database request failed",
        exc_info=(type(error), error, error.__traceback__),
    )
    return JSONResponse(
        status_code=503,
        content={"detail": "Database request failed. Check server logs."},
    )

# Never enable unrestricted CORS implicitly in production.
allowed_origins = settings.cors_origins
if settings.environment.lower() == "production":
    allowed_origins = [origin for origin in allowed_origins if origin != "*"]
else:
    local_origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    allowed_origins = list(dict.fromkeys([*allowed_origins, *local_origins]))

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
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
