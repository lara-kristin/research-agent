"""
Tests for synthesis and the limitations it reports.

The limitations are the part worth testing hardest. They are assembled from
what the run recorded rather than asked of the model, and a limitations
section that misreports a run is worse than none: it states something false
about the search in the document a researcher relies on.

What is patched is synthesis.generate_json, not llm.generate_json, for the
same namespace reason as elsewhere.
"""

from src import synthesis
from src.models import Assessment, Paper, SubQuestion


def _paper(title: str, verified: bool = False, abstract: str | None = "An abstract.") -> Paper:
    return Paper(
        title=title,
        doi=f"10.1/{title.lower()}",
        abstract=abstract,
        doi_verified=verified,
    )


def _sub_question(id: int, retried: bool = False) -> SubQuestion:
    return SubQuestion(
        id=id,
        text="An aspect?",
        search_query="keywords",
        approved=True,
        retried_once=retried,
    )


def _assessment(title: str, score: float) -> Assessment:
    return Assessment(
        paper_title=title, sub_question_id=1, relevance_score=score, reason="r"
    )


def _returns(payload):
    def fake(prompt, schema, purpose="request", use_cache=True):
        return payload

    return fake


def _ok(titles):
    return {
        "summaries": [{"paper_title": t, "summary": f"Summary of {t}."} for t in titles],
        "themes": ["A theme"],
        "gaps": ["A gap"],
    }


def test_summaries_are_matched_to_approved_papers(monkeypatch):
    """
    A summary naming a paper that was not approved would place text about an
    unapproved record in the brief, which is the same fabrication risk the
    assessment stage checks for. Unlike a relevance score, a summary cannot be
    checked against anything the system holds, so matching the title is the
    only control available.
    """
    monkeypatch.setattr(
        synthesis, "generate_json", _returns(_ok(["Approved", "NotApproved"]))
    )

    brief = synthesis.synthesise(
        "Q?", [_sub_question(1)], [_paper("Approved")], [_paper("Approved")], []
    )

    assert list(brief.summaries) == ["Approved"]


def test_a_missing_summary_is_left_absent(monkeypatch):
    """
    A paper appearing in the brief with no summary is visibly incomplete. One
    given a placeholder would read as though it had been summarised, which is
    a worse outcome than an obvious gap.
    """
    monkeypatch.setattr(synthesis, "generate_json", _returns(_ok(["A"])))

    papers = [_paper("A"), _paper("B")]
    brief = synthesis.synthesise("Q?", [_sub_question(1)], papers, papers, [])

    assert "B" not in brief.summaries
    assert len(brief.selected_papers) == 2


def test_unverified_papers_are_counted_in_the_limitations(monkeypatch):
    """
    The count is taken from the papers themselves rather than asked of the
    model, which is what makes it true of this run rather than plausible in
    general.
    """
    monkeypatch.setattr(synthesis, "generate_json", _returns(_ok(["A", "B", "C"])))

    papers = [_paper("A", verified=True), _paper("B"), _paper("C")]
    brief = synthesis.synthesise("Q?", [_sub_question(1)], papers, papers, [])

    assert any("2 of 3 selected papers" in limit for limit in brief.limitations)


def test_records_without_abstracts_are_reported_in_the_limitations(monkeypatch):
    """
    A record excluded from scoring was never a candidate for selection
    regardless of its content. The brief says so, because a reader comparing
    what was retrieved with what was selected would otherwise assume the
    difference was a judgement about relevance.
    """
    monkeypatch.setattr(synthesis, "generate_json", _returns(_ok(["A"])))

    approved = [_paper("A")]
    retrieved = approved + [_paper("NoAbstract", abstract=None)]
    brief = synthesis.synthesise("Q?", [_sub_question(1)], approved, retrieved, [])

    assert any("carried no abstract" in limit for limit in brief.limitations)


def test_a_reformulated_sub_question_is_reported_without_claiming_its_results(monkeypatch):
    """
    The limitation reports that a reformulation was attempted, not that its
    results were used. The reformulated query is kept only when it retrieved
    more, so asserting the evidence came from it would be false whenever the
    original result was retained.
    """
    monkeypatch.setattr(synthesis, "generate_json", _returns(_ok(["A"])))

    papers = [_paper("A")]
    brief = synthesis.synthesise(
        "Q?", [_sub_question(1, retried=True), _sub_question(2)], papers, papers, []
    )

    reformulation_note = next(
        limit for limit in brief.limitations if "reformulated query was tried" in limit
    )
    assert "sub-question(s) 1" in reformulation_note
    assert "2" not in reformulation_note.split("sub-question(s)")[1][:5]


def test_no_reformulation_note_when_none_occurred(monkeypatch):
    """
    The counterpart: a limitation that appears on every run regardless of what
    happened carries no information about the run it describes.
    """
    monkeypatch.setattr(synthesis, "generate_json", _returns(_ok(["A"])))

    papers = [_paper("A")]
    brief = synthesis.synthesise("Q?", [_sub_question(1)], papers, papers, [])

    assert not any("reformulated query was tried" in l for l in brief.limitations)


def test_clustered_scores_are_reported_as_coarse(monkeypatch):
    """
    Relevance scores were observed taking only a few distinct values across a
    run. Saying so keeps the brief from implying the scores are finer
    measurements than they are.
    """
    monkeypatch.setattr(synthesis, "generate_json", _returns(_ok(["A"])))

    papers = [_paper("A")]
    assessments = [_assessment("A", 0.9), _assessment("A", 0.6)]
    brief = synthesis.synthesise("Q?", [_sub_question(1)], papers, papers, assessments)

    assert any("coarse bands" in limit for limit in brief.limitations)


def test_a_brief_is_produced_when_nothing_was_approved(monkeypatch):
    """
    An empty brief that states its own limitations records what was asked and
    searched, which is more useful to the researcher than no file at all. No
    model call is made, since there is nothing to summarise.
    """
    called = []

    def should_not_run(prompt, schema, purpose="request", use_cache=True):
        called.append(1)
        return {}

    monkeypatch.setattr(synthesis, "generate_json", should_not_run)

    brief = synthesis.synthesise("Q?", [_sub_question(1)], [], [_paper("A")], [])

    assert called == []
    assert brief.selected_papers == []
    assert any("No paper was approved" in limit for limit in brief.limitations)