import uuid

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db import get_db
from app.models.identity_verification import IdentityVerification
from app.models.user import User
from app.schemas.identity import IdentityDocumentResponse
from app.services.documents import create_identity_verification, get_owned_identity_verification
from app.services.storage import PrivateObjectStorage, get_storage


router = APIRouter(prefix="/identity", tags=["Identity Documents"])


@router.post("/documents", response_model=IdentityDocumentResponse, status_code=201)
async def upload_identity_document(
    document_type: str = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: PrivateObjectStorage = Depends(get_storage),
) -> IdentityVerification:
    return await create_identity_verification(
        db=db,
        user=current_user,
        upload=file,
        document_type=document_type,
        storage=storage,
    )


@router.get("/documents/{verification_id}", response_model=IdentityDocumentResponse)
def get_identity_document_status(
    verification_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IdentityVerification:
    return get_owned_identity_verification(db, current_user, verification_id)
