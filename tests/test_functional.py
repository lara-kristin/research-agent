"""
Functional test: one complete run, from research question to saved brief.

Distinct from the unit tests in what it replaces. Those substitute the
system's own functions to isolate a behaviour; this one substitutes only the
boundary, the HTTP layer and the terminal, so every module runs for real and
the sequence between them is what is under test. A fault in how the
orchestrator wires the agents together would pass every unit test and fail
here.

Nothing reaches the network. The literature source, the DOI registry and the
model are all answered by a single dispatcher that recognises which service is
being called and, for the model, which of its four tasks is being asked.
"""

import builtins
import json

import pytest

from src import cache, clients, orchestrator
from src.models import Brief


class FakeResponse:
    """Stands in for a requests.Response, with only the members used."""

    def __init__(self, body: dict, status_code: int = 200):
        self.status_code = status_code
        self._body = body
        self.headers: dict[str, str] = {}

    def json(self) -> dict:
        return self._body

    @property
    def text(self) -> str:
        return json.dumps(self._body)

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise AssertionError(f"Unexpected status {self.status_code}")


def _paper(title: str, doi: str | None, abstract: str | None = "An abstract.") -> dict:
    """A Semantic Scholar record, shaped as that API returns one."""
    record = {
        "title": title,
        "year": 2025,
        "authors": [{"authorId": "1", "name": "A. Author"}],
        "abstract": abstract,
    }
    if doi:
        record["externalIds"] = {"DOI": doi}
    return record


# Three records per sub-question, with one shared between the first two so
# that deduplication has something to remove, and one carrying no abstract so
# that the exclusion from scoring is exercised.
SEARCH_RESULTS = {
    "query one": [
        _paper("Alpha", "10.1/alpha"),
        _paper("Beta", "10.1/beta"),
        _paper("Shared", "10.1/shared"),
    ],
    "query two": [
        _paper("Shared", "10.1/SHARED"),
        _paper("Gamma", "10.48550/arxiv.1234"),
        _paper("Delta", "10.1/delta"),
    ],
    "query three": [
        _paper("Epsilon", "10.1/epsilon"),
        _paper("NoAbstract", "10.1/noabs", abstract=None),
        _paper("Zeta", None),
    ],
}

PLAN = [
    {"id": 1, "text": "First aspect?", "search_query": "query one"},
    {"id": 2, "text": "Second aspect?", "search_query": "query two"},
    {"id": 3, "text": "Third aspect?", "search_query": "query three"},
]


def _assess(titles: list[str]) -> list[dict]:
    """Score every title against every sub-question, alternating selection."""
    out = []
    for index, title in enumerate(titles):
        for sub_question_id in (1, 2, 3):
            out.append(
                {
                    "paper_title": title,
                    "sub_question_id": sub_question_id,
                    # Alternating, so both sides of the threshold occur and the
                    # selection is a subset rather than everything.
                    "relevance_score": 0.9 if index % 2 == 0 else 0.2,
                    "reason": "r",
                }
            )
    return out


@pytest.fixture
def world(monkeypatch, tmp_path):
    """
    Answer every outbound request without a network, and record what was asked.

    Returns the record so a test can assert on the calls made as well as on
    the brief produced: a run that reaches the right output by making the
    wrong requests is not a working run.
    """
    calls: dict[str, list] = {"search": [], "crossref": [], "llm": []}

    def dispatch(method, url, **kwargs):
        if "semanticscholar" in url:
            query = kwargs["params"]["query"]
            calls["search"].append(query)
            data = SEARCH_RESULTS.get(query, [])
            return FakeResponse({"total": len(data), "data": data})

        if "crossref" in url:
            # Split on the endpoint, not the last slash: a DOI contains a
            # slash of its own, so rsplit would return only its suffix and the
            # arXiv prefix below would never match.
            doi = url.split("/works/", 1)[1]
            calls["crossref"].append(doi)
            if doi.startswith("10.48550"):
                return FakeResponse({}, status_code=404)
            # Titles are keyed off the DOI so the comparison succeeds.
            title = doi.rsplit("/", 1)[-1].capitalize()
            return FakeResponse({"message": {"title": [title]}})

        if "generativelanguage" in url:
            prompt = kwargs["json"]["contents"][0]["parts"][0]["text"]
            calls["llm"].append(prompt)

            if "Decompose it into exactly" in prompt:
                payload = PLAN
            elif "returned too few results" in prompt:
                payload = {"search_query": "reformulated"}
            elif "Assess every paper" in prompt:
                titles = [
                    line[len("Title: ") :]
                    for line in prompt.splitlines()
                    if line.startswith("Title: ")
                ]
                payload = _assess(titles)
            else:
                titles = [
                    line[len("Title: ") :]
                    for line in prompt.splitlines()
                    if line.startswith("Title: ")
                ]
                payload = {
                    "summaries": [
                        {"paper_title": t, "summary": f"Summary of {t}."} for t in titles
                    ],
                    "themes": ["A theme"],
                    "gaps": ["A gap"],
                }

            return FakeResponse(
                {"candidates": [{"content": {"parts": [{"text": json.dumps(payload)}]}}]}
            )

        raise AssertionError(f"Unexpected request to {url}")

    monkeypatch.setattr(clients.requests, "request", dispatch)
    monkeypatch.setattr(clients.RateLimiter, "wait", lambda self: None)
    monkeypatch.setattr(clients.request.retry, "sleep", lambda seconds: None)
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(orchestrator, "OUTPUT_DIR", tmp_path / "output")
    return calls


