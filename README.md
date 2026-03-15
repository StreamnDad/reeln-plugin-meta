# reeln-plugin-meta

A [reeln-cli](https://github.com/StreamnDad/reeln-cli) plugin for Meta platform integration (Facebook Live, Instagram, Threads).

## Install

```bash
pip install reeln-plugin-meta
```

Or for development:

```bash
git clone https://github.com/StreamnDad/reeln-plugin-meta
cd reeln-plugin-meta
make dev-install
```

## Features

- **Facebook Live Video** — creates a live video on your Facebook Page during `ON_GAME_INIT`
- Writes the livestream embed URL to `context.shared["livestreams"]["meta"]`
- All features are opt-in via boolean feature flags (default `false`)

## Setup

See the [Facebook App Setup Guide](docs/facebook-app-setup.md) for detailed
instructions on creating a Facebook App, generating tokens, and troubleshooting
common errors.

### Quick Start

```bash
# 1. Save your Page Access Token
echo "YOUR_PAGE_TOKEN" > ~/.config/reeln/secrets/meta_page_token.txt

# 2. Configure the plugin
reeln config set meta.page_access_token_file ~/.config/reeln/secrets/meta_page_token.txt
reeln config set meta.page_id YOUR_PAGE_ID
reeln config set meta.create_livestream true

# 3. Run a test broadcast
reeln game init
```

## Configuration

### Feature Flags

Each capability is gated behind a boolean flag (default `false`):

| Field | Default | Description |
|---|---|---|
| `create_livestream` | `false` | Enable Facebook Live Video creation on `ON_GAME_INIT` |
| `dry_run` | `false` | Log API calls without executing them |

### Required Settings

| Field | Type | Description |
|---|---|---|
| `page_access_token_file` | str | Path to Facebook Page access token file |
| `page_id` | str | Facebook Page ID |

### Livestream Settings

| Field | Type | Default | Description |
|---|---|---|---|
| `graph_api_version` | str | `v24.0` | Graph API version |
| `status` | str | `LIVE_NOW` | Broadcast status (`LIVE_NOW` or `UNPUBLISHED`) |
| `privacy` | str | *(omit)* | Privacy setting — **Page tokens do not support this field** (causes `#200 Permissions error`). Only use with User tokens (`EVERYONE`, `SELF`, etc.) |
| `content_category` | str | `SPORTS` | Content category (`SPORTS`, `VIDEO_GAMING`, etc.) |
| `game_id` | str | `""` | Facebook game ID to tag the broadcast with |
| `stop_on_delete_stream` | bool | `false` | Auto-end broadcast when RTMP stream disconnects |

All settings can be overridden per [named profile](https://reeln-cli.readthedocs.io/en/latest/guide/configuration.html#named-profiles).

> **Note:** Named profiles are standalone config files — they do **not** inherit
> or merge with the base `config.json`. Each profile must include the full
> configuration for all enabled plugins.

## Development

```bash
make dev-install      # uv venv + editable install with dev deps
make reeln-install    # install into sibling reeln-cli venv
make test             # pytest with 100% coverage
make lint             # ruff check
make format           # ruff format
make check            # lint + mypy + test
```

## License

AGPL-3.0-only
