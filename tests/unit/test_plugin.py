"""Tests for plugin module."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from reeln.plugins.hooks import Hook, HookContext
from reeln.plugins.registry import HookRegistry

from reeln_meta_plugin.auth import AuthError
from reeln_meta_plugin.comments import CommentError, CommentResult
from reeln_meta_plugin.facebook_reels import FacebookReelsError, ReelStartResult
from reeln_meta_plugin.livestream import LivestreamError, LivestreamResult
from reeln_meta_plugin.plugin import MetaPlugin
from reeln_meta_plugin.reels import ReelContainerResult, ReelsError
from tests.conftest import FakeGameInfo


class TestMetaPluginAttributes:
    def test_name(self) -> None:
        plugin = MetaPlugin()
        assert plugin.name == "meta"

    def test_version(self) -> None:
        plugin = MetaPlugin()
        assert plugin.version == "0.10.0"

    def test_api_version(self) -> None:
        plugin = MetaPlugin()
        assert plugin.api_version == 1


class TestMetaPluginConfigSchema:
    def test_page_access_token_file_required(self) -> None:
        schema = MetaPlugin.config_schema
        field = schema.field_by_name("page_access_token_file")
        assert field is not None
        assert field.required is True

    def test_page_id_required(self) -> None:
        schema = MetaPlugin.config_schema
        field = schema.field_by_name("page_id")
        assert field is not None
        assert field.required is True

    def test_create_livestream_default_false(self) -> None:
        schema = MetaPlugin.config_schema
        field = schema.field_by_name("create_livestream")
        assert field is not None
        assert field.default is False

    def test_dry_run_default_false(self) -> None:
        schema = MetaPlugin.config_schema
        field = schema.field_by_name("dry_run")
        assert field is not None
        assert field.default is False

    def test_graph_api_version_default(self) -> None:
        schema = MetaPlugin.config_schema
        field = schema.field_by_name("graph_api_version")
        assert field is not None
        assert field.default == "v24.0"

    def test_graph_api_version_optional(self) -> None:
        schema = MetaPlugin.config_schema
        field = schema.field_by_name("graph_api_version")
        assert field is not None
        assert field.required is False

    def test_status_default(self) -> None:
        schema = MetaPlugin.config_schema
        field = schema.field_by_name("status")
        assert field is not None
        assert field.default == "LIVE_NOW"

    def test_privacy_default(self) -> None:
        schema = MetaPlugin.config_schema
        field = schema.field_by_name("privacy")
        assert field is not None
        assert field.default == ""

    def test_content_category_default(self) -> None:
        schema = MetaPlugin.config_schema
        field = schema.field_by_name("content_category")
        assert field is not None
        assert field.default == "SPORTS"

    def test_game_id_default(self) -> None:
        schema = MetaPlugin.config_schema
        field = schema.field_by_name("game_id")
        assert field is not None
        assert field.default == ""

    def test_stop_on_delete_stream_default(self) -> None:
        schema = MetaPlugin.config_schema
        field = schema.field_by_name("stop_on_delete_stream")
        assert field is not None
        assert field.default is False

    def test_instagram_account_id_default(self) -> None:
        schema = MetaPlugin.config_schema
        field = schema.field_by_name("instagram_account_id")
        assert field is not None
        assert field.default == ""

    def test_publish_reels_default_false(self) -> None:
        schema = MetaPlugin.config_schema
        field = schema.field_by_name("publish_reels")
        assert field is not None
        assert field.default is False

    def test_publish_facebook_reels_default_false(self) -> None:
        schema = MetaPlugin.config_schema
        field = schema.field_by_name("publish_facebook_reels")
        assert field is not None
        assert field.default is False

    def test_facebook_reel_description_template_default(self) -> None:
        schema = MetaPlugin.config_schema
        field = schema.field_by_name("facebook_reel_description_template")
        assert field is not None
        assert field.default == ""

    def test_post_instagram_comment_default_false(self) -> None:
        schema = MetaPlugin.config_schema
        field = schema.field_by_name("post_instagram_comment")
        assert field is not None
        assert field.default is False

    def test_reel_caption_template_default(self) -> None:
        schema = MetaPlugin.config_schema
        field = schema.field_by_name("reel_caption_template")
        assert field is not None
        assert field.default == ""

    def test_instagram_comment_template_default(self) -> None:
        schema = MetaPlugin.config_schema
        field = schema.field_by_name("instagram_comment_template")
        assert field is not None
        assert field.default == ""

    def test_reel_share_to_feed_default(self) -> None:
        schema = MetaPlugin.config_schema
        field = schema.field_by_name("reel_share_to_feed")
        assert field is not None
        assert field.default is True

    def test_reel_thumb_offset_ms_default(self) -> None:
        schema = MetaPlugin.config_schema
        field = schema.field_by_name("reel_thumb_offset_ms")
        assert field is not None
        assert field.default == 0

    def test_reel_poll_interval_seconds_default(self) -> None:
        schema = MetaPlugin.config_schema
        field = schema.field_by_name("reel_poll_interval_seconds")
        assert field is not None
        assert field.default == 5

    def test_reel_poll_max_attempts_default(self) -> None:
        schema = MetaPlugin.config_schema
        field = schema.field_by_name("reel_poll_max_attempts")
        assert field is not None
        assert field.default == 60


class TestMetaPluginInit:
    def test_no_config(self) -> None:
        plugin = MetaPlugin()
        assert plugin._config == {}
        assert plugin._access_token is None
        assert plugin._game_info is None
        assert plugin._livestream_id is None
        assert plugin._published_reel_id is None

    def test_empty_config(self) -> None:
        plugin = MetaPlugin({})
        assert plugin._config == {}

    def test_with_config(self, plugin_config: dict[str, Any]) -> None:
        plugin = MetaPlugin(plugin_config)
        assert plugin._config == plugin_config


class TestMetaPluginRegister:
    def test_registers_on_game_init(self) -> None:
        plugin = MetaPlugin()
        registry = HookRegistry()
        plugin.register(registry)
        assert registry.has_handlers(Hook.ON_GAME_INIT)

    def test_registers_on_game_ready(self) -> None:
        plugin = MetaPlugin()
        registry = HookRegistry()
        plugin.register(registry)
        assert registry.has_handlers(Hook.ON_GAME_READY)

    def test_registers_on_game_finish(self) -> None:
        plugin = MetaPlugin()
        registry = HookRegistry()
        plugin.register(registry)
        assert registry.has_handlers(Hook.ON_GAME_FINISH)

    def test_registers_post_render(self) -> None:
        plugin = MetaPlugin()
        registry = HookRegistry()
        plugin.register(registry)
        assert registry.has_handlers(Hook.POST_RENDER)


class TestEnsureAuth:
    def test_returns_token(self, plugin_config: dict[str, Any]) -> None:
        plugin = MetaPlugin(plugin_config)
        token = plugin._ensure_auth()
        assert token == "test-access-token-123"

    def test_caches_token(self, plugin_config: dict[str, Any]) -> None:
        plugin = MetaPlugin(plugin_config)
        token1 = plugin._ensure_auth()
        token2 = plugin._ensure_auth()
        assert token1 == token2
        assert token1 is token2

    def test_reads_file_only_once(self, plugin_config: dict[str, Any]) -> None:
        plugin = MetaPlugin(plugin_config)
        with patch("reeln_meta_plugin.plugin.auth.read_token", return_value="tok") as mock_read:
            plugin._ensure_auth()
            plugin._ensure_auth()
        mock_read.assert_called_once()

    def test_no_token_file_config(self) -> None:
        plugin = MetaPlugin({"page_id": "123", "create_livestream": True})
        result = plugin._ensure_auth()
        assert result is None

    def test_no_token_file_logs_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        plugin = MetaPlugin({"page_id": "123", "create_livestream": True})
        with caplog.at_level(logging.WARNING):
            plugin._ensure_auth()
        assert "page_access_token_file not configured" in caplog.text

    def test_auth_error_returns_none(self, plugin_config: dict[str, Any]) -> None:
        plugin = MetaPlugin(plugin_config)
        with patch(
            "reeln_meta_plugin.plugin.auth.read_token",
            side_effect=AuthError("bad token"),
        ):
            result = plugin._ensure_auth()
        assert result is None

    def test_auth_error_logs_warning(
        self, plugin_config: dict[str, Any], caplog: pytest.LogCaptureFixture
    ) -> None:
        plugin = MetaPlugin(plugin_config)
        with (
            patch(
                "reeln_meta_plugin.plugin.auth.read_token",
                side_effect=AuthError("bad token"),
            ),
            caplog.at_level(logging.WARNING),
        ):
            plugin._ensure_auth()
        assert "authentication failed" in caplog.text


class TestBuildTitle:
    def test_basic_title(self) -> None:
        plugin = MetaPlugin()
        game_info = FakeGameInfo(home_team="Eagles", away_team="Hawks", date="2026-01-15")
        title = plugin._build_title(game_info)
        assert title == "Eagles vs Hawks - 2026-01-15"

    def test_title_with_venue(self) -> None:
        plugin = MetaPlugin()
        game_info = FakeGameInfo(
            home_team="Eagles", away_team="Hawks", date="2026-01-15", venue="Main Arena"
        )
        title = plugin._build_title(game_info)
        assert title == "Eagles vs Hawks - 2026-01-15 @ Main Arena"

    def test_title_empty_venue(self) -> None:
        plugin = MetaPlugin()
        game_info = FakeGameInfo(
            home_team="Eagles", away_team="Hawks", date="2026-01-15", venue=""
        )
        title = plugin._build_title(game_info)
        assert title == "Eagles vs Hawks - 2026-01-15"

    def test_title_missing_attributes(self) -> None:
        plugin = MetaPlugin()

        class Bare:
            pass

        title = plugin._build_title(Bare())
        assert title == " vs  - "


class TestComputeEventParams:
    def test_valid_12h_format(self) -> None:
        game_info = FakeGameInfo(date="2026-03-14", game_time="7:00 PM")
        result = MetaPlugin._compute_event_params(game_info)
        assert result.isdigit()
        assert int(result) > 0

    def test_valid_24h_format(self) -> None:
        game_info = FakeGameInfo(date="2026-03-14", game_time="19:00")
        result = MetaPlugin._compute_event_params(game_info)
        assert result.isdigit()

    def test_valid_12h_no_space(self) -> None:
        game_info = FakeGameInfo(date="2026-03-14", game_time="7:00PM")
        result = MetaPlugin._compute_event_params(game_info)
        assert result.isdigit()

    def test_valid_12h_with_timezone(self) -> None:
        game_info = FakeGameInfo(date="2026-03-14", game_time="8:15PM CDT")
        result = MetaPlugin._compute_event_params(game_info)
        assert result.isdigit()

    def test_valid_12h_space_with_timezone(self) -> None:
        game_info = FakeGameInfo(date="2026-03-14", game_time="8:15 PM CDT")
        result = MetaPlugin._compute_event_params(game_info)
        assert result.isdigit()

    def test_empty_game_time(self) -> None:
        game_info = FakeGameInfo(date="2026-03-14", game_time="")
        assert MetaPlugin._compute_event_params(game_info) == ""

    def test_empty_date(self) -> None:
        game_info = FakeGameInfo(date="", game_time="7:00 PM")
        assert MetaPlugin._compute_event_params(game_info) == ""

    def test_invalid_time_format(self) -> None:
        game_info = FakeGameInfo(date="2026-03-14", game_time="asdf")
        assert MetaPlugin._compute_event_params(game_info) == ""

    def test_invalid_date_format(self) -> None:
        game_info = FakeGameInfo(date="March 14", game_time="7:00 PM")
        assert MetaPlugin._compute_event_params(game_info) == ""

    def test_missing_attributes(self) -> None:
        class Bare:
            pass

        assert MetaPlugin._compute_event_params(Bare()) == ""

    def test_consistent_output(self) -> None:
        """Same inputs produce the same timestamp."""
        game_info = FakeGameInfo(date="2026-03-14", game_time="7:00 PM")
        result1 = MetaPlugin._compute_event_params(game_info)
        result2 = MetaPlugin._compute_event_params(game_info)
        assert result1 == result2


_FAKE_RESULT = LivestreamResult(
    id="live-123",
    stream_url="rtmps://live.facebook.com/rtmp/live-123",
    embed_url="https://www.facebook.com/123456789/videos/live-123",
)


class TestOnGameInit:
    def test_disabled_by_default(self) -> None:
        """When create_livestream is not set, on_game_init does nothing."""
        plugin = MetaPlugin({"page_access_token_file": "/tmp/tok", "page_id": "123"})
        game_info = FakeGameInfo()
        context = HookContext(hook=Hook.ON_GAME_INIT, data={"game_info": game_info})

        plugin.on_game_init(context)

        assert "livestreams" not in context.shared

    def test_full_flow(self, plugin_config: dict[str, Any]) -> None:
        plugin = MetaPlugin(plugin_config)
        game_info = FakeGameInfo()
        context = HookContext(hook=Hook.ON_GAME_INIT, data={"game_info": game_info})

        with patch(
            "reeln_meta_plugin.plugin.livestream.create_livestream",
            return_value=_FAKE_RESULT,
        ):
            plugin.on_game_init(context)

        assert context.shared["livestreams"]["meta"] == _FAKE_RESULT.embed_url

    def test_caches_livestream_id(self, plugin_config: dict[str, Any]) -> None:
        plugin = MetaPlugin(plugin_config)
        game_info = FakeGameInfo()
        context = HookContext(hook=Hook.ON_GAME_INIT, data={"game_info": game_info})

        with patch(
            "reeln_meta_plugin.plugin.livestream.create_livestream",
            return_value=_FAKE_RESULT,
        ):
            plugin.on_game_init(context)

        assert plugin._livestream_id == "live-123"

    def test_caches_game_info(self, plugin_config: dict[str, Any]) -> None:
        plugin = MetaPlugin(plugin_config)
        game_info = FakeGameInfo()
        context = HookContext(hook=Hook.ON_GAME_INIT, data={"game_info": game_info})

        with patch(
            "reeln_meta_plugin.plugin.livestream.create_livestream",
            return_value=_FAKE_RESULT,
        ):
            plugin.on_game_init(context)

        assert plugin._game_info is game_info

    def test_no_game_info_logs_warning(
        self, plugin_config: dict[str, Any], caplog: pytest.LogCaptureFixture
    ) -> None:
        plugin = MetaPlugin(plugin_config)
        context = HookContext(hook=Hook.ON_GAME_INIT, data={})

        with caplog.at_level(logging.WARNING):
            plugin.on_game_init(context)

        assert "no game_info" in caplog.text
        assert "livestreams" not in context.shared

    def test_no_token_config_logs_warning(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        plugin = MetaPlugin({"page_id": "123", "create_livestream": True})
        game_info = FakeGameInfo()
        context = HookContext(hook=Hook.ON_GAME_INIT, data={"game_info": game_info})

        with caplog.at_level(logging.WARNING):
            plugin.on_game_init(context)

        assert "page_access_token_file not configured" in caplog.text

    def test_auth_error_logs_warning(
        self, plugin_config: dict[str, Any], caplog: pytest.LogCaptureFixture
    ) -> None:
        plugin = MetaPlugin(plugin_config)
        game_info = FakeGameInfo()
        context = HookContext(hook=Hook.ON_GAME_INIT, data={"game_info": game_info})

        with (
            patch(
                "reeln_meta_plugin.plugin.auth.read_token",
                side_effect=AuthError("bad token"),
            ),
            caplog.at_level(logging.WARNING),
        ):
            plugin.on_game_init(context)

        assert "authentication failed" in caplog.text
        assert "livestreams" not in context.shared

    def test_no_page_id_logs_warning(
        self, token_file: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        plugin = MetaPlugin({"page_access_token_file": str(token_file), "create_livestream": True})
        game_info = FakeGameInfo()
        context = HookContext(hook=Hook.ON_GAME_INIT, data={"game_info": game_info})

        with caplog.at_level(logging.WARNING):
            plugin.on_game_init(context)

        assert "page_id not configured" in caplog.text

    def test_livestream_error_logs_warning(
        self, plugin_config: dict[str, Any], caplog: pytest.LogCaptureFixture
    ) -> None:
        plugin = MetaPlugin(plugin_config)
        game_info = FakeGameInfo()
        context = HookContext(hook=Hook.ON_GAME_INIT, data={"game_info": game_info})

        with (
            patch(
                "reeln_meta_plugin.plugin.livestream.create_livestream",
                side_effect=LivestreamError("api error"),
            ),
            caplog.at_level(logging.WARNING),
        ):
            plugin.on_game_init(context)

        assert "livestream creation failed" in caplog.text
        assert "livestreams" not in context.shared

    def test_description_passed_to_create_livestream(
        self, plugin_config: dict[str, Any]
    ) -> None:
        plugin = MetaPlugin(plugin_config)
        game_info = FakeGameInfo(description="Big game tonight")
        context = HookContext(hook=Hook.ON_GAME_INIT, data={"game_info": game_info})

        with patch(
            "reeln_meta_plugin.plugin.livestream.create_livestream",
            return_value=_FAKE_RESULT,
        ) as mock_create:
            plugin.on_game_init(context)

        assert mock_create.call_args[1]["description"] == "Big game tonight"

    def test_missing_description_attribute_defaults_empty(
        self, plugin_config: dict[str, Any]
    ) -> None:
        plugin = MetaPlugin(plugin_config)

        class BareGameInfo:
            date = "2026-01-15"
            home_team = "Eagles"
            away_team = "Hawks"
            venue = ""

        context = HookContext(hook=Hook.ON_GAME_INIT, data={"game_info": BareGameInfo()})

        with patch(
            "reeln_meta_plugin.plugin.livestream.create_livestream",
            return_value=_FAKE_RESULT,
        ) as mock_create:
            plugin.on_game_init(context)

        assert mock_create.call_args[1]["description"] == ""

    def test_custom_api_version(self, plugin_config: dict[str, Any]) -> None:
        plugin_config["graph_api_version"] = "v23.0"
        plugin = MetaPlugin(plugin_config)
        game_info = FakeGameInfo()
        context = HookContext(hook=Hook.ON_GAME_INIT, data={"game_info": game_info})

        with patch(
            "reeln_meta_plugin.plugin.livestream.create_livestream",
            return_value=_FAKE_RESULT,
        ) as mock_create:
            plugin.on_game_init(context)

        assert mock_create.call_args[1]["api_version"] == "v23.0"

    def test_default_livestream_settings(self, plugin_config: dict[str, Any]) -> None:
        """Verify defaults flow through when config doesn't override them."""
        plugin = MetaPlugin(plugin_config)
        game_info = FakeGameInfo()
        context = HookContext(hook=Hook.ON_GAME_INIT, data={"game_info": game_info})

        with patch(
            "reeln_meta_plugin.plugin.livestream.create_livestream",
            return_value=_FAKE_RESULT,
        ) as mock_create:
            plugin.on_game_init(context)

        kwargs = mock_create.call_args[1]
        assert kwargs["status"] == "LIVE_NOW"
        assert kwargs["event_params"] == ""
        assert kwargs["privacy"] == ""
        assert kwargs["content_category"] == "SPORTS"
        assert kwargs["game_id"] == ""
        assert kwargs["stop_on_delete_stream"] is False

    def test_scheduled_unpublished_with_game_time(self, plugin_config: dict[str, Any]) -> None:
        """With SCHEDULED_UNPUBLISHED + game_time, computes event_params."""
        plugin_config["status"] = "SCHEDULED_UNPUBLISHED"
        plugin = MetaPlugin(plugin_config)
        game_info = FakeGameInfo(game_time="7:00 PM")
        context = HookContext(hook=Hook.ON_GAME_INIT, data={"game_info": game_info})

        with patch(
            "reeln_meta_plugin.plugin.livestream.create_livestream",
            return_value=_FAKE_RESULT,
        ) as mock_create:
            plugin.on_game_init(context)

        kwargs = mock_create.call_args[1]
        assert kwargs["status"] == "SCHEDULED_UNPUBLISHED"
        assert kwargs["event_params"] != ""
        assert kwargs["event_params"].isdigit()

    def test_custom_livestream_settings(self, plugin_config: dict[str, Any]) -> None:
        """Verify config overrides flow through to create_livestream."""
        plugin_config.update({
            "status": "LIVE_NOW",
            "privacy": "SELF",
            "content_category": "VIDEO_GAMING",
            "game_id": "42",
            "stop_on_delete_stream": True,
        })
        plugin = MetaPlugin(plugin_config)
        game_info = FakeGameInfo()
        context = HookContext(hook=Hook.ON_GAME_INIT, data={"game_info": game_info})

        with patch(
            "reeln_meta_plugin.plugin.livestream.create_livestream",
            return_value=_FAKE_RESULT,
        ) as mock_create:
            plugin.on_game_init(context)

        kwargs = mock_create.call_args[1]
        assert kwargs["status"] == "LIVE_NOW"
        assert kwargs["privacy"] == "SELF"
        assert kwargs["content_category"] == "VIDEO_GAMING"
        assert kwargs["game_id"] == "42"
        assert kwargs["stop_on_delete_stream"] is True

    def test_scheduled_fallback_logs_warning(
        self, plugin_config: dict[str, Any], caplog: pytest.LogCaptureFixture
    ) -> None:
        """SCHEDULED_UNPUBLISHED with no game_time logs a warning about fallback."""
        plugin_config["status"] = "SCHEDULED_UNPUBLISHED"
        plugin = MetaPlugin(plugin_config)
        game_info = FakeGameInfo()  # no game_time
        context = HookContext(hook=Hook.ON_GAME_INIT, data={"game_info": game_info})

        with (
            patch(
                "reeln_meta_plugin.plugin.livestream.create_livestream",
                return_value=_FAKE_RESULT,
            ),
            caplog.at_level(logging.WARNING),
        ):
            plugin.on_game_init(context)

        assert "falling back to LIVE_NOW" in caplog.text

    def test_logs_info_on_success(
        self, plugin_config: dict[str, Any], caplog: pytest.LogCaptureFixture
    ) -> None:
        plugin = MetaPlugin(plugin_config)
        game_info = FakeGameInfo()
        context = HookContext(hook=Hook.ON_GAME_INIT, data={"game_info": game_info})

        with (
            patch(
                "reeln_meta_plugin.plugin.livestream.create_livestream",
                return_value=_FAKE_RESULT,
            ),
            caplog.at_level(logging.INFO),
        ):
            plugin.on_game_init(context)

        assert "created livestream" in caplog.text
        assert "stream_url=" in caplog.text

    def test_uses_cached_token(self, plugin_config: dict[str, Any]) -> None:
        """Verify _ensure_auth caching — read_token called once across two on_game_init calls."""
        plugin = MetaPlugin(plugin_config)

        with patch("reeln_meta_plugin.plugin.auth.read_token", return_value="tok") as mock_read:
            for _ in range(2):
                game_info = FakeGameInfo()
                context = HookContext(hook=Hook.ON_GAME_INIT, data={"game_info": game_info})
                with patch(
                    "reeln_meta_plugin.plugin.livestream.create_livestream",
                    return_value=_FAKE_RESULT,
                ):
                    plugin.on_game_init(context)

        mock_read.assert_called_once()


