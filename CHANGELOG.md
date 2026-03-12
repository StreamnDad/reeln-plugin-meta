# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [0.4.0] - 2026-03-09

### Added

- `graph_api.py` module — shared HTTP helpers (`http_post`, `format_meta_error`, `GraphAPIError`)
- Cached authentication via `_ensure_auth()` — token read once per game session
- `ON_GAME_FINISH` hook handler — resets cached auth and game info between sessions
- `dry_run` config field (default `false`) — logs API calls without executing them

### Changed

- `livestream.py` now delegates HTTP to `graph_api.py`; `LivestreamError` subclasses `GraphAPIError`
- Plugin registers both `ON_GAME_INIT` and `ON_GAME_FINISH` hooks

## [0.3.0] - 2026-03-05

### Added

- Feature flag system: each capability gated behind a boolean config field (default `false`)
- `create_livestream` feature flag for Facebook Live Video creation

## [0.2.0] - 2026-03-05

### Added

- Facebook Live Video settings: `status`, `privacy`, `content_category`, `game_id`,
  `save_vod`, `published`, `stop_on_delete_stream`
- All settings configurable via plugin config and overridable via named profiles

## [0.1.0] - 2026-03-04

### Added

- Initial plugin scaffolding with `MetaPlugin` class
- Token-based auth module (`auth.py`) with file-based Page Access Token
- Facebook Live Video creation (`livestream.py`) via Graph API
- `ON_GAME_INIT` hook handler — creates Facebook Live Video, writes URL to shared context
- Plugin config schema with `page_access_token_file`, `page_id`, `graph_api_version` fields
- 100% line + branch test coverage
