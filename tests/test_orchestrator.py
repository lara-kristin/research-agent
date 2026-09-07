"""
Tests for the orchestrator's deterministic checks.

These need no network at all: deduplication and Markdown rendering operate on
Paper objects, which is a consequence of keeping the domain models separate
from any API's response shape.
"""

from src.models import Paper
from src.orchestrator import _paper_to_markdown, deduplicate_by_doi


def test_duplicate_dois_are_removed_regardless_of_case():
    """
    The same paper can arrive under two sub-questions with differently
    capitalised DOIs. Deduplication depends on Paper normalising the DOI on
    construction, so this test also protects that dependency.
    """
    papers = [Paper(title="A", doi="10.1/X"), Paper(title="B", doi="10.1/x")]
    assert [p.title for p in deduplicate_by_doi(papers)] == ["A"]


def test_first_occurrence_is_kept():
    """
    Keeping the earlier record makes a run's output reproducible. Keeping the
    later one would make output depend on retrieval order, which varies.
    """
    papers = [Paper(title="First", doi="10.1/x"), Paper(title="Second", doi="10.1/x")]
    assert deduplicate_by_doi(papers)[0].title == "First"


def test_records_without_a_doi_are_all_retained():
    """
    Records with no DOI cannot be compared on the field this deduplicates by.
    Retaining them permits a duplicate, which is visible in the output;
    comparing titles instead would risk discarding a distinct paper, which is
    not. The diagram specifies deduplication by DOI.
    """
    papers = [Paper(title="A"), Paper(title="B"), Paper(title="C")]
    assert len(deduplicate_by_doi(papers)) == 3


def test_missing_abstract_is_stated_not_omitted():
    """
    Semantic Scholar does not return abstracts for every publisher, and a
    record with no abstract has no relevance signal for the Evaluation Agent
    to score. A blank space would be indistinguishable from a rendering fault.
    """
    rendered = _paper_to_markdown(Paper(title="A", doi="10.1/x"))
    assert "No abstract available" in rendered


def test_verification_status_appears_on_verified_records_too():
    """
    Status is stated on every record, not only the flagged ones. A reader who
    sees nothing cannot tell whether a paper was checked and passed or was
    never checked at all.
    """
    verified = Paper(title="A", doi="10.1/x", doi_verified=True)
    assert "verified against Crossref" in _paper_to_markdown(verified)