class TestOnGameInitDryRun:
    def test_dry_run_skips_api_call(self, plugin_config: dict[str, Any]) -> None:
        plugin_config["dry_run"] = True
        plugin = MetaPlugin(plugin_config)
        game_info = FakeGameInfo()
        context = HookContext(hook=Hook.ON_GAME_INIT, data={"game_info": game_info})

        with patch(
            "reeln_meta_plugin.plugin.livestream.create_livestream",
        ) as mock_create:
            plugin.on_game_init(context)

        mock_create.assert_not_called()
        assert "livestreams" not in context.shared

    def test_dry_run_logs_info(
        self, plugin_config: dict[str, Any], caplog: pytest.LogCaptureFixture
    ) -> None:
        plugin_config["dry_run"] = True
        plugin = MetaPlugin(plugin_config)
        game_info = FakeGameInfo()
        context = HookContext(hook=Hook.ON_GAME_INIT, data={"game_info": game_info})

        with caplog.at_level(logging.INFO):
            plugin.on_game_init(context)

        assert "DRY RUN" in caplog.text
        assert "would create livestream" in caplog.text

    def test_dry_run_false_calls_api(self, plugin_config: dict[str, Any]) -> None:
        plugin_config["dry_run"] = False
        plugin = MetaPlugin(plugin_config)
        game_info = FakeGameInfo()
        context = HookContext(hook=Hook.ON_GAME_INIT, data={"game_info": game_info})

        with patch(
            "reeln_meta_plugin.plugin.livestream.create_livestream",
            return_value=_FAKE_RESULT,
        ) as mock_create:
            plugin.on_game_init(context)

        mock_create.assert_called_once()


