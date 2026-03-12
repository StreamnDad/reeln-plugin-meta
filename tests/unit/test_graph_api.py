"""Tests for graph_api module."""

from __future__ import annotations

import json
import urllib.error
from io import BytesIO
from unittest.mock import patch

import pytest

from reeln_meta_plugin.graph_api import (
    GraphAPIError,
    format_meta_error,
    http_post,
)


class TestHttpPost:
    def test_success(self) -> None:
        fake_response = BytesIO(b'{"id": "123"}')

        with patch("reeln_meta_plugin.graph_api.urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__ = lambda s: fake_response
            mock_urlopen.return_value.__exit__ = lambda s, *a: None
            result = http_post("https://example.com", {"key": "val"})

        assert result == {"id": "123"}

    def test_http_error_with_meta_format(self) -> None:
        error_body = json.dumps({
            "error": {"message": "Invalid token", "type": "OAuthException", "code": 190}
        }).encode()
        exc = urllib.error.HTTPError(
            "https://example.com", 400, "Bad Request", {}, BytesIO(error_body)  # type: ignore[arg-type]
        )

        with (
            patch("reeln_meta_plugin.graph_api.urllib.request.urlopen", side_effect=exc),
            pytest.raises(GraphAPIError, match=r"OAuthException.*190.*Invalid token"),
        ):
            http_post("https://example.com", {"key": "val"})

    def test_http_error_non_json(self) -> None:
        exc = urllib.error.HTTPError(
            "https://example.com", 500, "Server Error", {}, BytesIO(b"not json")  # type: ignore[arg-type]
        )

        with (
            patch("reeln_meta_plugin.graph_api.urllib.request.urlopen", side_effect=exc),
            pytest.raises(GraphAPIError, match="HTTP 500"),
        ):
            http_post("https://example.com", {"key": "val"})

    def test_http_error_empty_body(self) -> None:
        exc = urllib.error.HTTPError(
            "https://example.com", 401, "Unauthorized", {}, None  # type: ignore[arg-type]
        )
        exc.fp = None  # type: ignore[assignment]

        with (
            patch("reeln_meta_plugin.graph_api.urllib.request.urlopen", side_effect=exc),
            pytest.raises(GraphAPIError, match="HTTP 401"),
        ):
            http_post("https://example.com", {"key": "val"})

    def test_url_error(self) -> None:
        exc = urllib.error.URLError("Connection refused")

        with (
            patch("reeln_meta_plugin.graph_api.urllib.request.urlopen", side_effect=exc),
            pytest.raises(GraphAPIError, match=r"Request failed.*Connection refused"),
        ):
            http_post("https://example.com", {"key": "val"})

    def test_invalid_json_response(self) -> None:
        fake_response = BytesIO(b"not json at all")

        with (
            patch("reeln_meta_plugin.graph_api.urllib.request.urlopen") as mock_urlopen,
            pytest.raises(GraphAPIError, match="Invalid JSON response"),
        ):
            mock_urlopen.return_value.__enter__ = lambda s: fake_response
            mock_urlopen.return_value.__exit__ = lambda s, *a: None
            http_post("https://example.com", {"key": "val"})


class TestFormatMetaError:
    def test_empty_string(self) -> None:
        assert format_meta_error("") == "(empty response)"

    def test_valid_error_json(self) -> None:
        data = json.dumps({
            "error": {"message": "Bad request", "type": "OAuthException", "code": 400}
        })
        result = format_meta_error(data)
        assert "OAuthException" in result
        assert "400" in result
        assert "Bad request" in result

    def test_error_without_type(self) -> None:
        data = json.dumps({"error": {"message": "Something went wrong"}})
        result = format_meta_error(data)
        assert result == "Something went wrong"

    def test_non_json(self) -> None:
        result = format_meta_error("plain text error")
        assert result == "plain text error"

    def test_non_dict_json(self) -> None:
        result = format_meta_error("[1, 2, 3]")
        assert result == "[1, 2, 3]"

    def test_no_error_key(self) -> None:
        data = json.dumps({"status": "error", "detail": "something"})
        result = format_meta_error(data)
        assert "status" in result

    def test_error_not_dict(self) -> None:
        data = json.dumps({"error": "just a string"})
        result = format_meta_error(data)
        assert "error" in result
