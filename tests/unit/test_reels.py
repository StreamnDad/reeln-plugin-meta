"""Tests for reels module."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from reeln_meta_plugin.graph_api import GraphAPIError
from reeln_meta_plugin.reels import (
    ReelContainerResult,
    ReelPublishResult,
    ReelsError,
    create_reel_container,
    get_permalink,
    poll_container_status,
    publish_reel,
)


class TestReelsErrorInheritance:
    def test_subclasses_graph_api_error(self) -> None:
        assert issubclass(ReelsError, GraphAPIError)


class TestReelContainerResult:
    def test_frozen(self) -> None:
        result = ReelContainerResult(container_id="c-1")
        with pytest.raises(AttributeError):
            result.container_id = "c-2"  # type: ignore[misc]


class TestReelPublishResult:
    def test_frozen(self) -> None:
        result = ReelPublishResult(media_id="m-1", permalink="https://ig.com/p/1")
        with pytest.raises(AttributeError):
            result.media_id = "m-2"  # type: ignore[misc]


class TestCreateReelContainer:
    def test_success(self) -> None:
        response = {"id": "container-123"}
        with patch("reeln_meta_plugin.reels.http_post", return_value=response):
            result = create_reel_container(
                ig_user_id="ig-456",
                access_token="tok",
                video_url="https://cdn.example.com/clip.mp4",
            )

        assert result.container_id == "container-123"

    def test_payload_and_url(self) -> None:
        response = {"id": "c-1"}
        with patch("reeln_meta_plugin.reels.http_post", return_value=response) as mock_post:
            create_reel_container(
                ig_user_id="ig-456",
                access_token="tok",
                video_url="https://cdn.example.com/clip.mp4",
                caption="Game highlights",
                share_to_feed=False,
                thumb_offset=5000,
                api_version="v23.0",
            )

        url, payload = mock_post.call_args[0]
        assert "v23.0" in url
        assert "ig-456/media" in url
        assert payload["media_type"] == "REELS"
        assert payload["video_url"] == "https://cdn.example.com/clip.mp4"
        assert payload["caption"] == "Game highlights"
        assert payload["share_to_feed"] == "false"
        assert payload["thumb_offset"] == "5000"
        assert payload["access_token"] == "tok"

    def test_defaults(self) -> None:
        response = {"id": "c-1"}
        with patch("reeln_meta_plugin.reels.http_post", return_value=response) as mock_post:
            create_reel_container(
                ig_user_id="ig-456",
                access_token="tok",
                video_url="https://cdn.example.com/clip.mp4",
            )

        url, payload = mock_post.call_args[0]
        assert "v24.0" in url
        assert payload["caption"] == ""
        assert payload["share_to_feed"] == "true"
        assert payload["thumb_offset"] == "0"

    def test_missing_id_raises(self) -> None:
        response = {"status": "ok"}
        with (
            patch("reeln_meta_plugin.reels.http_post", return_value=response),
            pytest.raises(ReelsError, match="missing id"),
        ):
            create_reel_container(
                ig_user_id="ig-456",
                access_token="tok",
                video_url="https://cdn.example.com/clip.mp4",
            )

    def test_graph_api_error_wrapped(self) -> None:
        with (
            patch(
                "reeln_meta_plugin.reels.http_post",
                side_effect=GraphAPIError("HTTP 500: server error"),
            ),
            pytest.raises(ReelsError, match="HTTP 500"),
        ):
            create_reel_container(
                ig_user_id="ig-456",
                access_token="tok",
                video_url="https://cdn.example.com/clip.mp4",
            )


class TestPollContainerStatus:
    def test_immediate_finished(self) -> None:
        with patch(
            "reeln_meta_plugin.reels.http_get",
            return_value={"status_code": "FINISHED"},
        ):
            result = poll_container_status(
                container_id="c-1",
                access_token="tok",
            )

        assert result == "FINISHED"

    def test_in_progress_then_finished(self) -> None:
        with (
            patch(
                "reeln_meta_plugin.reels.http_get",
                side_effect=[
                    {"status_code": "IN_PROGRESS"},
                    {"status_code": "IN_PROGRESS"},
                    {"status_code": "FINISHED"},
                ],
            ),
            patch("reeln_meta_plugin.reels.time.sleep") as mock_sleep,
        ):
            result = poll_container_status(
                container_id="c-1",
                access_token="tok",
                poll_interval=2.0,
            )

        assert result == "FINISHED"
        assert mock_sleep.call_count == 2
        mock_sleep.assert_called_with(2.0)

    def test_error_status_raises(self) -> None:
        with (
            patch(
                "reeln_meta_plugin.reels.http_get",
                return_value={"status_code": "ERROR"},
            ),
            pytest.raises(ReelsError, match="ERROR"),
        ):
            poll_container_status(container_id="c-1", access_token="tok")

    def test_expired_status_raises(self) -> None:
        with (
            patch(
                "reeln_meta_plugin.reels.http_get",
                return_value={"status_code": "EXPIRED"},
            ),
            pytest.raises(ReelsError, match="EXPIRED"),
        ):
            poll_container_status(container_id="c-1", access_token="tok")

    def test_max_attempts_exceeded(self) -> None:
        with (
            patch(
                "reeln_meta_plugin.reels.http_get",
                return_value={"status_code": "IN_PROGRESS"},
            ),
            patch("reeln_meta_plugin.reels.time.sleep"),
            pytest.raises(ReelsError, match="not ready after 3 attempts"),
        ):
            poll_container_status(
                container_id="c-1",
                access_token="tok",
                max_attempts=3,
            )

    def test_no_sleep_after_last_attempt(self) -> None:
        with (
            patch(
                "reeln_meta_plugin.reels.http_get",
                return_value={"status_code": "IN_PROGRESS"},
            ),
            patch("reeln_meta_plugin.reels.time.sleep") as mock_sleep,
            pytest.raises(ReelsError),
        ):
            poll_container_status(
                container_id="c-1",
                access_token="tok",
                max_attempts=2,
            )

        # Only sleeps between attempts, not after the last one
        assert mock_sleep.call_count == 1

    def test_graph_api_error_wrapped(self) -> None:
        with (
            patch(
                "reeln_meta_plugin.reels.http_get",
                side_effect=GraphAPIError("HTTP 400: bad request"),
            ),
            pytest.raises(ReelsError, match="HTTP 400"),
        ):
            poll_container_status(container_id="c-1", access_token="tok")

    def test_custom_api_version(self) -> None:
        with patch(
            "reeln_meta_plugin.reels.http_get",
            return_value={"status_code": "FINISHED"},
        ) as mock_get:
            poll_container_status(
                container_id="c-1",
                access_token="tok",
                api_version="v23.0",
            )

        url = mock_get.call_args[0][0]
        assert "v23.0" in url

    def test_missing_status_code_retries(self) -> None:
        """Empty status_code is treated as in-progress."""
        with (
            patch(
                "reeln_meta_plugin.reels.http_get",
                side_effect=[
                    {"status_code": ""},
                    {"status_code": "FINISHED"},
                ],
            ),
            patch("reeln_meta_plugin.reels.time.sleep"),
        ):
            result = poll_container_status(
                container_id="c-1",
                access_token="tok",
            )

        assert result == "FINISHED"


class TestPublishReel:
    def test_success(self) -> None:
        response = {"id": "media-789"}
        with patch("reeln_meta_plugin.reels.http_post", return_value=response):
            result = publish_reel(
                ig_user_id="ig-456",
                access_token="tok",
                container_id="c-1",
            )

        assert result == "media-789"

    def test_payload_and_url(self) -> None:
        response = {"id": "m-1"}
        with patch("reeln_meta_plugin.reels.http_post", return_value=response) as mock_post:
            publish_reel(
                ig_user_id="ig-456",
                access_token="tok",
                container_id="c-1",
                api_version="v23.0",
            )

        url, payload = mock_post.call_args[0]
        assert "v23.0" in url
        assert "ig-456/media_publish" in url
        assert payload["creation_id"] == "c-1"
        assert payload["access_token"] == "tok"

    def test_missing_id_raises(self) -> None:
        response = {"status": "ok"}
        with (
            patch("reeln_meta_plugin.reels.http_post", return_value=response),
            pytest.raises(ReelsError, match="missing id"),
        ):
            publish_reel(ig_user_id="ig-456", access_token="tok", container_id="c-1")

    def test_graph_api_error_wrapped(self) -> None:
        with (
            patch(
                "reeln_meta_plugin.reels.http_post",
                side_effect=GraphAPIError("HTTP 500: server error"),
            ),
            pytest.raises(ReelsError, match="HTTP 500"),
        ):
            publish_reel(ig_user_id="ig-456", access_token="tok", container_id="c-1")


class TestGetPermalink:
    def test_success_first_attempt(self) -> None:
        with patch(
            "reeln_meta_plugin.reels.http_get",
            return_value={"permalink": "https://www.instagram.com/reel/abc/"},
        ):
            result = get_permalink(media_id="m-1", access_token="tok")

        assert result == "https://www.instagram.com/reel/abc/"

    def test_success_on_retry(self) -> None:
        with (
            patch(
                "reeln_meta_plugin.reels.http_get",
                side_effect=[
                    GraphAPIError("HTTP 500: retry"),
                    {"permalink": "https://www.instagram.com/reel/abc/"},
                ],
            ),
            patch("reeln_meta_plugin.reels.time.sleep") as mock_sleep,
        ):
            result = get_permalink(
                media_id="m-1",
                access_token="tok",
                retry_delay=1.5,
            )

        assert result == "https://www.instagram.com/reel/abc/"
        mock_sleep.assert_called_once_with(1.5)

    def test_all_retries_exhausted(self) -> None:
        with (
            patch(
                "reeln_meta_plugin.reels.http_get",
                side_effect=GraphAPIError("HTTP 500: retry"),
            ),
            patch("reeln_meta_plugin.reels.time.sleep"),
            pytest.raises(ReelsError, match="Failed to get permalink after 2 retries"),
        ):
            get_permalink(
                media_id="m-1",
                access_token="tok",
                max_retries=2,
            )

    def test_empty_permalink_retries(self) -> None:
        with (
            patch(
                "reeln_meta_plugin.reels.http_get",
                side_effect=[
                    {"permalink": ""},
                    {"permalink": "https://www.instagram.com/reel/abc/"},
                ],
            ),
            patch("reeln_meta_plugin.reels.time.sleep"),
        ):
            result = get_permalink(media_id="m-1", access_token="tok")

        assert result == "https://www.instagram.com/reel/abc/"

    def test_empty_permalink_all_retries_exhausted(self) -> None:
        with (
            patch(
                "reeln_meta_plugin.reels.http_get",
                return_value={"permalink": ""},
            ),
            patch("reeln_meta_plugin.reels.time.sleep"),
            pytest.raises(ReelsError, match="Failed to get permalink after 2 retries"),
        ):
            get_permalink(
                media_id="m-1",
                access_token="tok",
                max_retries=2,
            )

    def test_custom_api_version(self) -> None:
        with patch(
            "reeln_meta_plugin.reels.http_get",
            return_value={"permalink": "https://ig.com/reel/x/"},
        ) as mock_get:
            get_permalink(
                media_id="m-1",
                access_token="tok",
                api_version="v23.0",
            )

        url = mock_get.call_args[0][0]
        assert "v23.0" in url

    def test_no_sleep_after_last_retry(self) -> None:
        with (
            patch(
                "reeln_meta_plugin.reels.http_get",
                side_effect=GraphAPIError("fail"),
            ),
            patch("reeln_meta_plugin.reels.time.sleep") as mock_sleep,
            pytest.raises(ReelsError),
        ):
            get_permalink(
                media_id="m-1",
                access_token="tok",
                max_retries=3,
            )

        assert mock_sleep.call_count == 2
