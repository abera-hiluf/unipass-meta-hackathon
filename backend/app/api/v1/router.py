from fastapi import APIRouter

from app.api.v1.db_health import router as db_health_router


router = APIRouter()
router.include_router(db_health_router)


@router.get("/health")
def versioned_health_check() -> dict[str, str]:
    return {"status": "healthy", "version": "v1"}
