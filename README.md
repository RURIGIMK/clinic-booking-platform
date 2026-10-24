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

## 4.1 What did you use AI for across the four sections?

I used AI as both a generative tool and an engineering assistant throughout the assessment. Its generative use included drafting and refining code, developing candidate implementation approaches, producing technical explanations, and creating documentation. I also used it to investigate errors, review configuration, and reason through testing and deployment.

- **Section 1, System Design:** I used AI to explore architecture options, organize the relationships between the application components, and develop explanations of the data models, booking rules, and design trade-offs. I reviewed the resulting design against the scenario and the implementation requirements.
- **Section 2, API Implementation:** I used AI to discuss implementation approaches and generate candidate code or technical solutions where useful. I treated generated output as a starting point that needed to fit the existing codebase, validation rules, and application structure.
- **Section 3, Deployment and CI/CD:** I used AI to investigate deployment failures, explore configuration issues, and identify possible fixes. I checked the suggestions against the repository, workflow configuration, and deployment logs.
- **Section 4, Documentation and Reflection:** I used AI generatively to draft and refine the README, architecture explanations, local setup instructions, deployment guidance, engineering trade-offs, and this reflection. I reviewed the documentation against the actual implementation and distinguished verified behaviour from work that remained unverified.

Generative AI was particularly useful for moving from a blank page to a structured draft, exploring alternative approaches quickly, and improving the clarity of technical explanations. Its output still required review, adaptation, and verification before being used in the submission.

## 4.2 Give one example where an AI suggestion improved your work. What did you prompt it with?

An example was investigating the Wrangler deployment failure. An early deployment attempt failed because Wrangler could not locate the expected entry point. Reviewing the deployment command alongside the repository configuration identified the configuration path as an area to correct. The deployment command was made explicit about using `wrangler.jsonc`.

A representative prompt for this investigation would be:

> Review the frontend deployment configuration and GitHub Actions workflow. Identify why Wrangler may not be locating the expected entry point, and suggest the smallest change consistent with the existing project structure.

This is a representative reconstruction of the prompt, not a claim that it reproduces the original wording verbatim.

The suggestion helped narrow the investigation to the relationship between the deployment command and the configuration file. A subsequent run exposed a separate missing-credentials issue. After the required Cloudflare secrets were configured in the GitHub `production` environment, the deployment workflow completed successfully.

The improvement came from using AI to narrow the investigation and then checking the proposed direction against the actual repository and workflow evidence. The two deployment errors had different causes, so resolving one did not automatically resolve the other.

## 4.3 Give one example where AI output was wrong or incomplete and how you caught it.

During deployment troubleshooting, an AI-generated explanation suggested that the existing Cloudflare deployment settings were misconfigured.

Rather than changing the settings immediately, I compared the explanation with the repository and workflow. The configuration already specified the `main` branch, the `frontend` directory, the Wrangler deployment command, and the API URL. The available evidence did not justify treating those settings as the primary cause without further investigation.

I challenged the explanation and redirected the investigation towards the actual configuration and workflow evidence. This avoided making unnecessary changes based on a diagnosis that was not sufficiently supported.

The experience reinforced that generative AI can produce plausible and confident explanations from incomplete context. I found it more useful to treat generated output as a hypothesis, inspect the relevant evidence, and change the implementation only when the evidence justified doing so.

## 4.4 Name two decisions you made without AI. Why did you trust your own judgment there?

### Decision 1: Not changing hosting settings without evidence

I chose not to change the existing Cloudflare settings simply because a troubleshooting explanation suggested they were wrong. I checked the configuration and workflow first.

I trusted this decision because the repository and deployment configuration provided direct evidence of the current setup. The proposed diagnosis was only a hypothesis. Changing settings without identifying a concrete fault could introduce unnecessary risk and make the original issue harder to isolate.

### Decision 2: Separating deployment success from end-to-end verification

I chose to document the successful deployment as evidence that the deployment workflow completed, rather than claiming that every booking operation had been verified in production.

A deployment log cannot establish that a patient can retrieve doctor availability, book an appointment, cancel it, or reschedule it successfully. Those behaviours require separate tests against the deployed API and database.

I trusted this distinction because it follows from what each check actually measures. It also keeps the README technically accurate by separating a successful deployment from functional verification that remains outstanding.

## 4.5 Reflection

My approach was to use AI to accelerate investigation, generate drafts and candidate solutions, and improve the clarity of technical documentation while retaining responsibility for engineering decisions.

The most useful results came from combining generative assistance with direct inspection of the repository, test output, configuration files, and deployment logs. AI helped me explore options and communicate decisions more efficiently, but it did not remove the need to understand the system or verify the result.

I remained responsible for deciding which suggestions to use, adapting generated code and documentation to the project, and ensuring that claims in the submission matched the available evidence. I consider that balance important when using AI in day-to-day engineering work.

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
