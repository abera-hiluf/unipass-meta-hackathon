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

Before starting the API, set `JWT_SECRET_KEY` in `backend/.env` to a long random value. The signing secret is required at runtime and is never returned by the API. `JWT_ALGORITHM` and `ACCESS_TOKEN_EXPIRE_MINUTES` may also be configured there; `.env.example` contains placeholders only.

```powershell
uvicorn app.main:app --reload
```

The API is available at `http://127.0.0.1:8000`. Swagger UI is available at `http://127.0.0.1:8000/docs`.

`GET /api/v1/db-health` runs `SELECT 1` through the configured Supabase Session Pooler connection. It returns `200` when PostgreSQL is reachable and a safe `503` response when it is unavailable. The root `/health` endpoint does not depend on PostgreSQL.

## Authentication Endpoints

- `POST /api/v1/auth/register` — Register a student or admin user account (uses Argon2 password hashing). Returns account metadata without credentials.
- `POST /api/v1/auth/login` — Authenticate credentials with Argon2 and receive a scoped JWT access token.
- `GET /api/v1/auth/me` — Retrieve the authenticated account profile (requires `Authorization: Bearer <token>`).

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

To inspect migration status:

```powershell
alembic current
```

To apply pending migrations (requires explicit approval before running on live Supabase):

```powershell
alembic upgrade head
```
