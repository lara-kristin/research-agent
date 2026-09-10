"""
Retrieval Agent.

Retrieves evidence for one sub-question and judges whether the result meets a
configured threshold. Mirrors the RetrievalAgent class in Diagram 1, which
holds a literature search client and a record threshold.

The agent judges its own result but does not act on that judgement: when the
threshold is unmet it reports the fact, and the orchestrator decides whether a
reformulation is warranted. Diagram 2 routes that request through the
orchestrator rather than directly to the Planning Agent, so that the retry
limit is enforced in one deterministic place.
"""

import logging

from src.models import Paper, SubQuestion
from src.semantic_scholar import search

logger = logging.getLogger(__name__)

# Three usable records, against a default of five requested per sub-question:
# a majority of what was asked for. Unlike the request timeout, this number
# rests on no measurement, so it is named here rather than buried in a
# condition, and is expected to be revised once there is evidence of how often
# it triggers and whether the reformulated queries retrieve better.
RECORD_THRESHOLD = 3


def retrieve_evidence(
    sub_question: SubQuestion, limit: int = 5, use_cache: bool = True
) -> list[Paper]:
    """
    Search for one sub-question and return the papers found.

    Uses search_query rather than text: the researcher approved both at the
    first checkpoint, and only the query is meant for a keyword endpoint.
    """
    logger.info(
        "Retrieving for sub-question %d with query %r",
        sub_question.id,
        sub_question.search_query,
    )
    return search(sub_question.search_query, limit=limit, use_cache=use_cache)


def count_usable(papers: list[Paper]) -> int:
    """
    Count the records that carry the evidence signal later stages need.

    A record without an abstract cannot be relevance-scored, so it contributes
    nothing to the question of whether enough evidence was found. Semantic
    Scholar does not return abstracts for every publisher, so this is a
    condition observed in ordinary use rather than an edge case: a search can
    return three records of which only one is assessable.

    Diagram 3 branches on usable records rather than on records retrieved,
    so counting all of them would diverge from the design as well as
    overstate the evidence.
    """
    return sum(1 for paper in papers if paper.abstract)


def assess_threshold(papers: list[Paper]) -> bool:
    """
    Report whether a result set meets the configured threshold.

    Counts usable records rather than assessing their relevance. Relevance is
    the Evaluation Agent's work and needs the model; a count is deterministic
    and stays here.

    Records without an abstract are still retained and reported to the
    researcher. They do not count towards the threshold, which is a different
    question from whether they are worth keeping.
    """
    usable = count_usable(papers)
    met = usable >= RECORD_THRESHOLD

    if usable < len(papers):
        logger.info(
            "%d of %d records carry an abstract and can be assessed downstream",
            usable,
            len(papers),
        )

    logger.info(
        "Threshold %s: %d usable records against a threshold of %d",
        "met" if met else "unmet",
        usable,
        RECORD_THRESHOLD,
    )
    return met