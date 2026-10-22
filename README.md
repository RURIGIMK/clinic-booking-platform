# Clinic Booking Platform

A full-stack clinic appointment booking demo for the Implementation Engineer take-home assessment. It demonstrates doctor availability, 30-minute booking slots, cancellation and rescheduling, API validation, automated checks, and a hosted deployment architecture.

## Status

- FastAPI API and SQLAlchemy models.
- React, TypeScript and Vite frontend.
- Five synthetic doctors with specialty-specific schedules and lunch breaks.
- Booking lifecycle tests and GitHub Actions CI.
- Deployment target: Cloudflare Pages, AWS Lambda, API Gateway HTTP API, Neon PostgreSQL and CloudWatch.
- The hosted environment is not configured until the resources and environment variables are set up. Do not claim the application is deployed until live smoke tests pass.

## Architecture

- **Frontend:** React, TypeScript, Vite, deployed to Cloudflare Pages.
- **API:** FastAPI on AWS Lambda, exposed through API Gateway HTTP API.
- **Database:** Neon PostgreSQL with TLS. SQLite remains the local default.
- **Logs:** AWS CloudWatch Logs.
- **CI:** GitHub Actions runs backend checks and builds the frontend on pushes to feature branches and main, and on pull requests targeting main.

## API endpoints

- `GET /health`: liveness check.
- `GET /ready`: checks database connectivity.
- `GET /doctors`: list active doctors.
- `GET /doctors/{id}/availability?date=YYYY-MM-DD`: available 30-minute slots.
- `POST /appointments`: book a future slot.
- `PATCH /appointments/{id}/cancel`: cancel with a reason.
- `PATCH /appointments/{id}/reschedule`: validate and move an appointment.
- `GET /patients/{id}/appointments`: list upcoming active appointments.

Validation errors return 422, missing resources 404, slot conflicts 409, and database write failures 503. A partial unique index guards against duplicate active bookings for the same doctor and start time. The demo uses synthetic data only and is not suitable for real patient information.

## Local setup

Requirements: Python 3.12, Node.js 22, npm and Git. SQLite is the default local database.

### API (Windows PowerShell)

Run from the repository root:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
$env:DATABASE_URL = "sqlite:///./clinic_booking.db"
$env:CORS_ORIGINS = "http://localhost:5173"
python backend/seed.py
uvicorn app.main:app --app-dir backend --reload
```

If PowerShell blocks activation, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` in that terminal and activate again. Check `http://localhost:8000/health` and `http://localhost:8000/docs`.

### Frontend

Open a second terminal at the repository root:

```powershell
cd frontend
npm ci
npm run dev
```

Open the local URL printed by Vite, normally `http://localhost:5173`. The demo interface uses synthetic patient ID 1.

### Checks

From the repository root with the Python virtual environment active:

```bash
pytest
ruff check backend --select F821,F822,F823,F811
```

Then in `frontend/`:

```bash
npm ci
npm run build
```

GitHub Actions repeats these checks. Report tests as passing only when the commands or workflow have actually passed.

## Deployment guide

The intended architecture is Cloudflare Pages (frontend), AWS Lambda plus API Gateway HTTP API (backend), Neon PostgreSQL (database), and CloudWatch Logs. Avoid RDS and NAT Gateways for this small demo. AWS budget alerts are notifications, not a hard spending cap.

### 1. Create the Neon database

Create a PostgreSQL project in a region compatible with the selected AWS region where available. Copy the connection string and keep it private. It should require TLS, commonly using `sslmode=require`. Do not commit it or put it in a frontend variable.

### 2. Initialize the hosted database once

The Lambda adapter uses `Mangum(app, lifespan="off")`, so the FastAPI startup hook does not create or alter tables on Lambda cold starts. Initialize the schema and synthetic data deliberately before sending traffic.

In a trusted local terminal, activate the project's Python virtual environment and install the project if needed. Set `DATABASE_URL` to the Neon connection string, confirm that it points to the intended Neon database, and run:

```bash
python backend/seed.py
```

The seed script creates missing tables, adds the two nullable lunch-break columns when needed, reconciles the five demo doctors' working-hour rows, and adds synthetic patients only when the patient table is empty. It does not explicitly delete appointments. Do not run it against a database containing real or important data without reviewing its effects first.

### 3. Package the Lambda function

Build a ZIP for the Lambda Python 3.12 x86_64 runtime from the repository root. This installs the project and its dependencies, including Mangum, into a clean target directory. Run the commands in WSL Ubuntu:

```bash
cd ~/PROJECTS/clinic-booking-platform
BUILD_DIR="$(mktemp -d /tmp/clinic-lambda-build.XXXXXX)"
ZIP_PATH="/tmp/clinic-booking-lambda.zip"
python -m pip install --target "$BUILD_DIR" --platform manylinux2014_x86_64 --python-version 3.12 --implementation cp --abi cp312 --only-binary=:all: --no-compile .
BUILD_DIR="$BUILD_DIR" ZIP_PATH="$ZIP_PATH" python - <<'PY'
import os
import zipfile
from pathlib import Path

build_dir = Path(os.environ["BUILD_DIR"])
zip_path = Path(os.environ["ZIP_PATH"])
with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
    for path in build_dir.rglob("*"):
        if path.is_file():
            archive.write(path, path.relative_to(build_dir))
with zipfile.ZipFile(zip_path) as archive:
    bad_file = archive.testzip()
    if bad_file:
        raise SystemExit(f"Invalid ZIP member: {bad_file}")
print(f"Created {zip_path} ({zip_path.stat().st_size / 1024 / 1024:.2f} MiB)")
PY
```

