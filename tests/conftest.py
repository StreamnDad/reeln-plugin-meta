"""Shared test fixtures for reeln-plugin-meta."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest


@dataclass
class FakeGameInfo:
    """Minimal stand-in for ``reeln.models.game.GameInfo``."""

    date: str = "2026-01-15"
    home_team: str = "Eagles"
    away_team: str = "Hawks"
    sport: str = "hockey"
    game_number: int = 1
    venue: str = ""
    game_time: str = ""
    description: str = ""
    thumbnail: str = ""


@pytest.fixture()
def game_info() -> FakeGameInfo:
    return FakeGameInfo()


@pytest.fixture()
def token_file(tmp_path: Path) -> Path:
    """Return a temporary token file with a valid token."""
    token = tmp_path / "page_token.txt"
    token.write_text("test-access-token-123")
    return token


@pytest.fixture()
def plugin_config(token_file: Path) -> dict[str, Any]:
    """Return a minimal valid plugin config."""
    return {
        "page_access_token_file": str(token_file),
        "page_id": "123456789",
        "create_livestream": True,
    }
