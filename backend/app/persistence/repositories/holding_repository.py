from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import delete, select

from app.domain.entities import Holding
from app.domain.enums import AssetClass
from app.persistence.models import AccountModel, HoldingModel
from app.persistence.repositories.base import BaseRepository


class HoldingRepository(BaseRepository[HoldingModel]):
    model = HoldingModel

    async def list_for_account(self, account_id: UUID) -> list[Holding]:
        result = await self.session.execute(select(HoldingModel).where(HoldingModel.account_id == account_id))
        return [_to_domain(row) for row in result.scalars().all()]

    async def list_for_user(self, user_id: UUID) -> list[Holding]:
        result = await self.session.execute(
            select(HoldingModel)
            .join(AccountModel, AccountModel.id == HoldingModel.account_id)
            .where(AccountModel.user_id == user_id)
        )
        return [_to_domain(row) for row in result.scalars().all()]

    async def create(self, holding: Holding) -> Holding:
        row = HoldingModel(
            id=holding.id or uuid4(),
            account_id=holding.account_id,
            symbol=holding.symbol,
            quantity=holding.quantity,
            cost_basis=holding.cost_basis,
            market_value=holding.market_value,
            asset_class=holding.asset_class.value,
            as_of=holding.as_of,
        )
        self.session.add(row)
        await self.session.flush()
        return _to_domain(row)

    async def replace_for_accounts(self, account_ids: list[UUID], holdings: list[Holding]) -> list[Holding]:
        """Replace holdings only for accounts confirmed by a successful
        holdings response. An empty response is therefore meaningful and
        clears stale positions, while a failed API call leaves prior data in
        place.
        """
        if not account_ids:
            return []
        await self.session.execute(delete(HoldingModel).where(HoldingModel.account_id.in_(account_ids)))
        rows = [
            HoldingModel(
                id=holding.id or uuid4(),
                account_id=holding.account_id,
                symbol=holding.symbol,
                quantity=holding.quantity,
                cost_basis=holding.cost_basis,
                market_value=holding.market_value,
                asset_class=holding.asset_class.value,
                as_of=holding.as_of,
            )
            for holding in holdings
        ]
        self.session.add_all(rows)
        await self.session.flush()
        return [_to_domain(row) for row in rows]


def _to_domain(row: HoldingModel) -> Holding:
    return Holding(
        id=row.id,
        account_id=row.account_id,
        symbol=row.symbol,
        quantity=row.quantity,
        cost_basis=row.cost_basis,
        market_value=row.market_value,
        asset_class=AssetClass(row.asset_class),
        as_of=row.as_of,
    )
