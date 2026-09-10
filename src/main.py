"""
Entry point. Run with: python -m src.main "your research question"

Reduced to four responsibilities: parse arguments, configure logging, call the
orchestrator, and translate the outcome into an exit code. The run sequence
itself lives in the orchestrator, because the design proposal makes that the
central coordinator and Diagram 1 places both review presentations on it. An
earlier version held the sequence here, which left the orchestrator holding
orchestration functions while the entry point did the orchestrating.

This is also the only module that configures logging. Configuring it more than
once would attach duplicate handlers and print every record twice.
"""

import argparse
import logging
import sys

from src.clients import QuotaExhaustedError, RetryableHTTPError
from src.llm import LLMResponseError
from src.llm import MissingAPIKeyError as MissingLLMKeyError
from src.logging_setup import configure
from src.orchestrator import run_research, save_papers
from src.semantic_scholar import MissingAPIKeyError

# Named explicitly rather than taken from __name__. Running a module with -m
# sets __name__ to "__main__", which would label this file's log records
# differently from every other module's in the same run.
logger = logging.getLogger("src.main")


def main() -> int:
    """
    Run the pipeline and return an exit code.

    Returns a code rather than calling sys.exit directly, so the sequence
    remains callable from a test. Zero results returns 0: a search that
    matched nothing is a successful request, and the distinction is the one
    the pipeline preserves throughout.
    """
    parser = argparse.ArgumentParser(description="Retrieve and validate academic papers.")
    parser.add_argument("query", help="the research question to investigate")
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="maximum records to retrieve per sub-question",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="bypass the response cache and issue every request live",
    )
    args = parser.parse_args()

    configure()

    # Stated at the start of every run. A cached run and a live run must not be
    # indistinguishable: a demonstration replaying stored answers while
    # appearing to exercise the live services would misrepresent the system.
    # Individual hits are logged as they occur; this line establishes which
    # kind of run a reader is looking at before the first request is made.
    if args.no_cache:
        logger.info("Cache bypassed: every request will be issued live")
    else:
        logger.info(
            "Response cache enabled; entries under 24 hours old will be reused. "
            "Use --no-cache to force live requests"
        )

    # Each of these is a condition the person running the system can act on: a
    # missing credential, a service that stayed unavailable across every
    # retry, an exhausted daily allowance, or a model response that could not
    # be used. Anything else is a defect and surfaces with its traceback
    # rather than being reported as though it were expected.
    try:
        result = run_research(args.query, limit=args.limit, use_cache=not args.no_cache)
    except (MissingAPIKeyError, MissingLLMKeyError) as exc:
        logger.error("%s", exc)
        return 1
    except QuotaExhaustedError as exc:
        # Reported separately because the remedy differs: no amount of waiting
        # within a run will help, and the allowance resets on a schedule the
        # client cannot influence.
        logger.error("LLM quota exhausted, not retryable within this run: %s", exc)
        return 1
    except RetryableHTTPError as exc:
        # Retrieval spans several searches, so this can arrive part-way
        # through. Records already retrieved are discarded rather than saved,
        # because a brief covering some sub-questions and silently omitting
        # others would misrepresent the search it claims to report.
        logger.error("A service was unavailable after repeated attempts: %s", exc)
        return 1
    except LLMResponseError as exc:
        logger.error("The model returned no usable response: %s", exc)
        return 1
    except KeyboardInterrupt:
        # Both checkpoints wait on input, so this is the ordinary way to stop a
        # run rather than a fault.
        print()
        logger.info("Cancelled at a review checkpoint. Nothing was saved.")
        return 1

    if result is None:
        logger.info(
            "Run stopped after a second scope rejection. Consider rephrasing the "
            "research question and starting again."
        )
        return 1

    papers, _assessments = result

    if not papers:
        logger.info("No approved evidence. Nothing to save.")
        return 0

    markdown_path, json_path = save_papers(papers, args.query)
    logger.info("Done. %s and %s", markdown_path, json_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())