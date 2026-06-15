"""Feed configuration for the home-page briefing panel (/api/news).

Edit these lists to tune *who* you follow — the fetch/parse logic in app.py
reads from here and never hardcodes a source. Everything here is fetched with
stdlib only (urllib + xml.etree + json); no source needs an API key.
"""

# Tech-news RSS/Atom feeds. Plain XML over HTTPS, no key.
NEWS_FEEDS = [
    ("Hacker News", "https://hnrss.org/frontpage"),
    ("TechCrunch", "https://techcrunch.com/feed/"),
    ("The Verge", "https://www.theverge.com/rss/index.xml"),
    ("Ars Technica", "https://feeds.arstechnica.com/arstechnica/index"),
]

# Bluesky founder/builder handles. The public AppView serves author feeds with
# no auth: app.bsky.feed.getAuthorFeed. Use the full handle (no leading @).
BLUESKY_HANDLES = [
    "pmarca.bsky.social",
    "paulg.bsky.social",
]

# Founder/company blogs that publish RSS (a calmer signal than social).
BLOG_FEEDS = [
    ("Stratechery (free)", "https://stratechery.com/feed/"),
]

# Company job boards. Greenhouse and Lever both serve free public JSON per
# company; the value is the board "token" (the slug in the careers URL).
GREENHOUSE_BOARDS = ["anthropic", "openai", "stripe"]
LEVER_BOARDS = []  # e.g. "ramp", "brex" — value is the lever.co/<slug> token

# Limits — keep the panel tight and the fetch cheap.
MAX_PER_NEWS_FEED = 6
MAX_PER_BLUESKY = 4
MAX_PER_BLOG = 3
MAX_PER_BOARD = 6
