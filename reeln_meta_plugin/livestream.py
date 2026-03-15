"""Facebook Live Video creation via the Graph API."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from reeln_meta_plugin.graph_api import GraphAPIError, http_post, http_post_multipart

log: logging.Logger = logging.getLogger(__name__)


class LivestreamError(GraphAPIError):
    """Raised when a livestream operation fails."""


@dataclass(frozen=True)
class LivestreamResult:
    """Result of creating a Facebook Live Video."""

    id: str
    stream_url: str
    embed_url: str


def create_livestream(
    *,
    page_id: str,
    access_token: str,
    title: str,
    description: str = "",
    api_version: str = "v24.0",
    status: str = "LIVE_NOW",
    privacy: str = "",
    content_category: str = "SPORTS",
    game_id: str = "",
    stop_on_delete_stream: bool = False,
    event_params: str = "",
) -> LivestreamResult:
    """Create a Facebook Live Video on a Page.

    Args:
        page_id: Facebook Page ID.
        access_token: Page Access Token.
        title: Live video title.
        description: Live video description.
        api_version: Graph API version.
        status: Broadcast status (``LIVE_NOW``, ``UNPUBLISHED``, or
            ``SCHEDULED_UNPUBLISHED``).
        privacy: Privacy setting (omit for Pages, or ``EVERYONE``/``SELF``
            for User tokens).
        content_category: Content category (e.g. ``SPORTS``, ``VIDEO_GAMING``).
        game_id: Facebook game ID to tag the broadcast with.
        stop_on_delete_stream: Auto-end broadcast when RTMP disconnects.
        event_params: Unix timestamp for scheduled start time. Required when
            status is ``SCHEDULED_UNPUBLISHED``.

    Returns:
        A ``LivestreamResult`` with the live video ID, stream URL, and embed URL.

    Raises:
        LivestreamError: If the API call fails or returns unexpected data.
    """
    url = f"https://graph.facebook.com/{api_version}/{page_id}/live_videos"
    payload: dict[str, str] = {
        "title": title,
        "description": description,
        "access_token": access_token,
        "status": status,
        "content_category": content_category,
        "stop_on_delete_stream": json.dumps(stop_on_delete_stream),
    }

    if privacy:
        payload["privacy"] = json.dumps({"value": privacy})
    if game_id:
        payload["game_id"] = game_id
    if event_params:
        payload["event_params"] = event_params

    try:
        data = http_post(url, payload)
    except GraphAPIError as exc:
        raise LivestreamError(str(exc)) from exc

    live_id = data.get("id")
    stream_url = data.get("stream_url") or data.get("secure_stream_url")
    if not live_id or not stream_url:
        raise LivestreamError(
            f"Unexpected API response — missing id or stream_url: {data}"
        )

    embed_url = f"https://www.facebook.com/{page_id}/videos/{live_id}"
    return LivestreamResult(id=live_id, stream_url=stream_url, embed_url=embed_url)


def update_livestream(
    *,
    live_video_id: str,
    access_token: str,
    title: str = "",
    description: str = "",
    api_version: str = "v24.0",
) -> None:
    """Update metadata on an existing Facebook Live Video.

    Args:
        live_video_id: The live video ID to update.
        access_token: Page Access Token.
        title: New title (skipped if empty).
        description: New description (skipped if empty).
        api_version: Graph API version.

    Raises:
        LivestreamError: If the API call fails.
    """
    url = f"https://graph.facebook.com/{api_version}/{live_video_id}"
    payload: dict[str, str] = {"access_token": access_token}

    if title:
        payload["title"] = title
    if description:
        payload["description"] = description

    if len(payload) == 1:
        return

    try:
        http_post(url, payload)
    except GraphAPIError as exc:
        raise LivestreamError(str(exc)) from exc


def upload_thumbnail(
    *,
    live_video_id: str,
    access_token: str,
    image_path: Path,
    api_version: str = "v24.0",
) -> None:
    """Upload a custom thumbnail to a Facebook Live Video.

    Args:
        live_video_id: The live video ID to update.
        access_token: Page Access Token.
        image_path: Path to the thumbnail image file.
        api_version: Graph API version.

    Raises:
        LivestreamError: If the upload fails.
    """
    url = f"https://graph.facebook.com/{api_version}/{live_video_id}"

    try:
        http_post_multipart(
            url,
            fields={"access_token": access_token},
            files={"custom_image": image_path},
        )
    except GraphAPIError as exc:
        raise LivestreamError(str(exc)) from exc
