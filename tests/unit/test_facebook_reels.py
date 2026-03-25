"""Tests for facebook_reels module."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from reeln_meta_plugin.facebook_reels import (
    FacebookReelsError,
    ReelStartResult,
    finish_reel,
    poll_reel_status,
    start_reel_upload,
    upload_reel_video,
)
from reeln_meta_plugin.graph_api import GraphAPIError

# ------------------------------------------------------------------
# FacebookReelsError
# ------------------------------------------------------------------


class TestFacebookReelsErrorInheritance:
    def test_is_graph_api_error(self) -> None:
        assert issubclass(FacebookReelsError, GraphAPIError)

    def test_is_exception(self) -> None:
        assert issubclass(FacebookReelsError, Exception)


# ------------------------------------------------------------------
# ReelStartResult
# ------------------------------------------------------------------


class TestReelStartResult:
    def test_frozen(self) -> None:
        r = ReelStartResult(video_id="v1", upload_url="https://rupload.facebook.com/v1")
        with pytest.raises(AttributeError):
            r.video_id = "v2"  # type: ignore[misc]

    def test_fields(self) -> None:
        r = ReelStartResult(video_id="v1", upload_url="https://rupload.facebook.com/v1")
        assert r.video_id == "v1"
        assert r.upload_url == "https://rupload.facebook.com/v1"


# ------------------------------------------------------------------
# start_reel_upload
# ------------------------------------------------------------------


class TestStartReelUpload:
    def test_success(self) -> None:
        with patch(
            "reeln_meta_plugin.facebook_reels.http_post",
            return_value={
                "video_id": "vid-123",
                "upload_url": "https://rupload.facebook.com/video-upload/v24.0/vid-123",
            },
        ) as mock_post:
            result = start_reel_upload(
                page_id="page-1",
                access_token="tok",
                api_version="v24.0",
            )

        assert result.video_id == "vid-123"
        assert "rupload" in result.upload_url
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert "video_reels" in call_args[0][0]
        assert call_args[0][1]["upload_phase"] == "start"

    def test_url_and_payload(self) -> None:
        with patch(
            "reeln_meta_plugin.facebook_reels.http_post",
            return_value={"video_id": "v1", "upload_url": "https://rupload.facebook.com/v1"},
        ) as mock_post:
            start_reel_upload(page_id="pg-42", access_token="tok-99", api_version="v25.0")

        url, payload = mock_post.call_args[0]
        assert url == "https://graph.facebook.com/v25.0/pg-42/video_reels"
        assert payload["upload_phase"] == "start"
        assert payload["access_token"] == "tok-99"

    def test_missing_video_id(self) -> None:
        with (
            patch(
                "reeln_meta_plugin.facebook_reels.http_post",
                return_value={"upload_url": "https://rupload.facebook.com/v1"},
            ),
            pytest.raises(FacebookReelsError, match="missing video_id"),
        ):
            start_reel_upload(page_id="p1", access_token="t")

    def test_missing_upload_url(self) -> None:
        with (
            patch(
                "reeln_meta_plugin.facebook_reels.http_post",
                return_value={"video_id": "v1"},
            ),
            pytest.raises(FacebookReelsError, match="missing upload_url"),
        ):
            start_reel_upload(page_id="p1", access_token="t")

    def test_api_error(self) -> None:
        with (
            patch(
                "reeln_meta_plugin.facebook_reels.http_post",
                side_effect=GraphAPIError("HTTP 400"),
            ),
            pytest.raises(FacebookReelsError, match="HTTP 400"),
        ):
            start_reel_upload(page_id="p1", access_token="t")

    def test_default_api_version(self) -> None:
        with patch(
            "reeln_meta_plugin.facebook_reels.http_post",
            return_value={"video_id": "v1", "upload_url": "https://rupload.facebook.com/v1"},
        ) as mock_post:
            start_reel_upload(page_id="p1", access_token="t")

        url = mock_post.call_args[0][0]
        assert "/v24.0/" in url


# ------------------------------------------------------------------
# upload_reel_video
# ------------------------------------------------------------------


class TestUploadReelVideo:
    def test_success(self) -> None:
        with patch(
            "reeln_meta_plugin.facebook_reels.http_post_rupload",
            return_value={"success": True},
        ) as mock_rupload:
            upload_reel_video(
                upload_url="https://rupload.facebook.com/v1",
                access_token="tok",
                video_url="https://cdn.example.com/clip.mp4",
            )

        mock_rupload.assert_called_once_with(
            "https://rupload.facebook.com/v1",
            "tok",
            file_url="https://cdn.example.com/clip.mp4",
        )

    def test_unexpected_response(self) -> None:
        with (
            patch(
                "reeln_meta_plugin.facebook_reels.http_post_rupload",
                return_value={"success": False},
            ),
            pytest.raises(FacebookReelsError, match="Upload failed"),
        ):
            upload_reel_video(
                upload_url="https://rupload.facebook.com/v1",
                access_token="tok",
                video_url="https://cdn.example.com/clip.mp4",
            )

    def test_api_error(self) -> None:
        with (
            patch(
                "reeln_meta_plugin.facebook_reels.http_post_rupload",
                side_effect=GraphAPIError("HTTP 500"),
            ),
            pytest.raises(FacebookReelsError, match="HTTP 500"),
        ):
            upload_reel_video(
                upload_url="https://rupload.facebook.com/v1",
                access_token="tok",
                video_url="https://cdn.example.com/clip.mp4",
            )


# ------------------------------------------------------------------
# poll_reel_status
# ------------------------------------------------------------------


class TestPollReelStatus:
    def test_immediate_complete(self) -> None:
        with patch(
            "reeln_meta_plugin.facebook_reels.http_get",
            return_value={
                "status": {
                    "video_status": "ready",
                    "processing_phase": {"status": "complete"},
                }
            },
        ):
            result = poll_reel_status(video_id="v1", access_token="t", max_attempts=1)

        assert result == "complete"

    def test_retry_then_complete(self) -> None:
        responses = [
            {
                "status": {
                    "video_status": "processing",
                    "processing_phase": {"status": "in_progress"},
                }
            },
            {
                "status": {
                    "video_status": "ready",
                    "processing_phase": {"status": "complete"},
                }
            },
        ]

        with (
            patch(
                "reeln_meta_plugin.facebook_reels.http_get",
                side_effect=responses,
            ),
            patch("reeln_meta_plugin.facebook_reels.time.sleep") as mock_sleep,
        ):
            result = poll_reel_status(
                video_id="v1", access_token="t", max_attempts=5, poll_interval=2.0,
            )

        assert result == "complete"
        mock_sleep.assert_called_once_with(2.0)

    def test_processing_error(self) -> None:
        with (
            patch(
                "reeln_meta_plugin.facebook_reels.http_get",
                return_value={
                    "status": {
                        "video_status": "error",
                        "processing_phase": {"status": "error", "errors": ["bad codec"]},
                    }
                },
            ),
            pytest.raises(FacebookReelsError, match="processing failed"),
        ):
            poll_reel_status(video_id="v1", access_token="t", max_attempts=1)

    def test_video_status_error(self) -> None:
        with (
            patch(
                "reeln_meta_plugin.facebook_reels.http_get",
                return_value={
                    "status": {
                        "video_status": "error",
                        "processing_phase": {"status": "not_started"},
                    }
                },
            ),
            pytest.raises(FacebookReelsError, match="video_status=error"),
        ):
            poll_reel_status(video_id="v1", access_token="t", max_attempts=1)

    def test_timeout(self) -> None:
        with (
            patch(
                "reeln_meta_plugin.facebook_reels.http_get",
                return_value={
                    "status": {
                        "video_status": "processing",
                        "processing_phase": {"status": "in_progress"},
                    }
                },
            ),
            patch("reeln_meta_plugin.facebook_reels.time.sleep"),
            pytest.raises(FacebookReelsError, match="not ready after 2 attempts"),
        ):
            poll_reel_status(
                video_id="v1", access_token="t", max_attempts=2, poll_interval=0.0,
            )

    def test_no_sleep_on_last_attempt(self) -> None:
        with (
            patch(
                "reeln_meta_plugin.facebook_reels.http_get",
                return_value={
                    "status": {
                        "video_status": "processing",
                        "processing_phase": {"status": "in_progress"},
                    }
                },
            ),
            patch("reeln_meta_plugin.facebook_reels.time.sleep") as mock_sleep,
            pytest.raises(FacebookReelsError),
        ):
            poll_reel_status(video_id="v1", access_token="t", max_attempts=1)

        mock_sleep.assert_not_called()

    def test_api_error(self) -> None:
        with (
            patch(
                "reeln_meta_plugin.facebook_reels.http_get",
                side_effect=GraphAPIError("HTTP 401"),
            ),
            pytest.raises(FacebookReelsError, match="HTTP 401"),
        ):
            poll_reel_status(video_id="v1", access_token="t", max_attempts=1)

    def test_unexpected_status_format(self) -> None:
        with (
            patch(
                "reeln_meta_plugin.facebook_reels.http_get",
                return_value={"status": "not_a_dict"},
            ),
            pytest.raises(FacebookReelsError, match="Unexpected status format"),
        ):
            poll_reel_status(video_id="v1", access_token="t", max_attempts=1)

    def test_default_api_version(self) -> None:
        with (
            patch(
                "reeln_meta_plugin.facebook_reels.http_get",
                return_value={
                    "status": {
                        "video_status": "ready",
                        "processing_phase": {"status": "complete"},
                    }
                },
            ) as mock_get,
        ):
            poll_reel_status(video_id="v1", access_token="t")

        url = mock_get.call_args[0][0]
        assert "/v24.0/" in url


# ------------------------------------------------------------------
# finish_reel
# ------------------------------------------------------------------


class TestFinishReel:
    def test_success(self) -> None:
        with patch(
            "reeln_meta_plugin.facebook_reels.http_post",
            return_value={"success": True},
        ) as mock_post:
            finish_reel(
                page_id="p1",
                access_token="tok",
                video_id="v1",
                title="Goal!",
                description="Amazing play",
                api_version="v24.0",
            )

        url, payload = mock_post.call_args[0]
        assert "video_reels" in url
        assert payload["upload_phase"] == "finish"
        assert payload["video_id"] == "v1"
        assert payload["video_state"] == "PUBLISHED"
        assert payload["title"] == "Goal!"
        assert payload["description"] == "Amazing play"

    def test_url_and_payload(self) -> None:
        with patch(
            "reeln_meta_plugin.facebook_reels.http_post",
            return_value={"success": True},
        ) as mock_post:
            finish_reel(
                page_id="pg-42",
                access_token="tok-99",
                video_id="vid-1",
                api_version="v25.0",
            )

        url, payload = mock_post.call_args[0]
        assert url == "https://graph.facebook.com/v25.0/pg-42/video_reels"
        assert payload["upload_phase"] == "finish"
        assert payload["video_id"] == "vid-1"
        assert payload["access_token"] == "tok-99"
        assert "title" not in payload
        assert "description" not in payload

    def test_empty_title_and_description_omitted(self) -> None:
        with patch(
            "reeln_meta_plugin.facebook_reels.http_post",
            return_value={"success": True},
        ) as mock_post:
            finish_reel(
                page_id="p1", access_token="t", video_id="v1",
                title="", description="",
            )

        payload = mock_post.call_args[0][1]
        assert "title" not in payload
        assert "description" not in payload

    def test_custom_video_state(self) -> None:
        with patch(
            "reeln_meta_plugin.facebook_reels.http_post",
            return_value={"success": True},
        ) as mock_post:
            finish_reel(
                page_id="p1", access_token="t", video_id="v1",
                video_state="DRAFT",
            )

        payload = mock_post.call_args[0][1]
        assert payload["video_state"] == "DRAFT"

    def test_unexpected_response(self) -> None:
        with (
            patch(
                "reeln_meta_plugin.facebook_reels.http_post",
                return_value={"success": False},
            ),
            pytest.raises(FacebookReelsError, match="Publish failed"),
        ):
            finish_reel(page_id="p1", access_token="t", video_id="v1")

    def test_api_error(self) -> None:
        with (
            patch(
                "reeln_meta_plugin.facebook_reels.http_post",
                side_effect=GraphAPIError("HTTP 400"),
            ),
            pytest.raises(FacebookReelsError, match="HTTP 400"),
        ):
            finish_reel(page_id="p1", access_token="t", video_id="v1")

    def test_default_api_version(self) -> None:
        with patch(
            "reeln_meta_plugin.facebook_reels.http_post",
            return_value={"success": True},
        ) as mock_post:
            finish_reel(page_id="p1", access_token="t", video_id="v1")

        url = mock_post.call_args[0][0]
        assert "/v24.0/" in url
