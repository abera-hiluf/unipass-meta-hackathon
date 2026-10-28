from fastapi import APIRouter


router = APIRouter()


@router.get("/health")
def versioned_health_check() -> dict[str, str]:
    return {"status": "healthy", "version": "v1"}
