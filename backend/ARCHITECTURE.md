# Meridian Backend — Architecture

This document is the design record for the FastAPI backend behind the Meridian
frontend (`TejasR04/Financial-Planner`). It covers what the frontend actually
needs, the domain model behind it, the database schema, the service
architecture, the AI tool layer, and a phased build order.

---

## 1. Frontend analysis

The frontend is a Next.js app with **5 pages**, all currently rendering from a
single static file (`lib/data.ts`) with zero network calls. There is no chat
UI yet, but the shape of the data makes the intended product clear: a
deterministic simulation engine with an AI layer that explains results.

| Page | Route | What it needs from the backend |
|---|---|---|
| Overview | `/` | KPI summary (net worth, liquid assets, monthly cash flow, savings rate) with 12-mo sparkline + delta; net-worth time series (assets/liabilities/net, with a projected flag); allocation breakdown; recent transactions; AI insights feed; cash-flow series (income vs. expenses); life-plan milestones |
| Accounts | `/accounts` | Full account list with balances, institution, type, sync status, APY; asset/liability aggregates; link-account and sync actions |
| Projections | `/projections` | Named scenarios (baseline + variants) with net-worth-at-target-age, retirement age, monthly contribution, Monte-Carlo success rate, and a full net-worth trajectory series; scenario comparison table; editable assumptions (retirement age, savings rate, expected return, inflation, withdrawal rate) that **recompute a projection live**; sensitivity rows (impact of nudging one input) |
| Insights | `/insights` | Ranked recommendations (title, body, projected $ impact, effort, category, confidence) with apply/dismiss actions; AI insights feed; a composite financial health score with sub-scores (liquidity, diversification, debt ratio, savings discipline) |
| Settings | `/settings` | User profile (name, email, base currency, DOB); planning defaults (target retirement age, target equity allocation, default withdrawal rate, include-Social-Security toggle); connected institutions with health status; notification preferences |

Other UI signals:
- **Command palette** — "Link account", "Export report" — implies async
  action endpoints and a report-generation job, not just reads.
- **Milestones/timeline** — implies a `Goal`-like entity with a target
  date/age and amount, distinct from a `Scenario`.
- **"Recommended" badge on best scenario** — implies scenario ranking is a
  backend computation, not a frontend heuristic.
- Every dollar figure that currently looks "live" (KPI deltas, sparkline,
  "4 minutes ago") is actually static — the backend needs to make these
  genuinely real without changing the visual contract.

### Assumptions the frontend currently bakes in (to fix in the backend)
- Single implicit user, single currency (USD), no multi-tenancy.
- Scenarios are hardcoded triples — the backend needs proper CRUD-able
  scenarios with arbitrary assumption sets.
- "Monte Carlo success rate" is a static number — no seed, no run metadata,
  no distribution. The backend needs to actually produce this.
- No error states, no loading states, no pagination anywhere — the frontend
  will need incremental changes once real data has latency and can fail
  (flagged in §8, Frontend/Backend mismatches).

---

## 2. Product framing

This is **not** a budgeting app. The product is a deterministic financial
simulation engine with an LLM orchestration layer on top. Concretely:

- All math (compounding, amortization, tax, contribution limits, retirement
  projections) lives in **plain, framework-independent Python services**.
  These are unit-testable in isolation, with no FastAPI or SQLAlchemy import
  anywhere in them.
- The LLM never computes a number. It calls a tool, gets a structured
  (Pydantic) result back, and narrates it.
- The same services back REST endpoints, scheduled jobs (e.g. nightly
  recommendation refresh), and AI tools — there is exactly one
  implementation of every calculation.

---

## 3. Layered architecture

```
API layer (FastAPI routers)          <- HTTP only: parse request, call service, serialize response
        |
AI agent layer (orchestrator + tool registry)   <- calls the SAME services as the API layer
        |
Business services (pure Python)      <- RetirementProjectionService, TaxCalculationService, ...
        |
Simulation engine (pure Python)      <- compounding, amortization, tax brackets, inflation, contribution limits
        |
Domain models (dataclasses/value objects)   <- Account, Transaction, Scenario, ProjectionResult, ...
        |
Persistence layer (SQLAlchemy repositories) <- translates domain <-> ORM rows
        |
External integrations (Plaid, CSV, manual entry)  <- normalized behind FinancialDataProvider
```

Rules enforced by the folder structure and by code review / CI lint:
- `app/services/*` and `app/simulation/*` **must not** import `fastapi`,
  `sqlalchemy`, or anything under `app/api/*`.
- `app/api/*` route handlers contain no arithmetic and no SQL — they call a
  service or repository and shape the response.
