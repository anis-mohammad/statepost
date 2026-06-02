"""Curated list of free US news RSS feeds, verified to parse with good images.

Order matters: the rotation engine cycles through these top-to-bottom so the
page mixes sources evenly. Add/remove freely — keys are the brand labels shown
on the card.
"""

US_FEEDS = {
    "PBS NewsHour": "https://www.pbs.org/newshour/feeds/rss/headlines",
    "NPR": "https://feeds.npr.org/1001/rss.xml",
    "NBC News": "http://feeds.nbcnews.com/nbcnews/public/news",
    "CBS News": "https://www.cbsnews.com/latest/rss/main",
    "ABC News": "https://abcnews.go.com/abcnews/topstories",
    "Fox News": "https://moxie.foxnews.com/google-publisher/latest.xml",
    "CNN": "http://rss.cnn.com/rss/cnn_topstories.rss",
    "The Hill": "https://thehill.com/news/feed/",
    "Politico": "https://www.politico.com/rss/politicopicks.xml",
    "NY Times": "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
    "LA Times": "https://www.latimes.com/local/rss2.0.xml",
    "Guardian US": "https://www.theguardian.com/us-news/rss",
    "Newsweek": "https://www.newsweek.com/rss",
}
