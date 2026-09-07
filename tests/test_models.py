"""
Tests for the domain models.

These run without network access, as the design proposal requires: a test
suite that depends on a live API is neither deterministic nor available when
the service is rate limiting, which this API does routinely.

The rejection tests below cover conditions the live service does not produce.
A malformed body cannot be provoked on demand, so it is evidenced here rather
than by a screenshot of a contrived run.
"""

import pytest
from pydantic import ValidationError

from src.models import Paper, SearchResponse


def test_doi_is_lowercased_on_construction():
    """
    DOIs are case-insensitive, so the same paper can arrive with different
    capitalisation from different sources. Deduplication compares DOIs
    directly and would miss such a duplicate if normalisation did not happen
    here.
    """
    paper = Paper(title="Test", doi="10.1234/ABC")
    assert paper.doi == "10.1234/abc"


def test_paper_is_unverified_by_default():
    """
    A paper must start unverified, so that verification is something Crossref
    grants rather than something assumed and then withdrawn.
    """
    paper = Paper(title="Test")
    assert paper.doi_verified is False
    assert paper.verification_note is None


def test_search_response_defaults_data_to_empty_list():
    """
    The API omits data entirely when nothing matches, established by
    inspecting a live response. Defaulting it here is what allows a zero
    result to be read as an empty search rather than a malformed body.
    """
    response = SearchResponse(total=0)
    assert response.data == []


def test_response_without_total_is_rejected():
    """
    A body lacking total is not a search result. Reading it as zero results
    would have the Retrieval Agent reformulate a sound query in response to a
    malformed response, which is the conflation the stage 1 remediation
    addressed.
    """
    with pytest.raises(ValidationError):
        SearchResponse(data=[])


def test_null_data_is_rejected():
    """
    A data field set to null is valid JSON and would pass a check for the
    key's presence. Declaring the type rejects it, which is why the
    hand-written isinstance check at stage 1 was retired rather than kept.
    """
    with pytest.raises(ValidationError):
        SearchResponse(total=0, data=None)


def test_paper_without_a_title_is_rejected():
    """
    Title is the one field with no default. A record with no title cannot be
    rendered for the researcher or scored for relevance, so it is refused at
    construction rather than carried through the pipeline as an empty string.
    """
    with pytest.raises(ValidationError):
        Paper(doi="10.1/x")