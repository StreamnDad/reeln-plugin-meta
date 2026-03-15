"""Tests for livestream module."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from reeln_meta_plugin.graph_api import GraphAPIError
from reeln_meta_plugin.livestream import (
    LivestreamError,
    LivestreamResult,
    create_livestream,
    update_livestream,
    upload_thumbnail,
)


class TestLivestreamResult:
    def test_frozen(self) -> None:
        result = LivestreamResult(id="1", stream_url="rtmps://", embed_url="https://fb.com/1")
        with pytest.raises(AttributeError):
            result.id = "2"  # type: ignore[misc]


class TestLivestreamErrorInheritance:
    def test_subclasses_graph_api_error(self) -> None:
        assert issubclass(LivestreamError, GraphAPIError)


class TestCreateLivestream:
    def test_success(self) -> None:
        response = {
            "id": "live-123",
            "stream_url": "rtmps://live.facebook.com/rtmp/live-123",
        }
        with patch("reeln_meta_plugin.livestream.http_post", return_value=response):
            result = create_livestream(
                page_id="page-456",
                access_token="tok",
                title="Eagles vs Hawks",
            )

        assert result.id == "live-123"
        assert result.stream_url == "rtmps://live.facebook.com/rtmp/live-123"
        assert result.embed_url == "https://www.facebook.com/page-456/videos/live-123"

    def test_uses_secure_stream_url_fallback(self) -> None:
        response = {
            "id": "live-123",
            "secure_stream_url": "rtmps://secure.facebook.com/rtmp/live-123",
        }
        with patch("reeln_meta_plugin.livestream.http_post", return_value=response):
            result = create_livestream(
                page_id="page-456",
                access_token="tok",
                title="Test",
            )

        assert result.stream_url == "rtmps://secure.facebook.com/rtmp/live-123"

    def test_missing_id_raises(self) -> None:
        response = {"stream_url": "rtmps://live.facebook.com/rtmp/xxx"}
        with (
            patch("reeln_meta_plugin.livestream.http_post", return_value=response),
            pytest.raises(LivestreamError, match="missing id or stream_url"),
        ):
            create_livestream(page_id="p", access_token="t", title="T")

    def test_missing_stream_url_raises(self) -> None:
        response = {"id": "live-123"}
        with (
            patch("reeln_meta_plugin.livestream.http_post", return_value=response),
            pytest.raises(LivestreamError, match="missing id or stream_url"),
        ):
            create_livestream(page_id="p", access_token="t", title="T")

    def test_description_and_api_version(self) -> None:
        response = {"id": "1", "stream_url": "rtmps://x"}
        with patch("reeln_meta_plugin.livestream.http_post", return_value=response) as mock_post:
            create_livestream(
                page_id="p",
                access_token="t",
                title="T",
                description="desc",
                api_version="v23.0",
            )

        url, payload = mock_post.call_args[0]
        assert "v23.0" in url
        assert payload["description"] == "desc"

    def test_default_description_and_api_version(self) -> None:
        response = {"id": "1", "stream_url": "rtmps://x"}
        with patch("reeln_meta_plugin.livestream.http_post", return_value=response) as mock_post:
            create_livestream(page_id="p", access_token="t", title="T")

        url, payload = mock_post.call_args[0]
        assert "v24.0" in url
        assert payload["description"] == ""

    def test_default_status_and_privacy(self) -> None:
        response = {"id": "1", "stream_url": "rtmps://x"}
        with patch("reeln_meta_plugin.livestream.http_post", return_value=response) as mock_post:
            create_livestream(page_id="p", access_token="t", title="T")

        _, payload = mock_post.call_args[0]
        assert payload["status"] == "LIVE_NOW"
        assert "privacy" not in payload
        assert "event_params" not in payload
        assert payload["content_category"] == "SPORTS"
        assert json.loads(payload["stop_on_delete_stream"]) is False

    def test_custom_status_and_privacy(self) -> None:
        response = {"id": "1", "stream_url": "rtmps://x"}
        with patch("reeln_meta_plugin.livestream.http_post", return_value=response) as mock_post:
            create_livestream(
                page_id="p",
                access_token="t",
                title="T",
                status="UNPUBLISHED",
                privacy="SELF",
                content_category="VIDEO_GAMING",
                stop_on_delete_stream=True,
            )

        _, payload = mock_post.call_args[0]
        assert payload["status"] == "UNPUBLISHED"
        assert json.loads(payload["privacy"]) == {"value": "SELF"}
        assert payload["content_category"] == "VIDEO_GAMING"
        assert json.loads(payload["stop_on_delete_stream"]) is True

    def test_game_id_included_when_set(self) -> None:
        response = {"id": "1", "stream_url": "rtmps://x"}
        with patch("reeln_meta_plugin.livestream.http_post", return_value=response) as mock_post:
            create_livestream(
                page_id="p",
                access_token="t",
                title="T",
                game_id="999",
            )

        _, payload = mock_post.call_args[0]
        assert payload["game_id"] == "999"

    def test_game_id_omitted_when_empty(self) -> None:
        response = {"id": "1", "stream_url": "rtmps://x"}
        with patch("reeln_meta_plugin.livestream.http_post", return_value=response) as mock_post:
            create_livestream(page_id="p", access_token="t", title="T")

        _, payload = mock_post.call_args[0]
        assert "game_id" not in payload

    def test_event_params_included_when_set(self) -> None:
        response = {"id": "1", "stream_url": "rtmps://x"}
        with patch("reeln_meta_plugin.livestream.http_post", return_value=response) as mock_post:
            create_livestream(
                page_id="p",
                access_token="t",
                title="T",
                status="SCHEDULED_UNPUBLISHED",
                event_params="1741539800",
            )

        _, payload = mock_post.call_args[0]
        assert payload["status"] == "SCHEDULED_UNPUBLISHED"
        assert payload["event_params"] == "1741539800"

    def test_event_params_omitted_when_empty(self) -> None:
        response = {"id": "1", "stream_url": "rtmps://x"}
        with patch("reeln_meta_plugin.livestream.http_post", return_value=response) as mock_post:
            create_livestream(page_id="p", access_token="t", title="T")

        _, payload = mock_post.call_args[0]
        assert "event_params" not in payload

    def test_graph_api_error_wrapped_as_livestream_error(self) -> None:
        with (
            patch(
                "reeln_meta_plugin.livestream.http_post",
                side_effect=GraphAPIError("HTTP 500: server error"),
            ),
            pytest.raises(LivestreamError, match="HTTP 500"),
        ):
            create_livestream(page_id="p", access_token="t", title="T")


class TestUpdateLivestream:
    def test_updates_title(self) -> None:
        with patch("reeln_meta_plugin.livestream.http_post", return_value={}) as mock_post:
            update_livestream(
                live_video_id="live-123",
                access_token="tok",
                title="New Title",
            )

        url, payload = mock_post.call_args[0]
        assert "live-123" in url
        assert payload["title"] == "New Title"
        assert "description" not in payload

    def test_updates_description(self) -> None:
        with patch("reeln_meta_plugin.livestream.http_post", return_value={}) as mock_post:
            update_livestream(
                live_video_id="live-123",
                access_token="tok",
                description="New Desc",
            )

        _, payload = mock_post.call_args[0]
        assert payload["description"] == "New Desc"
        assert "title" not in payload

    def test_updates_both(self) -> None:
        with patch("reeln_meta_plugin.livestream.http_post", return_value={}) as mock_post:
            update_livestream(
                live_video_id="live-123",
                access_token="tok",
                title="T",
                description="D",
            )

        _, payload = mock_post.call_args[0]
        assert payload["title"] == "T"
        assert payload["description"] == "D"

    def test_custom_api_version(self) -> None:
        with patch("reeln_meta_plugin.livestream.http_post", return_value={}) as mock_post:
            update_livestream(
                live_video_id="live-123",
                access_token="tok",
                title="T",
                api_version="v23.0",
            )

        url, _ = mock_post.call_args[0]
        assert "v23.0" in url

    def test_skips_when_no_fields(self) -> None:
        with patch("reeln_meta_plugin.livestream.http_post") as mock_post:
            update_livestream(
                live_video_id="live-123",
                access_token="tok",
            )

        mock_post.assert_not_called()

    def test_skips_when_empty_strings(self) -> None:
        with patch("reeln_meta_plugin.livestream.http_post") as mock_post:
            update_livestream(
                live_video_id="live-123",
                access_token="tok",
                title="",
                description="",
            )

        mock_post.assert_not_called()

    def test_graph_api_error_wrapped(self) -> None:
        with (
            patch(
                "reeln_meta_plugin.livestream.http_post",
                side_effect=GraphAPIError("HTTP 400: bad request"),
            ),
            pytest.raises(LivestreamError, match="HTTP 400"),
        ):
            update_livestream(
                live_video_id="live-123",
                access_token="tok",
                title="T",
            )


class TestUploadThumbnail:
    def test_success(self, tmp_path: Path) -> None:
        thumb = tmp_path / "thumb.png"
        thumb.write_bytes(b"\x89PNG")

        with patch("reeln_meta_plugin.livestream.http_post_multipart", return_value={}) as mock_post:
            upload_thumbnail(
                live_video_id="live-123",
                access_token="tok",
                image_path=thumb,
            )

        url = mock_post.call_args[0][0]
        kwargs = mock_post.call_args[1]
        assert "live-123" in url
        assert kwargs["fields"]["access_token"] == "tok"
        assert kwargs["files"]["custom_image"] == thumb

    def test_custom_api_version(self, tmp_path: Path) -> None:
        thumb = tmp_path / "thumb.png"
        thumb.write_bytes(b"\x89PNG")

        with patch("reeln_meta_plugin.livestream.http_post_multipart", return_value={}) as mock_post:
            upload_thumbnail(
                live_video_id="live-123",
                access_token="tok",
                image_path=thumb,
                api_version="v23.0",
            )

        assert "v23.0" in mock_post.call_args[0][0]

    def test_graph_api_error_wrapped(self, tmp_path: Path) -> None:
        thumb = tmp_path / "thumb.png"
        thumb.write_bytes(b"\x89PNG")

        with (
            patch(
                "reeln_meta_plugin.livestream.http_post_multipart",
                side_effect=GraphAPIError("HTTP 500: server error"),
            ),
            pytest.raises(LivestreamError, match="HTTP 500"),
        ):
            upload_thumbnail(
                live_video_id="live-123",
                access_token="tok",
                image_path=thumb,
            )