- `app/ai/tools/*` contain no business logic — each tool function unpacks
  its typed arguments, calls a service, and returns the service's typed
  result.

---

## 4. Domain model

Core entities (see `app/domain/entities.py` for the actual dataclasses):

- **User** — identity, base currency, date of birth (drives horizon math).
- **PlanningProfile** — 1:1 with User. Target retirement age, target equity
  allocation, default withdrawal rate, include-Social-Security flag,
  inflation assumption, expected-return assumption. Backs the Settings →
  Planning tab and seeds new scenarios.
- **Institution** — a linked data source (Plaid item, or manual).
- **Account** — normalized account (Investment / Depository / Retirement /
  Credit / Loan / Property), always in the user's base currency, sourced
  from exactly one `FinancialDataProvider`.
- **Holding** — investment position within an Investment/Retirement account
  (symbol, quantity, cost basis, asset class) — needed for allocation and
  tax-lot-aware recommendations even though the current UI only shows
  aggregated allocation.
- **Transaction** — normalized transaction with category, linked account,
  and a `TransactionType` (income, expense, transfer, contribution).
- **IncomeSource** — salary/other income with growth-rate assumption
  (separate from raw transactions — projections need a forward-looking
  income model, not just historical transactions).
- **Liability** — loan/credit detail (principal, rate, term, minimum
  payment) — superset of what `Account` exposes, needed for amortization.
- **Goal** — the backend entity behind the "Life plan" milestones: target
  amount, target date/age, priority, linked account(s) optional.
- **Scenario** — a named, versioned bundle of `PlanningAssumptions`
  (retirement age, savings rate, expected return, inflation, withdrawal
  rate, contribution amount) plus a baseline flag.
- **SimulationRun** — the persisted result of running the simulation engine
  against a Scenario: net-worth trajectory, retirement-age feasibility,
  Monte Carlo success rate, run metadata (seed, engine version, timestamp).
  Scenario is the *input*, SimulationRun is the *output* — this split is
  what lets Monte Carlo / re-runs be added later without touching Scenario.
- **Recommendation** — generated by `RecommendationEngine`, with category,
  projected impact, effort, confidence, and a status (new/applied/dismissed).
- **Insight** — lighter-weight, non-actionable observation (opportunity /
  alert / observation) surfaced alongside recommendations.
- **FinancialHealthScore** — composite + sub-scores, versioned by
  calculation date so history can be charted later.

---

## 5. Database schema

PostgreSQL via SQLAlchemy 2.0 (async) + Alembic migrations. Money stored as
`NUMERIC(18,2)` (never float). All tables have `id: UUID`, `created_at`,
`updated_at`.

```
users
  id, email (unique), hashed_password, full_name, base_currency,
  date_of_birth, created_at, updated_at

planning_profiles
  id, user_id (FK, unique), target_retirement_age, target_equity_allocation,
  default_withdrawal_rate, include_social_security, expected_return,
  inflation_rate, updated_at

institutions
  id, user_id (FK), name, provider (plaid|manual|csv), external_item_id,
  status (healthy|attention|error), last_synced_at

accounts
  id, user_id (FK), institution_id (FK, nullable), name, type
  (investment|depository|retirement|credit|loan|property), mask,
  currency, balance, apy, status (connected|attention|manual),
  external_account_id, updated_at

holdings
  id, account_id (FK), symbol, name, quantity, cost_basis,
  market_value, asset_class (equity|fixed_income|real_estate|cash|alt),
  as_of

transactions
  id, account_id (FK), posted_at, merchant, category, amount,
  type (income|expense|transfer|contribution), status (cleared|pending),
  external_transaction_id

income_sources
  id, user_id (FK), name, annual_amount, growth_rate, type (salary|other),
  active

liabilities
  id, account_id (FK, unique), principal, interest_rate, term_months,
  minimum_payment, origination_date

goals
  id, user_id (FK), title, target_amount, target_date, target_age,
  priority, status (upcoming|active|done), linked_account_id (nullable)

scenarios
  id, user_id (FK), name, description, is_baseline,
  retirement_age, savings_rate, monthly_contribution,
  expected_return, inflation_rate, withdrawal_rate,
  created_at, updated_at

simulation_runs
  id, scenario_id (FK), engine_version, seed, method (deterministic|monte_carlo),
  net_worth_at_target_age, success_rate, trajectory (JSONB: [{year, p10,p50,p90}]),
  assumptions_snapshot (JSONB), created_at

recommendations
  id, user_id (FK), title, body, category, impact_value, effort
  (low|medium|high), confidence, status (new|applied|dismissed),
  generated_at, source_run_id (FK, nullable)

insights
  id, user_id (FK), kind (opportunity|alert|observation), text, meta,
  generated_at

financial_health_scores
  id, user_id (FK), overall, liquidity, diversification, debt_ratio,
  savings_discipline, calculated_at
```

