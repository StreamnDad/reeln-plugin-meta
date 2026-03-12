# OBS Forums — Resource Listing Draft

> This document drafts the content for an OBS Forums resource page for
> reeln-plugin-meta.

---

## Resource Title

reeln-plugin-meta — Facebook Live Integration for reeln-cli

## Tagline

Automate Facebook Live broadcasts for your sports streams with reeln-cli.

## Version

0.5.0

## Overview

**reeln-plugin-meta** is a plugin for [reeln-cli](https://github.com/StreamnDad/reeln-cli) that automates Facebook Live Video creation and metadata management through Meta's Graph API.

Point OBS at the RTMP URL that the plugin generates and your stream goes live on your Facebook Page — no manual setup in Facebook Creator Studio required.

### What it does

- Creates a Facebook Live Video on your Page when a game session starts
- Returns an RTMP ingest URL you can feed into OBS
- Updates the livestream title and description mid-session as metadata is enriched by other reeln plugins
- Cleans up state when the session ends
- Shares the embed URL with other plugins via `context.shared["livestreams"]["meta"]`

### Key features

- **Opt-in by default** — nothing happens until you flip `create_livestream` to `true`
- **Dry-run mode** — test your config without hitting the Graph API
- **Per-profile overrides** — run `"privacy": "SELF"` for test broadcasts and `"EVERYONE"` on game day
- **VOD control** — choose whether to save and publish the recording after broadcast
- **Configurable privacy, status, and content category** — fine-tune every broadcast parameter

## Requirements

- Python 3.11+
- [reeln-cli](https://github.com/StreamnDad/reeln-cli) installed
- A Facebook Developer account with a Page Access Token (see setup guide below)
- OBS Studio (or any RTMP-capable encoder)

## Installation

```bash
pip install reeln-plugin-meta
```

## Quick Start

1. Create a Facebook App and generate a Page Access Token ([full guide](https://github.com/StreamnDad/reeln-plugin-meta#facebook-developer-setup))
2. Save the token to a file:
   ```bash
   mkdir -p secrets
   echo "YOUR_PAGE_ACCESS_TOKEN" > secrets/meta_page_token.txt
   ```
3. Configure the plugin:
   ```bash
   reeln config set meta.page_access_token_file ./secrets/meta_page_token.txt
   reeln config set meta.page_id YOUR_PAGE_ID
   reeln config set meta.create_livestream true
   ```
4. Start a reeln session — the plugin creates the livestream and outputs the RTMP URL
5. In OBS, set the **Stream** service to **Custom** and paste the RTMP URL

## Configuration Reference

### Feature Flags

| Setting | Default | Description |
|---|---|---|
| `create_livestream` | `false` | Enable Facebook Live Video creation |
| `dry_run` | `false` | Log API calls without executing them |

### Required

| Setting | Description |
|---|---|
| `page_access_token_file` | Path to file containing your Page Access Token |
| `page_id` | Your Facebook Page ID |

### Livestream Options

| Setting | Default | Description |
|---|---|---|
| `status` | `LIVE_NOW` | `LIVE_NOW` or `UNPUBLISHED` |
| `privacy` | `EVERYONE` | `EVERYONE` or `SELF` |
| `content_category` | `SPORTS` | `SPORTS`, `VIDEO_GAMING`, etc. |
| `game_id` | (empty) | Facebook game ID to tag the broadcast |
| `save_vod` | `true` | Save VOD after broadcast ends |
| `published` | `true` | Publish VOD to Page timeline |
| `stop_on_delete_stream` | `false` | Auto-end when RTMP disconnects |
| `graph_api_version` | `v24.0` | Meta Graph API version |

## Links

- **Source:** https://github.com/StreamnDad/reeln-plugin-meta
- **Issues:** https://github.com/StreamnDad/reeln-plugin-meta/issues
- **License:** AGPL-3.0-only
