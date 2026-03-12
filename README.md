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

## Facebook Developer Setup

### 1. Create a Facebook Developer Account

Go to [developers.facebook.com](https://developers.facebook.com/) and register as a developer.

### 2. Create an App

1. Go to **My Apps** → **Create App**
2. Select a use case (e.g. **Other** → **Business**)
3. Choose **Business** app type
4. Fill in app name, contact email, and select a Business portfolio
5. Click **Create App**

### 3. Get a Page Access Token

1. Go to the [Graph API Explorer](https://developers.facebook.com/tools/explorer/)
2. Select your app from the **Meta App** dropdown
3. Click **Generate Access Token**
4. Grant the following permissions:
   - `pages_show_list`
   - `pages_manage_posts`
   - `pages_read_engagement`
   - `publish_video`
5. Select your Page from the **User or Page** dropdown
6. Copy the **Page Access Token**

> **Note:** The default token expires in ~1 hour. For a long-lived token
> (60 days), exchange it via the
> [Access Token Debugger](https://developers.facebook.com/tools/debug/accesstoken/)
> or the token exchange endpoint:
> ```
> GET /oauth/access_token?grant_type=fb_exchange_token
>   &client_id=APP_ID&client_secret=APP_SECRET
>   &fb_exchange_token=SHORT_LIVED_TOKEN
> ```

### 4. Save the Token to a File

```bash
mkdir -p secrets
echo "YOUR_PAGE_ACCESS_TOKEN" > secrets/meta_page_token.txt
```

### 5. Get Your Page ID

Find your Page ID in **Page Settings → About → Page ID**, or query it via the API:

```bash
curl "https://graph.facebook.com/v24.0/me?access_token=YOUR_TOKEN"
```

### 6. Configure the Plugin

```bash
reeln config set meta.page_access_token_file ./secrets/meta_page_token.txt
reeln config set meta.page_id YOUR_PAGE_ID
reeln config set meta.create_livestream true
```

Or edit your reeln config JSON directly:

```json
{
  "plugins": {
    "enabled": ["meta"],
    "settings": {
      "meta": {
        "page_access_token_file": "./secrets/meta_page_token.txt",
        "page_id": "123456789",
        "create_livestream": true
      }
    }
  }
}
```

### 7. App Review

The `publish_video` permission may require App Review for production use.
During development, you can use the token with your own Pages without review.

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
| `privacy` | str | `EVERYONE` | Privacy setting (`EVERYONE` or `SELF`) |
| `content_category` | str | `SPORTS` | Content category (`SPORTS`, `VIDEO_GAMING`, etc.) |
| `game_id` | str | `""` | Facebook game ID to tag the broadcast with |
| `save_vod` | bool | `true` | Save a VOD recording after broadcast ends |
| `published` | bool | `true` | Publish VOD to Page timeline after broadcast ends |
| `stop_on_delete_stream` | bool | `false` | Auto-end broadcast when RTMP stream disconnects |

All settings can be overridden per [named profile](https://reeln-cli.readthedocs.io/en/latest/guide/configuration.html#named-profiles).
For example, a `config.testing.json` profile could set `"privacy": "SELF"` for test broadcasts
while your default config stays `"EVERYONE"` for game day.

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
