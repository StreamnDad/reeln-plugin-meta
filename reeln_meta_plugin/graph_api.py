"""Low-level HTTP helpers for the Meta Graph API."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
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
