"""Instagram Reels publishing via the Graph API."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from reeln_meta_plugin.graph_api import GraphAPIError, http_get, http_post

log: logging.Logger = logging.getLogger(__name__)


class ReelsError(GraphAPIError):
    """Raised when a Reels operation fails."""


@dataclass(frozen=True)
class ReelContainerResult:
    """Result of creating a Reel media container."""

    container_id: str


@dataclass(frozen=True)
class ReelPublishResult:
    """Result of publishing a Reel."""

    media_id: str
    permalink: str


def create_reel_container(
    *,
    ig_user_id: str,
    access_token: str,
    video_url: str,
    caption: str = "",
    share_to_feed: bool = True,
    thumb_offset: int = 0,
    api_version: str = "v24.0",
) -> ReelContainerResult:
    """Create an Instagram Reel media container.

    Args:
        ig_user_id: Instagram Business/Creator account ID.
        access_token: Page Access Token.
        video_url: Publicly accessible URL of the video.
        caption: Reel caption text.
        share_to_feed: Whether to also share to the Instagram feed.
        thumb_offset: Thumbnail offset in milliseconds from video start.
        api_version: Graph API version.

    Returns:
        A ``ReelContainerResult`` with the container ID.

    Raises:
        ReelsError: If the API call fails or returns unexpected data.
    """
    url = f"https://graph.facebook.com/{api_version}/{ig_user_id}/media"
    payload: dict[str, str] = {
        "media_type": "REELS",
        "video_url": video_url,
        "caption": caption,
        "share_to_feed": str(share_to_feed).lower(),
        "thumb_offset": str(thumb_offset),
        "access_token": access_token,
    }

    try:
        data = http_post(url, payload)
    except GraphAPIError as exc:
        raise ReelsError(str(exc)) from exc

    container_id = data.get("id")
    if not container_id:
        raise ReelsError(f"Unexpected API response — missing id: {data}")

    return ReelContainerResult(container_id=container_id)


def poll_container_status(
    *,
    container_id: str,
    access_token: str,
    api_version: str = "v24.0",
    max_attempts: int = 60,
    poll_interval: float = 5.0,
) -> str:
    """Poll an Instagram media container until processing completes.

    Args:
        container_id: The media container ID to poll.
        access_token: Page Access Token.
        api_version: Graph API version.
        max_attempts: Maximum number of poll attempts.
        poll_interval: Seconds between poll attempts.

    Returns:
        The final status code (``FINISHED``).

    Raises:
        ReelsError: If the container errors, expires, or polling times out.
    """
    url = f"https://graph.facebook.com/{api_version}/{container_id}"
    params = {"fields": "status_code", "access_token": access_token}

    for attempt in range(max_attempts):
        try:
            data = http_get(url, params)
        except GraphAPIError as exc:
            raise ReelsError(str(exc)) from exc

        status: str = data.get("status_code", "")

        if status == "FINISHED":
            return "FINISHED"

        if status in ("ERROR", "EXPIRED"):
            raise ReelsError(
                f"Container {container_id} failed with status: {status}"
            )

        if attempt < max_attempts - 1:
            time.sleep(poll_interval)

    raise ReelsError(
        f"Container {container_id} not ready after {max_attempts} attempts"
    )


def publish_reel(
    *,
    ig_user_id: str,
    access_token: str,
    container_id: str,
    api_version: str = "v24.0",
) -> str:
    """Publish a processed Reel container.

    Args:
        ig_user_id: Instagram Business/Creator account ID.
        access_token: Page Access Token.
        container_id: The processed media container ID.
        api_version: Graph API version.

    Returns:
        The published media ID.

    Raises:
        ReelsError: If the API call fails or returns unexpected data.
    """
    url = f"https://graph.facebook.com/{api_version}/{ig_user_id}/media_publish"
    payload: dict[str, str] = {
        "creation_id": container_id,
        "access_token": access_token,
    }

    try:
        data = http_post(url, payload)
    except GraphAPIError as exc:
        raise ReelsError(str(exc)) from exc

    media_id: str | None = data.get("id")
    if not media_id:
        raise ReelsError(f"Unexpected API response — missing id: {data}")

    return media_id


def get_permalink(
    *,
    media_id: str,
    access_token: str,
    api_version: str = "v24.0",
    max_retries: int = 3,
    retry_delay: float = 2.0,
) -> str:
    """Retrieve the permalink for a published Instagram media.

    Args:
        media_id: The published media ID.
        access_token: Page Access Token.
        api_version: Graph API version.
        max_retries: Maximum number of retry attempts.
        retry_delay: Seconds between retries.

    Returns:
        The permalink URL string.

    Raises:
        ReelsError: If all retries are exhausted.
    """
    url = f"https://graph.facebook.com/{api_version}/{media_id}"
    params = {"fields": "permalink", "access_token": access_token}

    last_error: Exception | None = None
    for attempt in range(max_retries):
        try:
            data = http_get(url, params)
            permalink: str = data.get("permalink", "")
            if permalink:
                return permalink
            raise ReelsError(f"Empty permalink in response: {data}")
        except GraphAPIError as exc:
            last_error = exc
            if attempt < max_retries - 1:
                time.sleep(retry_delay)

    raise ReelsError(
        f"Failed to get permalink after {max_retries} retries"
    ) from last_error
