import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_database_pool_defaults_are_bounded() -> None:
    settings = Settings(_env_file=None)

    assert settings.database_pool_size == 5
    assert settings.database_max_overflow == 5
    assert settings.database_pool_recycle_seconds == 300


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("database_pool_size", 0),
        ("database_max_overflow", -1),
        ("database_pool_recycle_seconds", -1),
    ],
)
def test_invalid_database_pool_settings_are_rejected(field: str, value: int) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{field: value})
