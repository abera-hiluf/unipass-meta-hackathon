UniPass AI
Your Identity, Your Control.

UniPass AI is an AI-assisted digital identity platform concept designed
to simplify identity verification across university campuses. It aims to
let students establish a reusable identity and, in a future
connected-campus ecosystem, share only the information required by
independent campus services---with their consent.
Project status: Hackathon prototype. Some integrations and
production capabilities described as goals below are not yet fully
implemented or independently verified. Do not use this prototype for
real identity verification or sensitive personal documents.

The problem
Students may be asked to submit the same identity information repeatedly
when using different university services. This can create fragmented
experiences, repetitive manual checks, and unnecessary exposure of
personal information.

UniPass AI explores a centralized identity layer that can support
multiple independent campus applications while keeping identity
verification, institutional eligibility, and application authorization
as distinct concerns.
Proposed solution
UniPass AI brings together:
- Centralized student account: A single account and identity
  workspace.
- Identity workflow: A structured process for institution
  information, identity document submission, selfie capture, liveness
  assessment, and final status review.
- AI-assisted document understanding: An integration foundation
  for multimodal AI to assist with document-related processing.
- Privacy-conscious design: Private evidence handling,
  authenticated access, and an emphasis on minimizing information
  shared with other services.
- Connected-campus vision: A future integration model in which
  independent applications request only the identity claims they need,
  subject to student consent.
Key design principles
1. One reusable identity: Reduce repeated identity onboarding
   across campus services.
2. Student control: Make data-sharing decisions explicit and
   understandable.
3. Separation of concerns: Selecting an institution is not proof of
   enrollment; document analysis is not identity approval; email
   confirmation is not institutional eligibility.
4. Human and backend-controlled decisions: AI outputs must not
   independently approve a person's identity.
5. Privacy by design: Protect identity evidence and avoid exposing
   sensitive data in routine API responses or logs.
Technology stack
The prototype has been developed using the following technologies:
  Layer                               Technologies
  Frontend                            React, Vite, Tailwind CSS

  Backend                             Python, FastAPI

  Database                            PostgreSQL (Supabase-hosted)

  Authentication                      JWT-based authentication, Argon2
password hashing

  AI integration                      Meta Model API integration
foundation; Muse Spark and SAM 3.1
explored
API documentation                   FastAPI / OpenAPI (Swagger UI)
Technology and integration status may change as the project evolves.
Refer to the current source code and configuration for the definitive
implementation.
Meta AI exploration
UniPass AI explores Meta's multimodal AI capabilities as potential
support for document-related workflows:
- Muse Spark: Intended for visual understanding, reasoning, and
  structured document-analysis assistance.
- SAM 3.1: Explored for image segmentation and visual-region
  processing.
These models are not presented as biometric identity-verification
systems. Document understanding, face matching, liveness detection, and
institutional enrollment verification are separate tasks and require
appropriate dedicated mechanisms and validation.

The existence of an API integration layer does not by itself mean that a
live model call or production integration has been completed. Check the
current implementation and test results before relying on any model
capability.
Identity workflow
The intended five-step student journey is:
1. Institution information --- enter account and institution
   information.
2. Identity document --- submit a supported identity document for
   processing.
3. Selfie capture --- capture and submit a selfie.
4. Liveness --- complete a liveness check when a suitable provider
   is configured.
5. Final identity status --- review the backend-reported status of
   each verification component.
The prototype may operate in a clearly identified local demonstration
mode. Demo-mode confirmation must not be represented as genuine email
ownership verification, institutional enrollment, biometric
verification, or identity approval.
Current limitations
This is a hackathon prototype, not a production identity provider.
Depending on the current configuration and implementation, the following
capabilities may be incomplete or unavailable:
- Production email delivery and genuine email ownership verification.
- Authoritative institutional enrollment verification or an official
  university integration.
- Production-grade document OCR and validation.
- Production liveness detection and face-matching providers.
- Complete OAuth 2.0 / OpenID Connect provider functionality.
- Connected-application registration, consent management, scopes, and
  revocation.
- AgentX campus-service execution and tool integrations.
- Production security, privacy, compliance, monitoring, and
  operational review.
Do not treat a selected institution, uploaded document, demo
confirmation, pending analysis, or unavailable provider as a successful
identity verification.
Running locally
These instructions assume the repository contains backend/ and
frontend/ directories and that the required dependencies and
environment configuration have been set up.
Prerequisites
- Python 3.12 or a compatible version supported by the backend
  dependencies.
- Node.js and npm.
- Access to a configured PostgreSQL database (the project has used
  Supabase PostgreSQL).
- Required environment variables configured locally.
Never commit .env files, API keys, database credentials, JWT secrets,
or identity documents.
1. Start the backend
From the repository root, open a terminal:
cd backend
Activate the Windows Git Bash virtual environment:
source .venv/Scripts/activate
Start FastAPI:
python -m uvicorn app.main:app --reload
Backend: http://127.0.0.1:8000

API documentation: http://127.0.0.1:8000/docs
2. Start the frontend
Open a second terminal:
cd frontend
npm install
npm run dev
Vite typically serves the frontend at http://localhost:5173. Use the
URL printed in your terminal if it differs.
Configuration
Configure the backend database connection, JWT settings, CORS origins,
storage settings, and any optional AI/provider settings using the
environment-variable names expected by the current source code.

For a local demonstration, use only synthetic test accounts and
synthetic identity documents. If a demo-mode setting exists, keep it
restricted to local development and ensure it cannot be enabled in
production.
Security and privacy notes
- Keep API keys and secrets on the backend.
- Use private storage for identity documents.
- Enforce authentication and per-user authorization on identity
  endpoints.
- Validate file type, content, and size on the server.
- Avoid logging passwords, tokens, identity-document contents, raw
  document numbers, biometric data, or storage credentials.
- Do not expose identity evidence through public URLs.
- Do not use this prototype to make consequential identity decisions.
- Obtain appropriate consent and legal/security review before handling
  real people's identity or biometric data.
Demo
Project demo video: Add your public or unlisted video URL here.

Public repository: Add the repository URL here.

For the hackathon demonstration, show only features that work in the
submitted build. Clearly explain any simulated or unavailable
integrations.
Roadmap
- Complete and test a secure OAuth 2.0 / OpenID Connect flow for
  independent campus applications.
- Implement user-facing consent, scope selection,
  connected-application management, and revocation.
- Integrate and evaluate suitable document-analysis, liveness, and
  face-matching providers.
- Establish an authoritative institutional eligibility integration.
- Complete privacy, security, accessibility, and production-readiness
  reviews.
- Build separate demo campus applications to validate reusable
  identity and consent-based access.
Acknowledgements
Built for the Meta Global AI Developer Hackathon 2026.

Developer: Abera Hiluf Teshale
UniPass AI --- Your Identity, Your Control.
