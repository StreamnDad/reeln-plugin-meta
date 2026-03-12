"""Facebook Live Video creation via the Graph API."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from reeln_meta_plugin.graph_api import GraphAPIError, http_post

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
    privacy: str = "EVERYONE",
    content_category: str = "SPORTS",
    game_id: str = "",
    save_vod: bool = True,
    published: bool = True,
    stop_on_delete_stream: bool = False,
) -> LivestreamResult:
    """Create a Facebook Live Video on a Page.

    Args:
        page_id: Facebook Page ID.
        access_token: Page Access Token.
        title: Live video title.
        description: Live video description.
        api_version: Graph API version.
        status: Broadcast status (``LIVE_NOW`` or ``UNPUBLISHED``).
        privacy: Privacy setting (``EVERYONE`` or ``SELF``).
        content_category: Content category (e.g. ``SPORTS``, ``VIDEO_GAMING``).
        game_id: Facebook game ID to tag the broadcast with.
        save_vod: Whether to save a VOD recording after broadcast ends.
        published: Whether the VOD publishes to the Page timeline.
        stop_on_delete_stream: Auto-end broadcast when RTMP disconnects.

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
        "privacy": json.dumps({"value": privacy}),
        "content_category": content_category,
        "save_vod": json.dumps(save_vod),
        "published": json.dumps(published),
        "stop_on_delete_stream": json.dumps(stop_on_delete_stream),
    }

    if game_id:
        payload["game_id"] = game_id

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