Configure the Lambda runtime as **Python 3.12**, architecture **x86_64**, and handler **`app.lambda_handler.handler`**. Upload `/tmp/clinic-booking-lambda.zip`. Give the function a Lambda execution role with basic CloudWatch Logs permissions. Set environment variables:

- `DATABASE_URL`: private Neon PostgreSQL connection string.
- `CORS_ORIGINS`: exact Cloudflare Pages origin, for example `https://your-project.pages.dev`.
- `CLINIC_TIMEZONE`: `Africa/Nairobi`.
- `APP_ENV`: `production`.

Set a bounded timeout and memory allocation, and use CloudWatch log retention to control storage. Never place database credentials in frontend environment variables or commit them to Git.

### 4. Expose the API with API Gateway

Create an API Gateway **HTTP API** with a Lambda proxy integration to this function. Configure a catch-all `$default` route (or explicit routes for all endpoints) and enable automatic deployment for the default stage. Keep the generated HTTPS invoke URL. Configure CORS for the deployed Pages origin, methods `GET`, `POST`, `PATCH`, and headers `Content-Type` and `X-Request-ID`. CORS should be restricted to the actual frontend origin once known.

### 5. Deploy the frontend to Cloudflare Pages

Import this GitHub repository into Cloudflare Pages and configure:

- Root directory: `frontend`
- Build command: `npm run build`
- Build output directory: `dist`
- Environment variable: `VITE_API_BASE_URL` set to the API Gateway origin (scheme and host only, no endpoint path).

If you need the Pages origin before finishing backend CORS, create the Pages project first with a temporary API origin, note the assigned `pages.dev` URL, then update the Lambda and API Gateway CORS settings and set the correct `VITE_API_BASE_URL` before rebuilding.

### 6. Verify the live system

After deployment, check the API endpoints in a browser or with curl:

```bash
curl -i "https://YOUR_API_ID.execute-api.eu-west-1.amazonaws.com/health"
curl -i "https://YOUR_API_ID.execute-api.eu-west-1.amazonaws.com/ready"
curl -i "https://YOUR_API_ID.execute-api.eu-west-1.amazonaws.com/doctors"
```

Then open the Cloudflare Pages URL, confirm doctors load, check availability for a future date, book a synthetic appointment, and verify cancellation and rescheduling. Check CloudWatch logs for errors. Do not claim successful deployment until these checks pass.

### 7. CI/CD

The current GitHub Actions workflow is CI: it tests the backend and builds the frontend. Automated deployment should be enabled only after the AWS Lambda/API and Cloudflare Pages resources exist. Prefer GitHub Actions OIDC to assume a narrowly scoped AWS deployment role rather than storing AWS access keys in GitHub secrets. Configure Cloudflare's deployment token as a GitHub secret. Do not use root AWS credentials in CI.

## Scheduling assumptions

- General Practice, Paediatrics and Family Medicine: Monday-Friday 08:00-17:00, lunch 12:00-13:00; Saturday 09:00-13:00.
- Dermatology: Monday, Tuesday, Thursday and Friday 09:00-16:00, lunch 12:00-13:00.
- Cardiology: Monday, Wednesday and Friday 09:00-16:00, lunch 12:00-13:00.
- Sunday: no routine appointments.

These are configurable demo assumptions, not universal clinic hours. Slots last 30 minutes and starts must align to the half-hour grid. Incoming appointment timestamps require a timezone offset and are stored in UTC; working hours use the configured clinic timezone, defaulting to `Africa/Nairobi`.

## Design decisions and limitations

- FastAPI provides typed request validation, generated OpenAPI documentation and a lightweight API framework.
- PostgreSQL supports relational integrity and transactions. SQLite is a convenient local default; concurrency behavior should be verified against PostgreSQL.
- Application checks alone cannot prevent simultaneous bookings. The partial unique index provides a database-level guard.
- Rescheduling validates the destination before updating the existing appointment.
- Authentication, authorization, reminders, payments, clinical records, audit trails, backups and production monitoring are outside this demo's scope. Do not use this application for real clinical data without appropriate security and operational controls.

Scheduling assumptions are not a universal rule for Kenyan clinics. Facility opening hours do not necessarily represent individual doctor shifts. References: [KESDI technical report](https://ncpd.go.ke/wp-content/uploads/2022/06/Final-KESDI-Health-Technical-Report-1.pdf), [Kenyatta National Hospital outpatient clinics](https://knh.or.ke/index.php/corporate-outpatient-clinic/) and [Jaramogi Oginga Odinga Teaching and Referral Hospital FAQs](https://www.jootrh.go.ke/faqs).

## Branching and commit conventions

Use short-lived branches and pull requests into `main`. Branch prefixes: `feature/`, `fix/`, `docs/`, `test/` and `chore/`. Follow Conventional Commits, for example `feat(api): add appointment rescheduling`, `fix(booking): reject duplicate active slots`, or `chore(ci): run backend and frontend checks`.

## AI usage reflection

Complete this section using actual examples from the work:
1. Explain how AI was used, including prompts and what was accepted or changed.
2. Record one useful suggestion and the prompt that produced it.
3. Record one incorrect or incomplete output, how it was detected, and how it was corrected.
4. Explain two engineering decisions made independently and why.

Do not invent AI incidents or test results.
