"""
Semantic Scholar Academic Graph API client.

Adapts one external source into the domain models. Everything specific to this
API lives here: its field names, its nesting, its conventions. A change of
source, such as the OpenAlex fallback named in the design proposal, is
therefore confined to a module of this kind rather than spreading through the
system.
"""

import logging
import os

from dotenv import load_dotenv

from src.clients import get, semantic_scholar_limiter
from src.models import Paper, SearchResponse

logger = logging.getLogger(__name__)

SEARCH_URL = "https://api.semanticscholar.org/graph/v1/paper/search"

# Requested at module level so a missing key fails once, on import, rather than
# part-way through a run that has already consumed quota.
load_dotenv()
API_KEY = os.getenv("SEMANTIC_SCHOLAR_API_KEY")


class MissingAPIKeyError(Exception):
    """
    Raised when no API key is configured.

    requests treats a header whose value is None as an instruction to omit it,
    so an absent key would otherwise send an unauthenticated request. That
    falls under the shared unauthenticated pool and is throttled for reasons
    unrelated to this client, producing a 429 indistinguishable from a genuine
    rate limit. Observed during development: three unauthenticated requests
    returned 429 where an invalid key returns 403.
    """


def _to_paper(record: dict) -> Paper:
    """
    Convert one API record into a Paper.

    Separated from the search itself so it can be tested against a recorded
    response without network access, as the design proposal requires of the
    unit tests.
    """
    # The DOI is nested inside externalIds rather than returned at the top
    # level, confirmed by inspecting a live response. Absent from some records,
    # which is why Paper.doi is optional and doi_verified defaults to False.
    external_ids = record.get("externalIds") or {}

    return Paper(
        title=record["title"],
        year=record.get("year"),
        doi=external_ids.get("DOI"),
        # Authors arrive as objects carrying an id and a name, so the names are
        # extracted here rather than storing a shape specific to this API.
        authors=[a["name"] for a in record.get("authors") or []],
        abstract=record.get("abstract"),
    )


def search(query: str, limit: int = 10, fields: str | None = None) -> list[Paper]:
    """
    Search Semantic Scholar and return the results as Paper objects.

    Returns an empty list when nothing matches, because a search with no
    results is a successful request rather than a failure. The distinction
    matters to the Retrieval Agent: an empty result set justifies query
    reformulation, whereas a refused request justifies a retry. Failures raise
    instead, so the caller can tell the two apart and decide.
    """
    if not API_KEY:
        raise MissingAPIKeyError(
            "SEMANTIC_SCHOLAR_API_KEY not found. Check .env exists and the name matches."
        )

    # Abstracts and authors are requested in the same call as titles, since
    # retrieving them afterwards for relevance scoring would cost one request
    # per paper under a limit shared across all Semantic Scholar endpoints.
    if fields is None:
        fields = "title,year,externalIds,authors,abstract"

    logger.info("Searching Semantic Scholar: query=%r limit=%d", query, limit)

    response = get(
        SEARCH_URL,
        semantic_scholar_limiter,
        params={"query": query, "limit": limit, "fields": fields},
        headers={"x-api-key": API_KEY},
    )

    # Retryable statuses are raised by the client before reaching here. What
    # remains is either success or a terminal refusal such as 403, which is
    # reported with the server's own message rather than retried.
    response.raise_for_status()

    # Validation replaces the shape checks written by hand at stage 1: total is
    # required, so a body without it is rejected, and data defaults to an empty
    # list because the API omits it entirely on zero matches.
    validated = SearchResponse.model_validate(response.json())

    logger.info("Retrieved %d of %d matching records", len(validated.data), validated.total)

    return [_to_paper(record) for record in validated.data]