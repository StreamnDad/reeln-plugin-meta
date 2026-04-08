"""Tests for auth_check() and auth_refresh() methods."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

from reeln.models.auth import AuthStatus

from reeln_meta_plugin.auth import AuthError
from reeln_meta_plugin.graph_api import GraphAPIError
from reeln_meta_plugin.plugin import MetaPlugin


class TestAuthCheck:
    """Tests for MetaPlugin.auth_check()."""

    def test_token_file_not_configured(self) -> None:
        """page_access_token_file missing returns NOT_CONFIGURED."""
        plugin = MetaPlugin(config={})
        results = plugin.auth_check()

        assert len(results) == 1
        assert results[0].service == "Facebook Page"
        assert results[0].status == AuthStatus.NOT_CONFIGURED
        assert "page_access_token_file" in results[0].message

    def test_page_id_not_configured(self, token_file: Path) -> None:
        """Token file set but page_id missing returns NOT_CONFIGURED for page."""
        plugin = MetaPlugin(
            config={"page_access_token_file": str(token_file)}
        )

        with patch("reeln_meta_plugin.plugin.auth") as mock_auth:
            mock_auth.read_token.return_value = "test-token"
            mock_auth.AuthError = AuthError
            results = plugin.auth_check()

        assert len(results) == 1
        assert results[0].service == "Facebook Page"
        assert results[0].status == AuthStatus.NOT_CONFIGURED
        assert "page_id" in results[0].message

    def test_token_read_fails(self, token_file: Path) -> None:
        """auth.read_token raising AuthError returns FAIL."""
        plugin = MetaPlugin(
            config={
                "page_access_token_file": str(token_file),
                "page_id": "123456789",
            }
        )

        with patch("reeln_meta_plugin.plugin.auth") as mock_auth:
            mock_auth.AuthError = AuthError
            mock_auth.read_token.side_effect = AuthError("Token file not found")
            results = plugin.auth_check()

        assert len(results) == 1
        assert results[0].service == "Facebook Page"
        assert results[0].status == AuthStatus.FAIL
        assert "Token file not found" in results[0].message

    def test_facebook_page_api_error(self, token_file: Path) -> None:
        """Graph API error on page check returns FAIL for Facebook Page."""
        plugin = MetaPlugin(
            config={
                "page_access_token_file": str(token_file),
                "page_id": "123456789",
            }
        )

        with (
            patch("reeln_meta_plugin.plugin.auth") as mock_auth,
            patch("reeln_meta_plugin.graph_api.http_get") as mock_http_get,
        ):
            mock_auth.read_token.return_value = "test-token"
            mock_auth.AuthError = AuthError
            mock_http_get.side_effect = GraphAPIError("HTTP 401: Invalid token")
            results = plugin.auth_check()

        assert len(results) == 1
        assert results[0].service == "Facebook Page"
        assert results[0].status == AuthStatus.FAIL
        assert "HTTP 401" in results[0].message
        assert results[0].hint != ""

    def test_facebook_page_success(self, token_file: Path) -> None:
        """Successful page API call returns OK with page name as identity."""
        plugin = MetaPlugin(
            config={
                "page_access_token_file": str(token_file),
                "page_id": "123456789",
            }
        )

        with (
            patch("reeln_meta_plugin.plugin.auth") as mock_auth,
            patch("reeln_meta_plugin.graph_api.http_get") as mock_http_get,
        ):
            mock_auth.read_token.return_value = "test-token"
            mock_auth.AuthError = AuthError
            mock_http_get.return_value = {
                "name": "My Page",
                "id": "123456789",
            }
            results = plugin.auth_check()

        assert len(results) == 1
        assert results[0].service == "Facebook Page"
        assert results[0].status == AuthStatus.OK
        assert results[0].identity == "My Page"
        assert results[0].message == "Token valid"

    def test_with_instagram_success(self, token_file: Path) -> None:
        """Both page and IG configured and valid returns 2 OK results."""
        plugin = MetaPlugin(
            config={
                "page_access_token_file": str(token_file),
                "page_id": "123456789",
                "instagram_account_id": "987654321",
            }
        )

        def mock_get(url: str, params: dict[str, str]) -> dict[str, Any]:
            if "123456789" in url:
                return {"name": "My Page", "id": "123456789"}
            if "987654321" in url:
                return {"username": "myinsta", "name": "My Insta"}
            msg = f"Unexpected URL: {url}"
            raise AssertionError(msg)

        with (
            patch("reeln_meta_plugin.plugin.auth") as mock_auth,
            patch("reeln_meta_plugin.graph_api.http_get") as mock_http_get,
        ):
            mock_auth.read_token.return_value = "test-token"
            mock_auth.AuthError = AuthError
            mock_http_get.side_effect = mock_get
            results = plugin.auth_check()

        assert len(results) == 2
        assert results[0].service == "Facebook Page"
        assert results[0].status == AuthStatus.OK
        assert results[0].identity == "My Page"
        assert results[1].service == "Instagram"
        assert results[1].status == AuthStatus.OK
        assert results[1].identity == "myinsta"

    def test_instagram_api_error(self, token_file: Path) -> None:
        """Page OK but IG call fails returns OK for page, FAIL for IG."""
        plugin = MetaPlugin(
            config={
                "page_access_token_file": str(token_file),
                "page_id": "123456789",
                "instagram_account_id": "987654321",
            }
        )

        def mock_get(url: str, params: dict[str, str]) -> dict[str, Any]:
            if "123456789" in url:
                return {"name": "My Page", "id": "123456789"}
            if "987654321" in url:
                raise GraphAPIError("HTTP 400: Invalid IG account")
            msg = f"Unexpected URL: {url}"
            raise AssertionError(msg)

        with (
            patch("reeln_meta_plugin.plugin.auth") as mock_auth,
            patch("reeln_meta_plugin.graph_api.http_get") as mock_http_get,
        ):
            mock_auth.read_token.return_value = "test-token"
            mock_auth.AuthError = AuthError
            mock_http_get.side_effect = mock_get
            results = plugin.auth_check()

        assert len(results) == 2
        assert results[0].service == "Facebook Page"
        assert results[0].status == AuthStatus.OK
        assert results[1].service == "Instagram"
        assert results[1].status == AuthStatus.FAIL
        assert "HTTP 400" in results[1].message
        assert results[1].hint != ""

    def test_no_instagram_configured(self, token_file: Path) -> None:
        """Only page configured returns 1 result, no IG result."""
        plugin = MetaPlugin(
            config={
                "page_access_token_file": str(token_file),
                "page_id": "123456789",
            }
        )

        with (
            patch("reeln_meta_plugin.plugin.auth") as mock_auth,
            patch("reeln_meta_plugin.graph_api.http_get") as mock_http_get,
        ):
            mock_auth.read_token.return_value = "test-token"
            mock_auth.AuthError = AuthError
            mock_http_get.return_value = {
                "name": "My Page",
                "id": "123456789",
            }
            results = plugin.auth_check()

        assert len(results) == 1
        assert results[0].service == "Facebook Page"
        # Ensure no Instagram result snuck in
        services = [r.service for r in results]
        assert "Instagram" not in services

    def test_token_file_not_configured_with_instagram(self) -> None:
        """Token file missing with IG configured returns NOT_CONFIGURED for both."""
        plugin = MetaPlugin(
            config={"instagram_account_id": "987654321"}
        )
        results = plugin.auth_check()

        assert len(results) == 2
        assert results[0].service == "Facebook Page"
        assert results[0].status == AuthStatus.NOT_CONFIGURED
        assert results[1].service == "Instagram"
        assert results[1].status == AuthStatus.NOT_CONFIGURED

    def test_token_read_fails_with_instagram(self, token_file: Path) -> None:
        """Token read failure with IG configured returns FAIL for both."""
        plugin = MetaPlugin(
            config={
                "page_access_token_file": str(token_file),
                "page_id": "123456789",
                "instagram_account_id": "987654321",
            }
        )

        with patch("reeln_meta_plugin.plugin.auth") as mock_auth:
            mock_auth.AuthError = AuthError
            mock_auth.read_token.side_effect = AuthError("Token file empty")
            results = plugin.auth_check()

        assert len(results) == 2
        assert results[0].service == "Facebook Page"
        assert results[0].status == AuthStatus.FAIL
        assert results[1].service == "Instagram"
        assert results[1].status == AuthStatus.FAIL


class TestAuthRefresh:
    """Tests for MetaPlugin.auth_refresh()."""

    def test_auth_refresh_returns_fail(self) -> None:
        """auth_refresh always returns FAIL with helpful hint."""
        plugin = MetaPlugin()
        results = plugin.auth_refresh()

        assert len(results) == 1
        assert results[0].service == "Meta"
        assert results[0].status == AuthStatus.FAIL
        assert "cannot be refreshed" in results[0].message
        assert "developers.facebook.com" in results[0].hint
