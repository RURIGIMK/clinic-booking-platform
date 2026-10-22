# Clinic Booking Platform

A full-stack clinic appointment booking application developed for the Implementation Engineer take-home assessment. The project demonstrates appointment scheduling, doctor availability, booking validation, cancellation and rescheduling, automated testing, and cloud deployment.

**Live application:** https://clinic-booking-platform.rurigimk.workers.dev  
**Source code:** https://github.com/RURIGIMK/clinic-booking-platform

## 1. Project Overview

The platform allows a demo patient to view doctors, check available appointment slots, book an appointment, review upcoming appointments, and cancel or reschedule an existing booking.

The application uses synthetic patient and doctor data. It is a demonstration system, not a production clinical application.

### Key Features

- Doctor directory with specialty information.
- Doctor availability based on configured working hours.
- Thirty-minute appointment slots.
- Lunch-break and working-hour validation.
- Appointment creation, cancellation, and rescheduling.
- Conflict detection for overlapping appointments.
- Timezone-aware appointment handling.
- Request identifiers and structured request logging.
- API health and readiness endpoints.
- Automated backend checks and frontend production builds.
- Deployment to Cloudflare Workers through GitHub Actions.

## 2. Technology Stack

| Layer | Technology | Purpose |
|---|---|---|
| Frontend | React, TypeScript, Vite | User interface and frontend build |
| API | Python, FastAPI | HTTP endpoints and request validation |
| ORM | SQLAlchemy | Database access and relational models |
| Database | Neon PostgreSQL | Hosted relational data storage |
| Local database | SQLite | Local development and testing |
| Serverless compute | AWS Lambda, Python 3.12 | Backend execution |
| API exposure | Amazon API Gateway HTTP API | Public HTTPS API endpoint |
| Lambda adapter | Mangum | Adapts FastAPI to AWS Lambda |
| Frontend hosting | Cloudflare Workers | Serves the built single-page application |
| CI/CD | GitHub Actions | Testing, building, and frontend deployment |
| Logging | Python logging and CloudWatch Logs | Request diagnostics and backend logs |

## 3. System Architecture

```text
                    Patient / Browser
                           |
                           v
              Cloudflare Workers
              React + TypeScript UI
                           |
                           | HTTPS API requests
                           v
              Amazon API Gateway
                    HTTP API
                           |
                           v
                 AWS Lambda Function
                    Python 3.12
                           |
                           v
                 FastAPI + SQLAlchemy
                           |
                           | TLS database connection
                           v
                    Neon PostgreSQL

     GitHub Repository
             |
             v
       GitHub Actions
       /      |       \\
 Backend   Frontend   Deploy frontend
 checks     build     to Cloudflare
```

The frontend and API are deployed separately. The frontend uses `VITE_API_BASE_URL` to determine which API origin receives requests. The API uses `DATABASE_URL` to connect to the database.

The production API base URL configured in the current workflow is:

`https://yfk5o3gvki.execute-api.eu-west-2.amazonaws.com`

The Cloudflare Worker serves the built frontend assets. API requests are sent to API Gateway rather than handled by the frontend Worker.

## 4. API Reference

The API exposes the following endpoints.

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | Basic liveness check |
| GET | `/ready` | Checks database connectivity |
| GET | `/doctors` | Lists active doctors |
| GET | `/doctors/{doctor_id}/availability?date=YYYY-MM-DD` | Returns available slots for a date |
| POST | `/appointments` | Creates an appointment |
| GET | `/patients/{patient_id}/appointments` | Lists upcoming booked appointments |
| PATCH | `/appointments/{appointment_id}/cancel` | Cancels an appointment |
| PATCH | `/appointments/{appointment_id}/reschedule` | Reschedules an appointment |

Interactive API documentation is available from FastAPI at `/docs` when running the API locally.

### Error handling

The API uses HTTP status codes to distinguish common outcomes:

- `201`: appointment created successfully.
- `404`: requested doctor, patient, or appointment does not exist.
- `409`: booking conflict or incompatible appointment state.
- `422`: invalid request data or unavailable appointment time.
- `503`: handled database operation failure or readiness failure.
- `500`: unexpected server error.

Responses may include an `X-Request-ID` header to help trace requests in logs.

## 5. Scheduling and Data Integrity

