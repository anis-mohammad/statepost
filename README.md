# News → Facebook Reel

Turn any news article (or RSS feed) into a clean 720×900 (4:5) photocard, render
it as a short MP4, and auto-publish it as a **Facebook Reel** via the Graph API —
locally or on a schedule with GitHub Actions.

```
URL / RSS  ──▶  scrape (headline + image)  ──▶  photocard (720×900 PNG)
            ──▶  3s video (H.264 + silent AAC)  ──▶  Facebook Reel
```

## What's inside

| File | Role |
|------|------|
| [src/scraper.py](src/scraper.py) | Extract headline/image/source from a URL (Open Graph tags) or an RSS feed |
| [src/photocard.py](src/photocard.py) | Render the 720×900 card with Pillow (Montserrat font, brand bar, gradient) |
| [src/video.py](src/video.py) | Card → 3s MP4 with a subtle slow-zoom, via `ffmpeg` |
| [src/facebook.py](src/facebook.py) | Publish a Reel through the Graph API resumable-upload flow |
| [main.py](main.py) | CLI that wires the whole pipeline together |
| [.github/workflows/post-reel.yml](.github/workflows/post-reel.yml) | Scheduled / manual auto-posting |

## Requirements

- Python 3.12
- `ffmpeg` on PATH (`brew install ffmpeg`)

## Setup

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env          # then fill in FB_PAGE_ID + FB_PAGE_ACCESS_TOKEN
```

## Usage

Generate a card + video **without** posting (great for previewing):

```bash
.venv/bin/python main.py --rss "https://feeds.bbci.co.uk/news/world/rss.xml" --no-post
.venv/bin/python main.py --url "https://www.example.com/news/story" --no-post
```

Generate **and publish** a Reel:

```bash
.venv/bin/python main.py --rss "https://feeds.bbci.co.uk/news/world/rss.xml"
```

**Auto-rotate across all US sources** (posts the next not-yet-posted story,
cycling through every feed in [src/feeds.py](src/feeds.py)):

```bash
.venv/bin/python main.py --rotate
```

Rotation remembers what it posted in `state.json` (repo root) so it never
repeats a story and spreads posts evenly across PBS NewsHour, NPR, NBC, CBS,
ABC, Fox, CNN, The Hill, Politico, NY Times, LA Times, Guardian US and Newsweek.
Edit `src/feeds.py` to add/remove sources.

Handy flags:

| Flag | Effect |
|------|--------|
| `--title "..."` | Override the scraped headline |
| `--brand "MY NEWS"` | Brand label shown on the card (default: detected source) |
| `--caption "..."` | Extra text appended to the Reel caption |
| `--rss-index N` | Use the Nth feed entry (0 = newest) |
| `--duration 5` | Video length in seconds (default 3) |
| `--zoom` | Enable a subtle slow-zoom (default: static, no movement) |
| `--no-post` | Build assets only |

Outputs land in `output/` as `YYYYMMDD-slug.png` and `.mp4`.

## Getting Facebook credentials

You need a **Facebook Page** and a **long-lived Page access token** with the
scopes `pages_manage_posts`, `pages_read_engagement`, `pages_show_list`.

1. Create an app at [developers.facebook.com](https://developers.facebook.com/).
2. In **Graph API Explorer**, select your app + Page, request the scopes above,
   and generate a User token.
3. Exchange it for a long-lived token, then get the **Page** token:
   ```bash
   # long-lived user token
   curl "https://graph.facebook.com/v21.0/oauth/access_token?grant_type=fb_exchange_token&client_id=APP_ID&client_secret=APP_SECRET&fb_exchange_token=SHORT_USER_TOKEN"
   # page token + id
   curl "https://graph.facebook.com/v21.0/me/accounts?access_token=LONG_USER_TOKEN"
   ```
4. Put the Page `id` and `access_token` into `.env`.

> Page tokens derived from a long-lived user token don't expire as long as the
> user stays logged in and the app stays active — good for automation.

## Automating with GitHub Actions

The workflow rotates across all US sources (`--rotate`) on a schedule and on
manual dispatch.

1. **Repo → Settings → Secrets and variables → Actions**
   - Secrets: `FB_PAGE_ID`, `FB_PAGE_ACCESS_TOKEN`
2. Adjust the `cron:` schedule in [post-reel.yml](.github/workflows/post-reel.yml)
   (default: every 3 hours, UTC). Dial it down for a new page.
3. Trigger manually from the **Actions** tab — you can pass a one-off `url`/`rss`
   or tick `no_post` to dry-run (assets are uploaded as a build artifact).

> Dedup state (`state.json`) is committed back to the repo after each run so the
> rotation never reposts a story. The workflow needs `contents: write` permission
> (already set) to push that commit.

## Notes & limits

- Scraping relies on the site exposing `og:title` / `og:image`. Most news sites
  do; for awkward ones, pass `--title` and the pipeline still uses the OG image.
- Reels require a video ≥ 3s with an audio stream — we add a silent AAC track.
- Respect each news site's terms of service and copyright before republishing
  their headlines/images.
