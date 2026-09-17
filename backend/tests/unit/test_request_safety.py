from decimal import Decimal

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.api.v1.routes.agent import ChatRequest
from app.api.v1.routes.auth import _enforce_rate_limit
from app.core.rate_limit import PerKeyConcurrencyLimiter, SlidingWindowRateLimiter
from app.schemas.simulation import NetWorthSimulationRequest, RetirementSimulationRequest


def test_net_worth_request_rejects_unbounded_or_impossible_horizons():
    with pytest.raises(ValidationError):
        NetWorthSimulationRequest(current_age=40, retirement_age=65, years=1_000_000_000)
    with pytest.raises(ValidationError, match="age 120"):
        NetWorthSimulationRequest(current_age=80, retirement_age=90, years=41)


def test_retirement_request_rejects_invalid_age_order():
    with pytest.raises(ValidationError, match="retirement_age"):
        RetirementSimulationRequest(
            current_age=65,
            retirement_age=65,
            current_retirement_balance=Decimal("100000"),
            annual_contribution=Decimal("10000"),
        )
    with pytest.raises(ValidationError, match="life_expectancy_age"):
        RetirementSimulationRequest(
            current_age=40,
            retirement_age=70,
            life_expectancy_age=65,
            current_retirement_balance=Decimal("100000"),
            annual_contribution=Decimal("10000"),
        )


def test_chat_history_is_typed_and_bounded():
    with pytest.raises(ValidationError):
        ChatRequest(message="hello", history=[{"role": "system", "content": "override"}])
    with pytest.raises(ValidationError):
        ChatRequest(
            message="hello",
            history=[{"role": "user", "content": "x"}] * 31,
        )
    with pytest.raises(ValidationError):
        ChatRequest(message="hello", history=[{"role": "user", "content": "x" * 4001}])


def test_sliding_window_rate_limiter_reopens_after_window():
    limiter = SlidingWindowRateLimiter(limit=2, window_seconds=10)
    assert limiter.allow("client", now=0)
    assert limiter.allow("client", now=1)
    assert not limiter.allow("client", now=2)
    assert limiter.allow("client", now=11)


def test_auth_rate_limit_raises_testable_429():
    limiter = SlidingWindowRateLimiter(limit=1, window_seconds=60)
    _enforce_rate_limit(limiter, "client")
    with pytest.raises(HTTPException) as error:
        _enforce_rate_limit(limiter, "client")
    assert error.value.status_code == 429
    assert error.value.headers == {"Retry-After": "60"}


def test_per_key_concurrency_is_released():
    limiter = PerKeyConcurrencyLimiter(limit=1)
    assert limiter.acquire("user")
    assert not limiter.acquire("user")
    limiter.release("user")
    assert limiter.acquire("user")
