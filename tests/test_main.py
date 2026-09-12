"""
Tests for the entry point.

The entry point does little, but what it does is translate outcomes into exit
codes, and an exit code is the only thing a shell or a marking script can read.
A run that fails while reporting success is indistinguishable from one that
worked.

Logging configuration is replaced along with the orchestrator. Configuring it
here would attach handlers and append to the working log file, so a test run
would write into the record of real runs.
"""

import sys

import pytest

from src import main as entry
from src.clients import QuotaExhaustedError, RetryableHTTPError
from src.llm import LLMResponseError
from src.models import Brief
from src.semantic_scholar import MissingAPIKeyError


@pytest.fixture(autouse=True)
def quiet_logging(monkeypatch):
    monkeypatch.setattr(entry, "configure", lambda *a, **k: None)


@pytest.fixture
def argv(monkeypatch):
    """Supply a command line, as the shell would."""

    def set_args(*extra: str):
        monkeypatch.setattr(sys, "argv", ["src.main", "A question?", *extra])

    return set_args


def test_a_successful_run_saves_and_returns_zero(argv, monkeypatch, tmp_path):
    """
    Zero means the run did what was asked. The brief must also reach disk:
    returning success without saving would report work that produced nothing.
    """
    saved = []
    monkeypatch.setattr(
        entry, "run_research", lambda q, limit, use_cache: (Brief(research_question=q), [])
    )
    monkeypatch.setattr(
        entry,
        "save_brief",
        lambda brief, assessments: saved.append(brief) or (tmp_path / "b.md", tmp_path / "b.json"),
    )
    argv()

    assert entry.main() == 0
    assert len(saved) == 1


def test_a_second_scope_rejection_returns_one_without_saving(argv, monkeypatch):
    """
    The run stopped because the researcher judged the question wrong twice.
    Nothing is saved, because there is no evidence the researcher accepted,
    and a brief written anyway would record a search they rejected.
    """
    saved = []
    monkeypatch.setattr(entry, "run_research", lambda q, limit, use_cache: None)
    monkeypatch.setattr(entry, "save_brief", lambda *a: saved.append(1))
    argv()

    assert entry.main() == 1
    assert saved == []


@pytest.mark.parametrize(
    "failure",
    [
        MissingAPIKeyError("no key"),
        QuotaExhaustedError("429 quota"),
        RetryableHTTPError("503"),
        LLMResponseError("no candidate"),
    ],
)
def test_each_actionable_failure_returns_one(argv, monkeypatch, failure):
    """
    Each of these is a condition the person running the system can act on: a
    missing credential, an exhausted allowance, a service that stayed
    unavailable, a model response that could not be used. All are reported
    rather than raised, so the run ends with a code rather than a traceback.
    """

    def fail(question, limit, use_cache):
        raise failure

    monkeypatch.setattr(entry, "run_research", fail)
    argv()

    assert entry.main() == 1


def test_an_unexpected_error_is_not_swallowed(argv, monkeypatch):
    """
    A defect must surface with its traceback rather than be reported as though
    it were an expected outcome. Catching everything would turn every bug into
    a tidy exit code and hide it.
    """

    def fail(question, limit, use_cache):
        raise ZeroDivisionError("a defect")

    monkeypatch.setattr(entry, "run_research", fail)
    argv()

    with pytest.raises(ZeroDivisionError):
        entry.main()


def test_the_no_cache_flag_reaches_the_orchestrator(argv, monkeypatch, tmp_path):
    """
    The flag is announced at the start of every run, so a flag that is
    reported but not passed on would produce a log stating that requests were
    live while they were served from disk.
    """
    seen = {}

    def capture(question, limit, use_cache):
        seen["use_cache"] = use_cache
        return Brief(research_question=question), []

    monkeypatch.setattr(entry, "run_research", capture)
    monkeypatch.setattr(
        entry, "save_brief", lambda *a: (tmp_path / "b.md", tmp_path / "b.json")
    )

    argv("--no-cache")
    entry.main()
    assert seen["use_cache"] is False

    argv()
    entry.main()
    assert seen["use_cache"] is True