class TestOnGameReady:
    def _ready_plugin(self, plugin_config: dict[str, Any]) -> MetaPlugin:
        """Return a plugin with cached state as if on_game_init already ran."""
        plugin = MetaPlugin(plugin_config)
        plugin._livestream_id = "live-123"
        plugin._access_token = "test-access-token-123"
        return plugin

    def test_skips_when_no_livestream_id(self, plugin_config: dict[str, Any]) -> None:
        plugin = MetaPlugin(plugin_config)
        context = HookContext(
            hook=Hook.ON_GAME_READY,
            data={},
            shared={"livestream_metadata": {"title": "New Title"}},
        )

        with patch("reeln_meta_plugin.plugin.livestream.update_livestream") as mock_update:
            plugin.on_game_ready(context)

        mock_update.assert_not_called()

    def test_skips_when_no_metadata_or_thumbnail(self, plugin_config: dict[str, Any]) -> None:
        plugin = self._ready_plugin(plugin_config)
        context = HookContext(hook=Hook.ON_GAME_READY, data={})

        with (
            patch("reeln_meta_plugin.plugin.livestream.update_livestream") as mock_update,
            patch("reeln_meta_plugin.plugin.livestream.upload_thumbnail") as mock_thumb,
        ):
            plugin.on_game_ready(context)

        mock_update.assert_not_called()
        mock_thumb.assert_not_called()

    def test_skips_when_metadata_empty_no_thumbnail(self, plugin_config: dict[str, Any]) -> None:
        plugin = self._ready_plugin(plugin_config)
        context = HookContext(
            hook=Hook.ON_GAME_READY,
            data={},
            shared={"livestream_metadata": {}},
        )

        with (
            patch("reeln_meta_plugin.plugin.livestream.update_livestream") as mock_update,
            patch("reeln_meta_plugin.plugin.livestream.upload_thumbnail") as mock_thumb,
        ):
            plugin.on_game_ready(context)

        mock_update.assert_not_called()
        mock_thumb.assert_not_called()

    def test_skips_when_title_desc_empty_no_thumbnail(self, plugin_config: dict[str, Any]) -> None:
        plugin = self._ready_plugin(plugin_config)
        context = HookContext(
            hook=Hook.ON_GAME_READY,
            data={},
            shared={"livestream_metadata": {"title": "", "description": ""}},
        )

        with (
            patch("reeln_meta_plugin.plugin.livestream.update_livestream") as mock_update,
            patch("reeln_meta_plugin.plugin.livestream.upload_thumbnail") as mock_thumb,
        ):
            plugin.on_game_ready(context)

        mock_update.assert_not_called()
        mock_thumb.assert_not_called()

    def test_skips_when_auth_fails(self, plugin_config: dict[str, Any]) -> None:
        plugin = MetaPlugin(plugin_config)
        plugin._livestream_id = "live-123"
        # No _access_token set, and mock auth to fail
        context = HookContext(
            hook=Hook.ON_GAME_READY,
            data={},
            shared={"livestream_metadata": {"title": "New Title"}},
        )

        with (
            patch(
                "reeln_meta_plugin.plugin.auth.read_token",
                side_effect=AuthError("bad token"),
            ),
            patch("reeln_meta_plugin.plugin.livestream.update_livestream") as mock_update,
        ):
            plugin.on_game_ready(context)

        mock_update.assert_not_called()

    def test_updates_with_title(self, plugin_config: dict[str, Any]) -> None:
        plugin = self._ready_plugin(plugin_config)
        context = HookContext(
            hook=Hook.ON_GAME_READY,
            data={},
            shared={"livestream_metadata": {"title": "Updated Title"}},
        )

        with patch("reeln_meta_plugin.plugin.livestream.update_livestream") as mock_update:
            plugin.on_game_ready(context)

        mock_update.assert_called_once_with(
            live_video_id="live-123",
            access_token="test-access-token-123",
            title="Updated Title",
            description="",
            api_version="v24.0",
        )

    def test_updates_with_description(self, plugin_config: dict[str, Any]) -> None:
        plugin = self._ready_plugin(plugin_config)
        context = HookContext(
            hook=Hook.ON_GAME_READY,
            data={},
            shared={"livestream_metadata": {"description": "Game day description"}},
        )

        with patch("reeln_meta_plugin.plugin.livestream.update_livestream") as mock_update:
            plugin.on_game_ready(context)

        mock_update.assert_called_once_with(
            live_video_id="live-123",
            access_token="test-access-token-123",
            title="",
            description="Game day description",
            api_version="v24.0",
        )

    def test_updates_with_both(self, plugin_config: dict[str, Any]) -> None:
        plugin = self._ready_plugin(plugin_config)
        context = HookContext(
            hook=Hook.ON_GAME_READY,
            data={},
            shared={"livestream_metadata": {"title": "T", "description": "D"}},
        )

        with patch("reeln_meta_plugin.plugin.livestream.update_livestream") as mock_update:
            plugin.on_game_ready(context)

        kwargs = mock_update.call_args[1]
        assert kwargs["title"] == "T"
        assert kwargs["description"] == "D"

    def test_custom_api_version(self, plugin_config: dict[str, Any]) -> None:
        plugin_config["graph_api_version"] = "v23.0"
        plugin = self._ready_plugin(plugin_config)
        context = HookContext(
            hook=Hook.ON_GAME_READY,
            data={},
            shared={"livestream_metadata": {"title": "T"}},
        )

        with patch("reeln_meta_plugin.plugin.livestream.update_livestream") as mock_update:
            plugin.on_game_ready(context)

        assert mock_update.call_args[1]["api_version"] == "v23.0"

    def test_update_error_logs_warning(
        self, plugin_config: dict[str, Any], caplog: pytest.LogCaptureFixture
    ) -> None:
        plugin = self._ready_plugin(plugin_config)
        context = HookContext(
            hook=Hook.ON_GAME_READY,
            data={},
            shared={"livestream_metadata": {"title": "T"}},
        )

        with (
            patch(
                "reeln_meta_plugin.plugin.livestream.update_livestream",
                side_effect=LivestreamError("api error"),
            ),
            caplog.at_level(logging.WARNING),
        ):
            plugin.on_game_ready(context)

        assert "livestream update failed" in caplog.text

    def test_logs_info_on_success(
        self, plugin_config: dict[str, Any], caplog: pytest.LogCaptureFixture
    ) -> None:
        plugin = self._ready_plugin(plugin_config)
        context = HookContext(
            hook=Hook.ON_GAME_READY,
            data={},
            shared={"livestream_metadata": {"title": "T"}},
        )

        with (
            patch("reeln_meta_plugin.plugin.livestream.update_livestream"),
            caplog.at_level(logging.INFO),
        ):
            plugin.on_game_ready(context)

        assert "updated livestream" in caplog.text

    def test_dry_run_skips_update(self, plugin_config: dict[str, Any]) -> None:
        plugin_config["dry_run"] = True
        plugin = self._ready_plugin(plugin_config)
        context = HookContext(
            hook=Hook.ON_GAME_READY,
            data={},
            shared={"livestream_metadata": {"title": "T"}},
        )

        with (
            patch("reeln_meta_plugin.plugin.livestream.update_livestream") as mock_update,
            patch("reeln_meta_plugin.plugin.livestream.upload_thumbnail") as mock_thumb,
        ):
            plugin.on_game_ready(context)

        mock_update.assert_not_called()
        mock_thumb.assert_not_called()

    def test_dry_run_logs_info(
        self, plugin_config: dict[str, Any], caplog: pytest.LogCaptureFixture
    ) -> None:
        plugin_config["dry_run"] = True
        plugin = self._ready_plugin(plugin_config)
        context = HookContext(
            hook=Hook.ON_GAME_READY,
            data={},
            shared={"livestream_metadata": {"title": "T"}},
        )

        with caplog.at_level(logging.INFO):
            plugin.on_game_ready(context)

        assert "DRY RUN" in caplog.text
        assert "would update livestream" in caplog.text


