"""Extract a news article's headline, image and source from a URL or RSS feed.

Two modes:
  - article(url): scrape a single page using Open Graph / Twitter / meta tags.
  - from_rss(feed_url): pull the latest (or Nth) entry from an RSS/Atom feed,
    then enrich it by scraping the entry's page for a better image.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import feedparser
import requests
from bs4 import BeautifulSoup

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
HEADERS = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}
TIMEOUT = 20


@dataclass
class Article:
    title: str
    image_url: str | None
    source: str
    url: str
    description: str = ""

    def __str__(self) -> str:
        img = (self.image_url[:60] + "...") if self.image_url else "(none)"
        return f"Article(source={self.source!r}, title={self.title!r}, image={img})"


def _clean(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def _meta(soup: BeautifulSoup, *keys: str) -> str | None:
    """Return the first matching <meta> content for property/name keys."""
    for key in keys:
        tag = soup.find("meta", attrs={"property": key}) or soup.find(
            "meta", attrs={"name": key}
        )
        if tag and tag.get("content"):
            return _clean(tag["content"])
    return None


def _source_name(soup: BeautifulSoup, url: str) -> str:
    site = _meta(soup, "og:site_name", "application-name")
    if site:
        return site
    host = urlparse(url).netloc.lower()
    host = re.sub(r"^www\.", "", host)
    # "bbc.com" -> "BBC", "prothomalo.com" -> "Prothomalo"
    name = host.split(".")[0]
    return name.upper() if len(name) <= 4 else name.capitalize()


def fetch_html(url: str) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.text


def article(url: str) -> Article:
    """Scrape a single article page using OG / Twitter / standard meta tags."""
    soup = BeautifulSoup(fetch_html(url), "html.parser")

    title = (
        _meta(soup, "og:title", "twitter:title")
        or _clean(soup.title.string if soup.title else None)
        or (_clean(soup.h1.get_text()) if soup.h1 else "")
    )

    image = _meta(
        soup,
        "og:image:secure_url",
        "og:image",
        "twitter:image",
        "twitter:image:src",
    )
    if image:
        image = urljoin(url, image)

    description = _meta(soup, "og:description", "twitter:description", "description")
    source = _source_name(soup, url)

    if not title:
        raise ValueError(f"Could not extract a headline from {url}")

    return Article(
        title=title,
        image_url=image,
        source=source,
        url=url,
        description=description or "",
    )


def _entry_image(entry) -> str | None:
    """Best-effort image straight from an RSS entry, before falling back to scrape."""
    media = entry.get("media_content") or entry.get("media_thumbnail")
    if media and isinstance(media, list) and media[0].get("url"):
        return media[0]["url"]
    for link in entry.get("links", []):
        if link.get("type", "").startswith("image") and link.get("href"):
            return link["href"]
    # Sometimes the image is embedded as <img> in the summary HTML.
    summary = entry.get("summary", "")
    m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', summary)
    if m:
        return m.group(1)
    return None


def from_rss(feed_url: str, index: int = 0) -> Article:
    """Return the article at `index` (0 = newest) of an RSS/Atom feed.

    Scrapes the entry's page to upgrade the image / source when possible,
    but falls back gracefully to the feed's own data.
    """
    feed = feedparser.parse(feed_url)
    if not feed.entries:
        raise ValueError(f"No entries found in feed {feed_url}")
    if index >= len(feed.entries):
        raise IndexError(
            f"Feed has {len(feed.entries)} entries; index {index} out of range"
        )

    entry = feed.entries[index]
    link = entry.get("link", feed_url)
    feed_title = _clean(entry.get("title", ""))
    feed_image = _entry_image(entry)
    feed_source = _clean(feed.feed.get("title", "")) or _source_name(
        BeautifulSoup("", "html.parser"), link
    )

    # Try to enrich from the page; keep feed values if scraping fails.
    try:
        scraped = article(link)
        return Article(
            title=scraped.title or feed_title,
            image_url=scraped.image_url or feed_image,
            source=scraped.source or feed_source,
            url=link,
            description=scraped.description,
        )
    except Exception:
        return Article(
            title=feed_title,
            image_url=feed_image,
            source=feed_source,
            url=link,
            description=_clean(entry.get("summary", "")),
        )


if __name__ == "__main__":
    import sys

    target = sys.argv[1] if len(sys.argv) > 1 else "https://www.bbc.com/news"
    if target.endswith((".xml", ".rss")) or "rss" in target or "feed" in target:
        print(from_rss(target))
    else:
        print(article(target))
