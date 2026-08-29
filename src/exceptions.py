# src/exceptions.py

"""Custom exception classes for Oisha-OS.

This module centralizes error types that are raised when required
credentials or configuration values are missing or invalid.
"""

class MissingCredentialError(Exception):
    """Raised when a required credential (e.g., API key, token, secret) is
    not provided via environment variables or the .env file.

    Parameters
    ----------
    name: str
        The name of the missing credential (environment variable).
    """

    def __init__(self, name: str):
        self.name = name
        super().__init__(f"Missing required credential: {name}")

    def __repr__(self) -> str:
        return f"MissingCredentialError(name={self.name!r})"
