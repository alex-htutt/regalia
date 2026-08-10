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

# ── Profile-tailored opportunity matching.
# The /api/news jobs section ranks live postings against the user's profile: roles
# matching an interest bucket score points, roles matching the user's career stage
# are boosted, off-stage roles are pushed down, and clearly-irrelevant roles drop
# out. Everything below is the SHIPPED DEFAULT / CATALOG — each user overrides it
# from Settings → Personalization (stored in config, resolved in app.py). A fresh
# install (no personalization saved) uses these lists as-is.
#
# INTEREST_KEYWORDS is the full CATALOG of interest buckets the user picks from;
# when the user selects a subset, only those buckets score. bucket label ->
# keywords. Short tokens (ml, ai) are matched word-bounded (see _score_job in
# app.py) so they don't hit inside other words.
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
    "Data": [
        "data engineer", "data scientist", "data science", "analytics",
        "data analyst", "etl", "data platform", "business intelligence",
    ],
    "Security": [
        "security engineer", "security", "cybersecurity", "appsec",
        "infosec", "penetration", "cryptography", "threat", "vulnerability",
    ],
    "DevOps/Infra": [
        "devops", "site reliability", "sre", "cloud engineer", "kubernetes",
        "platform engineer", "infrastructure", "systems engineer",
    ],
    "Product": [
        "product manager", "product management", "program manager",
        "technical product", "product owner",
    ],
    "Design": [
        "designer", "product design", "ux", "ui", "user experience",
        "user research", "design engineer",
    ],
}

# Substring-matched (lenient: "intern" catches internship/interns). A hit here
# is the strongest positive signal — tune for your career stage (these defaults
# assume an early-career/student profile).
EARLY_CAREER_SIGNALS = [
    "intern", "new grad", "new-grad", "newgrad", "early career",
    "early-career", "university", "campus", "co-op", "graduate",
    "apprentice", "student", "2026", "2027", "2028",
]

# Substring-matched roles to push down (not the target for this profile).
SENIOR_SIGNALS = [
    "senior", "staff", "principal", "lead", "manager", "director",
    "head of", "executive", "sr.", "vp ", "vice president",
]

# Soft location bonus — set to the regions you'd actually take a role in.
PREFERRED_LOCATIONS = [
    "new york", "ny", "remote", "san francisco", "bay area",
    "california", "ca", "boston", "seattle",
]

# ── Community listing feeds (v1.36) — "what just opened".
# Company boards (above) only show the handful of companies you thought to list,
# and they carry no post date, so nothing can be ranked by freshness. These are
# the community-maintained aggregator repos that students actually coordinate
# around (the ones linked from r/csMajors / Discord / the internship IG accounts)
# — each publishes a machine-readable listings.json, updated continuously, with a
# `date_posted` timestamp. That timestamp is what makes "just opened" possible.
#
# Each entry: (label, url, stages) — `stages` are the career_stage values the
# feed serves; a feed is only fetched when it matches the user's stage ("any"
# resolves to the early-career feeds, matching the scorer's default nudge).
# Dead/renamed repos degrade into `errors`, never a 500. GitHub redirects a
# renamed repo transparently, so a stale season slug keeps working.
COMMUNITY_LISTINGS = [
    ("Simplify · internships",
     "https://raw.githubusercontent.com/SimplifyJobs/Summer2027-Internships/dev/.github/scripts/listings.json",
     ("student", "early", "any")),
    ("Simplify · new grad",
     "https://raw.githubusercontent.com/SimplifyJobs/New-Grad-Positions/dev/.github/scripts/listings.json",
     ("early",)),
    ("vanshb03 · internships",
     "https://raw.githubusercontent.com/vanshb03/Summer2027-Internships/dev/.github/scripts/listings.json",
     ("student", "any")),
]

# A community posting older than this is not "just opened" and is dropped before
# scoring — these feeds carry years of dead history (~14k rows, ~1.5k still open).
COMMUNITY_MAX_AGE_DAYS = 21
MAX_PER_COMMUNITY_FEED = 120  # kept after the active+fresh filter, before scoring

