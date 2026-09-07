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
from src.logging_setup import configure
from src.orchestrator import (
    deduplicate_by_doi,
    save_papers,
    validate_dois_and_metadata,
)
from src.semantic_scholar import MissingAPIKeyError, search

# Named explicitly rather than taken from __name__. Running a module with -m
# sets __name__ to "__main__", which would label this file's log records
# differently from every other module's in the same run.
logger = logging.getLogger("src.main")


def main() -> int:
    """
    Run the retrieval pipeline and return an exit code.

    Returns a code rather than calling sys.exit directly, so the sequence
    remains callable from a test. Zero results returns 0: a search that
    matched nothing is a successful request, and the distinction is the same
    one the pipeline preserves throughout.
    """
    parser = argparse.ArgumentParser(description="Retrieve and validate academic papers.")
    parser.add_argument("query", help="search query")
    parser.add_argument("--limit", type=int, default=10, help="maximum records to retrieve")
    args = parser.parse_args()

    configure()

    # The three failures below are the ones a user can act on: a missing
    # credential, and a service that stayed unavailable across every retry.
    # Anything else is a defect and should surface with its traceback rather
    # than be reported as though it were expected.
    try:
        papers = search(args.query, limit=args.limit)
    except MissingAPIKeyError as exc:
        logger.error("%s", exc)
        return 1
    except RetryableHTTPError as exc:
        logger.error("Semantic Scholar unavailable after repeated attempts: %s", exc)
        return 1

    if not papers:
        logger.info("No matching papers. Nothing to validate or save.")
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