"""
Tests for the domain models.

These run without network access, as the design proposal requires: a test
suite that depends on a live API is neither deterministic nor available when
the service is rate limiting, which this API does routinely.
"""

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