from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class NetWorthHistoryPointResponse(BaseModel):
    date: date
    assets: Decimal
    liabilities: Decimal
    net: Decimal
