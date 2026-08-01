from uuid import uuid4

from app.core.security import create_password_reset_token, decode_token


def test_password_reset_token_is_type_scoped():
    user_id = uuid4()
    payload = decode_token(create_password_reset_token(user_id))

    assert payload["sub"] == str(user_id)
    assert payload["type"] == "password_reset"
    assert payload["jti"]


def test_password_reset_tokens_are_unique_even_when_created_together():
    user_id = uuid4()

    first = create_password_reset_token(user_id)
    second = create_password_reset_token(user_id)

    assert first != second
    assert decode_token(first)["jti"] != decode_token(second)["jti"]
