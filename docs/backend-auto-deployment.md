# Backend auto-deployment setup

This repository deploys the backend to the existing AWS Lambda function and then deploys the frontend to Cloudflare Workers. Deployments are triggered only by a push to `main`, normally after a pull request is merged. Pull requests and feature branches run CI checks but do not deploy.

## What the workflow does

1. Runs the existing backend lint and test checks.
2. On `main` only, authenticates to AWS using GitHub's OpenID Connect (OIDC), without storing long-lived AWS access keys.
3. Confirms that the Lambda function uses Python 3.12 and x86_64, builds a Lambda ZIP package, and updates the function code.
4. Checks the deployed API's `/health` and `/ready` endpoints.
5. Only if the backend deployment and smoke tests pass, deploys the frontend to Cloudflare Workers.

The workflow deliberately does not create or alter database tables. Database schema changes need a separate, reviewed migration plan.

## Cloudflare Workers Builds configuration

The Cloudflare Worker is configured with `frontend` as its root directory. Its build command is `npm run build`, and its deploy command must be `npx wrangler deploy`. Do not use `npx wrangler dev` as the deploy command: `wrangler dev` starts a local development server and waits for requests, so a hosted build can time out while the server remains running.

The repository's `frontend/wrangler.jsonc` specifies the Worker entry point and the `dist` assets directory. Cloudflare should use that configuration when running the deploy command. The frontend build receives `VITE_API_BASE_URL` as a build-time variable; the production value is `https://yfk5o3gvki.execute-api.eu-west-2.amazonaws.com`.

## Step 1: Verify the existing Lambda

The existing Lambda is:

- Function name: `clinic-booking-api`
- ARN: `arn:aws:lambda:eu-west-2:284443068612:function:clinic-booking-api`
- Region: `eu-west-2`
- Runtime: Python 3.12
- Architecture: x86_64
- Expected handler: `app.lambda_handler.handler`

Do not change the function runtime, architecture, handler, environment variables, VPC/network settings, or database configuration as part of this setup without reviewing the impact.

The API Gateway base URL currently configured in CI is:

`https://yfk5o3gvki.execute-api.eu-west-2.amazonaws.com`

Confirm that it is the correct deployed API base URL and that both `/health` and `/ready` work before enabling an automated production deployment. If API Gateway uses a named stage in its invoke URL, the stage path must be included consistently in the workflow's smoke tests and frontend build configuration.

## Step 2: Configure the AWS IAM deployment role

The GitHub Actions role is:

- Role name: `ClinicBookingGitHubActionsDeploy`
- ARN: `arn:aws:iam::284443068612:role/ClinicBookingGitHubActionsDeploy`

The OIDC provider should be `token.actions.githubusercontent.com`, with audience `sts.amazonaws.com`. Restrict the trust policy to this exact repository and the GitHub Actions `production` environment. The repository uses immutable owner and repository identifiers in its OIDC subject. The expected subject condition is:

`repo:RURIGIMK@122110352/clinic-booking-platform@1429661826:environment:production`

Do not use the older human-readable subject `repo:RURIGIMK/clinic-booking-platform:environment:production`; it does not match the immutable subject configured for this repository. Because the deployment job uses the `production` environment, the environment subject is the one to allow.

Attach a permissions policy limited to the one Lambda function. Required actions for this workflow are:

- `lambda:GetFunctionConfiguration`
- `lambda:UpdateFunctionCode`

Scope the resource to the exact Lambda ARN above. The role does not need `iam:PassRole`, permission to create functions, or broad administrator access for a code-only update.

## Step 3: Verify the existing GitHub production environment

The repository already has a `production` environment. Keep the existing environment and its Cloudflare configuration; do not recreate it or remove existing values.

Verify that these AWS entries are present:

- **Environment secret** `AWS_DEPLOY_ROLE_ARN`: `arn:aws:iam::284443068612:role/ClinicBookingGitHubActionsDeploy`
- **Environment variable** `AWS_LAMBDA_FUNCTION_NAME`: `clinic-booking-api`

The existing Cloudflare environment entries must remain in place:

- **Secret** `CLOUDFLARE_API_TOKEN`
- **Secret** `CLOUDFLARE_ACCOUNT_ID`

Do not store AWS access key IDs or secret access keys; the workflow uses OIDC. Use a Cloudflare token scoped to the required Worker deployment permissions only.

