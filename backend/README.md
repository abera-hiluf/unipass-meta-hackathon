# UniPass AI + AgentX Backend

Backend foundation for a secure digital student identity platform and AgentX, an AI assistant for coordinating university campus services.

## Prerequisites

- Python 3.12+
- Git

## Windows PowerShell setup

From the repository root:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Run the API

Before starting the API, set `JWT_SECRET_KEY` in `backend/.env` to a long random value. The signing secret is required at runtime and is never returned by the API. `JWT_ALGORITHM` and `ACCESS_TOKEN_EXPIRE_MINUTES` may also be configured there; `.env.example` contains placeholders only. Meta document analysis is opt-in via `DOCUMENT_ANALYSIS_PROVIDER=meta` and the backend-only `META_API_KEY`, `META_API_BASE_URL`, and `META_VISION_MODEL` values. It sends submitted image documents to Muse Spark; review provider and data-handling implications before enabling it.

```powershell
uvicorn app.main:app --reload
```

The API is available at `http://127.0.0.1:8000`. Swagger UI is available at `http://127.0.0.1:8000/docs`.

`GET /api/v1/db-health` runs `SELECT 1` through the configured Supabase Session Pooler connection. It returns `200` when PostgreSQL is reachable and a safe `503` response when it is unavailable. The root `/health` endpoint does not depend on PostgreSQL.

## Authentication Endpoints

- `POST /api/v1/auth/register` — Register a student or admin user account (uses Argon2 password hashing). Returns account metadata without credentials.
- `POST /api/v1/auth/login` — Authenticate credentials with Argon2 and receive a scoped JWT access token.
- `GET /api/v1/auth/me` — Retrieve the authenticated account profile (requires `Authorization: Bearer <token>`).

## Institutions and email verification

Authenticated account-email ownership is handled separately from institutional-email verification. Use `GET /api/v1/auth/email-verification`, `POST /api/v1/auth/email-verification/code`, and `POST /api/v1/auth/email-verification/confirm`. Identity-document and capture mutations require a confirmed email. `EMAIL_PROVIDER=none` is the safe default and reports delivery unavailable. To enable SMTP, set `EMAIL_PROVIDER=smtp`, `SMTP_HOST`, and `SMTP_SENDER`, and configure `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_STARTTLS`, `SMTP_SSL`, and `SMTP_TIMEOUT_SECONDS`. Keep SMTP credentials only in the backend environment.

- `GET /api/v1/institutions` — List active institutions.
- `GET /api/v1/institutions/me/selection` and `POST /api/v1/institutions/me/selection` — Read and save the authenticated student's institution selection.
- `POST /api/v1/institutions/{institution_id}/email-verification` — Request verification for an authenticated user's institutional email.
- `POST /api/v1/institutions/email-verification/confirm` — Confirm a single-use verification token.
- `GET /api/v1/institutions/me` — View the authenticated user's own institution affiliations.

The Anna University, BIT Campus, Tiruchirappalli entry is marked development-only and has no trusted email domain configured. Saved institution selection creates no affiliation and does not confirm enrollment. Account-email ownership and institutional-email verification are separate. No email provider is configured by default; configure SMTP before enabling delivery in a non-test environment.

## Identity document upload

- `POST /api/v1/identity/documents` — Upload a private passport or national-ID document for the authenticated user.
- `GET /api/v1/identity/documents/{verification_id}` — View safe processing metadata for the authenticated owner's request.
- `POST /api/v1/identity/documents/{verification_id}/analyze` — Start authenticated analysis for the owner's request.

Uploads are limited to 5 MiB by default and validated using extension, MIME type, and file signature. The development storage provider writes private objects under `backend/.local_storage/`, which is ignored by Git; it does not provide public URLs. Production must configure private object storage with restricted access and short-lived signed URLs. Upload success creates a `PENDING` verification request only; it is not identity approval.

Document analysis always performs local Pillow readability and dimension validation first. The default `DOCUMENT_ANALYSIS_PROVIDER=none` adapter returns `RETRY_REQUIRED`. Setting it to `meta` opts into the Meta Model API adapter, which sends raster documents to the Responses API and validates Muse Spark structured output; PDF image conversion is not implemented. It stores uncertain extracted document type, name, dates, and a private cropped portrait when the model returns valid normalized portrait bounds. Document numbers are never stored raw; the adapter retains only a keyed HMAC fingerprint. Model output is evidence only and does not approve identity. No production liveness or face-matching provider is configured.

