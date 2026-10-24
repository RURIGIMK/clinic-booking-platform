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

The OIDC provider should be `token.actions.githubusercontent.com`, with audience `sts.amazonaws.com`. Restrict the trust policy to this exact repository and the GitHub Actions `production` environment. The subject condition should be:

`repo:RURIGIMK/clinic-booking-platform:environment:production`

Because the deployment job uses the `production` environment, the environment subject is the one to allow.

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

## Step 4: Check the application database is already initialized

The current application has schema creation and compatibility code in a FastAPI startup hook, while the Lambda adapter is configured with `lifespan="off"`. Do not assume that startup hook runs in Lambda. Before deployment, confirm that the production database already has all current tables and columns, including `break_starts_at` and `break_ends_at` in `doctor_working_hours`.

The deployment job does not run `create_all()` or modify the production database. If schema changes are needed, make and test an explicit migration separately, with a backup/recovery plan. A code deployment should not silently become a production database migration.

## Step 5: Open a pull request and review the run

Open a pull request from `feature/backend-auto-deployment` into `main`. The backend checks and frontend build should run, but no deployment jobs should run on the feature branch or pull request.

Review the changed workflow, requirements file, and this guide. Merge only after checks pass and the AWS role permissions, trust policy, API base URL, health endpoints, and database schema readiness have been verified.

## Step 6: Verify a real deployment

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
