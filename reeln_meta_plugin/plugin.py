"""MetaPlugin — reeln-cli plugin for Meta platform integration."""

from __future__ import annotations

import logging
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
    version: str = "0.5.0"
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
                default="EVERYONE",
                description="Privacy setting (EVERYONE or SELF)",
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
                name="save_vod",
                field_type="bool",
                default=True,
                description="Save a VOD recording after broadcast ends",
            ),
            ConfigField(
                name="published",
                field_type="bool",
                default=True,
                description="Publish VOD to Page timeline after broadcast ends",
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

        if self._config.get("dry_run"):
            log.info(
                "Meta plugin: [DRY RUN] would create livestream — title=%r, page_id=%s",
                title,
                page_id,
            )
            return

        try:
            result = livestream.create_livestream(
                page_id=page_id,
                access_token=access_token,
                title=title,
                description=description,
                api_version=self._config.get("graph_api_version", "v24.0"),
                status=self._config.get("status", "LIVE_NOW"),
                privacy=self._config.get("privacy", "EVERYONE"),
                content_category=self._config.get("content_category", "SPORTS"),
                game_id=self._config.get("game_id", ""),
                save_vod=self._config.get("save_vod", True),
                published=self._config.get("published", True),
                stop_on_delete_stream=self._config.get("stop_on_delete_stream", False),
            )
        except livestream.LivestreamError as exc:
            log.warning("Meta plugin: livestream creation failed: %s", exc)
            return

        self._livestream_id = result.id
        context.shared["livestreams"] = context.shared.get("livestreams", {})
        context.shared["livestreams"]["meta"] = result.embed_url
        log.info("Meta plugin: created livestream %s", result.embed_url)

    def on_game_ready(self, context: HookContext) -> None:
        """Handle ``ON_GAME_READY`` — update livestream with enriched metadata."""
        if self._livestream_id is None:
            return

        metadata = context.shared.get("livestream_metadata")
        if not metadata:
            return

        access_token = self._ensure_auth()
        if access_token is None:
            return

        title = metadata.get("title", "")
        description = metadata.get("description", "")

        if not title and not description:
            return

        if self._config.get("dry_run"):
            log.info(
                "Meta plugin: [DRY RUN] would update livestream %s — title=%r",
                self._livestream_id,
                title,
            )
            return

        try:
            livestream.update_livestream(
                live_video_id=self._livestream_id,
                access_token=access_token,
                title=title,
                description=description,
                api_version=self._config.get("graph_api_version", "v24.0"),
            )
        except livestream.LivestreamError as exc:
            log.warning(
                "Meta plugin: livestream update failed (non-fatal): %s", exc
            )
            return

        log.info("Meta plugin: updated livestream %s metadata", self._livestream_id)

    def on_game_finish(self, context: HookContext) -> None:
        """Handle ``ON_GAME_FINISH`` — reset cached state."""
        self._access_token = None
        self._game_info = None
        self._livestream_id = None

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
