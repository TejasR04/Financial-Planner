from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.domain.entities import User
from app.persistence.repositories.account_repository import AccountRepository
from app.persistence.repositories.scenario_repository import ScenarioRepository
from app.persistence.repositories.user_repository import UserRepository
from app.schemas.scenario import (
    ScenarioCompareRequest,
    ScenarioCompareResponse,
    ScenarioCompareRow,
    ScenarioCreateRequest,
    ScenarioResponse,
    ScenarioRunHistoryResponse,
    ScenarioRunRequest,
    ScenarioRunResponse,
    ScenarioPreviewResponse,
    ScenarioSensitivityRequest,
    ScenarioSensitivityResponse,
    ScenarioUpdateRequest,
    SensitivityRowResponse,
)
from app.services.scenario_service import ScenarioService
from app.simulation.assumptions import PlanningAssumptions

router = APIRouter(prefix="/scenarios", tags=["scenarios"])

scenario_service = ScenarioService()


def _retirement_trajectory(result, assumptions: PlanningAssumptions) -> list[dict]:
    return [
        {
            "year": p.year_index,
            "age": p.age,
            "balance": str(p.ending_balance),
            "withdrawal": "0",
        }
        for p in result.retirement_projection.accumulation_series
    ] + [
        {
            "year": assumptions.years_to_retirement + p.year_index,
            "age": p.age,
            "balance": str(p.ending_balance),
            "withdrawal": str(-p.contributions),
        }
        for p in result.retirement_projection.decumulation_series
    ]


async def _compute_scenario(
    scenario, body: ScenarioRunRequest, current_user: User, db: AsyncSession
):
    accounts = await AccountRepository(db).list_for_user(current_user.id)
    planning_profile = await UserRepository(db).get_planning_profile(current_user.id)
    assumptions = PlanningAssumptions(
        current_age=body.current_age,
        retirement_age=scenario.retirement_age,
        savings_rate=scenario.savings_rate,
        monthly_contribution=scenario.monthly_contribution,
        expected_return=scenario.expected_return,
        inflation_rate=scenario.inflation_rate,
        withdrawal_rate=scenario.withdrawal_rate,
        desired_monthly_income_today=scenario.desired_monthly_income_today,
        target_equity_allocation=planning_profile.target_equity_allocation,
    )
    result = scenario_service.run(
        accounts=accounts,
        assumptions=assumptions,
        current_retirement_balance=body.current_retirement_balance,
        annual_contribution=scenario.monthly_contribution * 12,
        annual_spending_target=body.annual_spending_target,
        include_monte_carlo=body.include_monte_carlo,
        monte_carlo_trials=body.monte_carlo_trials,
    )
    return result, assumptions