The live API smoke test is never run automatically. From `backend/`, use ` $env:RUN_META_LIVE_TEST='1'; python scripts/meta_live_smoke.py` only with a valid local `META_API_KEY`; it sends a synthetic 1×1 PNG and prints only a safe success/failure summary.

## Selfie liveness foundation

Liveness uses `POST /api/v1/identity/verifications/{verification_id}/liveness/challenge`, followed by an authenticated capture submission to `POST /api/v1/identity/verifications/{verification_id}/liveness`. Challenges contain a short-lived randomized blink/turn sequence, are single-use, and are bound to the owning verification. The default provider is unavailable and conservatively returns `REVIEW_REQUIRED`; no liveness engine, face matching, or identity approval is enabled. Captures are private and stored under `liveness/` with configurable size and challenge-expiry limits.

## Face-matching foundation

Face matching uses `POST /api/v1/identity/verifications/{verification_id}/face-match` and `GET /api/v1/identity/verifications/{verification_id}/face-match`. The service retrieves the private document portrait and submitted selfie, validates both images locally, and delegates comparison to a `FaceMatchingAdapter`. No biometric provider is configured by default, so the safe result is `REVIEW_REQUIRED`. Similarity scores are not returned through ordinary API responses, and a match never approves identity. `FACE_MATCH_THRESHOLD` is a review-controlled threshold, not a probability calibration.

## Central verification review

`GET /api/v1/identity/status` returns the authenticated user's safe identity workflow status. Authorized users with the `admin` role can list review cases with `GET /api/v1/identity/reviews` and decide them with `POST /api/v1/identity/reviews/{verification_id}` using `approve`, `reject`, or `resubmit`. Approval requires confirmed institutional enrollment, completed document processing, `LIVE` liveness, and `MATCH` face matching; every decision records reviewer and timestamp metadata plus an audit event. No automatic approval is performed.

The frontend handoff contract, endpoint matrix, response/error conventions, suggested React routes, and incomplete integration boundaries are documented in `../docs/frontend-api.md`.

## Live selfie capture

- `POST /api/v1/identity/verifications/{verification_id}/selfie` — Submit a consented selfie for the authenticated owner.

The standalone development capture screen is at `frontend/selfie-capture.html`. It uses browser camera APIs, requires consent before capture, supports preview/retake, stops camera tracks, and uploads only after confirmation. Selfie uploads are stored privately and marked `SUBMITTED`; they do not perform or claim liveness detection or face matching. Configure retention and private-storage deletion policies before production use.

> **Important**: Account registration and login verify credentials only. They do not constitute identity verification or proof of university enrollment.

## Run tests

```powershell
pytest
```

## Database migrations

Database migrations are managed via Alembic:

- `0001_initial_models`: Initial users, student profiles, identity verifications, and audit logs tables.
- `0002_centralized_identity`: Verified attributes (`date_of_birth`, document type, HMAC fingerprint, status lifecycle).
- `0003_add_user_hashed_password`: Added `hashed_password` column to `users`.
- `0004_institution_email_verification`: Adds development-only institution configuration, user affiliations, and hashed email-verification challenges.
- No new migration is required for document upload; it reuses the existing `identity_verifications.document_storage_key` and tracking fields.
- `0006_document_analysis`: Adds analysis metadata, safe extracted fields, portrait storage references, and expanded processing statuses.
- `0008_liveness_tracking`: Adds liveness challenge hashes, expiry/use tracking, private capture references, assessment state, and safe reason/provider metadata.
- `0009_face_matching`: Adds face-matching assessment state, non-public score storage, provider/reason metadata, and timestamps.
- `0007_selfie_capture`: Adds separate selfie-submission status, consent timestamp, submission timestamp, reason code, and private storage reference.
- `0010_email_ownership`: Adds authenticated account-email verification challenges and persists a student's selected institution without creating an affiliation.
- `0011_document_metadata`: Persists model-extracted document type and expiration date.

To inspect migration status:

```powershell
alembic current
```

To apply pending migrations (requires explicit approval before running on live Supabase):

```powershell
alembic upgrade head
```
