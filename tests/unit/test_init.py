"""Tests for package __init__."""

from __future__ import annotations

import reeln_meta_plugin


class TestPackageExports:
    def test_version_string(self) -> None:
        assert isinstance(reeln_meta_plugin.__version__, str)
        assert len(reeln_meta_plugin.__version__.split(".")) == 3

    def test_meta_plugin_export(self) -> None:
        assert hasattr(reeln_meta_plugin, "MetaPlugin")
        assert reeln_meta_plugin.MetaPlugin is not None

    def test_all_exports(self) -> None:
        assert "MetaPlugin" in reeln_meta_plugin.__all__
        assert "__version__" in reeln_meta_plugin.__all__
