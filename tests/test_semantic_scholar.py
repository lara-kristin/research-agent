"""
Tests for the Semantic Scholar adapter.

Every test here reads a recorded response rather than calling the API, so the
suite is deterministic and runs while the service is rate limiting. The
recorded file is a real response, not a handwritten sample: assumptions about
this API's shape proved wrong twice during development, so the fixture tests
reality rather than expectation.
"""

import json
from pathlib import Path

import pytest

from src.models import SearchResponse
from src.semantic_scholar import _to_paper

FIXTURE = Path(__file__).parent / "fixtures" / "semantic_scholar_search.json"


@pytest.fixture
def recorded_response() -> SearchResponse:
    """The recorded live response, validated as the code would validate it."""
    return SearchResponse.model_validate(json.loads(FIXTURE.read_text(encoding="utf-8")))


def test_recorded_response_validates(recorded_response):
    """
    A live response must satisfy the model. If the API changes shape, this
    fails here rather than mid-run against real data.
    """
    assert recorded_response.total > 0
    assert len(recorded_response.data) > 0


def test_doi_is_extracted_from_nested_external_ids(recorded_response):
    """
    The DOI is nested inside externalIds rather than returned at the top
    level. Reading it from the wrong place would silently produce papers with
    no DOI, which would then be retained by deduplication and reported as
    unverifiable.
    """
    papers = [_to_paper(record) for record in recorded_response.data]
    assert any(paper.doi is not None for paper in papers)


def test_authors_are_reduced_to_names():
    """
    Authors arrive as objects carrying an id and a name. Storing the objects
    would leak this API's shape into the domain model and break the OpenAlex
    fallback named in the design proposal.
    """
    record = {
        "title": "Test",
        "authors": [{"authorId": "1", "name": "A. Author"}],
        "externalIds": {"DOI": "10.1/x"},
    }
    assert _to_paper(record).authors == ["A. Author"]


def test_record_without_external_ids_yields_no_doi():
    """
    Some records carry no externalIds at all, observed in a five-record live
    search. The absence must produce a paper with no DOI rather than an error,
    because such a record is retained rather than discarded.
    """
    assert _to_paper({"title": "Test"}).doi is None