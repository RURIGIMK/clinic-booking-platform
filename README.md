# Clinic Booking Platform

A full-stack clinic appointment booking system developed for the Implementation Engineer Take-Home Assessment. The application allows patients to view doctors, check appointment availability, book appointments, review upcoming bookings, cancel appointments, and reschedule existing bookings.

**Live application:** [https://clinic-booking-platform.rurigimk.workers.dev](https://clinic-booking-platform.rurigimk.workers.dev)

**GitHub repository:** [https://github.com/RURIGIMK/clinic-booking-platform](https://github.com/RURIGIMK/clinic-booking-platform)

**Technology stack:** Python, FastAPI, SQLAlchemy, PostgreSQL, React, TypeScript, AWS Lambda, Amazon API Gateway, Cloudflare Workers, and GitHub Actions.

---

# Section 1: System Design

## 1.1 Problem Statement

The clinic has five doctors, each with defined working hours. Patients need to view available appointment slots for a selected doctor and date, book a suitable slot, and manage existing appointments.

The main design requirement is to prevent two patients from booking the same doctor's appointment slot while keeping the application straightforward to operate and extend as the clinic grows.

The design therefore separates the user interface, API, booking logic, data persistence, and deployment infrastructure.

## 1.2 System Architecture

The application uses a client-server architecture with a separately deployed frontend and backend API.
```
                  Patient
                     |
                     v
             React + TypeScript
             Cloudflare Workers
                     |
                HTTPS requests
                     |
                     v
             Amazon API Gateway
                     |
                     v
               AWS Lambda
               Python 3.12
                     |
                     v
              FastAPI Application
                     |
             Booking and Validation
                     |
                     v
             SQLAlchemy ORM
                     |
                     v
             Neon PostgreSQL
```

The development and deployment workflow is separate from the runtime request flow.
```
             GitHub Repository
                     |
                     v
              GitHub Actions
                     |
            +--------+--------+
            |                 |
            v                 v
      Backend checks     Frontend build
            |                 |
            +--------+--------+
                     |
              Push to main
                     |
                     v
          AWS OIDC Authentication
                     |
                     v
             Deploy AWS Lambda
                     |
                     v
          API Smoke Tests: /health
                and /ready
                     |
              Both succeed
                     |
                     v
        Deploy Frontend to Cloudflare
```

The backend and frontend are independently deployable. **The production workflow coordinates their deployment order: it runs the configured checks, deploys the backend on pushes to `main`, and verifies the deployed API using `/health` and `/ready`. The frontend deployment proceeds only after the required checks, backend deployment, and API smoke tests succeed.**

## 1.3 Data Models

The system uses four principal relational models.

### Doctor

Represents a doctor who provides appointments.

| Field | Purpose |
| --- | --- |
| `id` | Primary key |
| `name` | Doctor's name |
| `specialty` | Medical specialty |
| `active` | Indicates whether the doctor is available for new bookings |
| `working_hours` | Relationship to the doctor's configured working sessions |

Separating doctor information from working hours allows a doctor's schedule to be changed without duplicating the doctor's details.

### DoctorWorkingHour

Represents a doctor's working session for a particular weekday.

| Field | Purpose |
| --- | --- |
| `id` | Primary key |
| `doctor_id` | Reference to the doctor |
| `weekday` | Day of the week, Monday to Sunday |
| `opens_at` | Start of the working session |
| `closes_at` | End of the working session |
| `break_starts_at` | Optional start of a break |
| `break_ends_at` | Optional end of a break |

A uniqueness constraint on `doctor_id` and `weekday` prevents multiple schedule records for the same doctor and weekday under the current one-session-per-day model.

### Patient

Represents a patient in the demonstration system.

| Field | Purpose |
| --- | --- |
| `id` | Primary key |
| `full_name` | Patient's name |

The current application uses synthetic patient records and a demonstration patient selector. This is not an authentication or identity-verification mechanism.

### Appointment

Represents a patient's booking with a doctor.

| Field | Purpose |
| --- | --- |
| `id` | Primary key |
| `doctor_id` | Reference to the doctor |
| `patient_id` | Reference to the patient |
| `starts_at` | Appointment start timestamp |
| `ends_at` | Appointment end timestamp |
| `status` | Current appointment status |
| `cancellation_reason` | Optional reason for cancellation |
| `created_at` | Timestamp when the appointment was created |

Appointments use a status to distinguish active bookings from cancelled ones. A cancelled appointment remains in the database rather than being deleted, preserving its basic booking history.

A database-level partial unique index prevents multiple active appointments from using the same doctor's start time. Application validation complements this constraint by checking the complete booking rules.

## 1.4 Key Booking Rules

The API validates a booking against the following conditions:

1. The doctor exists and is active.
2. The patient exists.
3. The appointment starts at least one hour after the current UTC time. Exactly one hour ahead is permitted.
4. The requested time aligns with a 30-minute slot.
5. The appointment falls within the doctor's configured working hours.
6. The appointment does not overlap a configured break.
7. The slot does not conflict with another active booking for the same doctor.

The application checks availability before creating a booking. However, an availability check alone is insufficient because two concurrent requests could attempt to book the same slot. The database uniqueness constraint provides an additional safeguard against duplicate active bookings.

### Cancellation

A cancellation changes the appointment status and records the supplied reason. The appointment is not deleted. Since availability is calculated from active bookings, a cancelled slot can become available again.

An attempt to cancel an already cancelled appointment returns an error rather than silently repeating the operation.

### Rescheduling

Rescheduling validates the requested destination using the same core rules as a new booking, including the one-hour minimum advance notice. If the destination is unavailable or invalid, the request is rejected.

A cancelled appointment cannot be rescheduled. For a successful reschedule, the original slot becomes available again and the appointment moves to the new time.

## 1.5 Components and Responsibilities

| Component | Responsibility |
| --- | --- |
| React and TypeScript frontend | Doctor selection, availability display, booking forms, and appointment management |
| FastAPI | REST endpoints, request validation, response formatting, and HTTP error handling |
| Booking logic | Slot generation, working-hour validation, cancellation, rescheduling, and conflict checks |
| SQLAlchemy | Relational persistence and database queries |
| Neon PostgreSQL | Hosted persistent application data |
| AWS Lambda | Serverless backend execution |
| Amazon API Gateway | Public HTTPS access to the backend |
| Cloudflare Workers | Frontend delivery |
| GitHub Actions | Automated checks, frontend build, and deployment |

## 1.6 Design Decisions and Trade-offs

**FastAPI rather than a larger web framework:** FastAPI provides request validation, typed endpoint definitions, and generated API documentation while keeping the backend relatively lightweight.

**SQLAlchemy:** The ORM separates database access from the HTTP layer and supports SQLite for local development and PostgreSQL for the hosted environment. The two databases still require testing for differences in concurrency and database-specific behaviour.

**PostgreSQL:** A relational database is appropriate because doctors, patients, schedules, and appointments have clear relationships and integrity requirements.

**Database-level uniqueness:** Application-level checks provide meaningful validation errors, while the database constraint protects against duplicate active bookings during concurrent requests. A database constraint does not replace all application validation, but it provides an important additional guarantee.

**Serverless backend:** AWS Lambda and API Gateway avoid maintaining a dedicated application server. The trade-offs include deployment packaging, cold starts, execution limits, and database connection management.

**Separate frontend hosting:** Cloudflare Workers serves the built frontend independently of the backend API. This simplifies frontend delivery but requires correct API URL and cross-origin configuration.

**Synthetic demonstration data:** Synthetic data makes the application reproducible without exposing real patient information. It is appropriate for the assessment but does not establish production readiness.

## 1.7 Assumptions and Ambiguities

The assessment leaves some operational details open. The following assumptions were adopted:

- Appointment durations are fixed at 30 minutes.
- A doctor's working schedule is configured by weekday.
- The seeded schedules are illustrative rather than actual operating hours for a real clinic.
- The clinic timezone defaults to `Africa/Nairobi`.
- Appointment timestamps supplied to the API must include a timezone offset.
- Appointment timestamps are persisted in UTC and interpreted in the clinic's local timezone for schedule validation.
- A slot is considered unavailable when it conflicts with an active booking.
- Cancellation preserves the appointment record and changes its status.
- Rescheduling is allowed only for appointments that have not been cancelled.
- The current patient selector is for demonstration purposes and does not prove patient identity.

The implementation rejects appointments that start less than one hour after the current UTC time. Exactly one hour ahead is permitted. The availability calculation excludes slots inside that window, and rescheduling applies the same validation as a new booking.

## 1.8 Seeded Doctor Schedules

The seed data contains five synthetic doctors.

| Specialty | Working schedule |
| --- | --- |
| General Practice | Monday to Friday, 08:00 to 17:00; Saturday, 09:00 to 13:00 |
| Paediatrics | Monday to Friday, 08:00 to 17:00; Saturday, 09:00 to 13:00 |
| Family Medicine | Monday to Friday, 08:00 to 17:00; Saturday, 09:00 to 13:00 |
| Dermatology | Monday, Tuesday, Thursday, and Friday, 09:00 to 16:00 |
| Cardiology | Monday, Wednesday, and Friday, 09:00 to 16:00 |

The weekday schedules include a lunch break from 12:00 to 13:00. The Saturday schedules do not include a lunch break. No routine Sunday sessions are seeded.

These schedules are configurable demonstration data, not fixed business rules for all clinics.

---

# Section 2: API Implementation

## 2.1 Technology

The backend is implemented in Python using FastAPI and SQLAlchemy. It exposes REST endpoints for doctor availability and appointment management.

The API is designed to keep HTTP request handling separate from the booking logic and database models.

## 2.2 API Endpoints

| Method | Endpoint | Description |
| --- | --- | --- |
| `GET` | `/health` | Checks whether the API process responds |
| `GET` | `/ready` | Checks database connectivity |
| `GET` | `/doctors` | Lists active doctors |
| `GET` | `/doctors/{doctor_id}/availability?date=YYYY-MM-DD` | Returns available 30-minute slots |
| `POST` | `/appointments` | Books an appointment |
| `GET` | `/patients/{patient_id}/appointments` | Lists upcoming booked appointments |
| `PATCH` | `/appointments/{appointment_id}/cancel` | Cancels an appointment with a reason |
| `PATCH` | `/appointments/{appointment_id}/reschedule` | Reschedules an appointment |

Interactive API documentation is available at `/docs` when running the backend locally.

## 2.3 Validation and Error Handling

The API distinguishes invalid input, missing resources, and booking conflicts through HTTP status codes.

| Status | Meaning |
| --- | --- |
| `200 OK` | Request completed successfully |
| `201 Created` | Appointment created |
| `404 Not Found` | Requested doctor, patient, or appointment does not exist |
| `409 Conflict` | Booking conflict or incompatible appointment state |
| `422 Unprocessable Entity` | Request validation failure or invalid appointment time |
| `503 Service Unavailable` | Database readiness or handled database operation failure |
| `500 Internal Server Error` | Unexpected server-side error |

The precise response depends on the failure and the endpoint's validation path. FastAPI's request validation also provides structured error details for malformed input.

The backend adds an `X-Request-ID` response header and logs request details, including method, path, status, and duration. This helps correlate a request with backend logs during troubleshooting.

## 2.4 Availability Calculation

Availability is generated from a doctor's configured working hours for the requested date.

The booking logic considers:

- The weekday's working session.
- Any configured break.
- The 30-minute slot interval.
- Existing active appointments.
- The current time, excluding slots that start less than one hour after the current UTC time.

The frontend displays the available slots returned by the API. The backend independently validates a booking request rather than trusting that a slot remains available simply because it was displayed earlier.

## 2.5 Basic Test Coverage

The repository includes a pytest test suite for backend behaviour and a frontend production build check in CI.

The backend checks include selected Ruff static checks and pytest execution. The frontend uses `npm ci` and `npm run build`.

The booking tests include rejection of appointments within the one-hour advance-notice window, acceptance of a booking more than one hour ahead, and rejection of a reschedule into the one-hour window.

These checks are useful for catching regressions, but the configured CI checks do not replace a live end-to-end smoke test against the deployed API and database. Concurrent booking behaviour and PostgreSQL-specific behaviour should receive additional testing before production use.

---

# Section 3: Deployment and CI/CD

## 3.1 Public Deployment

**Live application:** [https://clinic-booking-platform.rurigimk.workers.dev](https://clinic-booking-platform.rurigimk.workers.dev)

The frontend is deployed to Cloudflare Workers. The backend is exposed through Amazon API Gateway and executes on AWS Lambda. The hosted relational database is Neon PostgreSQL.

The production API origin configured in GitHub Actions is:

`https://yfk5o3gvki.execute-api.eu-west-2.amazonaws.com`

The frontend and backend are separate deployments. The frontend receives its API origin through the `VITE_API_BASE_URL` build-time variable.

## 3.2 Deployment Architecture

| Service | Role |
| --- | --- |
| Cloudflare Workers | Public frontend hosting |
| Amazon API Gateway HTTP API | HTTPS endpoint for backend requests |
| AWS Lambda, Python 3.12 | Backend execution |
| Neon PostgreSQL | Hosted database |
| GitHub Actions | Automated checks and deployment |

## 3.3 CI/CD Workflow

The workflow is defined in `.github/workflows/ci.yml`.

The pipeline is configured to run on:

- Pull requests targeting `main`.
- Pushes to `main`.
- Pushes to branches matching `feature/**`.

The backend job installs the Python project with its development dependencies, runs selected Ruff checks, and executes pytest.

The frontend job installs dependencies using `npm ci` and builds the production frontend using `npm run build`.

**Pull requests and feature branch pushes run the configured checks but do not deploy the application. Deployment jobs run on pushes to `main`.**

**For a push to `main`, the backend deployment job runs after the backend checks succeed. It authenticates to AWS using GitHub Actions OpenID Connect (OIDC), verifies that the Lambda function uses Python 3.12 and the `x86_64` architecture, packages the backend application and its Lambda dependencies, and updates the `clinic-booking-api` Lambda function.**

**After the Lambda update, the workflow waits for the function update to complete and runs API smoke tests against `/health` and `/ready`. The frontend deployment depends on the backend checks, frontend build, and successful backend deployment job, including its smoke tests. This prevents the frontend deployment from proceeding when the backend deployment or its smoke tests fail.**

**The frontend is built with `VITE_API_BASE_URL` set to the production API origin and deployed to Cloudflare Workers using Wrangler and `frontend/wrangler.jsonc`.**

**The deployment jobs use the GitHub Actions `production` environment. The backend deployment requires the `AWS_DEPLOY_ROLE_ARN` secret and the `AWS_LAMBDA_FUNCTION_NAME` environment variable. The frontend deployment requires these secrets:**

- `CLOUDFLARE_API_TOKEN`
- `CLOUDFLARE_ACCOUNT_ID`

**These values are configured in the GitHub environment settings rather than committed to source control. AWS authentication uses OIDC instead of storing long-lived AWS access keys in the repository.**

### Deployment trigger

**Branch:** `main`

**Trigger:** A push to `main`, including a merge that updates the branch, initiates the workflow. The deployment jobs run only for pushes to `main` and only after their configured dependencies succeed.

**A successful pull request check alone does not deploy the application. The production deployment is tied to the subsequent push to `main`.**

## 3.4 Deployment Troubleshooting

**The deployment process encountered separate issues at different stages.**

During deployment, Wrangler initially failed to locate the expected entry point. The deployment command was updated to explicitly reference `wrangler.jsonc`.

**A later backend deployment attempt failed during AWS OIDC authentication with the error `Not authorized to perform sts:AssumeRoleWithWebIdentity`. The issue was related to the AWS IAM role trust policy and the GitHub Actions OIDC subject claim. The repository's GitHub OIDC configuration used immutable subject claims, so the trust policy needed to match the subject format used by the workflow's `production` environment.**

**After the trust policy was corrected, a subsequent workflow run successfully assumed the AWS role, verified the Lambda runtime and architecture, updated the Lambda code, and passed the `/health` and `/ready` smoke tests.**

**These incidents illustrate the importance of diagnosing each deployment failure from its specific error message. The Wrangler configuration path and AWS OIDC trust policy were separate issues and required separate corrections. Successful API smoke tests confirm that the deployed API responded and that the readiness check passed at the time of the run. They do not, by themselves, prove that every booking operation works end to end.**

## 3.5 Local Development

### Prerequisites

- Git
- Python 3.12
- Node.js 22
- npm

### Backend setup

From PowerShell, clone the repository and create a virtual environment:
```powershell
git clone https://github.com/RURIGIMK/clinic-booking-platform.git
cd clinic-booking-platform

py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Configure the local environment:
```powershell
$env:DATABASE_URL = "sqlite:///./clinic_booking.db"
$env:CORS_ORIGINS = "http://localhost:5173"
$env:CLINIC_TIMEZONE = "Africa/Nairobi"
```

Seed the local database:
```powershell
python backend/seed.py
```

Start the API:
```powershell
uvicorn app.main:app --app-dir backend --reload
```

The backend is normally available at `http://localhost:8000`.

Useful local endpoints:

- Health: `http://localhost:8000/health`
- Readiness: `http://localhost:8000/ready`
- API documentation: `http://localhost:8000/docs`

If PowerShell blocks virtual environment activation, run the following command in the same terminal and try activation again:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

### Frontend setup

Open a second terminal at the repository root:
```powershell
cd frontend
npm ci
$env:VITE_API_BASE_URL = "http://localhost:8000"
npm run dev
```

Open the local URL printed by Vite, normally `http://localhost:5173`.

The `VITE_API_BASE_URL` variable is public build configuration. Do not put database credentials, API secrets, or other private values in frontend environment variables.

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

The same categories of backend checks and frontend build are configured in GitHub Actions.

## 3.6 Operational Verification

**The production deployment workflow successfully updated the backend Lambda function and passed its `/health` and `/ready` smoke tests. The health endpoint returned `{"status":"ok"}`, while the readiness endpoint returned `{"status":"ready"}`. This confirms that the API responded and the readiness check reported database connectivity at the time of the run. It does not establish that every application feature has been tested against the live environment.**

**A complete manual smoke test should verify the following behaviours before claiming that the full booking lifecycle has been verified in production:**

1. The live frontend loads.
2. The doctor directory is retrieved from the API.
3. Availability can be retrieved for a doctor and date.
4. A valid appointment can be created.
5. A second booking for the same slot is rejected.
6. Cancellation records a reason and releases the slot.
7. A cancelled appointment cannot be cancelled or rescheduled again.
8. Rescheduling validates the destination and releases the original slot.
9. The readiness endpoint reports database connectivity.

**The live application URL is published above, but the end-to-end checks should only be described as complete after they have actually been run and their results recorded. The successful deployment and API smoke tests should not be treated as evidence that every item in this manual test list has passed.**

# Section 4: AI Reflection

## 4.1 What did I use AI for?

I used AI throughout the implementation process as a development assistant. This included discussing the data model and system architecture, developing parts of the backend and frontend implementation, reviewing API logic, suggesting test cases, troubleshooting deployment issues, and improving the README and supporting documentation.

For the design, I used AI to evaluate possible approaches and identify technical trade-offs, particularly around data integrity and the relationship between application-level validation and database constraints. I considered its suggestions against the project requirements before deciding which approaches to retain.

For the API implementation, AI helped me work through booking and availability logic, validation, error handling, and testing. I reviewed the suggested implementation and checked it against the expected behaviour. Appointment validation, time handling, and booking conflicts required particular attention because incorrect assumptions could affect the availability of appointment slots.

For deployment, I used AI to investigate AWS Lambda packaging, GitHub Actions configuration, OpenID Connect (OIDC) authentication, and Cloudflare deployment issues. This required more troubleshooting than I initially expected because solutions based on common configurations did not always account for the specific settings used by my repository and deployment environment.

I also used AI to improve the wording and organisation of the README and deployment documentation. I remained responsible for checking the consistency of the documented implementation, the deployment configuration, and the claims made about what had been verified.

## 4.2 One suggestion that improved my work

One useful suggestion was to use GitHub OIDC to authenticate the deployment workflow to AWS rather than relying on long-lived AWS access keys stored in GitHub secrets.

This approach establishes a trust relationship between GitHub Actions and AWS, allowing the workflow to obtain temporary credentials. It avoids maintaining long-lived AWS credentials in the repository and allows the deployment role to be restricted to the resources and actions required by the workflow.

I also considered the compatibility of the AWS Lambda runtime and architecture when packaging the backend. Dependencies containing compiled components must be compatible with the target execution environment. A packaging process can complete successfully while an incompatible dependency still causes the function to fail when it starts.

I retained these considerations because they address practical deployment and security risks. However, the configuration still needed to be checked against the actual repository settings, permissions, runtime, and deployment process rather than accepted solely because AI suggested it.

**Prompt used:**

"I am at AWS IAM Step 4A for setting up GitHub Actions OIDC for RURIGIMK/clinic-booking-platform. My identity provider status is: exists. Guide me from this exact point using the current AWS console."

This prompt reflects my use of AI to work through the AWS IAM and GitHub Actions OIDC configuration step by step. I used the guidance to navigate the setup while checking the instructions against the AWS console and the repository's actual configuration.

## 4.3 One time AI was wrong or incomplete

One example arose during Cloudflare deployment troubleshooting. AI suggested possible configuration changes as explanations for the deployment problem, but the initial suggestions did not establish the actual cause. I needed to examine the repository and deployment workflow instead of assuming that a plausible explanation was correct.

The investigation included checking the deployment command and configuration. The Wrangler entry point needed to be specified explicitly for `wrangler.jsonc`, while a separate issue involving Cloudflare credentials required attention to the production environment's secrets.

This experience demonstrated that AI can generate technically plausible explanations based on common deployment patterns without fully accounting for the configuration of a particular project. Applying a suggested change without verifying its cause could introduce unrelated changes or make the original problem harder to identify.

I therefore treated AI suggestions as hypotheses and used repository configuration and deployment evidence to guide troubleshooting. The main lesson was that the usefulness of a suggestion depends on whether it matches the actual environment, not simply on whether it sounds technically correct.

## 4.4 Two decisions I made without AI

**Decision 1: Avoiding unsupported configuration changes**

I chose not to change existing hosting settings simply because AI suggested that they might be responsible for a deployment problem. I wanted changes to address an identifiable cause rather than introduce unrelated modifications. I trusted this decision because the repository configuration and workflow provided more relevant evidence than a general recommendation.

**Decision 2: Separating deployment success from functional verification**

I chose to distinguish successful deployment and health checks from verification of the complete appointment-booking workflow. A service responding successfully to a health request does not necessarily prove that the database schema is correct or that booking, cancellation, rescheduling, and concurrent requests all behave as expected.

I retained this distinction in the documentation so that the project's status would reflect the checks actually performed. I considered it important not to describe the application as fully verified when some database and functional checks remained outstanding.

These decisions demonstrate that I was not treating AI output or deployment status as a substitute for engineering judgment. I used the available evidence to decide what could reasonably be claimed about the system.

## 4.5 What I would do differently

I would define the verification steps earlier and separate deployment checks from functional and database checks. Health endpoints are useful for confirming that a service responds, but they do not replace testing the complete booking lifecycle or checking the production database schema.

The deployment and basic health and connectivity checks provided useful evidence that the service was responding. However, I have not yet verified the complete booking lifecycle against production PostgreSQL, and I would not claim that this testing has been completed.

In future projects, I would establish the acceptance criteria and verification commands before deployment, keep a clearer record of the actual prompts and configuration changes, and test assumptions behind AI-generated suggestions earlier. I would also document the difference between implemented features, successfully executed tests, and checks that remain outstanding.

This experience reinforced my understanding that AI is most useful as a development assistant when its suggestions are evaluated critically. It can accelerate implementation and troubleshooting, but the developer remains responsible for validating the results, understanding the system, and making accurate claims about what has been achieved.

---

# Security, Limitations, and Future Improvements

## Security and privacy

This application is a synthetic-data demonstration and should not be used to manage real patient information in its current form.

The patient selector is a demonstration convenience, not an authentication mechanism. The application does not implement a complete production identity and authorization model, comprehensive audit controls, or the operational safeguards required for a clinical service.

Before production use, the system would need appropriate authentication and authorization, patient identity verification, stronger auditability, secret management, monitoring, backup and recovery procedures, and a review of applicable privacy and regulatory requirements.

Private credentials must not be committed to the repository or embedded in frontend build variables.

## Known limitations

- The complete live booking lifecycle still requires a documented end-to-end smoke test.
- PostgreSQL-specific and concurrent booking behaviour should receive additional verification.
- The demo patient selector is not suitable for real patient identity or access control.
- Production authentication, authorization, privacy, and audit requirements remain outside the current demonstration scope.
- Monitoring, backup, recovery, and operational procedures require further development before production use.

## Future improvements

1. Add a comprehensive end-to-end test suite for booking, cancellation, rescheduling, and slot conflicts.
2. Expand concurrency tests against PostgreSQL.
3. Introduce secure authentication and patient-specific authorization.
4. Add a stronger audit trail and operational monitoring.
5. Establish backup, recovery, and deployment rollback procedures.
6. Review database connection management and performance as usage grows.

---

# References

- [FastAPI documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy documentation](https://docs.sqlalchemy.org/)
- [AWS Lambda documentation](https://docs.aws.amazon.com/lambda/)
- [Amazon API Gateway documentation](https://docs.aws.amazon.com/apigateway/)
- [Cloudflare Workers documentation](https://developers.cloudflare.com/workers/)
- [Wrangler configuration](https://developers.cloudflare.com/workers/wrangler/configuration/)
- [GitHub Actions documentation](https://docs.github.com/actions)