@pytest.fixture
def answers(monkeypatch):
    queue: list[str] = []

    def fake_input(prompt: str = "") -> str:
        if not queue:
            raise AssertionError(f"Unexpected prompt with no answer queued: {prompt!r}")
        return queue.pop(0)

    monkeypatch.setattr(builtins, "input", fake_input)
    return queue


def test_a_complete_run_produces_a_brief(world, answers):
    """
    The whole sequence, approved at both checkpoints: decomposition, retrieval
    for each sub-question, deduplication, validation, assessment, synthesis.
    """
    answers.extend(["approve", "approve"])

    brief, assessments = orchestrator.run_research("A research question?", limit=3)

    assert isinstance(brief, Brief)
    assert brief.research_question == "A research question?"
    assert len(brief.sub_questions) == 3
    assert brief.themes and brief.gaps and brief.limitations
    assert brief.selected_papers
    assert assessments

    # Each approved paper carries a summary, and no summary names a paper that
    # was not approved.
    approved_titles = {paper.title for paper in brief.selected_papers}
    assert set(brief.summaries) <= approved_titles


def test_every_sub_question_is_searched_and_every_doi_validated(world, answers):
    """
    A run that produced a plausible brief while skipping a sub-question or a
    validation would pass a test that only inspected the output.
    """
    answers.extend(["approve", "approve"])

    orchestrator.run_research("A research question?", limit=3)

    assert world["search"][:3] == ["query one", "query two", "query three"]

    # Nine records retrieved, one a duplicate, so eight survive deduplication.
    # Seven reach Crossref: the record carrying no DOI is never sent, because
    # it cannot be validated by any means and a request for it would spend
    # quota to receive a certain failure.
    assert len(world["crossref"]) == 7
    assert "10.1/shared" in world["crossref"]
    assert not any(d == "" or d is None for d in world["crossref"])


def test_the_duplicate_is_removed_and_the_doi_less_record_retained(world, answers):
    """
    The same paper is returned under two sub-questions with differently
    capitalised DOIs, and one record carries no DOI at all. Deduplication must
    merge the first, which depends on the DOI being normalised when the record
    is constructed, and must retain the second, which cannot be compared on
    the field it deduplicates by.
    """
    answers.extend(["approve", "approve"])

    brief, _ = orchestrator.run_research("A research question?", limit=3)

    # The duplicate is sent to Crossref once, not twice.
    assert world["crossref"].count("10.1/shared") == 1

    # The DOI-less record survives to the brief rather than being discarded.
    assert any(paper.doi is None for paper in brief.selected_papers)


def test_refinement_at_the_second_checkpoint_reaches_the_brief(world, answers):
    """
    A paper the researcher removes must not appear in the brief. The
    checkpoint's decision has to survive synthesis, which is the longest path
    any researcher input takes through the system.
    """
    answers.extend(["approve", "refine", "1"])

    brief, _ = orchestrator.run_research("A research question?", limit=3)

    # One fewer than an approved run would produce.
    answers.extend(["approve", "approve"])
    full, _ = orchestrator.run_research("A research question?", limit=3)

    assert len(brief.selected_papers) == len(full.selected_papers) - 1


def test_an_unmet_threshold_triggers_one_reformulation(world, answers):
    """
    The third sub-question returns three records of which one has no abstract,
    so two are usable against a threshold of three. That must prompt exactly
    one reformulation, and since the reformulated query returns nothing, the
    original result must be kept along with the original query.
    """
    answers.extend(["approve", "approve"])

    brief, _ = orchestrator.run_research("A research question?", limit=3)

    reformulations = [p for p in world["llm"] if "returned too few results" in p]
    assert len(reformulations) == 1

    third = next(sq for sq in brief.sub_questions if sq.id == 3)
    assert third.retried_once is True
    # The reformulated query found nothing, so the approved one is what
    # produced the evidence and is what the brief must record.
    assert third.search_query == "query three"
    assert any("reformulated query was tried" in l for l in brief.limitations)


def test_a_scope_rejection_returns_to_planning_then_stops(world, answers):
    """
    Two rejections exhaust the single permitted revision, and the run stops
    rather than searching again. The cap is what keeps a rejected question
    from consuming the allowance indefinitely.
    """
    answers.extend(
        ["approve", "reject", "wrong scope", "approve", "reject", "still wrong"]
    )

    result = orchestrator.run_research("A research question?", limit=3)

    assert result is None
    # Decomposition ran twice: once originally, once for the revision.
    decompositions = [p for p in world["llm"] if "Decompose it into exactly" in p]
    assert len(decompositions) == 2
    assert "wrong scope" in decompositions[1]


def test_the_brief_is_written_to_disk_in_both_formats(world, answers, tmp_path):
    """
    The design proposal requires Markdown for the researcher and JSON for
    machine reading. The JSON must carry every assessment, including those not
    selected, so a decision can be reconstructed.
    """
    answers.extend(["approve", "approve"])

    brief, assessments = orchestrator.run_research("A research question?", limit=3)
    markdown_path, json_path = orchestrator.save_brief(brief, assessments)

    assert markdown_path.exists() and json_path.exists()

    text = markdown_path.read_text(encoding="utf-8")
    assert "# Research brief: A research question?" in text
    assert "## Limitations of this search" in text

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert len(payload["assessments"]) == len(assessments)
    assert any(not a["selected"] for a in payload["assessments"])