### Scheduling assumptions

The seed data defines five synthetic doctors:

| Specialty | Routine schedule |
|---|---|
| General Practice | Monday to Friday, 08:00 to 17:00; Saturday, 09:00 to 13:00 |
| Paediatrics | Monday to Friday, 08:00 to 17:00; Saturday, 09:00 to 13:00 |
| Family Medicine | Monday to Friday, 08:00 to 17:00; Saturday, 09:00 to 13:00 |
| Dermatology | Monday, Tuesday, Thursday, and Friday, 09:00 to 16:00 |
| Cardiology | Monday, Wednesday, and Friday, 09:00 to 16:00 |

The weekday schedules include a 12:00 to 13:00 lunch break. The Saturday schedules for General Practice, Paediatrics, and Family Medicine do not include a lunch break. No routine Sunday sessions are seeded.

These are illustrative application settings, not a statement of standard operating hours for real clinics.

### Booking validation

The backend validates that an appointment:

1. Is in the future.
2. Belongs to an active doctor and an existing demo patient.
3. Fits the doctor's configured working hours.
4. Does not overlap a lunch break.
5. Aligns with the thirty-minute slot grid.
6. Does not overlap another active booking for the same doctor.

A database-level uniqueness guard provides additional protection against duplicate active bookings for the same doctor and start time. This matters because two concurrent requests can pass an application-level availability check before either request commits.

Rescheduling validates the requested destination before updating the existing appointment. Cancelled appointments cannot be rescheduled.

### Timezone handling

The configured clinic timezone defaults to `Africa/Nairobi`. Incoming appointment timestamps must include a timezone offset. The application converts appointment times to UTC for persistence and uses the clinic timezone when evaluating local working hours.

## 6. Run Locally

### Prerequisites

- Git
- Python 3.12
- Node.js 22
- npm

SQLite is used by default for local development. PostgreSQL is available for environments that need to match the hosted database more closely.

### Backend setup

From the repository root, open PowerShell:

```powershell
git clone https://github.com/RURIGIMK/clinic-booking-platform.git
cd clinic-booking-platform

py -3.12 -m venv .venv
.\\.venv\\Scripts\\Activate.ps1

python -m pip install --upgrade pip
python -m pip install -e ".[dev]"

$env:DATABASE_URL = "sqlite:///./clinic_booking.db"
$env:CORS_ORIGINS = "http://localhost:5173"
$env:CLINIC_TIMEZONE = "Africa/Nairobi"

python backend/seed.py
uvicorn app.main:app --app-dir backend --reload
```

If PowerShell blocks virtual environment activation, run the following in the same terminal and activate the environment again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Check the API at:

- `http://localhost:8000/health`
- `http://localhost:8000/ready`
- `http://localhost:8000/docs`

### Frontend setup

Open a second terminal at the repository root:

```powershell
cd frontend
npm ci
$env:VITE_API_BASE_URL = "http://localhost:8000"
npm run dev
```

Open the local URL printed by Vite, normally `http://localhost:5173`.

The frontend needs the correct `VITE_API_BASE_URL` at build time. Do not use a real database connection string as a frontend variable.

### Run the checks

From the repository root, with the Python environment active:

```powershell
ruff check backend --select F821,F822,F823,F811
pytest
```

From the `frontend` directory:

```powershell
npm ci
npm run build
```

These checks are also executed by GitHub Actions. A successful build does not by itself verify all live application flows.

## 7. CI/CD and Deployment

The GitHub Actions workflow is defined in `.github/workflows/ci.yml`.

On pull requests targeting `main` and pushes to `main` or `feature/**`, the workflow runs backend static checks and tests, then builds the frontend.

For a push to `main`, the frontend deployment job runs only after the backend and frontend jobs succeed. It builds the frontend with the configured API origin and deploys the `frontend` directory using Wrangler and `frontend/wrangler.jsonc`.

The deployment uses the GitHub `production` environment and requires these secrets:

- `CLOUDFLARE_API_TOKEN`
- `CLOUDFLARE_ACCOUNT_ID`

Deployment configuration details are documented in [CONFIGURATION.md](CONFIGURATION.md).

### Current deployment status

The last reported GitHub Actions deployment completed successfully and Wrangler reported the Worker URL:

https://clinic-booking-platform.rurigimk.workers.dev

Deployment success confirms that the frontend deployment job completed. End-to-end verification still requires checking that the live UI can load doctors and availability and that booking, cancellation, and rescheduling work correctly against the configured API and database.

## 8. Testing Strategy

The project includes automated backend tests and a frontend production build check.

The CI workflow currently runs:

1. Python dependency installation.
2. Ruff checks for selected undefined-name and redefinition errors.
3. Pytest against the configured backend test suite.
4. Frontend dependency installation using `npm ci`.
5. A TypeScript and Vite production build.
6. A frontend deployment on eligible pushes to `main`.

For a complete release check, the automated workflow should be supplemented by a manual smoke test of the deployed application, including database readiness and the appointment lifecycle.

## 9. Security and Scope

This is a synthetic-data demonstration. The current patient selector is a demo convenience, not an authentication mechanism.

The project does not provide a complete production security model, including verified patient identity, authorization policies, role-based access control, multi-factor authentication, a comprehensive audit trail, clinical record handling, appointment reminders, payment processing, disaster recovery, or production-grade monitoring.

Before using an appointment platform for real patients, the deployment would need a security and privacy review, appropriate authentication and authorization, secret management, operational monitoring, backup and recovery procedures, and verification of the applicable legal and regulatory requirements.

Never commit database credentials or deployment tokens to the repository. Do not put private credentials in `VITE_` variables because frontend variables are included in the browser build.

## 10. Engineering Decisions and Trade-offs

- **FastAPI:** provides request validation, generated OpenAPI documentation, and a lightweight Python API.
- **SQLAlchemy:** separates database operations from endpoint logic and supports both SQLite and PostgreSQL.
- **Serverless backend:** Lambda and API Gateway avoid managing a dedicated application server, but introduce deployment packaging and cold-start considerations.
- **Cloudflare Workers frontend:** serves the built single-page application independently of the API.
- **Database constraints:** complement application validation to reduce duplicate active bookings under concurrent requests.
- **Synthetic seed data:** makes the demo repeatable without depending on real patient information.
- **Separate CI and deployment jobs:** prevent frontend deployment when required backend checks or frontend builds fail.

SQLite is convenient for local work, but production concurrency and database behavior must be verified against PostgreSQL.

## 11. Use of AI in Development

AI was used as a supporting tool for implementation discussion, debugging, configuration review, and documentation. Suggestions were treated as hypotheses to verify against repository code, workflow configuration, deployment logs, and actual application behavior.

One concrete deployment issue involved the Wrangler configuration. An initial deployment attempt failed because Wrangler could not locate the entry point. The deployment command was updated to explicitly reference `wrangler.jsonc`. A subsequent attempt exposed missing Cloudflare credentials in the GitHub Actions environment. The required credentials were then configured as GitHub production environment secrets, and the failed deployment jobs were rerun successfully.

Another useful lesson came from reviewing the hosting settings. The existing Cloudflare configuration already specified the `main` branch, `frontend` directory, build command, Wrangler deployment command, and API URL. A troubleshooting explanation that treated those settings as misconfigured was challenged against the actual configuration. The diagnosis was revised rather than changing settings without evidence.

The engineering approach was to use AI to speed up investigation while checking proposed changes against the source files and workflow results. The final documentation distinguishes a successful deployment from functional verification that still needs to be completed.

## 12. Known Limitations and Next Steps

- Complete and record a live end-to-end smoke test.
- Verify database readiness and appointment operations against the deployed environment.
- Expand test coverage for concurrent bookings and PostgreSQL-specific behavior.
- Review production authentication, authorization, privacy, and audit requirements before handling real patient information.
- Define backup, recovery, monitoring, and operational procedures before any production use.

## 13. References

- [FastAPI documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy documentation](https://docs.sqlalchemy.org/)
- [AWS Lambda documentation](https://docs.aws.amazon.com/lambda/)
- [Amazon API Gateway documentation](https://docs.aws.amazon.com/apigateway/)
- [Cloudflare Workers documentation](https://developers.cloudflare.com/workers/)
- [Wrangler configuration](https://developers.cloudflare.com/workers/wrangler/configuration/)
- [GitHub Actions documentation](https://docs.github.com/actions)
