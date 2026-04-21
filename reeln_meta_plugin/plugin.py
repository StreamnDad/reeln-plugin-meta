"""MetaPlugin — reeln-cli plugin for Meta platform integration."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from reeln.models.auth import AuthCheckResult, AuthStatus
from reeln.models.plugin_schema import ConfigField, PluginConfigSchema
from reeln.plugins.capabilities import UploaderSkipped
from reeln.plugins.hooks import Hook, HookContext
from reeln.plugins.registry import HookRegistry

from reeln_meta_plugin import auth, comments, facebook_reels, livestream, reels

log: logging.Logger = logging.getLogger(__name__)


class MetaPlugin:
    """Plugin that provides Meta platform integration for reeln-cli.

    Subscribes to lifecycle hooks to create Facebook Live Videos and
    writes the livestream URL to ``context.shared["livestreams"]["meta"]``.
    """

    name: str = "meta"
    version: str = "0.11.0"
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
            ConfigField(
                name="instagram_account_id",
                field_type="str",
                default="",
                description="Instagram Business/Creator account ID (IG user ID)",
            ),
            ConfigField(
                name="publish_reels",
                field_type="bool",
                default=False,
                description="Enable Instagram Reel publishing on POST_RENDER",
            ),
            ConfigField(
                name="post_instagram_comment",
                field_type="bool",
                default=False,
                description="Enable posting a comment on published Reels",
            ),
            ConfigField(
                name="reel_caption_template",
                field_type="str",
                default="",
                description="Caption template for Reels ({home_team}, {away_team}, {date}, {venue})",
            ),
            ConfigField(
                name="instagram_comment_template",
                field_type="str",
                default="",
                description="Comment text template ({home_team}, {away_team}, {date}, {venue})",
            ),
            ConfigField(
                name="publish_facebook_reels",
                field_type="bool",
                default=False,
                description="Enable Facebook Page Reel publishing on POST_RENDER",
            ),
            ConfigField(
                name="facebook_reel_description_template",
                field_type="str",
                default="",
                description="Description template for Facebook Reels ({home_team}, {away_team}, {date}, {venue})",
            ),
            ConfigField(
                name="reel_share_to_feed",
                field_type="bool",
                default=True,
                description="Whether to also share the Reel to the Instagram feed",
            ),
            ConfigField(
                name="reel_thumb_offset_ms",
                field_type="int",
                default=0,
                description="Thumbnail offset in milliseconds from video start",
            ),
            ConfigField(
                name="reel_poll_interval_seconds",
                field_type="int",
                default=5,
                description="Seconds between container status polls",
            ),
            ConfigField(
                name="reel_poll_max_attempts",
                field_type="int",
                default=60,
                description="Maximum number of status poll attempts",
            ),
        )
    )

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self._config: dict[str, Any] = config or {}
        self._access_token: str | None = None
        self._game_info: object | None = None
        self._livestream_id: str | None = None
        self._published_reel_id: str | None = None

    def register(self, registry: HookRegistry) -> None:
        """Register hook handlers with the reeln plugin registry."""
        registry.register(Hook.ON_GAME_INIT, self.on_game_init)
        registry.register(Hook.ON_GAME_READY, self.on_game_ready)
        registry.register(Hook.ON_GAME_FINISH, self.on_game_finish)
        registry.register(Hook.POST_RENDER, self.on_post_render)

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
        if context.data.get("regenerate_image_only", False):
            return

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

    def upload(
        self, path: Path, *, metadata: dict[str, Any] | None = None
    ) -> str:
        """Publish Reels to Instagram and/or Facebook from a hosted URL.

        Implements the :class:`reeln.plugins.capabilities.Uploader` protocol
        so the plugin can be used by ``reeln queue publish`` for truthful
        per-target status reporting.

        Meta does **not** upload raw files — the Reels API requires a
        publicly accessible URL. The ``metadata["video_url"]`` key must be
        populated by an upstream file-hosting uploader (typically
        cloudflare, which runs first alphabetically). The ``path``
        argument is accepted to satisfy the protocol but is unused.

        Returns the Instagram permalink when IG publishing is enabled,
        otherwise the Facebook Reel URL when only FB publishing is
        enabled. In dry-run mode, returns a sentinel string without
        hitting the API.

        Raises:
            UploaderSkipped: when all publish flags are disabled, or when
                ``metadata["video_url"]`` is missing (cloudflare uploader
                not enabled or not yet run).
            RuntimeError: when authentication fails or no configured
                target (IG account id, Page id) is available.
            reels.ReelsError / facebook_reels.FacebookReelsError: on
                upstream API failure (propagated for FAILED status).
        """
        del path  # Unused — Meta consumes hosted URLs, not local files.
        meta = metadata or {}

        publish_ig = bool(self._config.get("publish_reels"))
        publish_fb = bool(self._config.get("publish_facebook_reels"))
        post_comment = bool(self._config.get("post_instagram_comment"))

        if not publish_ig and not publish_fb and not post_comment:
            raise UploaderSkipped(
                "no meta publishing flags enabled "
                "(publish_reels / publish_facebook_reels / post_instagram_comment)"
            )

        video_url = str(meta.get("video_url", ""))
        if not video_url and (publish_ig or publish_fb):
            raise UploaderSkipped(
                "Meta Reels require metadata['video_url'] "
                "— enable a file-hosting uploader (e.g. cloudflare) first"
            )

        access_token = self._ensure_auth()
        if access_token is None:
            raise RuntimeError(
                "Meta plugin: authentication failed "
                "(check page_access_token_file)"
            )

        # Hydrate _game_info from metadata when the plugin is freshly
        # instantiated for manual publish (no ON_GAME_INIT run).
        self._hydrate_game_info_from_metadata(meta)

        api_version = self._config.get("graph_api_version", "v24.0")

        # CRITICAL: collect per-sub-operation results and errors instead
        # of raising on the first failure. A late-stage failure must NOT
        # discard a successful earlier publish — otherwise clicking Retry
        # after a partial success creates duplicate posts on every retry
        # (e.g. IG succeeds, FB fails → user retries → another duplicate
        # IG Reel, FB fails again → infinite duplicate-posting loop).
        errors: list[str] = []
        ig_permalink = ""
        fb_page_id = ""
        fb_video_id = ""
        requested_publishes = 0
        succeeded_publishes = 0

        if publish_ig:
            requested_publishes += 1
            ig_user_id = self._config.get("instagram_account_id", "")
            if not ig_user_id:
                errors.append(
                    "IG Reel: instagram_account_id not configured"
                )
            else:
                caption = self._build_caption_from_metadata(meta)
                try:
                    ig_permalink = self._do_ig_reel_publish(
                        ig_user_id=ig_user_id,
                        access_token=access_token,
                        api_version=api_version,
                        video_url=video_url,
                        caption=caption,
                    )
                    succeeded_publishes += 1
                except reels.ReelsError as exc:
                    errors.append(f"IG Reel: {exc}")

        if publish_fb:
            requested_publishes += 1
            fb_page_id = self._config.get("page_id", "")
            if not fb_page_id:
                errors.append("Facebook Reel: page_id not configured")
            else:
                title = self._build_fb_title_from_metadata(meta)
                description = self._build_fb_description_from_metadata(meta)
                try:
                    fb_video_id = self._do_fb_reel_publish(
                        page_id=fb_page_id,
                        access_token=access_token,
                        api_version=api_version,
                        video_url=video_url,
                        title=title,
                        description=description,
                    )
                    succeeded_publishes += 1
                except facebook_reels.FacebookReelsError as exc:
                    errors.append(f"Facebook Reel: {exc}")

        if post_comment and self._published_reel_id:
            message = self._build_comment()
            if message and not self._config.get("dry_run"):
                try:
                    comments.post_comment(
                        media_id=self._published_reel_id,
                        access_token=access_token,
                        message=message,
                        api_version=api_version,
                    )
                except comments.CommentError as exc:
                    # Comment failure is non-fatal — log and continue so
                    # the overall publish still reports PUBLISHED.
                    log.warning(
                        "Meta plugin: comment posting failed (non-fatal): %s",
                        exc,
                    )

        # Decide the overall result:
        # - If nothing was requested, return the dry-run sentinel.
        # - If something was requested and everything that was requested
        #   failed, raise with the collected errors (publish_queue_item
        #   maps to FAILED).
        # - If at least one publish succeeded, return its URL and log
        #   warnings about the partial failures. This is what prevents
        #   the duplicate-posting loop on retry.
        if requested_publishes == 0:
            return (
                "meta:dry_run" if self._config.get("dry_run") else "meta:published"
            )

        if succeeded_publishes == 0:
            raise RuntimeError("; ".join(errors))

        if errors:
            log.warning(
                "Meta plugin: partial publish success — %d/%d targets "
                "published, errors: %s",
                succeeded_publishes,
                requested_publishes,
                "; ".join(errors),
            )

        # Prefer the IG permalink, fall back to the FB video URL.
        if ig_permalink:
            return ig_permalink
        if fb_video_id:
            return f"https://facebook.com/{fb_page_id}/videos/{fb_video_id}"

        # Both publishes reported success but neither returned a URL
        # (dry_run mode or permalink lookup failed) — return the sentinel
        # so publish_queue_item records PUBLISHED without an empty URL.
        return "meta:dry_run" if self._config.get("dry_run") else "meta:published"

    def _hydrate_game_info_from_metadata(
        self, metadata: dict[str, Any]
    ) -> None:
        """Populate ``self._game_info`` from a publish metadata dict.

        The manual publish path instantiates plugins fresh, so
        ``_game_info`` is None and template rendering / fallback titles
        would otherwise produce empty strings. This builds a minimal
        stand-in object with only the attributes templates/titles use.
        """
        if self._game_info is not None:
            return
        if not metadata:
            return

        class _MetaGameInfo:
            def __init__(self, **kwargs: Any) -> None:
                for key, value in kwargs.items():
                    setattr(self, key, value)

        self._game_info = _MetaGameInfo(
            home_team=str(metadata.get("home_team", "")),
            away_team=str(metadata.get("away_team", "")),
            date=str(metadata.get("date", "")),
            sport=str(metadata.get("sport", "")),
            venue="",  # Not in build_publish_metadata; template falls back to "".
            description=str(metadata.get("description", "")),
        )

    def _build_caption_from_metadata(self, metadata: dict[str, Any]) -> str:
        """Caption resolution for the manual publish path.

        Mirrors :meth:`_build_caption` but reads from the metadata dict
        instead of ``context.shared["render_metadata"]``.
        """
        description = str(metadata.get("description", ""))
        if description:
            return description
        template = self._config.get("reel_caption_template", "")
        if template:
            return self._render_template(template)
        if self._game_info is not None:
            return self._build_title(self._game_info)
        return ""

    def _build_fb_title_from_metadata(self, metadata: dict[str, Any]) -> str:
        """Facebook Reel title for the manual publish path."""
        title = str(metadata.get("title", ""))
        if title:
            return title
        if self._game_info is not None:
            return self._build_title(self._game_info)
        return ""

    def _build_fb_description_from_metadata(
        self, metadata: dict[str, Any]
    ) -> str:
        """Facebook Reel description for the manual publish path."""
        description = str(metadata.get("description", ""))
        if description:
            return description
        template = self._config.get("facebook_reel_description_template", "")
        if template:
            return self._render_template(template)
        return ""

    def on_post_render(self, context: HookContext) -> None:
        """Handle ``POST_RENDER`` — publish Reels and/or post comment."""
        publish_ig = self._config.get("publish_reels")
        publish_fb = self._config.get("publish_facebook_reels")
        comment = self._config.get("post_instagram_comment")

        if not publish_ig and not publish_fb and not comment:
            return

        access_token = self._ensure_auth()
        if access_token is None:
            return

        # Cache game_info from hook data if not set (create_livestream may be disabled)
        if self._game_info is None:
            hook_game_info = context.data.get("game_info")
            if hook_game_info is not None:
                self._game_info = hook_game_info

        api_version = self._config.get("graph_api_version", "v24.0")

        if publish_ig:
            ig_user_id = self._config.get("instagram_account_id", "")
            if not ig_user_id:
                log.warning("Meta plugin: instagram_account_id not configured, skipping IG Reel")
            else:
                self._publish_reel(context, ig_user_id, access_token, api_version)

        if publish_fb:
            self._publish_facebook_reel(context, access_token, api_version)

        if comment and self._published_reel_id:
            self._post_comment(access_token, api_version)

    def _publish_reel(
        self,
        context: HookContext,
        ig_user_id: str,
        access_token: str,
        api_version: str,
    ) -> None:
        """Execute the full Reel publishing flow (POST_RENDER wrapper).

        Thin wrapper around :meth:`_do_ig_reel_publish` that reads
        ``video_url`` from ``context.shared``, swallows
        :class:`reels.ReelsError` (a failure must never break the
        render pipeline), and writes the permalink back into
        ``context.shared["reels"]["meta"]`` on success.
        """
        video_url = context.shared.get("video_url", "")
        if not video_url:
            log.warning(
                "Meta plugin: no video_url in shared context, skipping Reel publish"
            )
            return

        caption = self._build_caption(context)

        try:
            permalink = self._do_ig_reel_publish(
                ig_user_id=ig_user_id,
                access_token=access_token,
                api_version=api_version,
                video_url=str(video_url),
                caption=caption,
            )
        except reels.ReelsError as exc:
            log.warning("Meta plugin: Reel publish failed: %s", exc)
            return

        context.shared["reels"] = context.shared.get("reels", {})
        context.shared["reels"]["meta"] = permalink

    def _do_ig_reel_publish(
        self,
        *,
        ig_user_id: str,
        access_token: str,
        api_version: str,
        video_url: str,
        caption: str,
    ) -> str:
        """Publish an Instagram Reel. Returns the permalink on success.

        Dry-run mode logs the intended publish and returns an empty
        string without hitting the API. Any :class:`reels.ReelsError`
        during container creation, polling, or publish is allowed to
        propagate — callers in the manual publish path rely on this
        for ``FAILED`` status reporting, while the
        POST_RENDER wrapper catches and logs them.
        """
        if self._config.get("dry_run"):
            log.info(
                "Meta plugin: [DRY RUN] would publish Reel — "
                "ig_user_id=%s, caption=%r, video_url=%s",
                ig_user_id,
                caption,
                video_url,
            )
            return ""

        container = reels.create_reel_container(
            ig_user_id=ig_user_id,
            access_token=access_token,
            video_url=video_url,
            caption=caption,
            share_to_feed=self._config.get("reel_share_to_feed", True),
            thumb_offset=self._config.get("reel_thumb_offset_ms", 0),
            api_version=api_version,
        )

        reels.poll_container_status(
            container_id=container.container_id,
            access_token=access_token,
            api_version=api_version,
            max_attempts=self._config.get("reel_poll_max_attempts", 60),
            poll_interval=float(
                self._config.get("reel_poll_interval_seconds", 5)
            ),
        )

        media_id = reels.publish_reel(
            ig_user_id=ig_user_id,
            access_token=access_token,
            container_id=container.container_id,
            api_version=api_version,
        )

        self._published_reel_id = media_id

        # Permalink retrieval is non-fatal — log and return empty on failure.
        permalink = ""
        try:
            permalink = reels.get_permalink(
                media_id=media_id,
                access_token=access_token,
                api_version=api_version,
            )
        except reels.ReelsError as exc:
            log.warning(
                "Meta plugin: permalink retrieval failed (non-fatal): %s",
                exc,
            )

        log.info(
            "Meta plugin: published Reel media_id=%s permalink=%s",
            media_id,
            permalink,
        )
        return permalink

    def _post_comment(self, access_token: str, api_version: str) -> None:
        """Post a comment on the last published Reel."""
        message = self._build_comment()
        if not message:
            log.warning("Meta plugin: instagram_comment_template is empty, skipping comment")
            return

        if self._config.get("dry_run"):
            log.info(
                "Meta plugin: [DRY RUN] would post comment — "
                "media_id=%s, message=%r",
                self._published_reel_id,
                message,
            )
            return

        try:
            result = comments.post_comment(
                media_id=self._published_reel_id or "",
                access_token=access_token,
                message=message,
                api_version=api_version,
            )
        except comments.CommentError as exc:
            log.warning("Meta plugin: comment posting failed (non-fatal): %s", exc)
            return

        log.info(
            "Meta plugin: posted comment id=%s on media %s",
            result.comment_id,
            self._published_reel_id,
        )

    def _publish_facebook_reel(
        self,
        context: HookContext,
        access_token: str,
        api_version: str,
    ) -> None:
        """Execute the full Facebook Reel publishing flow (POST_RENDER wrapper).

        Thin wrapper around :meth:`_do_fb_reel_publish` that reads
        ``video_url`` from ``context.shared``, swallows
        :class:`facebook_reels.FacebookReelsError` on any step so a
        publish failure never breaks the render pipeline, and writes
        the published video_id into ``context.shared["facebook_reels"]``.
        """
        video_url = context.shared.get("video_url", "")
        if not video_url:
            log.warning(
                "Meta plugin: no video_url in shared context, skipping Facebook Reel publish"
            )
            return

        page_id = self._config.get("page_id", "")
        if not page_id:
            log.warning("Meta plugin: page_id not configured, skipping Facebook Reel")
            return

        title = self._build_facebook_reel_title(context)
        description = self._build_facebook_reel_description(context)

        try:
            video_id = self._do_fb_reel_publish(
                page_id=page_id,
                access_token=access_token,
                api_version=api_version,
                video_url=str(video_url),
                title=title,
                description=description,
            )
        except facebook_reels.FacebookReelsError as exc:
            log.warning("Meta plugin: Facebook Reel publish failed: %s", exc)
            return

        context.shared["facebook_reels"] = context.shared.get("facebook_reels", {})
        context.shared["facebook_reels"]["meta"] = video_id

    def _do_fb_reel_publish(
        self,
        *,
        page_id: str,
        access_token: str,
        api_version: str,
        video_url: str,
        title: str,
        description: str,
    ) -> str:
        """Publish a Facebook Reel. Returns the video_id on success.

        Dry-run mode logs the intended publish and returns an empty
        string without hitting the API. Errors from any stage
        (start, upload, finish, poll) propagate as
        :class:`facebook_reels.FacebookReelsError` so callers in the
        manual publish path can map them to ``FAILED`` status.
        """
        if self._config.get("dry_run"):
            log.info(
                "Meta plugin: [DRY RUN] would publish Facebook Reel — "
                "page_id=%s, title=%r, video_url=%s",
                page_id,
                title,
                video_url,
            )
            return ""

        start = facebook_reels.start_reel_upload(
            page_id=page_id,
            access_token=access_token,
            api_version=api_version,
        )

        facebook_reels.upload_reel_video(
            upload_url=start.upload_url,
            access_token=access_token,
            video_url=video_url,
        )

        facebook_reels.finish_reel(
            page_id=page_id,
            access_token=access_token,
            video_id=start.video_id,
            title=title,
            description=description,
            api_version=api_version,
        )

        facebook_reels.poll_reel_status(
            video_id=start.video_id,
            access_token=access_token,
            api_version=api_version,
            max_attempts=self._config.get("reel_poll_max_attempts", 60),
            poll_interval=float(
                self._config.get("reel_poll_interval_seconds", 5)
            ),
        )

        log.info(
            "Meta plugin: published Facebook Reel video_id=%s",
            start.video_id,
        )
        return start.video_id

    def _build_facebook_reel_title(self, context: HookContext) -> str:
        """Build a Facebook Reel title from render metadata or game info.

        Resolution order:
        1. ``context.shared["render_metadata"]["title"]`` (AI-generated)
        2. ``_build_title(game_info)`` fallback
        """
        render_meta = context.shared.get("render_metadata", {})
        title = str(render_meta.get("title", ""))
        if title:
            return title
        if self._game_info is not None:
            return self._build_title(self._game_info)
        return ""

    def _build_facebook_reel_description(self, context: HookContext) -> str:
        """Build a Facebook Reel description from render metadata, template, or game info.

        Resolution order:
        1. ``context.shared["render_metadata"]["description"]`` (AI-generated)
        2. ``facebook_reel_description_template`` rendered with game_info
        3. Empty string
        """
        render_meta = context.shared.get("render_metadata", {})
        description = str(render_meta.get("description", ""))
        if description:
            return description
        template = self._config.get("facebook_reel_description_template", "")
        if template:
            return self._render_template(template)
        return ""

    def _build_caption(self, context: HookContext | None = None) -> str:
        """Build a Reel caption from render metadata, template, or game info.

        Resolution order:
        1. ``context.shared["render_metadata"]["description"]`` (AI-generated)
        2. ``reel_caption_template`` rendered with game_info
        3. ``_build_title(game_info)`` fallback
        """
        if context is not None:
            render_meta = context.shared.get("render_metadata", {})
            description = str(render_meta.get("description", ""))
            if description:
                return description
        template = self._config.get("reel_caption_template", "")
        if not template:
            if self._game_info is not None:
                return self._build_title(self._game_info)
            return ""
        return self._render_template(template)

    def _build_comment(self) -> str:
        """Build a comment message from the template and game info."""
        template = self._config.get("instagram_comment_template", "")
        if not template:
            return ""
        return self._render_template(template)

    def _render_template(self, template: str) -> str:
        """Render a template string with game info substitution."""
        game_info = self._game_info
        values: dict[str, str] = {
            "home_team": getattr(game_info, "home_team", "") if game_info else "",
            "away_team": getattr(game_info, "away_team", "") if game_info else "",
            "date": getattr(game_info, "date", "") if game_info else "",
            "venue": getattr(game_info, "venue", "") if game_info else "",
            "sport": getattr(game_info, "sport", "") if game_info else "",
        }

        class SafeDict(dict[str, str]):
            def __missing__(self, key: str) -> str:
                return ""

        return template.format_map(SafeDict(values))

    def on_game_finish(self, context: HookContext) -> None:
        """Handle ``ON_GAME_FINISH`` — reset cached state."""
        self._access_token = None
        self._game_info = None
        self._livestream_id = None
        self._published_reel_id = None

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

    def auth_check(self) -> list[AuthCheckResult]:
        """Test Meta authentication and return check results.

        Returns one result per service: Facebook Page, and optionally
        Instagram (if ``instagram_account_id`` is configured).
        """
        from reeln_meta_plugin import graph_api

        results: list[AuthCheckResult] = []

        token_file_str = self._config.get("page_access_token_file")
        if not token_file_str:
            results.append(
                AuthCheckResult(
                    service="Facebook Page",
                    status=AuthStatus.NOT_CONFIGURED,
                    message="page_access_token_file not configured",
                    hint="Set page_access_token_file in plugin config",
                )
            )
            if self._config.get("instagram_account_id"):
                results.append(
                    AuthCheckResult(
                        service="Instagram",
                        status=AuthStatus.NOT_CONFIGURED,
                        message="page_access_token_file not configured",
                        hint="Set page_access_token_file in plugin config",
                    )
                )
            return results

        token_path = Path(token_file_str)

        try:
            token = auth.read_token(token_path)
        except auth.AuthError as exc:
            results.append(
                AuthCheckResult(
                    service="Facebook Page",
                    status=AuthStatus.FAIL,
                    message=str(exc),
                    hint="Create a Page Access Token file at the configured path",
                )
            )
            if self._config.get("instagram_account_id"):
                results.append(
                    AuthCheckResult(
                        service="Instagram",
                        status=AuthStatus.FAIL,
                        message=str(exc),
                        hint="Create a Page Access Token file at the configured path",
                    )
                )
            return results

        api_version = self._config.get("graph_api_version", "v24.0")
        page_id = self._config.get("page_id")

        # --- Facebook Page check ---
        if not page_id:
            results.append(
                AuthCheckResult(
                    service="Facebook Page",
                    status=AuthStatus.NOT_CONFIGURED,
                    message="page_id not configured",
                    hint="Set page_id in plugin config",
                )
            )
        else:
            try:
                data = graph_api.http_get(
                    f"https://graph.facebook.com/{api_version}/{page_id}",
                    {"fields": "name,id", "access_token": token},
                )
                page_name = str(data.get("name", page_id))
                results.append(
                    AuthCheckResult(
                        service="Facebook Page",
                        status=AuthStatus.OK,
                        message="Token valid",
                        identity=page_name,
                    )
                )
            except graph_api.GraphAPIError as exc:
                results.append(
                    AuthCheckResult(
                        service="Facebook Page",
                        status=AuthStatus.FAIL,
                        message=str(exc),
                        hint="Generate a new Page Access Token at https://developers.facebook.com/tools/explorer/",
                    )
                )

        # --- Instagram check ---
        ig_user_id = self._config.get("instagram_account_id")
        if ig_user_id:
            try:
                data = graph_api.http_get(
                    f"https://graph.facebook.com/{api_version}/{ig_user_id}",
                    {"fields": "username,name", "access_token": token},
                )
                username = str(data.get("username", ig_user_id))
                results.append(
                    AuthCheckResult(
                        service="Instagram",
                        status=AuthStatus.OK,
                        message="Token valid",
                        identity=username,
                    )
                )
            except graph_api.GraphAPIError as exc:
                results.append(
                    AuthCheckResult(
                        service="Instagram",
                        status=AuthStatus.FAIL,
                        message=str(exc),
                        hint="Ensure the Page Access Token has instagram_basic permission",
                    )
                )

        return results

    def auth_refresh(self) -> list[AuthCheckResult]:
        """Attempt to refresh Meta authentication.

        Meta Page Access Tokens are manually generated — there is no
        automated refresh flow.
        """
        return [
            AuthCheckResult(
                service="Meta",
                status=AuthStatus.FAIL,
                message="Meta tokens cannot be refreshed automatically",
                hint="Generate a new Page Access Token at https://developers.facebook.com/tools/explorer/",
            )
        ]

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
