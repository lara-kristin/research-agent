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


def test_missing_summary_is_stated_not_omitted():
    """
    A paper can reach the brief without a summary if the model returned none
    for it. Stating the absence keeps it visible: a blank space would be
    indistinguishable from a rendering fault, and a placeholder summary would
    read as though the paper had been summarised.

    This replaces an earlier test asserting the same of a missing abstract.
    Abstracts are no longer reproduced in the brief, and a paper without one
    cannot be scored, so it can never reach the selected set.
    """
    rendered = _paper_to_markdown(Paper(title="A", doi="10.1/x"))
    assert "No summary was produced" in rendered


def test_summary_is_labelled_as_generated():
    """
    The brief mixes text the system produced with metadata it retrieved. A
    summary presented without attribution leaves a reader unable to tell which
    is which, in a document whose purpose is to distinguish them.
    """
    rendered = _paper_to_markdown(Paper(title="A", doi="10.1/x"), summary="A summary.")
    assert "generated from the abstract" in rendered


def test_sub_question_attribution_is_rendered():
    """
    Decomposing the question is what made per-aspect coverage knowable. A
    brief omitting which aspects a paper addresses discards the distinction
    the decomposition created.
    """
    rendered = _paper_to_markdown(
        Paper(title="A", doi="10.1/x"), summary="S", score=0.8, sub_question_ids=[1, 3]
    )
    assert "Addresses sub-question(s):** 1, 3" in rendered
    assert "[0.80]" in rendered


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


def test_a_worse_reformulation_leaves_the_original_query_recorded(monkeypatch):
    """
    The query recorded on a sub-question must be the one that produced the
    evidence kept beneath it.

    An earlier version wrote the reformulated sub-question back
    unconditionally while keeping the original papers when the retry did
    worse. The brief would then list a query that did not produce the evidence
    under it, and the limitation derived from the flag asserted that the
    evidence came from the reformulated query, which was false.
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
        lambda sq, use_cache=True: sq.model_copy(
            update={"search_query": "broader", "retried_once": True}
        ),
    )

    sub_questions = [_approved(1, query="original")]
    papers = orchestrator.retrieve_for_plan(sub_questions)

    assert len(papers) == 2
    assert sub_questions[0].search_query == "original"
    # The retry still happened, so the limit must still hold against it.
    assert sub_questions[0].retried_once is True


def test_a_better_reformulation_records_the_reformulated_query(monkeypatch):
    """
    The counterpart: when the retry does better its results are kept, so its
    query is what produced them and is what the brief must show.
    """
    results = [_papers(1), _papers(3)]
    monkeypatch.setattr(
        orchestrator,
        "retrieve_evidence",
        lambda sq, limit=5, use_cache=True: results.pop(0),
    )
    monkeypatch.setattr(
        orchestrator,
        "reformulate_query",
        lambda sq, use_cache=True: sq.model_copy(
            update={"search_query": "broader", "retried_once": True}
        ),
    )

    sub_questions = [_approved(1, query="original")]
    papers = orchestrator.retrieve_for_plan(sub_questions)

    assert len(papers) == 3
    assert sub_questions[0].search_query == "broader"
    assert sub_questions[0].retried_once is True