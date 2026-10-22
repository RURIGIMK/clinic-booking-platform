# Clinic Booking Platform

A full-stack clinic appointment booking demo for the Implementation Engineer take-home assessment. The project focuses on clear patient workflows, booking integrity, explicit API errors, automated checks and deployment readiness.

## Current status

- FastAPI REST API and SQLAlchemy data models committed on feature/booking-foundation.
- React and TypeScript appointment interface committed.
- Synthetic seed data and initial booking lifecycle tests committed.
- GitHub Actions CI workflow committed.
- Local execution and tests still need to be run and verified before deployment.
- AWS, Cloudflare and hosted PostgreSQL are intentionally not configured yet.

## Architecture

- Frontend: React, TypeScript, Vite and Lucide icons.
- API: FastAPI; interactive API docs at /docs.
- Persistence: SQLAlchemy with PostgreSQL support; SQLite is the local default.
- Tests: pytest and FastAPI TestClient.
- CI: GitHub Actions backend checks and frontend build on pull requests and feature branch pushes.
- Deployment target: Cloudflare Pages frontend, API host chosen after AWS permissions/cost checks, and managed PostgreSQL chosen after compatibility/free-tier checks.

## Endpoints

- GET /doctors: list active doctors.
- GET /doctors/{id}/availability?date=YYYY-MM-DD: available 30-minute slots.
- POST /appointments: book a future slot.
- PATCH /appointments/{id}/cancel: cancel with a reason and release the slot.
- PATCH /appointments/{id}/reschedule: validate and move an appointment.
- GET /patients/{id}/appointments: upcoming active appointments.
- GET /health and GET /ready: liveness and database readiness.

Validation errors return 422, missing resources 404, slot conflicts 409, and database write failures 503. A partial unique index guards against duplicate active appointments for the same doctor and start time. These behaviors must be tested locally, including against PostgreSQL, before making production-readiness claims.

## Local setup

Requirements: Python 3.11+, Node.js 22+, npm and Git. SQLite is the default, so PostgreSQL is not required for the first local run.

### 1. Clone the feature branch

    git clone https://github.com/RURIGIMK/clinic-booking-platform.git
    cd clinic-booking-platform
    git switch feature/booking-foundation

### 2. Install and run the API (Windows PowerShell)

From the repository root:

    py -3.12 -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install --upgrade pip
    python -m pip install -e ".[dev]"
    $env:DATABASE_URL = "sqlite:///./clinic_booking.db"
    $env:CORS_ORIGINS = "http://localhost:5173"
    python backend/seed.py
    uvicorn app.main:app --app-dir backend --reload

If activation is blocked, run Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass in the same terminal and activate again. Visit http://localhost:8000/docs and http://localhost:8000/health.

### 3. Start the frontend

Open a second PowerShell terminal at the repository root:

    cd frontend
    npm install
    npm run dev

Open the URL Vite prints, normally http://localhost:5173. The demo interface uses synthetic patient ID 1.

For hosted deployment, set VITE_API_BASE_URL to the API origin before building. Never put database credentials or private keys in frontend environment variables.

### 4. Run checks

From the repository root with the virtual environment active:

    pytest
    ruff check backend

Then from frontend:

    npm install
    npm run build

Only describe tests as passing after the commands have actually run successfully. GitHub Actions should repeat the checks on push/PR.

## Design decisions and trade-offs

- FastAPI provides typed request validation, generated OpenAPI documentation and a lightweight API framework. Django REST Framework is a valid alternative but has a broader framework footprint for this focused API.
- PostgreSQL supports relational integrity and transactions. SQLite is a convenience for first local run; concurrency behavior must be checked against PostgreSQL.
- Application availability checks alone cannot prevent simultaneous bookings. The partial unique index is a second line of defense.
- Rescheduling validates the destination before updating the existing appointment. A failed database write should roll back the move.
- All data is synthetic. Authentication, authorization, reminders, payments and clinical records are outside this demo's scope.
- Incoming timestamps require a timezone offset and are stored in UTC. Working hours are interpreted in the configured clinic timezone, which defaults to Africa/Nairobi. Set CLINIC_TIMEZONE to an appropriate IANA timezone for another clinic and test daylight-saving transitions where applicable.
- Budget target is $0 where feasible and a maximum planned spend of $5/month. Check AWS account eligibility and resource pricing before creating cloud resources.

## Reliability and security checklist

- Never commit .env files, credentials, tokens or real patient data.
- Configure production secrets in hosting environment settings.
- Restrict CORS to the deployed frontend origin.
- Use HTTPS and TLS for managed PostgreSQL.
- Avoid logging patient names, request bodies or secrets.
- If AWS is selected, configure bounded log retention, request throttling and budget alerts.
- Test database outage, concurrent booking, cancellation, rescheduling and rollback behavior before public deployment.
- Authentication, authorization, audit trails, backups, clinic-local timezone support and production monitoring are required before real clinical use.

## Branching and commit conventions

Use short-lived branches and pull requests into main. Branch prefixes: feature/, fix/, docs/, test/ and chore/. Follow Conventional Commits, for example:

- feat(api): add appointment rescheduling
- fix(booking): reject duplicate active slots
- test(api): cover cancellation conflicts
- docs(readme): clarify local setup
- chore(ci): run backend and frontend checks

## AI usage reflection

Complete this section after development with actual examples:
1. Explain how AI was used, including prompts and what was accepted or changed.
2. Record one useful suggestion and the prompt that produced it.
3. Record one incorrect or incomplete output, how it was detected, and how it was corrected.
4. Explain two engineering decisions made independently and why.

Do not invent AI incidents or test results.
