"""
Tests for the Planning Agent.

The LLM call is replaced rather than made. A test that called the provider
would be slow, non-deterministic, dependent on a network, and would consume a
daily request allowance that the project needs for real runs. Replacing it
tests this module's handling of a response, which is the part written here.

Note what is patched: planning_agent imports generate_json into its own
namespace, so the name to replace is src.planning_agent.generate_json.
Patching src.llm.generate_json would leave the agent's reference pointing at
the real function and the test would call the live API.
"""

import pytest
from pydantic import ValidationError

from src import planning_agent
from src.models import SubQuestion

VALID_PLAN = [
    {"id": 1, "text": "First aspect?", "search_query": "first keywords"},
    {"id": 2, "text": "Second aspect?", "search_query": "second keywords"},
    {"id": 3, "text": "Third aspect?", "search_query": "third keywords"},
]


def _fake_llm(returns, record_prompts=None):
    """
    Build a stand-in for generate_json.

    Optionally records the prompts it was given, so a test can assert what the
    agent asked for rather than only what it did with the answer.
    """

    def fake(prompt, schema, purpose="request", use_cache=True):
        if record_prompts is not None:
            record_prompts.append(prompt)
        return returns

    return fake


def test_valid_response_becomes_sub_questions(monkeypatch):
    """
    The provider's schema constrains shape, not meaning. This asserts the
    mapping from a well-formed response to the domain model, including that
    text and search_query stay distinct: collapsing them would mean the
    researcher approves something other than what is searched.
    """
    monkeypatch.setattr(planning_agent, "generate_json", _fake_llm(VALID_PLAN))

    result = planning_agent.plan_research("Any question?")

    assert len(result) == 3
    assert all(isinstance(sq, SubQuestion) for sq in result)
    assert result[0].search_query == "first keywords"
    assert result[0].text != result[0].search_query


def test_sub_questions_start_unapproved(monkeypatch):
    """
    Approval must come from the researcher, not from the agent. Retrieval
    refuses unapproved sub-questions, so a plan arriving pre-approved would
    bypass the first human checkpoint.
    """
    monkeypatch.setattr(planning_agent, "generate_json", _fake_llm(VALID_PLAN))

    assert all(not sq.approved for sq in planning_agent.plan_research("Any question?"))
    assert all(not sq.retried_once for sq in planning_agent.plan_research("Any question?"))


def test_response_missing_a_field_is_rejected(monkeypatch):
    """
    A response lacking search_query cannot be searched. Pydantic refuses it
    here rather than allowing a sub-question with no query to reach retrieval,
    where the failure would be reported as an empty search.
    """
    monkeypatch.setattr(
        planning_agent,
        "generate_json",
        _fake_llm([{"id": 1, "text": "Missing its query?"}]),
    )

    with pytest.raises(ValidationError):
        planning_agent.plan_research("Any question?")


def test_unexpected_count_is_returned_not_rejected(monkeypatch):
    """
    The schema cannot express "exactly three", so the count is checked in the
    agent and logged rather than raised. A plan of two is still usable and the
    researcher reviews it before anything is searched, so failing the run
    would discard a usable plan over a condition the checkpoint covers.
    """
    monkeypatch.setattr(planning_agent, "generate_json", _fake_llm(VALID_PLAN[:2]))

    assert len(planning_agent.plan_research("Any question?")) == 2


def test_feedback_reaches_the_prompt(monkeypatch):
    """
    A revision is meaningless if the reason is not passed on: the agent would
    regenerate and produce a different decomposition by chance rather than by
    correction.
    """
    prompts = []
    monkeypatch.setattr(
        planning_agent, "generate_json", _fake_llm(VALID_PLAN, record_prompts=prompts)
    )

    planning_agent.plan_research("Any question?", feedback="narrow question 3")

    assert "narrow question 3" in prompts[0]


def test_reformulation_replaces_the_query_and_marks_the_retry(monkeypatch):
    """
    The flag is what allows the orchestrator to enforce the one-retry limit,
    so it must be set on the returned copy. The original must be left
    unchanged, since a caller holding it should not have its state altered by
    a call it did not make.
    """
    monkeypatch.setattr(
        planning_agent, "generate_json", _fake_llm({"search_query": "broader terms"})
    )
    original = SubQuestion(id=1, text="An aspect?", search_query="narrow terms")

    revised = planning_agent.reformulate_query(original)

    assert revised.search_query == "broader terms"
    assert revised.retried_once is True
    assert original.search_query == "narrow terms"
    assert original.retried_once is False