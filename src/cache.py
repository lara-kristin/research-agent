"""
On-disk response cache.

Exists to conserve a daily request allowance during development, not to make
the system faster. The LLM provider permits a fixed number of requests per
day, and unlike a per-minute rate that limit cannot be relieved by pacing:
only not making the call conserves it. Repeated development runs would
otherwise spend the same allowance as real ones.

Deliberately bypassable. A cached run and a live run must not be
indistinguishable, because a demonstration replaying yesterday's answers while
appearing to exercise the live services would misrepresent the system. Every
hit is logged, and --no-cache forces a live run.
"""

import hashlib
import json
import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)

CACHE_DIR = Path("cache")

# Twenty-four hours. Consecutive identical searches were observed returning
# the same records in the same order, so a cached answer does not conceal
# ranking variation; what it can conceal is a paper published since. A day
# covers a working session while keeping any answer at most one day old, and
# acts as a backstop against a cache left unused for weeks silently serving
# stale results. Currency is otherwise a per-run decision, made with
# --no-cache rather than guessed at here.
MAX_AGE_SECONDS = 24 * 60 * 60


def _key(method: str, url: str, params: dict | None, body: object | None) -> str:
    """
    Derive a filename from everything that distinguishes one request from
    another.

    Hashed rather than used directly: a URL contains characters no filesystem
    accepts, and a prompt is far longer than a filename may be. sort_keys
    makes the digest independent of dictionary ordering, so two identical
    requests cannot produce two different keys.

    The API key is deliberately not part of this. It does not change the
    response, and hashing it would write a value derived from a credential to
    disk.
    """
    material = json.dumps(
        {"method": method, "url": url, "params": params, "body": body},
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]


def _describe(url: str, params: dict | None) -> str:
    """
    Identify a request in a log line.

    The URL alone is not enough: every search shares one endpoint, so three
    cache hits in a run would be three identical lines with no way to tell
    which query each answered. The query is what distinguishes them to a
    reader.
    """
    if params and "query" in params:
        return f"{url} query={params['query']!r}"
    return url


def read(method: str, url: str, params: dict | None, body: object | None) -> dict | None:
    """
    Return a cached response, or None if there is none or it has expired.

    A hit is logged at INFO rather than DEBUG, so that a run's log shows
    plainly which responses came from disk. A reader of the log should never
    have to guess whether a run touched the live services.
    """
    path = CACHE_DIR / f"{_key(method, url, params, body)}.json"
    if not path.exists():
        return None

    try:
        entry = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        # A damaged cache file is not a reason to fail a run: the request can
        # simply be made. Reported rather than passed over silently, because a
        # cache that never returns a hit would otherwise look like a cache
        # that is working.
        logger.warning("Unreadable cache entry %s, refetching: %s", path.name, exc)
        return None

    # Parsing successfully is not the same as having the expected shape. An
    # entry truncated by an interrupted write, or written by an earlier version
    # of this module, can be valid JSON and still lack these keys, and reading
    # into it directly would raise a KeyError part-way through a run, after
    # LLM calls had already been spent. This is the same fault as the original
    # stage 1 defect, where a response was read without checking whether it
    # was the kind of response expected.
    if not isinstance(entry, dict) or "stored_at" not in entry or "response" not in entry:
        logger.warning(
            "Cache entry %s is not in the expected form, refetching", path.name
        )
        return None

    if not isinstance(entry["stored_at"], (int, float)):
        logger.warning(
            "Cache entry %s has an unusable timestamp, refetching", path.name
        )
        return None

    age = time.time() - entry["stored_at"]
    if age > MAX_AGE_SECONDS:
        logger.info(
            "Cache entry expired after %.1f hours: %s",
            age / 3600,
            _describe(url, params),
        )
        return None

    # Reported in minutes rather than hours: entries are usually seconds old
    # during development, and 0.0 hours tells a reader nothing about whether a
    # hit came from this run or yesterday's.
    logger.info(
        "Cache hit (%.1f minutes old, not a live request): %s",
        age / 60,
        _describe(url, params),
    )
    return entry["response"]


def write(
    method: str,
    url: str,
    params: dict | None,
    body: object | None,
    status_code: int,
    response_body: object,
) -> None:
    """
    Store a successful response.

    Only successes are stored. Caching a rate-limit or server error would
    serve the failure back for a day, turning a transient fault into a
    persistent one and defeating the retry layer built to absorb it.
    """
    if status_code != 200:
        return

    CACHE_DIR.mkdir(exist_ok=True)
    path = CACHE_DIR / f"{_key(method, url, params, body)}.json"

    entry = {
        "stored_at": time.time(),
        # Recorded for a human reading the cache directory. Not used as the
        # lookup key, which is the digest above.
        "url": url,
        "response": response_body,
    }

    try:
        path.write_text(json.dumps(entry, indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError as exc:
        # A failed write costs a repeated request, nothing more. The run
        # continues rather than failing over a cache miss.
        logger.warning(
            "Could not write cache entry for %s: %s", _describe(url, params), exc
        )