Indexes: `accounts(user_id)`, `transactions(account_id, posted_at desc)`,
`scenarios(user_id)`, `simulation_runs(scenario_id, created_at desc)`,
`recommendations(user_id, status)`.

---

## 6. Folder structure

```
backend/
  app/
    main.py                     # FastAPI app factory, router mounting, middleware
    core/
      config.py                 # Pydantic Settings (env-driven)
      security.py                # JWT issue/verify, password hashing
      database.py                 # async engine/session factory
      exceptions.py                # domain exceptions -> HTTP mapping
    domain/
      entities.py                  # framework-free dataclasses (User, Account, Scenario, ...)
      enums.py
      value_objects.py             # Money, Rate, AgeHorizon, etc.
    persistence/
      models.py                     # SQLAlchemy ORM tables
      session.py
      repositories/
        base.py                      # generic repository interface
        account_repository.py
        scenario_repository.py
        transaction_repository.py
        recommendation_repository.py
        user_repository.py
    simulation/
      engine.py                     # SimulationEngine: growth, amortization, tax, inflation
      assumptions.py                 # PlanningAssumptions value object + defaults
      monte_carlo.py                  # pluggable sampler, deterministic engine used by default
      tax_tables.py                    # federal/state bracket data, versioned by year
    services/
      cash_flow_projection_service.py
      net_worth_projection_service.py
      retirement_projection_service.py
      tax_calculation_service.py
      debt_optimization_service.py
      portfolio_allocation_service.py
      recommendation_engine.py
      financial_health_service.py
      scenario_service.py
    providers/
      base.py                        # FinancialDataProvider ABC
      plaid_provider.py
      manual_provider.py
      csv_import_provider.py
      normalizer.py                   # provider payload -> domain Account/Transaction
    ai/
      tool_registry.py                 # ToolRegistry: name -> (schema, handler)
      tool_schemas.py                   # OpenAI-compatible JSON schemas, generated from Pydantic
      agent.py                          # orchestration loop (LLM <-> tools)
      tools/
        forecast_tools.py
        tax_tools.py
        debt_tools.py
        investment_tools.py
        scenario_tools.py
        recommendation_tools.py
    schemas/                              # Pydantic request/response DTOs (API boundary only)
      user.py, auth.py, account.py, transaction.py, scenario.py,
      simulation.py, recommendation.py, goal.py, insight.py
    api/
      deps.py                              # get_db, get_current_user, etc.
      v1/
        router.py                          # aggregates all route modules
        routes/
          auth.py
          users.py
          accounts.py
          transactions.py
          goals.py
          scenarios.py
          simulations.py
          recommendations.py
          insights.py
          agent.py                          # chat endpoint -> ai.agent
  alembic/
    env.py, versions/
  tests/
    unit/            # services + simulation engine, no DB, no HTTP
    integration/      # API + DB, using a test Postgres/sqlite
  Dockerfile
  docker-compose.yml
  pyproject.toml / requirements.txt
  alembic.ini
  .env.example
```

---

## 7. API contracts (v1)

All under `/api/v1`. Auth via `Authorization: Bearer <JWT>`. Pagination via
`?limit=&offset=` returning `{items, total, limit, offset}`.

```
POST   /auth/register
POST   /auth/login                       -> {access_token, refresh_token}
POST   /auth/refresh

GET    /users/me
PATCH  /users/me
GET    /users/me/planning-profile
PATCH  /users/me/planning-profile

GET    /accounts                          -> list, supports ?type=
POST   /accounts                          -> manual account creation
GET    /accounts/{id}
PATCH  /accounts/{id}
DELETE /accounts/{id}
POST   /accounts/{id}/sync                -> re-pull from provider
POST   /accounts/link/plaid/link-token     -> Plaid Link session
POST   /accounts/link/plaid/exchange        -> exchange public_token

GET    /transactions                        -> filters: account_id, category, date range
POST   /transactions                          -> manual entry
PATCH  /transactions/{id}
POST   /transactions/import/csv                -> CSVImportProvider

GET    /goals
POST   /goals
PATCH  /goals/{id}
DELETE /goals/{id}

GET    /scenarios
POST   /scenarios
GET    /scenarios/{id}
PATCH  /scenarios/{id}
DELETE /scenarios/{id}
POST   /scenarios/{id}/duplicate
POST   /scenarios/compare                    -> body: [scenario_id, ...] -> comparison table

POST   /simulations/net-worth                 -> body: assumptions (ad-hoc, unsaved) -> NetWorthProjection
POST   /simulations/retirement                -> RetirementProjection
POST   /simulations/cash-flow                  -> CashFlowProjection
POST   /simulations/monte-carlo                 -> MonteCarloResult
POST   /scenarios/{id}/run                        -> persists a SimulationRun for a saved scenario
GET    /scenarios/{id}/runs                        -> history of runs

GET    /recommendations                             -> ?status=
POST   /recommendations/generate                     -> triggers RecommendationEngine
PATCH  /recommendations/{id}                           -> apply/dismiss

GET    /insights

GET    /financial-health                                -> latest score
POST   /financial-health/recalculate

POST   /agent/chat                                        -> {message, conversation_id} -> {reply, tool_calls[], structured_results[]}
```

