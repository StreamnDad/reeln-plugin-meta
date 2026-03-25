"""Tests for comments module."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from reeln_meta_plugin.comments import CommentError, CommentResult, post_comment
from reeln_meta_plugin.graph_api import GraphAPIError


class TestCommentErrorInheritance:
    def test_subclasses_graph_api_error(self) -> None:
        assert issubclass(CommentError, GraphAPIError)


class TestCommentResult:
    def test_frozen(self) -> None:
        result = CommentResult(comment_id="cmt-1")
        with pytest.raises(AttributeError):
            result.comment_id = "cmt-2"  # type: ignore[misc]


class TestPostComment:
    def test_success(self) -> None:
        response = {"id": "cmt-123"}
        with patch("reeln_meta_plugin.comments.http_post", return_value=response):
            result = post_comment(
                media_id="m-1",
                access_token="tok",
                message="Great game!",
            )

        assert result.comment_id == "cmt-123"

    def test_payload_and_url(self) -> None:
        response = {"id": "cmt-1"}
        with patch("reeln_meta_plugin.comments.http_post", return_value=response) as mock_post:
            post_comment(
                media_id="m-1",
                access_token="tok",
                message="Nice!",
                api_version="v23.0",
            )

        url, payload = mock_post.call_args[0]
        assert "v23.0" in url
        assert "m-1/comments" in url
        assert payload["message"] == "Nice!"
        assert payload["access_token"] == "tok"

    def test_default_api_version(self) -> None:
        response = {"id": "cmt-1"}
        with patch("reeln_meta_plugin.comments.http_post", return_value=response) as mock_post:
            post_comment(
                media_id="m-1",
                access_token="tok",
                message="Hi",
            )

        url, _ = mock_post.call_args[0]
        assert "v24.0" in url

    def test_missing_id_raises(self) -> None:
        response = {"status": "ok"}
        with (
            patch("reeln_meta_plugin.comments.http_post", return_value=response),
            pytest.raises(CommentError, match="missing id"),
        ):
            post_comment(media_id="m-1", access_token="tok", message="Hi")

    def test_graph_api_error_wrapped(self) -> None:
        with (
            patch(
                "reeln_meta_plugin.comments.http_post",
                side_effect=GraphAPIError("HTTP 400: bad request"),
            ),
            pytest.raises(CommentError, match="HTTP 400"),
        ):
            post_comment(media_id="m-1", access_token="tok", message="Hi")
