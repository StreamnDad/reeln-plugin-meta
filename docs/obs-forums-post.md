# OBS Forums — Announcement Post Draft

> This document drafts an announcement/discussion post for the OBS Forums.

---

## Post Title

reeln-plugin-meta — Automate Facebook Live from OBS with reeln-cli

## Post Body

Hey everyone,

I wanted to share a plugin I've been working on for the [reeln-cli](https://github.com/StreamnDad/reeln-cli) streaming orchestration tool. If you stream sports (or anything, really) to Facebook Live, this might save you some time.

### What is reeln-plugin-meta?

**reeln-plugin-meta** is a plugin that automates the Facebook Live Video workflow through Meta's Graph API. Instead of manually setting up a broadcast in Creator Studio every time, the plugin handles it for you:

1. **Game starts** — the plugin creates a Facebook Live Video on your Page and hands back an RTMP ingest URL
2. **Metadata enriched** — as other reeln plugins contribute data (scores, lineups, etc.), the livestream title and description update automatically
3. **Game ends** — state is cleaned up; the VOD is optionally saved and published to your Page

You point OBS (or any RTMP encoder) at the RTMP URL that the plugin generates, and you're live.

### Why I built it

I stream youth and amateur sports and was tired of the manual pre-game ritual: open Creator Studio, fill in the title, set privacy, copy the stream key, paste it into OBS, repeat for every game. reeln-cli already orchestrates multi-platform streaming, so a Meta plugin was the natural next step.

### Features

- **Opt-in** — does nothing until you enable `create_livestream`
- **Dry-run mode** — test your setup without actually going live
- **Per-profile config** — use `"privacy": "SELF"` for test runs, `"EVERYONE"` for game day
- **VOD controls** — save recordings, publish to your timeline, or keep them private
- **Plays well with others** — writes the embed URL to a shared context so other plugins (overlays, notifications, etc.) can use it

### Setup in a nutshell

1. Create a Facebook Developer App and get a Page Access Token ([setup guide](https://github.com/StreamnDad/reeln-plugin-meta#facebook-developer-setup))
2. Install the plugin: `pip install reeln-plugin-meta`
3. Configure:
   ```
   reeln config set meta.page_access_token_file ./secrets/meta_page_token.txt
   reeln config set meta.page_id YOUR_PAGE_ID
   reeln config set meta.create_livestream true
   ```
4. Start a reeln session and point OBS at the RTMP URL it outputs

Full docs and source: [github.com/StreamnDad/reeln-plugin-meta](https://github.com/StreamnDad/reeln-plugin-meta)

### Looking for feedback

This is still evolving. Things on the roadmap:

- Instagram Live support
- Threads cross-posting
- Automatic stream key rotation

If you stream to Facebook Live and have ideas or run into issues, I'd love to hear from you. PRs and issues are welcome on GitHub.

**License:** AGPL-3.0

Thanks for reading!