Every list endpoint response is `{data: [...], meta: {...}}`; every compute
endpoint (`/simulations/*`, `/scenarios/{id}/run`) returns the exact
Pydantic model produced by the corresponding service, so REST and the AI
tool layer are byte-for-byte the same shape.

---

## 8. Reusable services (signatures)

All pure Python, `app/services/*`, take/return dataclasses or Pydantic
models — never ORM rows, never FastAPI request objects.

- **RetirementProjectionService.project(profile, accounts, income, assumptions) -> RetirementProjection**
- **NetWorthProjectionService.project(accounts, liabilities, assumptions, years) -> NetWorthProjection**
- **CashFlowProjectionService.project(income_sources, expenses, months) -> CashFlowProjection**
- **TaxCalculationService.estimate(income, filing_status, state, deductions) -> TaxEstimate**
- **DebtOptimizationService.optimize(liabilities, extra_monthly_payment, strategy) -> DebtPayoffPlan** (avalanche/snowball)
- **PortfolioAllocationService.analyze(holdings, target_allocation) -> AllocationAnalysis**
- **RecommendationEngine.generate(user_snapshot) -> list[Recommendation]** — composes the above services, does not compute anything itself
- **FinancialHealthService.score(user_snapshot) -> FinancialHealthScore**
- **ScenarioService** — CRUD orchestration + calls `RetirementProjectionService`/`NetWorthProjectionService` on `run()`

The `simulation/engine.py` module underlies all of these:
`compound_growth`, `real_return`, `amortize_loan`, `contribution_limit`,
`employer_match`, `estimate_federal_tax`, `inflate`, `project_series`.
Monte Carlo is added later purely by swapping the sampler in
`simulation/monte_carlo.py` — the deterministic path is the default and the
services never know which one ran.

---

## 9. Provider abstraction

```
FinancialDataProvider (ABC)
  get_accounts(user) -> list[NormalizedAccount]
  get_transactions(user, since) -> list[NormalizedTransaction]
  get_holdings(user, account_id) -> list[NormalizedHolding]

PlaidProvider(FinancialDataProvider)     # calls Plaid, maps Plaid types -> normalized
ManualProvider(FinancialDataProvider)     # reads directly from the DB (user-entered)
CSVImportProvider(FinancialDataProvider)   # parses uploaded CSV -> normalized
```

Nothing outside `app/providers/` ever imports a Plaid SDK type. Sync jobs and
`POST /accounts/{id}/sync` call `provider.get_accounts()` /
`normalizer.to_domain_account()` and hand the result to the repository.

---

## 10. AI agent architecture

```
ToolRegistry
  register(name, pydantic_input_schema, pydantic_output_schema, handler)
  to_openai_tools() -> list[dict]     # JSON schema for tool-calling APIs
  dispatch(name, raw_args) -> BaseModel

AgentOrchestrator
  handle_message(user, message, history) -> AgentResponse
    1. load user context (accounts/profile summary — kept small, not the full ledger)
    2. call LLM with tools = registry.to_openai_tools()
    3. for each tool_call the LLM emits: registry.dispatch(...) -> structured result
       (never hand-computed by the model)
    4. feed structured results back to the LLM for a final natural-language
       explanation, with an explicit system instruction: "state only what
       is present in the structured results; do not invent numbers"
    5. return {reply, tool_calls, structured_results} so the frontend can
       render both the prose and, later, an inline chart/table from the
       structured payload
```

Tool catalog (`app/ai/tools/*`), each a thin wrapper around one service call:

