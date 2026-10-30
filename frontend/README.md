# UniPass AI frontend

This folder now contains the React/Vite frontend foundation. The original `selfie-capture.html` remains available as a standalone camera prototype; the React app does not yet replace that capture flow.

The React app uses Tailwind CSS, React Router, Axios, and Lucide React. It calls only endpoints documented in `../docs/frontend-api.md`. The bearer JWT is kept in `sessionStorage` because the current backend does not provide HttpOnly-cookie authentication; this is a development limitation, not a production recommendation.

## Run

```bash
npm install
cp .env.example .env
npm run dev
```

Set `VITE_API_BASE_URL` in `.env` when the backend is not at `http://localhost:8000`. Never put Meta, database, JWT, or other backend secrets in frontend environment variables.

Build for a production-like check with `npm run build`.
