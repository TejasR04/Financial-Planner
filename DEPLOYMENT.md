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
scale to zero. Plaid synchronization should be a separate authenticated Cloud
Run job triggered by Cloud Scheduler. That job is intentionally a separate
release step from the web service.
