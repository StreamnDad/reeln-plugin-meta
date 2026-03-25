"""Facebook Page Reels publishing via the Graph API.

Four-step upload flow:
1. **Start** — ``POST /{page_id}/video_reels?upload_phase=start``
2. **Upload** — ``POST rupload.facebook.com`` with ``file_url`` header
3. **Finish** — ``POST /{page_id}/video_reels?upload_phase=finish`` (triggers processing)
4. **Poll** — ``GET /{video_id}?fields=status`` until processing completes
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from reeln_meta_plugin.graph_api import (
    GraphAPIError,
    http_get,
    http_post,
    http_post_rupload,
)

log: logging.Logger = logging.getLogger(__name__)


class FacebookReelsError(GraphAPIError):
    """Raised when a Facebook Reels operation fails."""


@dataclass(frozen=True)
class ReelStartResult:
    """Result of starting a Facebook Reel upload session."""

    video_id: str
    upload_url: str


def start_reel_upload(
    *,
    page_id: str,
    access_token: str,
    api_version: str = "v24.0",
) -> ReelStartResult:
    """Start a Facebook Reel upload session.

    Args:
        page_id: Facebook Page ID.
        access_token: Page Access Token.
        api_version: Graph API version.

    Returns:
        A ``ReelStartResult`` with the video ID and upload URL.

    Raises:
        FacebookReelsError: If the API call fails or returns unexpected data.
    """
    url = f"https://graph.facebook.com/{api_version}/{page_id}/video_reels"
    payload: dict[str, str] = {
        "upload_phase": "start",
        "access_token": access_token,
    }

    try:
        data = http_post(url, payload)
    except GraphAPIError as exc:
        raise FacebookReelsError(str(exc)) from exc

    video_id = data.get("video_id")
    if not video_id:
        raise FacebookReelsError(f"Unexpected API response — missing video_id: {data}")

    upload_url = data.get("upload_url", "")
    if not upload_url:
        raise FacebookReelsError(f"Unexpected API response — missing upload_url: {data}")

    return ReelStartResult(video_id=video_id, upload_url=upload_url)


def upload_reel_video(
    *,
    upload_url: str,
    access_token: str,
    video_url: str,
) -> None:
    """Upload a video to Facebook via the rupload endpoint.

    Uses the ``file_url`` header to have Meta's servers fetch the video
    from a CDN URL (e.g. Cloudflare R2).

    Args:
        upload_url: The rupload URL from the start phase.
        access_token: Page Access Token.
        video_url: Public CDN URL for the video file.

    Raises:
        FacebookReelsError: If the upload fails.
    """
    try:
        data = http_post_rupload(upload_url, access_token, file_url=video_url)
    except GraphAPIError as exc:
        raise FacebookReelsError(str(exc)) from exc

    if not data.get("success"):
        raise FacebookReelsError(f"Upload failed — unexpected response: {data}")


def poll_reel_status(
    *,
    video_id: str,
    access_token: str,
    api_version: str = "v24.0",
    max_attempts: int = 60,
    poll_interval: float = 5.0,
) -> str:
    """Poll a Facebook video until processing completes.

    Args:
        video_id: The video ID from the start phase.
        access_token: Page Access Token.
        api_version: Graph API version.
        max_attempts: Maximum number of poll attempts.
        poll_interval: Seconds between poll attempts.

    Returns:
        The final processing phase status (``complete``).

    Raises:
        FacebookReelsError: If processing fails or polling times out.
    """
    url = f"https://graph.facebook.com/{api_version}/{video_id}"
    params = {"fields": "status", "access_token": access_token}

    for attempt in range(max_attempts):
        try:
            data = http_get(url, params)
        except GraphAPIError as exc:
            raise FacebookReelsError(str(exc)) from exc

        status = data.get("status", {})
        if not isinstance(status, dict):
            raise FacebookReelsError(f"Unexpected status format: {data}")

        processing = status.get("processing_phase", {})
        processing_status = processing.get("status", "")
        video_status = status.get("video_status", "")
        uploading = status.get("uploading_phase", {})

        log.info(
            "Facebook Reel poll %d/%d: video_status=%s, processing=%s, uploading=%s",
            attempt + 1,
            max_attempts,
            video_status,
            processing_status,
            uploading.get("status", "") if isinstance(uploading, dict) else uploading,
        )

        if processing_status == "complete":
            return "complete"

        if processing_status == "error":
            errors = processing.get("errors", [])
            raise FacebookReelsError(
                f"Video {video_id} processing failed: {errors}"
            )

        if video_status == "error":
            raise FacebookReelsError(
                f"Video {video_id} failed with video_status=error"
            )

        if attempt < max_attempts - 1:
            time.sleep(poll_interval)

    raise FacebookReelsError(
        f"Video {video_id} not ready after {max_attempts} attempts"
    )


def finish_reel(
    *,
    page_id: str,
    access_token: str,
    video_id: str,
    title: str = "",
    description: str = "",
    video_state: str = "PUBLISHED",
    api_version: str = "v24.0",
) -> None:
    """Publish (finish) a Facebook Reel.

    Args:
        page_id: Facebook Page ID.
        access_token: Page Access Token.
        video_id: The video ID from the start phase.
        title: Reel title.
        description: Reel description/caption.
        video_state: ``PUBLISHED``, ``DRAFT``, or ``SCHEDULED``.
        api_version: Graph API version.

    Raises:
        FacebookReelsError: If the publish call fails.
    """
    url = f"https://graph.facebook.com/{api_version}/{page_id}/video_reels"
    payload: dict[str, str] = {
        "upload_phase": "finish",
        "video_id": video_id,
        "video_state": video_state,
        "access_token": access_token,
    }

    if title:
        payload["title"] = title
    if description:
        payload["description"] = description

    try:
        data = http_post(url, payload)
    except GraphAPIError as exc:
        raise FacebookReelsError(str(exc)) from exc

    if not data.get("success"):
        raise FacebookReelsError(f"Publish failed — unexpected response: {data}")
