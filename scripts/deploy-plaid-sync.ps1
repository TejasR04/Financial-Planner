# Explicit release step: creates/updates a Cloud Run job and its scheduler.
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$ProjectId,
    [Parameter(Mandatory)][string]$RuntimeServiceAccount,
    [Parameter(Mandatory)][string]$SchedulerServiceAccount,
    [Parameter(Mandatory)][string]$FrontendUrl,
    [Parameter(Mandatory)][ValidateSet('sandbox', 'production')][string]$PlaidEnvironment,
    [string]$Region = 'us-east1',
    [string]$TimeZone = 'America/New_York'
)
$ErrorActionPreference = 'Stop'

function Invoke-Gcloud {
    & gcloud @args
    if ($LASTEXITCODE -ne 0) { throw "gcloud failed; see output above." }
}

# Reuse the exact ready API revision, not a mutable image tag.
$revision = Invoke-Gcloud run services describe meridian-api --project=$ProjectId --region=$Region '--format=value(status.latestReadyRevisionName)'
if (-not $revision) { throw 'Deploy the backend containing app.jobs.plaid_sync first.' }
$image = Invoke-Gcloud run revisions describe $revision --project=$ProjectId --region=$Region '--format=value(status.imageDigest)'
if (-not $image) { throw 'Could not resolve the ready API image digest.' }

$jobName = 'meridian-plaid-sync'
$environmentFile = New-TemporaryFile
try {
    @{
        ENVIRONMENT = 'production'; FRONTEND_URL = $FrontendUrl
        CORS_ALLOW_ORIGINS = (ConvertTo-Json -Compress -InputObject @($FrontendUrl))
        REFRESH_COOKIE_SECURE = 'true'; PLAID_ENV = $PlaidEnvironment
        PLAID_AUTO_SYNC_ENABLED = 'false'; DATABASE_POOL_SIZE = '2'; DATABASE_MAX_OVERFLOW = '1'
    } | ConvertTo-Json | Set-Content -LiteralPath $environmentFile.FullName -Encoding utf8
    Invoke-Gcloud run jobs deploy $jobName --project=$ProjectId --region=$Region --image=$image `
    --service-account=$RuntimeServiceAccount --command=python '--args=-m,app.jobs.plaid_sync' `
    --tasks=1 --parallelism=1 --max-retries=1 --task-timeout=1800s --memory=512Mi --cpu=1 `
    "--env-vars-file=$($environmentFile.FullName)" `
    '--set-secrets=DATABASE_URL=database-url:latest,JWT_SECRET_KEY=jwt-secret-key:latest,PLAID_CLIENT_ID=plaid-client-id:latest,PLAID_SECRET=plaid-secret:latest,PLAID_TOKEN_ENCRYPTION_KEY=plaid-token-encryption-key:latest' --quiet
} finally {
    Remove-Item -LiteralPath $environmentFile.FullName
}

Invoke-Gcloud run jobs add-iam-policy-binding $jobName --project=$ProjectId --region=$Region `
    "--member=serviceAccount:$SchedulerServiceAccount" --role=roles/run.invoker --quiet

$existing = Invoke-Gcloud scheduler jobs list --project=$ProjectId --location=$Region "--filter=name:$jobName" '--format=value(name)'
$operation = if ($existing) { 'update' } else { 'create' }
Invoke-Gcloud scheduler jobs $operation http $jobName --project=$ProjectId --location=$Region `
    '--schedule=0 8,20 * * *' --time-zone=$TimeZone `
    "--uri=https://run.googleapis.com/v2/projects/$ProjectId/locations/$Region/jobs/${jobName}:run" `
    --http-method=POST --oauth-service-account-email=$SchedulerServiceAccount `
    '--headers=Content-Type=application/json' '--message-body={}' --max-retry-attempts=1 --quiet

Write-Output "Scheduled $jobName for 8 AM and 8 PM in $TimeZone. Verify its first execution in Cloud Run Jobs."