class TestOnGameReadyThumbnail:
    def _ready_plugin(self, plugin_config: dict[str, Any]) -> MetaPlugin:
        """Return a plugin with cached state as if on_game_init already ran."""
        plugin = MetaPlugin(plugin_config)
        plugin._livestream_id = "live-123"
        plugin._access_token = "test-access-token-123"
        return plugin

    def test_uploads_thumbnail(
        self, plugin_config: dict[str, Any], tmp_path: Path
    ) -> None:
        thumb = tmp_path / "thumb.png"
        thumb.write_bytes(b"\x89PNG")
        plugin = self._ready_plugin(plugin_config)
        context = HookContext(
            hook=Hook.ON_GAME_READY,
            data={},
            shared={"game_image": {"image_path": str(thumb)}},
        )

        with (
            patch("reeln_meta_plugin.plugin.livestream.update_livestream") as mock_update,
            patch("reeln_meta_plugin.plugin.livestream.upload_thumbnail") as mock_thumb,
        ):
            plugin.on_game_ready(context)

        mock_update.assert_not_called()
        mock_thumb.assert_called_once_with(
            live_video_id="live-123",
            access_token="test-access-token-123",
            image_path=thumb,
            api_version="v24.0",
        )

    def test_uploads_thumbnail_with_metadata(
        self, plugin_config: dict[str, Any], tmp_path: Path
    ) -> None:
        thumb = tmp_path / "thumb.png"
        thumb.write_bytes(b"\x89PNG")
        plugin = self._ready_plugin(plugin_config)
        context = HookContext(
            hook=Hook.ON_GAME_READY,
            data={},
            shared={
                "livestream_metadata": {"title": "T"},
                "game_image": {"image_path": str(thumb)},
            },
        )

        with (
            patch("reeln_meta_plugin.plugin.livestream.update_livestream") as mock_update,
            patch("reeln_meta_plugin.plugin.livestream.upload_thumbnail") as mock_thumb,
        ):
            plugin.on_game_ready(context)

        mock_update.assert_called_once()
        mock_thumb.assert_called_once()

    def test_skips_when_image_path_empty(self, plugin_config: dict[str, Any]) -> None:
        plugin = self._ready_plugin(plugin_config)
        context = HookContext(
            hook=Hook.ON_GAME_READY,
            data={},
            shared={"game_image": {"image_path": ""}},
        )

        with (
            patch("reeln_meta_plugin.plugin.livestream.update_livestream") as mock_update,
            patch("reeln_meta_plugin.plugin.livestream.upload_thumbnail") as mock_thumb,
        ):
            plugin.on_game_ready(context)

        mock_update.assert_not_called()
        mock_thumb.assert_not_called()

    def test_skips_when_image_file_missing(
        self, plugin_config: dict[str, Any], tmp_path: Path
    ) -> None:
        plugin = self._ready_plugin(plugin_config)
        context = HookContext(
            hook=Hook.ON_GAME_READY,
            data={},
            shared={"game_image": {"image_path": str(tmp_path / "nonexistent.png")}},
        )

        with (
            patch("reeln_meta_plugin.plugin.livestream.update_livestream") as mock_update,
            patch("reeln_meta_plugin.plugin.livestream.upload_thumbnail") as mock_thumb,
        ):
            plugin.on_game_ready(context)

        mock_update.assert_not_called()
        mock_thumb.assert_not_called()

    def test_skips_when_game_image_not_dict(self, plugin_config: dict[str, Any]) -> None:
        plugin = self._ready_plugin(plugin_config)
        context = HookContext(
            hook=Hook.ON_GAME_READY,
            data={},
            shared={"game_image": "not-a-dict"},
        )

        with (
            patch("reeln_meta_plugin.plugin.livestream.update_livestream") as mock_update,
            patch("reeln_meta_plugin.plugin.livestream.upload_thumbnail") as mock_thumb,
        ):
            plugin.on_game_ready(context)

        mock_update.assert_not_called()
        mock_thumb.assert_not_called()

    def test_thumbnail_error_nonfatal(
        self, plugin_config: dict[str, Any], tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        thumb = tmp_path / "thumb.png"
        thumb.write_bytes(b"\x89PNG")
        plugin = self._ready_plugin(plugin_config)
        context = HookContext(
            hook=Hook.ON_GAME_READY,
            data={},
            shared={"game_image": {"image_path": str(thumb)}},
        )

        with (
            patch(
                "reeln_meta_plugin.plugin.livestream.upload_thumbnail",
                side_effect=LivestreamError("upload failed"),
            ),
            caplog.at_level(logging.WARNING),
        ):
            plugin.on_game_ready(context)

        assert "thumbnail upload failed" in caplog.text

    def test_metadata_error_still_uploads_thumbnail(
        self, plugin_config: dict[str, Any], tmp_path: Path
    ) -> None:
        thumb = tmp_path / "thumb.png"
        thumb.write_bytes(b"\x89PNG")
        plugin = self._ready_plugin(plugin_config)
        context = HookContext(
            hook=Hook.ON_GAME_READY,
            data={},
            shared={
                "livestream_metadata": {"title": "T"},
                "game_image": {"image_path": str(thumb)},
            },
        )

        with (
            patch(
                "reeln_meta_plugin.plugin.livestream.update_livestream",
                side_effect=LivestreamError("api error"),
            ),
            patch("reeln_meta_plugin.plugin.livestream.upload_thumbnail") as mock_thumb,
        ):
            plugin.on_game_ready(context)

        mock_thumb.assert_called_once()

    def test_custom_api_version_for_thumbnail(
        self, plugin_config: dict[str, Any], tmp_path: Path
    ) -> None:
        plugin_config["graph_api_version"] = "v23.0"
        thumb = tmp_path / "thumb.png"
        thumb.write_bytes(b"\x89PNG")
        plugin = self._ready_plugin(plugin_config)
        context = HookContext(
            hook=Hook.ON_GAME_READY,
            data={},
            shared={"game_image": {"image_path": str(thumb)}},
        )

        with patch("reeln_meta_plugin.plugin.livestream.upload_thumbnail") as mock_thumb:
            plugin.on_game_ready(context)

        assert mock_thumb.call_args[1]["api_version"] == "v23.0"

    def test_dry_run_skips_thumbnail(
        self, plugin_config: dict[str, Any], tmp_path: Path
    ) -> None:
        plugin_config["dry_run"] = True
        thumb = tmp_path / "thumb.png"
        thumb.write_bytes(b"\x89PNG")
        plugin = self._ready_plugin(plugin_config)
        context = HookContext(
            hook=Hook.ON_GAME_READY,
            data={},
            shared={"game_image": {"image_path": str(thumb)}},
        )

        with patch("reeln_meta_plugin.plugin.livestream.upload_thumbnail") as mock_thumb:
            plugin.on_game_ready(context)

        mock_thumb.assert_not_called()

    def test_dry_run_logs_thumbnail_path(
        self, plugin_config: dict[str, Any], tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        plugin_config["dry_run"] = True
        thumb = tmp_path / "thumb.png"
        thumb.write_bytes(b"\x89PNG")
        plugin = self._ready_plugin(plugin_config)
        context = HookContext(
            hook=Hook.ON_GAME_READY,
            data={},
            shared={"game_image": {"image_path": str(thumb)}},
        )

        with caplog.at_level(logging.INFO):
            plugin.on_game_ready(context)

        assert "DRY RUN" in caplog.text
        assert "thumb.png" in caplog.text


class TestOnGameFinish:
    def test_resets_access_token(self, plugin_config: dict[str, Any]) -> None:
        plugin = MetaPlugin(plugin_config)
        plugin._access_token = "cached-token"
        context = HookContext(hook=Hook.ON_GAME_FINISH, data={})

        plugin.on_game_finish(context)

        assert plugin._access_token is None

    def test_resets_game_info(self, plugin_config: dict[str, Any]) -> None:
        plugin = MetaPlugin(plugin_config)
        plugin._game_info = FakeGameInfo()
        context = HookContext(hook=Hook.ON_GAME_FINISH, data={})

        plugin.on_game_finish(context)

        assert plugin._game_info is None

    def test_resets_livestream_id(self, plugin_config: dict[str, Any]) -> None:
        plugin = MetaPlugin(plugin_config)
        plugin._livestream_id = "live-123"
        context = HookContext(hook=Hook.ON_GAME_FINISH, data={})

        plugin.on_game_finish(context)

        assert plugin._livestream_id is None

    def test_resets_published_reel_id(self, plugin_config: dict[str, Any]) -> None:
        plugin = MetaPlugin(plugin_config)
        plugin._published_reel_id = "media-123"
        context = HookContext(hook=Hook.ON_GAME_FINISH, data={})

        plugin.on_game_finish(context)

        assert plugin._published_reel_id is None

    def test_allows_re_auth_after_reset(self, plugin_config: dict[str, Any]) -> None:
        """After on_game_finish, _ensure_auth reads the token again."""
        plugin = MetaPlugin(plugin_config)
        plugin._access_token = "old-token"

        context = HookContext(hook=Hook.ON_GAME_FINISH, data={})
        plugin.on_game_finish(context)

        with patch("reeln_meta_plugin.plugin.auth.read_token", return_value="new-token") as mock_read:
            token = plugin._ensure_auth()

        assert token == "new-token"
        mock_read.assert_called_once()


_FAKE_CONTAINER = ReelContainerResult(container_id="container-123")


class TestOnPostRenderDisabled:
    def test_both_flags_disabled(self, plugin_config: dict[str, Any]) -> None:
        plugin = MetaPlugin(plugin_config)
        context = HookContext(
            hook=Hook.POST_RENDER,
            data={},
            shared={"video_url": "https://cdn.example.com/clip.mp4"},
        )

        with patch("reeln_meta_plugin.plugin.reels.create_reel_container") as mock_create:
            plugin.on_post_render(context)

        mock_create.assert_not_called()

    def test_only_publish_reels_disabled(self, plugin_config: dict[str, Any]) -> None:
        plugin_config["post_instagram_comment"] = False
        plugin_config["publish_reels"] = False
        plugin = MetaPlugin(plugin_config)
        context = HookContext(hook=Hook.POST_RENDER, data={})

        with patch("reeln_meta_plugin.plugin.reels.create_reel_container") as mock_create:
            plugin.on_post_render(context)

        mock_create.assert_not_called()


class TestOnPostRenderReels:
    def _reels_plugin(self, plugin_config: dict[str, Any]) -> MetaPlugin:
        plugin_config.update({
            "publish_reels": True,
            "instagram_account_id": "ig-456",
        })
        plugin = MetaPlugin(plugin_config)
        plugin._access_token = "test-access-token-123"
        plugin._game_info = FakeGameInfo()
        return plugin

    def test_full_flow(self, plugin_config: dict[str, Any]) -> None:
        plugin = self._reels_plugin(plugin_config)
        context = HookContext(
            hook=Hook.POST_RENDER,
            data={},
            shared={"video_url": "https://cdn.example.com/clip.mp4"},
        )

        with (
            patch(
                "reeln_meta_plugin.plugin.reels.create_reel_container",
                return_value=_FAKE_CONTAINER,
            ),
            patch("reeln_meta_plugin.plugin.reels.poll_container_status", return_value="FINISHED"),
            patch("reeln_meta_plugin.plugin.reels.publish_reel", return_value="media-789"),
            patch(
                "reeln_meta_plugin.plugin.reels.get_permalink",
                return_value="https://www.instagram.com/reel/abc/",
            ),
        ):
            plugin.on_post_render(context)

        assert context.shared["reels"]["meta"] == "https://www.instagram.com/reel/abc/"
        assert plugin._published_reel_id == "media-789"

    def test_missing_ig_account_id(
        self, plugin_config: dict[str, Any], caplog: pytest.LogCaptureFixture
    ) -> None:
        plugin_config["publish_reels"] = True
        # No instagram_account_id
        plugin = MetaPlugin(plugin_config)
        context = HookContext(
            hook=Hook.POST_RENDER,
            data={},
            shared={"video_url": "https://cdn.example.com/clip.mp4"},
        )

        with caplog.at_level(logging.WARNING):
            plugin.on_post_render(context)

        assert "instagram_account_id not configured" in caplog.text

    def test_missing_video_url(
        self, plugin_config: dict[str, Any], caplog: pytest.LogCaptureFixture
    ) -> None:
        plugin = self._reels_plugin(plugin_config)
        context = HookContext(hook=Hook.POST_RENDER, data={}, shared={})

        with caplog.at_level(logging.WARNING):
            plugin.on_post_render(context)

        assert "no video_url" in caplog.text

    def test_auth_failure(self, plugin_config: dict[str, Any]) -> None:
        plugin_config.update({
            "publish_reels": True,
            "instagram_account_id": "ig-456",
        })
        plugin = MetaPlugin(plugin_config)
        # No cached token, mock auth to fail
        context = HookContext(
            hook=Hook.POST_RENDER,
            data={},
            shared={"video_url": "https://cdn.example.com/clip.mp4"},
        )

        with (
            patch(
                "reeln_meta_plugin.plugin.auth.read_token",
                side_effect=AuthError("bad token"),
            ),
            patch("reeln_meta_plugin.plugin.reels.create_reel_container") as mock_create,
        ):
            plugin.on_post_render(context)

        mock_create.assert_not_called()

    def test_dry_run(
        self, plugin_config: dict[str, Any], caplog: pytest.LogCaptureFixture
    ) -> None:
        plugin_config["dry_run"] = True
        plugin = self._reels_plugin(plugin_config)
        context = HookContext(
            hook=Hook.POST_RENDER,
            data={},
            shared={"video_url": "https://cdn.example.com/clip.mp4"},
        )

        with (
            patch("reeln_meta_plugin.plugin.reels.create_reel_container") as mock_create,
            caplog.at_level(logging.INFO),
        ):
            plugin.on_post_render(context)

        mock_create.assert_not_called()
        assert "DRY RUN" in caplog.text
        assert "would publish Reel" in caplog.text

    def test_container_creation_failure(
        self, plugin_config: dict[str, Any], caplog: pytest.LogCaptureFixture
    ) -> None:
        plugin = self._reels_plugin(plugin_config)
        context = HookContext(
            hook=Hook.POST_RENDER,
            data={},
            shared={"video_url": "https://cdn.example.com/clip.mp4"},
        )

        with (
            patch(
                "reeln_meta_plugin.plugin.reels.create_reel_container",
                side_effect=ReelsError("api error"),
            ),
            caplog.at_level(logging.WARNING),
        ):
            plugin.on_post_render(context)

        # _do_ig_reel_publish lets the ReelsError propagate; the wrapper
        # catches it and logs a single consolidated "Reel publish failed"
        # message with the underlying exception text.
        assert "Reel publish failed" in caplog.text
        assert "api error" in caplog.text
        assert plugin._published_reel_id is None

    def test_polling_failure(
        self, plugin_config: dict[str, Any], caplog: pytest.LogCaptureFixture
    ) -> None:
        plugin = self._reels_plugin(plugin_config)
        context = HookContext(
            hook=Hook.POST_RENDER,
            data={},
            shared={"video_url": "https://cdn.example.com/clip.mp4"},
        )

        with (
            patch(
                "reeln_meta_plugin.plugin.reels.create_reel_container",
                return_value=_FAKE_CONTAINER,
            ),
            patch(
                "reeln_meta_plugin.plugin.reels.poll_container_status",
                side_effect=ReelsError("timed out"),
            ),
            caplog.at_level(logging.WARNING),
        ):
            plugin.on_post_render(context)

        assert "Reel publish failed" in caplog.text
        assert "timed out" in caplog.text

    def test_publish_failure(
        self, plugin_config: dict[str, Any], caplog: pytest.LogCaptureFixture
    ) -> None:
        plugin = self._reels_plugin(plugin_config)
        context = HookContext(
            hook=Hook.POST_RENDER,
            data={},
            shared={"video_url": "https://cdn.example.com/clip.mp4"},
        )

        with (
            patch(
                "reeln_meta_plugin.plugin.reels.create_reel_container",
                return_value=_FAKE_CONTAINER,
            ),
            patch("reeln_meta_plugin.plugin.reels.poll_container_status", return_value="FINISHED"),
            patch(
                "reeln_meta_plugin.plugin.reels.publish_reel",
                side_effect=ReelsError("publish error"),
            ),
            caplog.at_level(logging.WARNING),
        ):
            plugin.on_post_render(context)

        assert "Reel publish failed" in caplog.text

    def test_permalink_failure_nonfatal(
        self, plugin_config: dict[str, Any], caplog: pytest.LogCaptureFixture
    ) -> None:
        plugin = self._reels_plugin(plugin_config)
        context = HookContext(
            hook=Hook.POST_RENDER,
            data={},
            shared={"video_url": "https://cdn.example.com/clip.mp4"},
        )

        with (
            patch(
                "reeln_meta_plugin.plugin.reels.create_reel_container",
                return_value=_FAKE_CONTAINER,
            ),
            patch("reeln_meta_plugin.plugin.reels.poll_container_status", return_value="FINISHED"),
            patch("reeln_meta_plugin.plugin.reels.publish_reel", return_value="media-789"),
            patch(
                "reeln_meta_plugin.plugin.reels.get_permalink",
                side_effect=ReelsError("permalink error"),
            ),
            caplog.at_level(logging.WARNING),
        ):
            plugin.on_post_render(context)

        assert "permalink retrieval failed" in caplog.text
        # Reel still counts as published
        assert plugin._published_reel_id == "media-789"
        assert context.shared["reels"]["meta"] == ""

    def test_caption_from_template(self, plugin_config: dict[str, Any]) -> None:
        plugin = self._reels_plugin(plugin_config)
        plugin._config["reel_caption_template"] = "{home_team} vs {away_team} highlights"
        context = HookContext(
            hook=Hook.POST_RENDER,
            data={},
            shared={"video_url": "https://cdn.example.com/clip.mp4"},
        )

        with (
            patch(
                "reeln_meta_plugin.plugin.reels.create_reel_container",
                return_value=_FAKE_CONTAINER,
            ) as mock_create,
            patch("reeln_meta_plugin.plugin.reels.poll_container_status", return_value="FINISHED"),
            patch("reeln_meta_plugin.plugin.reels.publish_reel", return_value="media-789"),
            patch("reeln_meta_plugin.plugin.reels.get_permalink", return_value="https://ig.com/r/1"),
        ):
            plugin.on_post_render(context)

        assert mock_create.call_args[1]["caption"] == "Eagles vs Hawks highlights"

    def test_caption_fallback_to_title(self, plugin_config: dict[str, Any]) -> None:
        plugin = self._reels_plugin(plugin_config)
        # No caption template, should fall back to _build_title
        context = HookContext(
            hook=Hook.POST_RENDER,
            data={},
            shared={"video_url": "https://cdn.example.com/clip.mp4"},
        )

        with (
            patch(
                "reeln_meta_plugin.plugin.reels.create_reel_container",
                return_value=_FAKE_CONTAINER,
            ) as mock_create,
            patch("reeln_meta_plugin.plugin.reels.poll_container_status", return_value="FINISHED"),
            patch("reeln_meta_plugin.plugin.reels.publish_reel", return_value="media-789"),
            patch("reeln_meta_plugin.plugin.reels.get_permalink", return_value="https://ig.com/r/1"),
        ):
            plugin.on_post_render(context)

        assert "Eagles vs Hawks" in mock_create.call_args[1]["caption"]

    def test_caption_fallback_no_game_info(self, plugin_config: dict[str, Any]) -> None:
        plugin = self._reels_plugin(plugin_config)
        plugin._game_info = None
        context = HookContext(
            hook=Hook.POST_RENDER,
            data={},
            shared={"video_url": "https://cdn.example.com/clip.mp4"},
        )

        with (
            patch(
                "reeln_meta_plugin.plugin.reels.create_reel_container",
                return_value=_FAKE_CONTAINER,
            ) as mock_create,
            patch("reeln_meta_plugin.plugin.reels.poll_container_status", return_value="FINISHED"),
            patch("reeln_meta_plugin.plugin.reels.publish_reel", return_value="media-789"),
            patch("reeln_meta_plugin.plugin.reels.get_permalink", return_value="https://ig.com/r/1"),
        ):
            plugin.on_post_render(context)

        assert mock_create.call_args[1]["caption"] == ""

    def test_custom_reel_settings(self, plugin_config: dict[str, Any]) -> None:
        plugin = self._reels_plugin(plugin_config)
        plugin._config.update({
            "reel_share_to_feed": False,
            "reel_thumb_offset_ms": 3000,
            "reel_poll_max_attempts": 10,
            "reel_poll_interval_seconds": 2,
            "graph_api_version": "v23.0",
        })
        context = HookContext(
            hook=Hook.POST_RENDER,
            data={},
            shared={"video_url": "https://cdn.example.com/clip.mp4"},
        )

        with (
            patch(
                "reeln_meta_plugin.plugin.reels.create_reel_container",
                return_value=_FAKE_CONTAINER,
            ) as mock_create,
            patch(
                "reeln_meta_plugin.plugin.reels.poll_container_status",
                return_value="FINISHED",
            ) as mock_poll,
            patch("reeln_meta_plugin.plugin.reels.publish_reel", return_value="media-789"),
            patch("reeln_meta_plugin.plugin.reels.get_permalink", return_value="https://ig.com/r/1"),
        ):
            plugin.on_post_render(context)

        create_kwargs = mock_create.call_args[1]
        assert create_kwargs["share_to_feed"] is False
        assert create_kwargs["thumb_offset"] == 3000
        assert create_kwargs["api_version"] == "v23.0"

        poll_kwargs = mock_poll.call_args[1]
        assert poll_kwargs["max_attempts"] == 10
        assert poll_kwargs["poll_interval"] == 2.0

    def test_logs_info_on_success(
        self, plugin_config: dict[str, Any], caplog: pytest.LogCaptureFixture
    ) -> None:
        plugin = self._reels_plugin(plugin_config)
        context = HookContext(
            hook=Hook.POST_RENDER,
            data={},
            shared={"video_url": "https://cdn.example.com/clip.mp4"},
        )

        with (
            patch(
                "reeln_meta_plugin.plugin.reels.create_reel_container",
                return_value=_FAKE_CONTAINER,
            ),
            patch("reeln_meta_plugin.plugin.reels.poll_container_status", return_value="FINISHED"),
            patch("reeln_meta_plugin.plugin.reels.publish_reel", return_value="media-789"),
            patch(
                "reeln_meta_plugin.plugin.reels.get_permalink",
                return_value="https://www.instagram.com/reel/abc/",
            ),
            caplog.at_level(logging.INFO),
        ):
            plugin.on_post_render(context)

        assert "published Reel" in caplog.text
        assert "media-789" in caplog.text


class TestOnPostRenderComments:
    def _comment_plugin(self, plugin_config: dict[str, Any]) -> MetaPlugin:
        plugin_config.update({
            "post_instagram_comment": True,
            "instagram_account_id": "ig-456",
            "instagram_comment_template": "Great game, {home_team}!",
        })
        plugin = MetaPlugin(plugin_config)
        plugin._access_token = "test-access-token-123"
        plugin._game_info = FakeGameInfo()
        plugin._published_reel_id = "media-789"
        return plugin

    def test_posts_comment(self, plugin_config: dict[str, Any]) -> None:
        plugin = self._comment_plugin(plugin_config)
        context = HookContext(hook=Hook.POST_RENDER, data={})

        with patch(
            "reeln_meta_plugin.plugin.comments.post_comment",
            return_value=CommentResult(comment_id="cmt-1"),
        ) as mock_comment:
            plugin.on_post_render(context)

        mock_comment.assert_called_once_with(
            media_id="media-789",
            access_token="test-access-token-123",
            message="Great game, Eagles!",
            api_version="v24.0",
        )

    def test_skips_when_no_published_reel(self, plugin_config: dict[str, Any]) -> None:
        plugin = self._comment_plugin(plugin_config)
        plugin._published_reel_id = None
        context = HookContext(hook=Hook.POST_RENDER, data={})

        with patch("reeln_meta_plugin.plugin.comments.post_comment") as mock_comment:
            plugin.on_post_render(context)

        mock_comment.assert_not_called()

    def test_skips_when_template_empty(
        self, plugin_config: dict[str, Any], caplog: pytest.LogCaptureFixture
    ) -> None:
        plugin = self._comment_plugin(plugin_config)
        plugin._config["instagram_comment_template"] = ""
        context = HookContext(hook=Hook.POST_RENDER, data={})

        with (
            patch("reeln_meta_plugin.plugin.comments.post_comment") as mock_comment,
            caplog.at_level(logging.WARNING),
        ):
            plugin.on_post_render(context)

        mock_comment.assert_not_called()
        assert "instagram_comment_template is empty" in caplog.text

    def test_dry_run(
        self, plugin_config: dict[str, Any], caplog: pytest.LogCaptureFixture
    ) -> None:
        plugin = self._comment_plugin(plugin_config)
        plugin._config["dry_run"] = True
        context = HookContext(hook=Hook.POST_RENDER, data={})

        with (
            patch("reeln_meta_plugin.plugin.comments.post_comment") as mock_comment,
            caplog.at_level(logging.INFO),
        ):
            plugin.on_post_render(context)

        mock_comment.assert_not_called()
        assert "DRY RUN" in caplog.text
        assert "would post comment" in caplog.text

    def test_comment_error_nonfatal(
        self, plugin_config: dict[str, Any], caplog: pytest.LogCaptureFixture
    ) -> None:
        plugin = self._comment_plugin(plugin_config)
        context = HookContext(hook=Hook.POST_RENDER, data={})

        with (
            patch(
                "reeln_meta_plugin.plugin.comments.post_comment",
                side_effect=CommentError("api error"),
            ),
            caplog.at_level(logging.WARNING),
        ):
            plugin.on_post_render(context)

        assert "comment posting failed" in caplog.text

    def test_logs_info_on_success(
        self, plugin_config: dict[str, Any], caplog: pytest.LogCaptureFixture
    ) -> None:
        plugin = self._comment_plugin(plugin_config)
        context = HookContext(hook=Hook.POST_RENDER, data={})

        with (
            patch(
                "reeln_meta_plugin.plugin.comments.post_comment",
                return_value=CommentResult(comment_id="cmt-1"),
            ),
            caplog.at_level(logging.INFO),
        ):
            plugin.on_post_render(context)

        assert "posted comment" in caplog.text
        assert "cmt-1" in caplog.text


class TestOnPostRenderBothEnabled:
    def test_reels_then_comment(self, plugin_config: dict[str, Any]) -> None:
        plugin_config.update({
            "publish_reels": True,
            "post_instagram_comment": True,
            "instagram_account_id": "ig-456",
            "instagram_comment_template": "GG!",
        })
        plugin = MetaPlugin(plugin_config)
        plugin._access_token = "test-access-token-123"
        plugin._game_info = FakeGameInfo()
        context = HookContext(
            hook=Hook.POST_RENDER,
            data={},
            shared={"video_url": "https://cdn.example.com/clip.mp4"},
        )

        with (
            patch(
                "reeln_meta_plugin.plugin.reels.create_reel_container",
                return_value=_FAKE_CONTAINER,
            ),
            patch("reeln_meta_plugin.plugin.reels.poll_container_status", return_value="FINISHED"),
            patch("reeln_meta_plugin.plugin.reels.publish_reel", return_value="media-789"),
            patch("reeln_meta_plugin.plugin.reels.get_permalink", return_value="https://ig.com/r/1"),
            patch(
                "reeln_meta_plugin.plugin.comments.post_comment",
                return_value=CommentResult(comment_id="cmt-1"),
            ) as mock_comment,
        ):
            plugin.on_post_render(context)

        # Reel was published and comment was posted on it
        assert plugin._published_reel_id == "media-789"
        mock_comment.assert_called_once()
        assert mock_comment.call_args[1]["media_id"] == "media-789"

    def test_reel_fails_comment_skipped(self, plugin_config: dict[str, Any]) -> None:
        plugin_config.update({
            "publish_reels": True,
            "post_instagram_comment": True,
            "instagram_account_id": "ig-456",
            "instagram_comment_template": "GG!",
        })
        plugin = MetaPlugin(plugin_config)
        plugin._access_token = "test-access-token-123"
        plugin._game_info = FakeGameInfo()
        context = HookContext(
            hook=Hook.POST_RENDER,
            data={},
            shared={"video_url": "https://cdn.example.com/clip.mp4"},
        )

        with (
            patch(
                "reeln_meta_plugin.plugin.reels.create_reel_container",
                side_effect=ReelsError("api error"),
            ),
            patch("reeln_meta_plugin.plugin.comments.post_comment") as mock_comment,
        ):
            plugin.on_post_render(context)

        # No reel → no comment
        mock_comment.assert_not_called()


class TestOnPostRenderGameInfoFromHookData:
    def test_caches_game_info_from_hook_data(self, plugin_config: dict[str, Any]) -> None:
        """When create_livestream is disabled, game_info comes from hook data."""
        plugin_config.update({
            "publish_reels": True,
            "instagram_account_id": "ig-456",
            "create_livestream": False,
        })
        plugin = MetaPlugin(plugin_config)
        plugin._access_token = "test-access-token-123"
        assert plugin._game_info is None

        game_info = FakeGameInfo(home_team="Storm", away_team="Thunder")
        context = HookContext(
            hook=Hook.POST_RENDER,
            data={"game_info": game_info},
            shared={"video_url": "https://cdn.example.com/clip.mp4"},
        )

        with (
            patch(
                "reeln_meta_plugin.plugin.reels.create_reel_container",
                return_value=ReelContainerResult(container_id="c-1"),
            ),
            patch("reeln_meta_plugin.plugin.reels.poll_container_status", return_value="FINISHED"),
            patch("reeln_meta_plugin.plugin.reels.publish_reel", return_value="media-1"),
            patch("reeln_meta_plugin.plugin.reels.get_permalink", return_value="https://ig.com/r/1"),
        ):
            plugin.on_post_render(context)

        assert plugin._game_info is game_info

    def test_does_not_overwrite_existing_game_info(self, plugin_config: dict[str, Any]) -> None:
        plugin_config.update({
            "publish_reels": True,
            "instagram_account_id": "ig-456",
        })
        plugin = MetaPlugin(plugin_config)
        plugin._access_token = "test-access-token-123"
        original_info = FakeGameInfo(home_team="Eagles")
        plugin._game_info = original_info

        context = HookContext(
            hook=Hook.POST_RENDER,
            data={"game_info": FakeGameInfo(home_team="Storm")},
            shared={"video_url": "https://cdn.example.com/clip.mp4"},
        )

        with (
            patch(
                "reeln_meta_plugin.plugin.reels.create_reel_container",
                return_value=ReelContainerResult(container_id="c-1"),
            ),
            patch("reeln_meta_plugin.plugin.reels.poll_container_status", return_value="FINISHED"),
            patch("reeln_meta_plugin.plugin.reels.publish_reel", return_value="media-1"),
            patch("reeln_meta_plugin.plugin.reels.get_permalink", return_value="https://ig.com/r/1"),
        ):
            plugin.on_post_render(context)

        assert plugin._game_info is original_info


class TestBuildCaption:
    def test_with_template(self) -> None:
        plugin = MetaPlugin({"reel_caption_template": "{home_team} vs {away_team}"})
        plugin._game_info = FakeGameInfo()
        assert plugin._build_caption() == "Eagles vs Hawks"

    def test_fallback_to_title(self) -> None:
        plugin = MetaPlugin({})
        plugin._game_info = FakeGameInfo()
        assert "Eagles vs Hawks" in plugin._build_caption()

    def test_no_game_info_no_template(self) -> None:
        plugin = MetaPlugin({})
        assert plugin._build_caption() == ""

    def test_unknown_placeholder_safe(self) -> None:
        plugin = MetaPlugin({"reel_caption_template": "{home_team} {unknown_field}"})
        plugin._game_info = FakeGameInfo()
        assert plugin._build_caption() == "Eagles "

    def test_render_metadata_preferred(self) -> None:
        plugin = MetaPlugin({"reel_caption_template": "{home_team} vs {away_team}"})
        plugin._game_info = FakeGameInfo()
        context = HookContext(
            hook=Hook.POST_RENDER,
            data={},
            shared={"render_metadata": {"title": "AI Title", "description": "AI generated caption"}},
        )
        assert plugin._build_caption(context) == "AI generated caption"

    def test_render_metadata_empty_falls_through(self) -> None:
        plugin = MetaPlugin({"reel_caption_template": "{home_team} vs {away_team}"})
        plugin._game_info = FakeGameInfo()
        context = HookContext(
            hook=Hook.POST_RENDER,
            data={},
            shared={"render_metadata": {"title": "AI Title", "description": ""}},
        )
        assert plugin._build_caption(context) == "Eagles vs Hawks"

    def test_render_metadata_missing_falls_through(self) -> None:
        plugin = MetaPlugin({"reel_caption_template": "{home_team} vs {away_team}"})
        plugin._game_info = FakeGameInfo()
        context = HookContext(hook=Hook.POST_RENDER, data={}, shared={})
        assert plugin._build_caption(context) == "Eagles vs Hawks"

    def test_no_context_uses_template(self) -> None:
        plugin = MetaPlugin({"reel_caption_template": "{home_team} vs {away_team}"})
        plugin._game_info = FakeGameInfo()
        assert plugin._build_caption() == "Eagles vs Hawks"


class TestBuildComment:
    def test_with_template(self) -> None:
        plugin = MetaPlugin({"instagram_comment_template": "Go {home_team}!"})
        plugin._game_info = FakeGameInfo()
        assert plugin._build_comment() == "Go Eagles!"

    def test_empty_template(self) -> None:
        plugin = MetaPlugin({})
        assert plugin._build_comment() == ""

    def test_no_game_info(self) -> None:
        plugin = MetaPlugin({"instagram_comment_template": "{home_team} rules"})
        assert plugin._build_comment() == " rules"


class TestRenderTemplate:
    def test_all_fields(self) -> None:
        plugin = MetaPlugin({})
        plugin._game_info = FakeGameInfo(
            home_team="Eagles",
            away_team="Hawks",
            date="2026-01-15",
            venue="Arena",
            sport="hockey",
        )
        result = plugin._render_template(
            "{home_team} vs {away_team} on {date} at {venue} ({sport})"
        )
        assert result == "Eagles vs Hawks on 2026-01-15 at Arena (hockey)"

    def test_missing_key_returns_empty(self) -> None:
        plugin = MetaPlugin({})
        plugin._game_info = FakeGameInfo()
        result = plugin._render_template("{nonexistent}")
        assert result == ""


class TestIntegrationWithRegistry:
    def test_full_lifecycle(self, plugin_config: dict[str, Any]) -> None:
        """Simulate the full plugin lifecycle: init -> ready -> finish."""
        plugin = MetaPlugin(plugin_config)
        registry = HookRegistry()
        plugin.register(registry)

        # ON_GAME_INIT — create livestream
        game_info = FakeGameInfo(home_team="Storm", away_team="Thunder")
        init_context = HookContext(hook=Hook.ON_GAME_INIT, data={"game_info": game_info})

        with patch(
            "reeln_meta_plugin.plugin.livestream.create_livestream",
            return_value=_FAKE_RESULT,
        ):
            registry.emit(Hook.ON_GAME_INIT, init_context)

        assert init_context.shared["livestreams"]["meta"] == _FAKE_RESULT.embed_url
        assert plugin._game_info is game_info
        assert plugin._access_token is not None
        assert plugin._livestream_id == "live-123"

        # ON_GAME_READY — update metadata and thumbnail
        ready_context = HookContext(
            hook=Hook.ON_GAME_READY,
            data={},
            shared={"livestream_metadata": {"title": "Storm vs Thunder - Updated"}},
        )

        with (
            patch("reeln_meta_plugin.plugin.livestream.update_livestream") as mock_update,
            patch("reeln_meta_plugin.plugin.livestream.upload_thumbnail"),
        ):
            registry.emit(Hook.ON_GAME_READY, ready_context)

        mock_update.assert_called_once()
        assert mock_update.call_args[1]["live_video_id"] == "live-123"
        assert mock_update.call_args[1]["title"] == "Storm vs Thunder - Updated"

        # ON_GAME_FINISH — reset state
        finish_context = HookContext(hook=Hook.ON_GAME_FINISH, data={})
        registry.emit(Hook.ON_GAME_FINISH, finish_context)

        assert plugin._access_token is None
        assert plugin._game_info is None
        assert plugin._livestream_id is None


# ------------------------------------------------------------------
# Facebook Reels
# ------------------------------------------------------------------

_FAKE_FB_START = ReelStartResult(
    video_id="fb-vid-123",
    upload_url="https://rupload.facebook.com/video-upload/v24.0/fb-vid-123",
)


class TestOnPostRenderFacebookReels:
    def _fb_reels_plugin(self, plugin_config: dict[str, Any]) -> MetaPlugin:
        plugin_config.update({
            "publish_facebook_reels": True,
            "page_id": "pg-123",
        })
        plugin = MetaPlugin(plugin_config)
        plugin._access_token = "test-access-token-123"
        plugin._game_info = FakeGameInfo()
        return plugin

    def test_full_flow(self, plugin_config: dict[str, Any]) -> None:
        plugin = self._fb_reels_plugin(plugin_config)
        context = HookContext(
            hook=Hook.POST_RENDER,
            data={},
            shared={"video_url": "https://cdn.example.com/clip.mp4"},
        )

        with (
            patch(
                "reeln_meta_plugin.plugin.facebook_reels.start_reel_upload",
                return_value=_FAKE_FB_START,
            ) as mock_start,
            patch("reeln_meta_plugin.plugin.facebook_reels.upload_reel_video") as mock_upload,
            patch("reeln_meta_plugin.plugin.facebook_reels.poll_reel_status", return_value="complete"),
            patch("reeln_meta_plugin.plugin.facebook_reels.finish_reel") as mock_finish,
        ):
            plugin.on_post_render(context)

        mock_start.assert_called_once()
        mock_upload.assert_called_once()
        assert mock_upload.call_args[1]["video_url"] == "https://cdn.example.com/clip.mp4"
        mock_finish.assert_called_once()
        assert context.shared["facebook_reels"]["meta"] == "fb-vid-123"

    def test_passes_correct_params(self, plugin_config: dict[str, Any]) -> None:
        plugin = self._fb_reels_plugin(plugin_config)
        plugin._config["graph_api_version"] = "v25.0"
        context = HookContext(
            hook=Hook.POST_RENDER,
            data={},
            shared={"video_url": "https://cdn.example.com/clip.mp4"},
        )

        with (
            patch(
                "reeln_meta_plugin.plugin.facebook_reels.start_reel_upload",
                return_value=_FAKE_FB_START,
            ) as mock_start,
            patch("reeln_meta_plugin.plugin.facebook_reels.upload_reel_video"),
            patch("reeln_meta_plugin.plugin.facebook_reels.poll_reel_status", return_value="complete"),
            patch("reeln_meta_plugin.plugin.facebook_reels.finish_reel") as mock_finish,
        ):
            plugin.on_post_render(context)

        start_kwargs = mock_start.call_args[1]
        assert start_kwargs["page_id"] == "pg-123"
        assert start_kwargs["access_token"] == "test-access-token-123"
        assert start_kwargs["api_version"] == "v25.0"

        finish_kwargs = mock_finish.call_args[1]
        assert finish_kwargs["page_id"] == "pg-123"
        assert finish_kwargs["video_id"] == "fb-vid-123"

    def test_missing_video_url(
        self, plugin_config: dict[str, Any], caplog: pytest.LogCaptureFixture,
    ) -> None:
        plugin = self._fb_reels_plugin(plugin_config)
        context = HookContext(hook=Hook.POST_RENDER, data={}, shared={})

        with caplog.at_level(logging.WARNING):
            plugin.on_post_render(context)

        assert "no video_url" in caplog.text

    def test_missing_page_id(
        self, plugin_config: dict[str, Any], caplog: pytest.LogCaptureFixture,
    ) -> None:
        plugin = self._fb_reels_plugin(plugin_config)
        plugin._config["page_id"] = ""
        context = HookContext(
            hook=Hook.POST_RENDER,
            data={},
            shared={"video_url": "https://cdn.example.com/clip.mp4"},
        )

        with caplog.at_level(logging.WARNING):
            plugin.on_post_render(context)

        assert "page_id not configured" in caplog.text

    def test_start_failure(
        self, plugin_config: dict[str, Any], caplog: pytest.LogCaptureFixture,
    ) -> None:
        plugin = self._fb_reels_plugin(plugin_config)
        context = HookContext(
            hook=Hook.POST_RENDER,
            data={},
            shared={"video_url": "https://cdn.example.com/clip.mp4"},
        )

        with (
            patch(
                "reeln_meta_plugin.plugin.facebook_reels.start_reel_upload",
                side_effect=FacebookReelsError("start failed"),
            ),
            caplog.at_level(logging.WARNING),
        ):
            plugin.on_post_render(context)

        # _do_fb_reel_publish lets the FacebookReelsError propagate; the
        # wrapper catches it with a single consolidated log message.
        assert "Facebook Reel publish failed" in caplog.text
        assert "start failed" in caplog.text
        assert "facebook_reels" not in context.shared

    def test_upload_failure(
        self, plugin_config: dict[str, Any], caplog: pytest.LogCaptureFixture,
    ) -> None:
        plugin = self._fb_reels_plugin(plugin_config)
        context = HookContext(
            hook=Hook.POST_RENDER,
            data={},
            shared={"video_url": "https://cdn.example.com/clip.mp4"},
        )

        with (
            patch(
                "reeln_meta_plugin.plugin.facebook_reels.start_reel_upload",
                return_value=_FAKE_FB_START,
            ),
            patch(
                "reeln_meta_plugin.plugin.facebook_reels.upload_reel_video",
                side_effect=FacebookReelsError("upload failed"),
            ),
            caplog.at_level(logging.WARNING),
        ):
            plugin.on_post_render(context)

        assert "Facebook Reel publish failed" in caplog.text
        assert "upload failed" in caplog.text

    def test_finish_failure(
        self, plugin_config: dict[str, Any], caplog: pytest.LogCaptureFixture,
    ) -> None:
        plugin = self._fb_reels_plugin(plugin_config)
        context = HookContext(
            hook=Hook.POST_RENDER,
            data={},
            shared={"video_url": "https://cdn.example.com/clip.mp4"},
        )

        with (
            patch(
                "reeln_meta_plugin.plugin.facebook_reels.start_reel_upload",
                return_value=_FAKE_FB_START,
            ),
            patch("reeln_meta_plugin.plugin.facebook_reels.upload_reel_video"),
            patch(
                "reeln_meta_plugin.plugin.facebook_reels.finish_reel",
                side_effect=FacebookReelsError("publish failed"),
            ),
            caplog.at_level(logging.WARNING),
        ):
            plugin.on_post_render(context)

        assert "Facebook Reel publish failed" in caplog.text

    def test_poll_failure(
        self, plugin_config: dict[str, Any], caplog: pytest.LogCaptureFixture,
    ) -> None:
        plugin = self._fb_reels_plugin(plugin_config)
        context = HookContext(
            hook=Hook.POST_RENDER,
            data={},
            shared={"video_url": "https://cdn.example.com/clip.mp4"},
        )

        with (
            patch(
                "reeln_meta_plugin.plugin.facebook_reels.start_reel_upload",
                return_value=_FAKE_FB_START,
            ),
            patch("reeln_meta_plugin.plugin.facebook_reels.upload_reel_video"),
            patch("reeln_meta_plugin.plugin.facebook_reels.finish_reel"),
            patch(
                "reeln_meta_plugin.plugin.facebook_reels.poll_reel_status",
                side_effect=FacebookReelsError("poll timeout"),
            ),
            caplog.at_level(logging.WARNING),
        ):
            plugin.on_post_render(context)

        assert "Facebook Reel publish failed" in caplog.text
        assert "poll timeout" in caplog.text

    def test_dry_run(
        self, plugin_config: dict[str, Any], caplog: pytest.LogCaptureFixture,
    ) -> None:
        plugin = self._fb_reels_plugin(plugin_config)
        plugin._config["dry_run"] = True
        context = HookContext(
            hook=Hook.POST_RENDER,
            data={},
            shared={"video_url": "https://cdn.example.com/clip.mp4"},
        )

        with (
            patch("reeln_meta_plugin.plugin.facebook_reels.start_reel_upload") as mock_start,
            caplog.at_level(logging.INFO),
        ):
            plugin.on_post_render(context)

        mock_start.assert_not_called()
        assert "DRY RUN" in caplog.text
        assert "would publish Facebook Reel" in caplog.text

    def test_uses_render_metadata_for_title_and_description(
        self, plugin_config: dict[str, Any],
    ) -> None:
        plugin = self._fb_reels_plugin(plugin_config)
        context = HookContext(
            hook=Hook.POST_RENDER,
            data={},
            shared={
                "video_url": "https://cdn.example.com/clip.mp4",
                "render_metadata": {"title": "AI Title", "description": "AI Desc"},
            },
        )

        with (
            patch(
                "reeln_meta_plugin.plugin.facebook_reels.start_reel_upload",
                return_value=_FAKE_FB_START,
            ),
            patch("reeln_meta_plugin.plugin.facebook_reels.upload_reel_video"),
            patch("reeln_meta_plugin.plugin.facebook_reels.poll_reel_status", return_value="complete"),
            patch("reeln_meta_plugin.plugin.facebook_reels.finish_reel") as mock_finish,
        ):
            plugin.on_post_render(context)

        finish_kwargs = mock_finish.call_args[1]
        assert finish_kwargs["title"] == "AI Title"
        assert finish_kwargs["description"] == "AI Desc"

    def test_falls_back_to_game_info_title(
        self, plugin_config: dict[str, Any],
    ) -> None:
        plugin = self._fb_reels_plugin(plugin_config)
        context = HookContext(
            hook=Hook.POST_RENDER,
            data={},
            shared={"video_url": "https://cdn.example.com/clip.mp4"},
        )

        with (
            patch(
                "reeln_meta_plugin.plugin.facebook_reels.start_reel_upload",
                return_value=_FAKE_FB_START,
            ),
            patch("reeln_meta_plugin.plugin.facebook_reels.upload_reel_video"),
            patch("reeln_meta_plugin.plugin.facebook_reels.poll_reel_status", return_value="complete"),
            patch("reeln_meta_plugin.plugin.facebook_reels.finish_reel") as mock_finish,
        ):
            plugin.on_post_render(context)

        finish_kwargs = mock_finish.call_args[1]
        assert "Eagles vs Hawks" in finish_kwargs["title"]
        assert finish_kwargs["description"] == ""

    def test_uses_description_template(
        self, plugin_config: dict[str, Any],
    ) -> None:
        plugin = self._fb_reels_plugin(plugin_config)
        plugin._config["facebook_reel_description_template"] = "{home_team} highlights!"
        context = HookContext(
            hook=Hook.POST_RENDER,
            data={},
            shared={"video_url": "https://cdn.example.com/clip.mp4"},
        )

        with (
            patch(
                "reeln_meta_plugin.plugin.facebook_reels.start_reel_upload",
                return_value=_FAKE_FB_START,
            ),
            patch("reeln_meta_plugin.plugin.facebook_reels.upload_reel_video"),
            patch("reeln_meta_plugin.plugin.facebook_reels.poll_reel_status", return_value="complete"),
            patch("reeln_meta_plugin.plugin.facebook_reels.finish_reel") as mock_finish,
        ):
            plugin.on_post_render(context)

        finish_kwargs = mock_finish.call_args[1]
        assert finish_kwargs["description"] == "Eagles highlights!"

    def test_uses_poll_config(self, plugin_config: dict[str, Any]) -> None:
        plugin = self._fb_reels_plugin(plugin_config)
        plugin._config["reel_poll_max_attempts"] = 10
        plugin._config["reel_poll_interval_seconds"] = 2
        context = HookContext(
            hook=Hook.POST_RENDER,
            data={},
            shared={"video_url": "https://cdn.example.com/clip.mp4"},
        )

        with (
            patch(
                "reeln_meta_plugin.plugin.facebook_reels.start_reel_upload",
                return_value=_FAKE_FB_START,
            ),
            patch("reeln_meta_plugin.plugin.facebook_reels.upload_reel_video"),
            patch("reeln_meta_plugin.plugin.facebook_reels.poll_reel_status", return_value="complete") as mock_poll,
            patch("reeln_meta_plugin.plugin.facebook_reels.finish_reel"),
        ):
            plugin.on_post_render(context)

        poll_kwargs = mock_poll.call_args[1]
        assert poll_kwargs["max_attempts"] == 10
        assert poll_kwargs["poll_interval"] == 2.0

    def test_logs_info_on_success(
        self, plugin_config: dict[str, Any], caplog: pytest.LogCaptureFixture,
    ) -> None:
        plugin = self._fb_reels_plugin(plugin_config)
        context = HookContext(
            hook=Hook.POST_RENDER,
            data={},
            shared={"video_url": "https://cdn.example.com/clip.mp4"},
        )

        with (
            patch(
                "reeln_meta_plugin.plugin.facebook_reels.start_reel_upload",
                return_value=_FAKE_FB_START,
            ),
            patch("reeln_meta_plugin.plugin.facebook_reels.upload_reel_video"),
            patch("reeln_meta_plugin.plugin.facebook_reels.poll_reel_status", return_value="complete"),
            patch("reeln_meta_plugin.plugin.facebook_reels.finish_reel"),
            caplog.at_level(logging.INFO),
        ):
            plugin.on_post_render(context)

        assert "published Facebook Reel" in caplog.text
        assert "fb-vid-123" in caplog.text

    def test_ig_not_required_for_fb_reels(self, plugin_config: dict[str, Any]) -> None:
        """Facebook Reels should work without instagram_account_id configured."""
        plugin_config.update({
            "publish_facebook_reels": True,
            "publish_reels": False,
            "page_id": "pg-123",
        })
        plugin = MetaPlugin(plugin_config)
        plugin._access_token = "test-access-token-123"
        plugin._game_info = FakeGameInfo()
        context = HookContext(
            hook=Hook.POST_RENDER,
            data={},
            shared={"video_url": "https://cdn.example.com/clip.mp4"},
        )

        with (
            patch(
                "reeln_meta_plugin.plugin.facebook_reels.start_reel_upload",
                return_value=_FAKE_FB_START,
            ),
            patch("reeln_meta_plugin.plugin.facebook_reels.upload_reel_video"),
            patch("reeln_meta_plugin.plugin.facebook_reels.poll_reel_status", return_value="complete"),
            patch("reeln_meta_plugin.plugin.facebook_reels.finish_reel"),
        ):
            plugin.on_post_render(context)

        assert context.shared["facebook_reels"]["meta"] == "fb-vid-123"


class TestBuildFacebookReelTitle:
    def test_render_metadata_preferred(self) -> None:
        plugin = MetaPlugin({"page_id": "pg-1"})
        plugin._game_info = FakeGameInfo()
        context = HookContext(
            hook=Hook.POST_RENDER,
            data={},
            shared={"render_metadata": {"title": "AI Title", "description": "AI Desc"}},
        )
        assert plugin._build_facebook_reel_title(context) == "AI Title"

    def test_falls_back_to_game_info(self) -> None:
        plugin = MetaPlugin({"page_id": "pg-1"})
        plugin._game_info = FakeGameInfo()
        context = HookContext(hook=Hook.POST_RENDER, data={}, shared={})
        assert "Eagles vs Hawks" in plugin._build_facebook_reel_title(context)

    def test_no_game_info(self) -> None:
        plugin = MetaPlugin({"page_id": "pg-1"})
        context = HookContext(hook=Hook.POST_RENDER, data={}, shared={})
        assert plugin._build_facebook_reel_title(context) == ""

    def test_empty_render_metadata_title_falls_through(self) -> None:
        plugin = MetaPlugin({"page_id": "pg-1"})
        plugin._game_info = FakeGameInfo()
        context = HookContext(
            hook=Hook.POST_RENDER,
            data={},
            shared={"render_metadata": {"title": "", "description": "Desc"}},
        )
        assert "Eagles vs Hawks" in plugin._build_facebook_reel_title(context)


class TestBuildFacebookReelDescription:
    def test_render_metadata_preferred(self) -> None:
        plugin = MetaPlugin({"page_id": "pg-1", "facebook_reel_description_template": "{home_team}!"})
        plugin._game_info = FakeGameInfo()
        context = HookContext(
            hook=Hook.POST_RENDER,
            data={},
            shared={"render_metadata": {"title": "T", "description": "AI Desc"}},
        )
        assert plugin._build_facebook_reel_description(context) == "AI Desc"

    def test_template_fallback(self) -> None:
        plugin = MetaPlugin({"page_id": "pg-1", "facebook_reel_description_template": "{home_team} highlights!"})
        plugin._game_info = FakeGameInfo()
        context = HookContext(hook=Hook.POST_RENDER, data={}, shared={})
        assert plugin._build_facebook_reel_description(context) == "Eagles highlights!"

    def test_no_render_metadata_no_template(self) -> None:
        plugin = MetaPlugin({"page_id": "pg-1"})
        context = HookContext(hook=Hook.POST_RENDER, data={}, shared={})
        assert plugin._build_facebook_reel_description(context) == ""

    def test_empty_render_metadata_falls_to_template(self) -> None:
        plugin = MetaPlugin({"page_id": "pg-1", "facebook_reel_description_template": "Go {home_team}!"})
        plugin._game_info = FakeGameInfo()
        context = HookContext(
            hook=Hook.POST_RENDER,
            data={},
            shared={"render_metadata": {"title": "T", "description": ""}},
        )
        assert plugin._build_facebook_reel_description(context) == "Go Eagles!"


# ------------------------------------------------------------------
# upload() — Uploader protocol for manual publish (reeln queue publish)
# ------------------------------------------------------------------


_CDN_URL = "https://cdn.example.com/clip.mp4"


def _make_meta_plugin(plugin_config: dict[str, Any], **overrides: Any) -> MetaPlugin:
    """Build a MetaPlugin with publishable defaults and test-stubbed auth."""
    cfg = dict(plugin_config)
    cfg.update(
        {
            "publish_reels": True,
            "instagram_account_id": "ig-456",
            "page_id": "pg-123",
            "reel_caption_template": "",
            "facebook_reel_description_template": "",
        }
    )
    cfg.update(overrides)
    plugin = MetaPlugin(cfg)
    plugin._access_token = "test-access-token-123"
    return plugin


class TestUpload:
    """Tests for the ``upload()`` method used by ``reeln queue publish``.

    Meta is unusual among uploaders: it doesn't upload raw files — it
    publishes Reels from a pre-existing hosted URL that upstream
    uploaders (cloudflare) wrote into ``metadata["video_url"]``. The
    ``path`` arg is accepted to satisfy the protocol but ignored.
    """

    def test_upload_no_flags_raises_skipped(
        self, plugin_config: dict[str, Any], tmp_path: Path
    ) -> None:
        from reeln.plugins.capabilities import UploaderSkipped

        # plugin_config has no publish flags enabled
        video = tmp_path / "clip.mp4"
        video.write_text("x")
        plugin = MetaPlugin(plugin_config)

        with pytest.raises(UploaderSkipped, match="no meta publishing flags"):
            plugin.upload(video, metadata={"video_url": _CDN_URL})

    def test_upload_missing_video_url_raises_skipped(
        self, plugin_config: dict[str, Any], tmp_path: Path
    ) -> None:
        from reeln.plugins.capabilities import UploaderSkipped

        video = tmp_path / "clip.mp4"
        video.write_text("x")
        plugin = _make_meta_plugin(plugin_config)

        with pytest.raises(UploaderSkipped, match="video_url"):
            plugin.upload(video, metadata={})

    def test_upload_missing_video_url_comment_only_does_not_raise(
        self, plugin_config: dict[str, Any], tmp_path: Path
    ) -> None:
        """When only post_instagram_comment is enabled (no publish), no
        video_url is required because comments don't need one."""
        video = tmp_path / "clip.mp4"
        video.write_text("x")
        plugin = _make_meta_plugin(
            plugin_config,
            publish_reels=False,
            publish_facebook_reels=False,
            post_instagram_comment=True,
        )
        plugin._published_reel_id = None  # no existing reel to comment on

        # No video_url, no reel to comment on — primary_url stays empty and
        # upload returns the sentinel without error.
        url = plugin.upload(video, metadata={})
        assert "meta:" in url

    def test_upload_auth_failure_raises_runtime_error(
        self, plugin_config: dict[str, Any], tmp_path: Path
    ) -> None:
        video = tmp_path / "clip.mp4"
        video.write_text("x")
        plugin = _make_meta_plugin(plugin_config)
        plugin._access_token = None

        with patch(
            "reeln_meta_plugin.plugin.auth.read_token",
            side_effect=AuthError("bad token"),
        ), pytest.raises(RuntimeError, match="authentication"):
            plugin.upload(video, metadata={"video_url": _CDN_URL})

    def test_upload_ig_missing_account_id_raises(
        self, plugin_config: dict[str, Any], tmp_path: Path
    ) -> None:
        video = tmp_path / "clip.mp4"
        video.write_text("x")
        plugin = _make_meta_plugin(plugin_config, instagram_account_id="")

        with pytest.raises(RuntimeError, match="instagram_account_id"):
            plugin.upload(video, metadata={"video_url": _CDN_URL})

    def test_upload_fb_missing_page_id_raises(
        self, plugin_config: dict[str, Any], tmp_path: Path
    ) -> None:
        video = tmp_path / "clip.mp4"
        video.write_text("x")
        plugin = _make_meta_plugin(
            plugin_config,
            publish_reels=False,
            publish_facebook_reels=True,
            page_id="",
        )

        with pytest.raises(RuntimeError, match="page_id"):
            plugin.upload(video, metadata={"video_url": _CDN_URL})

    def test_upload_ig_reel_success_returns_permalink(
        self, plugin_config: dict[str, Any], tmp_path: Path
    ) -> None:
        video = tmp_path / "clip.mp4"
        video.write_text("x")
        plugin = _make_meta_plugin(plugin_config)

        with (
            patch(
                "reeln_meta_plugin.plugin.reels.create_reel_container",
                return_value=_FAKE_CONTAINER,
            ),
            patch("reeln_meta_plugin.plugin.reels.poll_container_status"),
            patch(
                "reeln_meta_plugin.plugin.reels.publish_reel",
                return_value="media-abc",
            ),
            patch(
                "reeln_meta_plugin.plugin.reels.get_permalink",
                return_value="https://instagram.com/reel/abc",
            ),
        ):
            url = plugin.upload(
                video,
                metadata={
                    "video_url": _CDN_URL,
                    "title": "Goal!",
                    "description": "What a shot",
                    "home_team": "Eagles",
                    "away_team": "Hawks",
                },
            )

        assert url == "https://instagram.com/reel/abc"
        assert plugin._published_reel_id == "media-abc"

    def test_upload_ig_reel_error_when_only_target_propagates_as_runtime_error(
        self, plugin_config: dict[str, Any], tmp_path: Path
    ) -> None:
        """When IG is the ONLY publish target and it fails, the overall
        upload fails with a RuntimeError wrapping the IG error. The raw
        ReelsError is collected per-sub-operation, not propagated."""
        video = tmp_path / "clip.mp4"
        video.write_text("x")
        plugin = _make_meta_plugin(plugin_config)

        with patch(
            "reeln_meta_plugin.plugin.reels.create_reel_container",
            side_effect=ReelsError("container failed"),
        ), pytest.raises(RuntimeError, match=r"IG Reel.*container failed"):
            plugin.upload(video, metadata={"video_url": _CDN_URL})

    def test_upload_ig_reel_dry_run_returns_sentinel(
        self, plugin_config: dict[str, Any], tmp_path: Path
    ) -> None:
        video = tmp_path / "clip.mp4"
        video.write_text("x")
        plugin = _make_meta_plugin(plugin_config, dry_run=True)

        with patch(
            "reeln_meta_plugin.plugin.reels.create_reel_container"
        ) as mock_create:
            url = plugin.upload(video, metadata={"video_url": _CDN_URL})

        assert url == "meta:dry_run"
        mock_create.assert_not_called()

    def test_upload_fb_reel_success_returns_url(
        self, plugin_config: dict[str, Any], tmp_path: Path
    ) -> None:
        video = tmp_path / "clip.mp4"
        video.write_text("x")
        plugin = _make_meta_plugin(
            plugin_config,
            publish_reels=False,
            publish_facebook_reels=True,
        )

        with (
            patch(
                "reeln_meta_plugin.plugin.facebook_reels.start_reel_upload",
                return_value=_FAKE_FB_START,
            ),
            patch("reeln_meta_plugin.plugin.facebook_reels.upload_reel_video"),
            patch("reeln_meta_plugin.plugin.facebook_reels.finish_reel"),
            patch("reeln_meta_plugin.plugin.facebook_reels.poll_reel_status"),
        ):
            url = plugin.upload(
                video,
                metadata={
                    "video_url": _CDN_URL,
                    "title": "Goal!",
                    "description": "Description",
                },
            )

        assert "facebook.com/pg-123/videos/fb-vid-123" in url

    def test_upload_fb_reel_error_when_only_target_propagates_as_runtime_error(
        self, plugin_config: dict[str, Any], tmp_path: Path
    ) -> None:
        """When FB is the ONLY publish target and it fails, the overall
        upload fails with a RuntimeError wrapping the FB error."""
        video = tmp_path / "clip.mp4"
        video.write_text("x")
        plugin = _make_meta_plugin(
            plugin_config,
            publish_reels=False,
            publish_facebook_reels=True,
        )

        with patch(
            "reeln_meta_plugin.plugin.facebook_reels.start_reel_upload",
            side_effect=FacebookReelsError("start failed"),
        ), pytest.raises(
            RuntimeError, match=r"Facebook Reel.*start failed"
        ):
            plugin.upload(video, metadata={"video_url": _CDN_URL})

    def test_upload_ig_and_fb_prefers_ig_permalink(
        self, plugin_config: dict[str, Any], tmp_path: Path
    ) -> None:
        video = tmp_path / "clip.mp4"
        video.write_text("x")
        plugin = _make_meta_plugin(plugin_config, publish_facebook_reels=True)

        with (
            patch(
                "reeln_meta_plugin.plugin.reels.create_reel_container",
                return_value=_FAKE_CONTAINER,
            ),
            patch("reeln_meta_plugin.plugin.reels.poll_container_status"),
            patch(
                "reeln_meta_plugin.plugin.reels.publish_reel",
                return_value="media-abc",
            ),
            patch(
                "reeln_meta_plugin.plugin.reels.get_permalink",
                return_value="https://instagram.com/reel/abc",
            ),
            patch(
                "reeln_meta_plugin.plugin.facebook_reels.start_reel_upload",
                return_value=_FAKE_FB_START,
            ),
            patch("reeln_meta_plugin.plugin.facebook_reels.upload_reel_video"),
            patch("reeln_meta_plugin.plugin.facebook_reels.finish_reel"),
            patch("reeln_meta_plugin.plugin.facebook_reels.poll_reel_status"),
        ):
            url = plugin.upload(video, metadata={"video_url": _CDN_URL})

        assert url == "https://instagram.com/reel/abc"

    def test_upload_comment_success(
        self, plugin_config: dict[str, Any], tmp_path: Path
    ) -> None:
        video = tmp_path / "clip.mp4"
        video.write_text("x")
        plugin = _make_meta_plugin(
            plugin_config,
            post_instagram_comment=True,
            instagram_comment_template="Go {home_team}!",
        )
        plugin._published_reel_id = "media-xyz"

        with (
            patch(
                "reeln_meta_plugin.plugin.reels.create_reel_container",
                return_value=_FAKE_CONTAINER,
            ),
            patch("reeln_meta_plugin.plugin.reels.poll_container_status"),
            patch(
                "reeln_meta_plugin.plugin.reels.publish_reel",
                return_value="media-abc",
            ),
            patch(
                "reeln_meta_plugin.plugin.reels.get_permalink",
                return_value="https://instagram.com/reel/abc",
            ),
            patch(
                "reeln_meta_plugin.plugin.comments.post_comment",
                return_value=MagicMock(comment_id="c-1"),
            ) as mock_comment,
        ):
            plugin.upload(
                video,
                metadata={
                    "video_url": _CDN_URL,
                    "home_team": "Eagles",
                    "away_team": "Hawks",
                },
            )

        mock_comment.assert_called_once()

    def test_upload_comment_failure_non_fatal(
        self, plugin_config: dict[str, Any], tmp_path: Path
    ) -> None:
        video = tmp_path / "clip.mp4"
        video.write_text("x")
        plugin = _make_meta_plugin(
            plugin_config,
            post_instagram_comment=True,
            instagram_comment_template="Go {home_team}!",
        )

        with (
            patch(
                "reeln_meta_plugin.plugin.reels.create_reel_container",
                return_value=_FAKE_CONTAINER,
            ),
            patch("reeln_meta_plugin.plugin.reels.poll_container_status"),
            patch(
                "reeln_meta_plugin.plugin.reels.publish_reel",
                return_value="media-abc",
            ),
            patch(
                "reeln_meta_plugin.plugin.reels.get_permalink",
                return_value="https://instagram.com/reel/abc",
            ),
            patch(
                "reeln_meta_plugin.plugin.comments.post_comment",
                side_effect=CommentError("blocked"),
            ),
        ):
            # Comment failure must not prevent the overall publish from
            # succeeding — the Reel itself went up.
            url = plugin.upload(
                video,
                metadata={
                    "video_url": _CDN_URL,
                    "home_team": "Eagles",
                    "away_team": "Hawks",
                },
            )

        assert url == "https://instagram.com/reel/abc"

    def test_upload_hydrates_game_info_from_metadata(
        self, plugin_config: dict[str, Any], tmp_path: Path
    ) -> None:
        """When _game_info is None (manual publish path), the helper
        populates it from the metadata dict so template rendering works."""
        video = tmp_path / "clip.mp4"
        video.write_text("x")
        plugin = _make_meta_plugin(
            plugin_config,
            reel_caption_template="Match: {home_team} vs {away_team}",
        )
        assert plugin._game_info is None

        with (
            patch(
                "reeln_meta_plugin.plugin.reels.create_reel_container",
                return_value=_FAKE_CONTAINER,
            ) as mock_create,
            patch("reeln_meta_plugin.plugin.reels.poll_container_status"),
            patch(
                "reeln_meta_plugin.plugin.reels.publish_reel",
                return_value="media-abc",
            ),
            patch(
                "reeln_meta_plugin.plugin.reels.get_permalink",
                return_value="https://instagram.com/reel/abc",
            ),
        ):
            plugin.upload(
                video,
                metadata={
                    "video_url": _CDN_URL,
                    "home_team": "Eagles",
                    "away_team": "Hawks",
                    "date": "2026-01-15",
                    "sport": "hockey",
                },
            )

        # _game_info was hydrated from metadata
        assert plugin._game_info is not None
        # And the caption was rendered from the template with hydrated values
        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs["caption"] == "Match: Eagles vs Hawks"

    def test_upload_hydrate_noop_when_game_info_already_set(
        self, plugin_config: dict[str, Any], tmp_path: Path
    ) -> None:
        video = tmp_path / "clip.mp4"
        video.write_text("x")
        plugin = _make_meta_plugin(plugin_config)
        existing = FakeGameInfo(home_team="Existing", away_team="Teams")
        plugin._game_info = existing

        plugin._hydrate_game_info_from_metadata({"home_team": "Other"})

        assert plugin._game_info is existing

    def test_upload_hydrate_noop_when_metadata_empty(
        self, plugin_config: dict[str, Any]
    ) -> None:
        plugin = _make_meta_plugin(plugin_config)
        plugin._hydrate_game_info_from_metadata({})
        assert plugin._game_info is None

    def test_upload_caption_prefers_description(
        self, plugin_config: dict[str, Any]
    ) -> None:
        plugin = _make_meta_plugin(
            plugin_config,
            reel_caption_template="Template: {home_team}",
        )
        caption = plugin._build_caption_from_metadata(
            {"description": "AI-generated", "home_team": "Eagles"}
        )
        assert caption == "AI-generated"

    def test_upload_caption_falls_to_template(
        self, plugin_config: dict[str, Any]
    ) -> None:
        plugin = _make_meta_plugin(
            plugin_config,
            reel_caption_template="Go {home_team}!",
        )
        plugin._hydrate_game_info_from_metadata({"home_team": "Eagles"})
        caption = plugin._build_caption_from_metadata({"home_team": "Eagles"})
        assert caption == "Go Eagles!"

    def test_upload_caption_falls_to_title_when_no_template(
        self, plugin_config: dict[str, Any]
    ) -> None:
        plugin = _make_meta_plugin(plugin_config)
        plugin._game_info = FakeGameInfo(
            home_team="Eagles", away_team="Hawks", date="2026-01-15"
        )
        caption = plugin._build_caption_from_metadata({})
        assert "Eagles" in caption and "Hawks" in caption

    def test_upload_caption_empty_when_nothing_available(
        self, plugin_config: dict[str, Any]
    ) -> None:
        plugin = _make_meta_plugin(plugin_config)
        # No _game_info, no template, no description
        caption = plugin._build_caption_from_metadata({})
        assert caption == ""

    def test_upload_fb_title_from_metadata(
        self, plugin_config: dict[str, Any]
    ) -> None:
        plugin = _make_meta_plugin(plugin_config)
        title = plugin._build_fb_title_from_metadata({"title": "Custom Title"})
        assert title == "Custom Title"

    def test_upload_fb_title_fallback_to_game_info(
        self, plugin_config: dict[str, Any]
    ) -> None:
        plugin = _make_meta_plugin(plugin_config)
        plugin._game_info = FakeGameInfo(
            home_team="Eagles", away_team="Hawks", date="2026-01-15"
        )
        title = plugin._build_fb_title_from_metadata({})
        assert "Eagles" in title

    def test_upload_fb_title_empty_when_nothing_available(
        self, plugin_config: dict[str, Any]
    ) -> None:
        plugin = _make_meta_plugin(plugin_config)
        assert plugin._build_fb_title_from_metadata({}) == ""

    def test_upload_fb_description_from_metadata(
        self, plugin_config: dict[str, Any]
    ) -> None:
        plugin = _make_meta_plugin(plugin_config)
        desc = plugin._build_fb_description_from_metadata(
            {"description": "Big game"}
        )
        assert desc == "Big game"

    def test_upload_fb_description_falls_to_template(
        self, plugin_config: dict[str, Any]
    ) -> None:
        plugin = _make_meta_plugin(
            plugin_config,
            facebook_reel_description_template="Watch {home_team} highlights",
        )
        plugin._hydrate_game_info_from_metadata({"home_team": "Eagles"})
        desc = plugin._build_fb_description_from_metadata({})
        assert desc == "Watch Eagles highlights"

    def test_upload_fb_description_empty_when_nothing_available(
        self, plugin_config: dict[str, Any]
    ) -> None:
        plugin = _make_meta_plugin(plugin_config)
        assert plugin._build_fb_description_from_metadata({}) == ""

    def test_upload_accepts_no_metadata(
        self, plugin_config: dict[str, Any], tmp_path: Path
    ) -> None:
        """metadata=None is valid per the Uploader protocol."""
        from reeln.plugins.capabilities import UploaderSkipped

        video = tmp_path / "clip.mp4"
        video.write_text("x")
        plugin = _make_meta_plugin(plugin_config)

        # Without metadata, video_url is missing → UploaderSkipped.
        with pytest.raises(UploaderSkipped, match="video_url"):
            plugin.upload(video)

    def test_upload_ig_succeeds_fb_fails_returns_ig_permalink(
        self, plugin_config: dict[str, Any], tmp_path: Path
    ) -> None:
        """REGRESSION: IG publishes successfully, FB fails → upload()
        must return the IG permalink, NOT raise. Otherwise the dock
        marks meta as FAILED, the user clicks Retry, and the plugin
        publishes ANOTHER live IG Reel on every retry.

        This was a real production bug that caused multiple duplicate
        Instagram Reels before it was fixed.
        """
        video = tmp_path / "clip.mp4"
        video.write_text("x")
        plugin = _make_meta_plugin(plugin_config, publish_facebook_reels=True)

        with (
            patch(
                "reeln_meta_plugin.plugin.reels.create_reel_container",
                return_value=_FAKE_CONTAINER,
            ),
            patch("reeln_meta_plugin.plugin.reels.poll_container_status"),
            patch(
                "reeln_meta_plugin.plugin.reels.publish_reel",
                return_value="media-abc",
            ),
            patch(
                "reeln_meta_plugin.plugin.reels.get_permalink",
                return_value="https://instagram.com/reel/abc",
            ),
            patch(
                "reeln_meta_plugin.plugin.facebook_reels.start_reel_upload",
                side_effect=FacebookReelsError("FB fetch blocked"),
            ),
        ):
            url = plugin.upload(video, metadata={"video_url": _CDN_URL})

        # IG permalink returned — publish_queue_item records PUBLISHED.
        assert url == "https://instagram.com/reel/abc"
        # And _published_reel_id is set (for subsequent comment posting).
        assert plugin._published_reel_id == "media-abc"

    def test_upload_ig_fails_fb_succeeds_returns_fb_url(
        self, plugin_config: dict[str, Any], tmp_path: Path
    ) -> None:
        """Mirror of the IG-wins case: when IG fails but FB succeeds,
        return the FB video URL instead of raising."""
        video = tmp_path / "clip.mp4"
        video.write_text("x")
        plugin = _make_meta_plugin(plugin_config, publish_facebook_reels=True)

        with (
            patch(
                "reeln_meta_plugin.plugin.reels.create_reel_container",
                side_effect=ReelsError("IG container failed"),
            ),
            patch(
                "reeln_meta_plugin.plugin.facebook_reels.start_reel_upload",
                return_value=_FAKE_FB_START,
            ),
            patch("reeln_meta_plugin.plugin.facebook_reels.upload_reel_video"),
            patch("reeln_meta_plugin.plugin.facebook_reels.finish_reel"),
            patch("reeln_meta_plugin.plugin.facebook_reels.poll_reel_status"),
        ):
            url = plugin.upload(video, metadata={"video_url": _CDN_URL})

        assert "facebook.com/pg-123/videos/fb-vid-123" in url

    def test_upload_both_ig_and_fb_fail_raises_combined_errors(
        self, plugin_config: dict[str, Any], tmp_path: Path
    ) -> None:
        """When BOTH publishes fail, raise with both errors in the message."""
        video = tmp_path / "clip.mp4"
        video.write_text("x")
        plugin = _make_meta_plugin(plugin_config, publish_facebook_reels=True)

        with (
            patch(
                "reeln_meta_plugin.plugin.reels.create_reel_container",
                side_effect=ReelsError("IG container failed"),
            ),
            patch(
                "reeln_meta_plugin.plugin.facebook_reels.start_reel_upload",
                side_effect=FacebookReelsError("FB start failed"),
            ),pytest.raises(RuntimeError) as excinfo
        ):
            plugin.upload(video, metadata={"video_url": _CDN_URL})

        # Both sub-op errors should be in the composite message.
        assert "IG Reel" in str(excinfo.value)
        assert "IG container failed" in str(excinfo.value)
        assert "Facebook Reel" in str(excinfo.value)
        assert "FB start failed" in str(excinfo.value)

    def test_upload_partial_missing_config_with_other_target_succeeding(
        self, plugin_config: dict[str, Any], tmp_path: Path
    ) -> None:
        """Missing IG account id + FB succeeds → return FB URL, don't raise."""
        video = tmp_path / "clip.mp4"
        video.write_text("x")
        plugin = _make_meta_plugin(
            plugin_config,
            publish_facebook_reels=True,
            instagram_account_id="",  # misconfigured → errors, but FB saves us
        )

        with (
            patch(
                "reeln_meta_plugin.plugin.facebook_reels.start_reel_upload",
                return_value=_FAKE_FB_START,
            ),
            patch("reeln_meta_plugin.plugin.facebook_reels.upload_reel_video"),
            patch("reeln_meta_plugin.plugin.facebook_reels.finish_reel"),
            patch("reeln_meta_plugin.plugin.facebook_reels.poll_reel_status"),
        ):
            url = plugin.upload(video, metadata={"video_url": _CDN_URL})

        assert "facebook.com" in url

    def test_upload_ig_publish_non_fatal_empty_permalink(
        self, plugin_config: dict[str, Any], tmp_path: Path
    ) -> None:
        """Empty permalink (from _do_ig_reel_publish) still produces a
        successful return — primary_url falls back to the sentinel."""
        video = tmp_path / "clip.mp4"
        video.write_text("x")
        plugin = _make_meta_plugin(plugin_config)

        with (
            patch(
                "reeln_meta_plugin.plugin.reels.create_reel_container",
                return_value=_FAKE_CONTAINER,
            ),
            patch("reeln_meta_plugin.plugin.reels.poll_container_status"),
            patch(
                "reeln_meta_plugin.plugin.reels.publish_reel",
                return_value="media-abc",
            ),
            patch(
                "reeln_meta_plugin.plugin.reels.get_permalink",
                side_effect=ReelsError("permalink lookup down"),
            ),
        ):
            url = plugin.upload(video, metadata={"video_url": _CDN_URL})

        # get_permalink failure is caught inside _do_ig_reel_publish and
        # produces an empty permalink. Overall upload returns the sentinel.
        assert url == "meta:published"
