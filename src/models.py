"""
Domain models. These describe the data this system works with, not the shape
any particular API returns. Keeping the two separate means a change of source,
such as the OpenAlex fallback named in the design proposal, is confined to the
client that adapts it.
"""

from pydantic import BaseModel, Field, field_validator


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

    # DOIs are case-insensitive, so the same paper can arrive with different
    # capitalisation from different sources. Normalising here rather than at
    # each comparison means deduplication cannot miss a duplicate that differs
    # only in case.
    @field_validator("doi")
    @classmethod
    def normalise_doi(cls, value: str | None) -> str | None:
        return value.lower().strip() if value else None

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