# ── Forum buzz (v1.36) — "what people are actually applying to".
# Nobody publishes an applicant count, so popularity is inferred from how often a
# company is being talked about *right now* in the places early-career candidates
# post ("X OA just dropped", "Y superday", "Z return offers"). Titles are pulled
# from these feeds, n-grammed, and matched against the company names already in
# the posting pool — see opportunities.company_mentions(). No API key, no model.
#
# NOTE ON INSTAGRAM / X: neither has a keyless public read endpoint any more
# (X removed free API read access; the Instagram Graph API needs an approved
# business app), so neither can be a source here. Reddit's per-subreddit Atom
# feed is the closest working stand-in and covers the same conversation.
# Reddit rate-limits hard per IP (HTTP 429) — the briefing TTL cache is what
# keeps this polite, so don't add many more subreddits or lower NEWS_TTL far.
BUZZ_FEEDS = [
    ("r/csMajors", "https://www.reddit.com/r/csMajors/new.rss?limit=50"),
    ("r/internships", "https://www.reddit.com/r/internships/new.rss?limit=50"),
    ("Hacker News",
     "https://hn.algolia.com/api/v1/search_by_date?query=internship&tags=story&hitsPerPage=50"),
]

# Company nicknames as they're actually typed in forum posts -> the company name
# as it appears in a posting feed. Without these the obvious chatter ("JPMC OA",
# "BofA superday") never matches the listing it's about.
COMPANY_ALIASES = {
    "jpmc": "jpmorgan chase", "jpm": "jpmorgan chase", "jp morgan": "jpmorgan chase",
    "gs": "goldman sachs", "bofa": "bank of america", "ms": "morgan stanley",
    "amzn": "amazon", "msft": "microsoft", "goog": "google", "meta": "meta",
    "js": "jane street", "citsec": "citadel securities", "hrt": "hudson river trading",
    "sig": "susquehanna international group", "drw": "drw", "imc": "imc trading",
    "2sig": "two sigma", "d.e. shaw": "de shaw", "deshaw": "de shaw",
    "rbx": "roblox", "nvda": "nvidia", "tsla": "tesla", "pltr": "palantir",
}

# Single-word company names that are ordinary English and would match constantly
# ("Block", "Path", "Anthropic" is fine — "Block" is not). Skipped by the matcher.
BUZZ_STOPWORDS = {
    "block", "path", "apex", "atlas", "bond", "chase", "circle", "coach",
    "core", "crew", "figure", "flex", "found", "grid", "guide", "hive", "leap",
    "level", "lever", "loop", "match", "mission", "notion", "orbit", "pace",
    "peak", "pilot", "point", "prime", "pulse", "range", "reach", "ride",
    "rise", "scale", "shift", "signal", "solo", "spark", "sphere", "spot",
    "stack", "stream", "summit", "swift", "target", "tempo", "thread", "tide",
    "trust", "vault", "verse", "via", "wave", "wing", "zone",
}
MAX_BUZZ_TITLES = 400  # cap on discussion titles held for n-gramming

# Scoring weights for the two new signals (interest buckets are worth 3 each and
# an on-stage role 5, in _score_job — these are tuned to matter without drowning
# a genuine interest match).
FRESH_TODAY_DAYS = 2   # <= this many days old  -> "Just posted"
FRESH_WEEK_DAYS = 7    # <= this many days old  -> "New this week"
FRESH_TODAY_BONUS = 4
FRESH_WEEK_BONUS = 2
BUZZ_BONUS_PER_MENTION = 2
BUZZ_BONUS_CAP = 4

# Limits — keep the panel tight and the fetch cheap.
MAX_PER_NEWS_FEED = 6
MAX_PER_BOARD = 40   # parse cap per board *before* scoring (was the display cap)
MAX_JOBS_SHOWN = 12  # tailored postings shown after ranking
# Hard cap on how many slots one company may take. The score tie-break alone
# can't hold this line once the pool is large: a company posting 40 matching
# roles (ByteDance, Amazon) lands several of them at the top of a score band and
# crowds out every other employer. Relaxed only if the panel can't otherwise fill.
MAX_PER_COMPANY = 2
