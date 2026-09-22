from __future__ import annotations

from uuid import UUID, uuid4

from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import delete, select

from app.core.exceptions import NotFoundError, ValidationError
from app.domain.entities import Holding
from app.domain.enums import AssetClass
from app.domain.holding_valuation import holding_asset_class
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
            .where(
                AccountModel.user_id == user_id,
                AccountModel.archived_at.is_(None),
            )
        )
        return [_to_domain(row) for row in result.scalars().all()]

    async def list_automatic_for_user(self, user_id: UUID) -> list[Holding]:
        result = await self.session.execute(
            select(HoldingModel)
            .join(AccountModel, AccountModel.id == HoldingModel.account_id)
            .where(
                AccountModel.user_id == user_id,
                AccountModel.archived_at.is_(None),
                AccountModel.institution_id.is_(None),
                HoldingModel.pricing_mode == "automatic",
            )
        )
        return [_to_domain(row) for row in result.scalars().all()]

    async def apply_market_price_for_user(
        self, user_id: UUID, holding_id: UUID, price: Decimal, as_of: date
    ) -> Holding:
        row = await self.session.scalar(
            select(HoldingModel)
            .join(AccountModel, AccountModel.id == HoldingModel.account_id)
            .where(
                HoldingModel.id == holding_id,
                AccountModel.user_id == user_id,
                AccountModel.archived_at.is_(None),
                AccountModel.institution_id.is_(None),
                HoldingModel.pricing_mode == "automatic",
            )
        )
        if row is None:
            raise NotFoundError("Automatically priced holding", str(holding_id))
        row.last_price = price
        row.market_value = (price * row.quantity).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        row.as_of = as_of
        await self.session.flush()
        return _to_domain(row)

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
            pricing_mode=holding.pricing_mode,
            last_price=holding.last_price,
        )
        self.session.add(row)
        await self.session.flush()
        return _to_domain(row)

    async def update_for_user(self, user_id: UUID, holding_id: UUID, **fields) -> Holding:
        row = await self.session.scalar(select(HoldingModel).join(AccountModel).where(HoldingModel.id == holding_id, AccountModel.user_id == user_id, AccountModel.archived_at.is_(None)))
        if row is None:
            raise NotFoundError("Holding", str(holding_id))
        account = await self.session.get(AccountModel, row.account_id)
        if account is not None and account.institution_id is not None:
            raise ValidationError("Linked holdings are managed by the institution.")
        for key, value in fields.items():
            setattr(row, key, value)
        await self.session.flush()
        return _to_domain(row)

    async def delete_for_user(self, user_id: UUID, holding_id: UUID) -> None:
        row = await self.session.scalar(select(HoldingModel).join(AccountModel).where(HoldingModel.id == holding_id, AccountModel.user_id == user_id, AccountModel.archived_at.is_(None)))
        if row is None:
            raise NotFoundError("Holding", str(holding_id))
        account = await self.session.get(AccountModel, row.account_id)
        if account is not None and account.institution_id is not None:
            raise ValidationError("Linked holdings are managed by the institution.")
        await self.session.delete(row)
        await self.session.flush()

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
                pricing_mode=holding.pricing_mode,
                last_price=holding.last_price,
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
        asset_class=holding_asset_class(row.symbol, AssetClass(row.asset_class)),
        as_of=row.as_of,
        pricing_mode=getattr(row, "pricing_mode", "manual"),
        last_price=getattr(row, "last_price", None),
    )
