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

# (v1.23) The Bluesky/blog "social" section was retired — its overview column is
# now the Important-mail panel (config in email_sources.py, /api/mail/important).

# Company job boards. Greenhouse and Lever both serve free public JSON per
# company; the value is the board "token" (the slug in the careers URL).
# Wrong/dead tokens degrade gracefully (collected in `errors`), never a 500 —
# so it's safe to add aspirational boards. The profile scorer below decides
# which *postings* surface, so casting a wider net here only helps.
GREENHOUSE_BOARDS = [
    "anthropic", "openai", "stripe",   # AI labs + infra
    "databricks", "scaleai",           # AI/ML platforms
    "robinhood", "coinbase",           # fintech / trading-adjacent (quant + SWE)
]
LEVER_BOARDS = []  # e.g. "ramp", "brex" — value is the lever.co/<slug> token
# Quant/trading shops mostly run their own ATS (not Greenhouse/Lever), so they
# can't be pulled here without a custom adapter. The scorer still lights up the
# "Quant" tag whenever a matching role appears from any board above.

# ── Profile-tailored opportunity matching (sourced from My_Evil_Twin/me_technical.md)
# The /api/news jobs section ranks live postings against this profile: roles
# matching an interest bucket score points, internships / new-grad roles get a
# big boost, senior roles are pushed down, and clearly-irrelevant roles drop out.
# Interest buckets — bucket label -> keywords. Short tokens (ml, ai) are matched
# word-bounded (see _score_job in app.py) so they don't hit inside other words.
INTEREST_KEYWORDS = {
    "Quant": [
        "quant", "quantitative", "trading", "trader", "market making",
        "market maker", "alpha", "systematic", "execution", "low latency",
    ],
    "AI/ML": [
        "machine learning", "ml", "ai", "artificial intelligence",
        "deep learning", "llm", "nlp", "research scientist",
        "research engineer", "applied ai", "applied ml", "ml engineer",
        "ai engineer", "agent", "rag",
    ],
    "Embedded": [
        "embedded", "firmware", "fpga", "hardware", "control systems",
        "robotics", "rtos", "microcontroller", "asic", "signal processing",
    ],
    "SWE": [
        "software engineer", "software engineering", "swe", "backend",
        "full stack", "full-stack", "frontend", "platform engineer",
        "developer", "infrastructure engineer",
    ],
}

# Substring-matched (lenient: "intern" catches internship/interns). A hit here
# is the strongest positive signal — Alex is an undergrad (grad May 2028).
EARLY_CAREER_SIGNALS = [
    "intern", "new grad", "new-grad", "newgrad", "early career",
    "early-career", "university", "campus", "co-op", "graduate",
    "apprentice", "student", "2026", "2027", "2028",
]

# Substring-matched roles to push down (Alex isn't eligible / not the target).
SENIOR_SIGNALS = [
    "senior", "staff", "principal", "lead", "manager", "director",
    "head of", "executive", "sr.", "vp ", "vice president",
]

# Soft location bonus — Troy NY now, wants NY/Bay Area/CA (or remote).
PREFERRED_LOCATIONS = [
    "new york", "ny", "remote", "san francisco", "bay area",
    "california", "ca", "boston", "seattle",
]

# Limits — keep the panel tight and the fetch cheap.
MAX_PER_NEWS_FEED = 6
MAX_PER_BOARD = 40   # parse cap per board *before* scoring (was the display cap)
MAX_JOBS_SHOWN = 9   # tailored postings shown after ranking
