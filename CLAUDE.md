# CLAUDE.md

## Project Overview

**reeln-plugin-meta** — reeln-cli plugin for Meta platform integration (Facebook Live, Instagram Reels, Threads).

- **Package:** `reeln-plugin-meta` | **License:** AGPL-3.0
- **Python:** 3.11+ | Entry point: `reeln.plugins` → `meta = "reeln_meta_plugin:MetaPlugin"`

## Dev Commands

```bash
make dev-install    # uv venv + editable install with dev deps (also installs sibling ../reeln-cli)
make reeln-install  # install plugin editable into sibling ../reeln-cli/.venv
make test           # pytest with 100% line+branch coverage, parallel via xdist
make lint           # ruff check
make format         # ruff format
make check          # lint → mypy → test (sequential)
```

Single test: `.venv/bin/python -m pytest tests/unit/test_plugin.py::TestClassName::test_method -q`

## Architecture

| Module | Responsibility |
|---|---|
| `plugin.py` | `MetaPlugin` — lifecycle, hook handlers, config schema, cached auth |
| `auth.py` | File-based Page Access Token reading |
| `graph_api.py` | `http_get`, `http_post`, `http_post_multipart`, `http_post_rupload`, `format_meta_error`, `GraphAPIError` |
| `livestream.py` | Facebook Live Video create/update/thumbnail via Graph API |
| `facebook_reels.py` | Facebook Page Reels start/upload/finish/poll via Graph API + rupload |
| `reels.py` | Instagram Reels create container/poll/publish/permalink via Graph API |
| `comments.py` | Instagram comment posting on published media |
| `__init__.py` | Exports `MetaPlugin` and `__version__` |

**Dependency:** `reeln` (sibling install from `../reeln-cli`)

## Versioning

Update all three in lockstep on every change:
1. `reeln_meta_plugin/__init__.py` — `__version__`
2. `reeln_meta_plugin/plugin.py` — `version` class attribute
3. `CHANGELOG.md` — Keep a Changelog format

## Conventions

- `from __future__ import annotations` in every module
- 4-space indent, snake_case, type hints on all signatures
- `pathlib.Path` for all file paths — never raw strings
- 100% line + branch coverage — no exceptions
- Non-fatal errors: log warnings, don't crash the game flow
- All HTTP via `urllib` — no external HTTP libraries

## Context Rules

Domain-specific details are in `.claude/rules/` (loaded on demand via glob matching):
- `meta-api.md` — API URLs, known limitations, auth, platform features
- `plugin-lifecycle.md` — hooks, feature flags, shared context, versioning details
- `testing.md` — test patterns, fixtures, feature flag testing
- `workflow.md` — task-to-agent mapping
