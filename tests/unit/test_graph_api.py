"""Tests for graph_api module."""

from __future__ import annotations

import json
import urllib.error
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pytest

from reeln_meta_plugin.graph_api import (
    GraphAPIError,
    format_meta_error,
    http_post,
    http_post_multipart,
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


class TestHttpPostMultipart:
    def test_success(self, tmp_path: Path) -> None:
        image = tmp_path / "thumb.png"
        image.write_bytes(b"\x89PNG\r\ndata")

        fake_response = BytesIO(b'{"success": true}')

        with patch("reeln_meta_plugin.graph_api.urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__ = lambda s: fake_response
            mock_urlopen.return_value.__exit__ = lambda s, *a: None
            result = http_post_multipart(
                "https://example.com",
                {"access_token": "tok"},
                {"thumb": image},
            )

        assert result == {"success": True}

        # Verify multipart content-type header
        request = mock_urlopen.call_args[0][0]
        content_type = request.get_header("Content-type")
        assert "multipart/form-data" in content_type

        # Verify body contains field and file data
        body = request.data
        assert b"access_token" in body
        assert b"tok" in body
        assert b"thumb" in body
        assert b"thumb.png" in body
        assert b"\x89PNG\r\ndata" in body

    def test_http_error(self, tmp_path: Path) -> None:
        image = tmp_path / "thumb.png"
        image.write_bytes(b"\x89PNG")

        error_body = json.dumps({"error": {"message": "Bad image"}}).encode()
        exc = urllib.error.HTTPError(
            "https://example.com", 400, "Bad Request", {}, BytesIO(error_body)  # type: ignore[arg-type]
        )

        with (
            patch("reeln_meta_plugin.graph_api.urllib.request.urlopen", side_effect=exc),
            pytest.raises(GraphAPIError, match="HTTP 400"),
        ):
            http_post_multipart("https://example.com", {"access_token": "tok"}, {"thumb": image})

    def test_url_error(self, tmp_path: Path) -> None:
        image = tmp_path / "thumb.png"
        image.write_bytes(b"\x89PNG")

        exc = urllib.error.URLError("Connection refused")

        with (
            patch("reeln_meta_plugin.graph_api.urllib.request.urlopen", side_effect=exc),
            pytest.raises(GraphAPIError, match="Request failed"),
        ):
            http_post_multipart("https://example.com", {"access_token": "tok"}, {"thumb": image})

    def test_invalid_json_response(self, tmp_path: Path) -> None:
        image = tmp_path / "thumb.png"
        image.write_bytes(b"\x89PNG")

        fake_response = BytesIO(b"not json")

        with (
            patch("reeln_meta_plugin.graph_api.urllib.request.urlopen") as mock_urlopen,
            pytest.raises(GraphAPIError, match="Invalid JSON response"),
        ):
            mock_urlopen.return_value.__enter__ = lambda s: fake_response
            mock_urlopen.return_value.__exit__ = lambda s, *a: None
            http_post_multipart("https://example.com", {"access_token": "tok"}, {"thumb": image})

    def test_http_error_empty_body(self, tmp_path: Path) -> None:
        image = tmp_path / "thumb.png"
        image.write_bytes(b"\x89PNG")

        exc = urllib.error.HTTPError(
            "https://example.com", 401, "Unauthorized", {}, None  # type: ignore[arg-type]
        )
        exc.fp = None  # type: ignore[assignment]

        with (
            patch("reeln_meta_plugin.graph_api.urllib.request.urlopen", side_effect=exc),
            pytest.raises(GraphAPIError, match="HTTP 401"),
        ):
            http_post_multipart("https://example.com", {"access_token": "tok"}, {"thumb": image})

    def test_content_type_detection(self, tmp_path: Path) -> None:
        """Verify JPEG files get correct content type in the multipart body."""
        image = tmp_path / "photo.jpg"
        image.write_bytes(b"\xff\xd8\xff")

        fake_response = BytesIO(b'{"success": true}')

        with patch("reeln_meta_plugin.graph_api.urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__ = lambda s: fake_response
            mock_urlopen.return_value.__exit__ = lambda s, *a: None
            http_post_multipart("https://example.com", {}, {"thumb": image})

        body = mock_urlopen.call_args[0][0].data
        assert b"image/jpeg" in body


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
