# Backend auto-deployment setup

This repository deploys the backend to the existing AWS Lambda function and then deploys the frontend to Cloudflare Workers. Deployments are triggered only by a push to `main`, normally after a pull request is merged. Pull requests and feature branches run CI checks but do not deploy.

## What the workflow does

1. Runs the existing backend lint and test checks.
2. On `main` only, authenticates to AWS using GitHub's OpenID Connect (OIDC), without storing long-lived AWS access keys.
3. Confirms that the Lambda function uses Python 3.12 and x86_64, builds a Lambda ZIP package, and updates the function code.
4. Checks the deployed API's `/health` and `/ready` endpoints.
5. Only if the backend deployment and smoke tests pass, deploys the frontend to Cloudflare Workers.

The workflow deliberately does not create or alter database tables. Database schema changes need a separate, reviewed migration plan.

## Step 1: Verify the existing Lambda before enabling deployment

In AWS Console, open **Lambda**, select the function currently connected to the API Gateway endpoint, and record:

- Function name
- Runtime, expected to be Python 3.12
- Architecture, expected to be x86_64 for this workflow
- Handler, expected to be `app.lambda_handler.handler`
- Execution role and attached database/network configuration

Do not change the function runtime, architecture, handler, environment variables, VPC/network settings, or database configuration as part of this setup. If the runtime or architecture differs, update the workflow packaging target deliberately before enabling deployment.

The API Gateway base URL currently configured in CI is:

`https://yfk5o3gvki.execute-api.eu-west-2.amazonaws.com`

Confirm that it is the correct deployed API base URL and that both `/health` and `/ready` work before turning on automated deployments.

## Step 2: Create a narrowly scoped AWS IAM deployment role

Create an IAM role for GitHub Actions with a web identity / OIDC trust relationship.

The OIDC provider should be `token.actions.githubusercontent.com`, with audience `sts.amazonaws.com`. Restrict the trust policy to this exact repository and the GitHub Actions `production` environment. The subject condition should be:

`repo:RURIGIMK/clinic-booking-platform:environment:production`

Do not use a wildcard repository or branch subject. Since the workflow job uses the `production` environment, the environment subject is the one to allow.

Attach a permissions policy limited to the one Lambda function. Required actions for this workflow are:

- `lambda:GetFunctionConfiguration`
- `lambda:UpdateFunctionCode`

Scope the resource to the exact Lambda function ARN in `eu-west-2`. The role does not need `iam:PassRole`, permission to create functions, or broad administrator access for a code-only update.

Record the role ARN. Never paste credentials or secrets into the repository or chat.

## Step 3: Configure the GitHub production environment

In GitHub, open **Settings → Environments → New environment** and create `production`.

Add the following environment-scoped values:

- **Variable** `AWS_LAMBDA_FUNCTION_NAME`: exact existing Lambda function name
- **Secret** `AWS_DEPLOY_ROLE_ARN`: IAM role ARN created in Step 2
- **Secret** `CLOUDFLARE_API_TOKEN`: existing Cloudflare token used by the current frontend deployment
- **Secret** `CLOUDFLARE_ACCOUNT_ID`: existing Cloudflare account ID

Keep the Cloudflare values in place. Use a Cloudflare token scoped to the required Worker deployment permissions only. Do not store AWS access key IDs or secret access keys; the workflow uses OIDC.

If your repository already has the Cloudflare secrets at repository level, they can remain there. Environment-scoped values take precedence for jobs that use the `production` environment.

## Step 4: Check the application database is already initialized

The current application has schema creation and compatibility code in a FastAPI startup hook, while the Lambda adapter is configured with `lifespan="off"`. Do not assume that startup hook runs in Lambda. Before deployment, confirm that the production database already has all current tables and columns, including `break_starts_at` and `break_ends_at` in `doctor_working_hours`.

The new deployment job does not run `create_all()` or modify the production database. If schema changes are needed, make and test an explicit migration separately, with a backup/recovery plan. A code deployment should not silently become a production database migration.

## Step 5: Open a pull request and review the run

Push this branch and open a pull request into `main`. The backend checks and frontend build should run, but no deployment jobs should run on the feature branch or pull request.

Review the changed workflow, requirements file, and this guide. Merge only after the checks pass and the AWS values and role trust policy have been verified.

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
