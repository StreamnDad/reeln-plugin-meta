# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [0.9.0] - 2026-03-25

### Added

- `facebook_reels.py` module — Facebook Page Reels publishing via four-step upload (start → rupload with CDN URL → finish → poll)
- `publish_facebook_reels` feature flag — enables Facebook Page Reel publishing on `POST_RENDER` hook
- `facebook_reel_description_template` config field — template for Facebook Reel descriptions
- `http_post_rupload()` in `graph_api.py` — POST helper for `rupload.facebook.com` with OAuth header auth and `file_url` header
- Facebook Reel title/description resolution: prefers `render_metadata` (AI-generated), falls back to template or game info
- Shared context output: `context.shared["facebook_reels"]["meta"]` = video_id
- Dry-run support for Facebook Reel publishing
- Reel captions now prefer AI-generated description from `context.shared["render_metadata"]["description"]` (set by OpenAI plugin) before falling back to `reel_caption_template` or `_build_title()`
- `on_post_render` now reads `game_info` from `context.data` when `create_livestream` is disabled, enabling template rendering for Reels/comments without requiring the livestream feature

### Changed

- `on_post_render` now supports three independent publish flags: `publish_reels` (Instagram), `publish_facebook_reels` (Facebook), `post_instagram_comment`
- Instagram `instagram_account_id` check moved to IG-specific code path — no longer blocks Facebook Reels when IG is unconfigured

## [0.8.0] - 2026-03-24

### Added

- `reels.py` module — Instagram Reels publishing via two-stage container API (create container → poll status → publish → get permalink)
- `comments.py` module — Instagram comment posting on published media
- `http_get()` helper in `graph_api.py` — GET requests with query parameters for status polling and permalink retrieval
- `publish_reels` feature flag — enables Reel publishing on `POST_RENDER` hook
- `post_instagram_comment` feature flag — enables comment posting on published Reels
- `POST_RENDER` hook handler (`on_post_render`) — orchestrates Reel publishing and comment posting
- New config fields: `instagram_account_id`, `reel_caption_template`, `instagram_comment_template`, `reel_share_to_feed`, `reel_thumb_offset_ms`, `reel_poll_interval_seconds`, `reel_poll_max_attempts`
- Template-based caption and comment generation with `{home_team}`, `{away_team}`, `{date}`, `{venue}`, `{sport}` placeholders
- Container status polling with configurable timeout (default 5s × 60 attempts = 5 minutes)
- Permalink retrieval with retry logic (default 3 retries, 2s delay)
- Shared context output: `context.shared["reels"]["meta"]` = permalink
- Dry-run support for both Reel publishing and comment posting

### Notes

- Reel publishing requires a publicly accessible `video_url` in `context.shared["video_url"]` (set by a CDN upload plugin)
- Instagram API uses the same Page Access Token as Facebook Live (IG account must be linked to the Facebook Page)

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
