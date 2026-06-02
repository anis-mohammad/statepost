"""100 news-related hashtags, used 5 per post in rotating blocks.

Post 1 -> tags 1-5, post 2 -> 6-10, ... post 20 -> 96-100, then it wraps.
`#thestatepost` is added to every post on top of the rotating 5 (see main.py).
"""

BRAND_TAG = "thestatepost"          # always included, on top of the rotating 5
PER_POST = 5

HASHTAGS = [
    # general news (1-20)
    "news", "breakingnews", "newsupdate", "worldnews", "usnews",
    "dailynews", "headlines", "currentevents", "breaking", "topstories",
    "newsalert", "latestnews", "trendingnews", "viralnews", "newsfeed",
    "journalism", "media", "press", "factcheck", "livenews",
    # politics (21-40)
    "politics", "uspolitics", "government", "congress", "senate",
    "whitehouse", "election", "policy", "democracy", "washington",
    "capitolhill", "vote", "lawmakers", "legislation", "potus",
    "administration", "campaign", "political", "bipartisan", "votenews",
    # us / geography (41-50)
    "america", "usa", "american", "unitedstates", "statenews",
    "localnews", "nationalnews", "ushistory", "washingtondc", "statepolitics",
    # economy / business (51-62)
    "economy", "business", "finance", "markets", "stocks",
    "inflation", "jobs", "wallstreet", "trade", "taxes",
    "budget", "recession",
    # tech / science (63-72)
    "technology", "tech", "ai", "artificialintelligence", "science",
    "innovation", "cybersecurity", "bigtech", "data", "gadgets",
    # topics (73-90)
    "health", "healthcare", "climate", "environment", "energy",
    "education", "immigration", "justice", "law", "crime",
    "court", "supremecourt", "military", "defense", "foreignpolicy",
    "worldaffairs", "globalnews", "international",
    # engagement (91-100)
    "stayinformed", "newsoftheday", "todaynews", "breakingupdate", "developing",
    "exclusive", "investigation", "analysis", "opinion", "coverage",
]

assert len(HASHTAGS) == 100, f"expected 100 hashtags, got {len(HASHTAGS)}"


def block_at(cursor: int) -> list[str]:
    """Return the 5 hashtags starting at `cursor` (wrapping around the 100)."""
    n = len(HASHTAGS)
    c = cursor % n
    return [HASHTAGS[(c + i) % n] for i in range(PER_POST)]


def render(cursor: int) -> str:
    """'#thestatepost #tag1 #tag2 #tag3 #tag4 #tag5' for the given block."""
    tags = [BRAND_TAG] + block_at(cursor)
    return " ".join(f"#{t}" for t in tags)
