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
        assert plugin.version == "0.4.0"

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
        assert field.default == "EVERYONE"

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

    def test_save_vod_default(self) -> None:
        schema = MetaPlugin.config_schema
        field = schema.field_by_name("save_vod")
        assert field is not None
        assert field.default is True

    def test_published_default(self) -> None:
        schema = MetaPlugin.config_schema
        field = schema.field_by_name("published")
        assert field is not None
        assert field.default is True

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
        assert kwargs["privacy"] == "EVERYONE"
        assert kwargs["content_category"] == "SPORTS"
        assert kwargs["game_id"] == ""
        assert kwargs["save_vod"] is True
        assert kwargs["published"] is True
        assert kwargs["stop_on_delete_stream"] is False

    def test_custom_livestream_settings(self, plugin_config: dict[str, Any]) -> None:
        """Verify config overrides flow through to create_livestream."""
        plugin_config.update({
            "status": "UNPUBLISHED",
            "privacy": "SELF",
            "content_category": "VIDEO_GAMING",
            "game_id": "42",
            "save_vod": False,
            "published": False,
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
        assert kwargs["status"] == "UNPUBLISHED"
        assert kwargs["privacy"] == "SELF"
        assert kwargs["content_category"] == "VIDEO_GAMING"
        assert kwargs["game_id"] == "42"
        assert kwargs["save_vod"] is False
        assert kwargs["published"] is False
        assert kwargs["stop_on_delete_stream"] is True

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
        """Simulate the full plugin lifecycle: init -> register -> emit init -> emit finish."""
        plugin = MetaPlugin(plugin_config)
        registry = HookRegistry()
        plugin.register(registry)

        game_info = FakeGameInfo(home_team="Storm", away_team="Thunder")
        context = HookContext(hook=Hook.ON_GAME_INIT, data={"game_info": game_info})

        with patch(
            "reeln_meta_plugin.plugin.livestream.create_livestream",
            return_value=_FAKE_RESULT,
        ):
            registry.emit(Hook.ON_GAME_INIT, context)

        assert context.shared["livestreams"]["meta"] == _FAKE_RESULT.embed_url
        assert plugin._game_info is game_info
        assert plugin._access_token is not None

        finish_context = HookContext(hook=Hook.ON_GAME_FINISH, data={})
        registry.emit(Hook.ON_GAME_FINISH, finish_context)

        assert plugin._access_token is None
        assert plugin._game_info is None