- `forecast_tools.py` — `forecast_retirement`, `forecast_net_worth`, `forecast_cash_flow`
- `tax_tools.py` — `estimate_taxes`, `calculate_hsa_tax_savings`, `calculate_roth_vs_traditional`
- `debt_tools.py` — `prioritize_debt_payoff`
- `investment_tools.py` — `calculate_401k_match`, `analyze_allocation`
- `scenario_tools.py` — `compare_scenarios`, `run_monte_carlo`, `optimize_monthly_surplus`
- `recommendation_tools.py` — `generate_financial_health_score`, `get_recommendations`, `estimate_home_affordability`

Each tool file contains **only**: argument unpacking, a single service call,
and returning the service's return value. No arithmetic.

`POST /agent/chat` in `api/v1/routes/agent.py` is the only FastAPI-aware
piece of this stack — it wires a request to `AgentOrchestrator`, which is
otherwise framework-free and could be dropped behind an MCP server later
with no change to `tool_registry.py` or the tool wrapper functions.

---

## 11. Frontend/backend mismatches to resolve

1. **No auth in the UI at all.** Settings shows a single hardcoded profile.
   Backend needs auth from day one; frontend will need a login screen and
   token storage before anything else can go live.
2. **Static "N minutes ago" / "N accounts" copy** is hand-written per page.
   Once real, these need to come from `institutions.last_synced_at` and
   live counts — minor frontend changes, but every page has at least one.
3. **`ProjectionAssumptions` computes its own future value client-side**
   with a hardcoded salary (`190000`) and current net worth (`1284920`).
   This needs to move to `POST /simulations/net-worth` (debounced) once
   wired up — currently a real math bug waiting to happen (frontend and
   backend would silently disagree).
4. **Scenario "success rate" is a flat stored number.** The frontend has no
   loading state for a Monte Carlo run, which can take longer than a normal
   request — needs either a synchronous fast-path (small sample count) or a
   job + polling/websocket pattern.
5. **No pagination, no error states, no empty states** anywhere — fine for
   mock data, not fine once `/transactions` and `/accounts` are real and can
   be empty, slow, or partial (e.g. one Plaid item down).
6. **`Insight`/`Recommendation` are separate types with overlapping intent**
   (`insights.kind === "opportunity"` vs. `recommendations.category`). Keep
   them separate on the backend (different tables, different lifecycles —
   recommendations are actionable, insights are observational) but this is
   worth confirming with product before the FE builds a unified feed.
7. **Institution "status" in Settings ("Healthy"/"Action required") vs.
   Account "status" ("connected"/"attention"/"manual")** are two different
   enums describing similar things — backend models them as two separate
   concepts (`institutions.status` vs. `accounts.status`) since an
   institution can be healthy while one of its accounts needs attention.

---

## 12. Phased roadmap

**Phase 0 — Scaffolding (this repo).** Project layout, config, DB session,
JWT auth skeleton, Docker Compose (API + Postgres), Alembic wired to the
initial schema, CI-ready test setup.

**Phase 1 — Simulation core (done in this pass).** `simulation/engine.py`
with real, unit-tested math: compounding, amortization, inflation, federal
tax estimate, contribution limits, employer match. `RetirementProjectionService`,
`NetWorthProjectionService`, `CashFlowProjectionService`,
`TaxCalculationService`, `DebtOptimizationService` implemented and tested
against known values, independent of any DB.

**Phase 2 — Persistence + core CRUD.** SQLAlchemy models, repositories,
Alembic migration, `/accounts`, `/transactions`, `/goals`, `/scenarios`
CRUD endpoints. Manual + CSV providers (no external dependency).

**Phase 3 — Projections API.** `/simulations/*`, `/scenarios/{id}/run` +
`simulation_runs`, scenario comparison endpoint — this is what unblocks the
Projections page for real.

**Phase 4 — Recommendations & health score.** `RecommendationEngine`,
`FinancialHealthService`, `/recommendations`, `/insights`,
`/financial-health` — unblocks the Insights page.

**Phase 5 — AI layer.** `ToolRegistry`, tool wrappers over the Phase 1–4
services, `AgentOrchestrator`, `/agent/chat`. Add a chat surface to the
frontend.

**Phase 6 — Plaid integration.** `PlaidProvider`, webhook handling, account
linking flow, scheduled sync job.

**Phase 7 — Monte Carlo & optimization.** Swap in a real sampler in
`simulation/monte_carlo.py`, `PortfolioAllocationService` optimization,
`optimize_monthly_surplus` tool — the engine was designed in Phase 1 so this
requires no refactor of existing services.

This repository implements **Phase 0 and Phase 1** fully (runnable, tested),
scaffolds Phases 2–5 with real interfaces and TODOs so the shape is locked
in, and leaves Phases 6–7 as design-only per the roadmap above.
