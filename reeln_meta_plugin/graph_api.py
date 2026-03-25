"""Low-level HTTP helpers for the Meta Graph API."""

from __future__ import annotations

import json
import logging
import mimetypes
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any

log: logging.Logger = logging.getLogger(__name__)


class GraphAPIError(Exception):
    """Base exception for Graph API errors."""


def http_post(url: str, payload: dict[str, str]) -> dict[str, Any]:
    """Send a form-encoded POST and return parsed JSON.

    Args:
        url: API endpoint URL.
        payload: Form data.

    Returns:
        Parsed JSON response dict.

    Raises:
        GraphAPIError: On HTTP or parsing errors.
    """
    encoded = urllib.parse.urlencode(payload).encode()
    request = urllib.request.Request(url, data=encoded, method="POST")

    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read().decode()
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode() if exc.fp else ""
        detail = format_meta_error(error_body)
        raise GraphAPIError(f"HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise GraphAPIError(f"Request failed: {exc.reason}") from exc

    try:
        return json.loads(body)  # type: ignore[no-any-return]
    except json.JSONDecodeError as exc:
        raise GraphAPIError(f"Invalid JSON response: {body[:200]}") from exc


def http_post_multipart(
    url: str,
    fields: dict[str, str],
    files: dict[str, Path],
) -> dict[str, Any]:
    """Send a multipart/form-data POST and return parsed JSON.

    Args:
        url: API endpoint URL.
        fields: Text form fields (e.g. ``{"access_token": "tok"}``).
        files: File fields mapping field name to file path.

    Returns:
        Parsed JSON response dict.

    Raises:
        GraphAPIError: On HTTP or parsing errors.
    """
    boundary = uuid.uuid4().hex
    parts: list[bytes] = []

    for name, value in fields.items():
        parts.append(
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
            f"{value}\r\n".encode()
        )

    for name, path in files.items():
        content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        file_data = path.read_bytes()
        header = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{name}"; filename="{path.name}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
        ).encode()
        parts.append(header + file_data + b"\r\n")

    parts.append(f"--{boundary}--\r\n".encode())
    body = b"".join(parts)

    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            response_body = response.read().decode()
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode() if exc.fp else ""
        detail = format_meta_error(error_body)
        raise GraphAPIError(f"HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise GraphAPIError(f"Request failed: {exc.reason}") from exc

    try:
        return json.loads(response_body)  # type: ignore[no-any-return]
    except json.JSONDecodeError as exc:
        raise GraphAPIError(f"Invalid JSON response: {response_body[:200]}") from exc


def http_get(url: str, params: dict[str, str]) -> dict[str, Any]:
    """Send a GET request with query parameters and return parsed JSON.

    Args:
        url: API endpoint URL.
        params: Query string parameters.

    Returns:
        Parsed JSON response dict.

    Raises:
        GraphAPIError: On HTTP or parsing errors.
    """
    query = urllib.parse.urlencode(params)
    full_url = f"{url}?{query}" if query else url
    request = urllib.request.Request(full_url, method="GET")

    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read().decode()
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode() if exc.fp else ""
        detail = format_meta_error(error_body)
        raise GraphAPIError(f"HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise GraphAPIError(f"Request failed: {exc.reason}") from exc

    try:
        return json.loads(body)  # type: ignore[no-any-return]
    except json.JSONDecodeError as exc:
        raise GraphAPIError(f"Invalid JSON response: {body[:200]}") from exc


def http_post_rupload(
    url: str,
    access_token: str,
    *,
    file_url: str = "",
) -> dict[str, Any]:
    """Send a POST to Facebook's rupload endpoint and return parsed JSON.

    The rupload host (``rupload.facebook.com``) uses OAuth header
    authentication and accepts an optional ``file_url`` header to instruct
    Meta's servers to fetch the video from a CDN URL.

    Args:
        url: Full rupload URL (e.g. ``https://rupload.facebook.com/video-upload/v24.0/{video_id}``).
        access_token: Page Access Token.
        file_url: Public CDN URL for the video file.

    Returns:
        Parsed JSON response dict.

    Raises:
        GraphAPIError: On HTTP or parsing errors.
    """
    headers: dict[str, str] = {
        "Authorization": f"OAuth {access_token}",
    }
    if file_url:
        headers["file_url"] = file_url

    request = urllib.request.Request(url, data=b"", headers=headers, method="POST")

    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            body = response.read().decode()
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode() if exc.fp else ""
        detail = format_meta_error(error_body)
        raise GraphAPIError(f"HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise GraphAPIError(f"Request failed: {exc.reason}") from exc

    try:
        return json.loads(body)  # type: ignore[no-any-return]
    except json.JSONDecodeError as exc:
        raise GraphAPIError(f"Invalid JSON response: {body[:200]}") from exc


def format_meta_error(details: str) -> str:
    """Parse a Meta API error response into a user-friendly message.

    Args:
        details: Raw response body string.

    Returns:
        A formatted error message.
    """
    if not details:
        return "(empty response)"

    try:
        data = json.loads(details)
    except json.JSONDecodeError:
        return details[:200]

    if not isinstance(data, dict):
        return details[:200]

    error = data.get("error")
    if isinstance(error, dict):
        msg = error.get("message", "")
        err_type = error.get("type", "")
        code = error.get("code", "")
        return f"{err_type} ({code}): {msg}" if err_type else str(msg)

    return details[:200]
