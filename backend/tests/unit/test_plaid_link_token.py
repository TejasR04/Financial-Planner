"""Link request contracts for bank onboarding and reauthentication."""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from app.providers.plaid_client import PlaidClient
from app.providers.plaid_provider import PlaidProvider


@pytest.mark.asyncio
@pytest.mark.parametrize("access_token", [None, "existing-item-token"])
async def test_link_products_do_not_block_card_only_institutions(access_token):
    client = object.__new__(PlaidClient)
    expiration = datetime.now(timezone.utc)
    create = Mock(return_value=SimpleNamespace(link_token="link-token", expiration=expiration))
    client._client = SimpleNamespace(link_token_create=create)

    result = await client.create_link_token(uuid4(), update_access_token=access_token)

    request = create.call_args.args[0].to_dict()
    assert result.link_token == "link-token"
    if access_token is None:
        assert request["products"] == ["transactions"]
        assert request["optional_products"] == ["investments"]
        assert "access_token" not in request
    else:
        assert request["access_token"] == access_token
        for field in ("products", "optional_products", "additional_consented_products", "transactions"):
            assert field not in request


@pytest.mark.asyncio
async def test_reconnect_uses_the_owned_existing_item_without_exchanging_a_token():
    provider = object.__new__(PlaidProvider)
    user_id, institution_id = uuid4(), uuid4()
    provider._institutions = SimpleNamespace(
        get_decrypted_access_token_for_user=AsyncMock(return_value="existing-item-token"),
    )
    provider._client = SimpleNamespace(
        create_link_token=AsyncMock(return_value=SimpleNamespace(
            link_token="link-token", expiration=datetime.now(timezone.utc),
        )),
        exchange_public_token=AsyncMock(),
    )

    await provider.create_link_token(user_id, institution_id)

    provider._institutions.get_decrypted_access_token_for_user.assert_awaited_once_with(institution_id, user_id)
    provider._client.create_link_token.assert_awaited_once_with(user_id, update_access_token="existing-item-token")
    provider._client.exchange_public_token.assert_not_awaited()
