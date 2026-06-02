"""Rotate across all US feeds and return the next not-yet-posted article.

State is a small JSON file (default output/state.json):
  { "posted": ["url1", "url2", ...], "cursor": <int> }

`cursor` remembers which source we used last so each run advances to the next
source (round-robin), giving the page an even mix. Within a source we walk its
newest entries and skip any URL already in `posted`.
"""
from __future__ import annotations

import json
import os

from . import scraper
from .feeds import US_FEEDS

DEFAULT_STATE = "state.json"      # repo root so it can be committed back in CI
MAX_HISTORY = 1000          # cap the posted-URL list so the file stays small
ENTRIES_PER_FEED = 8        # how deep to look for a fresh story per source


def _load(path: str) -> dict:
    if os.path.exists(path):
        try:
            with open(path) as fh:
                data = json.load(fh)
                data.setdefault("posted", [])
                data.setdefault("cursor", 0)
                data.setdefault("hashtag_cursor", 0)
                return data
        except Exception:
            pass
    return {"posted": [], "cursor": 0, "hashtag_cursor": 0}


def _save(path: str, state: dict) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    state["posted"] = state["posted"][-MAX_HISTORY:]
    with open(path, "w") as fh:
        json.dump(state, fh, indent=2)


def pick_next(state_path: str = DEFAULT_STATE, feeds: dict | None = None):
    """Return (Article, source_name). Rotates sources; skips already-posted URLs.

    Raises RuntimeError if every source's recent entries have all been posted.
    """
    feeds = feeds or US_FEEDS
    names = list(feeds.keys())
    state = _load(state_path)
    seen = set(state["posted"])
    start = state["cursor"] % len(names)

    # Try each source once, starting at the rotation cursor.
    for step in range(len(names)):
        idx = (start + step) % len(names)
        name = names[idx]
        url = feeds[name]
        try:
            parsed = scraper.feedparser.parse(url)
        except Exception:
            continue
        for i in range(min(ENTRIES_PER_FEED, len(parsed.entries))):
            link = parsed.entries[i].get("link", "")
            if not link or link in seen:
                continue
            try:
                art = scraper.from_rss(url, i)
            except Exception:
                continue
            if not art.title:
                continue
            # advance cursor past this source so next run uses the following one
            state["cursor"] = (idx + 1) % len(names)
            return art, name, state

    raise RuntimeError("No fresh (unposted) story found across any source right now.")


def mark_posted(state_path: str, state: dict, url: str) -> None:
    if url and url not in state["posted"]:
        state["posted"].append(url)
    _save(state_path, state)


def peek_hashtags(state_path: str) -> tuple[str, int]:
    """Return (rendered hashtag line, cursor) for the next post — does NOT advance."""
    from .hashtags import render

    cursor = _load(state_path).get("hashtag_cursor", 0)
    return render(cursor), cursor


def advance_hashtags(state_path: str, used_cursor: int) -> None:
    """Advance the hashtag cursor by one block (5) after a successful post."""
    from .hashtags import HASHTAGS, PER_POST

    state = _load(state_path)
    state["hashtag_cursor"] = (used_cursor + PER_POST) % len(HASHTAGS)
    _save(state_path, state)


if __name__ == "__main__":
    art, source, _ = pick_next()
    print(f"[{source}] {art.title}\n  {art.url}")
