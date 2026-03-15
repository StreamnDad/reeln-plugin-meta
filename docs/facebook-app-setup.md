# Facebook App Setup Guide

Complete guide to setting up a Facebook App for use with reeln-plugin-meta.

## Prerequisites

- A Facebook account (personal profile)
- A Facebook Page you admin that meets these requirements (since June 2024):
  - **At least 60 days old**
  - **At least 100 followers**
- A Meta Business Portfolio (created automatically when you register as a developer)

## 1. Register as a Facebook Developer

1. Go to [developers.facebook.com](https://developers.facebook.com/)
2. Click **Get Started** and follow the registration flow
3. Accept the Meta Platform Terms

## 2. Create a Facebook App

1. Go to [**My Apps**](https://developers.facebook.com/apps/) → **Create App**
2. Select a use case — choose **Other** → **Business**
3. Choose the **Business** app type
4. Fill in:
   - **App name** (e.g. "My Livestream App")
   - **Contact email**
   - **Business portfolio** — select yours or create one
5. Click **Create App**

## 3. Add Use Cases

From your App Dashboard, go to **Use cases** → **Customize**.

### Facebook Live Video

1. Click **Add use case** → select **Manage Pages** (or a use case that includes Live Video)
2. Go to **Permissions and features** for that use case
3. Confirm **Live Video API** shows as **"Ready for testing"**
4. Confirm these permissions are listed:
   - `pages_show_list`
   - `pages_manage_posts`
   - `pages_read_engagement`

> **Note:** `publish_video` is not a separate token scope — it is granted
> implicitly through the **Live Video API** feature at the app level. You will
> not see it in the Graph API Explorer permissions list or the token debugger.

### Instagram (optional, for future features)

If you plan to use Instagram Reels or comments:

1. Add a use case that includes Instagram
2. Add permissions:
   - `instagram_basic`
   - `instagram_content_publish`
   - `instagram_manage_comments`

## 4. Generate a Page Access Token

### Option A: Graph API Explorer (recommended)

1. Go to the [Graph API Explorer](https://developers.facebook.com/tools/explorer/)
2. Select your app from the **Meta App** dropdown
3. Under **Permissions**, add:
   - `pages_show_list`
   - `pages_manage_posts`
   - `pages_read_engagement`
4. Click **Generate Access Token**
5. **Important:** When the Facebook authorization dialog appears, there is a step
   that asks **"What Pages do you want [app] to use?"** — you **must** select
   your Pages here. If you skip this step or select none, the token will not
   have Page access.
6. Once authorized, change the **User or Page** dropdown from "User Token" to
   your Page name
7. Copy the **Page Access Token**

### Option B: API call (if the Explorer dropdown doesn't work)

1. Generate a **User Access Token** in the Graph API Explorer with the
   permissions listed above
2. Run this query in the Explorer (or via curl):
   ```
   GET /me/accounts?fields=name,access_token,id
   ```
3. The response contains your Pages with their Page Access Tokens:
   ```json
   {
     "data": [
       {
         "name": "Your Page Name",
         "access_token": "EAAG...long_page_token...",
         "id": "123456789"
       }
     ]
   }
   ```
4. Copy the `access_token` and `id` for your Page

### Troubleshooting: `/me/accounts` returns empty

If `GET /me/accounts` returns `{"data": []}` despite having `pages_show_list`:

1. Go to [facebook.com/settings?tab=business_tools](https://www.facebook.com/settings?tab=business_tools)
2. Find your app and click **Remove**
3. Go back to the Graph API Explorer and click **Generate Access Token**
4. The full authorization flow will appear fresh — **select your Pages** when prompted
5. Run `GET /me/accounts` again

This happens when Pages were not selected during the original OAuth authorization.

### Verify your token

Confirm the token is a Page token (not a User token):

```bash
curl "https://graph.facebook.com/v24.0/me?fields=name,id&access_token=YOUR_PAGE_TOKEN"
```

This should return your **Page name and ID**, not your personal name.

You can also inspect the token at the
[Access Token Debugger](https://developers.facebook.com/tools/debug/accesstoken/).
It should show `Type: Page`.

## 5. Extend the Token (recommended)

The default Page Access Token from the Graph API Explorer expires in ~1 hour.

### Get a long-lived token (60 days)

Exchange it via the token endpoint:

```bash
curl "https://graph.facebook.com/v24.0/oauth/access_token?\
grant_type=fb_exchange_token&\
client_id=YOUR_APP_ID&\
client_secret=YOUR_APP_SECRET&\
fb_exchange_token=YOUR_SHORT_LIVED_USER_TOKEN"
```

Then use the long-lived **User** token to get a long-lived **Page** token:

```bash
curl "https://graph.facebook.com/v24.0/me/accounts?fields=name,access_token,id&access_token=YOUR_LONG_LIVED_USER_TOKEN"
```

The Page Access Token from this call will **not expire** as long as:
- The user remains an admin of the Page
- The user's long-lived token is valid
- The app is not removed from the user's business integrations

### Alternative: Access Token Debugger

1. Go to the [Access Token Debugger](https://developers.facebook.com/tools/debug/accesstoken/)
2. Paste your short-lived token
3. Click **Extend Access Token** at the bottom

## 6. Save the Token

```bash
mkdir -p ~/.config/reeln/secrets
echo "YOUR_PAGE_ACCESS_TOKEN" > ~/.config/reeln/secrets/meta_page_token.txt
chmod 600 ~/.config/reeln/secrets/meta_page_token.txt
```

## 7. Get Your Page ID

Your Page ID is returned with the token if you used `/me/accounts`. Otherwise:

```bash
curl "https://graph.facebook.com/v24.0/me?fields=id,name&access_token=YOUR_PAGE_TOKEN"
```

Or find it in **Page Settings** → **About** → **Page ID** on facebook.com.

## 8. Configure the Plugin

```bash
reeln config set meta.page_access_token_file ~/.config/reeln/secrets/meta_page_token.txt
reeln config set meta.page_id YOUR_PAGE_ID
reeln config set meta.create_livestream true
```

### Broadcast visibility

With `status: LIVE_NOW` (default), the live video is created but **nothing is visible
to your audience until you connect an RTMP stream**. This makes it safe for testing
without needing a separate privacy setting.

> **Important:** The `privacy` config field does **not** work with Page Access Tokens
> (causes `#200 Permissions error`). Leave it empty (the default). Privacy settings
> only work with User Access Tokens.

## 9. Verify

```bash
reeln game init
```

You should see:
```
INFO reeln_meta_plugin.plugin: Meta plugin: created livestream https://www.facebook.com/PAGE_ID/videos/LIVE_ID
```

## Common Errors

### `(#12) save_vod is deprecated`

You are running an older version of `reeln-plugin-meta`. Update to v0.6.0+:

```bash
pip install --upgrade reeln-plugin-meta
```

### `(#100) Can only pass one of: 'published, status'`

Same fix — update to v0.6.0+ which removed the deprecated `published` parameter.

### `(#200) Permissions error`

- **If using the `privacy` parameter:** Page Access Tokens do not support the
  `privacy` field. Remove it from your config (leave empty). Privacy only works
  with User Access Tokens.
- Confirm your token is a **Page** token (not a User token) — check with the
  [Access Token Debugger](https://developers.facebook.com/tools/debug/accesstoken/)
- Confirm the token has `pages_manage_posts` in its scopes
- Confirm the **Live Video API** feature is "Ready for testing" in your app's
  **Use cases** → **Permissions and features**

### `(#10) To use live-video-api on behalf of people who are not admins...`

This means you need **App Review** for production use. For development/testing,
make sure you are logged in as an admin, developer, or tester of the app.

Add testers at: **App Dashboard** → **App Roles** → **Roles**

### `You're not eligible to go live`

Since June 2024, Facebook requires:
- The Facebook account must be **at least 60 days old**
- The Facebook Page must have **at least 100 followers**

These are Facebook policy restrictions, not API limitations. Use a Page that meets both requirements.

### `/me/accounts` returns empty `{"data": []}`

See [Troubleshooting](#troubleshooting-meaccounts-returns-empty) above. The
most common cause is not selecting Pages during the OAuth authorization flow.

## App Review (production)

For production use (non-admin users), you will need:

1. **App Review** — submit the Live Video API feature for review
2. **Business Verification** — verify your business identity with Meta

Go to **App Dashboard** → **App Review** → **Permissions and Features** →
click **+ Add to App Review** next to Live Video API.

Review requirements include:
- A screencast demonstrating how your app uses live video
- A description of the use case
- Privacy policy URL

During development, these are **not required** — the "Ready for testing" status
allows admins, developers, and testers to use the feature.

## Privacy Settings Reference

> **Page tokens:** The `privacy` parameter causes `(#200) Permissions error` when
> used with Page Access Tokens. Leave the `privacy` config field empty (the default).
> Privacy settings only work with **User Access Tokens**.

| Value | Description |
|---|---|
| `EVERYONE` | Public — visible to all |
| `ALL_FRIENDS` | Friends of the Page admin only |
| `FRIENDS_OF_FRIENDS` | Friends of friends |
| `SELF` | Only you — for testing |

## Status Settings Reference

| Value | Description |
|---|---|
| `LIVE_NOW` | **(Default)** Start broadcasting immediately when the RTMP stream connects. Nothing is visible to your audience until the RTMP stream actually connects — safe for testing. |
| `UNPUBLISHED` | Create the live video as a draft. **Note:** UNPUBLISHED broadcasts are API-only — they do **not** appear in Facebook's Live Producer UI. You must start them via the API. |
