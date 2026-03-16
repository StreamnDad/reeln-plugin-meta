"""Tests for plugin module."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from reeln.plugins.hooks import Hook, HookContext
from reeln.plugins.registry import HookRegistry

from reeln_meta_plugin.auth import AuthError
from reeln_meta_plugin.livestream import LivestreamError, LivestreamResult
from reeln_meta_plugin.plugin import MetaPlugin
from tests.conftest import FakeGameInfo


class TestMetaPluginAttributes:
    def test_name(self) -> None:
        plugin = MetaPlugin()
        assert plugin.name == "meta"

    def test_version(self) -> None:
        plugin = MetaPlugin()
        assert plugin.version == "0.7.0"

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


class TestMetaPluginInit:
    def test_no_config(self) -> None:
        plugin = MetaPlugin()
        assert plugin._config == {}
        assert plugin._access_token is None
        assert plugin._game_info is None
        assert plugin._livestream_id is None

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
