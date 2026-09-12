"""
Tests for the Evaluation Agent.

The LLM call is replaced rather than made, so each condition can be exercised
deliberately. Several cannot be produced on demand from a live model: a
response naming a paper that was never retrieved, or a score outside the
permitted range, are failures the system must handle but cannot provoke.

What is patched is evaluation_agent.generate_json, not llm.generate_json: this
module imports the function into its own namespace, so replacing it where it
is defined would leave the reference pointing at the real one.
"""

import pytest

from src import evaluation_agent
from src.models import Paper, SubQuestion


def _paper(title: str, abstract: str | None = "An abstract.") -> Paper:
    return Paper(title=title, doi=f"10.1/{title.lower()}", abstract=abstract)


def _sub_question(id: int) -> SubQuestion:
    return SubQuestion(id=id, text="An aspect?", search_query="keywords", approved=True)


def _returns(items):
    """Build a stand-in for generate_json that returns a fixed response."""

    def fake(prompt, schema, purpose="request", use_cache=True):
        return items

    return fake


def test_scores_at_or_above_the_threshold_are_selected(monkeypatch):
    """
    The threshold is applied by the agent, not requested of the model, so the
    rule is one auditable line rather than a property of each response. The
    boundary is inclusive: a paper must be more relevant than not, and exactly
    at the threshold qualifies.
    """
    monkeypatch.setattr(
        evaluation_agent,
        "generate_json",
        _returns(
            [
                {"paper_title": "A", "sub_question_id": 1, "relevance_score": 0.6, "reason": "r"},
                {"paper_title": "B", "sub_question_id": 1, "relevance_score": 0.59, "reason": "r"},
            ]
        ),
    )

    results = evaluation_agent.evaluate_evidence(
        [_paper("A"), _paper("B")], [_sub_question(1)]
    )

    selected = {a.paper_title: a.selected for a in results}
    assert selected == {"A": True, "B": False}


def test_a_title_that_was_not_retrieved_is_discarded(monkeypatch):
    """
    An assessment naming a paper the system never retrieved would place a
    fabricated record in the brief. This is the citation-fabrication failure
    the design proposal guards against, arising inside the system rather than
    from the source.
    """
    monkeypatch.setattr(
        evaluation_agent,
        "generate_json",
        _returns(
            [
                {"paper_title": "A", "sub_question_id": 1, "relevance_score": 0.9, "reason": "r"},
                {"paper_title": "Invented", "sub_question_id": 1, "relevance_score": 1.0, "reason": "r"},
            ]
        ),
    )

    results = evaluation_agent.evaluate_evidence([_paper("A")], [_sub_question(1)])

    assert [a.paper_title for a in results] == ["A"]


def test_a_score_outside_the_range_is_discarded_without_losing_the_rest(monkeypatch):
    """
    The provider's schema constrains shape but cannot bound a number, so a
    score above 1.0 can arrive. Validating each assessment separately means
    one unusable entry discards itself rather than the whole response.
    """
    monkeypatch.setattr(
        evaluation_agent,
        "generate_json",
        _returns(
            [
                {"paper_title": "A", "sub_question_id": 1, "relevance_score": 1.5, "reason": "r"},
                {"paper_title": "B", "sub_question_id": 1, "relevance_score": 0.8, "reason": "r"},
            ]
        ),
    )

    results = evaluation_agent.evaluate_evidence(
        [_paper("A"), _paper("B")], [_sub_question(1)]
    )

    assert [a.paper_title for a in results] == ["B"]


def test_records_without_abstracts_are_not_sent_for_scoring(monkeypatch):
    """
    A record without an abstract has no relevance signal, and Semantic Scholar
    withholds abstracts for some publishers rather than at random. Scoring such
    records on their titles would systematically favour preprints over
    published articles for a reason unrelated to their content.

    The assertion is about the prompt, not the result: the paper must not be
    offered to the model at all.
    """
    seen = {}

    def capture(prompt, schema, purpose="request", use_cache=True):
        seen["prompt"] = prompt
        return [
            {"paper_title": "WithAbstract", "sub_question_id": 1, "relevance_score": 0.9, "reason": "r"}
        ]

    monkeypatch.setattr(evaluation_agent, "generate_json", capture)

    evaluation_agent.evaluate_evidence(
        [_paper("WithAbstract"), _paper("NoAbstract", abstract=None)],
        [_sub_question(1)],
    )

    assert "WithAbstract" in seen["prompt"]
    assert "NoAbstract" not in seen["prompt"]


def test_nothing_is_requested_when_no_record_can_be_assessed(monkeypatch):
    """
    Asserting that no call was made matters: sending a prompt containing no
    assessable evidence would spend a request from a daily allowance to
    receive an answer about nothing.
    """
    called = []

    def should_not_run(prompt, schema, purpose="request", use_cache=True):
        called.append(1)
        return []

    monkeypatch.setattr(evaluation_agent, "generate_json", should_not_run)

    results = evaluation_agent.evaluate_evidence(
        [_paper("A", abstract=None)], [_sub_question(1)]
    )

    assert called == []
    assert results == []


def test_every_paper_is_scored_against_every_sub_question(monkeypatch):
    """
    Scoring each pairing rather than each paper is what allows coverage to be
    reported per aspect of the research question, which is the reason for
    decomposing it. The prompt must therefore carry every sub-question.
    """
    seen = {}

    def capture(prompt, schema, purpose="request", use_cache=True):
        seen["prompt"] = prompt
        return []

    monkeypatch.setattr(evaluation_agent, "generate_json", capture)

    evaluation_agent.evaluate_evidence(
        [_paper("A")], [_sub_question(1), _sub_question(2), _sub_question(3)]
    )

    assert seen["prompt"].count("An aspect?") == 3