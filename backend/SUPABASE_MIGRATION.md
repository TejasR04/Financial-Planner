# Supabase database migration

This procedure copies the complete local Meridian PostgreSQL database to a new,
empty Supabase project. It preserves application users, password hashes,
Alembic state, financial data, and encrypted Plaid access tokens.

Do not delete the local Docker volume after migration. Keep it as a rollback
copy until the hosted application has been verified and backed up separately.

## Prerequisites

- The Supabase project is provisioned and empty.
- Its direct or session-pooler host, port, database, and username are recorded.
- Its database password is stored privately.
- Docker Desktop is running.
- `backend/.env` still contains the existing `PLAID_TOKEN_ENCRYPTION_KEY`.

Use the direct Supabase endpoint when the workstation has IPv6 connectivity.
Otherwise use the session pooler on port 5432. Do not use transaction-pooler
port 6543 for `pg_restore` or Alembic.

## 1. Stop application writes

From `backend/`, stop the API while leaving PostgreSQL available:

```powershell
docker compose stop api migrate
docker compose up -d db
docker compose exec db pg_isready -U meridian -d meridian
```

Do not import files, refresh Plaid, register users, or otherwise write to the
local application after this point.

## 2. Create a local encrypted-data backup artifact

Create a custom-format dump inside the database container, then copy it into an
ignored local directory:

```powershell
New-Item -ItemType Directory -Force -Path backups | Out-Null
docker compose exec -T db pg_dump `
  --username=meridian `
  --dbname=meridian `
  --format=custom `
  --schema=public `
  --no-owner `
  --no-acl `
  --file=/tmp/meridian-full.dump
docker compose cp db:/tmp/meridian-full.dump backups/meridian-full.dump
Get-Item backups/meridian-full.dump
```

Treat this dump like the underlying financial database. Do not email it, upload
it to source control, or leave it in an unencrypted shared directory.

## 3. Restore into Supabase

Set connection fields only in the current PowerShell process. This avoids
putting the password in the command line or shell history:

```powershell
$env:PGHOST = "YOUR_SUPABASE_HOST"
$env:PGPORT = "5432"
$env:PGDATABASE = "postgres"
$env:PGUSER = "YOUR_SUPABASE_USERNAME"
$env:PGPASSWORD = Read-Host "Supabase database password"
```

Verify the resolved target before allowing a destructive clean restore:

```powershell
Write-Host "Target: $env:PGUSER@$env:PGHOST`:$env:PGPORT/$env:PGDATABASE"
```

The next command cleans objects in the target `public` schema. Run it only when
the displayed target is the new Supabase project:

```powershell
docker run --rm `
  --env PGHOST `
  --env PGPORT `
  --env PGDATABASE `
  --env PGUSER `
  --env PGPASSWORD `
  --volume "${PWD}/backups:/backups:ro" `
  postgres:16-alpine `
  pg_restore `
  --clean `
  --if-exists `
  --no-owner `
  --no-acl `
  --exit-on-error `
  --dbname=postgres `
  /backups/meridian-full.dump
```

Warnings about objects not existing during `--clean` can be benign on a new
project. Any command failure must be investigated before continuing.

## 4. Bring the schema to the repository head

Create an async SQLAlchemy URL without printing it. Password characters must be
URL-encoded in this URL. Supabase's session-pooler URL can be adapted by changing
the scheme and adding `ssl=require`:

```text
postgresql+asyncpg://USER:ENCODED_PASSWORD@HOST:5432/postgres?ssl=require
```

Set it temporarily, then run Alembic:

```powershell
$env:DATABASE_URL = Read-Host "SQLAlchemy Supabase URL"
python -m alembic current
python -m alembic upgrade head
python -m alembic current
```

The final revision must match the repository's single Alembic head:

```powershell
python -m alembic heads
```

## 5. Verify the copy

Compare row counts without selecting sensitive row contents. First inspect the
local database:

```powershell
docker compose exec -T db psql -U meridian -d meridian -Atc `
  "SELECT relname || '=' || n_live_tup FROM pg_stat_user_tables ORDER BY relname;"
```

Then inspect Supabase:

```powershell
docker run --rm `
  --env PGHOST `
  --env PGPORT `
  --env PGDATABASE `
  --env PGUSER `
  --env PGPASSWORD `
  postgres:16-alpine `
  psql --no-psqlrc --tuples-only --no-align --command `
  "SELECT relname || '=' || n_live_tup FROM pg_stat_user_tables ORDER BY relname;"
```

Statistics can lag, so exact validation should use `COUNT(*)` for important
tables if any figures differ. At minimum verify `users`, `institutions`,
`accounts`, `transactions`, `budget_categories`, `scenarios`, and
`alembic_version`.

Finally clear secrets from the shell process:

```powershell
Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
```

## 6. Application verification

Before retiring the local runtime, verify against the hosted database that:

- An existing user can sign in with the existing password.
- Account, transaction, budget, scenario, and investment totals match.
- Alembic reports the repository head.
- A manual Plaid refresh works with the original encryption key.
- A new record created through the API remains after an API restart.

Only after these checks should Cloud Run become the primary API. Retain the
local Docker volume and the protected dump until a separate backup strategy is
in place.
