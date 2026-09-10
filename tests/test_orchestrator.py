"""
Tests for the orchestrator's deterministic checks.

Deduplication and Markdown rendering need no network at all: they operate on
Paper objects, which is a consequence of keeping the domain models separate
from any API's response shape.

The retrieval tests replace both the retrieval and planning calls rather than
making them. Note what is patched: this module imports those functions into
its own namespace, so the names to replace are orchestrator.retrieve_evidence
and orchestrator.reformulate_query. Patching them where they are defined would
leave the orchestrator's references pointing at the real functions, and the
tests would issue live requests.
"""

import pytest

from src import orchestrator
from src.models import Paper, SubQuestion
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


def _approved(id: int, query: str = "some keywords") -> SubQuestion:
    """A sub-question in the state retrieval requires: reviewed and approved."""
    return SubQuestion(id=id, text="An aspect?", search_query=query, approved=True)


def _papers(count: int, with_abstract: bool = True) -> list[Paper]:
    """
    Build a result set of a given size.

    with_abstract matters because the threshold counts usable records: a paper
    without an abstract cannot be relevance-scored, so it does not count
    towards sufficiency even though it is retained.
    """
    return [
        Paper(
            title=f"Paper {i}",
            doi=f"10.1/{i}-{count}-{with_abstract}",
            abstract="An abstract." if with_abstract else None,
        )
        for i in range(count)
    ]


def test_unapproved_sub_questions_are_refused():
    """
    The first human checkpoint is enforced by state, not by calling order.
    Without this check, retrieval would search whatever list it was handed and
    the checkpoint would be a convention rather than a control.
    """
    unapproved = SubQuestion(id=1, text="An aspect?", search_query="keywords")

    with pytest.raises(ValueError, match="approved"):
        orchestrator.retrieve_for_plan([unapproved])


def test_records_without_abstracts_do_not_meet_the_threshold(monkeypatch):
    """
    Three records of which none is assessable is not sufficient evidence.
    Diagram 3 branches on usable records, so counting all of them would
    overstate what was found and diverge from the design. Reformulation being
    requested is what shows the threshold was judged unmet.
    """
    monkeypatch.setattr(
        orchestrator,
        "retrieve_evidence",
        lambda sq, limit=5, use_cache=True: _papers(3, with_abstract=False),
    )

    reformulated = []

    def fake_reformulate(sub_question, use_cache=True):
        reformulated.append(sub_question.id)
        return sub_question.model_copy(update={"retried_once": True})

    monkeypatch.setattr(orchestrator, "reformulate_query", fake_reformulate)

    orchestrator.retrieve_for_plan([_approved(1)])

    assert reformulated == [1]


def test_reformulation_happens_at_most_once(monkeypatch):
    """
    The one-retry limit belongs to the orchestrator, not the agent: the flag
    records that a retry happened but does not prevent another. A sub-question
    arriving already retried must not be reformulated again, however far below
    the threshold its result falls.
    """
    monkeypatch.setattr(
        orchestrator,
        "retrieve_evidence",
        lambda sq, limit=5, use_cache=True: _papers(1),
    )

    calls = []

    def fake_reformulate(sub_question, use_cache=True):
        calls.append(sub_question.id)
        return sub_question

    monkeypatch.setattr(orchestrator, "reformulate_query", fake_reformulate)

    already_retried = _approved(1).model_copy(update={"retried_once": True})
    orchestrator.retrieve_for_plan([already_retried])

    assert calls == []


def test_original_result_kept_when_reformulation_finds_no_more(monkeypatch):
    """
    A broader query can return fewer usable records. Accepting the retry
    unconditionally would discard evidence already retrieved, so the
    reformulated result is kept only when it improves on the original.
    """
    results = [_papers(2), _papers(1)]
    monkeypatch.setattr(
        orchestrator,
        "retrieve_evidence",
        lambda sq, limit=5, use_cache=True: results.pop(0),
    )
    monkeypatch.setattr(
        orchestrator,
        "reformulate_query",
        lambda sq, use_cache=True: sq.model_copy(update={"retried_once": True}),
    )

    papers = orchestrator.retrieve_for_plan([_approved(1)])

    assert len(papers) == 2