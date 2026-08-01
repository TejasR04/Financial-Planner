# Meridian Financial Planner

Meridian is a full-stack financial-planning application with a Next.js
frontend and a FastAPI/PostgreSQL backend.

## Prerequisites

- Node.js 22 and npm 11
- Python 3.12 for direct backend development
- Docker with Docker Compose for the database, API, integration tests, and E2E tests

## Run locally

Create the backend environment file, then start PostgreSQL and the API:

```bash
cd backend
cp .env.example .env
# Set at least JWT_SECRET_KEY in .env.
docker compose up --build
```

In another terminal, install the locked frontend dependencies and start Next.js:

```bash
npm ci
npm run dev
```

The frontend is available at `http://localhost:3000`; the API and its OpenAPI
documentation are at `http://localhost:8000` and `http://localhost:8000/docs`.

## Quality checks

Run the frontend checks from the repository root:

```bash
npm run lint
npm run typecheck
npm run test:unit
npm run build
```

The E2E command owns an isolated Docker Compose project with a migrated test
database and API, so Docker must be running:

```bash
npm run test:e2e
```

Run backend checks from `backend/` after installing the pinned development
dependencies:

```bash
python -m pip install -r requirements-dev.txt
python -m ruff check app tests
python -m mypy
python -m pytest tests/unit -q
docker compose -f docker-compose.test.yml run --rm integration-test
```

## Documentation

- [Backend setup and quality workflow](backend/README.md)
- [Architecture and design record](backend/ARCHITECTURE.md)
- [Gemini integration](backend/AI_GEMINI.md)
