"""
Domain models. These describe the data this system works with, not the shape
any particular API returns. Keeping the two separate means a change of source,
such as the OpenAlex fallback named in the design proposal, is confined to the
client that adapts it.
"""

from enum import Enum

from pydantic import BaseModel, Field, field_validator


class Decision(Enum):
    """
    A researcher's verdict at a review checkpoint. Mirrors the Decision
    enumeration in Diagram 1.

    All four values live here, but the two checkpoints accept different
    subsets: sub-question review takes APPROVE or REVISE, and evidence review
    takes APPROVE, REFINE or REJECT_SCOPE. Keeping one enumeration rather than
    two avoids two names for the same verdict, and each checkpoint states
    which values it accepts.
    """

    APPROVE = "approve"
    REVISE = "revise"
    REFINE = "refine"
    REJECT_SCOPE = "reject_scope"


class Paper(BaseModel):
    """A retrieved paper. Mirrors the Paper class in Diagram 1."""

    title: str
    year: int | None = None
    doi: str | None = None
    authors: list[str] = Field(default_factory=list)
    abstract: str | None = None

    # Named doi_verified rather than doiVerified: the diagram uses UML
    # convention, Python uses snake_case. Defaults to False so a paper is
    # unverified until Crossref confirms it, rather than assumed sound.
    doi_verified: bool = False

    # A boolean alone cannot distinguish a DOI Crossref rejected from one it
    # was never able to hold. Testing showed arXiv DOIs are registered with
    # DataCite rather than Crossref, so unverified would otherwise conflate a
    # doubtful record with an ordinary preprint. The reason is recorded here so
    # the Evaluation Agent can weigh the two differently.
    verification_note: str | None = None

    # DOIs are case-insensitive, so the same paper can arrive with different
    # capitalisation from different sources. Normalising here rather than at
    # each comparison means deduplication cannot miss a duplicate that differs
    # only in case.
    @field_validator("doi")
    @classmethod
    def normalise_doi(cls, value: str | None) -> str | None:
        return value.lower().strip() if value else None


class SubQuestion(BaseModel):
    """
    One decomposed part of the research question. Mirrors SubQuestion in
    Diagram 1.

    text is the question a reader would recognise; search_query is the keyword
    form sent to the literature API. They are separate fields because they
    serve different consumers: the researcher reviews the first at the
    approval checkpoint, and only the second is ever sent to a search
    endpoint. Collapsing them would mean approving something other than what
    is searched.
    """

    id: int
    text: str
    search_query: str

    # Both default to the state that has not happened yet, so neither approval
    # nor a retry can be assumed by omission.
    approved: bool = False
    retried_once: bool = False


class Assessment(BaseModel):
    """
    One paper judged against one sub-question. Mirrors Assessment in
    Diagram 1.

    Holds identifiers rather than the objects themselves. A relevance score is
    about a pairing, and every paper is scored against every sub-question, so
    embedding whole papers would repeat each abstract once per sub-question in
    memory and in the saved output.

    paper_title is the identifier because a DOI cannot serve as one: records
    without a DOI are retained deliberately, so keying on it would make some
    papers unassessable for a reason unrelated to their relevance.
    """

    paper_title: str
    sub_question_id: int
    relevance_score: float = Field(ge=0.0, le=1.0)
    reason: str

    # Set by the agent applying a threshold, not by the model. The model
    # scores; the decision of what counts as selected is a deterministic rule
    # and stays auditable.
    selected: bool = False


class Brief(BaseModel):
    """
    The research brief. Mirrors Brief in Diagram 1.

    Summaries, themes and gaps are produced by the model, since each requires
    reading what the papers say. Limitations are not: they are assembled from
    what the run itself recorded, because the system knows which records it
    could not verify and which sub-questions returned thin coverage. A model
    asked to state limitations would produce plausible ones rather than the
    actual ones, which is the unfaithful-summarisation failure the design
    proposal cites.
    """

    research_question: str
    sub_questions: list[SubQuestion] = Field(default_factory=list)
    selected_papers: list[Paper] = Field(default_factory=list)

    # Keyed by paper title, matching how assessments identify papers. A paper
    # with no summary is visible as an absence rather than as a silent gap in
    # a positional list.
    summaries: dict[str, str] = Field(default_factory=dict)

    themes: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class SearchResponse(BaseModel):
    """
    The shape of a Semantic Scholar search response, as distinct from the
    domain data inside it. This is where the API's own conventions are
    absorbed: total is always present, whereas data is omitted entirely on
    zero matches, established by inspecting a live response. Declaring both
    facts here replaces the shape checks written by hand at stage 1.
    """

    total: int
    data: list[dict] = Field(default_factory=list)