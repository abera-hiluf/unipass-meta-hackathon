import uuid

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_email_verified_user
from app.db import get_db
from app.models.identity_verification import IdentityVerification
from app.models.user import User
from app.schemas.identity import IdentityDocumentResponse
from app.schemas.document_analysis import DocumentAnalysisResponse
from app.schemas.selfie import SelfieSubmissionResponse
from app.schemas.liveness import LivenessChallengeResponse, LivenessResultResponse
from app.schemas.face_matching import FaceMatchResponse
from app.schemas.review import IdentityReviewRequest, IdentityReviewResponse, IdentityStatusResponse
from app.services.analysis import DocumentAnalysisAdapter, get_document_analysis_adapter, start_document_analysis
from app.services.documents import create_identity_verification, get_owned_identity_verification
from app.services.storage import PrivateObjectStorage, get_storage
from app.services.selfies import submit_selfie
from app.services.liveness import LivenessAdapter, get_liveness_adapter, issue_liveness_challenge, submit_liveness_capture
from app.services.face_matching import FaceMatchingAdapter, get_face_matching_adapter, start_face_matching
from app.services.verification_review import identity_status, list_review_cases, require_reviewer, review_case


router = APIRouter(prefix="/identity", tags=["Identity Documents"])


@router.post("/documents", response_model=IdentityDocumentResponse, status_code=201)
async def upload_identity_document(
    document_type: str = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_email_verified_user),
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
    current_user: User = Depends(get_email_verified_user),
    db: Session = Depends(get_db),
) -> IdentityVerification:
    return get_owned_identity_verification(db, current_user, verification_id)


@router.post("/documents/{verification_id}/analyze", response_model=DocumentAnalysisResponse)
def analyze_identity_document(
    verification_id: uuid.UUID,
    current_user: User = Depends(get_email_verified_user),
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
    current_user: User = Depends(get_email_verified_user),
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


@router.post("/verifications/{verification_id}/liveness/challenge", response_model=LivenessChallengeResponse)
def create_liveness_challenge(
    verification_id: uuid.UUID,
    current_user: User = Depends(get_email_verified_user),
    db: Session = Depends(get_db),
) -> dict:
    return issue_liveness_challenge(db, current_user, verification_id)


@router.post("/verifications/{verification_id}/liveness", response_model=LivenessResultResponse)
async def submit_identity_liveness(
    verification_id: uuid.UUID,
    challenge_id: str = Form(...),
    consent: bool = Form(...),
    capture_state: str = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_email_verified_user),
    db: Session = Depends(get_db),
    storage: PrivateObjectStorage = Depends(get_storage),
    adapter: LivenessAdapter = Depends(get_liveness_adapter),
) -> dict:
    verification = await submit_liveness_capture(
        db=db,
        user=current_user,
        verification_id=verification_id,
        challenge_id=challenge_id,
        consent=consent,
        capture_state=capture_state,
        upload=file,
        storage=storage,
        adapter=adapter,
    )
    return {
        "verification_id": verification.id,
        "liveness_status": verification.liveness_status,
        "reason_code": verification.liveness_reason_code,
        "provider": verification.liveness_provider,
        "completed_at": verification.liveness_completed_at,
    }


@router.get("/verifications/{verification_id}/liveness", response_model=LivenessResultResponse)
def get_identity_liveness(
    verification_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    verification = db.get(IdentityVerification, verification_id)
    if verification is None or verification.user_id != current_user.id:
        from fastapi import HTTPException, status

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Verification not found")
    return {
        "verification_id": verification.id,
        "liveness_status": verification.liveness_status,
        "reason_code": verification.liveness_reason_code,
        "provider": verification.liveness_provider,
        "completed_at": verification.liveness_completed_at,
    }


@router.post("/verifications/{verification_id}/face-match", response_model=FaceMatchResponse)
def run_identity_face_match(
    verification_id: uuid.UUID,
    current_user: User = Depends(get_email_verified_user),
    db: Session = Depends(get_db),
    storage: PrivateObjectStorage = Depends(get_storage),
    adapter: FaceMatchingAdapter = Depends(get_face_matching_adapter),
) -> dict:
    return start_face_matching(db, current_user, verification_id, storage, adapter)


@router.get("/verifications/{verification_id}/face-match", response_model=FaceMatchResponse)
def get_identity_face_match(
    verification_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    verification = db.get(IdentityVerification, verification_id)
    if verification is None or verification.user_id != current_user.id:
        from fastapi import HTTPException, status

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Verification not found")
    return {
        "verification_id": verification.id,
        "status": verification.face_match_status,
        "reason_code": verification.face_match_reason_code,
        "provider": verification.face_match_provider,
        "completed_at": verification.face_match_completed_at,
    }


@router.get("/status", response_model=IdentityStatusResponse)
def get_identity_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    return identity_status(db, current_user)


@router.get("/reviews", response_model=list[dict])
def list_identity_reviews(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    return list_review_cases(db, current_user)


@router.post("/reviews/{verification_id}", response_model=IdentityReviewResponse)
def review_identity_case(
    verification_id: uuid.UUID,
    payload: IdentityReviewRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    return review_case(db, current_user, verification_id, payload.decision, payload.reason)
