"""
Tests for the review checkpoints.

The checkpoints are where the researcher's authority over scope and evidence
is exercised, so a fault here does not crash a run: it silently proceeds on a
decision the researcher did not make. That is the failure these tests exist
to prevent.

Input is supplied by replacing the built-in input function rather than by
typing. Each test provides a queue of answers, which also allows the
re-asking behaviour to be tested: a prompt that rejects an answer consumes
another, and a prompt that accepts it does not.
"""

import builtins

import pytest

from src import interface
from src.models import Assessment, Decision, Paper, SubQuestion


@pytest.fixture
def answers(monkeypatch):
    """
    Queue answers for successive prompts.

    Returns the queue so a test can assert it was drained: an answer left
    unconsumed means a prompt that should have been asked was not.
    """
    queue: list[str] = []

    def fake_input(prompt: str = "") -> str:
        if not queue:
            raise AssertionError(f"Unexpected prompt with no answer queued: {prompt!r}")
        return queue.pop(0)

    monkeypatch.setattr(builtins, "input", fake_input)
    return queue


def _sub_question(id: int = 1) -> SubQuestion:
    return SubQuestion(id=id, text="An aspect?", search_query="keywords")


def _paper(title: str) -> Paper:
    return Paper(title=title, doi=f"10.1/{title.lower()}", abstract="An abstract.")


def _assessment(title: str, score: float, sub_question_id: int = 1) -> Assessment:
    return Assessment(
        paper_title=title,
        sub_question_id=sub_question_id,
        relevance_score=score,
        reason="r",
        selected=True,
    )


def test_approving_sub_questions_returns_no_feedback(answers):
    """
    Approval carries no reason, because nothing is being asked of the Planning
    Agent. Returning feedback here would send a revision prompt on approval.
    """
    answers.append("approve")

    decision, feedback = interface.review_sub_questions([_sub_question()])

    assert decision is Decision.APPROVE
    assert feedback is None


def test_an_unrecognised_answer_is_asked_again(answers):
    """
    By this checkpoint the run has already spent model calls. A mistyped
    answer is not a reason to discard a plan the researcher has not rejected.
    """
    answers.extend(["maybe", "approve"])

    decision, _ = interface.review_sub_questions([_sub_question()])

    assert decision is Decision.APPROVE
    assert answers == []


def test_a_revision_requires_a_reason(answers):
    """
    An empty reason would send the agent to regenerate with nothing to work
    from, producing a different decomposition by chance rather than by
    correction.
    """
    answers.extend(["revise", "", "   ", "narrow question 3"])

    decision, feedback = interface.review_sub_questions([_sub_question()])

    assert decision is Decision.REVISE
    assert feedback == "narrow question 3"
    assert answers == []


def test_evidence_approval_returns_every_selected_title(answers):
    """
    Approval keeps what the agent proposed, so the titles returned are the
    selection unchanged.
    """
    answers.append("approve")
    papers = [_paper("A"), _paper("B")]
    assessments = [_assessment("A", 0.9), _assessment("B", 0.7)]

    decision, kept, feedback = interface.review_evidence(assessments, papers)

    assert decision is Decision.APPROVE
    assert sorted(kept) == ["A", "B"]
    assert feedback is None


def test_refinement_removes_the_numbered_rows(answers):
    """
    Rows are numbered by score, strongest first, so row 1 is the highest
    scoring paper. Removing by row number is what the researcher sees; the
    result is expressed as titles so the caller does not reinterpret an
    instruction.
    """
    answers.extend(["refine", "2"])
    papers = [_paper("A"), _paper("B")]
    assessments = [_assessment("A", 0.9), _assessment("B", 0.7)]

    decision, kept, _ = interface.review_evidence(assessments, papers)

    assert decision is Decision.REFINE
    assert kept == ["A"]


def test_an_out_of_range_row_number_is_asked_again(answers):
    """
    Silently ignoring an unrecognised entry would keep a paper the researcher
    meant to remove, and the mistake would not be visible in the output.
    """
    answers.extend(["refine", "99", "abc", "1"])
    papers = [_paper("A"), _paper("B")]
    assessments = [_assessment("A", 0.9), _assessment("B", 0.7)]

    _, kept, _ = interface.review_evidence(assessments, papers)

    assert kept == ["B"]
    assert answers == []


def test_refining_nothing_keeps_the_whole_selection(answers):
    """
    A researcher who reconsiders mid-refinement can withdraw without having to
    restart the run.
    """
    answers.extend(["refine", "none"])
    papers = [_paper("A"), _paper("B")]
    assessments = [_assessment("A", 0.9), _assessment("B", 0.7)]

    _, kept, _ = interface.review_evidence(assessments, papers)

    assert sorted(kept) == ["A", "B"]


def test_scope_rejection_returns_no_titles_and_a_reason(answers):
    """
    A scope rejection is a judgement that the question was wrong, so the
    evidence gathered under it is not a partial answer to salvage. The reason
    is required because the Planning Agent needs it to revise rather than
    merely regenerate.
    """
    answers.extend(["reject", "too narrow"])
    papers = [_paper("A")]

    decision, kept, feedback = interface.review_evidence([_assessment("A", 0.9)], papers)

    assert decision is Decision.REJECT_SCOPE
    assert kept == []
    assert feedback == "too narrow"


def test_refining_an_empty_selection_becomes_a_scope_rejection(answers):
    """
    There is nothing to refine, and approving an empty set would produce a
    brief containing no evidence. Reinterpreted explicitly rather than
    silently, and the reason is still required.
    """
    answers.extend(["refine", "the question is wrong"])

    decision, kept, feedback = interface.review_evidence([], [_paper("A")])

    assert decision is Decision.REJECT_SCOPE
    assert kept == []
    assert feedback == "the question is wrong"


def test_a_paper_selected_for_several_aspects_appears_once(answers):
    """
    A paper is scored once per sub-question, so one relevant to two aspects
    appears twice in the assessments. The researcher is deciding whether to
    keep a paper, not a pairing, so showing the rows unreduced would ask for
    the same paper to be deselected twice.
    """
    answers.extend(["refine", "1"])
    papers = [_paper("A")]
    assessments = [
        _assessment("A", 0.9, sub_question_id=1),
        _assessment("A", 0.7, sub_question_id=2),
    ]

    _, kept, _ = interface.review_evidence(assessments, papers)

    assert kept == []