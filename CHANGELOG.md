# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [0.7.0] - 2026-03-15

### Added

- `event_params` parameter on `create_livestream()` — Unix timestamp for scheduled start time
- `_compute_event_params()` helper — parses `game_info.date` + `game_info.game_time` into Unix timestamp (supports 12h/24h formats, strips timezone suffixes like "CDT")
- Automatic fallback: if `SCHEDULED_UNPUBLISHED` configured but no `game_time` available, falls back to `LIVE_NOW` with a warning

### Discovered

- `SCHEDULED_UNPUBLISHED` status is **deprecated** by Facebook — API returns `(#100) Invalid broadcast status, Scheduled Live has been deprecated` despite still being documented
- Facebook live video requirements (since June 2024): account 60+ days old AND Page 100+ followers
- Dry-run log now includes status in the output

## [0.6.0] - 2026-03-13

### Added

- Thumbnail upload support in `on_game_ready` — reads `context.shared["game_image"]["image_path"]` and uploads as custom thumbnail
- `upload_thumbnail()` in `livestream.py` — multipart POST to `/{live_video_id}` with `custom_image` field
- `http_post_multipart()` in `graph_api.py` — multipart/form-data POST helper for file uploads
- Metadata update and thumbnail upload are independent — either or both can succeed/fail non-fatally

### Changed

- `on_game_ready` now handles both metadata updates and thumbnail uploads independently

### Removed

- `save_vod` config field and API parameter — deprecated by Facebook (Graph API v24.0)
- `published` config field and API parameter — mutually exclusive with `status` (use `status` instead)
- `privacy` default changed from `EVERYONE` to empty string — `privacy` causes `(#200) Permissions error` with Page Access Tokens; only works with User tokens

## [0.5.0] - 2026-03-12

### Added

- `ON_GAME_READY` hook handler — updates livestream title and description with enriched metadata from other plugins
- `update_livestream()` in `livestream.py` — POST to `/{live_video_id}` to update metadata on an existing Facebook Live Video
- `_livestream_id` instance state — cached from `on_game_init` for use in `on_game_ready`
- Dry-run support for `on_game_ready`

### Changed

- Plugin now registers three hooks: `ON_GAME_INIT`, `ON_GAME_READY`, `ON_GAME_FINISH`
- `on_game_finish` also resets `_livestream_id`

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
