"""
Logging configuration, kept in one place so every module logs consistently.

The design proposal commits to recording queries, relevance scores and
decisions for post-run inspection. Logging rather than printing is what makes
that possible: print writes to the screen and is gone, whereas a log record
carries a level, a timestamp and its source module, and can be written to a
file for inspection after a run has finished.
"""

import logging
import sys


def configure(level: int = logging.INFO) -> None:
    """
    Configure logging for a run. Called once, from the entry point.

    Two destinations by design. The console shows a run in progress, which is
    what a demonstration needs. The file preserves the same records for
    post-run inspection, which is what the design proposal requires and what
    a screenshot cannot provide.
    """
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-8s %(name)s | %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            # Appends rather than overwrites, so a run does not destroy the
            # record of the one before it.
            logging.FileHandler("run.log", mode="a", encoding="utf-8"),
        ],
    )