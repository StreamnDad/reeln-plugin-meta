"""MetaPlugin — reeln-cli plugin for Meta platform integration."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from reeln.models.plugin_schema import ConfigField, PluginConfigSchema
from reeln.plugins.hooks import Hook, HookContext
from reeln.plugins.registry import HookRegistry

from reeln_meta_plugin import auth, livestream

log: logging.Logger = logging.getLogger(__name__)


class MetaPlugin:
    """Plugin that provides Meta platform integration for reeln-cli.

    Subscribes to lifecycle hooks to create Facebook Live Videos and
    writes the livestream URL to ``context.shared["livestreams"]["meta"]``.
    """

    name: str = "meta"
    version: str = "0.7.0"
    api_version: int = 1

    config_schema: PluginConfigSchema = PluginConfigSchema(
        fields=(
            ConfigField(
                name="page_access_token_file",
                field_type="str",
                required=True,
                description="Path to Facebook Page access token file",
            ),
            ConfigField(
                name="page_id",
                field_type="str",
                required=True,
                description="Facebook Page ID",
            ),
            ConfigField(
                name="create_livestream",
                field_type="bool",
                default=False,
                description="Enable Facebook Live Video creation on ON_GAME_INIT",
            ),
            ConfigField(
                name="dry_run",
                field_type="bool",
                default=False,
                description="Log API calls without executing them",
            ),
            ConfigField(
                name="graph_api_version",
                field_type="str",
                default="v24.0",
                description="Graph API version",
            ),
            ConfigField(
                name="status",
                field_type="str",
                default="LIVE_NOW",
                description="Broadcast status (LIVE_NOW or UNPUBLISHED)",
            ),
            ConfigField(
                name="privacy",
                field_type="str",
                default="",
                description="Privacy setting (omit for Pages, or EVERYONE/SELF for User tokens)",
            ),
            ConfigField(
                name="content_category",
                field_type="str",
                default="SPORTS",
                description="Content category (SPORTS, VIDEO_GAMING, ENTERTAINMENT, etc.)",
            ),
            ConfigField(
                name="game_id",
                field_type="str",
                default="",
                description="Facebook game ID to tag the broadcast with",
            ),
            ConfigField(
                name="stop_on_delete_stream",
                field_type="bool",
                default=False,
                description="Auto-end broadcast when RTMP stream disconnects",
            ),
        )
    )

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self._config: dict[str, Any] = config or {}
        self._access_token: str | None = None
        self._game_info: object | None = None
        self._livestream_id: str | None = None

    def register(self, registry: HookRegistry) -> None:
        """Register hook handlers with the reeln plugin registry."""
        registry.register(Hook.ON_GAME_INIT, self.on_game_init)
        registry.register(Hook.ON_GAME_READY, self.on_game_ready)
        registry.register(Hook.ON_GAME_FINISH, self.on_game_finish)

    def _ensure_auth(self) -> str | None:
        """Return cached access token, or read from file and cache.

        Returns:
            The access token string, or ``None`` on auth failure or missing config.
        """
        if self._access_token is not None:
            return self._access_token

        token_file_str = self._config.get("page_access_token_file")
        if not token_file_str:
            log.warning(
                "Meta plugin: page_access_token_file not configured, skipping"
            )
            return None

        token_path = Path(token_file_str)

        try:
            self._access_token = auth.read_token(token_path)
        except auth.AuthError as exc:
            log.warning("Meta plugin: authentication failed: %s", exc)
            return None

        return self._access_token

    def on_game_init(self, context: HookContext) -> None:
        """Handle ``ON_GAME_INIT`` — create a Facebook Live Video."""
        if not self._config.get("create_livestream"):
            return

        game_info = context.data.get("game_info")
        if game_info is None:
            log.warning("Meta plugin: no game_info in context, skipping")
            return

        self._game_info = game_info

        access_token = self._ensure_auth()
        if access_token is None:
            return

        page_id = self._config.get("page_id")
        if not page_id:
            log.warning("Meta plugin: page_id not configured, skipping")
            return

        title = self._build_title(game_info)
        description = getattr(game_info, "description", "")
        status = self._config.get("status", "LIVE_NOW")

        event_params = ""
        if status == "SCHEDULED_UNPUBLISHED":
            event_params = self._compute_event_params(game_info)
            if not event_params:
                log.warning(
                    "Meta plugin: SCHEDULED_UNPUBLISHED requires game_time, "
                    "falling back to LIVE_NOW"
                )
                status = "LIVE_NOW"

        if self._config.get("dry_run"):
            log.info(
                "Meta plugin: [DRY RUN] would create livestream — "
                "title=%r, page_id=%s, status=%s",
                title,
                page_id,
                status,
            )
            return

        try:
            result = livestream.create_livestream(
                page_id=page_id,
                access_token=access_token,
                title=title,
                description=description,
                api_version=self._config.get("graph_api_version", "v24.0"),
                status=status,
                privacy=self._config.get("privacy", ""),
                content_category=self._config.get("content_category", "SPORTS"),
                game_id=self._config.get("game_id", ""),
                stop_on_delete_stream=self._config.get("stop_on_delete_stream", False),
                event_params=event_params,
            )
        except livestream.LivestreamError as exc:
            log.warning("Meta plugin: livestream creation failed: %s", exc)
            return

        self._livestream_id = result.id
        context.shared["livestreams"] = context.shared.get("livestreams", {})
        context.shared["livestreams"]["meta"] = result.embed_url
        log.info(
            "Meta plugin: created livestream id=%s embed=%s stream_url=%s",
            result.id,
            result.embed_url,
            result.stream_url,
        )

    def on_game_ready(self, context: HookContext) -> None:
        """Handle ``ON_GAME_READY`` — update livestream with enriched metadata and thumbnail."""
        if self._livestream_id is None:
            return

        metadata = context.shared.get("livestream_metadata") or {}
        title = metadata.get("title", "")
        description = metadata.get("description", "")

        game_image = context.shared.get("game_image", {})
        image_path_str = (
            game_image.get("image_path", "") if isinstance(game_image, dict) else ""
        )
        thumbnail_path = Path(image_path_str) if image_path_str else None

        has_metadata = bool(title or description)
        has_thumbnail = thumbnail_path is not None and thumbnail_path.exists()

        if not has_metadata and not has_thumbnail:
            return

        access_token = self._ensure_auth()
        if access_token is None:
            return

        api_version = self._config.get("graph_api_version", "v24.0")

        if self._config.get("dry_run"):
            log.info(
                "Meta plugin: [DRY RUN] would update livestream %s — title=%r, thumbnail=%s",
                self._livestream_id,
                title,
                thumbnail_path,
            )
            return

        if has_metadata:
            try:
                livestream.update_livestream(
                    live_video_id=self._livestream_id,
                    access_token=access_token,
                    title=title,
                    description=description,
                    api_version=api_version,
                )
            except livestream.LivestreamError as exc:
                log.warning(
                    "Meta plugin: livestream update failed (non-fatal): %s", exc
                )

        if has_thumbnail and thumbnail_path is not None:
            try:
                livestream.upload_thumbnail(
                    live_video_id=self._livestream_id,
                    access_token=access_token,
                    image_path=thumbnail_path,
                    api_version=api_version,
                )
            except livestream.LivestreamError as exc:
                log.warning(
                    "Meta plugin: thumbnail upload failed (non-fatal): %s", exc
                )

        log.info("Meta plugin: updated livestream %s", self._livestream_id)

    def on_game_finish(self, context: HookContext) -> None:
        """Handle ``ON_GAME_FINISH`` — reset cached state."""
        self._access_token = None
        self._game_info = None
        self._livestream_id = None

    @staticmethod
    def _compute_event_params(game_info: object) -> str:
        """Compute a Unix timestamp from game_info date and game_time.

        Returns:
            Unix timestamp as a string, or empty string if game_time is missing
            or cannot be parsed.
        """
        date_str = getattr(game_info, "date", "")
        game_time_str = getattr(game_info, "game_time", "")

        if not date_str or not game_time_str:
            return ""

        # Strip trailing timezone abbreviations (e.g. "8:15PM CDT" → "8:15PM")
        time_clean = game_time_str.strip()
        parts = time_clean.rsplit(maxsplit=1)
        if len(parts) == 2 and parts[1].isalpha():
            time_clean = parts[0]

        time_formats = ["%I:%M %p", "%I:%M%p", "%H:%M"]
        parsed_time = None
        for fmt in time_formats:
            try:
                parsed_time = datetime.strptime(time_clean.strip(), fmt)
                break
            except ValueError:
                continue

        if parsed_time is None:
            return ""

        try:
            game_date = datetime.strptime(date_str.strip(), "%Y-%m-%d")
        except ValueError:
            return ""

        local_dt = game_date.replace(
            hour=parsed_time.hour, minute=parsed_time.minute
        )
        # naive datetime → .timestamp() assumes local timezone
        timestamp = int(local_dt.timestamp())
        return str(timestamp)

    def _build_title(self, game_info: object) -> str:
        """Build a livestream title from game info."""
        home_team = getattr(game_info, "home_team", "")
        away_team = getattr(game_info, "away_team", "")
        date = getattr(game_info, "date", "")
        venue = getattr(game_info, "venue", "")

        title = f"{home_team} vs {away_team} - {date}"
        if venue:
            title += f" @ {venue}"
        return title
