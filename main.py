"""News -> photocard -> 3s video -> Facebook Reel.

Examples:
  # From a single article URL, generate card + video only (no posting):
  python main.py --url "https://www.bbc.com/news/..." --no-post

  # From an RSS feed (newest entry), generate and publish a Reel:
  python main.py --rss "https://feeds.bbci.co.uk/news/rss.xml"

  # Override the headline / brand label:
  python main.py --url "..." --title "Custom headline" --brand "MY NEWS"

Credentials for posting come from environment / .env:
  FB_PAGE_ID, FB_PAGE_ACCESS_TOKEN
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date

from dotenv import load_dotenv

from src import scraper
from src.photocard import CardStyle, make_frames, save_card
from src.video import encode_frames


def _slug(text: str, maxlen: int = 40) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (s[:maxlen] or "card").strip("-")


def clean_title(title: str) -> str:
    """Strip newsroom prefixes/suffixes like 'WATCH LIVE:' or '– live'."""
    t = title.strip()
    # leading markers: WATCH, WATCH LIVE, LIVE, LIVE UPDATES, Live blog, etc.
    t = re.sub(r"^(watch\s*live|watch|live\s*updates?|live\s*blog|live)\s*[:\-–—]\s*",
               "", t, flags=re.IGNORECASE)
    # trailing markers: ' – live', ' - live updates'
    t = re.sub(r"\s*[\-–—]\s*(live(\s*updates?)?|live\s*blog)\s*$", "", t, flags=re.IGNORECASE)
    return t.strip() or title.strip()


def build_caption(art: scraper.Article, extra: str | None, hashtags: str | None = None) -> str:
    parts = [art.title]
    if extra:
        parts.append(extra)
    caption = "\n".join(parts)
    if hashtags:
        caption += f"\n\n{hashtags}"
    return caption


def build_source_comment(art: scraper.Article) -> str:
    """Attribution posted as the first comment (kept out of the caption)."""
    return f"Source: {art.source}\n{art.url}"


def _save_staged(path, art, video_path, card_path, caption, rotation_state, state_path,
                 hashtag_cursor) -> None:
    payload = {
        "title": art.title,
        "source": art.source,
        "url": art.url,
        "video_path": video_path,
        "card_path": card_path,
        "caption": caption,
        "source_comment": build_source_comment(art),   # posted as first comment
        "rotation_state": rotation_state,   # advanced cursor (or None for --url/--rss)
        "state_path": state_path,
        "hashtag_cursor": hashtag_cursor,   # block used; advanced on publish
    }
    with open(path, "w") as fh:
        json.dump(payload, fh, indent=2)


def _publish_staged(staged_path: str) -> int:
    if not os.path.exists(staged_path):
        print(f"✗ Nothing staged ({staged_path}). Run --rotate / --url first.")
        return 1
    with open(staged_path) as fh:
        staged = json.load(fh)
    video_path = staged["video_path"]
    if not os.path.exists(video_path):
        print(f"✗ Staged video missing: {video_path}")
        return 1

    print(f"→ Publishing staged Reel: {staged['title']!r}  [{staged['source']}]")
    from src.facebook import FacebookError, comment, post_reel  # late import: creds only here

    result = post_reel(video_path, description=staged["caption"])
    print(f"✓ Published. video_id={result.get('video_id')}  post_id={result.get('post_id')}")

    # source attribution as the first comment (kept out of the caption)
    src_comment = staged.get("source_comment", "")
    posted_comment = False
    # video_id works for reels; post_id hits a deprecated endpoint — try video first
    for obj_id in (result.get("video_id"), result.get("post_id")):
        if not obj_id or not src_comment:
            continue
        try:
            cres = comment(obj_id, src_comment)
            print(f"✓ Source comment posted (id={cres.get('id')}).")
            posted_comment = True
            break
        except FacebookError:
            continue
    if src_comment and not posted_comment:
        print("⚠ Could not auto-post the comment (needs App Review for pages_manage_engagement).")
        print("  Paste this as the first comment manually:\n")
        print("  " + src_comment.replace("\n", "\n  ") + "\n")

    # advance rotation + record this URL so it's never reposted
    from src import aggregator

    if staged.get("rotation_state") and staged.get("url"):
        aggregator.mark_posted(staged["state_path"], staged["rotation_state"], staged["url"])
    # advance the hashtag block so the next post uses the next 5
    if staged.get("hashtag_cursor") is not None and staged.get("state_path"):
        aggregator.advance_hashtags(staged["state_path"], staged["hashtag_cursor"])
    os.remove(staged_path)
    return 0


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    p = argparse.ArgumentParser(description="News -> Facebook Reel pipeline")
    src_grp = p.add_mutually_exclusive_group()
    src_grp.add_argument("--url", help="article URL (generic OG-tag scrape)")
    src_grp.add_argument("--rss", help="RSS/Atom feed URL")
    src_grp.add_argument(
        "--rotate",
        action="store_true",
        help="auto-pick the next unposted story, rotating across all US sources (stages it)",
    )
    p.add_argument("--publish", action="store_true", help="publish the previously staged Reel")
    p.add_argument("--rss-index", type=int, default=0, help="entry index in feed (0=newest)")
    p.add_argument("--state", default="state.json", help="rotation/dedup state file")
    p.add_argument("--staged", default="staged.json", help="staged-Reel file (prepare→publish)")
    p.add_argument("--title", help="override the scraped headline")
    p.add_argument("--brand", help="main brand/logo text on the card (default: THE STATE POST)")
    p.add_argument("--duration", type=float, default=3.0, help="video length in seconds")
    p.add_argument("--no-post", action="store_true", help="generate + stage but do not publish")
    p.add_argument("--caption", help="extra text appended to the Reel caption")
    p.add_argument("--outdir", default="output", help="output directory")
    args = p.parse_args(argv)

    # publish mode: post the exact staged Reel (what was previewed)
    if args.publish:
        return _publish_staged(args.staged)

    if not (args.url or args.rss or args.rotate):
        p.error("one of --url, --rss, --rotate, or --publish is required")

    # 1. scrape
    print("→ Fetching article…")
    rotation_state = None
    if args.rotate:
        from src import aggregator

        art, source, rotation_state = aggregator.pick_next(args.state)
        print(f"  [rotation → {source}]")
    elif args.rss:
        art = scraper.from_rss(args.rss, args.rss_index)
    else:
        art = scraper.article(args.url)
    art.title = args.title if args.title else clean_title(art.title)
    print(f"  {art}")

    base = f"{date.today():%Y%m%d}-{_slug(art.title)}"
    card_path = f"{args.outdir}/{base}.png"
    video_path = f"{args.outdir}/{base}.mp4"

    # 2. photocard
    print("→ Building photocard…")
    style = CardStyle(brand=args.brand) if args.brand else CardStyle()
    save_card(art, card_path, style)
    print(f"  {card_path}")

    # 3. video — animated card with the blinking "live" dot
    print("→ Rendering video…")
    fps = 30
    n_frames = max(1, int(round(args.duration * fps)))
    frames = make_frames(art, style, n_frames, fps=fps)
    encode_frames(frames, video_path, fps=fps, duration=args.duration)
    print(f"  {video_path}")

    # 4. stage the exact assets so --publish posts precisely this story
    from src import aggregator

    hashtag_line, hashtag_cursor = aggregator.peek_hashtags(args.state)
    caption = build_caption(art, args.caption, hashtag_line)
    print(f"  hashtags: {hashtag_line}")
    _save_staged(args.staged, art, video_path, card_path, caption,
                 rotation_state, args.state, hashtag_cursor)

    if args.no_post:
        print(f"✓ Staged (not posted). Review {card_path}, then run:  python main.py --publish")
        return 0

    # rotation must be reviewed before going live; direct --url/--rss can post now
    if args.rotate:
        print(f"✓ Staged. Review {card_path}, then run:  python main.py --publish")
        return 0
    return _publish_staged(args.staged)


if __name__ == "__main__":
    sys.exit(main())
