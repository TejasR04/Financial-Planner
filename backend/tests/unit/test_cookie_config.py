import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_cross_site_refresh_cookie_requires_https() -> None:
    with pytest.raises(ValidationError, match="REFRESH_COOKIE_SECURE"):
        Settings(
            _env_file=None,
            refresh_cookie_samesite="none",
            refresh_cookie_secure=False,
        )


def test_secure_cross_site_refresh_cookie_is_supported() -> None:
    settings = Settings(
        _env_file=None,
        refresh_cookie_samesite="none",
        refresh_cookie_secure=True,
    )

    assert settings.refresh_cookie_samesite == "none"
