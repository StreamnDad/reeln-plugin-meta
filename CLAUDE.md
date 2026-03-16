# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**reeln-plugin-meta** is a reeln-cli plugin that provides Meta platform integration (Instagram Reels, Facebook video, Threads posts).

- **Package:** `reeln-plugin-meta` | **License:** AGPL-3.0
- **Python:** 3.11+ | **Plugin framework:** reeln-cli plugin system
- Entry point: `reeln.plugins` → `meta = "reeln_meta_plugin:MetaPlugin"`

## Dev Commands

```bash
make dev-install    # uv venv + editable install with dev deps (also installs sibling ../reeln-cli)
make reeln-install  # install plugin editable into sibling ../reeln-cli/.venv
make test           # pytest with 100% line+branch coverage, parallel via xdist
make lint           # ruff check
make format         # ruff format
make check          # lint → mypy → test (sequential)
```

Run a single test file or test:
```bash
.venv/bin/python -m pytest tests/unit/test_plugin.py -q
.venv/bin/python -m pytest tests/unit/test_plugin.py::TestClassName::test_method -q
```

## Architecture

This plugin hooks into reeln-cli lifecycle events via the plugin system.

### Implemented Modules

| Module | Responsibility |
|---|---|
| `plugin.py` | `MetaPlugin` — plugin lifecycle, hook handlers, config schema, cached auth |
| `auth.py` | Token-based auth — file-based Page Access Token reading |
| `graph_api.py` | Shared HTTP helpers — `http_post`, `http_post_multipart`, `format_meta_error`, `GraphAPIError` |
| `livestream.py` | Facebook Live Video creation + update + thumbnail upload via Graph API (delegates HTTP to `graph_api`) |
| `__init__.py` | Exports `MetaPlugin` and `__version__` |

### Feature Flags

Each Meta capability **must** be gated behind a boolean config field that defaults to `false`.
This ensures features are opt-in and can be toggled per named profile. Current flags:

| Config Field | Default | Capability |
|---|---|---|
| `create_livestream` | `false` | Facebook Live Video on `ON_GAME_INIT` |
| `dry_run` | `false` | Log API calls without executing them |

Future capabilities must follow this pattern:

| Config Field | Default | Capability |
|---|---|---|
| `publish_reels` | `false` | Instagram Reel publishing |
| `upload_facebook_video` | `false` | Facebook Page video uploads |
| `post_instagram_comment` | `false` | Comments on published Instagram media |
| `create_threads_post` | `false` | Threads text/video posts |
| `create_game_thread` | `false` | Threads game thread on `ON_GAME_INIT` |

When implementing a new capability, always:
1. Add a boolean `ConfigField` with `default=False`
2. Guard the hook handler with `if not self._config.get("feature_name"):` early return
3. Test both the enabled and disabled (default) paths

### Key Hooks

- **`ON_GAME_INIT`** — creates Facebook Live Video (when `create_livestream` is `true`)
- **`ON_GAME_READY`** — updates livestream metadata (title, description) and uploads thumbnail from `context.shared["game_image"]["image_path"]`
- **`ON_GAME_FINISH`** — resets cached auth token and game info between sessions

### Shared Context Convention

Plugins communicate via `HookContext.shared` (mutable dict on frozen dataclass):
```python
context.shared["livestreams"]["meta"] = "https://www.facebook.com/PAGE_ID/videos/LIVE_ID"
```

### External Dependencies

- `reeln` — plugin hooks, capabilities, and models (sibling install)

### Meta APIs

All Meta API calls use `urllib` (no external HTTP library), following the pattern established in streamn-dad-highlights:

- **Instagram Graph API** (`graph.facebook.com/v24.0`) — Reel publishing (two-stage: create container → publish), comments, permalinks
- **Facebook Graph API** (`graph.facebook.com/v24.0`) — Video uploads to Pages
- **Threads API** (`graph.threads.net`) — Thread creation/publishing, replies, topic tags
- **Auth** — File-based access tokens (user token, page token, Threads token); Threads OAuth code exchange

### Features to Port from streamn-dad-highlights

These features from `replay_publisher/meta.py` and `replay_publisher/cli.py` should be incrementally ported:

1. **Instagram Reels** — two-stage publish with status polling and thumbnail offset
2. **Facebook Video** — page video uploads with published/draft mode
3. **Instagram Comments** — post comments on published media
4. **Threads Posts** — text and video posts with reply threading and topic tags
5. **Threads Game Thread** — root thread creation during game init, reply threading for updates
6. **Permalink Fetching** — retry-based Instagram permalink retrieval
7. ~~**Dry-Run Mode** — full pipeline without actual API calls~~ *(done in v0.4.0)*
8. **Template Rendering** — configurable text templates with context variables

## Versioning

Every code change **must** bump the version following [Semantic Versioning](https://semver.org/):

- **Major** — breaking changes to plugin behavior or config schema
- **Minor** — new features, new capabilities, new config options
- **Patch** — bug fixes, internal refactors, test-only changes

Update all three locations in lockstep:

1. `reeln_meta_plugin/__init__.py` — `__version__`
2. `reeln_meta_plugin/plugin.py` — `version` class attribute
3. `CHANGELOG.md` — new section under `[Unreleased]` with date and description

## Conventions

- `from __future__ import annotations` in every module
- 4-space indent, snake_case, type hints on all signatures
- `pathlib.Path` for all file paths
- 100% line + branch coverage — no exceptions
- Keep a Changelog format in CHANGELOG.md
- Tests use `tmp_path` for all file I/O and mock external API clients
- Non-fatal errors: plugin operations log warnings but don't crash the game flow

### Known Facebook API Limitations

- **`privacy` parameter:** Does not work with Page Access Tokens (causes `#200 Permissions error`). Only works with User Access Tokens. Default is empty string (omit from payload).
- **`SCHEDULED_UNPUBLISHED`:** Deprecated by Facebook — API returns `(#100) Invalid broadcast status, Scheduled Live has been deprecated` despite still being in their docs. The `event_params` code is kept for future use if Facebook re-enables it.
- **`save_vod`:** Deprecated in Graph API v24.0 — removed in v0.6.0.
- **`published` + `status`:** Mutually exclusive — removed `published` in v0.6.0, use `status` only.
- **`UNPUBLISHED` broadcasts:** API-only — they do not appear in Facebook's Live Producer UI.
- **`LIVE_NOW` broadcasts:** Nothing visible until RTMP stream connects — safe for testing without privacy settings.
- **Page requirements (since June 2024):** Account must be 60+ days old AND Page must have 100+ followers for live video.
- **Named profiles:** reeln-cli named profiles are standalone config files — they do NOT inherit/merge from base `config.json`.
