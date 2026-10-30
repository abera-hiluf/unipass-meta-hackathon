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

Before starting the API, set `JWT_SECRET_KEY` in `backend/.env` to a long random value. The signing secret is required at runtime and is never returned by the API. `JWT_ALGORITHM` and `ACCESS_TOKEN_EXPIRE_MINUTES` may also be configured there; `.env.example` contains placeholders only. The reserved Meta configuration uses `META_API_KEY`, `META_API_BASE_URL`, `META_SAM_MODEL`, and `META_VISION_MODEL`; no Meta request is made by the current implementation.

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

- `GET /api/v1/institutions` — List active institutions.
- `POST /api/v1/institutions/{institution_id}/email-verification` — Request verification for an authenticated user's institutional email.
- `POST /api/v1/institutions/email-verification/confirm` — Confirm a single-use verification token.
- `GET /api/v1/institutions/me` — View the authenticated user's own institution affiliations.

The Anna University, BIT Campus, Tiruchirappalli entry is marked development-only and has no trusted email domain configured. Email verification does not confirm enrollment or grant campus-service access. No email provider is configured by default; set up a real provider before enabling delivery in a non-test environment.

## Identity document upload

- `POST /api/v1/identity/documents` — Upload a private passport or national-ID document for the authenticated user.
- `GET /api/v1/identity/documents/{verification_id}` — View safe processing metadata for the authenticated owner's request.
- `POST /api/v1/identity/documents/{verification_id}/analyze` — Start authenticated analysis for the owner's request.

Uploads are limited to 5 MiB by default and validated using extension, MIME type, and file signature. The development storage provider writes private objects under `backend/.local_storage/`, which is ignored by Git; it does not provide public URLs. Production must configure private object storage with restricted access and short-lived signed URLs. Upload success creates a `PENDING` verification request only; no OCR, biometric processing, or identity approval is performed.

Document analysis always performs local Pillow readability and dimension validation first. The default `DOCUMENT_ANALYSIS_PROVIDER=none` adapter returns `RETRY_REQUIRED`. Setting it to `meta` opts into the Meta Model API adapter, which sends image documents to the Responses API and validates Muse Spark structured output; it does not process PDFs, selfies, or approve identity. Document numbers are never stored raw; the adapter retains only a keyed HMAC fingerprint. SAM 3.1 is reserved for a later segmentation adapter because its documented output is streamed special-token geometry and is not OCR.

The live API smoke test is never run automatically. From `backend/`, use ` $env:RUN_META_LIVE_TEST='1'; python scripts/test_meta_live.py` only with a valid local `META_API_KEY`; it sends a synthetic 1×1 PNG and prints only a safe success/failure summary.

## Selfie liveness foundation

Liveness uses `POST /api/v1/identity/verifications/{verification_id}/liveness/challenge`, followed by an authenticated capture submission to `POST /api/v1/identity/verifications/{verification_id}/liveness`. Challenges contain a short-lived randomized blink/turn sequence, are single-use, and are bound to the owning verification. The default provider is unavailable and conservatively returns `REVIEW_REQUIRED`; no liveness engine, face matching, or identity approval is enabled. Captures are private and stored under `liveness/` with configurable size and challenge-expiry limits.

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
- `0007_selfie_capture`: Adds separate selfie-submission status, consent timestamp, submission timestamp, reason code, and private storage reference.

To inspect migration status:

```powershell
alembic current
```

To apply pending migrations (requires explicit approval before running on live Supabase):

```powershell
alembic upgrade head
```
