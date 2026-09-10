"""
Crossref validation.

Confirms independently that a retrieved DOI is registered and that its
metadata matches the record it arrived with. The design proposal treats this
as a control against fabricated or mistaken citation details, so the check
must query a service other than the one the record came from.
"""

import logging
import os
import re

from dotenv import load_dotenv

from src.clients import crossref_limiter, get
from src.models import Paper

logger = logging.getLogger(__name__)

WORKS_URL = "https://api.crossref.org/works/"

# arXiv registers its DOIs with DataCite rather than Crossref, so a Crossref
# lookup cannot succeed for them however valid the DOI is. Observed during
# testing: two of three records from a multi-agent systems search were arXiv
# preprints. Recognising the prefix keeps an ordinary preprint distinct from a
# DOI Crossref actively failed to match.
ARXIV_DOI_PREFIX = "10.48550"

# Crossref asks callers to identify themselves, which grants access to a more
# reliably provisioned pool of servers. Held in .env rather than the source:
# not because it is secret, but because a public repository should not carry a
# personal address. Absence degrades service rather than preventing it.
load_dotenv()
CONTACT_EMAIL = os.getenv("CROSSREF_CONTACT_EMAIL")


# Publishers deposit titles containing presentational markup, so a Crossref
# record can carry tags the retrieved title does not. Observed in a live run:
# a registered title arrived as "<i>The Truth Becomes Clearer Through
# Debate!</i>" against the same title in plain text.
_HTML_TAG = re.compile(r"<[^>]+>")


def _normalise_title(title: str) -> str:
    """
    Reduce a title to a form two sources can be compared on.

    Punctuation, case and spacing vary between sources for the same work, so
    comparing raw strings would report mismatches that are purely
    typographical.

    Markup is removed before punctuation, and the order matters. Stripping
    non-alphanumerics first leaves the letters inside a tag behind, so <i>
    contributes a stray "i" that fuses with the surrounding words and the
    comparison fails on a title that is in fact identical. That mattered
    because a title mismatch is reported as the signal of a doubtful citation,
    so a correctly registered paper was being flagged exactly as a fabricated
    one would be.
    """
    without_markup = _HTML_TAG.sub(" ", title)
    return re.sub(r"[^a-z0-9]+", "", without_markup.lower())


def verify(paper: Paper) -> Paper:
    """
    Return the paper with doi_verified set according to Crossref.

    Returns a copy rather than modifying the original, so a caller holding the
    unverified record still has it. Five outcomes are distinguished and none
    of them is an error: no DOI to check, an arXiv DOI Crossref cannot hold, a
    DOI Crossref does not recognise, a Crossref record with no title, and a
    registered title that disagrees with the retrieved one. All
    four leave the paper unverified, which is the flagged state the design
    proposal requires. Each records its reason in verification_note, because
    an arXiv preprint and a DOI Crossref rejected are both unverified but
    warrant different treatment downstream.
    """
    if not paper.doi:
        # Confirmed at stage 1 that some records carry no DOI at all. Such a
        # record cannot be validated against Crossref by any means, so it is
        # reported rather than silently passed over.
        logger.info("No DOI to verify: %r", paper.title)
        return paper.model_copy(update={"verification_note": "no DOI in record"})

    params = {"mailto": CONTACT_EMAIL} if CONTACT_EMAIL else {}
    response = get(WORKS_URL + paper.doi, crossref_limiter, params=params)

    # A 404 means the DOI is not registered with Crossref. That is an answer,
    # not a failure of the request, so it is handled here rather than raised:
    # the paper stays unverified and the run continues.
    if response.status_code == 404:
        if paper.doi.startswith(ARXIV_DOI_PREFIX):
            logger.info("arXiv preprint, not held by Crossref: %s", paper.doi)
            return paper.model_copy(
                update={"verification_note": "arXiv preprint, registered with DataCite not Crossref"}
            )
        logger.warning("DOI not registered with Crossref: %s", paper.doi)
        return paper.model_copy(update={"verification_note": "DOI not registered with Crossref"})

    # Anything else in the 4xx or 5xx range is a problem with the request
    # itself, which the caller needs to hear about rather than have recorded
    # as a verification result.
    response.raise_for_status()

    registered = response.json()["message"]

    # Crossref returns titles as a list, since a work can carry more than one.
    registered_titles = registered.get("title") or []
    if not registered_titles:
        logger.warning("Crossref record has no title to compare: %s", paper.doi)
        return paper.model_copy(update={"verification_note": "Crossref record has no title"})

    if _normalise_title(registered_titles[0]) != _normalise_title(paper.title):
        logger.warning(
            "Title mismatch for %s: retrieved %r, registered %r",
            paper.doi,
            paper.title,
            registered_titles[0],
        )
        return paper.model_copy(update={"verification_note": "title disagrees with Crossref"})

    logger.info("Verified %s", paper.doi)
    return paper.model_copy(update={"doi_verified": True})