# Meridian Backend

FastAPI backend for the Meridian financial planning platform. See
[`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full design record (frontend
analysis, domain model, DB schema, API contracts, AI tool registry, and the
phased roadmap this repo implements against).

## What's implemented

- **Phase 0 — Scaffolding.** Layered folder structure, config, JWT auth,
  async SQLAlchemy session setup, Docker Compose, Alembic wiring.
- **Phase 1 — Simulation core.** `app/simulation/engine.py` and the services
  in `app/services/*` are fully implemented and unit-tested with no DB
  dependency — this is the actual product core.
- **Phase 2 — Persistence + core CRUD.** ORM models for the full schema;
  repositories for User, Account, Transaction, IncomeSource,
  Liability, and Scenario, all fully implemented. Live routes:
  `/auth/*`, `/users/me*`, `/accounts*`, `/transactions*` (including
  `/transactions/import/csv`). Manual entry uses the account and transaction
  repositories directly; `CSVImportProvider` normalizes uploaded rows.
- **Phase 3 — Projections API.** `ScenarioService` (the "run a scenario"
  computation, composing NetWorth + Retirement + optional Monte Carlo) is
  implemented and tested. Live routes: `/scenarios*` full CRUD,
  `/scenarios/{id}/duplicate`, `/scenarios/{id}/run` (persists a
  `SimulationRun`), `/scenarios/{id}/runs` (history), `/scenarios/compare`,
  plus the full `/simulations/*` set — `retirement`, `net-worth`,
  `cash-flow`, `monte-carlo`, `debt-optimization`.
- **Phase 4 — Recommendations & health score.** `PortfolioAllocationService`
  (filled a gap from the original spec — was named but not built) and
  `InsightService` are new. Repositories for Holding, Recommendation,
  Insight, and FinancialHealthScore, plus `snapshot_builder.py` (the one
  DB-aware assembly point that turns repositories into a `FinancialSnapshot`
  for the pure services to consume). Live routes: `/recommendations`,
  `/recommendations/generate`, `/recommendations/{id}` (apply/dismiss),
  `/insights`, `/financial-health`, `/financial-health/recalculate`,
  `/accounts/allocation`. This is what unblocks the Insights page and the
  Overview page's allocation chart.
- **Phase 5 — AI layer.** `ToolRegistry` with all 13 registered tools from the spec
  registered and wired to the real services (13 including
  `find_earliest_retirement_age`, which directly backs the "can I retire at
  58" example in the spec) — `AgentOrchestrator` implements the full
  Gemini function-calling loop; `POST /agent/chat` is live when
  `GEMINI_API_KEY` is configured.
- **Phase 6 — Plaid integration.** Plaid Link, encrypted access-token
  storage, account/transaction/holding synchronization, reconnect flows,
  and singleton scheduled polling are wired through `PlaidProvider`.

See `/docs` once running (or `ARCHITECTURE.md` §7) for the current API
surface. OpenAPI generation and the unit/Postgres integration suites are
exercised by CI rather than duplicated here as volatile counts.

Monte Carlo projections are implemented in `simulation/monte_carlo.py` and
used by both scenario runs and the ad-hoc simulation endpoint. Plaid webhooks
are not implemented; synchronization currently uses explicit and scheduled
polling.

## Running locally

```bash
cp .env.example .env        # fill in JWT_SECRET_KEY and GEMINI_API_KEY
docker compose up --build
```

The API comes up on `http://localhost:8000`. Interactive docs at
`/docs`. Health check at `/health`.

To generate the initial migration once the containers are up:

```bash
docker compose exec api alembic revision --autogenerate -m "initial schema"
docker compose exec api alembic upgrade head
```

## Running tests

The service and simulation-engine tests have no DB dependency and run
directly:

```bash
pip install -r requirements-dev.txt
pytest tests/unit -v
```

Integration tests (`tests/integration/`, DB-backed) run in the disposable
Postgres Docker Compose stack described in `docker-compose.test.yml`.

Runtime and development dependencies are declared once in `pyproject.toml`.
`requirements.txt` is the pinned production lock; `requirements-dev.txt` is
the pinned development/test lock. Regenerate both after dependency changes:

```bash
python -m piptools compile --strip-extras --resolver=backtracking --output-file=requirements.txt pyproject.toml
python -m piptools compile --strip-extras --resolver=backtracking --extra=dev --output-file=requirements-dev.txt pyproject.toml
```

The backend quality gates used by CI can be run locally with:

```bash
python -m ruff check app tests
python -m mypy
python -m pytest -q --cov=app --cov-branch --cov-report=term-missing:skip-covered --cov-fail-under=60
```

## Project layout

See `ARCHITECTURE.md` §6 for the full annotated tree. In short:

```
app/domain/        framework-free entities, enums, value objects
app/simulation/     the deterministic engine — compounding, amortization, tax, Monte Carlo
app/services/         business services built on the engine (one calculation, one place)
app/persistence/       SQLAlchemy models + repositories (ORM <-> domain translation)
app/providers/           FinancialDataProvider abstraction (Plaid/CSV)
app/ai/                    tool registry + agent orchestration
app/api/                    FastAPI routes (thin — no business logic)
app/schemas/                  Pydantic request/response DTOs
```

## Design rules this codebase enforces

- `app/services/*` and `app/simulation/*` never import `fastapi` or
  `sqlalchemy`. They're plain Python, unit-testable with no fixtures beyond
  Decimal inputs.
- API route handlers do not contain arithmetic or SQL. They call a
  service/repository and shape the response.
- AI tools in `app/ai/tools/*` unpack arguments, call one service, and
  return its result — nothing else.
- Every financial calculation exists exactly once. If you find yourself
  reimplementing compounding, amortization, or tax math anywhere outside
  `app/simulation/engine.py`, that's a bug.
