"""Regalia's own version — the single source of truth for the update check.

Releases are cut by pushing a git tag `v<__version__>` (see
`.github/workflows/release.yml`); the GitHub Release's `tag_name` is what the
updater compares this against. Bump this string in the same commit that you tag.

stdlib only; imported by updater/app, imports none of them.
"""

from __future__ import annotations

import re

__version__ = "1.31"

# owner/repo the release check queries (github.com/<REPO>). The desktop builds
# are published as Releases here; the updater hits its `releases/latest` API.
REPO = "alex-htutt/regalia"


def parse(tag: str) -> tuple[int, ...]:
    """Turn a version-ish string ('v1.29', '1.25.2', 'v1.30-beta') into a tuple
    of ints for ordering. Leading 'v' and any trailing pre-release suffix are
    dropped; missing/garbage components count as 0 so a comparison never raises."""
    s = (tag or "").strip().lstrip("vV")
    s = re.split(r"[-+ ]", s, maxsplit=1)[0]  # drop pre-release / build metadata
    out: list[int] = []
    for part in s.split("."):
        m = re.match(r"\d+", part)
        out.append(int(m.group()) if m else 0)
    return tuple(out) or (0,)


def is_newer(candidate: str, current: str = __version__) -> bool:
    """True when `candidate` (e.g. a GitHub tag) is a strictly newer release
    than `current` (this build). Zero-pads so (1,29) and (1,29,0) compare equal."""
    a, b = parse(candidate), parse(current)
    width = max(len(a), len(b))
    a += (0,) * (width - len(a))
    b += (0,) * (width - len(b))
    return a > b
