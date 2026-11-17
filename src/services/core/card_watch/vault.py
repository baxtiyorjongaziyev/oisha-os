"""Encrypt/decrypt manager session strings (Fernet, key in ``CARD_WATCH_SESSION_KEY``).

Stored form in the secrets env file: ``CARD_WATCH_SESSION_<KEY>=enc:<fernet token>``.
The Fernet token is bound to the manager key via a ``<key>:`` prefix inside the
plaintext, so a session copied into another manager's slot is rejected.
"""
from __future__ import annotations

import os
from typing import Optional

PREFIX = "enc:"
KEY_ENV = "CARD_WATCH_SESSION_KEY"


class SessionVaultError(RuntimeError):
    pass


def _fernet(key: Optional[str] = None):
    from cryptography.fernet import Fernet

    raw = (key or os.getenv(KEY_ENV, "")).strip()
    if not raw:
        raise SessionVaultError(f"{KEY_ENV} is not set")
    return Fernet(raw.encode())


def new_key() -> str:
    from cryptography.fernet import Fernet

    return Fernet.generate_key().decode()


def encrypt(manager_key: str, session: str, key: Optional[str] = None) -> str:
    token = _fernet(key).encrypt(f"{manager_key}:{session}".encode())
    return PREFIX + token.decode()


def decrypt(manager_key: str, stored: str, key: Optional[str] = None) -> str:
    """Return the plain session for ``manager_key``; raise on tamper/mismatch."""
    if not stored.startswith(PREFIX):
        raise SessionVaultError("session is not encrypted (expected enc: prefix)")
    from cryptography.fernet import InvalidToken

    try:
        plain = _fernet(key).decrypt(stored[len(PREFIX):].encode()).decode()
    except InvalidToken as exc:
        raise SessionVaultError("cannot decrypt session (wrong key or tampered)") from exc
    owner, _, session = plain.partition(":")
    if owner != manager_key or not session:
        raise SessionVaultError("session belongs to another manager")
    return session
