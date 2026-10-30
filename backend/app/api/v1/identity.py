import uuid

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db import get_db
from app.models.identity_verification import IdentityVerification
from app.models.user import User
from app.schemas.identity import IdentityDocumentResponse
from app.schemas.document_analysis import DocumentAnalysisResponse
from app.schemas.selfie import SelfieSubmissionResponse
from app.services.analysis import DocumentAnalysisAdapter, get_document_analysis_adapter, start_document_analysis
from app.services.documents import create_identity_verification, get_owned_identity_verification
from app.services.storage import PrivateObjectStorage, get_storage
from app.services.selfies import submit_selfie


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


@router.post("/documents/{verification_id}/analyze", response_model=DocumentAnalysisResponse)
def analyze_identity_document(
    verification_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: PrivateObjectStorage = Depends(get_storage),
    adapter: DocumentAnalysisAdapter = Depends(get_document_analysis_adapter),
) -> dict:
    return start_document_analysis(
        db=db,
        user=current_user,
        verification_id=verification_id,
        storage=storage,
        adapter=adapter,
    )


@router.post("/verifications/{verification_id}/selfie", response_model=SelfieSubmissionResponse, status_code=201)
async def submit_identity_selfie(
    verification_id: uuid.UUID,
    consent: bool = Form(...),
    capture_state: str = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: PrivateObjectStorage = Depends(get_storage),
) -> dict:
    verification = await submit_selfie(
        db=db,
        user=current_user,
        verification_id=verification_id,
        upload=file,
        consent=consent,
        capture_state=capture_state,
        storage=storage,
    )
    return {
        "verification_id": verification.id,
        "selfie_status": verification.selfie_status,
        "selfie_reason_code": verification.selfie_reason_code,
        "selfie_submitted_at": verification.selfie_submitted_at,
    }
