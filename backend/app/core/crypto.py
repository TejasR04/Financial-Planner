"""Symmetric encryption for secrets that must be stored at rest, namely
Plaid `access_token`s. Nothing outside this module should touch the
Fernet key or do the encrypt/decrypt itself — repositories and providers
call `encrypt_secret`/`decrypt_secret` and never see raw key material.

Plaid access tokens are long-lived bearer credentials that grant read
access to a user's real linked bank data — they're treated the same as
passwords: never logged, never returned in any API response, never
stored in plaintext.
"""
from __future__ import annotations

from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings


class DecryptionError(Exception):
    """Raised when a stored secret can't be decrypted (wrong/rotated key,
    or corrupted data). Callers should treat this as the credential being
    unusable, not retry with the raw bytes."""


@lru_cache
def _fernet() -> Fernet:
    settings = get_settings()
    key = settings.plaid_token_encryption_key
    if not key:
        raise RuntimeError("PLAID_TOKEN_ENCRYPTION_KEY is not configured")
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_secret(plaintext: str) -> str:
    """Encrypt a secret for storage. Returns a str safe to put in a Text column."""
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_secret(ciphertext: str) -> str:
    """Decrypt a secret previously produced by `encrypt_secret`."""
    try:
        return _fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise DecryptionError("Stored secret could not be decrypted") from exc
