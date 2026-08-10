"""Community listing feeds + forum-buzz signals for the Opportunities briefing.

Config-only lives in `news_sources.py` (which feeds, which weights); this module
is the engine, mirroring the `email_sources.py` / `mailbox.py` split.

Two questions the old Greenhouse-only pipeline could not answer:

  "what just opened?"      -> `fetch_listings()`. Company boards return no post
                              date, so nothing could be ranked by recency. The
                              community aggregator repos publish a `date_posted`
                              per row, which makes freshness a real signal.
  "what are people
   actually applying to?"  -> `fetch_buzz()` + `company_mentions()`. No board
                              publishes an applicant count, so popularity is
                              inferred from how often a company is named right
                              now in the forums where candidates post.

Everything here is stdlib (`urllib` is injected, `json`/`gzip`/`re`/`xml`), no
API key, no model call, and deterministic — the same inputs always score the
same way. Every fetch is individually wrapped: one dead feed becomes a string in
`errors`, never an exception that reaches the request.

The HTTP getter is a parameter (`get`), not an import, so the whole module is
testable offline — the smoke tests pass a canned fetcher.
"""

from __future__ import annotations

import json
import re
import time
import xml.etree.ElementTree as ET

import news_sources

DAY = 86400.0

# Legal/filler tails dropped when matching a company name against chatter — a
# post says "Scale OA", never "Scale AI, Inc. OA".
_NAME_TAILS = (
    "inc", "inc.", "llc", "ltd", "ltd.", "corp", "corp.", "corporation",
    "co", "co.", "company", "group", "holdings", "technologies", "technology",
    "labs", "lab", "systems", "solutions", "partners", "capital", "securities",
    "management", "global", "international", "usa", "us",
)
_WORD_RE = re.compile(r"[a-z0-9&+]+")
_MAX_NGRAM = 4


