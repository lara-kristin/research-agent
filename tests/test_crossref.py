"""
Tests for Crossref validation.

The HTTP call is replaced rather than made, so the five outcomes can each be
exercised deliberately. Several are otherwise hard or impossible to produce on
demand: a Crossref record with no title, or a title that disagrees with the
retrieved one, cannot be conjured from the live service.

What is patched is crossref.get, not clients.get: this module imports the
function into its own namespace, so replacing it where it is defined would
leave the reference pointing at the real one.
"""

from src import crossref
from src.models import Paper


class FakeResponse:
    """
    Stands in for a requests.Response.

    Only the three members crossref.verify touches are provided. A fuller
    imitation would suggest the tests depend on more of the interface than
    they do.
    """

    def __init__(self, status_code: int, body: dict | None = None):
        self.status_code = status_code
        self._body = body or {}

    def json(self) -> dict:
        return self._body

    def raise_for_status(self) -> None:
        """Never raises: these tests supply only statuses verify handles."""


def _crossref_body(title: str) -> dict:
    """A Crossref works response, with the title nested as that API returns it."""
    return {"message": {"title": [title]}}


def test_matching_title_verifies_the_doi(monkeypatch):
    """
    The DOI resolves and the registered title agrees, which is the only
    outcome that sets doi_verified.
    """
    monkeypatch.setattr(
        crossref, "get", lambda *a, **k: FakeResponse(200, _crossref_body("A Paper"))
    )

    result = crossref.verify(Paper(title="A Paper", doi="10.1/x"))

    assert result.doi_verified is True
    assert result.verification_note is None


def test_punctuation_and_case_differences_still_verify(monkeypatch):
    """
    Sources differ typographically for the same work. Comparing raw strings
    would report a mismatch that is purely a matter of punctuation, and a
    mismatch is the same flag as a genuinely wrong title.
    """
    monkeypatch.setattr(
        crossref,
        "get",
        lambda *a, **k: FakeResponse(200, _crossref_body("A Paper: Revisited!")),
    )

    result = crossref.verify(Paper(title="a paper revisited", doi="10.1/x"))

    assert result.doi_verified is True


def test_disagreeing_title_does_not_verify(monkeypatch):
    """
    A registered title that differs is recorded rather than treated as a
    match. This is the check that would catch a mistaken or fabricated DOI,
    which is what the design proposal asks validation to guard against.
    """
    monkeypatch.setattr(
        crossref,
        "get",
        lambda *a, **k: FakeResponse(200, _crossref_body("An Entirely Different Paper")),
    )

    result = crossref.verify(Paper(title="A Paper", doi="10.1/x"))

    assert result.doi_verified is False
    assert "disagrees" in result.verification_note


def test_arxiv_doi_is_recorded_as_a_preprint(monkeypatch):
    """
    arXiv registers with DataCite, so Crossref returns 404 however valid the
    DOI is. Recording the reason separates an ordinary preprint from a DOI
    Crossref rejected, which matters because preprints are a large share of
    results in this field.
    """
    monkeypatch.setattr(crossref, "get", lambda *a, **k: FakeResponse(404))

    result = crossref.verify(Paper(title="A Preprint", doi="10.48550/arxiv.2503.13657"))

    assert result.doi_verified is False
    assert "preprint" in result.verification_note


def test_unregistered_doi_is_distinguished_from_a_preprint(monkeypatch):
    """
    The same 404 means something different for a non-arXiv DOI: Crossref
    should hold it and does not. Both are unverified, and the Evaluation Agent
    needs to weigh them differently.
    """
    monkeypatch.setattr(crossref, "get", lambda *a, **k: FakeResponse(404))

    result = crossref.verify(Paper(title="A Paper", doi="10.9999/nonexistent"))

    assert "not registered" in result.verification_note
    assert "preprint" not in result.verification_note


def test_record_without_a_doi_is_not_requested(monkeypatch):
    """
    A record with no DOI cannot be validated by any means, so no request is
    made. Asserting that nothing was called matters: issuing a request for an
    empty DOI would spend quota to receive a certain failure.
    """
    called = []
    monkeypatch.setattr(crossref, "get", lambda *a, **k: called.append(1))

    result = crossref.verify(Paper(title="No DOI Here"))

    assert called == []
    assert result.verification_note == "no DOI in record"


def test_crossref_record_with_no_title_does_not_verify(monkeypatch):
    """
    A response carrying no title leaves nothing to compare against. Treating
    that as a match would verify a DOI on the strength of a record that says
    nothing about it.
    """
    monkeypatch.setattr(
        crossref, "get", lambda *a, **k: FakeResponse(200, {"message": {}})
    )

    result = crossref.verify(Paper(title="A Paper", doi="10.1/x"))

    assert result.doi_verified is False
    assert "no title" in result.verification_note