from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import select

from app.persistence.models import ScenarioModel, SimulationRunModel
from app.persistence.repositories.base import BaseRepository
from app.simulation.assumptions import PlanningAssumptions


class ScenarioRepository(BaseRepository[ScenarioModel]):
    model = ScenarioModel

    async def list_for_user(self, user_id: UUID) -> list[ScenarioModel]:
        result = await self.session.execute(
            select(ScenarioModel).where(ScenarioModel.user_id == user_id).order_by(ScenarioModel.created_at)
        )
        return list(result.scalars().all())

    async def get(self, scenario_id: UUID) -> ScenarioModel:
        return await self._get_or_raise("Scenario", scenario_id)

    async def create(self, user_id: UUID, name: str, description: str | None, assumptions: PlanningAssumptions,
                      is_baseline: bool = False) -> ScenarioModel:
        row = ScenarioModel(
            id=uuid4(),
            user_id=user_id,
            name=name,
            description=description,
            is_baseline=is_baseline,
            retirement_age=assumptions.retirement_age,
            savings_rate=assumptions.savings_rate,
            monthly_contribution=assumptions.monthly_contribution,
            expected_return=assumptions.expected_return,
            inflation_rate=assumptions.inflation_rate,
            withdrawal_rate=assumptions.withdrawal_rate,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def delete(self, scenario_id: UUID) -> None:
        row = await self._get_or_raise("Scenario", scenario_id)
        await self.session.delete(row)
        await self.session.flush()

    async def record_run(
        self, scenario_id: UUID, engine_version: str, net_worth_at_target_age, trajectory: dict,
        assumptions_snapshot: dict, method: str = "deterministic", success_rate=None, seed: int | None = None,
        monthly_sustainable_withdrawal=None,
    ) -> SimulationRunModel:
        row = SimulationRunModel(
            id=uuid4(),
            scenario_id=scenario_id,
            engine_version=engine_version,
            method=method,
            net_worth_at_target_age=net_worth_at_target_age,
            monthly_sustainable_withdrawal=monthly_sustainable_withdrawal,
            success_rate=success_rate,
            trajectory=trajectory,
            assumptions_snapshot=assumptions_snapshot,
            seed=seed,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def list_runs(self, scenario_id: UUID) -> list[SimulationRunModel]:
        result = await self.session.execute(
            select(SimulationRunModel)
            .where(SimulationRunModel.scenario_id == scenario_id)
            .order_by(SimulationRunModel.created_at.desc())
        )
        return list(result.scalars().all())