def _localname(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag


# ── Community listing feeds ─────────────────────────────────────────────────

def feeds_for_stage(stage: str) -> list[tuple[str, str]]:
    """The configured listing feeds that serve this career stage.

    Each feed is a multi-megabyte download, so stage-gating is a real cost
    control, not just relevance: a senior profile fetches none of them.
    """
    stage = (stage or "any").strip().lower()
    return [(label, url) for label, url, stages in news_sources.COMMUNITY_LISTINGS
            if stage in stages]


def _normalize(raw: dict, label: str, now: float) -> dict | None:
    """One aggregator row -> a posting dict shaped like the board postings in
    `app._fetch_jobs`, or None if it's closed, hidden, undated or stale.

    Handles both schemas in use: SimplifyJobs rows carry `terms` + `category`,
    the vanshb03 fork carries a single `season` and neither of the other two.
    """
    if raw.get("active") is False or raw.get("is_visible") is False:
        return None
    title = str(raw.get("title") or "").strip()
    company = str(raw.get("company_name") or "").strip()
    url = str(raw.get("url") or raw.get("company_url") or "").strip()
    if not title or not url:
        return None
    try:
        posted = float(raw.get("date_posted") or raw.get("date_updated") or 0)
    except (TypeError, ValueError):
        return None
    # Undated rows can't be ranked for freshness, which is the entire reason
    # these feeds are here — drop rather than guess a date.
    if posted <= 0 or (now - posted) > news_sources.COMMUNITY_MAX_AGE_DAYS * DAY:
        return None
    terms = raw.get("terms")
    if not isinstance(terms, list):
        terms = [raw["season"]] if raw.get("season") else []
    locations = raw.get("locations")
    location = ", ".join(str(x) for x in locations[:2]) if isinstance(locations, list) else ""
    return {
        # `source` is what the UI prints as the row's byline — the company reads
        # better there than the feed name, and it also drives the round-robin in
        # _fetch_jobs, so one company can't take every slot.
        "source": company or label,
        "title": title,
        "url": url,
        "location": location,
        "company": company,
        "posted": posted,
        "terms": [str(t) for t in terms],
        "via": label,
    }


def fetch_listings(feeds, get, now: float | None = None) -> tuple[list[dict], list[str]]:
    """Fetch + normalize the community feeds. Returns (postings, errors).

    `get(url)` must return raw bytes; `feeds` is [(label, url)] from
    `feeds_for_stage()`. Only open, visible, recently-posted rows survive.
    """
    now = time.time() if now is None else now
    out: list[dict] = []
    errors: list[str] = []
    for label, url in feeds:
        try:
            rows = json.loads(get(url))
            if not isinstance(rows, list):
                raise ValueError("expected a JSON array")
        except Exception as e:  # noqa: BLE001 — one dead feed must not sink the panel
            errors.append(f"{label}: {type(e).__name__}")
            continue
        fresh = []
        for raw in rows:
            if isinstance(raw, dict):
                item = _normalize(raw, label, now)
                if item:
                    fresh.append(item)
        fresh.sort(key=lambda j: -j["posted"])
        out.extend(fresh[: news_sources.MAX_PER_COMMUNITY_FEED])
    return out, errors


# ── Forum buzz ──────────────────────────────────────────────────────────────

def _parse_buzz(payload: bytes) -> list[str]:
    """Discussion titles out of either shape we fetch: a Reddit Atom feed or the
    Hacker News Algolia JSON. Sniffed by first byte rather than by URL so a
    source can change host without breaking the parse."""
    head = payload.lstrip()[:1]
    if head in (b"{", b"["):
        data = json.loads(payload)
        hits = data.get("hits", []) if isinstance(data, dict) else data
        return [str(h.get("title") or h.get("story_title") or "").strip()
                for h in hits if isinstance(h, dict)]
    root = ET.fromstring(payload)
    titles = []
    for entry in root.iter():
        if _localname(entry.tag) not in ("entry", "item"):
            continue
        for child in entry:
            if _localname(child.tag) == "title" and child.text:
                titles.append(child.text.strip())
                break
    return titles


def fetch_buzz(feeds, get) -> tuple[list[str], list[str]]:
    """Collect recent discussion titles. Returns (titles, errors).

    Reddit answers 429 to a burst from one IP; that surfaces as a skipped source
    and the ranking simply loses the buzz bonus for this refresh.
    """
    titles: list[str] = []
    errors: list[str] = []
    for label, url in feeds:
        try:
            titles.extend(t for t in _parse_buzz(get(url)) if t)
        except Exception as e:  # noqa: BLE001
            errors.append(f"buzz/{label}: {type(e).__name__}")
    return titles[: news_sources.MAX_BUZZ_TITLES], errors


def _tokens(text: str) -> list[str]:
    return _WORD_RE.findall(text.lower())


def _name_keys(company: str) -> list[str]:
    """Match keys for a company name: the whole name, plus the name with a legal
    or filler tail removed ("Citadel Securities" also answers to "Citadel").

    A single-word key must be >=4 characters and not an everyday English word,
    or it matches half the forum ("Block", "Path", "Scale").
    """
    toks = _tokens(company)
    while len(toks) > 1 and toks[-1] in _NAME_TAILS:
        toks = toks[:-1]
    if not toks:
        return []
    keys = [" ".join(toks)]
    if len(toks) > 1:
        keys.append(toks[0])
    out = []
    for k in keys:
        if " " not in k and (len(k) < 4 or k in news_sources.BUZZ_STOPWORDS):
            continue
        if k not in out:
            out.append(k)
    return out


def _ngram_counts(titles) -> dict[str, int]:
    """Every 1..4-word phrase in the titles, counted once per title it appears in.

    Counting phrases up front turns matching into dict lookups: the alternative
    (a regex per company against every title) is thousands of scans per refresh,
    since the pool routinely holds >1000 distinct companies. Word-bounded by
    construction — the text is tokenized, so "ai" can never match inside "said".
    """
    counts: dict[str, int] = {}
    for title in titles:
        toks = _tokens(title)
        seen = set()
        for n in range(1, _MAX_NGRAM + 1):
            for i in range(len(toks) - n + 1):
                seen.add(" ".join(toks[i:i + n]))
        for phrase in seen:
            counts[phrase] = counts.get(phrase, 0) + 1
    return counts


def company_mentions(titles, companies) -> dict[str, int]:
    """company name -> how many discussion titles named it (0 entries omitted).

    Aliases are resolved first, so "JPMC OA" credits the JPMorgan Chase posting.
    Keys are the company strings exactly as passed in, so the caller can look up
    with `job["company"]`.
    """
    counts = _ngram_counts(titles)
    if not counts:
        return {}
    for alias, canonical in news_sources.COMPANY_ALIASES.items():
        hits = counts.get(" ".join(_tokens(alias)), 0)
        if hits:
            key = " ".join(_tokens(canonical))
            counts[key] = counts.get(key, 0) + hits
    out: dict[str, int] = {}
    for company in companies:
        if not company:
            continue
        total = max((counts.get(k, 0) for k in _name_keys(company)), default=0)
        if total:
            out[company] = total
    return out


# ── Scoring signals ─────────────────────────────────────────────────────────

def signals(job: dict, mentions: dict, now: float | None = None) -> tuple[int, list[str]]:
    """Freshness + buzz contribution for one posting: (bonus, tags).

    Additive on top of `app._score_job`'s interest/stage/location scoring, so a
    buzzing role the user has no interest in still can't outrank a real match.
    Board postings carry no date and get no freshness bonus — that's why the
    community feeds exist rather than replacing the boards.
    """
    now = time.time() if now is None else now
    bonus = 0
    tags: list[str] = []
    posted = job.get("posted") or 0
    if posted:
        age = (now - posted) / DAY
        if age <= news_sources.FRESH_TODAY_DAYS:
            bonus += news_sources.FRESH_TODAY_BONUS
            tags.append("Just posted")
        elif age <= news_sources.FRESH_WEEK_DAYS:
            bonus += news_sources.FRESH_WEEK_BONUS
            tags.append("New this week")
    hits = mentions.get(job.get("company") or "", 0)
    if hits:
        bonus += min(hits * news_sources.BUZZ_BONUS_PER_MENTION,
                     news_sources.BUZZ_BONUS_CAP)
        tags.append(f"Buzzing ×{hits}" if hits > 1 else "Buzzing")
    return bonus, tags
