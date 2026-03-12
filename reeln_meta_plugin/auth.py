"""Token-based authentication for Meta APIs."""

from __future__ import annotations

from pathlib import Path

from reeln.core.config import data_dir


class AuthError(Exception):
    """Raised when authentication fails."""


def default_token_path() -> Path:
    """Return the default Page Access Token file path."""
    return Path(data_dir() / "meta" / "page_token.txt")


def read_token(path: Path) -> str:
    """Read and validate a token from a file.

    Args:
        path: Path to the token file.

    Returns:
        The token string (stripped of whitespace).

    Raises:
        AuthError: If the file is missing or empty.
    """
    if not path.exists():
        raise AuthError(f"Token file not found: {path}")

    token = path.read_text().strip()
    if not token:
        raise AuthError(f"Token file is empty: {path}")

    return token
