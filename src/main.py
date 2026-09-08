"""
Entry point. Run with: python -m src.main "your query here"

Kept separate from the orchestrator so that the orchestrator's functions stay
importable and testable without argument parsing or logging setup running as a
side effect. This module is the only place that configures logging, because
configuring it more than once would attach duplicate handlers and print every
record twice.
"""

import argparse
import logging
import sys

from src.clients import RetryableHTTPError
from src.interface import review_sub_questions
from src.llm import LLMResponseError
from src.llm import MissingAPIKeyError as MissingLLMKeyError
from src.logging_setup import configure
from src.models import Decision, SubQuestion
from src.orchestrator import (
    deduplicate_by_doi,
    retrieve_for_plan,
    save_papers,
    validate_dois_and_metadata,
)
from src.planning_agent import plan_research
from src.semantic_scholar import MissingAPIKeyError

# Named explicitly rather than taken from __name__. Running a module with -m
# sets __name__ to "__main__", which would label this file's log records
# differently from every other module's in the same run.
logger = logging.getLogger("src.main")


def plan_with_review(question: str) -> list[SubQuestion]:
    """
    Decompose the question and revise until the researcher approves.

    The loop lives here rather than in the Planning Agent or the interface,
    because Diagram 2 places it in the orchestrator's control flow: the agent
    produces a plan, the interface collects a verdict, and neither decides
    whether to go round again.

    Deliberately uncapped. The design proposal leaves revision at this
    checkpoint unrestricted and caps only the later ones, on the grounds that
    correcting here costs one model call whereas correcting after retrieval
    costs searches and repeated validation. Each iteration is a human choosing
    to revise, so there is no runaway to guard against.

    Approval is recorded on the sub-questions themselves rather than implied
    by returning from this function, so a later stage cannot mistake an
    unreviewed plan for an approved one.
    """
    feedback = None
    while True:
        sub_questions = plan_research(question, feedback)
        decision, feedback = review_sub_questions(sub_questions)

        if decision is Decision.APPROVE:
            return [sq.model_copy(update={"approved": True}) for sq in sub_questions]


def main() -> int:
    """
    Run the retrieval pipeline and return an exit code.

    Returns a code rather than calling sys.exit directly, so the sequence
    remains callable from a test. Zero results returns 0: a search that
    matched nothing is a successful request, and the distinction is the same
    one the pipeline preserves throughout.
    """
    parser = argparse.ArgumentParser(description="Retrieve and validate academic papers.")
    parser.add_argument("query", help="the research question to investigate")
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="maximum records to retrieve per sub-question",
    )
    args = parser.parse_args()

    configure()

    # The three failures below are the ones a user can act on: a missing
    # credential, and a service that stayed unavailable across every retry.
    # Anything else is a defect and should surface with its traceback rather
    # than be reported as though it were expected.
    try:
        sub_questions = plan_with_review(args.query)
    except MissingLLMKeyError as exc:
        logger.error("%s", exc)
        return 1
    except LLMResponseError as exc:
        logger.error("Planning failed: %s", exc)
        return 1
    except KeyboardInterrupt:
        # The checkpoint waits on input, so this is the ordinary way to stop a
        # run rather than a fault. Reported as such, and nothing has been
        # searched or saved at this point.
        print()
        logger.info("Cancelled at sub-question review. Nothing was searched.")
        return 1

    logger.info(
        "Approved plan: %s",
        "; ".join(f"{sq.id}={sq.search_query}" for sq in sub_questions),
    )

    try:
        papers = retrieve_for_plan(sub_questions, limit=args.limit)
    except MissingAPIKeyError as exc:
        logger.error("%s", exc)
        return 1
    except RetryableHTTPError as exc:
        # Retrieval spans several searches, so this can arrive part-way
        # through. Any records already retrieved are discarded rather than
        # saved, because a brief covering some sub-questions and silently
        # omitting others would misrepresent the search it claims to report.
        logger.error("Semantic Scholar unavailable after repeated attempts: %s", exc)
        return 1
    except LLMResponseError as exc:
        # Reformulation needs the model, so a planning failure can occur here
        # as well as at decomposition.
        logger.error("Query reformulation failed: %s", exc)
        return 1

    if not papers:
        logger.info("No matching papers for any sub-question. Nothing to validate or save.")
        return 0

    papers = deduplicate_by_doi(papers)

    try:
        papers = validate_dois_and_metadata(papers)
    except RetryableHTTPError as exc:
        # Retrieval succeeded, so the records exist and are worth keeping. They
        # are saved unverified rather than discarded, because a Crossref
        # outage is a fact about the service and not about the papers.
        logger.error("Crossref unavailable, saving records unverified: %s", exc)

    markdown_path, json_path = save_papers(papers, args.query)
    logger.info("Done. %s and %s", markdown_path, json_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())