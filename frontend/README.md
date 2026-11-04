# UniPass AI frontend

This folder now contains the React/Vite frontend foundation. The original `selfie-capture.html` remains available as a standalone camera prototype; the React app does not yet replace that capture flow.

The React app uses Tailwind CSS, React Router, Axios, and Lucide React. It calls only endpoints documented in `../docs/frontend-api.md`. The bearer JWT is kept in `sessionStorage` because the current backend does not provide HttpOnly-cookie authentication; this is a development limitation, not a production recommendation.

## Run

```bash
npm install
cp .env.example .env
npm run dev
```

In development, API requests use the Vite proxy to `http://127.0.0.1:8000` by default, avoiding browser CORS and `localhost`/`127.0.0.1` origin mismatches. Set `VITE_API_BASE_URL` in `.env` to an absolute API origin only when using a different backend; direct cross-origin requests require that backend to allow the frontend origin. Never put Meta, database, JWT, or other backend secrets in frontend environment variables.

Build for a production-like check with `npm run build`.
