"""
Shared HTTP infrastructure. Throttling and retry live here rather than in any
agent: both are deterministic concerns, which the design proposal assigns to
the orchestrator's remit rather than to an agent's reasoning.
"""

import json
import logging
import time

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src import cache

# __name__ resolves to this module's import path, so records from this file are
# labelled src.clients. Naming loggers per module means a log line identifies
# where it came from without the message having to say so.
logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Paces outgoing requests to stay within a limit stated in advance.

    Proactive by design: it acts before a failure occurs. Recovery from
    failures that happen regardless is a separate mechanism, because pacing
    conditional on failure would only slow down after a known limit had
    already been exceeded.
    """

    def __init__(self, min_interval_seconds: float):
        self.min_interval = min_interval_seconds
        # Zero rather than the current time, so the first request is not
        # delayed: there is no previous call for it to be spaced from.
        self._last_call = 0.0

    def wait(self) -> None:
        # monotonic() rather than time(), because the wall clock can jump
        # backwards when the system synchronises it, which would make an
        # interval appear longer than it was and release a request early.
        elapsed = time.monotonic() - self._last_call
        remaining = self.min_interval - elapsed
        if remaining > 0:
            time.sleep(remaining)
        # Stamped after sleeping, so it records when the request is issued
        # rather than when it was asked for.
        self._last_call = time.monotonic()


# One instance per service, not one shared instance. The one-per-second limit
# was issued for Semantic Scholar and covers its endpoints only, so a shared
# limiter would delay Crossref calls for a limit that does not apply to them.
semantic_scholar_limiter = RateLimiter(1.0)

# Crossref publishes no fixed limit for anonymous use. One per second is a
# self-imposed pace, chosen to match the stricter of the two services rather
# than to satisfy a stated requirement.
crossref_limiter = RateLimiter(1.0)

# Four seconds corresponds to fifteen requests per minute, the allowance shown
# for this model on the project's own rate-limit dashboard. Set from that
# figure rather than from documentation: an earlier interval of six seconds was
# derived from an assumed limit of ten per minute, which the model in use at
# the time did not have, so the limiter permitted twice the real rate and
# contributed to rate-limit failures it existed to prevent.
gemini_limiter = RateLimiter(4.0)


class QuotaExhaustedError(Exception):
    """
    Raised when a 429 reports an exhausted allowance rather than too fast a
    rate. The two arrive with the same status code and mean different things:
    a rate limit is relieved by waiting seconds, whereas a daily quota is
    relieved only when it resets.

    Not retryable, and that distinction is not cosmetic. Retrying a quota
    failure fails every attempt and spends each one against the very
    allowance that is exhausted, so the policy meant to recover from
    congestion instead deepens the exhaustion. Observed in development: a
    project limited to 20 requests per day recorded 21.
    """


class RetryableHTTPError(Exception):
    """
    Raised for HTTP failures that may succeed on a later attempt: 429, 500,
    502, 503, 504. A distinct exception type exists so the retry policy can
    select on it. A 403 or 404 raises nothing retryable, because repeating a
    refused or absent request cannot change its outcome.

    Carries retry_after when the server supplied that header, so the wait
    policy can defer to the service's own instruction instead of guessing.
    """

    def __init__(self, message: str, retry_after: float | None = None):
        super().__init__(message)
        self.retry_after = retry_after


# The exponential curve is the fallback, used whenever the server gives no
# instruction of its own.
_exponential_wait = wait_exponential(multiplier=1, min=1, max=30)


def _wait_policy(retry_state) -> float:
    """
    Prefer the server's Retry-After over the exponential curve.

    A 429 is evidence that the pacing assumption was wrong, and the service is
    better placed than this client to say how long to wait. Deferring to it is
    not a departure from the proactive/reactive separation: it is the reactive
    layer reading the authoritative signal rather than inventing one. Capped so
    an unexpectedly large value cannot stall a run indefinitely.
    """
    hinted = getattr(retry_state.outcome.exception(), "retry_after", None)
    if hinted is not None:
        return min(hinted, 60.0)
    return _exponential_wait(retry_state)


def _log_retry(retry_state) -> None:
    """
    Log each failed attempt before the backoff wait.

    Without this an absorbed failure is invisible: the caller sees only a
    successful response, and the retries can be inferred only from elapsed
    time. Recording them makes the reactive layer's work observable, which is
    what the requirement for evidence of execution asks for.
    """
    logger.warning(
        "Attempt %d failed (%s), retrying in %.1fs",
        retry_state.attempt_number,
        retry_state.outcome.exception(),
        retry_state.next_action.sleep,
    )


class CachedResponse:
    """
    Stands in for a requests.Response when a cached body is returned.

    Callers already branch on status_code and call json(), so presenting a
    cached entry in that shape means the cache is invisible to them. Only
    successful responses are cached, so the status is always 200; a failure is
    never replayed.
    """

    status_code = 200

    def __init__(self, body: object):
        self._body = body

    def json(self) -> object:
        return self._body

    def raise_for_status(self) -> None:
        """Never raises: a cached entry is by definition a success."""

    @property
    def text(self) -> str:
        return json.dumps(self._body)


# Retry wraps a function that calls the limiter, so every attempt is paced.
# The reverse arrangement would let retries burst past the throttle, which is
# the behaviour that produces a 429 in the first place.
@retry(
    retry=retry_if_exception_type((RetryableHTTPError, requests.RequestException)),
    # Six rather than four: four consecutive 429s were observed under normal
    # development use, exhausting the policy and failing a sound request. The
    # ceiling is set from that observation rather than chosen for neatness.
    stop=stop_after_attempt(6),
    wait=_wait_policy,
    reraise=True,
    before_sleep=_log_retry,
)
def request(
    method: str,
    url: str,
    limiter: RateLimiter,
    use_cache: bool = True,
    **kwargs,
) -> requests.Response | CachedResponse:
    """
    Issue a paced request, retrying only failures a later attempt could resolve.

    Reactive by design: it handles failures that occur despite the pacing
    above. Semantic Scholar's own API release notes require exponential
    backoff, so this is compliance with a stated provider requirement rather
    than a defensive choice.

    Method is a parameter rather than there being one decorated function per
    verb, so that a change to the retry policy cannot apply to some callers and
    not others.

    A cache hit returns before the limiter is consulted. Pacing exists to stay
    within a limit on requests actually sent, and a request that is not sent
    consumes nothing, so waiting first would slow a run for no purpose.
    """
    if use_cache:
        cached = cache.read(method, url, kwargs.get("params"), kwargs.get("json"))
        if cached is not None:
            return CachedResponse(cached)

    limiter.wait()

    # 30 seconds rather than 10: a successful response was observed taking 8
    # seconds, so a 10-second ceiling would abandon requests the service was
    # still answering. Set from measurement rather than convention. A ceiling
    # is still required, since requests applies none by default and a stalled
    # connection would otherwise hang indefinitely.
    response = requests.request(method, url, timeout=30, **kwargs)

    if response.status_code in (429, 500, 502, 503, 504):
        # A quota failure is separated from a rate-limit failure before the
        # retry policy sees it. Both are 429s, so the body is what
        # distinguishes them: providers name the exhausted quota in it.
        # Matching on the body is fragile, and deliberately so rather than
        # silently: a wording change makes a quota failure look retryable
        # again, which is the milder of the two errors available here.
        body = response.text.lower()
        if response.status_code == 429 and (
            "quota" in body or "resource_exhausted" in body
        ):
            raise QuotaExhaustedError(f"{response.status_code} - {response.text}")

        # Retry-After may arrive as seconds or as an HTTP date. Only the
        # numeric form is read: the date form is rare here, and parsing it
        # wrongly would produce a worse wait than the exponential fallback.
        header = response.headers.get("Retry-After")
        retry_after = float(header) if header and header.isdigit() else None
        raise RetryableHTTPError(
            f"{response.status_code} - {response.text}", retry_after=retry_after
        )

    if use_cache:
        # Stored after the retryable and quota checks above, so only a
        # response that reached this point is a candidate. cache.write
        # declines anything that is not a 200.
        try:
            cache.write(
                method,
                url,
                kwargs.get("params"),
                kwargs.get("json"),
                response.status_code,
                response.json(),
            )
        except ValueError:
            # A 200 whose body is not JSON is not cacheable, and is not an
            # error here: the caller decides what to make of it.
            pass

    # Every other outcome, success or terminal failure, is returned as-is for
    # the caller to interpret. Raising here would remove the caller's ability
    # to distinguish a 403 from a 200, which stage 3 depends on.
    return response


def get(url: str, limiter: RateLimiter, **kwargs) -> requests.Response | CachedResponse:
    """Paced, retrying, cacheable GET."""
    return request("GET", url, limiter, **kwargs)


def post(url: str, limiter: RateLimiter, **kwargs) -> requests.Response | CachedResponse:
    """
    Paced, retrying POST.

    Retrying a POST is safe here only because the endpoints this system posts
    to are generative rather than state-changing: a repeated request produces
    another answer, not a duplicate record. That would not hold for an
    endpoint that creates something.
    """
    return request("POST", url, limiter, **kwargs)