from uuid import uuid4

from app.core.security import create_password_reset_token, decode_token


def test_password_reset_token_is_type_scoped():
    user_id = uuid4()
    payload = decode_token(create_password_reset_token(user_id))

    assert payload["sub"] == str(user_id)
    assert payload["type"] == "password_reset"
