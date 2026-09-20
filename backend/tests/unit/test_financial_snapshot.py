from datetime import date
from decimal import Decimal
from uuid import uuid4

from app.domain.entities import Account, FinancialSnapshot, Holding, PlanningProfile, User
from app.domain.enums import AccountType, AssetClass


def test_liquid_assets_include_taxable_brokerage_cash_but_not_retirement_cash():
    user = User(id=uuid4(), email="person@example.com", full_name="Person")
    taxable = Account(
        id=uuid4(), user_id=user.id, name="Brokerage", type=AccountType.INVESTMENT,
        balance=Decimal("25000"),
    )
    retirement = Account(
        id=uuid4(), user_id=user.id, name="IRA", type=AccountType.RETIREMENT,
        balance=Decimal("50000"),
    )
    checking = Account(
        id=uuid4(), user_id=user.id, name="Checking", type=AccountType.DEPOSITORY,
        balance=Decimal("2000"),
    )
    holdings = [
        Holding(uuid4(), taxable.id, "CASH", Decimal("1"), Decimal("10000"),
                Decimal("10000"), AssetClass.CASH, date.today()),
        Holding(uuid4(), retirement.id, "CASH", Decimal("1"), Decimal("7000"),
                Decimal("7000"), AssetClass.CASH, date.today()),
    ]
    snapshot = FinancialSnapshot(
        user=user, profile=PlanningProfile(user.id),
        accounts=[taxable, retirement, checking], holdings=holdings,
    )

    assert snapshot.liquid_assets == Decimal("12000")