@router.get("", response_model=list[ScenarioResponse])
async def list_scenarios(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[ScenarioResponse]:
    rows = await ScenarioRepository(db).list_for_user(current_user.id)
    return [ScenarioResponse.model_validate(r, from_attributes=True) for r in rows]


@router.post("", response_model=ScenarioResponse, status_code=status.HTTP_201_CREATED)
async def create_scenario(
    body: ScenarioCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ScenarioResponse:
    assumptions = PlanningAssumptions(
        current_age=body.current_age,
        retirement_age=body.retirement_age,
        savings_rate=body.savings_rate,
        monthly_contribution=body.monthly_contribution,
        expected_return=body.expected_return,
        inflation_rate=body.inflation_rate,
        withdrawal_rate=body.withdrawal_rate,
        desired_monthly_income_today=body.desired_monthly_income_today,
    )
    row = await ScenarioRepository(db).create(
        current_user.id, body.name, body.description, assumptions, is_baseline=body.is_baseline
    )
    await db.commit()
    return ScenarioResponse.model_validate(row, from_attributes=True)


@router.get("/{scenario_id}", response_model=ScenarioResponse)
async def get_scenario(
    scenario_id: UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> ScenarioResponse:
    row = await ScenarioRepository(db).get_for_user(current_user.id, scenario_id)
    return ScenarioResponse.model_validate(row, from_attributes=True)


@router.patch("/{scenario_id}", response_model=ScenarioResponse)
async def update_scenario(
    scenario_id: UUID,
    body: ScenarioUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ScenarioResponse:
    repo = ScenarioRepository(db)
    fields = body.model_dump(exclude_unset=True, exclude={"clear_income_target"})
    row = await repo.update_for_user(current_user.id, scenario_id, **fields)
    if body.clear_income_target:
        row.desired_monthly_income_today = None
        await db.flush()
    await db.commit()
    return ScenarioResponse.model_validate(row, from_attributes=True)


@router.delete("/{scenario_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scenario(
    scenario_id: UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> None:
    await ScenarioRepository(db).delete_for_user(current_user.id, scenario_id)
    await db.commit()


@router.post("/{scenario_id}/duplicate", response_model=ScenarioResponse, status_code=status.HTTP_201_CREATED)
async def duplicate_scenario(
    scenario_id: UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> ScenarioResponse:
    repo = ScenarioRepository(db)
    original = await repo.get_for_user(current_user.id, scenario_id)
    assumptions = PlanningAssumptions(
        current_age=original.retirement_age - 1 if original.retirement_age > 1 else 1,
        retirement_age=original.retirement_age,
        savings_rate=original.savings_rate,
        monthly_contribution=original.monthly_contribution,
        expected_return=original.expected_return,
        inflation_rate=original.inflation_rate,
        withdrawal_rate=original.withdrawal_rate,
        desired_monthly_income_today=original.desired_monthly_income_today,
    )
    # NOTE: current_age isn't stored on Scenario itself (it's a property of
    # the user/point-in-time run), so duplication preserves every stored
    # assumption and the caller supplies current_age again on /run.
    copy = await repo.create(
        current_user.id, f"{original.name} (copy)", original.description, assumptions, is_baseline=False
    )
    await db.commit()
    return ScenarioResponse.model_validate(copy, from_attributes=True)


@router.post("/{scenario_id}/run", response_model=ScenarioRunResponse, status_code=status.HTTP_201_CREATED)
async def run_scenario(
    scenario_id: UUID,
    body: ScenarioRunRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ScenarioRunResponse:
    """Runs the scenario's stored assumptions against the user's current
    account book, persists the result as a SimulationRun, and returns it.
    This is the single computation path also used by `compare_scenarios`
    (via /scenarios/compare, which reads the latest persisted run) and by
    the `run_monte_carlo`/forecast AI tools' underlying services — the only
    thing unique to this route is that it *persists* a run.
    """
    scenario_repo = ScenarioRepository(db)
    scenario = await scenario_repo.get_for_user(current_user.id, scenario_id)
    result, assumptions = await _compute_scenario(scenario, body, current_user, db)

    trajectory = [
        {
            "year": p.year_index, "age": p.age,
            "assets": str(p.assets), "liabilities": str(p.liabilities), "net": str(p.net),
        }
        for p in result.net_worth_projection.series
    ]
    retirement_trajectory = _retirement_trajectory(result, assumptions)
    assumptions_snapshot = {
        "current_age": assumptions.current_age,
        "retirement_age": assumptions.retirement_age,
        "expected_return": str(assumptions.expected_return),
        "inflation_rate": str(assumptions.inflation_rate),
        "withdrawal_rate": str(assumptions.withdrawal_rate),
    }

    run_row = await scenario_repo.record_run_for_user(
        user_id=current_user.id,
        scenario_id=scenario_id,
        engine_version=result.engine_version,
        net_worth_at_target_age=result.retirement_projection.projected_balance_at_retirement,
        monthly_sustainable_withdrawal=result.retirement_projection.monthly_sustainable_withdrawal,
        trajectory=trajectory,
        retirement_trajectory=retirement_trajectory,
        assumptions_snapshot=assumptions_snapshot,
        method="monte_carlo" if result.monte_carlo else "deterministic",
        success_rate=(round(result.monte_carlo.success_rate, 4) if result.monte_carlo else None),
        seed=result.monte_carlo.seed if result.monte_carlo else None,
    )
    await db.commit()
    return ScenarioRunResponse.model_validate(run_row, from_attributes=True)


@router.post("/{scenario_id}/preview", response_model=ScenarioPreviewResponse)
async def preview_scenario(
    scenario_id: UUID,
    body: ScenarioRunRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ScenarioPreviewResponse:
    """Return a fresh scenario calculation without creating a run record."""
    scenario = await ScenarioRepository(db).get_for_user(current_user.id, scenario_id)
    result, assumptions = await _compute_scenario(scenario, body, current_user, db)
    trajectory = [
        {
            "year": p.year_index,
            "age": p.age,
            "assets": str(p.assets),
            "liabilities": str(p.liabilities),
            "net": str(p.net),
        }
        for p in result.net_worth_projection.series
    ]
    return ScenarioPreviewResponse(
        net_worth_at_target_age=result.retirement_projection.projected_balance_at_retirement,
        monthly_sustainable_withdrawal=result.retirement_projection.monthly_sustainable_withdrawal,
        success_rate=(round(result.monte_carlo.success_rate, 4) if result.monte_carlo else None),
        trajectory=trajectory,
        retirement_trajectory=_retirement_trajectory(result, assumptions),
    )


@router.get("/{scenario_id}/runs", response_model=ScenarioRunHistoryResponse)
async def list_scenario_runs(
    scenario_id: UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> ScenarioRunHistoryResponse:
    rows = await ScenarioRepository(db).list_runs_for_user(current_user.id, scenario_id)
    return ScenarioRunHistoryResponse(
        data=[ScenarioRunResponse.model_validate(r, from_attributes=True) for r in rows]
    )


@router.post("/{scenario_id}/sensitivity", response_model=ScenarioSensitivityResponse)
async def scenario_sensitivity(
    scenario_id: UUID,
    body: ScenarioSensitivityRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ScenarioSensitivityResponse:
    """Genuinely re-runs the projection engine with one assumption nudged
    per row (see `ScenarioService.analyze_sensitivity`) — nothing here is
    a canned/hardcoded number.
    """
    scenario = await ScenarioRepository(db).get_for_user(current_user.id, scenario_id)
    planning_profile = await UserRepository(db).get_planning_profile(current_user.id)
    assumptions = PlanningAssumptions(
        current_age=body.current_age,
        retirement_age=scenario.retirement_age,
        savings_rate=scenario.savings_rate,
        monthly_contribution=scenario.monthly_contribution,
        expected_return=scenario.expected_return,
        inflation_rate=scenario.inflation_rate,
        withdrawal_rate=scenario.withdrawal_rate,
        desired_monthly_income_today=scenario.desired_monthly_income_today,
        target_equity_allocation=planning_profile.target_equity_allocation,
    )
    result = scenario_service.analyze_sensitivity(
        assumptions=assumptions,
        current_retirement_balance=body.current_retirement_balance,
    )
    return ScenarioSensitivityResponse(
        baseline_balance_at_retirement=result.baseline_balance_at_retirement,
        baseline_success_rate=result.baseline_success_rate,
        rows=[
            SensitivityRowResponse(label=r.label, kind=r.kind, value=r.value, note=r.note)
            for r in result.rows
        ],
    )


@router.post("/compare", response_model=ScenarioCompareResponse)
async def compare_scenarios(
    body: ScenarioCompareRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ScenarioCompareResponse:
    """Compares scenarios by their most recently persisted run. Scenarios
    with no run yet still appear in the table (has_run=False) so the
    frontend can prompt the user to run them rather than silently omitting
    a row — mirrors the always-visible three-card layout on the current
    Projections page.
    """
    repo = ScenarioRepository(db)
    rows: list[ScenarioCompareRow] = []
    for scenario_id in body.scenario_ids:
        scenario = await repo.get_for_user(current_user.id, scenario_id)
        runs = await repo.list_runs_for_user(current_user.id, scenario_id)
        latest = runs[0] if runs else None
        rows.append(
            ScenarioCompareRow(
                scenario_id=scenario.id,
                name=scenario.name,
                net_worth_at_target_age=latest.net_worth_at_target_age if latest else None,
                retirement_age=scenario.retirement_age,
                monthly_contribution=scenario.monthly_contribution,
                success_rate=latest.success_rate if latest else None,
                has_run=latest is not None,
            )
        )
    return ScenarioCompareResponse(rows=rows)
