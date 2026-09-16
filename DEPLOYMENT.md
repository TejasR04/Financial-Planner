# Production deployment

Meridian uses GitHub as the source of truth and CI/CD entry point:

- Vercel hosts the Next.js frontend and deploys from `main`.
- Cloud Run hosts FastAPI and deploys through GitHub Actions.
- Supabase hosts PostgreSQL.
- Google Secret Manager holds backend credentials.

## 1. Vercel

Import `TejasR04/Financial-Planner` in Vercel and keep the repository root as
the project root. Add this production environment variable after the first
Cloud Run deployment:

```text
NEXT_PUBLIC_API_URL=https://YOUR-CLOUD-RUN-SERVICE.run.app/api/v1
```

Vercel automatically deploys pushes to `main` and creates previews for pull
requests. Record the production URL for the backend configuration below.

## 2. Google Cloud secrets

Create these Secret Manager secrets in the Cloud project. Their values never
belong in GitHub or in the repository:

```text
database-url
jwt-secret-key
plaid-client-id
plaid-secret
plaid-token-encryption-key
gemini-api-key
```

`database-url` must be the SQLAlchemy async Supabase session-pooler URL. Keep
the existing Plaid encryption key or previously stored Plaid tokens will no
longer decrypt.

## 3. GitHub production environment

In GitHub, open **Settings > Environments**, create `production`, and add these
environment variables:

```text
GCP_PROJECT_ID=your-google-cloud-project-id
GCP_WORKLOAD_IDENTITY_PROVIDER=projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/github/providers/financial-planner
GCP_SERVICE_ACCOUNT=github-cloud-run@PROJECT_ID.iam.gserviceaccount.com
FRONTEND_URL=https://your-project.vercel.app
PLAID_ENV=sandbox
```

Use Google Workload Identity Federation for GitHub authentication. Do not
create or upload a long-lived service-account JSON key. Restrict the provider
to `TejasR04/Financial-Planner` and the `main` branch, and grant the deployment
service account only the roles needed to build/deploy Cloud Run and use the
runtime service account.

The Cloud Run runtime identity needs `Secret Manager Secret Accessor` for the
six secrets. Source deployments also require the documented Cloud Build and
Artifact Registry permissions.

## 4. Database migration

Apply migrations before a backend revision that needs them:

```powershell
cd backend
python -m alembic upgrade head
```

For now this is an explicit release step using the production Supabase
`DATABASE_URL`. Do not run migrations concurrently from multiple deployments.

## 5. Deploy

Push to `main`, or open **Actions > Deploy backend > Run workflow**. The
workflow builds the existing `backend/Dockerfile` and deploys `meridian-api` in
`us-east1`. The first service must be made publicly invokable because browser
clients cannot attach Google Cloud IAM credentials:

```powershell
gcloud run services add-iam-policy-binding meridian-api `
  --region us-east1 `
  --member="allUsers" `
  --role="roles/run.invoker"
```

After deployment, put the reported Cloud Run URL into Vercel's
`NEXT_PUBLIC_API_URL` and redeploy the frontend. Verify:

```powershell
Invoke-RestMethod https://YOUR-CLOUD-RUN-SERVICE.run.app/health
Invoke-RestMethod https://YOUR-CLOUD-RUN-SERVICE.run.app/health/ready
```

## Plaid scheduling

The API deployment disables the in-process Plaid loop because Cloud Run may
scale to zero. The one-shot runner is `python -m app.jobs.plaid_sync`. Deploy it
as a private Cloud Run Job with Cloud Scheduler at **8 AM and 8 PM Eastern**
(`America/New_York`, including daylight-saving changes). It uses the same
database lease as the local polling loop, commits each user independently,
and exits unsuccessfully if any institution fails so Cloud Run can retry.

This is an explicit release step; committing this code does **not** activate
the schedule. First deploy the backend revision containing the runner. Enable
the Cloud Scheduler API, and provision two service accounts:

- Runtime account: Secret Accessor for the five secrets referenced by the script.
- Scheduler account: only needs Cloud Run Invoker on this job (script grants it).

The operator needs Cloud Run deployment/IAM and Cloud Scheduler management
permissions, plus permission to act as both service accounts. No public access
is granted to the job. Use the session-pooler database URL, not a transaction
pooler, because the lease is session-scoped. Cloud Scheduler and job executions
may incur Google Cloud charges.

```powershell
./scripts/deploy-plaid-sync.ps1 `
  -ProjectId YOUR_PROJECT_ID `
  -RuntimeServiceAccount plaid-sync@YOUR_PROJECT_ID.iam.gserviceaccount.com `
  -SchedulerServiceAccount plaid-scheduler@YOUR_PROJECT_ID.iam.gserviceaccount.com `
  -FrontendUrl https://YOUR_FRONTEND.vercel.app `
  -PlaidEnvironment production
```

Use `sandbox` if the existing linked Items are sandbox Items. The script reuses
the ready API image digest; rerun it after backend releases to update the job.
It does not execute a sync immediately. Validate the first scheduled execution
under Cloud Run > Jobs > meridian-plaid-sync, inspect failure logs, and configure
an alert on failed executions. To pause without deleting anything:

```powershell
gcloud scheduler jobs pause meridian-plaid-sync --location=us-east1 --project=YOUR_PROJECT_ID
```

This imports Plaid's latest available transactions/accounts/holdings. It does
not force a bank fetch through the separately enabled Transactions Refresh
add-on. See [Plaid freshness](https://plaid.com/docs/transactions/) and
[Cloud Run scheduled jobs](https://docs.cloud.google.com/run/docs/execute/jobs-on-schedule).
