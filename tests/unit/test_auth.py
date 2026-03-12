"""Tests for auth module."""

from __future__ import annotations

from pathlib import Path

import pytest

from reeln_meta_plugin.auth import AuthError, default_token_path, read_token


class TestDefaultTokenPath:
    def test_returns_path(self) -> None:
        result = default_token_path()
        assert isinstance(result, Path)
        assert result.name == "page_token.txt"
        assert "meta" in str(result)


class TestReadToken:
    def test_valid_token(self, token_file: Path) -> None:
        result = read_token(token_file)
        assert result == "test-access-token-123"

    def test_strips_whitespace(self, tmp_path: Path) -> None:
        token = tmp_path / "token.txt"
        token.write_text("  my-token  \n")
        result = read_token(token)
        assert result == "my-token"

    def test_missing_file(self, tmp_path: Path) -> None:
        missing = tmp_path / "nonexistent.txt"
        with pytest.raises(AuthError, match="Token file not found"):
            read_token(missing)

    def test_empty_file(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty.txt"
        empty.write_text("")
        with pytest.raises(AuthError, match="Token file is empty"):
            read_token(empty)

    def test_whitespace_only_file(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws.txt"
        ws.write_text("   \n  ")
        with pytest.raises(AuthError, match="Token file is empty"):
            read_token(ws)
