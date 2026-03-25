"""Instagram comments via the Graph API."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from reeln_meta_plugin.graph_api import GraphAPIError, http_post

log: logging.Logger = logging.getLogger(__name__)


class CommentError(GraphAPIError):
    """Raised when a comment operation fails."""


@dataclass(frozen=True)
class CommentResult:
    """Result of posting a comment."""

    comment_id: str


def post_comment(
    *,
    media_id: str,
    access_token: str,
    message: str,
    api_version: str = "v24.0",
) -> CommentResult:
    """Post a comment on a published Instagram media.

    Args:
        media_id: The published media ID.
        access_token: Page Access Token.
        message: Comment text.
        api_version: Graph API version.

    Returns:
        A ``CommentResult`` with the comment ID.

    Raises:
        CommentError: If the API call fails or returns unexpected data.
    """
    url = f"https://graph.facebook.com/{api_version}/{media_id}/comments"
    payload: dict[str, str] = {
        "message": message,
        "access_token": access_token,
    }

    try:
        data = http_post(url, payload)
    except GraphAPIError as exc:
        raise CommentError(str(exc)) from exc

    comment_id = data.get("id")
    if not comment_id:
        raise CommentError(f"Unexpected API response — missing id: {data}")

    return CommentResult(comment_id=comment_id)