## Step 4: Verify the PostgreSQL schema before deployment

The application defines its schema in SQLAlchemy models and includes `Base.metadata.create_all()` plus a compatibility helper in a FastAPI startup hook. The Lambda adapter is configured with `lifespan="off"`, so do not assume that startup hook runs in Lambda. The deployment workflow does not run `create_all()`, alter tables, or apply migrations.

Use a read-only database session against the same PostgreSQL database used by the production API. Do not paste credentials into logs, commits, or chat. Confirm that these tables exist:

- `doctors`
- `doctor_working_hours`
- `patients`
- `appointments`

Confirm that `doctor_working_hours` includes `break_starts_at` and `break_ends_at`, and that `appointments` includes the columns defined in `backend/app/models.py`: `doctor_id`, `patient_id`, `starts_at`, `ends_at`, `status`, `cancellation_reason`, and `created_at`.

Run these read-only checks in a PostgreSQL SQL client:

```sql
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN (
    'doctors', 'doctor_working_hours', 'patients', 'appointments'
  )
ORDER BY table_name;

SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'doctor_working_hours'
ORDER BY ordinal_position;

SELECT indexname, indexdef
FROM pg_indexes
WHERE schemaname = 'public'
  AND tablename = 'appointments'
ORDER BY indexname;
```

Expected concurrency safeguard: the appointments table should have the partial unique index `uq_active_doctor_slot` on `(doctor_id, starts_at)` for rows where `status = 'booked'`. This lets PostgreSQL reject two active bookings for the same doctor's exact slot even when requests race. The application maps an `IntegrityError` from booking or rescheduling to HTTP 409. The index does not replace application validation for clinic hours, breaks, slot alignment, or overlapping intervals.

If a required table, column, or index is missing, stop and plan a reviewed migration with a backup and recovery procedure. Do not treat a successful `/ready` response as proof that the full application schema is correct: `/ready` currently checks database connectivity with `SELECT 1` only.

## Step 5: Verify booking concurrency safely

The current automated booking tests check sequential duplicate booking and slot release, but they do not prove that simultaneous PostgreSQL requests cannot both book the same slot. Verify this separately against a staging database that matches the production schema, using synthetic doctor and patient records only.

1. Choose a future, valid 30-minute slot for a synthetic doctor.
2. Submit two booking requests at the same time for the same doctor and `starts_at`, using separate database sessions.
3. Confirm that exactly one request succeeds and the other receives HTTP 409. Inspect the database to confirm there is only one active booking for that doctor and start time.
4. Repeat for rescheduling into a slot another active appointment already occupies.
5. Confirm that cancelling the winning booking releases the slot and that a new booking can then succeed.

Do not run a race test against real patient records or an actively used production slot. If staging verification cannot be performed, record concurrency as unverified rather than assuming the database constraint is present or effective.

## Step 6: Open a pull request and review the run

Open a pull request from a feature branch into `main`. The backend checks and frontend build should run, but deployment jobs should not run on the feature branch or pull request.

Review the changed workflow, Lambda requirements file, and this guide. Merge only after CI passes and the AWS role permissions, immutable OIDC trust subject, API base URL, health endpoints, PostgreSQL schema, and concurrency safeguard have been verified.

## Step 7: Verify a real deployment

After merging to `main`:

1. Open **Actions → CI/CD** in GitHub.
2. Confirm `backend` and `frontend` pass.
3. Confirm `deploy-backend` passes, including Lambda configuration checks and both API smoke tests.
4. Confirm `deploy-frontend` runs only after backend deployment succeeds.
5. Open the live frontend and perform a synthetic end-to-end test: list doctors, check availability, create a test booking, cancel it, and verify the slot becomes available again. Use only synthetic demo data.
6. If a deployment fails, read the failed step logs. Do not repeatedly rerun a failed deployment until the cause is understood.

## Cost and safety notes

- GitHub Actions uses the repository's available Actions allowance; monitor usage in GitHub billing.
- Updating an existing Lambda function adds no separate deployment service. Lambda and API Gateway runtime charges depend on usage.
- OIDC avoids storing long-lived AWS keys.
- The workflow does not deploy from feature branches, run database migrations, or create AWS resources.
- The workflow updates Lambda code before the frontend. If backend deployment or smoke tests fail, frontend deployment is skipped.
