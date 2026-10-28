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

```powershell
uvicorn app.main:app --reload
```

The API is available at `http://127.0.0.1:8000`. Swagger UI is available at `http://127.0.0.1:8000/docs`.

## Run tests

```powershell
pytest
```

The current health checks do not require PostgreSQL. Database integration, authentication, and the official Meta Model API provider will be added in later stages. Meta models remain the planned provider for AgentX; no live Meta API calls are made by this foundation.
