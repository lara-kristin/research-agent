"""
Tests for the shared HTTP client.

These exist because the retry policy once became silently detached from the
function it governed: a class definition inserted between the decorator and
its function left the decorator applied to the class, so every request was
issued with no retry at all. The file compiled and the whole suite passed. A
mechanism whose absence resembles success needs a test that fails when it is
absent.

requests.request is replaced rather than the client's own functions, so the
retry policy, the error classification and the caching decision are all
exercised as written.
"""

import pytest

from src import cache, clients


class FakeResponse:
    """Stands in for a requests.Response, with only the members used here."""

    def __init__(self, status_code: int, body: dict | None = None, text: str = ""):
        self.status_code = status_code
        self._body = body or {}
        self.text = text or "{}"
        self.headers: dict[str, str] = {}

    def json(self) -> dict:
        return self._body


@pytest.fixture(autouse=True)
def no_pacing_or_caching(monkeypatch, tmp_path):
    """
    Remove the behaviours that would make these tests slow or unreliable.

    Pacing and backoff would otherwise add real seconds per attempt. An
    earlier version of this fixture replaced the module-level wait policy,
    which had no effect: tenacity captures the policy when the decorator runs
    at import time, so the module attribute is no longer what governs the
    wait. The suite still passed, but took thirty-two seconds rather than a
    fraction of one. The sleep is therefore replaced on the retry object the
    decorator attached to the function, which the per-call copy inherits.

    The cache is redirected to a temporary directory rather than switched off,
    so a test run can neither read the working cache nor write into it.
    """
    monkeypatch.setattr(clients.RateLimiter, "wait", lambda self: None)
    monkeypatch.setattr(clients.request.retry, "sleep", lambda seconds: None)
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path / "cache")


def test_a_retryable_failure_is_retried_until_it_succeeds(monkeypatch):
    """
    The test the detached decorator would have failed. A single 503 followed
    by a success must produce a success, which is only possible if a second
    attempt is made.
    """
    responses = [FakeResponse(503), FakeResponse(200, {"ok": True})]
    attempts = []

    def fake_request(method, url, **kwargs):
        attempts.append(method)
        return responses.pop(0)

    monkeypatch.setattr(clients.requests, "request", fake_request)

    response = clients.get("https://example.test/thing", clients.crossref_limiter)

    assert response.status_code == 200
    assert len(attempts) == 2


def test_retrying_stops_after_the_attempt_limit(monkeypatch):
    """
    A policy that never gives up would hang a run against a service that is
    down. Six attempts, then the original failure is surfaced rather than
    tenacity's own wrapper, so the caller learns what actually failed.
    """
    attempts = []

    def always_503(method, url, **kwargs):
        attempts.append(method)
        return FakeResponse(503)

    monkeypatch.setattr(clients.requests, "request", always_503)

    with pytest.raises(clients.RetryableHTTPError, match="503"):
        clients.get("https://example.test/thing", clients.crossref_limiter)

    assert len(attempts) == 6


def test_a_terminal_failure_is_not_retried(monkeypatch):
    """
    Repeating a refused request cannot change its outcome. A 403 is returned
    for the caller to interpret rather than retried, and the caller's ability
    to tell a 403 from a 200 is what the retrieval stage depends on.
    """
    attempts = []

    def forbidden(method, url, **kwargs):
        attempts.append(method)
        return FakeResponse(403, text='{"message":"Forbidden"}')

    monkeypatch.setattr(clients.requests, "request", forbidden)

    response = clients.get("https://example.test/thing", clients.crossref_limiter)

    assert response.status_code == 403
    assert len(attempts) == 1


def test_a_quota_failure_is_not_retried(monkeypatch):
    """
    A quota 429 and a rate-limit 429 share a status code and mean different
    things. Retrying an exhausted allowance fails every attempt and spends
    each one against the very limit that is exhausted, which is how a project
    limited to twenty requests a day recorded twenty-one.
    """
    attempts = []

    def quota_exceeded(method, url, **kwargs):
        attempts.append(method)
        return FakeResponse(429, text='{"error":{"status":"RESOURCE_EXHAUSTED"}}')

    monkeypatch.setattr(clients.requests, "request", quota_exceeded)

    with pytest.raises(clients.QuotaExhaustedError):
        clients.get("https://example.test/thing", clients.crossref_limiter)

    assert len(attempts) == 1


def test_a_rate_limit_without_quota_wording_is_retried(monkeypatch):
    """
    The counterpart to the test above, and the reason the distinction is worth
    making rather than treating every 429 as terminal. Semantic Scholar's
    rate-limit response names no quota, and recovering from it is what allows
    a run to continue through ordinary congestion.
    """
    responses = [
        FakeResponse(429, text='{"message":"Too Many Requests","code":"429"}'),
        FakeResponse(200, {"ok": True}),
    ]
    attempts = []

    def rate_limited_then_ok(method, url, **kwargs):
        attempts.append(method)
        return responses.pop(0)

    monkeypatch.setattr(clients.requests, "request", rate_limited_then_ok)

    response = clients.get("https://example.test/thing", clients.crossref_limiter)

    assert response.status_code == 200
    assert len(attempts) == 2


def test_a_cached_response_is_returned_without_a_request(monkeypatch):
    """
    A cache hit must not reach the network. Asserting that no request was made
    is the point: a cache that fetched anyway would still return the right
    answer while conserving nothing, which is the only thing it exists to do.
    """
    attempts = []

    def count_and_succeed(method, url, **kwargs):
        attempts.append(method)
        return FakeResponse(200, {"value": 1})

    monkeypatch.setattr(clients.requests, "request", count_and_succeed)

    url = "https://example.test/cacheable"
    first = clients.get(url, clients.crossref_limiter, params={"query": "x"})
    second = clients.get(url, clients.crossref_limiter, params={"query": "x"})

    assert len(attempts) == 1
    assert first.json() == second.json()


def test_a_bypassed_request_still_refreshes_the_cache(monkeypatch):
    """
    use_cache governs reading, not writing. Bypassing the cache is a request
    for current data, so it would be perverse for it to leave an older entry
    in place for the next cached run to serve.
    """
    bodies = [{"value": 1}, {"value": 2}]

    def changing(method, url, **kwargs):
        return FakeResponse(200, bodies.pop(0))

    monkeypatch.setattr(clients.requests, "request", changing)

    url = "https://example.test/refresh"
    clients.get(url, clients.crossref_limiter, params={"query": "x"})
    clients.get(url, clients.crossref_limiter, params={"query": "x"}, use_cache=False)

    # Reads from the cache now, and must see what the bypassed request stored.
    third = clients.get(url, clients.crossref_limiter, params={"query": "x"})
    assert third.json() == {"value": 2}


def test_a_failed_response_is_not_cached(monkeypatch):
    """
    Storing a failure would serve it back for the life of the entry, turning a
    transient fault into a persistent one and defeating the retry layer built
    to absorb it.
    """
    attempts = []

    def forbidden(method, url, **kwargs):
        attempts.append(method)
        return FakeResponse(403, text='{"message":"Forbidden"}')

    monkeypatch.setattr(clients.requests, "request", forbidden)

    url = "https://example.test/forbidden"
    clients.get(url, clients.crossref_limiter, params={"query": "x"})
    clients.get(url, clients.crossref_limiter, params={"query": "x"})

    assert len(attempts) == 2