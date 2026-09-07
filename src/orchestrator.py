"""
Orchestrator: the deterministic coordinator described in the design proposal.

Not an agent. It sequences the agents and performs the checks that need no
model: deduplication, validation and storage. Keeping these here rather than
inside an agent is what the proposal means by restricting model use to
semantic tasks and leaving exact rules deterministic.
"""

import logging

from src.crossref import verify
from src.models import Paper

logger = logging.getLogger(__name__)


def deduplicate_by_doi(papers: list[Paper]) -> list[Paper]:
    """
    Remove repeated records, identified by DOI.

    Records without a DOI are all retained. They cannot be compared on the
    field this function deduplicates by, and falling back to title comparison
    would risk merging two genuinely different papers whose titles resemble
    each other. That failure is worse than the one it prevents: a duplicate is
    visible in the output, whereas a paper silently discarded is not. The
    diagram specifies deduplication by DOI, so the absence of one is reported
    rather than worked around.

    The first occurrence is kept, so where the same paper arrives under two
    sub-questions the earlier retrieval survives. Order is otherwise
    preserved, which keeps a run's output comparable between executions.
    """
    seen: set[str] = set()
    unique: list[Paper] = []
    duplicates = 0

    for paper in papers:
        if paper.doi is None:
            # Retained deliberately, not overlooked. Logged so the count of
            # unverifiable records in a run is recoverable afterwards.
            logger.debug("Retaining record with no DOI: %r", paper.title)
            unique.append(paper)
            continue

        # Comparison is safe without normalising here, because Paper lowercases
        # and strips the DOI on construction. Doing it once at the boundary
        # rather than at each comparison is what makes that possible.
        if paper.doi in seen:
            duplicates += 1
            logger.debug("Duplicate DOI discarded: %s", paper.doi)
            continue

        seen.add(paper.doi)
        unique.append(paper)

    logger.info(
        "Deduplication: %d records in, %d out, %d duplicates removed",
        len(papers),
        len(unique),
        duplicates,
    )
    return unique


def validate_dois_and_metadata(papers: list[Paper]) -> list[Paper]:
    """
    Check every record against Crossref and return them with the outcome set.

    A failure to reach Crossref is deliberately not caught here. Recording it
    as an unverified result would conflate an infrastructure fault with a
    verification finding, which is the same conflation the status-code
    handling at stage 1 exists to prevent. Retryable failures have already
    been absorbed by the client, so anything reaching this point is terminal
    and the caller needs to hear about it rather than read it as evidence
    about a paper.

    Called once per paper. The ad-hoc commands used during development called
    verify twice per record, which doubled Crossref requests for no benefit.
    """
    validated = [verify(paper) for paper in papers]

    verified_count = sum(1 for paper in validated if paper.doi_verified)
    logger.info(
        "Validation: %d of %d records verified against Crossref",
        verified_count,
        len(validated),
    )
    return validated